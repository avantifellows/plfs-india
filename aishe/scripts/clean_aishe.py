"""
Parse the AISHE Final Report workbooks in raw/ into the tidy parquet tables
registered in sources.py, written to clean/.

Produces (one parquet per BQ table):
  outturn_state_level.parquet                 Table 33  — out-turn by state x level
  outturn_ug_discipline.parquet               Table 35  — UG out-turn by discipline
  outturn_programme_social_category.parquet   Table 34a — out-turn by programme x social category
  outturn_discipline_social_category.parquet  derived   — 34a rolled up to discipline via the codemap
  programme_discipline_map.parquet            codemap   — codemaps/programme_to_discipline.csv as a dim
  ug_discipline_panel.parquet                 Tables 12 + 35 across 2019-20..2021-22
  ug_discipline_extrapolated.parquet          derived   — linear projection of the panel to 2024-26

The single-year out-turn cuts (Tables 33/34a/35) come from the 2021-22 report
and carry aishe_year = "2021-22" so future reports can be appended.

Usage:
  python3 scripts/clean_aishe.py             # parse everything -> clean/*.parquet
  python3 scripts/clean_aishe.py --table aishe_fact_outturn_state_level
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import CLEAN, CODEMAPS, REPORTS, TABLES

OUTTURN_YEAR = "2021-22"   # the single-year out-turn cuts come from this report

LEVELS = [
    "Ph.D.", "M.Phil.", "Post Graduate", "Under Graduate",
    "PG Diploma", "Diploma", "Certificate", "Integrated",
]
GENDERS = ["Male", "Female", "Total"]
SOCIAL_CATEGORIES = [
    "All Categories", "Scheduled Caste", "Scheduled Tribe",
    "Other Backward Classes", "Persons with Disability", "Muslim",
    "Other Minority Communities", "EWS",
]


def _wb(year: str):
    path = REPORTS[year]
    if not path.exists():
        raise SystemExit(
            f"missing raw workbook: {path}\n"
            f"Download the AISHE {year} Final Report and place it there (see README)."
        )
    return openpyxl.load_workbook(path, data_only=True)


def _sheet(wb, *normalized_names):
    """Find a sheet whose space-stripped lowercase name matches any candidate."""
    want = {n.replace(" ", "").lower() for n in normalized_names}
    for s in wb.sheetnames:
        if s.replace(" ", "").lower() in want:
            return wb[s]
    raise SystemExit(f"no sheet matching {normalized_names} (have: {wb.sheetnames})")


# ─── Table 33: state x level out-turn ─────────────────────────────────────────
def parse_state_level(wb) -> pd.DataFrame:
    ws = _sheet(wb, "33OutTurnState")
    rows = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        state = row[1]
        if state is None or not str(state).strip():
            continue
        state = str(state).strip()
        if state.lower() in {"all india", "india", "total"}:
            continue
        for li, level in enumerate(LEVELS):
            for gi, gender in enumerate(GENDERS):
                val = row[2 + li * 3 + gi]
                rows.append({
                    "aishe_year": OUTTURN_YEAR, "state": state, "level": level,
                    "gender": gender,
                    "out_turn": int(val) if isinstance(val, (int, float)) else 0,
                })
    return pd.DataFrame(rows)


# ─── Table 35: UG out-turn by discipline ──────────────────────────────────────
def parse_ug_discipline(wb) -> pd.DataFrame:
    ws = _sheet(wb, "35UGDisc")
    rows = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        disc, subj, male, female, total = row[1], row[2], row[3], row[4], row[5]
        if disc is None:
            continue
        disc = str(disc).strip()
        if disc.endswith("Total"):
            disc = disc[: -len("Total")].strip()
        if subj not in (None, "") and not str(disc).endswith("Total"):
            continue
        if not isinstance(total, (int, float)):
            continue
        rows.append({"aishe_year": OUTTURN_YEAR, "discipline": disc, "gender": "Male", "out_turn": int(male or 0)})
        rows.append({"aishe_year": OUTTURN_YEAR, "discipline": disc, "gender": "Female", "out_turn": int(female or 0)})
        rows.append({"aishe_year": OUTTURN_YEAR, "discipline": disc, "gender": "Total", "out_turn": int(total or 0)})
    return pd.DataFrame(rows)


# ─── Table 34a: out-turn by programme x social category ───────────────────────
def parse_programme_social(wb) -> pd.DataFrame:
    ws = _sheet(wb, "34a")
    rows = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        prog = row[1]
        if prog is None or not str(prog).strip():
            continue
        prog = str(prog).strip()
        for ci, cat in enumerate(SOCIAL_CATEGORIES):
            for gi, gender in enumerate(GENDERS):
                col_idx = 2 + ci * 3 + gi
                val = row[col_idx] if col_idx < len(row) else None
                rows.append({
                    "aishe_year": OUTTURN_YEAR, "programme": prog,
                    "social_category": cat, "gender": gender,
                    "out_turn": int(val) if isinstance(val, (int, float)) else 0,
                })
    return pd.DataFrame(rows)


# ─── codemap: programme -> discipline (committed CSV -> dim) ───────────────────
def load_programme_map() -> pd.DataFrame:
    csv_path = CODEMAPS / "programme_to_discipline.csv"
    if not csv_path.exists():
        raise SystemExit(
            f"missing codemap: {csv_path}\nRun scripts/build_programme_map.py first."
        )
    return pd.read_csv(csv_path, dtype=str).fillna("")


# ─── derived: 34a rolled up to discipline via the codemap ─────────────────────
def rollup_discipline_social(prog_df: pd.DataFrame, map_df: pd.DataFrame) -> pd.DataFrame:
    prog_to_disc = dict(zip(map_df["programme"], map_df["discipline"]))
    agg: dict[tuple, int] = defaultdict(int)
    for r in prog_df.itertuples(index=False):
        disc = prog_to_disc.get(r.programme, "Others")
        agg[(disc, r.social_category, r.gender)] += int(r.out_turn)
    cat_idx = {c: i for i, c in enumerate(SOCIAL_CATEGORIES)}
    gen_idx = {g: i for i, g in enumerate(GENDERS)}
    keys = sorted(agg, key=lambda k: (k[0], cat_idx.get(k[1], 99), gen_idx.get(k[2], 99)))
    return pd.DataFrame([
        {"aishe_year": OUTTURN_YEAR, "discipline": k[0], "social_category": k[1],
         "gender": k[2], "out_turn": agg[k]}
        for k in keys
    ])


# ─── 3-year UG discipline panel (Tables 12 enrolment + 35 out-turn) ───────────
def _parse_discipline_series(ws, metric: str, year: str) -> list[dict]:
    schema = None
    for ri in range(1, 6):
        cells = [str(c.value).strip() if c.value is not None else "" for c in ws[ri]]
        if cells and cells[0] == "Discipline":
            schema = "old"
            break
        if len(cells) >= 2 and cells[1] == "Discipline":
            schema = "new"
            break
    if schema is None:
        raise SystemExit(f"could not detect schema in sheet {ws.title!r}")
    if schema == "old":
        col_disc, col_subj, col_m, col_f, col_t = 0, 1, 2, 3, 4
    else:
        col_disc, col_subj, col_m, col_f, col_t = 1, 2, 3, 4, 5

    rows = []
    for r in ws.iter_rows(min_row=4, values_only=True):
        if not r or len(r) <= col_t:
            continue
        disc, subj, male, female, total = r[col_disc], r[col_subj], r[col_m], r[col_f], r[col_t]
        if disc is None or not str(disc).strip():
            continue
        disc_s = str(disc).strip()
        if disc_s.isdigit():
            continue
        is_total = (subj is None or str(subj).strip() == "") or disc_s.endswith("Total")
        if not is_total:
            continue
        clean = disc_s[:-len("Total")].strip() if disc_s.endswith("Total") else disc_s
        if not clean or not isinstance(total, (int, float)):
            continue
        for gender, val in (("Male", male), ("Female", female), ("Total", total)):
            rows.append({
                "aishe_year": year, "metric": metric, "discipline": clean,
                "gender": gender, "value": int(val) if isinstance(val, (int, float)) else 0,
            })
    return rows


def parse_panel() -> pd.DataFrame:
    all_rows = []
    for year in REPORTS:
        wb = _wb(year)
        enrol = _sheet(wb, "12UGDisc")
        outturn = _sheet(wb, "35UGDisc")
        all_rows += _parse_discipline_series(enrol, "enrolment", year)
        all_rows += _parse_discipline_series(outturn, "out_turn", year)
    return pd.DataFrame(all_rows)


# ─── derived: linear projection of the panel to 2024-25 / 2025-26 ─────────────
YEAR_INDEX = {"2019-20": 2019, "2020-21": 2020, "2021-22": 2021}
TARGET_YEARS = {"2024-25": 2024, "2025-26": 2025}
EXCLUDE_DISCIPLINES = {"Grand", "All India", "Grand Total", "Total"}


def _linear_fit(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return slope, my - slope * mx


def extrapolate(panel_df: pd.DataFrame) -> pd.DataFrame:
    by_key: dict[tuple, list] = defaultdict(list)
    for r in panel_df.itertuples(index=False):
        disc = r.discipline.strip()
        if disc in EXCLUDE_DISCIPLINES or disc.startswith("Grand"):
            continue
        yr = YEAR_INDEX.get(r.aishe_year)
        if yr is None:
            continue
        by_key[(r.metric, disc, r.gender)].append((yr, int(r.value)))

    out = []
    for (metric, disc, gender), points in sorted(by_key.items()):
        if len(points) < 2:
            continue
        points.sort()
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        if max(ys) == 0:
            continue
        slope, intercept = _linear_fit(xs, ys)
        base_year, base_val = xs[-1], ys[-1]
        for label, ti in TARGET_YEARS.items():
            est = max(0.0, slope * ti + intercept)
            growth = ((est / base_val) - 1) * 100 if base_val else 0
            out.append({
                "target_year": label, "metric": metric, "discipline": disc,
                "gender": gender, "value_estimate": int(round(est)),
                "method": f"linear fit on {len(points)} years (2019-22)",
                "slope_per_year": round(slope, 1),
                "base_year": f"{base_year}-{(base_year + 1) % 100:02d}",
                "base_year_value": base_val,
                "years_extrapolated": ti - base_year,
                "growth_pct_total": round(growth, 1),
            })
    return pd.DataFrame(out)


def build_all() -> dict[str, pd.DataFrame]:
    wb2122 = _wb(OUTTURN_YEAR)
    prog_df = parse_programme_social(wb2122)
    map_df = load_programme_map()
    panel_df = parse_panel()
    return {
        "outturn_state_level.parquet": parse_state_level(wb2122),
        "outturn_ug_discipline.parquet": parse_ug_discipline(wb2122),
        "outturn_programme_social_category.parquet": prog_df,
        "outturn_discipline_social_category.parquet": rollup_discipline_social(prog_df, map_df),
        "programme_discipline_map.parquet": map_df,
        "ug_discipline_panel.parquet": panel_df,
        "ug_discipline_extrapolated.parquet": extrapolate(panel_df),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", default=None, help="Build only this BQ table (e.g. aishe_fact_outturn_state_level)")
    args = ap.parse_args()

    by_parquet = {t.parquet: t for t in TABLES}
    frames = build_all()
    CLEAN.mkdir(parents=True, exist_ok=True)

    chosen = frames.items()
    if args.table:
        match = [t for t in TABLES if t.bq_name == args.table]
        if not match:
            raise SystemExit(f"unknown table {args.table!r}; known: {[t.bq_name for t in TABLES]}")
        chosen = [(match[0].parquet, frames[match[0].parquet])]

    print("AISHE → clean/*.parquet")
    for parquet, df in chosen:
        out = CLEAN / parquet
        df.to_parquet(out, index=False, engine="pyarrow")
        print(f"  {by_parquet[parquet].bq_name:<46} {len(df):>6,} rows → {out.name}")
    print("✓ done.")


if __name__ == "__main__":
    main()
