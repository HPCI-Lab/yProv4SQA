"""
yprov4sqa/agent/loader.py
=========================
Parses the enriched prov_output.json into assessment row dicts.

Now reads BOTH original fields AND new enriched fields:
  Original: date, badge, QC percentages
  Enriched: tools_failed, failure_messages, fix_hints,
            badge_path (bronze/silver/gold missing/fulfilled)
"""

import json
import re

QC_COLS   = ['QC.Acc','QC.Doc','QC.Lic','QC.Sec',
             'QC.Sty','QC.Ver','QC.Met','QC.Uni']
BADGE_ORD = {'No Badge':0,'no_badge':0,'bronze':1,'silver':2,'gold':3}
QC_DESCRIPTIONS = {
    'QC.Acc': 'Code Accessibility: source code must be open, publicly available, and under a VCS (e.g. GitHub). NOT web/WCAG accessibility.',
    'QC.Doc': 'Documentation: covers target-audience and contribution-related documentation.',
    'QC.Lic': 'Licensing: resolves the legal aspects for source code reuse through license files.',
    'QC.Sec': 'Security: detects insecure patterns when writing code.',
    'QC.Sty': 'Code Style: fosters readability of the code by following a style standard.',
    'QC.Ver': 'Semantic Versioning: release tags must follow SemVer spec (e.g. v1.2.0).',
    'QC.Met': 'Code Metadata: citation metadata file required (CITATION.cff or codemeta.json).',
    'QC.Uni': 'Unit Testing: unit tests must exist, pass, and reach minimum 70% coverage.',
}

ROWS:      list[dict] = []
REPO:      dict       = {}
PROV_PATH: str        = ''   # absolute path to the loaded prov_output.json


def load_provenance(path: str) -> tuple[list[dict], dict]:
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)

    global ROWS, REPO, PROV_PATH
    import os as _os
    PROV_PATH = _os.path.abspath(path)
    entities   = raw.get('entity',   {})
    activities = raw.get('activity', {})

    rows = []
    # Collect all assessment indices that actually exist in the document.
    # Using a key-driven scan avoids early termination when an index is missing
    # (e.g. a skipped or deleted report), which would silently drop all later data.
    import re as _re
    all_indices = sorted(
        int(m.group(1))
        for k in entities
        if (m := _re.fullmatch(r'ex:assessment(\d+)', k))
    )
    for i in all_indices:
        a_key, o_key = f'ex:assessment{i}', f'ex:output{i}'
        if a_key not in entities or o_key not in entities:
            continue  # skip corrupt/incomplete pairs

        a = entities[a_key]
        o = entities[o_key]

        date   = (a.get('ex:commit_date',[''])[0]
                  if isinstance(a.get('ex:commit_date'), list)
                  else a.get('ex:commit_date',''))
        badge  = o.get('ex:badge_won','No Badge')
        commit = ((a.get('ex:commit_id',[''])[0]
                   if isinstance(a.get('ex:commit_id'), list)
                   else a.get('ex:commit_id','')))[:12]
        branch = (a.get('ex:branch_name',[''])[0]
                  if isinstance(a.get('ex:branch_name'), list)
                  else a.get('ex:branch_name',''))
        sqaaas_version = (a.get('ex:version',[''])[0]
                          if isinstance(a.get('ex:version'), list)
                          else a.get('ex:version',''))
        report_permalink = (a.get('ex:report_permalink',[''])[0]
                            if isinstance(a.get('ex:report_permalink'), list)
                            else a.get('ex:report_permalink',''))
        open_badge_url = (o.get('ex:openBadgeId:str',[''])[0]
                          if isinstance(o.get('ex:openBadgeId:str'), list)
                          else o.get('ex:openBadgeId:str',''))

        # ── Original QC scores ────────────────────────────────
        # Use fullmatch with anchored index to avoid suffix collisions:
        # e.g. endswith('1') wrongly matches ex:qc_QC.Acc11, ex:qc_QC.Acc21, etc.
        qc = {}
        for k, v in activities.items():
            m = re.fullmatch(rf'ex:qc_([A-Za-z.]+)_{i}', k)
            if m:
                nm = m.group(1)
                try:
                    qc[nm] = float(
                        v.get('ex:percentage','0%').replace('%','')
                    )
                except ValueError:
                    qc[nm] = 0.0

        # ── Enriched QC fields ────────────────────────────────
        enriched_qc = {}
        for k, v in activities.items():
            m = re.fullmatch(rf'ex:qc_([A-Za-z.]+)_{i}', k)
            if m:
                nm = m.group(1)

                # tools_failed / tools_passed
                enriched_qc[f'{nm}_tools_failed'] = v.get('ex:tools_failed', [])
                enriched_qc[f'{nm}_tools_passed'] = v.get('ex:tools_passed', [])
                enriched_qc[f'{nm}_failure_messages'] = v.get('ex:failure_messages', [])

                # fix_hints — stored as JSON string
                raw_hints = v.get('ex:fix_hints', '[]')
                try:
                    enriched_qc[f'{nm}_fix_hints'] = (
                        json.loads(raw_hints)
                        if isinstance(raw_hints, str) else raw_hints
                    )
                except Exception:
                    enriched_qc[f'{nm}_fix_hints'] = []

                # subcriteria_summary — stored as JSON string
                raw_sub = v.get('ex:subcriteria_summary', '[]')
                try:
                    enriched_qc[f'{nm}_subcriteria'] = (
                        json.loads(raw_sub)
                        if isinstance(raw_sub, str) else raw_sub
                    )
                except Exception:
                    enriched_qc[f'{nm}_subcriteria'] = []

        # ── Badge path from Output entity ─────────────────────
        badge_enriched = {}
        for level in ('bronze', 'silver', 'gold'):
            badge_enriched[f'{level}_missing']   = o.get(f'ex:{level}_missing',   [])
            badge_enriched[f'{level}_fulfilled']  = o.get(f'ex:{level}_fulfilled', [])

        # ── Full row ──────────────────────────────────────────
        rows.append({
            'i':          i,
            'date':       date,
            'badge':      badge,
            'badge_ord':  BADGE_ORD.get(badge, 0),
            'commit':     commit,
            'branch':     branch,
            'sqaaas_version':   sqaaas_version,
            'report_permalink': report_permalink,
            'open_badge_url':   open_badge_url,
            'is_partial_run':   bool(a.get('ex:is_partial_run', False)),
            **{c: qc.get(c, 0.0) for c in QC_COLS},
            **enriched_qc,
            **badge_enriched,
        })

    # Sort by date, but keep empty dates at the end so they don't mess with first/last
    rows.sort(key=lambda r: (r['date'] == '', r['date']))

    repo_raw = entities.get('ex:repository1', {})
    REPO = {
        'name': repo_raw.get('ex:name', ''),
        'url':  repo_raw.get('ex:url',  ''),
    }
    ROWS = rows

    if rows:
        print(f"[loader] {len(rows)} assessments  "
              f"{rows[0]['date'][:10]} → {rows[-1]['date'][:10]}"
              f"  repo={REPO['name']}")
    else:
        print(f"[loader] WARNING: no assessments found in {path}")

    return ROWS, REPO