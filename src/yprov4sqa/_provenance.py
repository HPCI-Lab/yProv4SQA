# yprov4sqa/_provenance.py  (final enriched version)
"""
Enriched provenance processor.

Every QualityCheck activity node now contains:
  ORIGINAL:  percentage, total/success_subcriteria, valid
  ENRICHED:  tools_failed, tools_passed, failure_messages,
             fix_hints, subcriteria_summary, requirement_level,
             standard_title/version/url, plugin_name/version,
             tool_level, build_repo, ci_url,
             ci_stdout_command, ci_stdout_text (500 chars),
             required_for_next_level_badge

Every Output entity now contains:
  ORIGINAL:  badge_won, issuedOn, etc.
  ENRICHED:  badge_path, bronze/silver/gold missing+fulfilled,
             verification_url

Every Assessment entity now contains:
  ORIGINAL:  commit_id, branch, version
  ENRICHED:  report_permalink, is_main_repo
"""

import os, re, json, argparse
from pathlib import Path

from .models.provenance_model        import ProvenanceModel
from .models.repository              import Repository
from .models.assessment              import Assessment
from .models.agent                   import Agent
from .models.quality_check           import QualityCheck
from .models.output                  import Output
from .models.provenance_relationship import ProvenanceRelationship

# Filename written by _fetcher.py: {YYYY-MM-DDTHH_MM_SSZ}_{index}_{hash}_{branch}.json
# Example: 2024-07-02T18_37_32Z_0001_1291_main.json
_FNAME_DATE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}Z)')


def _date_from_filename(file_path: str) -> str:
    """Extract commit date from the new-style fetcher filename, or '' if not present."""
    stem = Path(file_path).stem
    m = _FNAME_DATE_RE.match(stem)
    if m:
        raw = m.group(1)
        return raw[:11] + raw[11:].replace('_', ':')
    return ''


def _normalise_iso(ts: str) -> str:
    """Trim nanosecond badge timestamps to microsecond precision."""
    if not ts:
        return ''
    ts = ts.strip()
    if '.' in ts:
        base, frac = ts.split('.', 1)
        frac = frac.rstrip('Z')[:6]
        return f'{base}.{frac}Z'
    return ts


def _assessment_date(file_path: str, report_data: dict) -> str:
    """
    Resolve the best available date for an assessment, with a three-level fallback:

    1. Filename date  — present when files were fetched with fetch-sqa-reports
                        (new format: YYYY-MM-DDTHH_MM_SSZ_NNNN_hash_branch.json).
    2. badge.software.data.createdAt — the badge assertion timestamp embedded in
                        the report itself. Available in all reports that earned a
                        badge. Close enough to the assessment time for ordering.
    3. badge.software.data.issuedOn  — same assertion, alternative field name.
    4. Empty string   — only for 'no_badge' reports with no date in the filename
                        (older format). Honest: we have no date without an API call.
    """
    # Level 1: filename
    date = _date_from_filename(file_path)
    if date:
        return date

    # Level 2 & 3: badge assertion timestamp inside the report
    badge_data = report_data.get('badge', {}).get('software', {}).get('data', {})
    for field in ('createdAt', 'issuedOn'):
        ts = badge_data.get(field, '')
        if ts:
            return _normalise_iso(ts)

    return ''


def _unwrap(val):
    """Return val[0] if val is a single-element list, else val unchanged."""
    if isinstance(val, list):
        return val[0] if len(val) == 1 else val
    return val


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: {path}: {e}")
        return {}


# ── Helper utilities ──────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    if not text: return ''
    return re.sub(r'<[^>]+>', '', str(text)).strip()[:300]


def _str(val, limit=200) -> str:
    """Safely convert any value to a clean string."""
    if val is None: return ''
    return str(val)[:limit]


def _first_standard(subcriteria: dict) -> dict:
    """Extract standard metadata from the first evidence that has it."""
    for sub_val in subcriteria.values():
        for ev in sub_val.get('evidence', []):
            std = ev.get('standard')
            if std and isinstance(std, dict):
                return std
    return {}


def _first_plugin(subcriteria: dict) -> dict:
    """Extract plugin metadata from the first evidence that has it."""
    for sub_val in subcriteria.values():
        for ev in sub_val.get('evidence', []):
            plugin = ev.get('plugin')
            if plugin and isinstance(plugin, dict):
                return plugin
    return {}


