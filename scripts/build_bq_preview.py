"""
Build a `bq_preview/` directory that's a faithful preview of the BigQuery
tables we'd create — for the CTO to review the schema design before we
actually load anything into BQ.

What lands in bq_preview/:
  schemas/         — BQ-format JSON schemas (one per table)
  data/            — actual data (small tables in full; big tables sampled)
  ddl/             — BQ DDL (CREATE TABLE) — what would actually run on BQ
  README.md       — review guide

Tables:
  Fact / wide:
    persons        — all releases unioned, canonical columns + weight_annual
    households     — same
  Dimensions:
    releases       — release registry (11 rows)
    dim_state, dim_district, dim_activity_status, dim_*  — code maps

Sampling:
  Big tables (persons, households) are sampled to ~100 rows per release.
  That's ~1100 rows × 2 tables = enough to spot-check the schema and
  cross-release behavior, but small enough to scroll through.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from releases import RELEASES, ROOT
from weights import get_weight_fn

# Reproducible sampling
random.seed(2025)

OUT = ROOT / "bq_preview"
SAMPLE_PER_RELEASE = 100   # rows per release in big-table samples


# -------- Canonical schemas --------------------------------------------------

def _f(name: str, type_: str, mode: str = "NULLABLE", description: str = "") -> dict:
    """Shorthand for a BQ schema field."""
    return {"name": name, "type": type_, "mode": mode, "description": description}


PERSONS_SCHEMA = [
    # Release metadata (partition + filter cols)
    _f("release_id",     "STRING",  "REQUIRED", "Release identifier (e.g. 'calendar_2025'). Partition key."),
    _f("release_format", "STRING",  "REQUIRED", "'annual' (Jul-Jun) or 'calendar' (Jan-Dec)."),
    _f("release_year",   "STRING",  "REQUIRED", "Human-readable year label, e.g. '2018-19' or 'CY2024'."),
    _f("catalog_id",     "STRING",  "REQUIRED", "microdata.gov.in catalog ID, e.g. '213'."),

    # Survey identification (joins back to households)
    _f("qtr",            "STRING",  description="Quarter code (annual / pre-CY2025 releases)."),
    _f("month",          "STRING",  description="Month code (CY2025 only — replaces qtr)."),
    _f("visit",          "STRING",  description="V1 (first visit) or V2/V3/V4 (revisits)."),
    _f("sec",            "STRING",  description="Sector: 1=Rural, 2=Urban."),
    _f("st",             "STRING",  description="State/UT code (2-digit). Joins to dim_state."),
    _f("dc",             "STRING",  description="District code (2-digit, scoped to state). Joins to dim_district."),
    _f("nss_reg",        "STRING",  description="NSS region code."),
    _f("strm",           "STRING",  description="Stratum code (resets per state)."),
    _f("sstrm",          "STRING",  description="Sub-stratum code."),
    _f("ss",             "STRING",  description="Sub-sample (1 or 2)."),
    _f("sro",            "STRING",  description="FOD sub-region code."),
    _f("mfsu",           "STRING",  description="First Stage Unit (FSU) serial within stratum."),
    _f("sss",            "STRING",  description="Second Stage Stratum number."),
    _f("ssu",            "STRING",  description="Sample household number within FSU."),
    _f("srl_no",         "STRING",  description="Person serial number within household."),

    # Demographics
    _f("rel",            "STRING",  description="Relationship to head. Joins to dim_relation_to_head."),
    _f("sex",            "STRING",  description="1=Male, 2=Female, 3=Transgender. Joins to dim_sex."),
    _f("age",            "INT64",   description="Age in completed years."),
    _f("marst",          "STRING",  description="Marital status. Joins to dim_marital_status."),
    _f("gedu_lvl",       "STRING",  description="General education code. Joins to dim_general_education."),
    _f("tedu_lvl",       "STRING",  description="Technical education code. Joins to dim_technical_education."),
    _f("voc",            "STRING",  description="Vocational/technical training received. Joins to dim_vocational_training_received."),

    # Usual Principal Activity Status (Block 5.1)
    _f("pas",            "STRING",  description="Usual principal activity status code. Joins to dim_activity_status."),
    _f("ind_pas",        "STRING",  description="Industry (NIC 2008, 5-digit) in principal status."),
    _f("ocu_pas",        "STRING",  description="Occupation (NCO 2015, 3-digit) in principal status."),
    _f("etyp_pas",       "STRING",  description="Enterprise type in principal status. Joins to dim_enterprise_type."),
    _f("ssec_pas",       "STRING",  description="Social security benefits in principal status. Joins to dim_social_security."),
    _f("job_pas",        "STRING",  description="Job contract type in principal status. Joins to dim_job_contract."),
    _f("wrkr_pas",       "STRING",  description="Number-of-workers band in principal status. Joins to dim_no_of_workers."),

    # Usual Subsidiary Activity Status (Block 5.2)
    _f("sas",            "STRING",  description="Usual subsidiary activity status code."),
    _f("ind_sas",        "STRING",  description="Industry code in subsidiary status (5-digit NIC)."),
    _f("ocu_sas",        "STRING",  description="Occupation code in subsidiary status (3-digit NCO)."),

    # Current Weekly Status (Block 6)
    _f("aps_cws",        "STRING",  description="CWS activity status code."),
    _f("aind_cws",       "STRING",  description="Industry code in CWS (2-digit NIC division)."),
    _f("ocu_cws",        "STRING",  description="Occupation code in CWS (3-digit NCO)."),

    # Earnings (Block 6)
    _f("ern_reg",        "INT64",   description="Monthly earnings for regular salaried/wage activity (₹)."),
    _f("ern_self",       "INT64",   description="Monthly earnings for self-employment (₹)."),

    # Weight columns (raw + computed)
    _f("nss",            "INT64",   description="FSUs surveyed in cell for this sub-sample."),
    _f("nsc",            "INT64",   description="FSUs surveyed in cell combined across sub-samples."),
    _f("mult",           "INT64",   description="Sub-sample-wise multiplier (2 implied decimals)."),
    _f("no_qtr",         "INT64",   description="Count of contributing FSUs across quarters."),
    _f("weight_annual",  "FLOAT64", "REQUIRED",
        "Calibrated annual weight per row. Computed at load time via "
        "scripts/weights.py based on the release's weight_rule. SUM(weight_annual) "
        "over a filter gives a weighted-population estimate."),
]

HOUSEHOLDS_SCHEMA = [
    _f("release_id",     "STRING",  "REQUIRED", "Release identifier. Partition key."),
    _f("release_format", "STRING",  "REQUIRED", "'annual' or 'calendar'."),
    _f("release_year",   "STRING",  "REQUIRED", "Year label, e.g. '2018-19' or 'CY2024'."),
    _f("catalog_id",     "STRING",  "REQUIRED", "microdata.gov.in catalog ID."),

    # Household primary key
    _f("qtr",            "STRING"),
    _f("month",          "STRING"),
    _f("visit",          "STRING"),
    _f("sec",            "STRING"),
    _f("st",             "STRING"),
    _f("dc",             "STRING"),
    _f("nss_reg",        "STRING"),
    _f("strm",           "STRING"),
    _f("sstrm",          "STRING"),
    _f("ss",             "STRING"),
    _f("mfsu",           "STRING"),
    _f("sss",            "STRING"),
    _f("ssu",            "STRING"),

    # Block 3 — household characteristics
    _f("hh_size",        "INT64",   description="Total household members."),
    _f("hh_type",        "STRING",  description="Household type. Joins to dim_household_type_rural (sec=1) or dim_household_type_urban (sec=2)."),
    _f("religion",       "STRING",  description="Religion code. Joins to dim_religion."),
    _f("social_grp",     "STRING",  description="Social group code (ST/SC/OBC/Other). Joins to dim_social_group."),
    _f("hce_tot",        "INT64",   description="Total household monthly consumer expenditure (₹). PLFS standard income proxy."),
    _f("hce1",           "INT64",   description="Consumer goods+services HCE component."),
    _f("hce2",           "INT64",   description="Home-grown stock imputed HCE component."),
    _f("hce3",           "INT64",   description="Wages-in-kind imputed HCE component."),
    _f("hce4",           "INT64",   description="Annual clothing/footwear (1/12 averaged)."),
    _f("hce5",           "INT64",   description="Annual durables (1/12 averaged)."),

    # Weight columns
    _f("nss",            "INT64"),
    _f("nsc",            "INT64"),
    _f("mult",           "INT64"),
    _f("no_qtr",         "INT64"),
    _f("weight_annual",  "FLOAT64", "REQUIRED", "Calibrated annual weight per household."),
]

RELEASES_SCHEMA = [
    _f("release_id",     "STRING",  "REQUIRED"),
    _f("label",          "STRING",  "REQUIRED"),
    _f("format",         "STRING",  "REQUIRED", "'annual' or 'calendar'."),
    _f("year_label",     "STRING",  "REQUIRED"),
    _f("period_start",   "STRING",  "REQUIRED", "First month of reference period."),
    _f("period_end",     "STRING",  "REQUIRED", "Last month of reference period."),
    _f("catalog_id",     "STRING",  "REQUIRED"),
    _f("catalog_url",    "STRING",  "REQUIRED"),
    _f("weight_rule",    "STRING",  "REQUIRED", "'combined' / 'half_yearly' / 'simple' / 'limited'. See WEIGHTS.md."),
    _f("input_kind",     "STRING",  "REQUIRED", "'txt' (fixed-width) / 'csv' / 'tsv' — source format."),
    _f("n_files",        "INT64",   "REQUIRED"),
    _f("file_keys",      "STRING",  "REQUIRED", "Pipe-separated list (e.g., 'hhv1|hhrv|perv1|perrv')."),
]

CODEMAP_SCHEMA = [
    _f("code",        "STRING", "REQUIRED", "Zero-padded code as stored in data."),
    _f("description", "STRING", "REQUIRED"),
]

DISTRICT_SCHEMA = [
    _f("state_code",    "STRING", "REQUIRED"),
    _f("state_name",    "STRING", "REQUIRED"),
    _f("district_code", "STRING", "REQUIRED"),
    _f("district_name", "STRING", "REQUIRED"),
]

NCO_FULL_SCHEMA = [
    _f("code",          "STRING", "REQUIRED", "8-digit detailed NCO 2015 code (e.g. '2512.0100')."),
    _f("description",   "STRING", "REQUIRED"),
    _f("nco_2004_code", "STRING", description="Equivalent NCO 2004 code (e.g. '2132.10')."),
]


# Codemaps with the simple (code, description) schema
SIMPLE_CODEMAPS = [
    "activity_status", "enterprise_type", "general_education", "household_type_rural",
    "household_type_urban", "job_contract", "marital_status", "membership_status",
    "nco_division", "nco_family", "nco_group", "nco_subdivision",
    "nic_class", "nic_division", "nic_group", "nic_subclass",
    "no_of_workers", "paid_leave_eligible", "product_destination", "quarter",
    "relation_to_head", "religion", "sector", "sex", "social_group",
    "social_security", "sub_sample", "technical_education", "visit",
    "vocational_training_received", "vt_duration", "vt_field_of_training",
    "vt_funding_source", "vt_type_of_training",
]


# -------- Persons / households column projection -----------------------------

PERSONS_COLS = [c["name"] for c in PERSONS_SCHEMA]
HOUSEHOLDS_COLS = [c["name"] for c in HOUSEHOLDS_SCHEMA]
INT_COLS_PERSONS = {c["name"] for c in PERSONS_SCHEMA if c["type"] == "INT64"}
INT_COLS_HH = {c["name"] for c in HOUSEHOLDS_SCHEMA if c["type"] == "INT64"}


def _safe_int(x):
    if x is None or x == "": return None
    try: return int(x)
    except (ValueError, TypeError):
        try: return int(float(x))
        except (ValueError, TypeError): return None


def project_person_row(row, meta, weight_fn):
    """Cast a parsed CSV row to the canonical persons schema."""
    out = {
        "release_id":     meta["release_id"],
        "release_format": meta["format"],
        "release_year":   meta["year_label"],
        "catalog_id":     meta["catalog_id"],
    }
    for col in PERSONS_COLS:
        if col in out: continue
        if col == "weight_annual":
            try: out[col] = weight_fn(row)
            except Exception: out[col] = None
            continue
        v = row.get(col, "")
        if col in INT_COLS_PERSONS:
            out[col] = _safe_int(v)
        else:
            out[col] = v if v != "" else None
    return out


def project_household_row(row, meta, weight_fn):
    out = {
        "release_id":     meta["release_id"],
        "release_format": meta["format"],
        "release_year":   meta["year_label"],
        "catalog_id":     meta["catalog_id"],
    }
    for col in HOUSEHOLDS_COLS:
        if col in out: continue
        if col == "weight_annual":
            try: out[col] = weight_fn(row)
            except Exception: out[col] = None
            continue
        v = row.get(col, "")
        if col in INT_COLS_HH:
            out[col] = _safe_int(v)
        else:
            out[col] = v if v != "" else None
    return out


# -------- Writers ------------------------------------------------------------

def write_schema(path: Path, schema: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n


# -------- Build big tables (sampled) -----------------------------------------

def build_persons_sample(per_release: int = SAMPLE_PER_RELEASE) -> int:
    rows_out = []
    for rid, cfg in RELEASES.items():
        per_path = cfg["out_dir"] / "perv1.csv"
        if not per_path.exists():
            per_path = cfg["out_dir"] / "cperv1.csv"
        if not per_path.exists():
            continue
        meta = {
            "release_id": rid, "format": cfg["format"],
            "year_label": cfg["year_label"], "catalog_id": cfg["catalog_id"],
        }
        # weight_fn raises NotImplementedError for CY2021; handle gracefully
        try: weight_fn = get_weight_fn(rid)
        except Exception: weight_fn = lambda r: None

        # Reservoir sample
        reservoir = []
        with per_path.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i < per_release:
                    reservoir.append(row)
                else:
                    j = random.randint(0, i)
                    if j < per_release:
                        reservoir[j] = row
        for r in reservoir:
            try:
                rows_out.append(project_person_row(r, meta, weight_fn))
            except Exception as e:
                print(f"  WARN: skip a row in {rid}: {e}")
    return write_jsonl(OUT / "data" / "persons_sample.jsonl", rows_out)


def build_households_sample(per_release: int = SAMPLE_PER_RELEASE) -> int:
    rows_out = []
    for rid, cfg in RELEASES.items():
        hh_path = cfg["out_dir"] / "hhv1.csv"
        if not hh_path.exists():
            hh_path = cfg["out_dir"] / "chhv1.csv"
        if not hh_path.exists():
            continue
        meta = {
            "release_id": rid, "format": cfg["format"],
            "year_label": cfg["year_label"], "catalog_id": cfg["catalog_id"],
        }
        try: weight_fn = get_weight_fn(rid)
        except Exception: weight_fn = lambda r: None

        reservoir = []
        with hh_path.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i < per_release:
                    reservoir.append(row)
                else:
                    j = random.randint(0, i)
                    if j < per_release:
                        reservoir[j] = row
        for r in reservoir:
            try:
                rows_out.append(project_household_row(r, meta, weight_fn))
            except Exception:
                pass
    return write_jsonl(OUT / "data" / "households_sample.jsonl", rows_out)


# -------- Build small tables (full content) ----------------------------------

def build_releases_table() -> int:
    rows = []
    for rid, cfg in RELEASES.items():
        rows.append({
            "release_id":   rid,
            "label":        cfg["label"],
            "format":       cfg["format"],
            "year_label":   cfg["year_label"],
            "period_start": cfg["period_start"],
            "period_end":   cfg["period_end"],
            "catalog_id":   cfg["catalog_id"],
            "catalog_url":  cfg["catalog_url"],
            "weight_rule":  cfg["weight_rule"],
            "input_kind":   cfg["input_kind"],
            "n_files":      len(cfg["files"]),
            "file_keys":    "|".join(f["key"] for f in cfg["files"]),
        })
    return write_jsonl(OUT / "data" / "releases.jsonl", rows)


def build_codemap_table(name: str, schema=None) -> int:
    src = ROOT / "codemaps" / f"{name}.csv"
    if not src.exists():
        return 0
    rows = []
    with src.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    out_name = f"dim_{name}.jsonl"
    return write_jsonl(OUT / "data" / out_name, rows)


# -------- DDL emitter --------------------------------------------------------

BQ_TYPE_MAP = {"STRING": "STRING", "INT64": "INT64", "FLOAT64": "FLOAT64"}


def emit_ddl(path: Path, dataset: str = "plfs") -> None:
    """Emit BigQuery DDL for all tables. Persons + households are partitioned
    by release_id (column-partition via a generated date is overkill at our
    scale; release_id partition keeps queries within a single release fast)."""
    chunks = []

    def _ddl(table: str, schema: list[dict], partition_by: str | None = None) -> str:
        cols = []
        for c in schema:
            line = f"  {c['name']} {BQ_TYPE_MAP[c['type']]}"
            if c.get("mode") == "REQUIRED":
                line += " NOT NULL"
            desc = c.get("description", "").replace("'", "\\'")
            if desc:
                line += f"  OPTIONS(description='{desc}')"
            cols.append(line)
        parts = f"PARTITION BY RANGE_BUCKET(\n  -- partition by release_id; or use ingestion-time if you prefer\n  -- ABS(MOD(FARM_FINGERPRINT({partition_by}), 100))\n  -- For PLFS scale, can also leave un-partitioned; clustering on release_id is enough\n)" if False else ""
        cluster = f"\nCLUSTER BY release_id" if partition_by == "release_id" else ""
        return (
            f"-- {table}\n"
            f"CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (\n"
            + ",\n".join(cols)
            + f"\n){cluster};\n"
        )

    chunks.append("-- BigQuery DDL for the PLFS clean tables.\n"
                  "-- Generated by scripts/build_bq_preview.py — DO NOT EDIT BY HAND.\n"
                  "-- See bq_preview/README.md for review notes.\n\n"
                  f"CREATE SCHEMA IF NOT EXISTS `{dataset}`;\n\n")
    chunks.append("-- ============================================================\n"
                  "-- FACT-ISH TABLES (unioned across all releases)\n"
                  "-- ============================================================\n\n")
    chunks.append(_ddl("persons", PERSONS_SCHEMA, partition_by="release_id"))
    chunks.append("\n")
    chunks.append(_ddl("households", HOUSEHOLDS_SCHEMA, partition_by="release_id"))
    chunks.append("\n-- ============================================================\n"
                  "-- DIMENSION TABLES\n"
                  "-- ============================================================\n\n")
    chunks.append(_ddl("releases", RELEASES_SCHEMA))
    chunks.append("\n")
    chunks.append(_ddl("dim_state", CODEMAP_SCHEMA))
    chunks.append("\n")
    chunks.append(_ddl("dim_district", DISTRICT_SCHEMA))
    chunks.append("\n")
    chunks.append(_ddl("dim_nco_full", NCO_FULL_SCHEMA))
    chunks.append("\n")
    for name in SIMPLE_CODEMAPS:
        if name in ("nco_full",): continue
        chunks.append(_ddl(f"dim_{name}", CODEMAP_SCHEMA))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(chunks), encoding="utf-8")


# -------- README -------------------------------------------------------------

REVIEW_README = """\
# BigQuery preview — for review before we load

