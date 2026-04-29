#!/usr/bin/env python

import ROOT
import numpy as np

import pandas as pd
import matplotlib.pyplot as plt
from rich import print

datapath='data/radbkg/data-fixed/radiological_decay0_dunevd10kt_1x8x6_patched_wall_gammas_2337894_9_evfix_ana.ntuple.root'
datapath='~/devel/dune-trigger/eos-vd-miniprod/radiological_decay0_dunevd10kt_1x8x6_patched_wall_gammas_batch2/ana/*.root'
datapath='/home/thea/devel/dune-trigger/dune-trg-utilities/data/vd-1x8x14_radbkg_pipeline_5221880_anatree.ntuple.root'

# TODO: read list from first file
mcthruth_blockid_map = [
        [
            28,
            "Rn220ChainFromPb212GenInUpperMesh1x8x6"
        ],
        [
            27,
            "CryostatNGammasAtLAr1x8x6"
        ],
        [
            26,
            "Kr85GenInLAr"
        ],
        [
            25,
            "U238ChainGenInAnode"
        ],
        [
            24,
            "K40GenInCathode"
        ],
        [
            23,
            "foamGammasAtLAr1x8x6"
        ],
        [
            22,
            "K42From42ArGenInUpperMesh1x8x6"
        ],
        [
            21,
            "Th232ChainGenInCathode"
        ],
        [
            20,
            "Rn222ChainRn222GenInLAr"
        ],
        [
            19,
            "U238ChainGenInCathode"
        ],
        [
            18,
            "K40GenInAnode"
        ],
        [
            17,
            "CavernwallNeutronsAtLAr1x8x6"
        ],
        [
            16,
            "Rn220ChainPb212GenInLAr"
        ],
        [
            15,
            "K42From42ArGenInLAr"
        ],
        [
            14,
            "Rn222ChainGenInPDS"
        ],
        [
            13,
            "Ar42GenInLAr"
        ],
        [
            12,
            "Rn222ChainFromBi210GenInUpperMesh1x8x6"
        ],
        [
            11,
            "Rn222ChainFromPo218GenInUpperMesh1x8x6"
        ],
        [
            10,
            "Rn222ChainPb210GenInLAr"
        ],
        [
            9,
            "Ar39GenInLAr"
        ],
        [
            8,
            "Rn222ChainPb214GenInLAr"
        ],
        [
            7,
            "Rn222ChainPo218GenInLAr"
        ],
        [
            6,
            "Rn222ChainFromPb214GenInUpperMesh1x8x6"
        ],
        [
            5,
            "Rn222ChainFromPb210GenInUpperMesh1x8x6"
        ],
        [
            4,
            "CavernwallGammasAtLAr1x8x6"
        ],
        [
            3,
            "Th232ChainGenInAnode"
        ],
        [
            2,
            "Rn222ChainFromBi214GenInUpperMesh1x8x6"
        ],
        [
            1,
            "Rn222ChainBi214GenInLAr"
        ],
        [
            0,
            "CavernNGammasAtLAr1x8x6"
        ]
    ]


ROOT.EnableImplicitMT()

rdf = ROOT.RDataFrame(f'triggerAna/mctruths', datapath)


ROOT.RDF.Experimental.AddProgressBar(rdf)


histos = {}
# for block_id, gen_name in mcthruth_blockid_map:
#     print(f"Scheduling {gen_name}")
#     histos[gen_name] = rdf.Filter(f'generator_name == "{gen_name}"').Histo1D((gen_name, f"Kinetic Energy {gen_name}", 150, 0., 0.015), 'kinetic_energy')

# draw_ke_spectrum( mct_ke, 'mc_ke_all.pdf')
# draw_ke_spectrum( mct_ke.query('pdg==11'), 'mc_ke_electrons.pdf')
# draw_ke_spectrum( mct_ke.query('pdg==22'), 'mc_ke_gammas.pdf')


pdg_map  = {
    'electrons': 11,
    'gammas': 22
}

for p_name, pdg_id in pdg_map.items():
    print(f"Scheduling {p_name}")
    histos[p_name] = rdf.Filter(f'pdg == {pdg_id}').Histo1D((p_name, f"Kinetic Energy {p_name}", 150, 0., 0.015), 'kinetic_energy')


output_file = ROOT.TFile("output.root", "RECREATE")
for h in histos.values():
    print(f"Writing {h.GetName()}")
    h.SetDirectory(output_file)
    h.Write()
    
output_file.Close()
