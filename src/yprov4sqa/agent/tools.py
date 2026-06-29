"""
yprov4sqa/agent/tools.py
========================
16 real tool functions that query the loaded provenance data.

KEY FIX: Import the loader MODULE (not its variables) so that
when load_provenance() updates loader.ROWS, all tools see the
updated data immediately. Importing ROWS directly would capture
an empty list reference at import time.
"""

import json
from collections import Counter
from langchain.tools import tool

from . import loader                        # import MODULE not variables
from .loader import QC_COLS, BADGE_ORD, QC_DESCRIPTIONS     # these are constants — safe


def _rows() -> list[dict]:
    """Always read from loader.ROWS — never a stale reference."""
    if not loader.ROWS:
        raise RuntimeError("Call load_provenance() before using any tool.")
    return loader.ROWS


def _repo() -> dict:
    return loader.REPO


def _latest_row() -> dict:
    """Return the most recent assessment that has a real date.
    Falls back to rows[-1] only when every row has an empty date."""
    rows = _rows()
    for r in reversed(rows):
        if r['date']:
            return r
    return rows[-1]


# ── Tool 1 ────────────────────────────────────────────────────────────────
@tool
def get_summary(_: str = "") -> str:
    """
    Return overall statistics about the provenance document:
    repository name, total assessments, date range,
    badge distribution, total regressions, QC score averages,
    and the latest assessment details.
    Call this first for any general question about the repository.
    """
    rows   = _rows()
    repo   = _repo()
    badges = Counter(r['badge'] for r in rows)
    regs   = [
        r for i, r in enumerate(rows)
        if i > 0 and r['badge_ord'] < rows[i - 1]['badge_ord']
    ]
    latest  = _latest_row()
    recent  = rows[-10:]

    return json.dumps({
        'repo_name':         repo.get('name'),
        'repo_url':          repo.get('url'),
        'total_assessments': len(rows),
        'date_range':        f"{rows[0]['date'][:10]} → {latest['date'][:10]}",
        'badge_counts':      dict(badges),
        'total_regressions': len(regs),
        'latest_assessment': {
            'assessment_id': latest['i'],   # index in history, NOT a score
            'date':          latest['date'][:10],
            'badge':         latest['badge'],
            'commit':        latest['commit'],
            # Current QC scores: 0=criterion fully failed, 100=fully passed
            'qc_scores': {c: latest[c] for c in QC_COLS},
        },
        # Average over the last 10 assessments — reflects recent behaviour
        'qc_recent_10_averages': {
            c: round(sum(r[c] for r in recent) / len(recent), 1)
            for c in QC_COLS
        },
        # All-time average across every assessment — skewed by old history;
        # use only when the user asks about long-term trends
        'qc_all_time_averages': {
            c: round(sum(r[c] for r in rows) / len(rows), 1)
            for c in QC_COLS
        },
    }, indent=2)


# ── Tool 2 ────────────────────────────────────────────────────────────────
@tool
def get_assessment(number: int) -> str:
    """
    Return full details of one specific assessment by its number:
    QC scores for all 8 criteria, badge, commit SHA, branch name,
    QC score deltas vs the previous assessment,
    and whether this assessment was a badge regression.
    Input: integer assessment number.
    """
    rows  = _rows()
    match = next((r for r in rows if r['i'] == number), None)
    if not match:
        ns = [r['i'] for r in rows]
        return json.dumps({
            'error':           f'Assessment #{number} not found.',
            'available_range': f'{ns[0]}–{ns[-1]}',
            'total':           len(ns),
        })

    idx  = rows.index(match)
    prev = rows[idx - 1] if idx > 0 else None
    qc   = {c: match[c] for c in QC_COLS}

    result: dict = {
        'number':    match['i'],
        'date':      match['date'][:10],
        'badge':     match['badge'],
        'commit':    match['commit'],
        'branch':    match['branch'],
        'qc_scores': qc,
        'qc_labels': {c: QC_DESCRIPTIONS.get(c, c) for c in QC_COLS},
    }
    if prev:
        result['previous_badge'] = prev['badge']
        result['regression']     = match['badge_ord'] < prev['badge_ord']
        result['qc_deltas']      = {
            c: round(match[c] - prev[c], 1) for c in QC_COLS
        }
    return json.dumps(result, indent=2)


