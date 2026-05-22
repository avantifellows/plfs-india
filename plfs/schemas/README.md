# BigQuery table schemas

Canonical column-level documentation for the six tables produced by
[`scripts/load_bq.py`](../scripts/load_bq.py). One YAML file per table.

| File | Rows | Purpose |
|---|---:|---|
| [`plfs_fact_persons.yaml`](plfs_fact_persons.yaml) | ~10.5M | Person-level fact — every analysis lives here |
| [`plfs_fact_households.yaml`](plfs_fact_households.yaml) | ~2.5M | Household-level fact — income proxy via `mpce` |
| [`plfs_releases.yaml`](plfs_releases.yaml) | 11 | Release registry — catalog IDs, URLs, weight rules |
| [`plfs_dim_nco.yaml`](plfs_dim_nco.yaml) | ~2,700 | Full NCO 2015 occupation hierarchy |
| [`plfs_dim_nic.yaml`](plfs_dim_nic.yaml) | ~1,300 | Full NIC 2008 industry hierarchy |
| [`plfs_dim_geo.yaml`](plfs_dim_geo.yaml) | ~700 | State + district lookup |

## PLFS concepts in 60 seconds

If you've never worked with PLFS, read this before the schemas. Each YAML
repeats the relevant bits inline, but here's the whole mental model:

- **What PLFS is** — the Periodic Labour Force Survey, MoSPI/NSO's official
  household survey of employment. It samples ~100k households per release;
  it does **not** cover everyone, which is why weights exist (below).

- **It's a sample → always weight.** Each person/household row carries
  `weight_annual` = how many real people/households in India that record
  stands for. Population counts = `SUM(weight_annual)`, not `COUNT(*)`.
  Medians/quantiles must be weighted too. (`weight_annual` is NULL for
  CY2021 — partial schema, unweightable.)

- **Three ways to measure "employed".** PLFS reads each person's activity
  status over three reference periods, kept in parallel column families:
  *Usual Principal* (`*_pas`, the main status over the last year),
  *Usual Subsidiary* (`*_sas`, a secondary activity ≥30 days), and
  *Current Weekly* (`*_cws`, the last 7 days). Don't mix them in one number.
  Status codes: 11/12 self-employed, 21 unpaid family, 31 regular salaried,
  41/42 casual, 8x/9x unemployed / out of labour force.

- **NIC vs NCO — two different classifications on every job.**
  *NIC* (industry, → `plfs_dim_nic`) = the **employer's sector** — what the
  business does (e.g. NIC '62' = IT services). *NCO* (occupation, →
  `plfs_dim_nco`) = what the **person** does (e.g. NCO '251' = software
  developer). Same occupation appears across many industries. Both are
  nested numeric codes where each broader level is a prefix of the detailed
  one, so you roll up by truncating digits.

- **Income is proxied by spending.** PLFS doesn't ask income; it records
  monthly consumer expenditure (HCE). `mpce` = expenditure per head =
  the standard living-standard / income proxy. (See
  [`plfs_fact_households.yaml`](plfs_fact_households.yaml).)

- **Education is split in two.** `gedu_lvl` = general/academic schooling
  level; `tedu_lvl` = technical/professional qualification (engineering,
  medical, …), recorded separately.

- **Codes are strings, zero-padded.** District codes are scoped per state —
  always join geography on `(state_code, district_code)`.

Schemas are documentation today. The loader script uses `autodetect=True`
when calling `bigquery.Client.load_table_from_dataframe`, which infers
column types from the pandas DataFrame. If we ever need stricter type
control (e.g. forcing NULLABLE → REQUIRED, or pinning `INT64` over
`NUMERIC`), wire these YAML files in as explicit schemas at load time.

## Conventions

- **All codes are STRING**, zero-padded as in the MoSPI source (`'01'`,
  `'62011'`). Storing as INT would lose the padding and break joins
  against the dim tables.
- **Labels are denormalized inline** on the fact tables as `*_label`
  columns for the common small-enum lookups (sex, sector, religion,
  marital status, education levels, activity status, enterprise type,
  job contract, social security, etc.). No separate `dim_sex` table.
- **Hierarchical dims** (NCO / NIC / geography) stay as separate
  tables because they have real structure analysts query against.
- **Weights** are pre-computed at load time as `weight_annual`. The
  raw inputs (`mult`, `nss`, `nsc`, `no_qtr`) are retained for
  transparency. CY2021 has a partial schema; `weight_annual` is NULL.
