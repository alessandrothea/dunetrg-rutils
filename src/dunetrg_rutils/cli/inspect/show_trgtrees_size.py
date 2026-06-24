#!/usr/bin/env python3
"""Print on-disk and in-memory sizes of all TTrees and RNtuples found in ROOT file(s)."""

from collections import defaultdict
from pathlib import Path

import click
import ROOT  # noqa: must be importable
from tabulate import tabulate
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
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

    latest_keys: dict[str, object] = {}
    for key in directory.GetListOfKeys():
        name = key.GetName()
        if name not in latest_keys or key.GetCycle() > latest_keys[name].GetCycle():
            latest_keys[name] = key
    for key in latest_keys.values():
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
# Directory scanner
# ---------------------------------------------------------------------------

def collect_files_from_dir(directory: str, pattern: str) -> list[Path]:
    d = Path(directory)
    if not d.is_dir():
        console.print(f"[bold red]ERROR[/] Not a directory: {directory}")
        return []
    matched = sorted(d.glob(pattern))
    found = [p for p in matched if p.suffix == ".root"]
    if not found:
        console.print(f"[yellow]WARNING[/] No .root files matched '{pattern}' in {directory}")
    return found


# ---------------------------------------------------------------------------
# Per-file reporting
# ---------------------------------------------------------------------------

def process_file(filepath: str, quiet: bool = False, markdown: bool = False) -> list[dict]:
    p = Path(filepath)
    if not p.exists():
        console.print(f"[bold red]ERROR[/] File not found: {filepath}")
        return []

    ROOT.gROOT.SetBatch(True)
    ROOT.gErrorIgnoreLevel = ROOT.kWarning

    tfile = ROOT.TFile.Open(str(p))
    if not tfile or tfile.IsZombie():
        console.print(f"[bold red]ERROR[/] Cannot open: {filepath}")
        return []

    stat = p.stat()
    if not quiet:
        if markdown:
            print(f"\n## {p.resolve()}  ({human(stat.st_size).strip()})\n")
        else:
            header = (
                f"[bold cyan]{p.resolve()}[/]\n"
                f"[dim]Size:[/] [yellow]{human(stat.st_size)}[/]  [dim]({stat.st_size:,} bytes)[/]"
            )
            console.print(Panel(header, box=box.ROUNDED, expand=False))

    items = collect_objects(tfile)
    tfile.Close()

    if not items:
        if not quiet:
            if markdown:
                print("_No TTree or RNTuple objects found._\n")
            else:
                console.print("  [italic dim]No TTree or RNTuple objects found.[/]\n")
        return []

    if not quiet:
        n = len(items)
        label = f"TOTAL ({n} object{'s' if n != 1 else ''})"

        total_disk = sum(it["nbytes_disk"] for it in items)
        total_mem  = sum(it["nbytes_mem"]  for it in items)
        total_ratio = (total_mem / total_disk) if total_disk else float("nan")
        ratio_footer = f"{total_ratio:.2f}x" if total_disk else "n/a"

        rows = []
        errors = []
        for it in items:
            ratio     = (it["nbytes_mem"] / it["nbytes_disk"]) if it["nbytes_disk"] else float("nan")
            ratio_str = f"{ratio:.2f}x" if it["nbytes_disk"] else "n/a"
            entries_str = f"{it['entries']:,}" if it["entries"] is not None else "n/a"
            err = it.get("error")
            if err:
                errors.append(err)
            rows.append((
                it["path"] + (" [WARN]" if err else ""),
                it["kind"],
                entries_str,
                human(it["nbytes_disk"]),
                human(it["nbytes_mem"]),
                ratio_str,
            ))

        if markdown:
            headers = ["Path", "Type", "Entries", "Disk (compressed)", "Mem (raw)", "Ratio"]
            rows.append((label, "", "", human(total_disk), human(total_mem), ratio_footer))
            print(tabulate(rows, headers=headers, tablefmt="github"))
            print()
            for err in errors:
                print(f"> **WARN** {err}\n")
        else:
            table = Table(box=box.SIMPLE_HEAD, show_footer=True, expand=False)
            table.add_column("Path",              footer=label,             style="cyan",   no_wrap=True)
            table.add_column("Type",              footer="",                style="magenta")
            table.add_column("Entries",           footer="",                justify="right")
            table.add_column("Disk (compressed)", footer=human(total_disk), justify="right", style="blue")
            table.add_column("Mem (raw)",         footer=human(total_mem),  justify="right", style="green")
            table.add_column("Ratio",             footer=ratio_footer,      justify="right")
            for row, it in zip(rows, items):
                path_cell = it["path"] + (f" [bold red][WARN][/]" if it.get("error") else "")
                table.add_row(path_cell, it["kind"], row[2], row[3], row[4], row[5])
                if it.get("error"):
                    console.print(f"  [dim red]  {it['error']}[/]")
            console.print(table)

    return items