def _extract_qc_enriched(qc_name: str, qc_data: dict) -> dict:
    """
    Extract all enriched fields from one QC criterion.
    Returns complete dict ready to pass to QualityCheck constructor.
    """
    subcriteria      = qc_data.get('subcriteria', {})
    tools_failed     = []
    tools_passed     = []
    failure_messages = []
    fix_hints        = []
    sub_summary      = []
    top_req_level    = 'MUST'

    # Standard + plugin come from first available evidence
    std    = _first_standard(subcriteria)
    plugin = _first_plugin(subcriteria)

    # Collect ci_url, build_repo, tool_level, commands, stdout from all evidence
    ci_urls     = []
    build_repos = []
    tool_levels = []
    commands    = []
    stdouts     = []

    req_for_next = None   # required_for_next_level_badge (any sub True → True)

    for sub_key, sub_val in subcriteria.items():
        req_level  = sub_val.get('requirement_level', 'MUST')
        sub_hint   = _clean_html(sub_val.get('hint', ''))
        sub_desc   = sub_val.get('description', '')
        sub_valid  = sub_val.get('valid', None)
        sub_tool_failures = []

        rnlb = sub_val.get('required_for_next_level_badge')
        if rnlb is True:
            req_for_next = True
        elif rnlb is False and req_for_next is None:
            req_for_next = False

        for ev in sub_val.get('evidence', []):
            ev_valid  = ev.get('valid', False)
            ev_msg    = ev.get('message', '')
            tool      = ev.get('tool') or {}
            ci        = tool.get('ci') or {}

            tool_name    = tool.get('name', '')
            tool_version = tool.get('version', '')
            ci_status    = ci.get('status', '')

            # ── Always capture failure (even when tool=None) ──
            if not ev_valid and ev_msg:
                source = tool_name if tool_name else 'file_check'
                msg    = f"[{sub_key}][{source}] {ev_msg}"
                if msg not in failure_messages:
                    failure_messages.append(msg)

            if tool_name:
                label = (f"{tool_name} v{tool_version}"
                         if tool_version else tool_name)
                if ci_status == 'FAILED':
                    tools_failed.append(label)
                    sub_tool_failures.append(tool_name)
                elif ci_status == 'SUCCESS':
                    tools_passed.append(tool_name)

            # Collect CI metadata (deduplicated later)
            if ci.get('url'):
                ci_urls.append(ci['url'])
            if tool.get('build_repo'):
                build_repos.append(_str(tool['build_repo'], 200))
            if tool.get('level'):
                tool_levels.append(tool['level'])
            if ci.get('stdout_command'):
                raw_cmd = ci['stdout_command']
                cmd_str = (raw_cmd[0] if isinstance(raw_cmd, list) and raw_cmd
                           else _str(raw_cmd, 120))
                if cmd_str and cmd_str not in commands:
                    commands.append(cmd_str)
            if ci.get('stdout_text'):
                raw_out = ci['stdout_text']
                out_str = (_str(raw_out, 500)
                           if not isinstance(raw_out, str)
                           else raw_out[:500])
                if out_str and out_str not in stdouts:
                    stdouts.append(out_str)

            # Track subcriterion validity from evidence
            if sub_valid is None:
                sub_valid = ev_valid
            elif ev_valid:
                sub_valid = True

        if sub_valid is False and sub_hint:
            fix_hints.append({
                'subcriterion':      sub_key,
                'description':       sub_desc[:120],
                'requirement_level': req_level,
                'hint':              sub_hint,
                'tools_failing': (sub_tool_failures
                                  if sub_tool_failures else ['file_check']),
            })

        sub_summary.append({
            'id':                sub_key,
            'description':       sub_desc[:100],
            'valid':             bool(sub_valid),
            'requirement_level': req_level,
            'required_for_next_level_badge': rnlb,
        })

        if req_level == 'MUST':
            top_req_level = 'MUST'

    return {
        'tools_failed':        list(dict.fromkeys(tools_failed)),
        'tools_passed':        list(dict.fromkeys(tools_passed)),
        'failure_messages':    failure_messages,
        'fix_hints':           fix_hints,
        'subcriteria_summary': sub_summary,
        'requirement_level':   top_req_level,
        # Standard traceability
        'standard_title':   std.get('title', ''),
        'standard_version': std.get('version', ''),
        'standard_url':     std.get('url', ''),
        # Plugin
        'plugin_name':    plugin.get('name', ''),
        'plugin_version': plugin.get('version', ''),
        # Tool metadata
        'tool_level':  tool_levels[0] if tool_levels else '',
        'build_repo':  build_repos[0] if build_repos else '',
        # CI details
        'ci_url':            ci_urls[0]  if ci_urls    else '',
        'ci_stdout_command': commands[0] if commands   else '',
        'ci_stdout_text':    stdouts[0]  if stdouts    else '',
        # Badge gate
        'required_for_next_level_badge': req_for_next,
    }