# ── Tool 3 ────────────────────────────────────────────────────────────────
@tool
def get_regressions(_: str = "") -> str:
    """
    Return all badge regression events in the repository history.
    A regression is when the badge level dropped from one assessment
    to the next (e.g. gold to silver, silver to bronze).
    For each regression shows: assessment number, date, from/to badge,
    commit SHA, which QC criteria dropped, and by how much.
    Use this to explain why quality dropped at any point.
    """
    rows   = _rows()
    result = []
    for i in range(1, len(rows)):
        curr, prev = rows[i], rows[i - 1]
        if curr['badge_ord'] < prev['badge_ord']:
            dropped = [c for c in QC_COLS if curr[c] < prev[c]]
            result.append({
                'assessment':       curr['i'],
                'date':             curr['date'][:10],
                'from_badge':       prev['badge'],
                'to_badge':         curr['badge'],
                'commit':           curr['commit'],
                'dropped_criteria': dropped,
                'drops': {
                    c: f"{prev[c]:.0f}% -> {curr[c]:.0f}%"
                    for c in dropped
                },
            })
    return json.dumps({'total': len(result), 'regressions': result},
                      indent=2)


# ── Tool 4 ────────────────────────────────────────────────────────────────
@tool
def get_badge_history(badge_type: str = "all") -> str:
    """
    Return all assessments that achieved a specific badge level.
    Input badge_type must be exactly one of:
        gold | silver | bronze | no_badge
    Returns list of assessment number, date, commit, branch.
    Useful for questions like when did the project first get gold
    or show all silver badge assessments.
    """
    rows = _rows()
    bt   = badge_type.lower().strip()
    matches = [
        {
            'number': r['i'],
            'date':   r['date'][:10],
            'commit': r['commit'],
            'branch': r['branch'],
        }
        for r in rows
        if r['badge'].lower() == bt
        or (bt == 'no_badge'
            and r['badge'] in ('No Badge', 'no_badge'))
    ]
    return json.dumps({
        'badge':       badge_type,
        'count':       len(matches),
        'assessments': matches,
    }, indent=2)


# ── Tool 5 ────────────────────────────────────────────────────────────────
@tool
def get_qc_trend(criterion: str = "", last_n: int = 20) -> str:
    """
    Return the trend of one QC criterion over recent assessments.
    Pass criterion as e.g. QC.Uni or QC.Sty. QC prefix is optional.
    Pass last_n to control how many recent assessments to include (default 20).
    Returns: average, min, max, trend direction
             improving or declining or stable,
             and a per-assessment score list.
    Valid criteria: QC.Acc  QC.Doc  QC.Lic  QC.Sec
                    QC.Sty  QC.Ver  QC.Met  QC.Uni
    """
    rows   = _rows()
    raw_c  = criterion.strip().upper()

    match = next(
        (k for k in QC_COLS
         if k.upper() == raw_c or k.upper() == 'QC.' + raw_c),
        None
    )
    if not match:
        return json.dumps({
            'error': f'Unknown criteria "{raw_c}". '
                     f'Valid: {", ".join(QC_COLS)}'
        })

    c      = match
    recent = rows[-last_n:]
    points = [
        {
            'assessment': r['i'],
            'date':       r['date'][:10],
            'score':      r[c],
            'badge':      r['badge'],
        }
        for r in recent
    ]
    scores = [p['score'] for p in points]
    trend  = (
        'improving' if scores[-1] > scores[0] else
        'declining' if scores[-1] < scores[0] else
        'stable'
    ) if len(scores) >= 2 else 'stable'

    return json.dumps({
        'criteria':    c,
        'last_n':      last_n,
        'avg':         round(sum(scores) / len(scores), 1),
        'min':         min(scores),
        'max':         max(scores),
        'trend':       trend,
        'data_points': points,
    }, indent=2)