This directory is a **preview** of what we'd put in BigQuery. Generated by
`scripts/build_bq_preview.py` — no actual BQ resources have been created.

## What to review

1. **Schemas** (`schemas/*.schema.json`) — column names, types, descriptions.
   These follow BigQuery's JSON schema format and can be passed directly to
   `bq mk --schema=...` once approved.
2. **DDL** (`ddl/create_tables.sql`) — the actual `CREATE TABLE` statements
   we'd run on BQ.
3. **Sample data** (`data/*_sample.jsonl`) — ~100 rows per release for the
   big tables. JSON Lines format; each line is one row. Verify the projection
   looks sane (especially the cross-release behavior).
4. **Full dimension tables** (`data/dim_*.jsonl`, `data/releases.jsonl`) —
   the small reference tables in full.

## Table inventory

| Table                 | Type        | Rows (real) | Sample here |
| --------------------- | ----------- | ----------: | ----------: |
| `persons`             | fact (wide) | ~10.5 M     | ~1,100      |
| `households`          | fact (wide) | ~2.5 M      | ~1,100      |
| `releases`            | dim         | 11          | full        |
| `dim_state`           | dim         | 36          | full        |
| `dim_district`        | dim         | ~700        | full        |
| `dim_activity_status` | dim         | ~20         | full        |
| `dim_*` (other code maps) | dim     | varies      | full        |

