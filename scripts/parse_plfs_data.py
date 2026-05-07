"""
Parse PLFS 2023-24 fixed-width unit-level .txt files into per-file CSVs.

Inputs:  raw/data/{HHV1,HHRV,PERV1,PERRV}.TXT
Layouts: clean/layout/{hhv1,hhrv,perv1,perrv}_layout.csv  (built by
         scripts/build_layouts.py)
Outputs: clean/{hhv1,hhrv,perv1,perrv}.csv               (one row per record,
         columns named per the layout's field_name)

The .txt files use a fixed byte-position layout — see Data_Layout_PLFS_2023-24.xlsx.
We slice each line by [byte_start, byte_end] (1-indexed inclusive, as printed in
the layout) and emit the value verbatim (preserving leading zeros, blanks, and
sign). Numeric coercion is left to downstream tools — store as text to avoid
losing zero-padded codes that join to code-map CSVs.

Convention: input files are case-insensitive (HHV1.TXT or HHV1.txt both work).
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (lower-case file_key, expected record length excluding line terminator)
FILES = [
    ("hhv1", 126),
    ("hhrv", 86),
    ("perv1", 330),
    ("perrv", 275),
]


def load_layout(file_key: str):
    """Return list of (field_name, start_idx, end_idx) — 0-based half-open."""
    p = ROOT / "clean" / "layout" / f"{file_key}_layout.csv"
    out = []
    with p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fn = row["field_name"].strip() or f"col_{row['srl']}"
            bs = int(row["byte_start"])
            be = int(row["byte_end"])
            out.append((fn, bs - 1, be))  # 1-indexed inclusive -> 0-indexed half-open
    return out


def find_input(file_key: str) -> Path | None:
    """Locate the .TXT/.txt file in raw/data/ for this file_key."""
    base = ROOT / "raw" / "data"
    for p in base.glob(f"{file_key.upper()}*"):
        if p.suffix.lower() == ".txt":
            return p
    for p in base.glob(f"{file_key}*"):
        if p.suffix.lower() == ".txt":
            return p
    return None


def parse_file(file_key: str, expected_len: int):
    layout = load_layout(file_key)
    src = find_input(file_key)
    if src is None:
        print(f"  SKIP {file_key}: no input file in raw/data/")
        return None
    out = ROOT / "clean" / f"{file_key}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    bad_len = 0
    headers = [fn for fn, _, _ in layout]
    with src.open(encoding="latin-1") as fin, out.open("w", newline="", encoding="utf-8") as fout:
        w = csv.writer(fout)
        w.writerow(headers)
        for line in fin:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if len(line) < expected_len:
                bad_len += 1
                # pad short lines so slicing doesn't break
                line = line.ljust(expected_len)
            row = [line[s:e].strip() for _, s, e in layout]
            w.writerow(row)
            n += 1
    print(f"  {file_key:6s} {n:>7} rows  src={src.name}  out=clean/{file_key}.csv  short_lines={bad_len}")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--only",
        nargs="*",
        choices=[f for f, _ in FILES],
        help="Parse only specific files (default: all four)",
    )
    args = ap.parse_args()
    targets = args.only or [f for f, _ in FILES]
    print(f"{'file':<6} {'rows':>7}  details")
    total = 0
    for fk, length in FILES:
        if fk not in targets:
            continue
        n = parse_file(fk, length)
        if n:
            total += n
    print(f"\nTotal rows: {total}")


if __name__ == "__main__":
    main()