# ---------------------------------------------------------------------------
# Grand summary
# ---------------------------------------------------------------------------

def print_grand_summary(all_items: list[dict], n_files: int, markdown: bool = False) -> None:
    groups: dict[str, dict] = defaultdict(lambda: dict(kind="", files=0, entries=0, disk=0, mem=0))
    for it in all_items:
        key = it["path"]
        g = groups[key]
        g["kind"] = it["kind"]
        g["files"] += 1
        g["entries"] += it["entries"] or 0
        g["disk"] += it["nbytes_disk"]
        g["mem"] += it["nbytes_mem"]

    total_disk = sum(g["disk"] for g in groups.values())
    total_mem  = sum(g["mem"]  for g in groups.values())
    total_ratio = (total_mem / total_disk) if total_disk else float("nan")
    ratio_footer = f"{total_ratio:.2f}x" if total_disk else "n/a"
    n_trees = len(groups)
    label = f"TOTAL ({n_trees} tree{'s' if n_trees != 1 else ''})"

    rows = []
    for tree_path, g in sorted(groups.items()):
        ratio     = (g["mem"] / g["disk"]) if g["disk"] else float("nan")
        ratio_str = f"{ratio:.2f}x" if g["disk"] else "n/a"
        rows.append((tree_path, g["kind"], str(g["files"]), f"{g['entries']:,}",
                     human(g["disk"]), human(g["mem"]), ratio_str))

    n_files_label = f"{n_files} file{'s' if n_files != 1 else ''}"
    if markdown:
        print(f"\n## Grand summary — {n_files_label}  ({human(total_disk).strip()} disk / {human(total_mem).strip()} mem)\n")
        headers = ["Tree path", "Type", "Files", "Total entries", "Disk (compressed)", "Mem (raw)", "Avg ratio"]
        rows.append((label, "", "", "", human(total_disk), human(total_mem), ratio_footer))
        print(tabulate(rows, headers=headers, tablefmt="github"))
        print()
    else:
        summary_header = (
            f"[bold cyan]Grand summary[/]\n"
            f"[dim]Files:[/] [yellow]{n_files_label}[/]"
            f"  [dim]Disk:[/] [yellow]{human(total_disk)}[/]"
            f"  [dim]Mem:[/] [yellow]{human(total_mem)}[/]"
        )
        console.print(Panel(summary_header, box=box.ROUNDED, expand=False))
        table = Table(box=box.SIMPLE_HEAD, show_footer=True, expand=False)
        table.add_column("Tree path",        footer=label,             style="cyan",    no_wrap=True)
        table.add_column("Type",             footer="",                style="magenta")
        table.add_column("Files",            footer="",                justify="right")
        table.add_column("Total entries",    footer="",                justify="right")
        table.add_column("Disk (compressed)",footer=human(total_disk), justify="right", style="blue")
        table.add_column("Mem (raw)",        footer=human(total_mem),  justify="right", style="green")
        table.add_column("Avg ratio",        footer=ratio_footer,      justify="right")
        for row in rows:
            table.add_row(*row)
        console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@click.command(help=__doc__, context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("files", nargs=-1, metavar="FILE.root [...]")
@click.option("--dir", "-d", "directories", multiple=True, metavar="DIR",
              help="Directory to scan recursively (can be repeated).")
@click.option("--pattern", "-p", default="**/*.root", show_default=True,
              help="Glob pattern applied inside each --dir.")
@click.option("--quiet", "-q", is_flag=True,
              help="Suppress per-file tables; show only the grand summary.")
@click.option("--no-summary", is_flag=True,
              help="Suppress the grand summary table.")
@click.option("--markdown", "-m", is_flag=True,
              help="Print tables as GitHub-Flavored Markdown instead of rich terminal output.")
def main(files: tuple[str, ...], directories: tuple[str, ...],
         pattern: str, quiet: bool, no_summary: bool, markdown: bool) -> None:
    all_files: list[str] = list(files)
    for d in directories:
        all_files.extend(str(p) for p in collect_files_from_dir(d, pattern))

    if not all_files:
        raise click.UsageError("Provide at least one FILE or use --dir to scan a directory.")

    all_items: list[dict] = []
    file_iter = track(all_files, description="Processing files…") if quiet else all_files
    for f in file_iter:
        items = process_file(f, quiet=quiet, markdown=markdown)
        for it in items:
            it["_file"] = f
        all_items.extend(items)

    if not no_summary and len(all_files) > 1:
        print_grand_summary(all_items, n_files=len(all_files), markdown=markdown)


if __name__ == "__main__":
    main()