def _extract_badge_path(badge_software: dict) -> dict:
    path = {}
    for level in ('bronze', 'silver', 'gold'):
        crit = badge_software.get('criteria', {}).get(level, {})
        path[level] = {
            'fulfilled': crit.get('fulfilled', []),
            'missing':   crit.get('missing',   []),
        }
    return path


def _qc_description(qc_name: str, qc_data: dict) -> str:
    """
    Derive a human-readable description for a QC criterion.

    The SQAaaS report never carries a top-level 'description' on the QC
    block — that field simply does not exist in any report version.
    The real descriptions live on each subcriterion. We collect them all
    and join them so the provenance node carries meaningful text instead
    of the placeholder "Description for QC.Acc".

    Single-subcriterion criteria (QC.Acc, QC.Met, QC.Sec, QC.Sty, QC.Uni)
    produce a single sentence. Multi-subcriterion criteria (QC.Doc, QC.Lic,
    QC.Ver) produce a semicolon-separated list of their sub-questions.
    """
    subcriteria = qc_data.get('subcriteria', {})
    descs = [
        sv.get('description', '').strip()
        for sv in subcriteria.values()
        if sv.get('description', '').strip()
    ]
    if descs:
        return '; '.join(descs)
    # Absolute last resort — still better than "Description for QC.Acc"
    return qc_name


# ── Main file processor ───────────────────────────────────────────────────

