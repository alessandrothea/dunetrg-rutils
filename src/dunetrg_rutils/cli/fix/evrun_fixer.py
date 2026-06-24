#!/usr/bin/env python


# # Enable multi-threading with the specified amount of threads (let's start with just one)
# # Note that in newer ROOT versions you simply need to write ROOT.EnableImplicitMT()
# ROOT.EnableImplicitMT()

from rich import print
import click
from pathlib import Path
import re
import concurrent.futures

def process_ntuple(k, nt_path, nt_base, outdir):

    # Ready to go, let's load ROOT
    import ROOT

    ROOT.EnableImplicitMT()

    if nt_path.startswith('/eos/project/'):
        nt_path='root://eosproject.cern.ch/'+nt_path
    print(f"Processing file {k}: {nt_path}")
    info_obj = None
    tree_names = []
    tp_tree_names = []

    try:
        with ROOT.TFile.Open(nt_path) as infile:
            # infile['triggerAna'].ls()
            info_obj = infile['triggerAna/info']
            tree_names  = [key.GetName() for key in infile['triggerAna'].GetListOfKeys() if key.GetClassName()=='TTree']
            tp_tree_names  = [f'TriggerPrimitives/{key.GetName()}' for key in infile['triggerAna/TriggerPrimitives'].GetListOfKeys() if key.GetClassName()=='TTree']
    except OSError:
        print(f"Failed to open file {k} - skipping")
        return None

    outpath=f'{outdir}/{nt_base}_{k[0]}_{k[1]}_evfix_ana.ntuple.root'
    print(f"Saving fixed ntuples to {outpath}")


    with ROOT.TFile(outpath, "RECREATE") as outfile:
        outfile.mkdir('triggerAna')
        # outfile['triggerAna'].WriteObject(info_obj, 'info')


    rso = ROOT.RDF.RSnapshotOptions()
    rso.fMode = "UPDATE"
    # rso.fOutputFormat = ROOT.RDF.ESnapshotOutputFormat.kRNTuple

    run_no, job_no = k

    for t in tree_names+tp_tree_names:
        rdf = ROOT.RDataFrame(f'triggerAna/{t}', nt_path)
        rdf_up = rdf.Redefine('event', f'event+{job_no*10}')
        rdf_up = rdf_up.Redefine('run', f'{run_no}')
        rdf_up.Snapshot(f'triggerAna/{t}', outpath, options=rso)

    with ROOT.TFile(outpath, "UPDATE") as outfile:
        outfile['triggerAna'].WriteObject(info_obj, 'info')

    return outpath


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('ntuple_files', type=click.Path(dir_okay=False, exists=True), nargs=-1)
@click.option('-o', '--outdir', type=click.Path(file_okay=False), default='data')
def main(ntuple_files, outdir):
    """Utility script to fix duplicated event numbers in grid jobs.

    The event numners are overwritten adding 10*<job number> to the original event number.

    Args:
        ntuple_files (_type_): _description_
        outdir (_type_): _description_

    Returns:
        _type_: _description_
    """
    ntuple_regex = re.compile(r'(.*)_(\d+)_(\d+)_ana\.ntuple\.root$')
    no_match = []
    ntuple_list = {}
    for ntf in ntuple_files:
        m  = ntuple_regex.match(Path(ntf).name)
        if m:
            ntuple_list[(int(m.group(2)), int(m.group(3)))] = (ntf, m.group(1))
        else:
            no_match.append(ntf)

    if no_match:
        print("Found file names without job id:")
        for ntf in no_match:
            print(f"- {ntf}")


    print(f"Found {len(ntuple_files)} to fix")
    print(ntuple_files)
    # return


    # with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
    with concurrent.futures.ProcessPoolExecutor(max_workers=30) as executor:
        future_to_outpaths = {executor.submit(process_ntuple, k, nt_path, nt_base, outdir):k for k, (nt_path, nt_base) in ntuple_list.items()}
        for future in concurrent.futures.as_completed(future_to_outpaths):
            k = future_to_outpaths[future]
            try:
                data = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (k, exc))
            else:
                print(f"File {data} completed")


if __name__ == '__main__':
    main()
