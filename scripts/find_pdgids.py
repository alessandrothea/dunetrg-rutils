#!/usr/bin/env python

import glob
import os
import sys

import click

from rich import print


def resolve_input_files(inputs):
    """Resolve a mix of ROOT files, globs, and list files into a flat list of ROOT files."""
    files = []
    for inp in inputs:
        if inp.endswith('.root') and os.path.isfile(inp):
            files.append(inp)
        elif '*' in inp or '?' in inp or '[' in inp:
            matched = sorted(glob.glob(inp, recursive=True))
            if not matched:
                click.echo(f"Warning: glob '{inp}' matched no files", err=True)
            files.extend(matched)
        elif os.path.isfile(inp):
            # Treat as a text file containing paths/globs
            with open(inp) as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            files.extend(resolve_input_files(lines))
        else:
            click.echo(f"Warning: '{inp}' is not a file or glob — skipping", err=True)
    return files


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('inputs', nargs=-1, required=True, metavar='FILE/GLOB/LIST...')
def cli(inputs):
    files = resolve_input_files(list(inputs))
    if not files:
        click.echo("Error: no ROOT files resolved from the given inputs.", err=True)
        sys.exit(1)
    print(f"Processing {len(files)} file(s):")

    import ROOT
    import dunetrg_rutils.uv as uv
    import particle

    ROOT.EnableImplicitMT()


    df = ROOT.RDataFrame('triggerAna/mctruths', files)
    # df = ROOT.RDataFrame('triggerAna/mcparticles', files)

    finder = uv.UniqueValueFinder(df)

    # Single branch — auto-detected type
    pdgs = finder.find("pdg")
    print(f"pdgs: {pdgs}")

    pdg_map = {}
    for p in pdgs:
        pp = particle.Particle.from_pdgid(p)
        print(pp)
        pdg_map[p] = f"${pp.latex_name}$"

    print(pdg_map)

    # # Callable shortcut
    # names = finder("generator_name")

    # # Multiple branches in one call
    # results = finder.find_many(["pdg", "generator_name", "run"])
    # for branch, values in results.items():
    #     print(f"{branch}: {len(values)} unique: {values}")

    # # # Works on filtered nodes too
    # # filtered = df.Filter("event_number > 1000")
    # # finder_f = UniqueValueFinder(filtered)
    # # rare_pdgs = finder_f.find("pdg")

    # # Inspect type parsing
    # print(finder.column_type("pdg"))  # ('int', True)


if __name__ == '__main__':
    cli()