def process_file(file_path, prov_model, gindex, repo_dict, repo_name_override=None):
    data = load_json(file_path)
    if not data:
        return

    repo_list = data.get('repository', [])
    if not repo_list:
        return

    repo_data  = repo_list[0]
    repo_name  = repo_name_override or repo_data.get('name', 'Unknown')
    badge_sw   = data.get('badge', {}).get('software', {})
    report     = data.get('report', {})
    meta       = data.get('meta', {})

    # Commit date: read from the filename (set during fetch-sqa-reports).
    # Never call the GitHub API here — that would issue one request per file
    # and hit rate limits for large repositories.
    commit_date = _assessment_date(file_path, data)

    # ── Repository entity ─────────────────────────────────────────────────
    if repo_name in repo_dict:
        repository_id = repo_dict[repo_name]['id']
    else:
        repository_id = f"repository{gindex}"
        repo_dict[repo_name] = {'id': repository_id, 'name': repo_name}
        repo = Repository(
            id          = repository_id,
            name        = repo_data.get('name', ''),
            url         = repo_data.get('url', ''),
            avatar_url  = repo_data.get('avatar_url', ''),
            description = repo_data.get('description', ''),
            languages   = repo_data.get('languages', []),
        )
        prov_model.add_entity(repo)

    # ── Output entity (enriched) ──────────────────────────────────────────
    output_id  = f"output{gindex}"
    badge_info = badge_sw.get('data', {})
    badge_path = _extract_badge_path(badge_sw)

    output = Output(
        id                    = output_id,
        badge_won             = repo_data.get('badge_status', 'No Badge'),
        Issued_On             = badge_info.get('issuedOn',             ''),
        entityType            = badge_info.get('entityType',           ''),
        openBadgeId           = badge_info.get('openBadgeId',          ''),
        createdAt             = badge_info.get('createdAt',            ''),
        badgeclassOpenBadgeId = badge_info.get('badgeclassOpenBadgeId',''),
        image_URL             = badge_info.get('image',                ''),
        badge_path            = badge_path,
        verification_url      = badge_sw.get('verification_url', ''),
    )
    prov_model.add_entity(output)

    # ── Assessment entity (enriched) ──────────────────────────────────────
    assessment_id = f"assessment{gindex}"

    # A partial run is one where SQAaaS only evaluated a subset of criteria
    # and issued no badge assertion. This happens when a single check is
    # triggered manually or when the pipeline aborts early.
    # We flag it so consumers can distinguish partial from full assessments
    # while still keeping the event in provenance history.
    # NOTE: old SQAaaS versions (e.g. 2.9.3) only had 7 criteria but still
    # earned badges — those are NOT partial runs. We check badge_issued to
    # tell them apart.
    QC_FULL_COUNT = 8
    _badge_data   = badge_sw.get('data', {})
    _badge_issued = bool(_badge_data.get('createdAt') or _badge_data.get('issuedOn'))
    _badge_status = (repo_data.get('badge_status') or '').lower()
    is_partial_run = (
        len(report) < QC_FULL_COUNT
        and _badge_status in ('no_badge', '')
        and not _badge_issued
    )

    # _unwrap: commit_id arrives as ["sha"] in some report versions — store as scalar
    assessment = Assessment(
        id               = assessment_id,
        report_json_url  = meta.get('report_json_url', ''),
        commit_id        = _unwrap(repo_data.get('commit_id', '')),
        branch_name      = _unwrap(repo_data.get('tag', '')),
        commit_date      = commit_date,
        version          = meta.get('version', ''),
        report_permalink = meta.get('report_permalink', ''),
        is_main_repo     = repo_data.get('is_main_repo', None),
        is_partial_run   = is_partial_run,
    )
    prov_model.add_entity(assessment)

    # ── QualityCheck activities (fully enriched) ──────────────────────────
    for qc_name, qc_data in report.items():
        cov      = qc_data.get('coverage', {})
        enriched = _extract_qc_enriched(qc_name, qc_data)

        qc = QualityCheck(
            id                  = f"qc_{qc_name}_{gindex}",
            description         = _qc_description(qc_name, qc_data),
            is_output           = qc_data.get('valid', False),
            percentage          = f"{cov.get('percentage', 0)}%",
            total_subcriteria   = cov.get('total_subcriteria',   0),
            success_subcriteria = cov.get('success_subcriteria', 0),
            # aggregated
            tools_failed        = enriched['tools_failed'],
            tools_passed        = enriched['tools_passed'],
            failure_messages    = enriched['failure_messages'],
            fix_hints           = enriched['fix_hints'],
            subcriteria_summary = enriched['subcriteria_summary'],
            requirement_level   = enriched['requirement_level'],
            # standard traceability
            standard_title      = enriched['standard_title'],
            standard_version    = enriched['standard_version'],
            standard_url        = enriched['standard_url'],
            # plugin
            plugin_name         = enriched['plugin_name'],
            plugin_version      = enriched['plugin_version'],
            # tool
            tool_level          = enriched['tool_level'],
            build_repo          = enriched['build_repo'],
            # CI
            ci_url              = enriched['ci_url'],
            ci_stdout_command   = enriched['ci_stdout_command'],
            ci_stdout_text      = enriched['ci_stdout_text'],
            # badge gate
            required_for_next_level_badge = enriched['required_for_next_level_badge'],
        )
        prov_model.add_QualityCheck(qc)

        prov_model.add_relationship(
            ProvenanceRelationship(
                RelFrom=f"qc_{qc_name}_{gindex}",
                RelTo=assessment_id,
                relationship_type="wasGeneratedBy",
            ),
            "wasGeneratedBy"
        )

    # ── Relationships ─────────────────────────────────────────────────────
    for rf, rt in [(repository_id, assessment_id),
                   (assessment_id, output_id)]:
        prov_model.add_relationship(
            ProvenanceRelationship(RelFrom=rf, RelTo=rt,
                                   relationship_type="wasDerivedFrom"),
            "wasDerivedFrom"
        )
    prov_model.add_relationship(
        ProvenanceRelationship(RelFrom="SQAaaS", RelTo=repository_id,
                               relationship_type="wasAttributedTo"),
        "wasAttributedTo"
    )


# ── Process all files ─────────────────────────────────────────────────────

