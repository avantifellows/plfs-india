# PLFS — Cleaned Microdata + Code Maps

This repository converts the official PLFS (Periodic Labour Force Survey)
unit-level data from MoSPI/NSO into clean per-table CSVs with a canonical
column schema and code-map lookups, plus a single release registry that
documents every source URL.

**11 releases supported, 2018-19 → CY2025**. The full year-wide PLFS pipeline
from pre-COVID baseline through CY2025 is wireable end-to-end.

See [`clean/releases.csv`](clean/releases.csv) for the canonical release list
(source URLs, weight rules, sample sizes).

## Repository layout

```
PLFS/
├── README.md                     ← this file
├── WEIGHTS.md                    ← per-release weight rules
│
├── raw/                          ← source files (mostly gitignored; data is gated)
│   ├── docs_*/                   ← layout XLSX + README PDF per release
│   ├── docs/                     ← annual 2023-24 (legacy path, kept)
│   ├── data_*/                   ← unit-level data per release (gitignored)
│   └── external/                 ← NIC 2008, NCO 2015 reference PDFs
│
├── clean/
│   ├── releases.csv              ← REGISTRY: catalog IDs, URLs, weight rules
│   ├── layouts/                  ← ONE layout CSV per release (consolidated)
│   │   ├── annual_2018_19.csv    ← all files of one release in one CSV
│   │   ├── ...
│   │   └── calendar_2025.csv
│   └── {release_id}/             ← parsed data per release
│       ├── hhv1.csv  hhrv.csv  perv1.csv  perrv.csv     (annual releases)
│       └── chhv1.csv cperv1.csv                          (calendar releases)
│
├── codemaps/                     ← (code, description) lookup CSVs
│
├── scripts/                      ← ETL infrastructure
│   ├── releases.py               ← single source of truth: release configs + URLs
│   ├── canonicalize.py           ← layout-name → canonical-mnemonic mapping
│   ├── build_layouts.py          ← XLSX → clean/layouts/{release_id}.csv
│   ├── parse_data.py             ← unified parser: handles txt / csv / tsv input
│   ├── build_codemaps.py         ← writes codemaps/*.csv from instruction manual
│   └── parse_nco_2015.py         ← writes codemaps/nco_*.csv from NCO PDF
│
└── analyses/                     ← exploratory research scripts (read clean/* CSVs)
    ├── analysis_youth_engg_full_longitudinal.py
    └── analysis_*.py
```

## Quickstart

```bash
# Build the release registry (clean/releases.csv)
python3 scripts/releases.py

# Build all 11 release layouts from their XLSX files
python3 scripts/build_layouts.py

# Build code-map CSVs (one-time)
python3 scripts/build_codemaps.py
python3 scripts/parse_nco_2015.py

# Parse data for one release
python3 scripts/parse_data.py calendar_2025

# Parse all 11 releases (~90 seconds total)
python3 scripts/parse_data.py
```

## How to add a new release

1. Add an entry to `RELEASES` in `scripts/releases.py` — fill in catalog URL,
   format (`annual`/`calendar`), period, weight rule, paths, byte totals,
   section row bounds, file names.
2. Place the source XLSX in `raw/docs_<release_id>/` and the data files
   in `raw/data_<release_id>/` (or wherever the config points).
3. `python3 scripts/build_layouts.py <release_id>` — verify byte totals match.
4. `python3 scripts/parse_data.py <release_id>` — verify row counts match
   the release's README.
5. `python3 scripts/releases.py` — regenerate the registry CSV.

## Data fetch (gated by microdata.gov.in)

Most PLFS data is behind a free MoSPI login. Catalog URLs are in
`clean/releases.csv`. Three usable paths:

- **Browser**: each catalog page has a "Get Microdata" tab → log in → download
- **`mospi-unitdata` Python client**: authenticated API, gives Nesstar archives
  for older releases (need Nesstar Explorer to extract — Windows app)
- **Nesstar archives** (older releases): extract via Wine on macOS *or* a
  cloud Windows VM. We use a one-shot GCE Windows VM + GCS bucket workflow
  documented in our session history; see `docs/` if you need to repeat it.

## Code maps

Every coded column in a clean data table joins to a code map in `codemaps/`
on the `code` column. Codes are stored as zero-padded text.

Notable code maps:
- `state.csv` (36 states/UTs), `district.csv` (~700 districts)
- `religion.csv`, `social_group.csv`, `household_type_rural.csv`, `household_type_urban.csv`
- `general_education.csv`, `technical_education.csv`
- `activity_status.csv` (UPS / USS / CWS shared codes)
- `enterprise_type.csv`, `job_contract.csv`, `social_security.csv`
- `nic_division.csv`, `nic_group.csv`, `nic_class.csv`, `nic_subclass.csv` (NIC 2008)
- `nco_division.csv`, `nco_subdivision.csv`, `nco_group.csv`, `nco_family.csv`, `nco_full.csv` (NCO 2015)

## Weights

See [WEIGHTS.md](WEIGHTS.md). Three rules across releases:

- **`combined`** — `mult / no_qtr / IF(nss = nsc, 100, 200)`. Standard rule.
  Used by all annual releases + CY2022 + CY2024.
- **`half_yearly`** — same as combined but **with an extra `/2`**. CY2023 only
  (it uses half-yearly panels).
- **`simple`** — `mult / 100`. CY2025 only (redesigned weight scheme).
- **`limited`** — CY2021 omits `tedu_lvl`/`pas`/`ind_pas`/`ern_reg` from the
  schedule. Usable only for demographic and CWS analyses.

Each release's `weight_rule` is in `clean/releases.csv` — pick the right
function based on that column.

## Status

| Release          | Format   | Catalog | Parsed | Sample size |
| ---------------- | -------- | :-----: | :----: | -----------:|
| `annual_2018_19` | annual   | 216     | ✅     | persons: 420k FV / 533k RV |
| `annual_2019_20` | annual   | 217     | ✅     | persons: 418k FV / 523k RV |
| `annual_2020_21` | annual   | 206     | ✅     | persons: 413k FV / 510k RV |
| `calendar_2021`  | calendar | 209     | ✅     | persons: 421k (limited schema) |
| `annual_2021_22` | annual   | 214     | ✅     | persons: 428k FV / 511k RV |
| `calendar_2022`  | calendar | 211     | ✅     | persons: 425k |
| `annual_2022_23` | annual   | 210     | ✅     | persons: 419k FV / 508k RV |
| `calendar_2023`  | calendar | 208     | ✅     | persons: 416k (half-yearly) |
| `annual_2023_24` | annual   | 213     | ✅     | persons: 418k FV / 504k RV |
| `calendar_2024`  | calendar | 254     | ✅     | persons: 416k |
| `calendar_2025`  | calendar | 284     | ✅     | persons: 1.15M |

Total: **~10.5M person-rows** across all releases.

## Source

PLFS data is published by the **National Statistical Office, MoSPI, Govt of India**
at https://microdata.gov.in. Use freely under their terms — cite the
catalog ID + period of any release you use.
