# nas

NAS 2021 (National Achievement Survey) national proficiency → BigQuery.

Student-achievement performance and proficiency for grades 3 / 5 / 8 / 10,
aggregated from state level up to **national**, broken out by school management
and by location. NAS publishes these figures at the state level only; this
pipeline computes a student-weighted national mean, then stages parquet → GCS → BQ.

**Source:** NAS 2021, NCERT. Upstream is the **community CSV mirror**
[`gsidhu/NAS-2021-data`](https://github.com/gsidhu/NAS-2021-data) — a tidy CSV
form of NCERT's published NAS 2021 results. `scripts/fetch.py` shallow-clones
that repo into `raw/`, so the source CSVs land at `raw/NAS-2021-data/csv_data/`.

## Pipeline at a glance

```
gsidhu/NAS-2021-data (community CSV mirror of NCERT NAS 2021)
       │ scripts/fetch.py                  (git clone --depth 1 → raw/)
       ▼
raw/NAS-2021-data/csv_data/                (local; gitignored)
       │ scripts/clean_nas.py              (state → national, student-weighted)
       ▼
clean/national_proficiency.parquet         (local; gitignored)
       │ scripts/upload_to_gcs.py          (raw CSVs + clean parquet → GCS)
       ▼
gs://avantifellows-external-data/nas/raw/csv_data/<...>          (traceability)
gs://avantifellows-external-data/nas/clean/national_proficiency.parquet
       │ scripts/load_bq.py
       ▼
avantifellows.external_data_sources.nas_fact_national_proficiency   (asia-south1)
```

## Table produced

**`nas_fact_national_proficiency`** — 90 rows. Grain:
`(grade, subject, dimension, category)` →
`pct_correct_mean, pct_proficient_advanced, pct_basic_below_basic`.

Schema: [`schemas/nas_fact_national_proficiency.yaml`](schemas/nas_fact_national_proficiency.yaml).

## Aggregation notes (read before analysing)

- **State → national, student-weighted.** NAS reports percent-correct and
  proficiency bands at the **state** level only. The national figure is a mean
  across states weighted by `total_student × (state's share of students in that
  management/location bucket) / 100`. The share columns
  (`govt_school`, `private_school`, `rural_location`, …) come from
  `NAS_participation_state.csv`.
- **Two proficiency tails only.** NAS publishes "% Proficient and Advance" (top
  tail) and "% Basic and Below Basic" (bottom tail). The four-band split is not
  in this data set, so the fact carries only the two tails plus the
  percent-correct mean.
- **Dimensions:** `management` (State Govt, Govt Aided, Private Recognised,
  Central Govt) and `location` (Rural, Urban).
- **Subjects vary by grade:** grade 3/5 → language, math, evs; grade 8 →
  language, math, sci, sst; grade 10 → eng, mil, math, sci, sst.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
gcloud auth application-default login            # for upload + load

# 1. clone the community CSV mirror into raw/
.venv/bin/python scripts/fetch.py
# 2. aggregate state → national → clean/national_proficiency.parquet
.venv/bin/python scripts/clean_nas.py
# 3. stage raw CSVs + clean parquet to GCS
.venv/bin/python scripts/upload_to_gcs.py --dry-run
.venv/bin/python scripts/upload_to_gcs.py
# 4. load to BigQuery (post-approval)
.venv/bin/python scripts/load_bq.py --dry-run
.venv/bin/python scripts/load_bq.py
```