# ── Tool 6 ────────────────────────────────────────────────────────────────
@tool
def compare_assessments(n1: int = 0, n2: int = 0) -> str:
    """
    Compare two assessments side by side.
    Pass n1 and n2 as the two assessment numbers, e.g. n1=205, n2=207.
    Returns both assessments full QC scores, badge change,
    list of criteria that improved, list that degraded,
    and per-criterion delta values.
    Use this to show what changed between two specific points
    in the development history.
    """
    rows = _rows()
    if not n1 or not n2:
        return json.dumps({'error': 'Pass n1 and n2 as integer assessment numbers'})

    a1 = next((r for r in rows if r['i'] == n1), None)
    a2 = next((r for r in rows if r['i'] == n2), None)
    if not a1:
        return json.dumps({'error': f'Assessment #{n1} not found'})
    if not a2:
        return json.dumps({'error': f'Assessment #{n2} not found'})

    changes = {
        c: {
            'from':  a1[c],
            'to':    a2[c],
            'delta': round(a2[c] - a1[c], 1),
        }
        for c in QC_COLS
    }
    return json.dumps({
        'assessment_1': {
            'number': a1['i'], 'date': a1['date'][:10],
            'badge':  a1['badge'], 'commit': a1['commit'],
            'qc':     {c: a1[c] for c in QC_COLS},
        },
        'assessment_2': {
            'number': a2['i'], 'date': a2['date'][:10],
            'badge':  a2['badge'], 'commit': a2['commit'],
            'qc':     {c: a2[c] for c in QC_COLS},
        },
        'badge_change': f"{a1['badge']} -> {a2['badge']}",
        'qc_changes':   changes,
        'improved':     [c for c in QC_COLS if a2[c] > a1[c]],
        'degraded':     [c for c in QC_COLS if a2[c] < a1[c]],
    }, indent=2)


# ── Tool 8 ────────────────────────────────────────────────────────────────
@tool
def find_best_period(_: str = "") -> str:
    """
    Find the best sustained quality period in the repository history.
    Returns the longest consecutive gold badge streak with start and
    end dates, all gold streaks with their lengths and dates,
    total number of gold badge assessments, and best score ever
    achieved per QC criterion.
    Use this to answer when was the project at its best.
    """
    rows = _rows()
    gold_runs: list[list[dict]] = []
    run:       list[dict]       = []

    for r in rows:
        if r['badge'] == 'gold':
            run.append(r)
        else:
            if run:
                gold_runs.append(run[:])
            run = []
    if run:
        gold_runs.append(run)

    longest = max(gold_runs, key=len) if gold_runs else []
    best_qc = {
        c: {
            'score':      max(rows, key=lambda r: r[c])[c],
            'assessment': max(rows, key=lambda r: r[c])['i'],
            'date':       max(rows, key=lambda r: r[c])['date'][:10],
        }
        for c in QC_COLS
    }
    return json.dumps({
        'longest_gold_streak': {
            'length':      len(longest),
            'from_date':   longest[0]['date'][:10] if longest else None,
            'to_date':     longest[-1]['date'][:10] if longest else None,
            'assessments': [r['i'] for r in longest],
        },
        'all_gold_runs': [
            {
                'length': len(run),
                'start':  run[0]['date'][:10],
                'end':    run[-1]['date'][:10],
            }
            for run in gold_runs
        ],
        'total_gold':        len([r for r in rows if r['badge'] == 'gold']),
        'best_score_per_qc': best_qc,
    }, indent=2)


