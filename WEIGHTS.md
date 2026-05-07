# PLFS 2023-24 — Weights / Multipliers

This file is the operational reference for applying the survey weight when
you tabulate PLFS estimates. It reproduces the official rule from the
**README** that ships with the unit-level data and the **Estimation
Procedure** booklet (Section 3 for quarterly estimates, Section 4 for annual
estimates).

## TL;DR — three formulas, one column

Every record (HHV1, HHRV, PERV1, PERRV) carries three pre-computed fields at
the **end** of the row:

| field    | length | meaning                                                                                         |
| -------- | -----: | ----------------------------------------------------------------------------------------------- |
| `nss`    | 3      | # of FSUs surveyed in (sector × state × stratum × sub-stratum) **for one sub-sample**           |
| `nsc`    | 3      | # of FSUs surveyed in (sector × state × stratum × sub-stratum) **combined** across sub-samples  |
| `mult`   | 10     | Sub-sample-wise multiplier (raw weight, with 2 implied decimals — divide by 100 to get a float) |
| `no_qtr` | 1      | Count of contributing (sector × state × stratum × sub-stratum) cells across the 4 quarters      |

To produce population estimates, divide `mult` by a divisor that depends on
which estimate you want.

| You want…                                                                | Divisor              | Formula                  |
| ------------------------------------------------------------------------ | -------------------- | ------------------------ |
| **Quarterly, single sub-sample** (filter to one of `ss=1` or `ss=2` only) | `100`                | `weight = mult / 100`    |
| **Quarterly, both sub-samples combined**                                 | `100` if `nss = nsc` else `200` | `weight = mult / IF(nss=nsc, 100, 200)` |
| **Annual** (full July 2023 – June 2024 estimate)                         | `no_qtr` (per-record value)     | `weight = mult / no_qtr`                |

> Note: `mult` already has 2 implied decimals — it is stored as integer
> hundredths. If your tool reads it as an integer, divide by an extra `100`
> to get the true float value. The ratios above give you population units.

## Why it works that way

PLFS draws **two independent sub-samples** in every (sector × state × stratum
× sub-stratum) cell. Each sub-sample independently estimates the cell's total,
so combining them by simple addition would double-count — hence the `÷200`
when both are present, and `÷100` when only one happens to be in the cell
(`nss = nsc`). For an annual estimate the contributing cells are summed
across quarters and divided by the number of quarters that contributed,
which `no_qtr` gives you per-record.

## On the formula a researcher shared

Some users (and Stata snippets) re-derive the `÷100 vs ÷200` divisor by
*grouping*, like:

```
mult / IF(Sector × Stratum × Sub-Stratum
        = Sector × Stratum × Sub-Stratum × Sub-Sample, 100, 200)
```

That formula has two issues you should know about before using it:

1. **It drops `state`.** The official cell key is `Sector × State × Stratum
   × Sub-Stratum`. PLFS stratum codes (1, 2, 3, …) reset within each state,
   so `Stratum=2` in Punjab and `Stratum=2` in Tamil Nadu are different
   strata. Grouping without state collapses unrelated strata together, and
   you'll get the wrong divisor whenever a stratum number is reused across
   states with different sub-sample patterns. Fix: include `state` in the
   grouping key.
2. **It re-does work the file already did.** PLFS already provides `nss`
   (one sub-sample's count) and `nsc` (combined count) per record — these
   are the same numbers the formula is trying to re-derive by grouping.
   Just use them directly: `IF(nss = nsc, 100, 200)`. This is also more
   robust under filtering — if you filter rows before grouping, your
   re-derived counts will be wrong, but `nss` and `nsc` were computed
   on the full sample before any filter.
3. **It only gives the *quarterly combined* weight.** For an **annual**
   estimate (July 2023 – June 2024), the divisor is `no_qtr`, not 100/200.
   The two are not interchangeable.

## Worked examples

```python
import pandas as pd

per = pd.read_csv("clean/perv1.csv", dtype=str)
# convert what you need to numeric
for col in ["mult", "nss", "nsc", "no_qtr"]:
    per[col] = pd.to_numeric(per[col])

# (a) Annual estimate (rural+urban combined, July 2023 – June 2024)
per["weight_annual"] = per["mult"] / per["no_qtr"] / 100   # /100 strips 2 implied decimals

# (b) Quarterly combined (filter to a single quarter first)
q1 = per[per["qtr"] == "01"].copy()
q1["weight_q"] = q1["mult"] / q1["nss"].where(q1["nss"] == q1["nsc"], q1["nsc"]).map({True: 100}.get)
# clearer:
q1["divisor"] = q1.apply(lambda r: 100 if r.nss == r.nsc else 200, axis=1)
q1["weight_q"] = q1["mult"] / q1["divisor"] / 100

# (c) Sub-sample 1 only, quarterly
q1_ss1 = q1[q1["ss"] == "1"].copy()
q1_ss1["weight"] = q1_ss1["mult"] / 100 / 100
```

## Validation checks

- **Sum of annual weights** ≈ India's projected adult+child population
  for 2023-24 (~1.43 billion). MoSPI's published figures use this.
- **`nss <= nsc`** always. If you see `nss > nsc` it's a parse error.
- **`mult > 0`** for every record (no zero or negative weights).
- For sub-sample-wise tabulation, the **two sub-samples should give similar
  estimates** (their difference is the basis of variance estimates — see
  Estimation Procedure §3.8.1, §4.1.6).

## Sources

- [README.docx in the PLFS 2023-24 release](raw/docs/README.docx) — the operational rule lives here
- [Estimation Procedure_PLFS](raw/docs/EstimationProcedure_PLFS.pdf) — derivations (esp. §3, §4)
- [Data layout XLSX](raw/docs/Data_Layout_PLFS_2023-24.xlsx) — confirms `nss`, `nsc`, `mult`, `no_qtr` are at end-of-record
