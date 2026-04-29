#!/usr/bin/env python

import ROOT
import numpy as np

import pandas as pd
import matplotlib.pyplot as plt
from rich import print

def draw_ke_spectrum(mct_ke_df, figname):
    max_ke = mct_ke_df.kinetic_energy.max()
    max_ke = 5e-3
    num_bkg=20

    print("Grouping mctruth objects")

    part_by_gen = sorted([(n,df) for n,df in mct_ke_df.groupby('generator_name')], reverse=True, key=lambda x: len(x[1]))
    top_by_gen = part_by_gen[:num_bkg]
    print("Grouping completed")

    all_gens = mct_ke_df.generator_name.unique()
    colors = plt.cm.tab10.colors 
    color_map = {pdg: colors[i % len(colors)] for i, pdg in enumerate(all_gens)}

    bins=np.linspace(0,max_ke*1000,200)
    fig,axes=plt.subplots(1,1, figsize=(12,10))

    ax=axes
    print("Creating histograms")
    for gen_id, df in top_by_gen:

        (df.kinetic_energy*1000).hist(bins=bins, label=f"{gen_id}", histtype='step', ax=ax)

    ax.legend()
    ax.set_yscale('log')
    ax.set_ylabel('counts')
    ax.set_xlabel(r'$E_{kin}$')
    ax.set_title('MCThruths particles')

    fig.savefig(figname)

ROOT.EnableImplicitMT()

datapath='data/radbkg/data-fixed/radiological_decay0_dunevd10kt_1x8x6_patched_wall_gammas_2337894_9_evfix_ana.ntuple.root'
datapath='data/radbkg/data-fixed/*_ana.ntuple.root'
# datapath='~/devel/dune-trigger/eos-vd-miniprod/radiological_decay0_dunevd10kt_1x8x6_patched_wall_gammas_batch2/ana/*.root'

rdf = ROOT.RDataFrame(f'triggerAna/mctruths', datapath)

ROOT.RDF.Experimental.AddProgressBar(rdf)

print("[yellow]Importing data into memory[/yellow]")

arr = rdf.AsNumpy(columns=["generator_name", "kinetic_energy", "pdg"])

print("[yellow]Data loading in memory completed[/yellow]")

mct_ke = pd.DataFrame(arr)

# Electrons
draw_ke_spectrum( mct_ke, 'mc_ke_all.pdf')
draw_ke_spectrum( mct_ke.query('pdg==11'), 'mc_ke_electrons.pdf')
draw_ke_spectrum( mct_ke.query('pdg==22'), 'mc_ke_gammas.pdf')