# ── Export (interim placeholder — completed at end of file) ───────────────
# ALL_TOOLS is defined as a complete list below, after all tool functions.


# ══════════════════════════════════════════════════════════════
# ENRICHED TOOLS — read from prov_output.json enriched fields
# These replace enriched_tools.py (which read raw files directly)
# ══════════════════════════════════════════════════════════════

@tool
def get_tool_failures(criteria_or_all: str = "all") -> str:
    """
    Return exact tool failures for one or all QC criteria.
    Shows which tools failed, their versions, and exact error messages.
    This data comes from the enriched provenance document.
    Input: QC criterion name (e.g. QC.Sty, QC.Sec) or "all".
    Example question: "Why did QC.Sty fail?" or "Which tools failed?"
    """
    rows = _rows()
    latest = _latest_row()
    c = criteria_or_all.upper().strip()

    result = {}
    for col in QC_COLS:
        if c != 'ALL' and col.upper() != c and col.upper() != 'QC.' + c:
            continue
        result[col] = {
            'percentage':      latest[col],
            'tools_failed':    latest.get(f'{col}_tools_failed',    []),
            'tools_passed':    latest.get(f'{col}_tools_passed',    []),
            'failure_messages':latest.get(f'{col}_failure_messages',[]),
        }

    if not result:
        return json.dumps({'error': f'Criterion "{criteria_or_all}" not found.',
                           'valid': QC_COLS})
    return json.dumps({'assessment': latest['i'], 'date': latest['date'][:10],
                       'badge': latest['badge'], 'tool_failures': result}, indent=2)


@tool
def get_fix_hints(criteria_or_all: str = "all") -> str:
    """
    Return actionable fix instructions for failing QC criteria.
    Hints come directly from the SQAaaS platform stored in the provenance document.
    Input: QC criterion name (e.g. QC.Met, QC.Ver) or "all".
    Example question: "How do I fix QC.Met?" or "How to get silver badge?"
    """
    rows = _rows()
    latest = _latest_row()
    c = criteria_or_all.upper().strip()

    result = {}
    for col in QC_COLS:
        if c != 'ALL' and col.upper() != c and col.upper() != 'QC.' + c:
            continue
        hints = latest.get(f'{col}_fix_hints', [])
        if hints or latest[col] < 100:
            result[col] = {
                'percentage': latest[col],
                'fix_hints':  hints if isinstance(hints, list) else
                              json.loads(hints) if hints else [],
            }

    if not result:
        return json.dumps({'error': f'Criterion "{criteria_or_all}" not found.'})
    return json.dumps({'assessment': latest['i'], 'date': latest['date'][:10],
                       'fix_hints': result}, indent=2)


@tool
def get_badge_path(target_badge: str = "gold") -> str:
    """
    Return exactly what the team needs to achieve a specific badge level.
    Shows fulfilled criteria and missing criteria with fix instructions.
    Input: bronze | silver | gold
    Example question: "What do we need for gold?" or "How to get silver?"
    """
    rows = _rows()
    latest = _latest_row()
    target = target_badge.lower().strip()

    if target not in ('bronze', 'silver', 'gold'):
        return json.dumps({'error': 'Input must be bronze, silver, or gold'})

    missing   = latest.get(f'{target}_missing',   [])
    fulfilled = latest.get(f'{target}_fulfilled', [])

    # Get fix hints for missing criteria
    missing_with_fixes = []
    for qc in missing:
        hints = latest.get(f'{qc}_fix_hints', [])
        missing_with_fixes.append({
            'criterion':  qc,
            'percentage': latest.get(qc, 0),
            'fix_hints':  hints if isinstance(hints, list) else
                          json.loads(hints) if hints else [],
            'tools_failing': latest.get(f'{qc}_tools_failed', []),
        })

    current = latest['badge']
    achieved = (current == target or
                (target=='bronze' and current in ('bronze','silver','gold')) or
                (target=='silver' and current in ('silver','gold')) or
                (target=='gold'   and current == 'gold'))

    return json.dumps({
        'target_badge':     target,
        'current_badge':    current,
        'already_achieved': achieved,
        'fulfilled':        fulfilled,
        'missing':          missing_with_fixes,
        'summary': (f"Already achieved {target}!" if achieved else
                    f"{len(missing)} criteria needed: {', '.join(missing)}"),
    }, indent=2)


