#!/usr/bin/env python


# # Enable multi-threading with the specified amount of threads (let's start with just one)
# # Note that in newer ROOT versions you simply need to write ROOT.EnableImplicitMT()

from rich import print
import click
from pathlib import Path
import concurrent.futures


def make_vector_filter(df, condition: str, exclude: list[str] = []):
    """
    Applies a boolean mask derived from `condition` to all vector branches
    discovered from the RDataFrame itself. The condition must be an
    RVec-compatible expression that returns a vector<bool>, e.g. "sot > 7".

    Returns a new RDataFrame with all vector branches filtered in-place.
    """
    vector_branches = [
        str(name)
        for name in df.GetColumnNames()
        if df.GetColumnType(name).startswith("ROOT::VecOps::RVec<")
        and name not in exclude
    ]

    # for name in df.GetColumnNames():
        # print(name, f"'{df.GetColumnType(name)}'", df.GetColumnType(name).startswith("ROOT::VecOps::RVec<"), name not in exclude)

    print(f"Found vector branches: '{vector_branches}'")
    df = df.Define("mask", condition)

    for name in vector_branches:
        df = df.Redefine(name, f"{name}[mask]")

    return df, vector_branches


def process_ntuple(k, nt_path, outdir, cfg, n_total):

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

    p = Path(nt_path)
    width = len(str(n_total))
    outpath = f'{outdir}/{p.stem}_slimmed_{k:0{width}d}of{n_total}{p.suffix}'
    print(f"Saving fixed slimmed to {outpath}")


    rso = ROOT.RDF.RSnapshotOptions()
    rso.fMode = "UPDATE"
    if cfg['save_as_rtuple']:
        rso.fOutputFormat = ROOT.RDF.ESnapshotOutputFormat.kRNTuple

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

    print(tp_tree_names)
    # tp_tree_names = []
    for t in tp_tree_names:
        rdf = ROOT.RDataFrame(f'triggerAna/{t}', nt_path)
        for n, c in cfg['tp_cut'].items():
            if add_ev_uid:
                rdf = rdf.Define("event_uid", event_uid_func)
            # rdf = rdf.Filter(c, n)

            rdf, v = make_vector_filter(rdf, c)
        rdf.Snapshot(f'triggerAna/{t}', outpath, options=rso)

    with ROOT.TFile(outpath, "UPDATE") as outfile:
        outfile['triggerAna'].WriteObject(info_obj, 'info')

    return outpath


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('ntuple_files', type=click.Path(dir_okay=False, exists=True), nargs=-1)
@click.option('-m', '--mode', type=click.Choice(['bkg', 'nu', 'pgun']), default='data')
@click.option('-w', '--num-workers', type=click.IntRange(0,40), default=30)
@click.option('-o', '--outdir', type=click.Path(file_okay=False), default='data')
@click.option('-f', '--filelist', type=click.Path(dir_okay=False, exists=True), default=None,
              help='Text file with one input .root file path per line')
def main(ntuple_files, mode, outdir, filelist, num_workers):

    if filelist:
        extra = Path(filelist).read_text().splitlines()
        ntuple_files = list(ntuple_files) + [p for p in extra if p.strip() and not p.startswith('#')]

    cfg = {
        'top_trees_mask': [
            'event_summary',
            'simide_summary',
        ],
        # NOTE: In the new TTree format, there can o
        'tp_cut': {
            'tp_filter': '(adc_peak > 45) & (samples_over_threshold >= 9)'
        },
        'add_ev_uid': False,
        'save_as_rtuple': False
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
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:

        n_total = len(ntuple_files)
        future_to_outpaths = {executor.submit(process_ntuple, k, nt_path, outdir, cfg, n_total): k for k, nt_path in enumerate(ntuple_files)}
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
