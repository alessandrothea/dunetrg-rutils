#!/usr/bin/env python

import sys
from pathlib import Path

import click

from rich import print


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('hist_file', metavar='HIST_FILE', type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option('--output-dir', '-o', type=click.Path(file_okay=False), default='.', show_default=True,
              help='Directory to write output PNGs.')
@click.option('--n-top', type=int, default=30, show_default=True,
              help='Number of top generators to show in the by-generator plot.')
def cli(hist_file, output_dir, n_top):
    import ROOT
    import matplotlib.pyplot as plt
    import mplhep as hep

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    f = ROOT.TFile.Open(hist_file)
    if not f or f.IsZombie():
        click.echo(f"Error: could not open {hist_file}", err=True)
        sys.exit(1)

    ke_by_gen_dir = f['kinetic_energy_by_generator_name']
    ke_by_pdg_dir = f['kinetic_energy_by_pdg']

    ke_by_gen_hists = {k.GetName(): ke_by_gen_dir[k.GetName()] for k in ke_by_gen_dir.GetListOfKeys()}
    ke_by_gen_sorted = sorted(ke_by_gen_hists.items(), key=lambda x: x[1].Integral(), reverse=True)

    ke_by_pdg_hists = {k.GetName(): ke_by_pdg_dir[k.GetName()] for k in ke_by_pdg_dir.GetListOfKeys()}

    # Plot 1: total kinetic energy
    fig, ax = plt.subplots()
    hep.histplot(ke_by_gen_sorted[0][1], ax=ax, color='k', yerr=False)
    ax.set_yscale('log')
    ax.set_ylabel('Entries')
    ax.set_xlabel('Kinetic Energy [GeV]')
    fig.tight_layout()
    fig.savefig(out / 'ke_total.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved [bold]ke_total.png[/bold]")

    # Plot 2: top N generators overlaid
    top_bkg = dict(ke_by_gen_sorted[1:1 + n_top])
    fig, ax = plt.subplots(figsize=(20, 14))
    for n, h in top_bkg.items():
        hep.histplot(h, ax=ax, label=n, yerr=False)
    ax.set_yscale('log')
    ax.set_ylim(ymin=1)
    ax.set_ylabel('Entries')
    ax.set_xlabel('Kinetic Energy [GeV]')
    ax.legend()
    fig.savefig(out / 'ke_by_generator.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved [bold]ke_by_generator.png[/bold]")

    # Plot 3: by PDG / particle type
    fig, ax = plt.subplots(figsize=(10, 7))
    for n, h in ke_by_pdg_hists.items():
        hep.histplot(h, ax=ax, label=n, yerr=False)
    ax.set_yscale('log')
    ax.set_ylim(ymin=1)
    ax.set_ylabel('Entries')
    ax.set_xlabel('Kinetic Energy [GeV]')
    ax.legend()
    fig.savefig(out / 'ke_by_pdg.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved [bold]ke_by_pdg.png[/bold]")

    f.Close()


if __name__ == '__main__':
    cli()
