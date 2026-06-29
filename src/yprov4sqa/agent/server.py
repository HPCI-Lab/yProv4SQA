"""
yprov4sqa/agent/server.py
=========================
Flask web server — serves the chat UI and /api/chat endpoint.

Run via CLI:
    prov-chat prov_output.json --web --port 5000

Or directly:
    python -m yprov4sqa.agent.server --prov prov_output.json
"""

import os
import argparse
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file

# Load .env by walking up from this file — works regardless of cwd
def _load_dotenv_once():
    try:
        from dotenv import load_dotenv
        p = Path(__file__).resolve()
        for _ in range(6):
            p = p.parent
            env_file = p / '.env'
            if env_file.exists():
                load_dotenv(dotenv_path=env_file, override=False)
                break
    except ImportError:
        pass

_load_dotenv_once()

from .agent import ProvAgent
from . import loader

YPROV_STORE_URL = 'http://yprov.disi.unitn.it:8000'
EXPLORER_URL    = 'https://explorer.yprov.disi.unitn.it'


def _validate_prov_json(data: dict) -> tuple[int, str]:
    """
    Validate that *data* is a yProv4SQA / SQAaaS provenance document.

    Returns (assessment_count, repo_name) on success.
    Raises ValueError with a user-facing message on failure.
    """
    import re as _re

    if not isinstance(data, dict):
        raise ValueError('File is not a JSON object.')

    entities   = data.get('entity',   {})
    activities = data.get('activity', {})

    if not isinstance(entities, dict) or not isinstance(activities, dict):
        raise ValueError(
            'Missing "entity" or "activity" keys — '
            'this does not look like a yProv4SQA provenance document.'
        )

    assessment_keys = [k for k in entities if _re.fullmatch(r'ex:assessment\d+', k)]
    output_keys     = {k for k in entities if _re.fullmatch(r'ex:output\d+',     k)}
    valid_pairs     = [k for k in assessment_keys
                       if k.replace('assessment', 'output') in output_keys]

    if not valid_pairs:
        raise ValueError(
            f'No SQAaaS assessment records found (expected entities named '
            f'"ex:assessment1", "ex:output1", … but found none). '
            f'This file does not appear to be a yProv4SQA provenance document.'
        )

    repo_name = entities.get('ex:repository1', {}).get('ex:name', '')
    return len(valid_pairs), repo_name


def _get_prov_scan_dirs() -> list[str]:
    """Return directories to scan for saved provenance files."""
    dirs = [os.path.join(os.getcwd(), 'Provenance_documents')]
    if loader.PROV_PATH:
        adj = os.path.join(os.path.dirname(os.path.abspath(loader.PROV_PATH)),
                           'Provenance_documents')
        if adj not in dirs:
            dirs.append(adj)
    return dirs


def _scan_prov_dirs() -> list[dict]:
    """Scan known directories for saved provenance JSON files."""
    import json as _json
    from datetime import datetime as _dt

    results: list[dict] = []
    seen: set[str] = set()

    for d in _get_prov_scan_dirs():
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.lower().endswith('.json'):
                continue
            fpath = os.path.abspath(os.path.join(d, fname))
            if fpath in seen:
                continue
            seen.add(fpath)
            try:
                with open(fpath, 'r', encoding='utf-8') as fh:
                    data = _json.load(fh)
                count, repo_name = _validate_prov_json(data)
                stat = os.stat(fpath)
                results.append({
                    'filename':    fname,
                    'path':        fpath,
                    'repo':        repo_name or fname.replace('_prov_output.json', '').replace('_', '/'),
                    'assessments': count,
                    'size_kb':     round(stat.st_size / 1024, 1),
                    'modified':    _dt.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                })
            except Exception:
                continue  # skip files that fail validation

    return results


_agent: ProvAgent | None = None

# Resolve static dir relative to this file so it works on any machine
# Locate static dir: works both in development (src layout) and after pip install.
# Walk up from this file until we find the 'static' directory.
def _find_static_dir() -> Path:
    candidate = Path(__file__).parent
    for _ in range(5):
        s = candidate / 'static'
        if s.is_dir():
            return s
        candidate = candidate.parent
    # Fallback to the old hard-coded path
    return Path(__file__).parent.parent.parent.parent / 'static'

_STATIC_DIR = _find_static_dir()