`persons` and `households` are partitioned by `release_id` so cross-release
queries scan only what they need.

## Schema design decisions worth discussing

1. **One big `persons` table vs separate per-release tables.**
   We picked one big table partitioned by `release_id`. Trade-off:
   - **One big table** (current): easy cross-year queries (`WHERE release_id IN ('cy2024','cy2025')`),
     consistent canonical columns, NULL for missing fields (e.g., CY2021's
     stripped schema has NULLs in `tedu_lvl`/`pas` columns).
   - **Per-release tables**: cleaner per-release schemas, no NULL columns.
     But every cross-year query needs a UNION ALL.
   This is the call most likely to be reversed — flag if CTO disagrees.

2. **`weight_annual` computed at load time, not query time.**
   The right weight formula differs per release (`combined` / `half_yearly` /
   `simple`). Computing it during ETL (via `scripts/weights.py`) means every
   downstream query is `SUM(weight_annual * <indicator>)` — no per-release
   conditional logic in analytics SQL.

3. **Codes stored as STRING with zero-padding.**
   PLFS codes are zero-padded text in source (`'01'`, `'03'`, etc.). Storing
   as STRING preserves this and matches the join keys in code-map dimensions.
   INT16 would also work but join syntax gets awkward.

4. **Earnings stored as INT64.**
   PLFS records `ern_reg` and `ern_self` as whole rupees. Negatives allowed
   (self-employment can show losses). No decimals.

