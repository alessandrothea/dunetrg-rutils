#!/usr/bin/env python3
"""Print on-disk and in-memory sizes of all TTrees and RNtuples found in ROOT file(s)."""

from pathlib import Path

import click
import ROOT  # noqa: must be importable
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def human(nbytes: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(nbytes) < 1024.0:
            return f"{nbytes:7.2f} {unit}"
        nbytes /= 1024.0
    return f"{nbytes:.2f} PiB"


# ---------------------------------------------------------------------------
# Recursive collector
# ---------------------------------------------------------------------------

def collect_objects(directory, path: str = "") -> list[dict]:
    """Recursively walk a TDirectory and collect every TTree and RNTuple."""
    results = []

    for key in directory.GetListOfKeys():
        classname = key.GetClassName()
        name      = key.GetName()
        full_path = f"{path}/{name}" if path else name

        if classname in ("TDirectory", "TDirectoryFile"):
            subdir = key.ReadObj()
            if subdir:
                results.extend(collect_objects(subdir, full_path))

        elif classname in ("TTree", "TChain", "TNtuple", "TNtupleD"):
            tree = key.ReadObj()
            if not tree:
                continue
            results.append(dict(
                path=full_path,
                kind=classname,
                entries=int(tree.GetEntries()),
                nbytes_disk=int(tree.GetZipBytes()),
                nbytes_mem=int(tree.GetTotBytes()),
            ))

        elif "RNTuple" in classname:
            try:
                model   = ROOT.RNTupleModel.Create()
                reader  = ROOT.RNTupleReader.Open(model, name, directory.GetFile().GetName())
                descriptor  = reader.GetDescriptor()
                entries     = int(reader.GetNEntries())

                nbytes_disk = 0
                nbytes_mem  = 0
                for cluster_id in range(descriptor.GetNClusters()):
                    cdesc = descriptor.GetClusterDescriptor(cluster_id)
                    for col_id in range(descriptor.GetNColumns()):
                        try:
                            page_range = cdesc.GetPageRange(col_id)
                            for page_info in page_range.fPageInfos:
                                nbytes_disk += int(page_info.fLocator.fBytesOnStorage)
                                nbytes_mem  += int(page_info.fNElements *
                                                   descriptor.GetColumnDescriptor(col_id)
                                                   .GetModel().GetElementSize())
                        except Exception:
                            pass

                results.append(dict(
                    path=full_path,
                    kind="RNTuple",
                    entries=entries,
                    nbytes_disk=nbytes_disk,
                    nbytes_mem=nbytes_mem,
                ))
            except Exception as exc:
                results.append(dict(
                    path=full_path,
                    kind="RNTuple",
                    entries=None,
                    nbytes_disk=0,
                    nbytes_mem=0,
                    error=str(exc),
                ))

    return results


# ---------------------------------------------------------------------------
# Per-file reporting
# ---------------------------------------------------------------------------

def process_file(filepath: str) -> None:
    p = Path(filepath)
    if not p.exists():
        console.print(f"[bold red]ERROR[/] File not found: {filepath}")
        return

    ROOT.gROOT.SetBatch(True)
    ROOT.gErrorIgnoreLevel = ROOT.kWarning

    tfile = ROOT.TFile.Open(str(p))
    if not tfile or tfile.IsZombie():
        console.print(f"[bold red]ERROR[/] Cannot open: {filepath}")
        return

    stat = p.stat()
    header = (
        f"[bold cyan]{p.resolve()}[/]\n"
        f"[dim]Size:[/] [yellow]{human(stat.st_size)}[/]  [dim]({stat.st_size:,} bytes)[/]"
    )
    console.print(Panel(header, box=box.ROUNDED, expand=False))

    items = collect_objects(tfile)
    tfile.Close()

    if not items:
        console.print("  [italic dim]No TTree or RNTuple objects found.[/]\n")
        return

    table = Table(box=box.SIMPLE_HEAD, show_footer=True, expand=False)
    n = len(items)
    label = f"TOTAL ({n} object{'s' if n != 1 else ''})"

    total_disk = sum(it["nbytes_disk"] for it in items)
    total_mem  = sum(it["nbytes_mem"]  for it in items)
    total_ratio = (total_mem / total_disk) if total_disk else float("nan")
    ratio_footer = f"{total_ratio:.2f}x" if total_disk else "n/a"

    table.add_column("Path",              footer=label,         style="cyan",   no_wrap=True)
    table.add_column("Type",              footer="",            style="magenta")
    table.add_column("Entries",           footer="",            justify="right")
    table.add_column("Disk (compressed)", footer=human(total_disk), justify="right", style="blue")
    table.add_column("Mem (raw)",         footer=human(total_mem),  justify="right", style="green")
    table.add_column("Ratio",             footer=ratio_footer,  justify="right")

    for it in items:
        ratio     = (it["nbytes_mem"] / it["nbytes_disk"]) if it["nbytes_disk"] else float("nan")
        ratio_str = f"{ratio:.2f}x" if it["nbytes_disk"] else "n/a"
        entries_str = f"{it['entries']:,}" if it["entries"] is not None else "n/a"
        err = it.get("error")
        path_cell = it["path"] + (f" [bold red][WARN][/]" if err else "")
        table.add_row(
            path_cell,
            it["kind"],
            entries_str,
            human(it["nbytes_disk"]),
            human(it["nbytes_mem"]),
            ratio_str,
        )
        if err:
            console.print(f"  [dim red]  {err}[/]")

    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@click.command(help=__doc__, context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("files", nargs=-1, required=True, metavar="FILE.root [...]")
def main(files: tuple[str, ...]) -> None:
    for f in files:
        process_file(f)


if __name__ == "__main__":
    main()