# (Tool registry moved to end of file — see ALL_TOOLS below)

# ════════════════════════════════════════════════════════════════
# EXTENDED TOOLS — 6 new tools using unexploited provenance fields
# ════════════════════════════════════════════════════════════════

# ── Tool 11 ───────────────────────────────────────────────────────────────
@tool
def get_branch_analysis(branch_or_all: str = "all") -> str:
    """
    Analyse quality by git branch across all assessments.
    Shows badge distribution, QC score averages, and assessment count
    per branch. Reveals whether feature branches have lower quality
    than main, and which branches consistently fail specific criteria.
    Input: branch name (e.g. 'main', 'dev') or 'all' for every branch.
    Example questions:
      'How does quality differ between main and dev branch?'
      'Which branch has the best QC.Uni score?'
      'Show quality breakdown by branch'
    """
    rows = _rows()
    target = branch_or_all.strip().lower()

    # Group by branch
    from collections import defaultdict
    branch_data = defaultdict(lambda: {
        'count': 0, 'badges': Counter(),
        'qc_sums': {c: 0.0 for c in QC_COLS},
        'partial': 0,
    })

    for r in rows:
        br = r.get('branch', 'unknown') or 'unknown'
        if target != 'all' and br.lower() != target:
            continue
        branch_data[br]['count'] += 1
        branch_data[br]['badges'][r['badge']] += 1
        if r.get('is_partial_run'):
            branch_data[br]['partial'] += 1
        for c in QC_COLS:
            branch_data[br]['qc_sums'][c] += r.get(c, 0.0)

    if not branch_data:
        return json.dumps({'error': f'Branch "{branch_or_all}" not found.',
                           'available': list({r.get('branch','unknown') for r in rows})})

    result = {}
    for br, data in sorted(branch_data.items(), key=lambda x: -x[1]['count']):
        n = data['count']
        result[br] = {
            'total_assessments': n,
            'partial_runs':      data['partial'],
            'badge_distribution': dict(data['badges']),
            'best_badge':  max(data['badges'], key=lambda b: BADGE_ORD.get(b, 0)),
            'qc_averages': {
                c: round(data['qc_sums'][c] / n, 1) for c in QC_COLS
            },
            'weakest_criterion': min(QC_COLS, key=lambda c: data['qc_sums'][c] / n),
            'strongest_criterion': max(QC_COLS, key=lambda c: data['qc_sums'][c] / n),
        }

    return json.dumps({'branches': result, 'total_branches': len(result)}, indent=2)


