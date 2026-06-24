#!/usr/bin/env python

import sys

import click

from rich import print

from dunetrg_rutils.utils import resolve_input_files


@click.command()
@click.option('--check-mctruth', is_flag=True, default=False)
@click.option('--output-hist-file', type=click.Path(exists=False, file_okay=True, dir_okay=False), default='mctruth_hists.root')
@click.argument('inputs', nargs=-1, required=True, metavar='FILE/GLOB/LIST...')
def cli(inputs, output_hist_file, check_mctruth):
    files = resolve_input_files(list(inputs))
    if not files:
        click.echo("Error: no ROOT files resolved from the given inputs.", err=True)
        sys.exit(1)
    print(f"Processing {len(files)} file(s):")

    import ROOT
    import json


    files_map_not_found = []

    master_mcthruth_blockid_map = {}


    for f in files:
        # print(f"  {f}")
        f = ROOT.TFile(f)

        info_obj = f['triggerAna/info']
        info = json.loads(info_obj.GetTitle())
        if 'mctruth_blockid_map' not in info:
            files_map_not_found.append(f)
            continue

        mctruth_blockid_map = info['mctruth_blockid_map']
        for id, name in mctruth_blockid_map:
            if name not in master_mcthruth_blockid_map:
                master_mcthruth_blockid_map[name] = set()

            master_mcthruth_blockid_map[name].add(id)

    print(f"Files with no mctruth map: {files_map_not_found}")

    print(master_mcthruth_blockid_map)

    ROOT.EnableImplicitMT()
    import dunetrg_rutils.uv as uv
    import particle

    rdf = ROOT.RDataFrame(f'triggerAna/mctruths', files)

    var_bins = (150, 0., 0.015)
    var_name='kinetic_energy'
    var_title='Kinetic Energy'

    output_file = ROOT.TFile(output_hist_file, "RECREATE")

    def make_histos( var_name, var_title, var_bins, group_by, groups, output_file):
        # pass

        histos = {}
        histos['all'] = (
            rdf
            .Histo1D((var_name, var_title, *var_bins), var_name)
        )

        # for block_id, gen_name in master_mcthruth_blockid_map:
        for g_val, g_name in groups.items():
            print(f"Scheduling {group_by}=={g_name}")
            histos[g_name] = (
                rdf
                .Define(f"{var_name}_{g_name}", f'{var_name}[{group_by} == {g_val}]')
                .Histo1D((str(g_name), f"{var_title} [{g_name}])", *var_bins), f"{var_name}_{g_name}")
            )

        var_dir = output_file.mkdir(f"{var_name}_by_{group_by}")
        var_dir.cd()

        for h in histos.values():
            print(f"Writing {h.GetName()}")
            h.SetDirectory(var_dir)
            h.Write()

    group_by='generator_name'
    groups = { f'"{gen_name}"':gen_name for gen_name in master_mcthruth_blockid_map }

    make_histos(
        var_name,
        var_title,
        var_bins,
        group_by,
        groups,
        output_file
    )

    group_by = 'pdg'
    groups = {
            1000020040: 'He4', #'$^{4}\\mathrm{He}$',
            11: 'eminus', #'$e^{-}$',
            -11: 'eplus', #'$e^{+}$',
            22: 'gamma', #'$\\gamma$'
        }

    make_histos(
        var_name,
        var_title,
        var_bins,
        group_by,
        groups,
        output_file
    )

    output_file.Close()

if __name__ == '__main__':
    cli()
