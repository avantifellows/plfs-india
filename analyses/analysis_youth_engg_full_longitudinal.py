"""
Longitudinal: engineers (UG/PG, tedu_lvl in {03, 13}) age 20-24 in regular salaried jobs ≥ ₹25k.
Across all usable PLFS releases 2018-19 to CY2025.

Excluded: calendar_2021 (cat 209) — limited schema, no tedu_lvl/pas/ern_reg.

Notes:
  - calendar_2023 (cat 208) uses half-yearly panels — annual estimate needs an
    extra /2 over the standard formula. Handled via release-specific weight.
  - annual_2022_23 (cat 210) has known high-multiplier rural outlier (Assam,
    single uninhabited village). Likely affects rural numbers; urban engineers
    should be unaffected. Reported as-is.
  - calendar_2025 (cat 284) uses simplified rule: weight = mult/100.

Wage tiers (nominal):
  Low: ₹25,000 – ₹29,999
  Med: ₹30,000 – ₹49,999
  High: ≥ ₹50,000
"""
import csv, collections
from pathlib import Path

ENGG_TEDU = {'03', '13'}
AGE_LO, AGE_HI = 20, 24
WAGE_FLOOR = 25_000

def safe_int(x, d=0):
    try: return int(x)
    except (ValueError, TypeError): return d

def w_combined(r):
    mult = safe_int(r.get('mult'))
    nss = safe_int(r.get('nss')); nsc = safe_int(r.get('nsc'))
    nq = safe_int(r.get('no_qtr'), 1) or 1
    div = 100 if nss == nsc else 200
    return mult / nq / div

def w_combined_halfyearly(r):
    """CY2023: half-yearly panels. Standard formula gives half-year estimate;
    divide by 2 for full calendar year."""
    return w_combined(r) / 2

def w_simple(r):
    return safe_int(r.get('mult')) / 100

WEIGHT = {
    'annual_2018_19': w_combined,
    'annual_2019_20': w_combined,
    'annual_2020_21': w_combined,
    'annual_2021_22': w_combined,
    'calendar_2022':  w_combined,
    'annual_2022_23': w_combined,
    'calendar_2023':  w_combined_halfyearly,   # release-specific
    'annual_2023_24': w_combined,
    'calendar_2024':  w_combined,
    'calendar_2025':  w_simple,                # release-specific
}

# Release → file path + reference period label + format flag
RELEASES = [
    ('annual_2018_19',  'clean/annual_2018_19/perv1.csv',   'Jul 2018 – Jun 2019',  'annual',   '2018-19'),
    ('annual_2019_20',  'clean/annual_2019_20/perv1.csv',   'Jul 2019 – Jun 2020',  'annual',   '2019-20'),
    ('annual_2020_21',  'clean/annual_2020_21/perv1.csv',   'Jul 2020 – Jun 2021',  'annual',   '2020-21'),
    ('annual_2021_22',  'clean/annual_2021_22/perv1.csv',   'Jul 2021 – Jun 2022',  'annual',   '2021-22'),
    ('calendar_2022',   'clean/calendar_2022/cperv1.csv',   'Jan – Dec 2022',       'calendar', 'CY2022'),
    ('annual_2022_23',  'clean/annual_2022_23/perv1.csv',   'Jul 2022 – Jun 2023',  'annual',   '2022-23'),
    ('calendar_2023',   'clean/calendar_2023/cperv1.csv',   'Jan – Dec 2023 *',     'calendar', 'CY2023'),
    ('annual_2023_24',  'clean/annual_2023_24/perv1.csv',   'Jul 2023 – Jun 2024',  'annual',   '2023-24'),
    ('calendar_2024',   'clean/calendar_2024/cperv1.csv',   'Jan – Dec 2024',       'calendar', 'CY2024'),
    ('calendar_2025',   'clean/calendar_2025/cperv1.csv',   'Jan – Dec 2025',       'calendar', 'CY2025'),
]


def tier(wage):
    if wage < 30_000: return 'Low (₹25-30k)'
    if wage < 50_000: return 'Med (₹30-50k)'
    return 'High (>₹50k)'

TIERS = ['Low (₹25-30k)', 'Med (₹30-50k)', 'High (>₹50k)']

# Per release: collect cohort
data = {}
for release, path, period, fmt, year in RELEASES:
    weight_fn = WEIGHT[release]
    rows = []
    p = Path(path)
    if not p.exists():
        print(f'  MISSING: {path}')
        continue
    with p.open() as f:
        for r in csv.DictReader(f):
            if r.get('tedu_lvl') not in ENGG_TEDU: continue
            try: age = int(r['age'])
            except (ValueError, KeyError): continue
            if not (AGE_LO <= age <= AGE_HI): continue
            if r.get('pas') != '31': continue
            try: w = weight_fn(r)
            except (ValueError, ZeroDivisionError): continue
            wage = safe_int(r.get('ern_reg'))
            if wage < WAGE_FLOOR: continue
            rows.append({'wage': wage, 'tier': tier(wage), 'weight': w})
    data[year] = {'rows': rows, 'fmt': fmt, 'period': period, 'release': release}