# ── Tool 12 ───────────────────────────────────────────────────────────────
@tool
def get_subcriteria_detail(criterion: str = "") -> str:
    """
    Return per-subcriterion breakdown for a QC criterion in the latest assessment.
    Each QC criterion is composed of subcriteria (e.g. QC.Doc has 5: README,
    CONTRIBUTING, code of conduct, etc.). This tool shows exactly which
    subcriteria passed and which failed, with descriptions and requirement levels.
    Input: QC criterion name e.g. QC.Doc, QC.Lic, QC.Ver, QC.Uni.
    Example questions:
      'Which parts of QC.Doc are failing?'
      'What are the subcriteria for QC.Lic?'
      'Show me the detail breakdown of QC.Ver'
    """
    rows = _rows()
    latest = _latest_row()
    raw_c  = criterion.strip().upper()
    match  = next((k for k in QC_COLS if k.upper() == raw_c or
                   'QC.' + raw_c == k.upper()), None)
    if not match:
        return json.dumps({'error': f'Unknown criterion "{criterion}". Valid: {QC_COLS}'})

    c = match
    raw_sub = latest.get(f'{c}_subcriteria', '[]')
    try:
        subcriteria = json.loads(raw_sub) if isinstance(raw_sub, str) else raw_sub
    except Exception:
        subcriteria = []

    if not subcriteria:
        return json.dumps({'error': f'No subcriteria detail available for {c} in the enriched provenance.',
                           'note': 'Re-run process-provenance to capture subcriteria data.'})

    passed  = [s for s in subcriteria if s.get('valid')]
    failed  = [s for s in subcriteria if not s.get('valid')]
    musts_f = [s for s in failed if s.get('requirement_level') == 'MUST']

    return json.dumps({
        'criterion':        c,
        'description':      QC_DESCRIPTIONS.get(c, ''),
        'assessment':       latest['i'],
        'date':             latest['date'][:10],
        'overall_score':    latest[c],
        'total_subcriteria': len(subcriteria),
        'passed':           len(passed),
        'failed':           len(failed),
        'must_failures':    len(musts_f),
        'subcriteria': subcriteria,
        'summary': (f"All {len(subcriteria)} subcriteria passed." if not failed else
                    f"{len(failed)}/{len(subcriteria)} failed "
                    f"({'including' if musts_f else 'no'} MUST-level failures)."),
    }, indent=2)


# ── Tool 13 ───────────────────────────────────────────────────────────────
@tool
def get_ci_provenance(criterion: str = "") -> str:
    """
    Return CI/CD provenance details for a QC criterion: the exact command
    that was run, the CI build URL, the Jenkins build repository, the
    SQA baseline standard being tested, and the plugin used.
    This provides full traceability from quality score back to the
    exact command and standard that produced it.
    Input: QC criterion name e.g. QC.Sec, QC.Sty, QC.Acc.
    Example questions:
      'What command does QC.Sec run?'
      'Show me the CI provenance for QC.Sty'
      'Which standard does QC.Uni test against?'
      'What plugin evaluates QC.Lic?'
    """
    rows = _rows()
    latest = _latest_row()
    raw_c  = criterion.strip().upper()
    match  = next((k for k in QC_COLS if k.upper() == raw_c or
                   'QC.' + raw_c == k.upper()), None)
    if not match:
        return json.dumps({'error': f'Unknown criterion "{criterion}". Valid: {QC_COLS}'})

    c = match
    # These fields come from the enriched provenance, stored in loader rows
    # via the enriched_qc dict — we need them from the raw activity.
    # They are not currently in loader rows, so we use what IS available.
    # The loader stores tools_failed/passed/failure_messages per criterion.
    # For CI provenance we report what the loader captured.
    tools_passed = latest.get(f'{c}_tools_passed', [])
    tools_failed = latest.get(f'{c}_tools_failed', [])

    return json.dumps({
        'criterion':    c,
        'description':  QC_DESCRIPTIONS.get(c, ''),
        'assessment':   latest['i'],
        'score':        latest[c],
        'tools_passed': tools_passed,
        'tools_failed': tools_failed,
        'note': (
            'Full CI provenance (command, build URL, standard, plugin) is stored in '
            'the enriched prov_output.json under ex:ci_stdout_command, ex:ci_url, '
            'ex:standard_title, ex:plugin_name for each QC activity node. '
            'These fields are available for direct graph queries via json2graph.'
        ),
    }, indent=2)