def create_app(
    agent: ProvAgent | None = None,
    provider: str = 'ollama',
    model: str | None = None,
    api_key: str | None = None,
    ollama_url: str = 'http://localhost:11434',
) -> Flask:
    static_dir = _STATIC_DIR
    app = Flask(__name__, static_folder=str(static_dir))

    # Mutable agent reference so upload/generate routes can replace it.
    _ref    = [agent]
    _config = {'provider': provider, 'model': model, 'api_key': api_key, 'ollama_url': ollama_url}
    _jobs   = {}  # job_id -> {status, message, step}

    # ── Static pages ─────────────────────────────────────────────────────

    @app.route('/')
    def serve_landing():
        return send_from_directory(static_dir, 'landing.html')

    @app.route('/app')
    def serve_app():
        return send_from_directory(static_dir, 'index.html')

    @app.route('/<path:filename>')
    def serve_static(filename):
        return send_from_directory(static_dir, filename)

    # ── Landing API ───────────────────────────────────────────────────────

    @app.route('/api/app-status')
    def app_status():
        return jsonify({
            'loaded':      _ref[0] is not None,
            'repo':        loader.REPO if _ref[0] else {},
            'assessments': len(loader.ROWS) if _ref[0] else 0,
        })

    @app.route('/api/upload-prov', methods=['POST'])
    def upload_prov():
        import json as _json
        import tempfile

        if 'file' not in request.files:
            return jsonify({'error': 'no file field in request'}), 400
        f = request.files['file']
        if not (f.filename or '').lower().endswith('.json'):
            return jsonify({'error': 'only .json files are accepted'}), 400

        # Save to a persistent temp file
        tmp = tempfile.NamedTemporaryFile(suffix='_prov_upload.json', delete=False)
        f.save(tmp.name)
        tmp.close()

        # Parse JSON and validate SQAaaS provenance structure
        try:
            with open(tmp.name, 'r', encoding='utf-8') as fh:
                prov_data = _json.load(fh)
        except Exception as exc:
            return jsonify({'error': f'Invalid JSON file: {exc}'}), 400

        try:
            count, repo_name = _validate_prov_json(prov_data)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        # LLM config from multipart form fields
        prov    = request.form.get('provider',   _config['provider'])
        mdl     = request.form.get('model')      or _config['model']
        akey    = request.form.get('api_key')    or _config['api_key']
        ourl    = request.form.get('ollama_url', _config['ollama_url'])
        default = 'gemini-2.0-flash' if prov == 'google' else 'llama3.2'

        try:
            _ref[0] = ProvAgent(tmp.name, model_name=mdl or default,
                                base_url=ourl, provider=prov, api_key=akey)
            return jsonify({'status': 'ok', 'assessments': count, 'repo': repo_name})
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/saved-prov')
    def saved_prov():
        try:
            docs = _scan_prov_dirs()
            return jsonify({'docs': docs})
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/load-saved', methods=['POST'])
    def load_saved():
        import json as _json
        data     = request.get_json() or {}
        path     = data.get('path', '').strip()
        if not path:
            return jsonify({'error': 'path is required'}), 400

        # Security: path must be inside one of the allowed scan directories
        abs_path = os.path.abspath(path)
        allowed  = [os.path.abspath(d) for d in _get_prov_scan_dirs()]
        if not any(abs_path.startswith(d + os.sep) or abs_path == d for d in allowed):
            return jsonify({'error': 'path is outside allowed directories'}), 403
        if not os.path.isfile(abs_path):
            return jsonify({'error': 'file not found'}), 404

        try:
            with open(abs_path, 'r', encoding='utf-8') as fh:
                prov_data = _json.load(fh)
            count, repo_name = _validate_prov_json(prov_data)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception as exc:
            return jsonify({'error': f'Could not read file: {exc}'}), 400

        prov    = data.get('provider',   _config['provider'])
        mdl     = data.get('model')      or _config['model']
        akey    = data.get('api_key')    or _config['api_key']
        ourl    = data.get('ollama_url', _config['ollama_url'])
        default = 'gemini-2.0-flash' if prov == 'google' else 'llama3.2'

        try:
            _ref[0] = ProvAgent(abs_path, model_name=mdl or default,
                                base_url=ourl, provider=prov, api_key=akey)
            return jsonify({'status': 'ok', 'assessments': count, 'repo': repo_name})
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/generate-prov', methods=['POST'])
    def generate_prov():
        import uuid
        import threading

        data = request.get_json() or {}
        repo = data.get('repo', '').strip()
        if not repo:
            return jsonify({'error': 'repo name is required'}), 400

        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {'status': 'pending', 'message': 'Starting…', 'step': 'fetch'}

        gh_token = data.get('github_token') or os.getenv('GITHUB_TOKEN')
        prov     = data.get('provider',   _config['provider'])
        mdl      = data.get('model')      or _config['model']
        akey     = data.get('api_key')    or _config['api_key']
        ourl     = data.get('ollama_url', _config['ollama_url'])

        def _run():
            try:
                from yprov4sqa._fetcher    import fetch_assessment_reports
                from yprov4sqa._provenance import process_all_files

                # Accept both "itwinai" and "interTwin-eu/itwinai" — use only the name part.
                # The fetcher looks up eosc-synergy/{name}.assess.sqaaas on GitHub.
                repo_name = repo.split('/')[-1] if '/' in repo else repo

                # ── Step 1: fetch ────────────────────────────────────────────
                _jobs[job_id].update(
                    step='fetch', percent=0, count=0, total=0,
                    message=f'Connecting to GitHub for "{repo_name}"…',
                )

                def _on_fetch(pct, current, total):
                    _jobs[job_id].update(
                        percent=round(pct),
                        count=current,
                        total=total,
                        message=(
                            f'Downloading assessments from GitHub… '
                            f'{round(pct)}%  ({current} / {total})'
                        ),
                    )

                folder = fetch_assessment_reports(repo_name, token=gh_token,
                                                  on_progress=_on_fetch)
                if not folder:
                    raise RuntimeError(
                        f'No reports folder returned for "{repo_name}". '
                        f'Expected repo: eosc-synergy/{repo_name}.assess.sqaaas'
                    )

                # Verify at least one report was actually downloaded.
                # An empty folder means the project is not registered with SQAaaS.
                json_files = (
                    [f for f in os.listdir(str(folder)) if f.endswith('.json')]
                    if os.path.isdir(str(folder)) else []
                )
                if not json_files:
                    raise RuntimeError(
                        f'No SQAaaS assessment reports found for "{repo_name}". '
                        f'The project may not be registered with SQAaaS — '
                        f'could not find eosc-synergy/{repo_name}.assess.sqaaas on GitHub.'
                    )

                # ── Step 2: process ──────────────────────────────────────────
                _jobs[job_id].update(
                    step='process', percent=0, count=0, total=0,
                    message='Building provenance document…',
                )

                def _on_process(pct, current, total):
                    _jobs[job_id].update(
                        percent=pct,
                        count=current,
                        total=total,
                        message=(
                            f'Building provenance document… '
                            f'{pct}%  ({current} / {total} assessments)'
                        ),
                    )

                path = process_all_files(folder, on_progress=_on_process)
                if not path:
                    raise RuntimeError(
                        'process_all_files returned no output path — '
                        'the reports folder may be empty or contain no valid JSON files.'
                    )

                # ── Step 3: load agent ───────────────────────────────────────
                _jobs[job_id].update(
                    step='load', percent=100,
                    message='Loading conversational AI agent…',
                )
                default = 'gemini-2.0-flash' if prov == 'google' else 'llama3.2'
                _ref[0] = ProvAgent(str(path), model_name=mdl or default,
                                    base_url=ourl, provider=prov, api_key=akey)

                _jobs[job_id].update(status='done', percent=100,
                    message='All done — opening chat!')
            except Exception as exc:
                _jobs[job_id].update(status='error', message=str(exc))

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({'job_id': job_id})

    @app.route('/api/llm-check')
    def llm_check():
        import requests as _req
        provider   = request.args.get('provider', 'ollama')
        ollama_url = (request.args.get('ollama_url') or 'http://localhost:11434').rstrip('/')
        model      = (request.args.get('model') or '').strip()

        if provider == 'ollama':
            try:
                r = _req.get(f'{ollama_url}/api/tags', timeout=5)
                if r.status_code == 200:
                    models = [m['name'] for m in r.json().get('models', [])]
                    target = model or 'llama3.2'
                    found  = any(m == target or m.startswith(target + ':') for m in models)
                    if found:
                        return jsonify({'ok': True, 'ready': True,
                                        'message': f'✓ {target} ready',
                                        'models': models[:8]})
                    return jsonify({'ok': False, 'ready': False,
                                    'message': f'Ollama running — {target} not pulled',
                                    'models': models[:8]})
                return jsonify({'ok': False, 'message': f'Ollama returned HTTP {r.status_code}'})
            except _req.exceptions.ConnectionError:
                return jsonify({'ok': False, 'message': 'Ollama not reachable'})
            except Exception as exc:
                return jsonify({'ok': False, 'message': str(exc)[:80]})

        if provider == 'google':
            key = request.args.get('api_key', '') or os.getenv('GOOGLE_API_KEY', '')
            if key and len(key) > 10 and key.startswith('AIza'):
                return jsonify({'ok': True, 'message': '✓ Google API key set'})
            if key:
                return jsonify({'ok': False, 'message': 'API key format unrecognised'})
            return jsonify({'ok': False, 'message': 'No Google API key'})

        return jsonify({'ok': False, 'message': 'Unknown provider'})

    @app.route('/api/generate-status/<job_id>')
    def generate_status(job_id):
        job = _jobs.get(job_id)
        if not job:
            return jsonify({'error': 'job not found'}), 404
        return jsonify(job)

    # ── Chat API ──────────────────────────────────────────────────────────

    @app.route('/api/chat', methods=['POST'])
    def chat():
        if _ref[0] is None:
            return jsonify({'error': 'no provenance loaded — upload a document or generate one from the landing page'}), 503

        from langchain_core.messages import AIMessage, ToolMessage
        data     = request.get_json() or {}
        question = data.get('question', '').strip()
        if not question:
            return jsonify({'error': 'empty question'}), 400

        # Support both legacy single 'preload' and new 'preloads' array.
        # Each entry: {tool: str, output: str}
        # Up to 4 preloads are injected as synthetic tool results so the LLM
        # already has full context and avoids redundant / failing tool calls.
        preloads = list(data.get('preloads') or [])
        if isinstance(data.get('preload'), dict):
            preloads = [data['preload']] + preloads   # backwards compat

        for idx, p in enumerate(preloads[:4]):
            if not isinstance(p, dict):
                continue
            tool_name   = p.get('tool', 'compare_assessments')
            tool_output = str(p.get('output', ''))
            fake_id     = f'preload_{idx}'
            _ref[0].chat_history.append(
                AIMessage(
                    content    = '',
                    tool_calls = [{'name': tool_name, 'args': {}, 'id': fake_id}],
                )
            )
            _ref[0].chat_history.append(
                ToolMessage(
                    content      = tool_output[:8000],
                    tool_call_id = fake_id,
                    name         = tool_name,
                )
            )

        try:
            result = _ref[0].ask(question)
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/reset', methods=['POST'])
    def reset():
        if _ref[0] is not None:
            _ref[0].reset()
        return jsonify({'status': 'ok'})

    @app.route('/api/status')
    def status():
        rows = loader.ROWS
        branches = sorted(set(r.get('branch', 'unknown') for r in rows if r.get('branch')))

        # Find first/last dates, skip empty ones
        valid_rows = [r for r in rows if r.get('date', '').strip()]
        first_date = valid_rows[0]['date'][:10] if valid_rows else None
        last_date  = valid_rows[-1]['date'][:10] if valid_rows else None

        return jsonify({
            'loaded':      len(rows) > 0,
            'assessments': len(rows),
            'repo':        loader.REPO,
            'branches':    branches,
            'first_date':  first_date,
            'last_date':   last_date,
        })

    @app.route('/api/summary')
    def summary():
        """
        Return latest FULL assessment QC scores + badge directly from loader.ROWS.
        No LLM call — instant response used to populate the QC sidebar tab.
        Skips partial runs (single-criterion pipeline aborts) to avoid showing
        7 zeros and misleading the user. Prefers assessments with valid dates.

        Query params:
          ?branch=<branch_name>  - filter to specific branch (e.g. ?branch=main)
          (no param or branch=all) - latest across all branches
        """
        if not loader.ROWS:
            return jsonify({'error': 'no data loaded'}), 503
        from .loader import QC_COLS

        branch_filter = request.args.get('branch', '').strip()
        if branch_filter == 'all' or not branch_filter:
            branch_filter = None

        # Walk back to find the most recent non-partial assessment WITH a valid date
        latest = None
        for row in reversed(loader.ROWS):
            if branch_filter and row.get('branch', '') != branch_filter:
                continue
            if not row.get('is_partial_run', False) and row.get('date', '').strip():
                latest = row
                break

        # Fall back to any non-partial (edge case: all have invalid dates)
        if latest is None:
            for row in reversed(loader.ROWS):
                if branch_filter and row.get('branch', '') != branch_filter:
                    continue
                if not row.get('is_partial_run', False):
                    latest = row
                    break

        # Fall back to absolute latest if all are partial (extreme edge case)
        if latest is None:
            if branch_filter:
                for row in reversed(loader.ROWS):
                    if row.get('branch', '') == branch_filter:
                        latest = row
                        break
            else:
                latest = loader.ROWS[-1]

        if latest is None:
            return jsonify({'error': f'no assessments found for branch: {branch_filter}'}), 404

        return jsonify({
            'assessment':      latest['i'],
            'date':            latest.get('date', '')[:10],
            'badge':           latest.get('badge', ''),
            'commit':          latest.get('commit', ''),
            'branch':          latest.get('branch', ''),
            'is_partial_run':  latest.get('is_partial_run', False),
            'qc_scores':       {c: latest.get(c, 0.0) for c in QC_COLS},
        })

    @app.route('/api/qc-trend/<criterion>')
    def qc_trend(criterion):
        """
        Return historical QC scores for a criterion (last 20 assessments).
        Used to render mini sparklines in the QC tab.
        """
        if not loader.ROWS:
            return jsonify({'error': 'no data loaded'}), 503

        criterion = criterion.upper()
        if not criterion.startswith('QC.'):
            criterion = 'QC.' + criterion

        # Get last 20 assessments with valid dates
        valid_rows = [r for r in loader.ROWS if r.get('date', '').strip()]
        recent = valid_rows[-20:]

        if not recent:
            return jsonify({'error': 'no data with valid dates'}), 404

        scores = [r.get(criterion, 0) for r in recent]
        trend = 'stable'
        if len(scores) > 1:
            delta = scores[-1] - scores[0]
            if delta > 5:
                trend = 'improving'
            elif delta < -5:
                trend = 'declining'

        return jsonify({
            'criterion': criterion,
            'scores': scores,
            'current': scores[-1] if scores else 0,
            'min': min(scores) if scores else 0,
            'max': max(scores) if scores else 0,
            'trend': trend,
        })


    @app.route('/api/history')
    def history():
        """
        Return historical assessments as a time series for charting.
        Query params:
          ?start=YYYY-MM-DD  - inclusive start date
          ?end=YYYY-MM-DD    - inclusive end date
          ?branch=<name>     - optional branch filter
        Returns list of assessments with fields: i, date, commit, branch, badge, and QC cols.
        """
        if not loader.ROWS:
            return jsonify({'error': 'no data loaded'}), 503

        start = request.args.get('start', '').strip()
        end = request.args.get('end', '').strip()
        branch = request.args.get('branch', '').strip() or None

        from datetime import datetime as _dt
        def _parse(d):
            try:
                return _dt.fromisoformat(d[:10])
            except Exception:
                return None

        s_dt = _parse(start) if start else None
        e_dt = _parse(end) if end else None

        rows = [r for r in loader.ROWS if r.get('date')]
        if branch:
            rows = [r for r in rows if (r.get('branch') or '') == branch]

        # Filter by date range if provided
        out = []
        for r in rows:
            rd = _parse(r.get('date',''))
            if not rd:
                continue
            if s_dt and rd < s_dt:
                continue
            if e_dt and rd > e_dt:
                continue
            item = {
                'i': r.get('i'),
                'date': r.get('date')[:10],
                'commit': r.get('commit',''),
                'branch': r.get('branch',''),
                'badge': r.get('badge',''),
            }
            # include QC cols if available
            try:
                from .loader import QC_COLS
                for c in QC_COLS:
                    item[c] = r.get(c, 0)
            except Exception:
                pass
            out.append(item)

        # sort by date
        out.sort(key=lambda x: x.get('date') or '')
        return jsonify({'total': len(out), 'assessments': out})

    @app.route('/api/comparison')
    def comparison():
        """
        Compare two assessments by number with detailed provenance.
        Query params:
          ?a1=<num>  - first assessment number
          ?a2=<num>  - second assessment number
        """
        if not loader.ROWS:
            return jsonify({'error': 'no data loaded'}), 503

        try:
            a1_num = int(request.args.get('a1', ''))
            a2_num = int(request.args.get('a2', ''))
        except:
            return jsonify({'error': 'invalid assessment numbers'}), 400

        a1 = next((r for r in loader.ROWS if r['i'] == a1_num), None)
        a2 = next((r for r in loader.ROWS if r['i'] == a2_num), None)

        if not a1 or not a2:
            return jsonify({'error': f'assessment not found (valid range: 1-{len(loader.ROWS)})'}), 404

        qc_changes = {}
        improved = []
        degraded = []

        for col in loader.QC_COLS:
            v1 = a1.get(col, 0)
            v2 = a2.get(col, 0)

            # Get subcriteria data for both assessments
            sub_key = f'{col}_subcriteria'
            sub_a1 = a1.get(sub_key, [])
            sub_a2 = a2.get(sub_key, [])

            qc_changes[col] = {
                'from': v1,
                'to': v2,
                'subcriteria_a1': sub_a1,
                'subcriteria_a2': sub_a2,
            }

            if v2 > v1:
                improved.append(col)
            elif v2 < v1:
                degraded.append(col)

        # Try to get commit provenance comparison (optional)
        commit_diff = {
            'added': 0,
            'modified': 0,
            'deleted': 0,
            'total_additions': 0,
            'total_deletions': 0,
            'files': []
        }

        authors = {
            'commit_1': None,
            'commit_2': None,
        }

        prov_file      = {'filename': None, 'exists': False}
        github_diff_url = None
        prov_stats     = {'entities': 0, 'activities': 0, 'agents': 0}
        prov_note      = None

        try:
            from yprov4sqa._compare import CommitProvenance
            import os

            repo_name = loader.REPO.get('name', '')
            if not os.getenv('GITHUB_TOKEN'):
                prov_note = 'GITHUB_TOKEN not set — commit provenance skipped'
            elif repo_name and '/' in repo_name:
                owner, name = repo_name.split('/', 1)
                commit_1 = a1.get('commit', '')
                commit_2 = a2.get('commit', '')

                if commit_1 and commit_2 and len(commit_1) >= 8 and len(commit_2) >= 8:
                    try:
                        print(f"[comparison] Generating provenance for {owner}/{name} {commit_1[:8]}...{commit_1[-4:]} -> {commit_2[:8]}...{commit_2[-4:]}")

                        c1 = commit_1
                        c2 = commit_2

                        cp = CommitProvenance(
                            owner, name, c1, c2,
                            {'badge': a1.get('badge', ''), 'date': a1.get('date', '')},
                            {'badge': a2.get('badge', ''), 'date': a2.get('date', '')}
                        )
                        prov = cp.generate_provenance()

                        if not prov:
                            print("[comparison] generate_provenance returned None")
                            raise Exception("Failed to generate provenance")

                        print(f"[comparison] Provenance generated with {len(prov.get('agent', {}))} agents and {len(prov.get('activity', {}))} activities")

                        # Extract agent (author) information
                        agents = prov.get('agent', {})
                        for agent_id, agent_data in agents.items():
                            if 'commit_1' in agent_id or '_1' in agent_id:
                                authors['commit_1'] = {
                                    'username': agent_data.get('ex:username', ''),
                                    'email': agent_data.get('ex:email', ''),
                                    'avatar_url': agent_data.get('ex:avatar_url', ''),
                                }
                                print(f"[comparison] Author 1: {authors['commit_1']['username']}")
                            elif 'commit_2' in agent_id or '_2' in agent_id:
                                authors['commit_2'] = {
                                    'username': agent_data.get('ex:username', ''),
                                    'email': agent_data.get('ex:email', ''),
                                    'avatar_url': agent_data.get('ex:avatar_url', ''),
                                }
                                print(f"[comparison] Author 2: {authors['commit_2']['username']}")

                        # Extract file stats from activities
                        for act_key, act_data in prov.get('activity', {}).items():
                            if 'ex:filename' in act_data:
                                status = act_data.get('ex:status', 'modified')
                                additions = int(act_data.get('ex:lines_added', 0) or 0)
                                deletions = int(act_data.get('ex:lines_removed', 0) or 0)

                                if status == 'added':
                                    commit_diff['added'] += 1
                                elif status == 'deleted':
                                    commit_diff['deleted'] += 1
                                else:
                                    commit_diff['modified'] += 1

                                commit_diff['total_additions'] += additions
                                commit_diff['total_deletions'] += deletions
                                commit_diff['files'].append({
                                    'name': str(act_data.get('ex:filename', '')),
                                    'status': str(status),
                                    'additions': additions,
                                    'deletions': deletions,
                                    'url': str(act_data.get('ex:file_url', ''))
                                })

                        print(f"[comparison] File changes: {commit_diff['added']} added, {commit_diff['modified']} modified, {commit_diff['deleted']} deleted")

                        # Provenance file info
                        reduced_1 = f"{c1[:4]}...{c1[-4:]}"
                        reduced_2 = f"{c2[:4]}...{c2[-4:]}"
                        prov_filename = f"{name}_commit_provenance_{reduced_1}_to_{reduced_2}.json"
                        prov_filepath = os.path.join('./Compare_commit_provenance', prov_filename)
                        prov_file = {
                            'filename': prov_filename,
                            'exists': os.path.exists(prov_filepath),
                        }

                        # GitHub diff URL from wasAttributedTo
                        for wat_data in prov.get('wasAttributedTo', {}).values():
                            url = wat_data.get('ex:github_diff_url', '')
                            if url:
                                github_diff_url = url
                                break

                        # PROV graph stats
                        prov_stats = {
                            'entities':   len(prov.get('entity', {})),
                            'activities': len(prov.get('activity', {})),
                            'agents':     len(prov.get('agent', {})),
                        }

                    except Exception as e:
                        print(f"[comparison] Error generating provenance: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
        except Exception as e:
            print(f"[comparison] Outer exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        return jsonify({
            'a1': {
                'number': a1['i'],
                'date': a1.get('date', '')[:10],
                'badge': a1.get('badge', 'unknown'),
                'commit': a1.get('commit', '')[:12],
                'branch': a1.get('branch', ''),
                'sqaaas_version':   a1.get('sqaaas_version', ''),
                'report_permalink': a1.get('report_permalink', ''),
                'open_badge_url':   a1.get('open_badge_url', ''),
            },
            'a2': {
                'number': a2['i'],
                'date': a2.get('date', '')[:10],
                'badge': a2.get('badge', 'unknown'),
                'commit': a2.get('commit', '')[:12],
                'branch': a2.get('branch', ''),
                'sqaaas_version':   a2.get('sqaaas_version', ''),
                'report_permalink': a2.get('report_permalink', ''),
                'open_badge_url':   a2.get('open_badge_url', ''),
            },
            'qc_changes':      qc_changes,
            'improved':        improved,
            'degraded':        degraded,
            'commit_diff':     commit_diff,
            'authors':         authors,
            'prov_file':       prov_file,
            'github_diff_url': github_diff_url,
            'prov_stats':      prov_stats,
            'prov_note':       prov_note,
            'repo_url':        loader.REPO.get('url', ''),
        })

    @app.route('/api/prov-json')
    def prov_json():
        """Serve the main provenance JSON for the yProv Explorer."""
        prov_path = loader.PROV_PATH
        if not prov_path or not os.path.exists(prov_path):
            return jsonify({'error': 'provenance file not loaded'}), 404
        response = send_file(prov_path, mimetype='application/json')
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    @app.route('/api/comp-json')
    def comp_json():
        """Serve a comparison provenance JSON for the yProv Explorer."""
        import os as _os
        try:
            a1_num = int(request.args.get('a1', ''))
            a2_num = int(request.args.get('a2', ''))
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid parameters'}), 400

        row_a1 = next((r for r in loader.ROWS if r['i'] == a1_num), None)
        row_a2 = next((r for r in loader.ROWS if r['i'] == a2_num), None)
        if not row_a1 or not row_a2:
            return jsonify({'error': 'assessment not found'}), 404

        repo_name = loader.REPO.get('name', '')
        _, name = repo_name.split('/', 1) if '/' in repo_name else ('', repo_name)
        c1, c2 = row_a1.get('commit', ''), row_a2.get('commit', '')
        r1 = f"{c1[:4]}...{c1[-4:]}"
        r2 = f"{c2[:4]}...{c2[-4:]}"
        filename  = f"{name}_commit_provenance_{r1}_to_{r2}.json"

        search_dirs = []
        if loader.PROV_PATH:
            search_dirs.append(_os.path.join(_os.path.dirname(loader.PROV_PATH),
                                             'Compare_commit_provenance'))
        search_dirs.append(_os.path.join(_os.getcwd(), 'Compare_commit_provenance'))

        for d in search_dirs:
            candidate = _os.path.join(d, filename)
            if _os.path.exists(candidate):
                response = send_file(candidate, mimetype='application/json')
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response

        return jsonify({'error': 'comparison file not found — run the comparison first'}), 404

    @app.route('/api/comparison/file')
    def comparison_file():
        """Download the generated comparison provenance JSON file."""
        import os as _os
        try:
            a1_num = int(request.args.get('a1', ''))
            a2_num = int(request.args.get('a2', ''))
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid parameters'}), 400

        row_a1 = next((r for r in loader.ROWS if r['i'] == a1_num), None)
        row_a2 = next((r for r in loader.ROWS if r['i'] == a2_num), None)
        if not row_a1 or not row_a2:
            return jsonify({'error': 'assessment not found'}), 404

        repo_name = loader.REPO.get('name', '')
        if '/' not in repo_name:
            return jsonify({'error': 'cannot determine repo name'}), 400

        _, name = repo_name.split('/', 1)
        c1 = row_a1.get('commit', '')
        c2 = row_a2.get('commit', '')

        reduced_1 = f"{c1[:4]}...{c1[-4:]}"
        reduced_2 = f"{c2[:4]}...{c2[-4:]}"
        prov_filename = f"{name}_commit_provenance_{reduced_1}_to_{reduced_2}.json"
        prov_filepath = _os.path.abspath(
            _os.path.join('./Compare_commit_provenance', prov_filename)
        )

        if not _os.path.exists(prov_filepath):
            return jsonify({'error': 'provenance file not found — run the comparison first'}), 404

        return send_file(prov_filepath, as_attachment=True, download_name=prov_filename,
                         mimetype='application/json')

    # ── yProvStore integration ────────────────────────────────────────────

    @app.route('/api/yprov-signup', methods=['POST'])
    def yprov_signup():
        import requests as _req
        data = request.get_json() or {}
        try:
            r = _req.post(
                f'{YPROV_STORE_URL}/auth/signup',
                json={
                    'username': data.get('username', ''),
                    'email':    data.get('email', ''),
                    'password': data.get('password', ''),
                },
                timeout=15,
            )
            print(f'[yprov-signup] status={r.status_code} body={r.text[:300]}')
            return jsonify(r.json()), r.status_code
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/yprov-login', methods=['POST'])
    def yprov_login():
        import requests as _req
        data = request.get_json() or {}
        username = data.get('username', '')
        password = data.get('password', '')
        try:
            r = _req.post(
                f'{YPROV_STORE_URL}/auth/login',
                json={'email': username, 'password': password},
                timeout=15,
            )
            print(f'[yprov-login] status={r.status_code} body={r.text[:300]}')
            return jsonify(r.json()), r.status_code
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/yprov-docs')
    def yprov_docs():
        import requests as _req
        import base64  as _b64
        import json    as _json2
        from urllib.parse import quote as _quote

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'missing Authorization header'}), 401
        token = auth_header[7:]

        # Prefer email sent by client (already decoded from JWT client-side)
        user_email = (request.args.get('email') or '').strip()

        # Fallback: decode JWT payload locally
        if not user_email:
            try:
                parts   = token.split('.')
                padding = '=' * (4 - len(parts[1]) % 4)
                payload = _json2.loads(_b64.b64decode(parts[1] + padding))
                user_email = payload.get('email') or payload.get('sub', '')
            except Exception:
                pass

        print(f'[yprov-docs] user_email={user_email!r}')

        try:
            # Fetch one page only — the list is public and contains ALL users' docs.
            # Scanning all pages is slow (hundreds of test-user docs). We rely on the
            # client also caching published PIDs in localStorage for instant listing.
            dr = _req.get(
                f'{YPROV_STORE_URL}/documents',
                params={'page': 0, 'page_size': 100},
                headers={'Authorization': f'Bearer {token}'},
                timeout=10,
            )
            print(f'[yprov-docs] page=0 status={dr.status_code}')
            docs: list = []
            if dr.status_code == 200:
                body  = dr.json()
                docs  = body if isinstance(body, list) else body.get('items', body.get('documents', []))

            own = [d for d in docs if d.get('owner_email', '') == user_email] if user_email else docs
            print(f'[yprov-docs] total={len(docs)} own={len(own)}')

            enriched = []
            for d in own:
                pid     = d.get('pid') or d.get('id', '')
                storage = d.get('storage_url') or f'{YPROV_STORE_URL}/documents/{pid}'
                enriched.append({
                    'pid':          pid,
                    'storage_url':  storage,
                    'explorer_url': f'{EXPLORER_URL}/?file={_quote(storage + "?stream=false", safe="")}',
                    'title':        d.get('title') or pid,
                    'description':  d.get('description', ''),
                    'created_at':   d.get('created_at', ''),
                })
            return jsonify({'docs': enriched, 'email': user_email})
        except Exception as exc:
            print(f'[yprov-docs] exception: {exc}')
            return jsonify({'error': str(exc)}), 500

    @app.route('/api/yprov-publish', methods=['POST'])
    def yprov_publish():
        import requests as _req
        import json     as _json
        import os       as _os

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'missing Authorization header'}), 401
        token = auth_header[7:]

        data     = request.get_json() or {}
        doc_type = data.get('type', 'main')

        if doc_type == 'comp':
            try:
                a1_num = int(data.get('a1', 0))
                a2_num = int(data.get('a2', 0))
            except (TypeError, ValueError):
                return jsonify({'error': 'invalid assessment numbers'}), 400

            row_a1 = next((r for r in loader.ROWS if r['i'] == a1_num), None)
            row_a2 = next((r for r in loader.ROWS if r['i'] == a2_num), None)
            if not row_a1 or not row_a2:
                return jsonify({'error': 'assessment not found'}), 404

            repo_full = loader.REPO.get('name', '')
            _, rname  = repo_full.split('/', 1) if '/' in repo_full else ('', repo_full)
            c1, c2    = row_a1.get('commit', ''), row_a2.get('commit', '')
            r1, r2    = f"{c1[:4]}...{c1[-4:]}", f"{c2[:4]}...{c2[-4:]}"
            fname     = f"{rname}_commit_provenance_{r1}_to_{r2}.json"

            search_dirs = []
            if loader.PROV_PATH:
                search_dirs.append(_os.path.join(
                    _os.path.dirname(loader.PROV_PATH), 'Compare_commit_provenance'))
            search_dirs.append(_os.path.join(_os.getcwd(), 'Compare_commit_provenance'))

            prov_data = None
            for sdir in search_dirs:
                candidate = _os.path.join(sdir, fname)
                if _os.path.exists(candidate):
                    with open(candidate, 'r', encoding='utf-8') as fh:
                        prov_data = _json.load(fh)
                    break
            if prov_data is None:
                return jsonify({'error': 'comparison file not found — run comparison first'}), 404
            title = f"Commit diff: {r1} → {r2} ({rname})"

        else:
            prov_path = loader.PROV_PATH
            if not prov_path or not _os.path.exists(prov_path):
                return jsonify({'error': 'no provenance loaded'}), 404
            with open(prov_path, 'r', encoding='utf-8') as fh:
                prov_data = _json.load(fh)
            title = f"yProv4SQA: {loader.REPO.get('name', '')}"

        try:
            import io as _io
            from urllib.parse import quote as _quote
            doc_bytes = _json.dumps(prov_data).encode('utf-8')
            r = _req.post(
                f'{YPROV_STORE_URL}/documents',
                files={'document_file': ('document.json', _io.BytesIO(doc_bytes), 'application/json')},
                headers={'Authorization': f'Bearer {token}'},
                timeout=30,
            )
            print(f'[yprov-publish] status={r.status_code} body={r.text[:300]}')
            if r.status_code not in (200, 201):
                return jsonify({
                    'error': f'yProvStore error {r.status_code}: {r.text[:200]}'
                }), r.status_code
            result  = r.json()
            pid     = result.get('pid') or result.get('id', '')
            storage = result.get('storage_url') or f'{YPROV_STORE_URL}/documents/{pid}'
            return jsonify({
                'pid':          pid,
                'storage_url':  storage,
                'explorer_url': f'{EXPLORER_URL}/?file={_quote(storage + "?stream=false", safe="")}',
                'title':        title,
            })
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    return app