def process_all_files(folder_path, on_progress=None, repo_filter=None):
    prov_model = ProvenanceModel()
    prov_model.add_agent(
        Agent(id="SQAaaS", name="SQAaaS", agent_type="prov:SoftwareAgent")
    )

    _RUN_IDX_RE = re.compile(r'^report_(\d+)_')

    def _sort_key(fp):
        fname = os.path.basename(fp)
        # New fetcher format: YYYY-MM-DDTHH_MM_SSZ_NNNN_... → sorts correctly as string
        if _FNAME_DATE_RE.match(fname):
            return (fname, 0)
        # Old format: report_{run_index}_... → sort numerically by run index
        m = _RUN_IDX_RE.match(fname)
        if m:
            return ('', int(m.group(1)))
        return (fname, 0)

    all_files = sorted(
        [os.path.join(folder_path, f)
         for f in os.listdir(folder_path)
         if f.endswith('.json')],
        key=_sort_key
    )

    # Pre-pass: read every file once to collect repo name, commit_id.
    # Used for both canonical-repo detection and commit deduplication.
    from collections import Counter
    file_meta: list = []   # [(fp, repo_name, commit_id), ...]
    repo_counter: Counter = Counter()

    for fp in all_files:
        data = load_json(fp)
        repo_list = data.get('repository', [])
        if not repo_list:
            continue
        repo_name = repo_list[0].get('name', '')
        commit_id = _unwrap(repo_list[0].get('commit_id', ''))
        file_meta.append((fp, repo_name, commit_id))
        if repo_name:
            repo_counter[repo_name] += 1

    # Determine canonical repo: explicit override > most frequent name.
    if repo_filter:
        canonical = repo_filter
        if canonical not in repo_counter:
            print(f"Warning: --repo '{canonical}' not found in any report. "
                  f"Known repos: {list(repo_counter)}")
    else:
        canonical = repo_counter.most_common(1)[0][0] if repo_counter else None

    if canonical:
        forks = {name: cnt for name, cnt in repo_counter.items() if name != canonical}
        fork_total = sum(forks.values())
        print(f"Canonical repo : {canonical} ({repo_counter[canonical]} reports)")
        if forks:
            print(f"Forks merged   : {fork_total} reports from {list(forks)} "
                  f"→ renamed to canonical")

    # Deduplicate by commit_id across all repos (canonical + forks), keeping latest.
    # Fork assessments are kept but will be attributed to the canonical repo name.
    commit_to_file: dict = {}
    no_commit_files: list = []
    for fp, repo_name, commit_id in file_meta:
        if commit_id:
            commit_to_file[commit_id] = fp   # last write = latest chronologically
        else:
            no_commit_files.append(fp)

    input_files = (
        sorted(commit_to_file.values(), key=_sort_key) + no_commit_files
    )
    kept    = len(input_files)
    deduped = len(all_files) - kept
    if deduped > 0:
        print(f"Deduplication  : kept {kept} of {len(all_files)} "
              f"({deduped} older re-assessments of the same commit discarded)")

    total     = len(input_files)
    repo_dict = {}

    for gindex, fp in enumerate(input_files, start=1):
        pct = int(round(gindex / total * 100))
        print(f"\rProcessing {gindex}/{total} — {pct}%", end="", flush=True)
        if on_progress:
            on_progress(pct, gindex, total)
        process_file(fp, prov_model, gindex, repo_dict, repo_name_override=canonical)
    print()

    out_dir = "./Provenance_documents"
    os.makedirs(out_dir, exist_ok=True)

    names    = [d['name'] for d in repo_dict.values()]
    stub     = names[0].replace('/', '_') if names else 'provenance'
    out_path = os.path.join(out_dir, f"{stub}_prov_output.json")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(prov_model.to_json())

    print(f"\nSaved → {out_path}")
    print("New QualityCheck attributes:")
    print("  ex:tools_failed/passed, ex:failure_messages, ex:fix_hints")
    print("  ex:subcriteria_summary, ex:standard_title/version/url")
    print("  ex:plugin_name/version, ex:tool_level, ex:build_repo")
    print("  ex:ci_url, ex:ci_stdout_command, ex:ci_stdout_text")
    print("  ex:required_for_next_level_badge")
    print("New Output attributes:")
    print("  ex:badge_path, ex:*_missing, ex:*_fulfilled, ex:verification_url")
    return Path(out_path)


def main():
    parser = argparse.ArgumentParser(
        description='Process SQAaaS reports → enriched W3C PROV document')
    parser.add_argument('folder_path',
                        help='Folder containing SQAaaS report_*.json files')
    args = parser.parse_args()
    process_all_files(args.folder_path)


if __name__ == '__main__':
    main()