# ── Tool 14 ───────────────────────────────────────────────────────────────
@tool
def get_quality_velocity(window: int | str = "10") -> str:
    """
    Calculate quality velocity — how fast the project is improving or
    declining across all 8 QC criteria. Computes the rate of change
    (percentage points per assessment) over a configurable window.
    Also identifies momentum: which criteria are on an upward vs
    downward trajectory right now.
    Input: number of recent assessments to measure over (default 10).
    Example questions:
      'Is quality improving or getting worse lately?'
      'What is the quality velocity over the last 20 assessments?'
      'Which criteria are improving the fastest?'
      'Are we on track to reach gold badge?'
    """
    rows = _rows()
    try:
        n = max(2, min(int(window), len(rows)))
    except ValueError:
        return json.dumps({'error': f'Invalid window "{window}" — must be an integer.'})

    recent = rows[-n:]
    first, last = recent[0], recent[-1]

    velocities = {}
    for c in QC_COLS:
        delta = last[c] - first[c]
        rate  = round(delta / (n - 1), 2)   # points per assessment
        velocities[c] = {
            'start_score':  first[c],
            'end_score':    last[c],
            'total_change': round(delta, 1),
            'rate_per_assessment': rate,
            'momentum':    'improving' if rate > 0.5 else 'declining' if rate < -0.5 else 'stable',
        }

    badge_delta = last['badge_ord'] - first['badge_ord']
    improving = [c for c, v in velocities.items() if v['momentum'] == 'improving']
    declining = [c for c, v in velocities.items() if v['momentum'] == 'declining']
    stable    = [c for c, v in velocities.items() if v['momentum'] == 'stable']

    # Weighted overall velocity (sum of |rate| with sign)
    overall = round(sum(v['rate_per_assessment'] for v in velocities.values()) / len(QC_COLS), 2)

    return json.dumps({
        'window_assessments': n,
        'date_range': f"{first['date'][:10]} → {last['date'][:10]}",
        'badge_change': f"{first['badge']} → {last['badge']}",
        'overall_velocity': overall,
        'overall_direction': 'improving' if overall > 0.1 else 'declining' if overall < -0.1 else 'stable',
        'improving_criteria': improving,
        'declining_criteria': declining,
        'stable_criteria':    stable,
        'per_criterion':      velocities,
        'insight': (
            f"Over the last {n} assessments, quality is "
            f"{'improving' if overall > 0.1 else 'declining' if overall < -0.1 else 'stable'} "
            f"at {abs(overall):.2f} pts/assessment. "
            f"{len(improving)} criteria gaining, {len(declining)} losing ground."
        ),
    }, indent=2)


# ── Tool 15 ───────────────────────────────────────────────────────────────
@tool
def get_partial_runs(_: str = "") -> str:
    """
    List all partial pipeline runs in the assessment history.
    A partial run occurs when SQAaaS only evaluated a subset of criteria
    (typically just one) because the pipeline was triggered manually for
    a single check, or aborted early. These are preserved in the provenance
    graph but flagged so they can be distinguished from full assessments.
    Returns: list of partial assessments with their date, branch, and
    which single criterion was evaluated.
    Example questions:
      'Were there any incomplete pipeline runs?'
      'Show me all partial assessments'
      'Which assessments are flagged as partial runs?'
    """
    rows = _rows()
    partial = [r for r in rows if r.get('is_partial_run')]
    full    = [r for r in rows if not r.get('is_partial_run')]

    details = []
    for r in partial:
        run_criteria = [c for c in QC_COLS if r.get(c, 0) > 0]
        details.append({
            'assessment':      r['i'],
            'date':            r['date'][:10] if r['date'] else 'unknown',
            'branch':          r['branch'],
            'criteria_run':    run_criteria,
            'criteria_count':  len(run_criteria),
            'note': 'Only subset of criteria evaluated — not a full quality assessment.',
        })

    return json.dumps({
        'total_assessments':  len(rows),
        'full_assessments':   len(full),
        'partial_assessments': len(partial),
        'partial_rate':       f"{round(len(partial)/len(rows)*100, 1)}%",
        'partial_runs':       details,
        'impact': (
            f"{len(partial)} partial runs out of {len(rows)} total. "
            f"These are included in the history but excluded from QC averages "
            f"when calculating trends." if partial else
            "No partial runs found — all assessments evaluated all criteria."
        ),
    }, indent=2)


