#!/usr/bin/env python


import click
import ROOT

@click.command()
@click.argument('ntuple_files', type=click.Path(dir_okay=False, exists=True), nargs=-1)
def main(ntuple_files):

    max_ts = 0
    for f in ntuple_files:
        rdf = ROOT.RDataFrame(f'triggerAna/simides', f)

        f_max_ts = rdf.Max('timestamp').GetValue()
        print(f, f_max_ts)

        max_ts = max(max_ts, f_max_ts)

    print(f">>> max_ts={max_ts} <<<")


if __name__ == '__main__':
    main()