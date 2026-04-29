import glob
import os

import click


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