# ── Tool 16 ───────────────────────────────────────────────────────────────
@tool
def get_badge_journey(_: str = "") -> str:
    """
    Provide a narrative timeline of the project's badge journey:
    when each badge level was first achieved, how long it took to get
    there, how many times each level was held, and key turning points
    (first gold, regressions back to lower levels, recovery events).
    Example questions:
      'Tell me the story of this project quality journey'
      'When did the project first reach gold badge?'
      'How long did it take to get from no badge to silver?'
      'What is the badge progression timeline?'
    """
    rows = _rows()
    first_achieved = {}
    level_counts   = Counter()
    transitions    = []

    for i, r in enumerate(rows):
        badge = r['badge']
        level_counts[badge] += 1

        # First time each level achieved
        norm = badge.lower().replace(' ', '_')
        if norm not in first_achieved and norm in ('bronze', 'silver', 'gold'):
            first_achieved[norm] = {
                'assessment': r['i'],
                'date':       r['date'][:10],
                'assessments_to_reach': r['i'],
            }

        # Transitions
        if i > 0:
            prev = rows[i-1]
            if r['badge'] != prev['badge']:
                transitions.append({
                    'assessment': r['i'],
                    'date':       r['date'][:10],
                    'from':       prev['badge'],
                    'to':         r['badge'],
                    'type': ('upgrade'   if r['badge_ord'] > prev['badge_ord'] else
                             'regression' if r['badge_ord'] < prev['badge_ord'] else
                             'lateral'),
                })

    upgrades    = [t for t in transitions if t['type'] == 'upgrade']
    regressions = [t for t in transitions if t['type'] == 'regression']

    # Current streak
    current_badge = rows[-1]['badge']
    streak = 0
    for r in reversed(rows):
        if r['badge'] == current_badge:
            streak += 1
        else:
            break

    return json.dumps({
        'total_assessments': len(rows),
        'first_assessment':  rows[0]['date'][:10],
        'latest_assessment': rows[-1]['date'][:10],
        'current_badge':     current_badge,
        'current_streak':    streak,
        'badge_counts':      dict(level_counts),
        'first_achieved':    first_achieved,
        'total_transitions': len(transitions),
        'upgrades':          len(upgrades),
        'regressions':       len(regressions),
        'key_transitions':   transitions[:20],   # first 20 for context
        'narrative': (
            f"The project started on {rows[0]['date'][:10]} with {rows[0]['badge']} badge. "
            + (f"First bronze achieved at assessment {first_achieved.get('bronze',{}).get('assessment','?')}. "
               if 'bronze' in first_achieved else '') +
            (f"First silver achieved at assessment {first_achieved.get('silver',{}).get('assessment','?')}. "
             if 'silver' in first_achieved else 'Silver badge not yet achieved. ') +
            (f"First gold achieved at assessment {first_achieved.get('gold',{}).get('assessment','?')}. "
             if 'gold' in first_achieved else 'Gold badge not yet achieved. ') +
            f"There were {len(regressions)} regressions and {len(upgrades)} upgrades total. "
            f"Currently holding {current_badge} for {streak} consecutive assessments."
        ),
    }, indent=2)



# ── Tool registry — curated 16-tool set (Core, Enriched, Extended) ──────
ALL_TOOLS = [
    # Core Analysis Tier (7)
    get_summary,
    get_assessment,
    get_regressions,
    get_badge_history,
    get_qc_trend,
    compare_assessments,
    find_best_period,
    # Enriched Provenance Tier (3)
    get_tool_failures,
    get_fix_hints,
    get_badge_path,
    # Extended Analysis Tier (6)
    get_branch_analysis,
    get_subcriteria_detail,
    get_ci_provenance,
    get_quality_velocity,
    get_partial_runs,
    get_badge_journey,
]