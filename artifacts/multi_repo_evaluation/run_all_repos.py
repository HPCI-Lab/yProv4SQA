"""
results/run_all_repos.py
========================
Fetch + process SQAaaS assessment reports for multiple repositories
and produce a summary table (results/summary.json + results/summary.csv).

Usage:
    cd /home/yousa/projects/yProv4SQA_AI/yProv4SQA
    export GITHUB_TOKEN=<your_token>
    python3 results/run_all_repos.py
"""

import os
import sys
import json
import time
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from yprov4sqa._fetcher   import fetch_assessment_reports
from yprov4sqa._provenance import process_all_files

# ── Repositories to evaluate ─────────────────────────────────────────────────
# (repo_name, github_owner/repo, language, domain)
REPOS = [
    # name used by fetcher       # actual GitHub repo          # language  # domain
    ('itwinai',       'interTwin-eu/itwinai',                  'Python',   'HPC / AI'),
    ('im',            'grycap/im',                             'Python',   'Cloud infra'),
    ('oscar',         'grycap/oscar',                          'Go',       'Serverless / FaaS'),
    ('fedcloudclient','EGI-Federation/fedcloudclient',         'Python',   'Cloud federation'),
    ('SeisSol',       'SeisSol/SeisSol',                      'C++',      'HPC / Seismology'),
    ('o3api',         'EOSC-synergy/o3api',                    'Python',   'Climate science'),
]

RESULTS_DIR = Path(__file__).parent
_raw_token  = os.getenv('GITHUB_TOKEN', '')

# Validate token with a quick probe — fall back to unauthenticated if invalid
# (all eosc-synergy assess repos are public, so no token is fine)
TOKEN = None
if _raw_token:
    import requests as _req
    probe = _req.get(
        'https://api.github.com/repos/eosc-synergy/itwinai.assess.sqaaas',
        headers={'Authorization': f'token {_raw_token}'},
        timeout=10,
    )
    if probe.status_code == 200:
        TOKEN = _raw_token
        print(f"✓ GitHub token valid — authenticated (5000 req/hr)")
    else:
        print(f"⚠  GITHUB_TOKEN returned {probe.status_code} — clearing it, running unauthenticated (60 req/hr)")
        os.environ.pop('GITHUB_TOKEN', None)   # prevent _github.py from picking it up
else:
    print("⚠  GITHUB_TOKEN not set — running unauthenticated (60 req/hr)")

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_date(s):
    """Return YYYY-MM-DD or empty string."""
    if not s:
        return ''
    return str(s)[:10]

def summarise_reports(folder: Path) -> dict:
    """Count reports and extract date range + badge distribution."""
    files = sorted(f for f in folder.iterdir() if f.suffix == '.json')
    total = len(files)
    if total == 0:
        return {'total': 0, 'date_from': '', 'date_to': '', 'badges': {}}

    dates  = []
    badges = {'gold': 0, 'silver': 0, 'bronze': 0, 'none': 0}

    for fpath in files:
        try:
            data = json.loads(fpath.read_text())
            repo = data.get('repository', [])
            row  = repo[0] if isinstance(repo, list) and repo else (repo if isinstance(repo, dict) else {})
            d    = row.get('commit_date') or row.get('date', '')
            if d:
                dates.append(d[:10])
            badge = (data.get('pipeline_badge', {}) or {}).get('status', '').lower()
            if 'gold'   in badge: badges['gold']   += 1
            elif 'silver' in badge: badges['silver'] += 1
            elif 'bronze' in badge: badges['bronze'] += 1
            else:                   badges['none']   += 1
        except Exception:
            continue

    dates.sort()
    return {
        'total':     total,
        'date_from': dates[0]  if dates else '',
        'date_to':   dates[-1] if dates else '',
        'badges':    badges,
    }

def summarise_prov(prov_path: Path) -> dict:
    """Extract stats from a generated provenance document."""
    try:
        data       = json.loads(prov_path.read_text())
        entities   = data.get('entity',   {})
        activities = data.get('activity', {})
        agents     = data.get('agent',    {})

        # Assessment entities: ex:assessment1, ex:assessment2, …
        import re
        ass_keys = [k for k in entities if re.fullmatch(r'ex:assessment\d+', k)]
        n        = len(ass_keys)

        # Date range from entities
        dates = []
        for k in ass_keys:
            d = entities[k].get('ex:commit_date', '')
            if d:
                dates.append(d[:10])
        dates.sort()

        # Badge distribution
        badges = {'gold': 0, 'silver': 0, 'bronze': 0, 'none': 0}
        out_keys = [k for k in entities if re.fullmatch(r'ex:output\d+', k)]
        for k in out_keys:
            b = entities[k].get('ex:badge', '').lower()
            if   'gold'   in b: badges['gold']   += 1
            elif 'silver' in b: badges['silver'] += 1
            elif 'bronze' in b: badges['bronze'] += 1
            else:               badges['none']   += 1

        size_kb = round(prov_path.stat().st_size / 1024, 1)

        return {
            'assessments': n,
            'date_from':   dates[0]  if dates else '',
            'date_to':     dates[-1] if dates else '',
            'badges':      badges,
            'doc_size_kb': size_kb,
            'entities':    len(entities),
            'activities':  len(activities),
            'agents':      len(agents),
        }
    except Exception as e:
        print(f"  [warn] prov parse error: {e}")
        return {}

