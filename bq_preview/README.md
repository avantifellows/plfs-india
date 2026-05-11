# PLFS → BigQuery — preview for review

This directory is the proposal for what we'd land in BigQuery, generated
as plain JSON files so the schema design + sample data can be reviewed
without touching GCP. Nothing has been created on BQ yet.

This README has the context — what PLFS is, what we use it for, how the data
flows, and the technical decisions worth a second pair of eyes.
Skip to [the schema](#6-the-schema) for the column list.

---

## 1. What is PLFS, briefly

**PLFS** = **Periodic Labour Force Survey**, run by MoSPI / NSO (Govt of India).
It's the official source for India's employment and unemployment statistics —
where the LFPR / WPR / unemployment rate numbers come from. It's a household
sample survey covering ~100k households and ~400k–1.1M individuals per release.

Two release cadences:

- **Annual** (Jul-Jun) — the canonical employment-indicators report. 4 data
  files: `HHV1`/`HHRV` (household first-visit + revisits), `PERV1`/`PERRV`
  (person first-visit + revisits).
- **Calendar Year** (Jan-Dec) — started CY2021. Faster turnaround, first-visit
  only. 2 data files: `CHHV1` + `CPERV1`.

Each survey collects, per person:

- Demographics (age, sex, marital status, relation to head)
- Education (general level, technical level — engineering / medical / other)
- Usual principal activity status (job, industry NIC code, occupation NCO code,
  enterprise type, social security, wages)
- Usual subsidiary activity status (same fields for any second job)
- Current weekly activity status (last 7 days, day-by-day)
- Monthly earnings (regular salaried + self-employment)

Per household:

- Religion, social group (SC/ST/OBC/Other), household type
- Monthly consumer expenditure (the standard income proxy in Indian household
  surveys — PLFS doesn't ask income directly)

PLFS data is published with per-record **sampling weights** so you can scale
up survey counts to India-wide population estimates.

## 2. What Avanti uses this for

The questions we've already been running against this data give a sense of
why we want it in a queryable warehouse:

- **Engineering jobs longitudinal**: How many engineering grads age 20-24 are
  in regular salaried jobs paying ≥ ₹25k/month, year-by-year from 2018-19 to
  CY2025? How does that split by wage tier (₹25-30k / ₹30-50k / >₹50k)?
  Visible result: a ~25% drop in CY2024→CY2025 — the IT-services cuts.
- **Women in IT longitudinal**: Same question, restricted to NIC 62-63
  (computer programming / information services). How has the women's share
  of entry-level IT jobs evolved 2022→2025?
- **Education-wages gap**: For engineering grads vs general grads vs school-
  only, what's the median wage at age 25-29 and 35-39? What's the
  inter-generational mobility story?
- **Socio-economic profile of engg grads**: Of the ~9M engineering degree
  holders in India today, what % come from low-income (HCE proxy) households?
  What % are first-generation learners (head-of-household has below-graduate
  education)?
- **Underemployment patterns**: ~3-4% of working engineering grads are coded
  as shop salespersons (NCO 522) or office clerks (NCO 411) — engineering
  degrees being used for jobs that don't need them.

These analyses currently run as standalone Python scripts against per-release
CSVs. They work but they're:

1. **Slow** — every analysis re-reads all relevant CSVs (10.5M rows total),
   filters in Python, computes weights.
2. **Hard to compose** — joining engineering grads to their households (for
   income / first-gen) needs custom Python.
3. **Hard to share** — anyone wanting to ask a new question needs the local
   CSVs and the Python infra.

Moving to BigQuery fixes all three: SQL is the analysis language, joins
across persons↔households↔code-maps are first-class, and anyone with read
access to the dataset can query without copying data.

## 3. Sources

**Single source of truth**: https://microdata.gov.in (the National Data
Archive run by MoSPI). Each release has a catalog ID. The 11 releases we
have cleaned:

| Release | Catalog | URL |
|---|---:|---|
| Annual Jul18-Jun19 | 216 | https://microdata.gov.in/nada43/index.php/catalog/216 |
| Annual Jul19-Jun20 | 217 | https://microdata.gov.in/nada43/index.php/catalog/217 |
| Annual Jul20-Jun21 | 206 | https://microdata.gov.in/nada43/index.php/catalog/206 |
| Calendar Year 2021 | 209 | https://microdata.gov.in/nada43/index.php/catalog/209 |
| Annual Jul21-Jun22 | 214 | https://microdata.gov.in/nada43/index.php/catalog/214 |
| Calendar Year 2022 | 211 | https://microdata.gov.in/nada43/index.php/catalog/211 |
| Annual Jul22-Jun23 | 210 | https://microdata.gov.in/nada43/index.php/catalog/210 |
| Calendar Year 2023 | 208 | https://microdata.gov.in/nada43/index.php/catalog/208 |
| Annual Jul23-Jun24 | 213 | https://microdata.gov.in/nada43/index.php/catalog/213 |
| Calendar Year 2024 | 254 | https://microdata.gov.in/nada43/index.php/catalog/254 |
| Calendar Year 2025 | 284 | https://microdata.gov.in/nada43/index.php/catalog/284 |

Plus **two non-PLFS reference datasets**:

- **NIC 2008** (National Industrial Classification) — from MoSPI. ~2k codes
  organised into divisions / groups / classes / subclasses.
- **NCO 2015** (National Classification of Occupations) — from DGE&T,
  Ministry of Labour. ~2.7k 8-digit codes mapping to NCO 2004.

Both are committed as `dim_nic_*` and `dim_nco_*` reference tables.

### Extraction story (relevant context)

PLFS unit-level data is mostly distributed as `.Nesstar` archives — a
proprietary NSDstat format that requires a Windows GUI app (Nesstar
Explorer) to extract. Catalogs from 2022+ also offer pre-converted CSV
downloads. For older releases we had to:

1. Spin up a Windows Server 2022 VM in `asia-south1` (`avantifellows` project)
2. RDP in, install Nesstar Explorer
3. Manually export each `.Nesstar` archive to TSV (24 file exports across 7 archives)
4. Push back to a GCS bucket, then pull to local
5. Tear down VM + bucket

Total one-time extraction cost: ~₹100. The extracted TSVs and the original
catalog URLs are all in `clean/releases.csv` so this never has to be
repeated unless data corrupts.

## 4. Data flow

```
        ┌─────────────────┐
        │ microdata.gov.in│  (PLFS source — 11 catalog IDs)
        └────────┬────────┘
                 │ manual download (gated by free login)
                 ▼
        ┌─────────────────┐
        │   raw/           │  XLSX layouts, README PDFs, source data
        │     docs_*/      │  (committed: docs only; data files gitignored)
        │     data*/       │
        │     external/    │  NIC 2008 + NCO 2015 reference PDFs
        └────────┬────────┘
                 │ scripts/build_layouts.py    (XLSX → consolidated layout CSV)
                 │ scripts/parse_data.py        (per-release source → canonical CSV)
                 │ scripts/build_codemaps.py    (one-off: reference code lists)
                 │ scripts/parse_nco_2015.py    (one-off: NCO PDF → CSVs)
                 ▼
        ┌─────────────────┐
        │   clean/         │  Per-release CSVs with canonical column names
        │     releases.csv │  Release registry (catalog IDs, URLs, weight rules)
        │     layouts/     │  11 layout CSVs (one per release)
        │     {release}/   │  {hhv1,hhrv,perv1,perrv}.csv  or  {chhv1,cperv1}.csv
        │   codemaps/      │  Code-map dimension tables (state, district, NCO, NIC, …)
        └────────┬────────┘
                 │ scripts/weights.py — per-release calibrated weight functions
                 │ scripts/build_bq_preview.py — generates THIS directory
                 ▼
        ┌─────────────────┐
        │   bq_preview/    │  ← YOU ARE HERE
        │     schemas/     │  JSON schemas (BQ format)
        │     data/        │  JSONL samples + full dim tables
        │     ddl/         │  CREATE TABLE statements
        └────────┬────────┘
                 │ (after review)
                 │ scripts/load_bq.py — to be written
                 ▼
        ┌─────────────────┐
        │   BigQuery       │  plfs.persons, plfs.households, plfs.releases,
        │                  │  plfs.dim_* (36 dimension tables)
        └─────────────────┘
```

**Important property**: every step is reproducible from the source URLs in
`clean/releases.csv`. If a release gets republished or we add a new year,
the only change is in `scripts/releases.py` (single source of truth for
release config). The rest re-runs.

## 5. Why BigQuery (vs alternatives)

We considered:

- **Stay on CSVs** — what we have. Doesn't scale to "ask any question";
  every new question is a fresh Python script.
- **DuckDB on local CSVs** — fast enough for our data volume but doesn't
  share; needs Python + local CSVs to query.
- **Postgres** — works but adds operational burden (instance, backups,
  vacuum). At our scale (10.5M rows) it's overkill.
- **BigQuery** — pay-per-query, no instance, serverless, free tier covers
  our use ~indefinitely. Easy to connect Looker / Metabase / Streamlit /
  Quarto to. Already in `avantifellows` GCP project.

**Cost estimate**: At ~10.5M rows and ~50 cols each (mostly STRING), the
persons table is ~3-5 GB. Free tier covers 1 TB scanned per month. Our
typical query patterns (filter by `release_id` + age + `tedu_lvl`, project
a handful of columns) should scan well under 100 MB each. **Expected
monthly bill: $0** unless usage spikes by 50×.

## 6. The schema

Two "fact-ish" tables, clustered for fast filtering by release. 36
dimension tables for code lookups.

### `persons` (fact)

- ~10.5 M rows across all releases
- Clustered by `release_id` (every analysis filters to a subset of releases)
- 44 columns: identification keys, demographics, three activity-status
  contexts (principal / subsidiary / CWS), earnings, raw weight columns
- **Plus `weight_annual` (FLOAT64)** — the calibrated weight, computed
  during load via `scripts/weights.py`. Every analytics query becomes
  `SELECT release_id, SUM(weight_annual * indicator) FROM persons WHERE …`
  with no per-release branching logic.

See `schemas/persons.schema.json` for full column list with descriptions.

### `households` (fact)

- ~2.5 M rows across all releases
- Same clustering approach
- 27 columns: identification keys (joins back to persons), household
  characteristics (size, type, religion, social group), consumer
  expenditure components

### `releases` (dim, 11 rows)

The registry — catalog IDs, URLs, weight rules, formats. Full content
in `data/releases.jsonl`.

### Dimension tables (36 small ref tables)

- **Geography**: `dim_state` (36), `dim_district` (~700)
- **Survey design**: `dim_sector`, `dim_quarter`, `dim_visit`, `dim_sub_sample`
- **Block 3 (household)**: `dim_religion`, `dim_social_group`,
  `dim_household_type_rural`, `dim_household_type_urban`
- **Block 4 (demographics)**: `dim_sex`, `dim_marital_status`,
  `dim_relation_to_head`, `dim_general_education`, `dim_technical_education`,
  `dim_vocational_training_received`
- **Block 4.1 (training)**: `dim_vt_field_of_training`, `dim_vt_duration`,
  `dim_vt_type_of_training`, `dim_vt_funding_source`
- **Block 5 (economic activity)**: `dim_activity_status`,
  `dim_enterprise_type`, `dim_no_of_workers`, `dim_job_contract`,
  `dim_paid_leave_eligible`, `dim_social_security`,
  `dim_product_destination`
- **NIC 2008** (industry): `dim_nic_division` (88), `dim_nic_group` (238),
  `dim_nic_class` (419), `dim_nic_subclass` (1304)
- **NCO 2015** (occupation): `dim_nco_division` (9), `dim_nco_subdivision`
  (40), `dim_nco_group` (127), `dim_nco_family` (433), `dim_nco_full` (2673)

Each table has `code` + `description` columns (a few have richer schemas —
`dim_district` adds `state_code`, `dim_nco_full` adds `nco_2004_code`).

## 7. Schema design decisions worth a second opinion

1. **One big `persons` table clustered by `release_id`, vs per-release tables**

   We picked one big table. Trade-off:
   - **One big table** (chosen): easy cross-year queries
     (`WHERE release_id IN ('cy2024','cy2025')`), consistent canonical columns.
     Schemas vary across releases (CY2021 is stripped down, CY2025 has new
     `bstrm`/`zst` fields); missing fields are NULL.
   - **Per-release tables**: cleaner per-release schemas, no NULL columns.
     But every cross-year query needs UNION ALL.

   This is the most likely call to be reversed if the review disagrees.

2. **`weight_annual` computed at load time, not query time**

   Three different weight rules across releases (`combined` / `half_yearly` /
   `simple` — see `WEIGHTS.md`). Computing during ETL means every downstream
   query is `SUM(weight_annual * indicator)` — no per-release CASE logic in
   analytics SQL. The raw `mult`, `nss`, `nsc`, `no_qtr` columns are kept
   for transparency (e.g., if someone wants the quarterly weight instead).

3. **Codes stored as STRING with zero-padding**

   PLFS codes are zero-padded text in source (`'01'` for state, `'03'` for
   tedu_lvl = engineering degree, etc.). Storing as STRING preserves this
   and matches join keys in code-map dimensions. INT16 would also work
   but join syntax becomes awkward (`CAST(t.tedu_lvl AS INT64) = d.code`).

4. **Earnings as INT64**

   `ern_reg` and `ern_self` are whole rupees in source. Negatives allowed
   (self-employment losses). No decimals.

5. **`mult` stored raw (with 2 implied decimals) rather than as a divided float**

   Lets analysts re-derive quarterly or sub-sample weights if needed. The
   calibrated annual weight lives in the separate `weight_annual` column.

6. **Code-map labels NOT pre-joined into `persons` / `households`**

   Code maps stay as separate `dim_*` tables, joined at query time.
   Reason: code lists may need bilingual labels eventually and may change
   across release years. Joining at query time keeps fact tables narrow
   and dimensions correctable.

7. **No table partitioning beyond clustering on `release_id`**

   At 10.5M rows total, BigQuery's standard 1GB partition floor would make
   release-level partitioning wasteful. Clustering on `release_id` gets us
   filter pushdown without the partition tax.

## 8. What to look at first

Recommended review order (~30 min):

1. **`schemas/persons.schema.json`** — does the column list make sense?
   Anything we should add / drop / rename?
2. **`data/persons_sample.jsonl`** — open in jq or vim, look at 10-20 rows
   from different releases. Spot-check the canonical schema works:
   - CY2021 rows have NULLs in `tedu_lvl` / `pas` (limited schema)
   - CY2025 rows have `month` populated, `qtr` NULL
   - `weight_annual` is populated and reasonable (typical: 200-2000)
3. **`data/releases.jsonl`** — 11 rows; confirm catalog IDs + URLs are real
4. **`ddl/create_tables.sql`** — the SQL we'd actually run on BQ
5. **`schemas/households.schema.json`** — narrower than persons; check that
   the join keys to persons are clear

## 9. Open questions for review

- **Dataset name**: the DDL uses `plfs`. Should this live in a specific GCP
  project (probably `avantifellows`)? Different name?
- **Access control**: read access for the research team is one set of
  permissions; future Streamlit/dashboard frontends would need
  service-account auth. Worth deciding upfront.
- **Update cadence**: PLFS publishes new releases every 6-9 months (next:
  Annual Jul24-Jun25 expected Q2 2026). Should `scripts/load_bq.py` be
  wired into a Cloud Run job triggered on `clean/releases.csv` changes,
  or kept manual for now?
- **Cost monitoring**: worth setting a budget alert on the project? At
  current usage it'll be $0, but a guardrail is cheap.

## 10. How to go live (after sign-off)

```bash
# 1. Create dataset
bq mk plfs

# 2. Create tables (uses generated DDL)
bq query --use_legacy_sql=false < bq_preview/ddl/create_tables.sql

# 3. Load all 11 releases (script TBD — should take ~10 min for full dataset)
python3 scripts/load_bq.py        # streams clean/{release}/*.csv into plfs.persons / plfs.households
                                  # joins releases registry + computes weight_annual via scripts/weights.py
                                  # loads dim_* from codemaps/

# 4. Smoke-test
bq query --use_legacy_sql=false '
SELECT release_id, COUNT(*) AS rows,
       SUM(weight_annual) / 1e9 AS pop_billions
FROM plfs.persons
GROUP BY release_id
ORDER BY release_id'
# Expected: 1.08B - 1.22B per release (validates weight calibration)
```
