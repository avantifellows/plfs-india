# PLFS 2023-24 — Cleaned Microdata + Code Maps

Reference period: **July 2023 – June 2024** (Schedule 10.4, Periodic Labour
Force Survey).

This repository converts the official PLFS unit-level fixed-width text files
into per-table CSVs, with every coded column joined to a corresponding
code-map CSV. Use it as a starting point for analysis (no transformations
applied beyond column slicing and code lookups) or as a load layer for a
warehouse (BigQuery is the next step).

## Status

- ✅ Documentation, layout, and code maps fully assembled.
- ⏳ **Unit-level data** (`HHV1.txt`, `HHRV.txt`, `PERV1.txt`, `PERRV.txt`)
  must be downloaded by the user — see [Step 0](#step-0-fetch-the-unit-level-data)
  below. The portal requires a free login.
- The parser is ready and will run as soon as the four `.txt` files land in
  `raw/data/`.

---

## Repository layout

```
PLFS/
├── README.md                 ← this file
├── WEIGHTS.md                ← weight/multiplier methodology + worked examples
├── raw/
│   ├── docs/                 ← official PLFS 2023-24 documentation (downloaded)
│   │   ├── README.docx       ← MoSPI operational rider for users
│   │   ├── InstructionManual_VolI.pdf
│   │   ├── InstructionManual_VolII.pdf
│   │   ├── EstimationProcedure_PLFS.pdf
│   │   ├── Data_Layout_PLFS_2023-24.xlsx
│   │   ├── UpdatedInstructions_2023-24.pdf
│   │   ├── NMDS_Metadata.docx
│   │   └── District_codes_PLFS_Panel_4.xlsx
│   ├── data/                 ← (you fetch these — see Step 0)
│   │   ├── HHV1.txt          ← Household, Visit-1, all 4 quarters (101,920 rows)
│   │   ├── HHRV.txt          ← Household, Visits 2/3/4 (132,844 rows)
│   │   ├── PERV1.txt         ← Person, Visit-1 (418,159 rows)
│   │   └── PERRV.txt         ← Person, Visits 2/3/4 (504,440 rows)
│   └── external/             ← non-PLFS sources (NIC, NCO)
│       ├── NIC_2008.xlsx     ← MoSPI source for industry codes
│       └── NCO_2015_VolI.pdf ← DGE source for occupation codes
├── clean/
│   ├── layout/               ← per-file fixed-width schema (built from XLSX)
│   │   ├── hhv1_layout.csv   ← 37 fields, 126 bytes
│   │   ├── hhrv_layout.csv   ← 32 fields,  86 bytes
│   │   ├── perv1_layout.csv  ← 139 fields, 330 bytes
│   │   └── perrv_layout.csv  ← 104 fields, 275 bytes
│   ├── hhv1.csv              ← (built by parser) one row per first-visit household
│   ├── hhrv.csv              ← (built by parser) one row per revisit household-visit
│   ├── perv1.csv             ← (built by parser) one row per first-visit person
│   └── perrv.csv             ← (built by parser) one row per revisit person-visit
├── codemaps/                 ← (code, description) lookup CSVs (see index below)
└── scripts/
    ├── build_layouts.py      ← extracts layout from Data_Layout_PLFS_2023-24.xlsx
    ├── build_codemaps.py     ← writes code-map CSVs from instruction manual
    ├── parse_nco_2015.py     ← parses NCO 2015 PDF into hierarchical CSVs
    └── parse_plfs_data.py    ← slices fixed-width .txt → per-file CSV
```

---

## Step 0 — Fetch the unit-level data

The four `.txt` files are gated behind a free MoSPI login. There are two
clean ways to grab them:

### Option A — Browser download (one-shot)

1. Register at https://microdata.gov.in (instant, free).
2. Open the catalog page:
   <https://microdata.gov.in/NADA/index.php/catalog/213>
3. Click the **Get Microdata** tab → log in → download the ZIP.
4. Unzip and drop the four `.TXT` files into `raw/data/`.

### Option B — Python client (scriptable)

The official `mospi-unitdata` package wraps an authenticated API:

```bash
pip install mospi-unitdata
# Get an API key from microdata.gov.in profile settings
export MOSPI_API_KEY=...
python -c "
from MospiUnitdata import download_dataset
download_dataset('DDI-IND-CSO-PLFS-2023-24', './raw/data', '$MOSPI_API_KEY')
"
```

Catalog ID for this release: **`DDI-IND-CSO-PLFS-2023-24`** (a.k.a. catalog
node 213 in the URL).

> File-name casing on the source download varies (`HHV1.TXT` vs
> `HHV1.txt`). The parser handles both.

---

## Step 1 — Build the layouts and code maps

These steps don't need the data and can be run anytime:

```bash
python3 scripts/build_layouts.py     # writes clean/layout/*_layout.csv + codemaps/state.csv
python3 scripts/build_codemaps.py    # writes most codemaps/*.csv (from Vol I)
python3 scripts/parse_nco_2015.py    # writes codemaps/nco_*.csv (from NCO PDF)
```

They also already shipped — re-run only if you've replaced a source file.

## Step 2 — Parse the data

Once `raw/data/{HHV1,HHRV,PERV1,PERRV}.txt` are present:

```bash
python3 scripts/parse_plfs_data.py            # parse all four
python3 scripts/parse_plfs_data.py --only hhv1  # parse a single file
```

The parser slices each line by byte-position from the layout, strips trailing
spaces, and writes one CSV per file with named columns (lower-snake). All
values are emitted as **text** to preserve leading zeros — coerce to numeric
downstream.

---

## Tables produced

| File              | Grain                                       | Rows (per MoSPI) | Bytes/row |
| ----------------- | ------------------------------------------- | ---------------: | --------: |
| `clean/hhv1.csv`  | One row per **household × Visit-1**         |          101,920 |       126 |
| `clean/hhrv.csv`  | One row per **household × Visit-{2,3,4}**   |          132,844 |        86 |
| `clean/perv1.csv` | One row per **person × Visit-1**            |          418,159 |       330 |
| `clean/perrv.csv` | One row per **person × Visit-{2,3,4}**      |          504,440 |       275 |

### Joining the four tables

**Household primary key** (HHV1, HHRV):

```
qtr × visit × sec × fsu_no × hg_sb × sss × hh_no
```

**Person primary key** (PERV1, PERRV): adds `srl_no` to the household key:

```
qtr × visit × sec × fsu_no × hg_sb × sss × hh_no × srl_no
```

`PERV1` joins to `HHV1` on the household key; `PERRV` joins to `HHRV` on the
household key. Across visits (e.g., panel-tracking the same household
through Q1→Q4), drop `qtr` and `visit` from the key and join on the
remaining seven columns — the same household keeps the same `fsu_no`,
`hg_sb`, `sss`, `hh_no` across visits.

> Source for the keys: `raw/docs/README.docx` (the "Common Primary Key"
> tables).

### Rotational panel — what visits roll up to which quarter

| Quarter | First-visit data         | Revisit data                                            |
| ------- | ------------------------ | ------------------------------------------------------- |
| Q1      | Q1 (Jul-Sep '23)         | Q6, Q7, Q8 of Panel III                                  |
| Q2      | Q2 (Oct-Dec '23)         | Q7, Q8 of Panel III + Q1 of Panel IV                     |
| Q3      | Q3 (Jan-Mar '24)         | Q8 of Panel III + Q1, Q2 of Panel IV                     |
| Q4      | Q4 (Apr-Jun '24)         | Q1, Q2, Q3 of Panel IV                                   |

(Source: `raw/docs/README.docx`, table B.)

---

## Code-map index

Every coded column in the four data tables joins to one of these CSVs on
`code`. **All codes are stored as zero-padded text** (so `01` joins, not `1`).

### Identifiers

| Code map                                                              | Used by columns           | Source                       |
| --------------------------------------------------------------------- | ------------------------- | ---------------------------- |
| [state.csv](codemaps/state.csv)                                       | `st`                      | Data Layout XLSX             |
| [district.csv](codemaps/district.csv)                                 | `(st, dc)`                | District_codes_PLFS_Panel_4  |
| [sector.csv](codemaps/sector.csv)                                     | `sec`                     | Vol I §1.4                   |
| [quarter.csv](codemaps/quarter.csv)                                   | `qtr`                     | README §A                    |
| [visit.csv](codemaps/visit.csv)                                       | `visit`                   | README §A                    |
| [sub_sample.csv](codemaps/sub_sample.csv)                             | `ss`                      | Vol I §1.2.12                |

### Block 3 — household characteristics

| Code map                                                                       | Used by             | Source         |
| ------------------------------------------------------------------------------ | ------------------- | -------------- |
| [household_type_rural.csv](codemaps/household_type_rural.csv)                  | `hh_type` if `sec=1` | Vol I §3.3.2  |
| [household_type_urban.csv](codemaps/household_type_urban.csv)                  | `hh_type` if `sec=2` | Vol I §3.3.2  |
| [religion.csv](codemaps/religion.csv)                                          | `religion`          | Vol I §3.3.3   |
| [social_group.csv](codemaps/social_group.csv)                                  | `social_grp`        | Vol I §3.3.4   |

### Block 4 — demographics

| Code map                                                                       | Used by             | Source                |
| ------------------------------------------------------------------------------ | ------------------- | --------------------- |
| [membership_status.csv](codemaps/membership_status.csv)                        | `whether_member`    | Vol I §3.4.3 (revisit only) |
| [relation_to_head.csv](codemaps/relation_to_head.csv)                          | `rel_head`          | Vol I §3.4.4          |
| [sex.csv](codemaps/sex.csv)                                                    | `sex`               | Vol I §3.4.5          |
| [marital_status.csv](codemaps/marital_status.csv)                              | `mar_st`            | Vol I §3.4.7          |
| [general_education.csv](codemaps/general_education.csv)                        | `gen_edu`           | Vol I §3.4.9          |
| [technical_education.csv](codemaps/technical_education.csv)                    | `tedu_lvl`          | Vol I §3.4.10         |
| [vocational_training_received.csv](codemaps/vocational_training_received.csv)  | `voc`               | Vol I §3.4.13         |

### Block 4.1 — formal vocational/technical training

| Code map                                                                       | Used by              | Source             |
| ------------------------------------------------------------------------------ | -------------------- | ------------------ |
| [vt_field_of_training.csv](codemaps/vt_field_of_training.csv)                  | `vt_field`           | Vol I §3.4.1.3     |
| [vt_duration.csv](codemaps/vt_duration.csv)                                    | `vt_dur`             | Vol I §3.4.1.4     |
| [vt_type_of_training.csv](codemaps/vt_type_of_training.csv)                    | `vt_type`            | Vol I §3.4.1.5     |
| [vt_funding_source.csv](codemaps/vt_funding_source.csv)                        | `vt_fund`            | Vol I §3.4.1.6     |

### Block 5.1 / 5.2 / 6 — economic activity

| Code map                                                                       | Used by                                   | Source                  |
| ------------------------------------------------------------------------------ | ----------------------------------------- | ----------------------- |
| [activity_status.csv](codemaps/activity_status.csv)                            | `sts_pas`, `sts_sas`, `aps_cws` & per-day CWS columns | Vol I §3.5.1.7  |
| [enterprise_type.csv](codemaps/enterprise_type.csv)                            | `ent_pas`, `ent_sas`, `ent_cws`           | Vol I §3.5.1.16         |
| [no_of_workers.csv](codemaps/no_of_workers.csv)                                | `wkr_pas`, `wkr_sas`, `wkr_cws`           | Vol I §3.5.1.17         |
| [job_contract.csv](codemaps/job_contract.csv)                                  | `jc_pas`, `jc_sas`                        | Vol I §3.5.1.19         |
| [paid_leave_eligible.csv](codemaps/paid_leave_eligible.csv)                    | `pl_pas`, `pl_sas`                        | Vol I §3.5.1.20         |
| [social_security.csv](codemaps/social_security.csv)                            | `ss_pas`, `ss_sas`                        | Vol I §3.5.1.21         |
| [product_destination.csv](codemaps/product_destination.csv)                    | `prdest_pas`                              | Vol I §3.5.1.22         |

> Exact column names depend on the layout (see `clean/layout/*_layout.csv`).
> The mapping above is by *concept*; some files use slightly different
> suffixes for principal status (`pas`), subsidiary status (`sas`), and
> current weekly status (`cws`).

### Industry & occupation (external sources)

PLFS uses **NIC 2008** for industry and **NCO 2015** for occupation, neither
of which is included in the PLFS docs.

| Code map                                                | Used by                      | Source       |
| ------------------------------------------------------- | ---------------------------- | ------------ |
| [nic_division.csv](codemaps/nic_division.csv)           | `aind_pas`, `aind_cws` (2-digit) | NIC_2008.xlsx |
| [nic_group.csv](codemaps/nic_group.csv)                 | (3-digit aggregation)         | NIC_2008.xlsx |
| [nic_class.csv](codemaps/nic_class.csv)                 | (4-digit aggregation)         | NIC_2008.xlsx |
| [nic_subclass.csv](codemaps/nic_subclass.csv)           | `ind_pas`, `ind_sas`, `indNN` (5-digit) | NIC_2008.xlsx |
| [nco_division.csv](codemaps/nco_division.csv)           | (1-digit)                     | NCO 2015 Vol-I |
| [nco_subdivision.csv](codemaps/nco_subdivision.csv)     | (2-digit)                     | NCO 2015 Vol-I |
| [nco_group.csv](codemaps/nco_group.csv)                 | `ocu_pas`, `ocu_sas`, `ocu_cws` (3-digit) | NCO 2015 Vol-I |
| [nco_family.csv](codemaps/nco_family.csv)               | (4-digit aggregation)         | NCO 2015 Vol-I |
| [nco_full.csv](codemaps/nco_full.csv)                   | (8-digit detailed; with NCO 2004 mapping) | NCO 2015 Vol-I |

> Some NCO descriptions in `nco_subdivision.csv` are mildly truncated due
> to wrapping in the source PDF — the codes themselves are exact.

---

## Weights

See [WEIGHTS.md](WEIGHTS.md). Short version:

```
weight_quarterly_subsample = mult / 100
weight_quarterly_combined  = mult / IF(nss = nsc, 100, 200)
weight_annual              = mult / no_qtr
```

`mult` has 2 implied decimals — divide by an extra `100` if you read it as
an integer. The official cell key is `Sector × State × Stratum × Sub-Stratum`
(don't drop `state` — strata reset per state).

---

## Sources

- **PLFS 2023-24 catalog (NADA):** https://microdata.gov.in/NADA/index.php/catalog/213
- **MoSPI annual report:** https://www.mospi.gov.in/annual-report-periodic-labour-force-survey-plfs-2023-24
- **NIC 2008 (XLSX):** https://www.mospi.gov.in/sites/default/files/main_menu/national_product_classification/NIC_2008.xlsx
- **NCO 2015 Vol-I (PDF, code structure):** https://www.ncs.gov.in/Documents/National%20Classification%20of%20Occupations%20_Vol%20I-%202015.pdf
- **`mospi-unitdata` Python client:** https://pypi.org/project/mospi-unitdata/

## License

PLFS data are released by MoSPI under their standard terms (research use
only, citation required). The scripts in this repo are MIT.