5. **`mult` stored as INT64** (raw, with 2 implied decimals), not as the
   pre-divided float. Reason: keeping the raw value lets us re-derive
   sub-sample or quarterly weights if needed. The calibrated annual weight
   is the `weight_annual` column.

6. **Code-map dimension tables vs inline labels.**
   We're keeping code maps as separate `dim_*` tables and joining at query
   time. Reason: labels are bilingual and may change across release years;
   centralising them keeps the schema simple. Pre-joining labels into
   `persons` would balloon the table for no real benefit.

## Where the data ends

- **Real data**: lives in `clean/` as CSVs. The big-table samples here are a
  random 100 rows per release from those CSVs.
- **Code-map tables**: full content (under a few hundred rows each).
- **Release registry**: same data as `clean/releases.csv`.

## How to look at a file

```bash
# Schema for the persons table
cat bq_preview/schemas/persons.schema.json | jq .

# 5 random sampled person rows
head -5 bq_preview/data/persons_sample.jsonl | jq .

# All states
cat bq_preview/data/dim_state.jsonl | jq .

# DDL
less bq_preview/ddl/create_tables.sql
```

## When ready to go live

```bash
# Create dataset
bq mk plfs

# Create tables (uses the DDL we generated)
bq query --use_legacy_sql=false < bq_preview/ddl/create_tables.sql

# Load (separate script — would build full rows including weight_annual via scripts/weights.py)
python3 scripts/load_bq.py        # to be written
```
"""


def write_readme() -> None:
    (OUT / "README.md").write_text(REVIEW_README, encoding="utf-8")


# -------- Driver -------------------------------------------------------------

def main() -> None:
    # Schemas
    write_schema(OUT / "schemas" / "persons.schema.json",    PERSONS_SCHEMA)
    write_schema(OUT / "schemas" / "households.schema.json", HOUSEHOLDS_SCHEMA)
    write_schema(OUT / "schemas" / "releases.schema.json",   RELEASES_SCHEMA)
    write_schema(OUT / "schemas" / "dim_state.schema.json",        CODEMAP_SCHEMA)
    write_schema(OUT / "schemas" / "dim_district.schema.json",     DISTRICT_SCHEMA)
    write_schema(OUT / "schemas" / "dim_nco_full.schema.json",     NCO_FULL_SCHEMA)
    for name in SIMPLE_CODEMAPS:
        write_schema(OUT / "schemas" / f"dim_{name}.schema.json", CODEMAP_SCHEMA)

    # Small tables (full content)
    n_releases = build_releases_table()
    n_state = build_codemap_table("state")
    n_district = (write_jsonl(OUT / "data" / "dim_district.jsonl",
                              csv.DictReader((ROOT / "codemaps" / "district.csv").open(encoding="utf-8"))))
    n_nco_full = (write_jsonl(OUT / "data" / "dim_nco_full.jsonl",
                              csv.DictReader((ROOT / "codemaps" / "nco_full.csv").open(encoding="utf-8"))))
    codemap_counts = {"state": n_state, "district": n_district, "nco_full": n_nco_full}
    for name in SIMPLE_CODEMAPS:
        codemap_counts[name] = build_codemap_table(name)

    # Big tables (sampled)
    n_persons_sample = build_persons_sample()
    n_households_sample = build_households_sample()

    # DDL
    emit_ddl(OUT / "ddl" / "create_tables.sql")

    # README
    write_readme()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"BQ preview written to: {OUT.relative_to(ROOT)}/\n")
    print(f"  Tables (full content):")
    print(f"    releases:           {n_releases:>5} rows")
    for name in ("state", "district", "nco_full"):
        print(f"    dim_{name:<14} {codemap_counts.get(name, 0):>5} rows")
    print(f"    + {len(SIMPLE_CODEMAPS)} other dim_* code maps (full content)")
    print(f"  Tables (sampled):")
    print(f"    persons_sample:     {n_persons_sample:>5} rows")
    print(f"    households_sample:  {n_households_sample:>5} rows")
    print(f"\n  Schemas:  {len(list((OUT / 'schemas').glob('*.json')))} files")
    print(f"  DDL:      bq_preview/ddl/create_tables.sql")
    print(f"  Review:   bq_preview/README.md")


if __name__ == "__main__":
    main()
