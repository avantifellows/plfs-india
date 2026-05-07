"""
Extract per-file fixed-width layouts from Data_Layout_PLFS_2023-24.xlsx.

Outputs one CSV per data file (hhv1, hhrv, perv1, perrv) into clean/layout/,
each row = one field with srl, name, block, item, length, byte_start, byte_end,
field_name, remarks.

The XLSX has two parallel sources:
- 'Data Layout' sheet: srl + name + block + item + length + byte_position + remarks
  (sectioned by file, separated by header rows like "File: HHV1.txt ...")
- Per-file sheets ('hhv1', 'perv1', 'hhrv', 'perrv'): srl + name + block + item +
  length + field_name (the short snake_case variable name)
We join them on srl per file.
"""

import csv
import os
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_XLSX = ROOT / "raw" / "docs" / "Data_Layout_PLFS_2023-24.xlsx"
OUT_DIR = ROOT / "clean" / "layout"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (file_key, marker substring in col1, header-row offset, end-of-section row in 'Data Layout')
SECTIONS = [
    ("hhv1", "HHV1.txt", 2, 42),
    ("hhrv", "HHRV.txt", 44, 79),
    ("perv1", "PERV1.txt", 81, 223),
    ("perrv", "PERRV.txt", 225, 330),
]


def extract_data_layout(ws, start_row, end_row):
    """Yield rows from 'Data Layout' sheet between section bounds.

    Skips the file-header row and the column-header row.
    """
    for r in range(start_row, end_row + 1):
        srl = ws.cell(r, 1).value
        if not isinstance(srl, int):
            continue  # skip headers / blank rows
        yield {
            "srl": srl,
            "name": ws.cell(r, 2).value,
            "block": ws.cell(r, 3).value,
            "item": ws.cell(r, 4).value,
            "length": ws.cell(r, 5).value,
            "byte_start": ws.cell(r, 6).value,
            "byte_end": ws.cell(r, 7).value,
            "remarks": ws.cell(r, 8).value,
        }


def extract_field_names(ws):
    """Build {srl: field_name} from a per-file sheet."""
    out = {}
    for r in range(1, ws.max_row + 1):
        srl = ws.cell(r, 1).value
        if not isinstance(srl, int):
            continue
        out[srl] = ws.cell(r, 6).value
    return out


def main():
    wb = openpyxl.load_workbook(LAYOUT_XLSX, data_only=True)
    layout_ws = wb["Data Layout"]

    summary = []
    for file_key, _marker, start_row, end_row in SECTIONS:
        rows = list(extract_data_layout(layout_ws, start_row, end_row))
        names = extract_field_names(wb[file_key])
        out_path = OUT_DIR / f"{file_key}_layout.csv"
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "srl",
                    "field_name",
                    "name",
                    "block",
                    "item",
                    "length",
                    "byte_start",
                    "byte_end",
                    "remarks",
                ]
            )
            total_len = 0
            for row in rows:
                fn = names.get(row["srl"]) or ""
                w.writerow(
                    [
                        row["srl"],
                        fn,
                        row["name"],
                        row["block"] or "",
                        row["item"] or "",
                        row["length"],
                        row["byte_start"],
                        row["byte_end"],
                        row["remarks"] or "",
                    ]
                )
                total_len += row["length"] or 0
        summary.append((file_key, len(rows), total_len, out_path.name))

    # Also dump state code map (it's tiny, lives in the same xlsx)
    state_path = ROOT / "codemaps" / "state.csv"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state_code", "state_name"])
        ws = wb["State code"]
        for r in range(3, ws.max_row + 1):
            code = ws.cell(r, 1).value
            name = ws.cell(r, 2).value
            if code and name:
                w.writerow([str(code).zfill(2), name.strip()])

    print(f"{'file':<8} {'fields':>6} {'total_bytes':>12}  output")
    for fk, n, tb, on in summary:
        print(f"{fk:<8} {n:>6} {tb:>12}  clean/layout/{on}")
    print(f"state codes -> codemaps/state.csv")


if __name__ == "__main__":
    main()
