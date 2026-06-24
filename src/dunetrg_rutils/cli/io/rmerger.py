#!/usr/bin/env python
import click
from rich import print
from pathlib import Path
from math import log10, floor
from dunetrg_rutils.utils import resolve_input_files


def merge_unsafe(ntuple_files, outfile):
    print(f"Merging {len(ntuple_files)} files")
    import ROOT

    m = ROOT.TFileMerger()
    for i,f in enumerate(ntuple_files):
        print(i, type(f), f)
        m.AddFile(f)
    m.OutputFile(str(outfile))
    m.Merge()
    print(f"Merged {len(ntuple_files)} files into {outfile}")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument('inputs', nargs=-1, required=True, metavar='FILE/GLOB/LIST...')
@click.option('-m', '--max-files-per-chunk', type=int, default=500, help='Max files per chunk')
@click.option('-k', '--keep-tmp-files', is_flag=True, default=False, help='Keep temporaty files')
@click.option('-o', '--outfile', type=click.Path(exists=False), default='tfile_merged.root')
def main(inputs, max_files_per_chunk, keep_tmp_files, outfile):

    print(f'Merging {len(inputs)} files')
 
    ntuple_files = resolve_input_files(list(inputs))
    if not ntuple_files:
        click.echo("Error: no ROOT files resolved from the given inputs.", err=True)
        raise SystemExit(1)

    # max_files_per_chunk = 10

    num_files = len(ntuple_files)
    # num_files = 1000
    outfile = Path(outfile)
    if num_files/max_files_per_chunk  > 1:
        chunks = [ntuple_files[x:x+max_files_per_chunk] for x in range(0, num_files, max_files_per_chunk)]
        print(f'Merging {len(inputs)} in {len(chunks)} chunks')


        width = floor(log10(len(chunks))) + 1

        tmp_files = []
        for i,fs in enumerate(chunks):
            tmp_out = outfile.parent / (f'tmp_{i:0{width}d}_' + outfile.name)
            tmp_files.append(tmp_out)

            merge_unsafe(fs, tmp_out)


        merge_unsafe([str(f) for f in tmp_files], outfile)

        if not keep_tmp_files:
            for tmp_file in tmp_files:
                tmp_file.unlink(missing_ok=True)


    else:
        merge_unsafe(ntuple_files, outfile)


if __name__=='__main__':
    main()
