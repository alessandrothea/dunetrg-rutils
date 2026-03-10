#!/usr/bin/env python


# # Enable multi-threading with the specified amount of threads (let's start with just one)
# # Note that in newer ROOT versions you simply need to write ROOT.EnableImplicitMT()
# ROOT.EnableImplicitMT()

from rich import print
import click
from pathlib import Path
import re
import concurrent.futures


def process_ntuple(k, nt_path, outdir, cfg):

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
            tree_names  = [k.GetName() for k in infile['triggerAna'].GetListOfKeys() if k.GetClassName()=='TTree']
            tp_tree_names  = [f'TriggerPrimitives/{k.GetName()}' for k in infile['triggerAna/TriggerPrimitives'].GetListOfKeys() if k.GetClassName()=='TTree' and k.GetName().startswith('tpmakerTPC') ]
    except OSError:
        print(f"Failed to open file {k} - skipping")
        return None

    outpath=f'{outdir}/{Path(nt_path).name}'
    print(f"Saving fixed slimmed to {outpath}")


    rso = ROOT.RDF.RSnapshotOptions()
    rso.fMode = "UPDATE"
    # rso.fOutputFormat = ROOT.RDF.ESnapshotOutputFormat.kRNTuple

    tree_names = [ t for t in tree_names if t in cfg['top_trees_mask']]


    # Create an empty file
    with ROOT.TFile.Open(outpath, "RECREATE") as outfile:
        pass

    add_ev_uid = cfg['add_ev_uid']
    event_uid_func = "uint64_t ev_uid = run*(uint64_t)1000000+subrun*100+event; return ev_uid;"

    for t in tree_names:
        rdf = ROOT.RDataFrame(f'triggerAna/{t}', nt_path)
        if add_ev_uid:
            rdf = rdf.Define("event_uid", event_uid_func)
        rdf.Snapshot(f'triggerAna/{t}', outpath, options=rso)

    # print(tp_tree_names)
    # tp_tree_names = []
    for t in tp_tree_names:
        rdf = ROOT.RDataFrame(f'triggerAna/{t}', nt_path)
        for n, c in cfg['tp_cut'].items():
            if add_ev_uid:
                rdf = rdf.Define("event_uid", event_uid_func)
            rdf = rdf.Filter(c, n)            
        rdf.Snapshot(f'triggerAna/{t}', outpath, options=rso)

    with ROOT.TFile(outpath, "UPDATE") as outfile:
        outfile['triggerAna'].WriteObject(info_obj, 'info')

    return outpath


@click.command()
@click.argument('ntuple_files', type=click.Path(dir_okay=False, exists=True), nargs=-1)
@click.option('-m', '--mode', type=click.Choice(['bkg', 'nu', 'pgun']), default='data')
@click.option('-o', '--outdir', type=click.Path(file_okay=False), default='data')
def main(ntuple_files, mode, outdir):


    cfg = {
        'top_trees_mask': [
            'event_summary',
        ],
        'tp_cut': {
            'sot_cut': 'samples_over_threshold > 7'
        },
        'add_ev_uid': True
    }

    match mode:
        case 'bkg':
            pass
        case 'nu':
            cfg['top_trees_mask'] += [
                'mctruths',
                'mcneutrinos'                
            ]
        case 'pgun':
            cfg['top_trees_mask'] += [
                'mctruths',
            ]
        case _:
            raise click.Error(f"Uknown mode! {mode}")
        
    print(cfg)

    outdir = Path(outdir)
    if not outdir.exists():
        outdir.mkdir(parents=True)

        print(f"Created '{outdir}'")


    # with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
    with concurrent.futures.ProcessPoolExecutor(max_workers=30) as executor:

        future_to_outpaths = {executor.submit(process_ntuple, k, nt_path, outdir, cfg):k for k, nt_path in enumerate(ntuple_files)}
        for future in concurrent.futures.as_completed(future_to_outpaths):
            k = future_to_outpaths[future]
            try:
                data = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (k, exc))
                print(type(exc))
            else:
                print(f"File {data} completed")


if __name__ == '__main__':
    main()