print('=' * 110)
print('Engineering grads age 20-24 in regular salaried jobs ≥ ₹25,000/month (nominal) — wage-tier longitudinal')
print('=' * 110)
print(f'{"Year":<10} {"Period":<22} {"Format":<10} ', '  '.join(f'{t:<19}' for t in TIERS), '   Total')
print('-' * 130)

for year, d in data.items():
    rows = d['rows']
    total_w = sum(r['weight'] for r in rows)
    cells = []
    for t in TIERS:
        w = sum(r['weight'] for r in rows if r['tier'] == t)
        n = sum(1 for r in rows if r['tier'] == t)
        share = w/total_w*100 if total_w else 0
        cells.append(f'{w:>9,.0f} ({share:>4.1f}%) n={n:<3}')
    print(f'{year:<10} {d["period"]:<22} {d["fmt"]:<10} ', '  '.join(f'{c:<19}' for c in cells), f'   {total_w:>9,.0f} (n={len(rows):>3})')

# Sample sizes table
print('\n' + '=' * 80)
print('Raw sample sizes — flag cells with n<10 as too sparse to interpret')
print('=' * 80)
print(f'{"Year":<10} ', '  '.join(f'{t:<14}' for t in TIERS), '   Total')
print('-' * 80)
sparse_cells = 0
for year, d in data.items():
    rows = d['rows']
    cells = []
    for t in TIERS:
        n = sum(1 for r in rows if r['tier'] == t)
        flag = ' ⚠️' if n < 10 else ''
        cells.append(f'n = {n:>4}{flag}')
        if n < 10: sparse_cells += 1
    cells.append(f'n = {len(rows):>4}')
    print(f'{year:<10} ', '  '.join(f'{c:<14}' for c in cells))

print(f'\nTotal sparse cells (n<10): {sparse_cells}')

# Year-over-year change in totals (nominal)
print('\n' + '=' * 110)
print('Total cohort growth (₹25k+ regular jobs for engineers 20-24) — anchor to 2018-19')
print('=' * 110)
years_seen = list(data.keys())
baseline = sum(r['weight'] for r in data[years_seen[0]]['rows'])
print(f'{"Year":<10} {"Total weighted":>16} {"Δ vs 2018-19":>18}')
print('-' * 50)
for year, d in data.items():
    tot = sum(r['weight'] for r in d['rows'])
    pct = (tot/baseline - 1)*100 if baseline else 0
    print(f'{year:<10} {tot:>16,.0f} {pct:>+16.1f}%')

# Drill into HIGH tier specifically — most volatile
print('\n' + '=' * 110)
print('High-wage engineering jobs (>₹50k/month) — engineer 20-24, year by year')
print('=' * 110)
print(f'{"Year":<10} {"Weighted":>12} {"Median wage in tier":>20} {"P75 wage":>10} {"P90 wage":>10}  {"raw n":>7}')
print('-' * 80)
def wp(vw, q):
    if not vw: return None
    s = sorted(vw); tot = sum(w for _, w in s)
    cum = 0
    for v, w in s:
        cum += w
        if cum >= tot*q: return v
    return s[-1][0]
for year, d in data.items():
    rows = [r for r in d['rows'] if r['tier'] == 'High (>₹50k)']
    n = len(rows)
    w_total = sum(r['weight'] for r in rows)
    vw = [(r['wage'], r['weight']) for r in rows]
    med = wp(vw, 0.5); p75 = wp(vw, 0.75); p90 = wp(vw, 0.9)
    print(f'{year:<10} {w_total:>12,.0f} {f"₹{med:,}" if med else "—":>20} '
          f'{f"₹{p75:,}" if p75 else "—":>10} {f"₹{p90:,}" if p90 else "—":>10}  {n:>7,}')

# Drill into the LOW tier (₹25-30k) — most exposed to AI cuts at entry level
print('\n' + '=' * 110)
print('Low-wage entry-tier engineering jobs (₹25-30k/month) — engineer 20-24')
print('=' * 110)
print(f'{"Year":<10} {"Weighted":>12} {"Median wage in tier":>20} {"P75":>10}  {"raw n":>7}')
print('-' * 65)
for year, d in data.items():
    rows = [r for r in d['rows'] if r['tier'] == 'Low (₹25-30k)']
    n = len(rows)
    w_total = sum(r['weight'] for r in rows)
    vw = [(r['wage'], r['weight']) for r in rows]
    med = wp(vw, 0.5); p75 = wp(vw, 0.75)
    print(f'{year:<10} {w_total:>12,.0f} {f"₹{med:,}" if med else "—":>20} '
          f'{f"₹{p75:,}" if p75 else "—":>10}  {n:>7,}')

# DROP recommendations
print('\n' + '=' * 110)
print('SPARSENESS ASSESSMENT — which datasets to keep / drop')
print('=' * 110)
for year, d in data.items():
    rows = d['rows']
    n_total = len(rows)
    n_high = sum(1 for r in rows if r['tier'] == 'High (>₹50k)')
    n_low = sum(1 for r in rows if r['tier'] == 'Low (₹25-30k)')
    if n_total < 50:
        verdict = 'DROP (total n<50)'
    elif n_high < 10 and n_low < 10:
        verdict = 'CAUTION (both high and low tiers sparse)'
    else:
        verdict = 'KEEP'
    print(f'  {year:<10} n={n_total:>4}  high={n_high:>3}  low={n_low:>3}  →  {verdict}')