# ── Main loop ─────────────────────────────────────────────────────────────────

rows = []

for repo_name, gh_repo, language, domain in REPOS:
    print(f"\n{'='*60}")
    print(f"  {repo_name}  ({gh_repo})")
    print(f"{'='*60}")

    row = {
        'repo_name':   repo_name,
        'github_repo': gh_repo,
        'github_link': f'https://github.com/{gh_repo}',
        'sqaaas_link': f'https://github.com/eosc-synergy/{repo_name}.assess.sqaaas',
        'language':    language,
        'domain':      domain,
    }

    # ── Step 1: fetch ──────────────────────────────────────────────────────
    reports_dir = RESULTS_DIR / f'{repo_name}_SQAaaS_reports'

    if reports_dir.exists() and any(reports_dir.iterdir()):
        print(f"  [skip fetch] {reports_dir} already exists")
    else:
        t0 = time.time()
        try:
            out = fetch_assessment_reports(repo_name, token=TOKEN)
            reports_dir = Path(out) if out else reports_dir
            row['fetch_time_s'] = round(time.time() - t0, 1)
            print(f"  Fetched in {row['fetch_time_s']}s")
        except Exception as e:
            print(f"  [ERROR] fetch failed: {e}")
            row['error'] = str(e)
            rows.append(row)
            continue

    # ── Step 2: process ────────────────────────────────────────────────────
    prov_dir  = RESULTS_DIR / 'Provenance_documents'
    prov_dir.mkdir(exist_ok=True)
    prov_glob = list(prov_dir.glob(f'*{repo_name}*prov*.json'))

    if prov_glob:
        prov_path = prov_glob[0]
        print(f"  [skip process] {prov_path.name} already exists")
    else:
        t0 = time.time()
        try:
            # process_all_files saves to ./Provenance_documents/ relative to cwd
            os.chdir(str(RESULTS_DIR))
            prov_out  = process_all_files(str(reports_dir))
            gen_time  = round(time.time() - t0, 1)
            prov_path = Path(prov_out) if prov_out else None
            row['gen_time_s'] = gen_time
            print(f"  Processed in {gen_time}s → {prov_path}")
        except Exception as e:
            print(f"  [ERROR] process failed: {e}")
            row['error'] = str(e)
            rows.append(row)
            continue

    # ── Step 3: collect stats ──────────────────────────────────────────────
    if prov_path and prov_path.exists():
        stats = summarise_prov(prov_path)
        row.update(stats)
        print(f"  Assessments : {stats.get('assessments', '?')}")
        print(f"  Date range  : {stats.get('date_from', '?')} → {stats.get('date_to', '?')}")
        print(f"  Badges      : {stats.get('badges', {})}")
        print(f"  Doc size    : {stats.get('doc_size_kb', '?')} KB")
    else:
        # Fallback: stats from raw reports folder
        rpt_stats = summarise_reports(reports_dir)
        row.update({
            'assessments': rpt_stats['total'],
            'date_from':   rpt_stats['date_from'],
            'date_to':     rpt_stats['date_to'],
            'badges':      rpt_stats['badges'],
        })

    rows.append(row)

# ── Save JSON ─────────────────────────────────────────────────────────────────
out_json = RESULTS_DIR / 'summary.json'
out_json.write_text(json.dumps(rows, indent=2))
print(f"\n\nSaved: {out_json}")

# ── Save CSV ──────────────────────────────────────────────────────────────────
csv_cols = [
    'repo_name', 'github_link', 'sqaaas_link', 'language', 'domain',
    'assessments', 'date_from', 'date_to',
    'badges_gold', 'badges_silver', 'badges_bronze', 'badges_none',
    'doc_size_kb', 'entities', 'activities', 'agents',
    'fetch_time_s', 'gen_time_s', 'error',
]

out_csv = RESULTS_DIR / 'summary.csv'
with open(out_csv, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction='ignore')
    w.writeheader()
    for r in rows:
        flat = dict(r)
        b = flat.pop('badges', {})
        flat['badges_gold']   = b.get('gold',   0)
        flat['badges_silver'] = b.get('silver', 0)
        flat['badges_bronze'] = b.get('bronze', 0)
        flat['badges_none']   = b.get('none',   0)
        w.writerow(flat)

print(f"Saved: {out_csv}")

# ── Print table ───────────────────────────────────────────────────────────────
print("\n\n" + "="*90)
print("SUMMARY TABLE")
print("="*90)
header = f"{'Repo':<20} {'Assessments':>12} {'Date From':>12} {'Date To':>12} {'Gold':>6} {'Silver':>7} {'Bronze':>7} {'None':>5} {'Size KB':>8}"
print(header)
print("-"*90)
for r in rows:
    b = r.get('badges', {})
    print(f"{r['repo_name']:<20} {r.get('assessments',0):>12} {r.get('date_from',''):>12} {r.get('date_to',''):>12} {b.get('gold',0):>6} {b.get('silver',0):>7} {b.get('bronze',0):>7} {b.get('none',0):>5} {r.get('doc_size_kb',0):>8}")
print("="*90)
