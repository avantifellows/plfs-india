"""
Release configuration for PLFS unit-level data.

Each release describes:
- Where its layout XLSX lives
- Where its data .txt files live (input)
- Where to write per-file CSVs (output)
- For each file, byte-totals + how to extract field names from the XLSX

Three release shapes the docs use:

1. ANNUAL (Jul-Jun, e.g. catalog 213): 4 files (HHV1, HHRV, PERV1, PERRV).
   The Data Layout sheet contains all 4 sections (with byte positions). The
   per-file sheet (`hhv1`, `hhrv`, `perv1`, `perrv`) carries field_name only.
   Join by Srl (column 1).

2. CALENDAR-2024 (catalog 254): 2 files (CHHV1, CPERV1). Same shape as
   ANNUAL — Data Layout has byte positions; per-file sheet has field_name.
   Join by Srl (`chhv1` sheet) or by row order (`cperv1` sheet, no Srl col).

3. CALENDAR-2025 (catalog 284): 2 files (CHHV1, CPERV1). Per-file sheet
   already contains byte_start, byte_end, field_name — fully self-contained.
   `Data Layout` is informational only.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# byte_total = expected record length (matches "RECORD LENGTH:N+1" in XLSX)
# section = (start_row, end_row) inclusive in 'Data Layout' sheet (set None
#           when the per-file sheet is self-contained)
# fieldname_sheet = sheet to read field names from
# fieldname_col = 1-indexed column with field_name in that sheet
# srl_join = whether to join Data Layout to fieldname_sheet via Srl (col A)
#            or by row order (False = use ordinal position)

RELEASES = {
    # ---- Annual Jul 2018 – Jun 2019 (catalog 216) ----
    # Pre-COVID baseline. CSV input (txt2csv pre-converted).
    # 4 files: HH_FV.txt, HH_RV.txt, PER_FV.txt, PER_RV.txt
    # HH_FV and HH_RV share the same 32-field schema in this release.
    "annual_2018_19": {
        "label": "PLFS Annual, July 2018 – June 2019 (catalog 216)",
        "input_kind": "csv",  # source CSVs already exist (txt2csv pre-converted)
        "xlsx": ROOT / "raw" / "docs_annual_2018_19" / "Data_Layout_PLFS.xlsx",
        "data_dir": ROOT / "raw" / "216 - PLFS_2018_19_CSV",
        "out_dir": ROOT / "clean" / "annual_2018_19",
        "layout_dir": ROOT / "clean" / "annual_2018_19" / "layout",
        "files": [
            # 2018-19 HH_FV and HH_RV share one section (rows 4-36, 32 fields, 86 bytes)
            {"key": "hhv1",  "section": (4, 36),    "byte_total": 86,  "csv_name": "HHV1_2018-19 (1).csv"},
            {"key": "hhrv",  "section": (4, 36),    "byte_total": 86,  "csv_name": "HHRV-2018-19 (1).csv"},
            {"key": "perv1", "section": (40, 169),  "byte_total": 319, "csv_name": "PerV1_2018-19.csv"},
            {"key": "perrv", "section": (173, 276), "byte_total": 275, "csv_name": "PerRV_2018-19.csv"},
        ],
    },

    # ---- Annual Jul 2019 – Jun 2020 (catalog 217) ----
    # Pre-COVID + first-quarter-of-COVID lockdown. TSV input (Nesstar export).
    # HH_FV and HH_RV share one 32-field schema (rows 4-36). Total 4 files.
    "annual_2019_20": {
        "label": "PLFS Annual, July 2019 – June 2020 (catalog 217)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_annual_2019_20" / "Data_Layout_PLFS_2019-20.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2019-2020",
        "out_dir": ROOT / "clean" / "annual_2019_20",
        "layout_dir": ROOT / "clean" / "annual_2019_20" / "layout",
        "files": [
            {"key": "hhv1",  "section": (4, 36),    "byte_total": 86,  "csv_name": "HHFV_2019-20.txt"},
            {"key": "hhrv",  "section": (4, 36),    "byte_total": 86,  "csv_name": "HHRV_2019-20.txt"},
            {"key": "perv1", "section": (40, 169),  "byte_total": 319, "csv_name": "PERFV_2019-20.txt"},
            {"key": "perrv", "section": (173, 279), "byte_total": 275, "csv_name": "PERRV_2019-20.txt"},
        ],
    },

    # ---- Annual Jul 2020 – Jun 2021 (catalog 206) ----
    # COVID year. New separate HHV1 (37 fields) / HHRV (32) split.
    "annual_2020_21": {
        "label": "PLFS Annual, July 2020 – June 2021 (catalog 206)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_annual_2020_21" / "Data_Layout_PLFS_2020-21.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2020-21",
        "out_dir": ROOT / "clean" / "annual_2020_21",
        "layout_dir": ROOT / "clean" / "annual_2020_21" / "layout",
        "files": [
            {"key": "hhv1",  "section": (4, 45),    "byte_total": 126, "csv_name": "hhv1.txt"},
            {"key": "hhrv",  "section": (46, 82),   "byte_total":  86, "csv_name": "hhrv.txt"},
            {"key": "perv1", "section": (83, 246),  "byte_total": 362, "csv_name": "perv1.txt"},
            {"key": "perrv", "section": (247, 350), "byte_total": 275, "csv_name": "perrv.txt"},
        ],
    },

    # ---- Calendar Year 2021 (catalog 209) ----
    # First calendar release. Smaller schema — only Blocks 1, 4, 6 (no usual-status).
    # Annotated as such in the layout XLSX.
    "calendar_2021": {
        "label": "PLFS Calendar Year 2021, January – December 2021 (catalog 209)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_calendar_2021" / "Data_Layout_PLFS_Calendar_2021.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2021-21",
        "out_dir": ROOT / "clean" / "calendar_2021",
        "layout_dir": ROOT / "clean" / "calendar_2021" / "layout",
        "files": [
            {"key": "chhv1",  "section": (4, 47),  "byte_total": 128, "csv_name": "hhv1.txt"},
            {"key": "cperv1", "section": (48, 74), "byte_total":  71, "csv_name": "cperv1.txt"},
        ],
    },

    # ---- Annual Jul 2021 – Jun 2022 (catalog 214) ----
    "annual_2021_22": {
        "label": "PLFS Annual, July 2021 – June 2022 (catalog 214)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_annual_2021_22" / "Data_Layout_PLFS_2021-22.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2021-22",
        "out_dir": ROOT / "clean" / "annual_2021_22",
        "layout_dir": ROOT / "clean" / "annual_2021_22" / "layout",
        "files": [
            {"key": "hhv1",  "section": (4, 45),    "byte_total": 126, "csv_name": "hhv1.txt"},
            {"key": "hhrv",  "section": (46, 82),   "byte_total":  86, "csv_name": "hhrv.txt"},
            {"key": "perv1", "section": (83, 230),  "byte_total": 333, "csv_name": "perv1.txt"},
            {"key": "perrv", "section": (231, 334), "byte_total": 275, "csv_name": "perrv.txt"},
        ],
    },

    # ---- Annual Jul 2022 – Jun 2023 (catalog 210) ----
    "annual_2022_23": {
        "label": "PLFS Annual, July 2022 – June 2023 (catalog 210)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_annual_2022_23" / "Data_Layout_PLFS_2022-23.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2022-23",
        "out_dir": ROOT / "clean" / "annual_2022_23",
        "layout_dir": ROOT / "clean" / "annual_2022_23" / "layout",
        "files": [
            {"key": "hhv1",  "section": (4, 45),    "byte_total": 126, "csv_name": "hhv1.txt"},
            {"key": "hhrv",  "section": (46, 82),   "byte_total":  86, "csv_name": "hhrv.txt"},
            {"key": "perv1", "section": (83, 226),  "byte_total": 330, "csv_name": "perv1.txt"},
            {"key": "perrv", "section": (227, 330), "byte_total": 275, "csv_name": "perrv.txt"},
        ],
    },

    # ---- Calendar Year 2023 (catalog 208 / "203" folder name) ----
    # Same schema as CY2024 = same as CY2022.
    "calendar_2023": {
        "label": "PLFS Calendar Year 2023, January – December 2023 (catalog 208)",
        "input_kind": "tsv",
        "xlsx": ROOT / "raw" / "docs_calendar_2023" / "Data_LayoutPLFS_Calendar_2023.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2023-23",
        "out_dir": ROOT / "clean" / "calendar_2023",
        "layout_dir": ROOT / "clean" / "calendar_2023" / "layout",
        "files": [
            {"key": "chhv1",  "section": (4, 45),   "byte_total": 129, "csv_name": "CHHV1.txt"},
            {"key": "cperv1", "section": (46, 297), "byte_total": 333, "csv_name": "cperv1.txt"},
        ],
    },

    # ---- Calendar Year 2022 (catalog 211) ----
    # Same schema as CY2024. CSV input (txt2csv pre-converted).
    "calendar_2022": {
        "label": "PLFS Calendar Year 2022, January – December 2022 (catalog 211)",
        "input_kind": "csv",
        "xlsx": ROOT / "raw" / "docs_calendar_2022" / "Data_LayoutPLFS_Calendar_2022.xlsx",
        "data_dir": ROOT / "raw" / "211 - PLFS_Data_2022-22_CSV",
        "out_dir": ROOT / "clean" / "calendar_2022",
        "layout_dir": ROOT / "clean" / "calendar_2022" / "layout",
        "files": [
            {"key": "chhv1",  "section": (4, 44),   "byte_total": 129, "csv_name": "chhv1.csv"},
            {"key": "cperv1", "section": (46, 296), "byte_total": 333, "csv_name": "cperv1.csv"},
        ],
    },

    "annual_2023_24": {
        "label": "PLFS Annual, July 2023 – June 2024 (catalog 213)",
        "input_kind": "tsv",   # switched from txt fixed-width — using Nesstar-extracted TSV
        "xlsx": ROOT / "raw" / "docs" / "Data_Layout_PLFS_2023-24.xlsx",
        "data_dir": ROOT / "raw" / "_extracted_from_nesstar" / "DDI-IND-CSO-PLFS-2023-24",
        "out_dir": ROOT / "clean" / "annual_2023_24",
        "layout_dir": ROOT / "clean" / "annual_2023_24" / "layout",
        "files": [
            {"key": "hhv1",  "section": (2, 42),    "byte_total": 126, "csv_name": "hhv1.txt"},
            {"key": "hhrv",  "section": (44, 79),   "byte_total":  86, "csv_name": "hhrv.txt"},
            {"key": "perv1", "section": (81, 223),  "byte_total": 330, "csv_name": "perv1.txt"},
            {"key": "perrv", "section": (225, 330), "byte_total": 275, "csv_name": "perrv.txt"},
        ],
    },
    "calendar_2024": {
        "label": "PLFS Calendar Year 2024, January – December 2024 (catalog 254)",
        "xlsx": ROOT / "raw" / "docs_calendar_2024" / "Data_Layout_PLFS_Calendar_2024.xlsx",
        "data_dir": ROOT / "raw" / "data_calendar_2024",
        "out_dir": ROOT / "clean" / "calendar_2024",
        "layout_dir": ROOT / "clean" / "calendar_2024" / "layout",
        "self_contained": False,
        "files": [
            # chhv1 sheet has Srl col (6 cols total). Section in Data Layout: rows 2-44.
            {"key": "chhv1",  "section": (2, 45),    "fieldname_sheet": "chhv1",  "fieldname_col": 6, "srl_join": True,  "byte_total": 129, "data_filename": "CHHV1.TXT"},
            # cperv1 sheet has NO Srl col (5 cols, headers at row 2). Pair by row order.
            {"key": "cperv1", "section": (46, 297),  "fieldname_sheet": "cperv1", "fieldname_col": 5, "srl_join": False, "byte_total": 333, "data_filename": "CPERV1.TXT"},
        ],
    },
    "calendar_2025": {
        "label": "PLFS Calendar Year 2025, January – December 2025 (catalog 284)",
        "xlsx": ROOT / "raw" / "docs_calendar_2025" / "FV_Data_Layout_2025.xlsx",
        "data_dir": ROOT / "raw" / "data_calendar_2025",
        "out_dir": ROOT / "clean" / "calendar_2025",
        "layout_dir": ROOT / "clean" / "calendar_2025" / "layout",
        "self_contained": True,
        "files": [
            # CY2025 per-file sheet has all 9 cols including byte positions (start in F, end in G,
            # field_name in H). Source-of-truth is the per-file sheet.
            {"key": "chhv1",  "fieldname_sheet": "CHHV1",  "fieldname_col": 8,
             "byte_start_col": 6, "byte_end_col": 7, "byte_total": 218,
             "data_filename": "CHHV1.TXT"},
            {"key": "cperv1", "fieldname_sheet": "CPERV1", "fieldname_col": 8,
             "byte_start_col": 6, "byte_end_col": 7, "byte_total": 371,
             "data_filename": "CPERV1.TXT"},
        ],
    },
}
