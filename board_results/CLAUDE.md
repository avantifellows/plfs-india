# CLAUDE.md — board_results

Source-level orientation for the board-results pipeline. Read the top-level
`../CLAUDE.md` for cross-cutting repo conventions first.

## What this source is

Indian school board exam results (Class X + Class XII) from the MoE *Result of
Secondary & Higher Secondary Examination* (RSHSE) PDFs. Upstream is one report
PDF per year (`raw/*.pdf`, gitignored). Heavy PDF parsing (pdfplumber), so this
follows the `plfs/` heavy-parse shape for cleaning and the `nirf/`/`jnv/` shape
for loading (clean parquet → GCS → BQ).

## Layout

```
board_results/
├── scripts/
│   ├── sources.py                 # config + Table/RawFile registries (single source of truth)
│   ├── clean_overall.py           # parse Sec A/B overall tables -> clean/overall_class_x_xii.parquet
│   ├── clean_class_xii_stream.py  # parse Sec B stream tables -> clean/class_xii_stream.parquet
│   ├── upload_to_gcs.py           # raw PDFs (as-is) + clean parquet -> gs://…/board_results/{raw,clean}/
│   └── load_bq.py                 # GCS clean/ -> avantifellows.external_data_sources.board_results_*
├── schemas/                       # one YAML per BQ table
├── raw/                           # source PDFs (gitignored)
└── clean/                         # parsed parquet (gitignored)
```

Add/change tables in `scripts/sources.py` (the `TABLES` registry); the loader
and uploader iterate over it.

## Parsing gotchas (carried over from the original extractors)

- **Section disambiguation.** Section A = Class X, Section B = Class XII. The
  section a page belongs to is detected from divider pages + the running page
  header — and the header check looks only at the first line, because board
  names contain "Higher Secondary" and would otherwise mis-flip the section.
- **Table numbers move across years.** Overall = Table 3 (2020/21) / Table 1
  (2022/24); stream = Tables 13/15/17 (2020/21) / 31/33/35 (2022/24). Anchored
  in `sources.py`-adjacent config inside each cleaner.
- **2020 layout is fragile.** pdfplumber over-splits the 2020 PDF into ~54
  physical columns with drifting positions; the 2020 stream parser compresses
  non-empty cells and assumes left-to-right stream order. See README caveat.
- **Schema differs by year.** 2020/2021 overall tables omit the Registered
  column → `registered` is NULL (nullable Int64) for those years.
- **Whitespace.** Board/state names are whitespace-normalized (newlines →
  spaces) so BQ strings are single-line. The original CSV extractor left
  newlines in the stream table; this port fixes that.
- **Blacked-out cells dropped, not zeroed.** Missing values are omitted.

## Refreshing for a new RSHSE release

1. Download the new report PDF into `raw/` (canonical filename) and add it to
   `REPORTS` in `sources.py`. Add the year to the loop in each cleaner.
2. Confirm the table numbers for the new layout (they shift between the
   compact and expanded report formats).
3. `clean_*.py` → `upload_to_gcs.py` → `load_bq.py`. Loads are `WRITE_TRUNCATE`.

## Don't

- Don't commit anything under `raw/` or `clean/` — gitignored data.
- Don't sum across `social_category` (overlapping) or treat blacked-out streams
  as zero.