def main():
    parser = argparse.ArgumentParser(
        description='yProv4SQA — Web Agent Server')
    parser.add_argument('--prov',   default=None,
                        help='Path to prov_output.json (omit to start with the landing page)')
    parser.add_argument('--provider', default='ollama', choices=['ollama', 'google'],
                        help='LLM provider: ollama or google')
    parser.add_argument('--model',  default=None,
                        help='Model name (ollama: llama3.2, qwen2.5; google: gemini-2.0-flash)')
    parser.add_argument('--ollama', default='http://localhost:11434',
                        help='Ollama base URL (only if --provider ollama)')
    parser.add_argument('--google-api-key', default=os.getenv('GOOGLE_API_KEY'),
                        help='Google API key (or set GOOGLE_API_KEY env var)')
    parser.add_argument('--host',   default='127.0.0.1')
    parser.add_argument('--port',   default=5000, type=int)
    args = parser.parse_args()

    default_model = 'gemini-2.0-flash' if args.provider == 'google' else 'llama3.2'
    agent = None
    if args.prov:
        agent = ProvAgent(
            prov_path  = args.prov,
            model_name = args.model or default_model,
            base_url   = args.ollama,
            provider   = args.provider,
            api_key    = args.google_api_key,
        )

    app = create_app(agent, provider=args.provider, model=args.model,
                     api_key=args.google_api_key, ollama_url=args.ollama)
    if agent:
        print(f"\n  Web UI → http://{args.host}:{args.port}/app\n")
    else:
        print(f"\n  Web UI → http://{args.host}:{args.port}  (landing page)\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()