"""
yprov4sqa/agent/agent.py
========================
Lightweight tool-calling agent using ChatOllama.bind_tools().

Replaces the heavy create_agent()/CompiledStateGraph approach (which
compiled a full LangGraph state machine at startup and froze VS Code).
This version builds nothing at startup — the LLM connection is made
only when the user asks the first question.
"""

import os
import re
import json
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage,
)



from .tools import ALL_TOOLS
from .loader import load_provenance


def _extract_text_tool_calls(content: str, known_tools: set | None = None,
                             hint_tool: str | None = None) -> list[dict]:
    """
    Fallback parser: extract tool calls from model text output.
    Handles three formats that smaller/Ollama models produce:

    1. JSON object:
         {"name": "compare_assessments", "parameters": {"n1": 50, "n2": 100}}

    2. LangChain object repr (seen in some Ollama builds):
         {object <nil> {compare_assessments} [50,100] {"n1":{"type":"integer"}}}

    3. Python-style function call:
         compare_assessments(50, 100)   or   compare_assessments(n1=50, n2=100)
    """
    if not content:
        return []

    text = re.sub(r'```(?:json)?\s*', '', content)
    text = re.sub(r'```', '', text)

    calls: list[dict] = []

    # ── Format 1: JSON object with "name" key ─────────────────────────────
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                fragment = text[start:i + 1]
                try:
                    obj = json.loads(fragment)
                    if isinstance(obj, dict) and 'name' in obj:
                        name = obj['name']
                        args = obj.get('parameters',
                               obj.get('args',
                               obj.get('input', {})))
                        if not isinstance(args, dict):
                            args = {}
                        calls.append({'name': name, 'args': args,
                                      'id': f'txt_{len(calls)}'})
                except (json.JSONDecodeError, ValueError):
                    pass
                start = -1

    if calls:
        return calls

    # ── Format 2: {object <nil> {tool_name} [pos_args] {schema}} ──────────
    # e.g. {object <nil> {compare_assessments} [50,100] {"n1":{"type":"integer"}}}
    obj_pat = re.compile(
        r'\{object\s+<\w+>\s+\{(\w+)\}'   # {object <nil> {tool_name}
        r'\s+(\[[^\]]*\])'                 # [positional_args_json]
        r'\s+(\{[^}]+\})\}',               # {schema_json}
        re.DOTALL,
    )
    for m in obj_pat.finditer(text):
        tool_name = m.group(1)
        try:
            pos_args = json.loads(m.group(2))   # e.g. [50, 100] or ["QC.Uni", 20]
        except (json.JSONDecodeError, ValueError):
            continue
        try:
            schema = json.loads(m.group(3))     # e.g. {"num1_num2": {"type":"string"}}
        except (json.JSONDecodeError, ValueError):
            schema = {}

        param_names = list(schema.keys())
        args: dict = {}
        if len(param_names) == 1:
            # Single-param tool — join positional args with comma
            args[param_names[0]] = ','.join(str(a) for a in pos_args)
        else:
            for idx, pname in enumerate(param_names):
                if idx < len(pos_args):
                    args[pname] = str(pos_args[idx])

        calls.append({'name': tool_name, 'args': args,
                      'id': f'obj_{len(calls)}'})

    if calls:
        return calls

    # ── Format 3: function-call style  tool_name("arg1", arg2) ───────────
    # Matches any known tool name immediately followed by (...)
    if known_tools:
        fn_pat = re.compile(
            r'\b(' + '|'.join(re.escape(t) for t in known_tools) + r')\s*'
            r'\(([^)]*)\)',
        )
        for m in fn_pat.finditer(text):
            tool_name = m.group(1)
            raw_inner = m.group(2).strip()
            # Parse comma-separated quoted or unquoted tokens
            tokens = [t.strip().strip('"\'') for t in raw_inner.split(',') if t.strip()]
            # All single-string-arg tools: join with comma
            args = {}
            if tokens:
                # Determine the first param name from the schema if possible
                args['__positional__'] = ','.join(tokens)
            calls.append({'name': tool_name, 'args': args,
                          'id': f'fn_{len(calls)}'})

    # ── Format 4: raw args dict with no "name" key ────────────────────────
    # Some models output just {"window": 10} when they mean to call the
    # hinted tool.  If we have a hint and the content is a bare JSON dict,
    # use the hint tool with that dict as args.
    if not calls and hint_tool:
        depth, start = 0, -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    fragment = text[start:i + 1]
                    try:
                        obj = json.loads(fragment)
                        if isinstance(obj, dict) and 'name' not in obj:
                            calls.append({'name': hint_tool, 'args': obj,
                                          'id': f'raw_{len(calls)}'})
                    except (json.JSONDecodeError, ValueError):
                        pass
                    start = -1
                    break  # only need the first dict

    return calls

SYSTEM_PROMPT = """You are an expert Software Quality Assurance (SQA) analyst.
You have access to tools that query a real W3C PROV-compliant provenance
document for a GitHub repository assessed by the SQAaaS platform.

AVAILABLE TOOLS — you may ONLY call these 16, never invent tool names:
  get_summary, get_assessment, get_regressions, get_badge_history,
  get_qc_trend, compare_assessments, find_best_period,
  get_tool_failures, get_fix_hints, get_badge_path,
  get_branch_analysis, get_subcriteria_detail, get_ci_provenance,
  get_quality_velocity, get_partial_runs, get_badge_journey

RULES — follow these strictly:
1. Always call at least one tool before answering. Never guess data values.
2. Call multiple tools in sequence when one result raises a follow-up question.
3. Be precise: use exact assessment numbers, percentages, dates from tool results.
4. Explain QC drops using delta values returned by tools.
5. Give actionable recommendations based on what the tools return.
6. For ANY general, overview, or summary question about the repository, ALWAYS
   call get_summary first — never invent filters or call tools unnecessarily.
   Use get_summary to get an overall picture; use get_qc_trend for per-criterion trends.
7. When describing the CURRENT state of the project use latest_assessment.qc_scores
   from get_summary — NOT qc_all_time_averages (which is skewed by old history).
8. For recent trends call get_summary and read qc_recent_10_averages.
   For long-term history call get_summary and read qc_all_time_averages.
   Both fields are returned by get_summary — do NOT invent a separate tool.
9. When comparing two assessments, call compare_assessments for QC score changes.
   Use get_regressions to explain badge drops and get_qc_trend for criterion history.

PROVENANCE MODEL CONTEXT (W3C PROV standard):
- Entity:   Repository, Assessment (one per commit), Output (badge result)
- Activity: QualityCheck — 8 per assessment (QC.Acc, QC.Doc, QC.Lic, QC.Sec,
                                               QC.Sty, QC.Ver, QC.Met, QC.Uni)
- Agent:    SQAaaS (automated assessment platform)
- Relations: wasGeneratedBy, wasDerivedFrom, wasAttributedTo

QUALITY CRITERION GLOSSARY (SQAaaS official names — indigo-dc/sqa-baseline v4.1):
- QC.Acc = Code Accessibility   : source code MUST be open, public, and in a VCS.
                                   NOT accessibility (a11y/WCAG). NOT accuracy.
- QC.Doc = Documentation        : docs treated as code; README, CONTRIBUTING etc. required.
- QC.Lic = Licensing            : OSI-compliant open-source license required (MIT, Apache…).
- QC.Sec = Security             : SAST tools (bandit) applied; no known vulnerabilities.
- QC.Sty = Code Style           : community style standards followed (flake8, rubocop…).
- QC.Ver = Semantic Versioning  : release tags MUST follow SemVer (e.g. v1.2.0).
- QC.Met = Code Metadata        : citation file required (CITATION.cff or codemeta.json).
- QC.Uni = Unit Testing         : unit tests MUST exist, pass, and reach 70% coverage.

BADGE LEVELS (SQAaaS stable criteria):
- Bronze: QC.Acc, QC.Doc, QC.Lic
- Silver: + QC.Ver, QC.Met
- Gold:   + QC.Sec, QC.Sty, QC.Uni

QC SCORE MEANING — never misinterpret these:
- 100%  = criterion FULLY PASSED (all subcriteria satisfied)
- 0%    = criterion COMPLETELY FAILED (no subcriteria passed) — this is BAD
- 50%   = criterion PARTIALLY passed
- assessment_id is a sequential history index (e.g. 110 = the 110th run),
  it is NOT a score and must never be presented as one.

"""

# Lookup map: tool name → callable (built once at module load, lightweight)
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}

MAX_ITERATIONS  = 8     # max tool-call rounds per question
HISTORY_WINDOW  = 8     # keep last 4 turns (human+AI pairs) to limit token count
TOOL_OUT_LIMIT  = 1500  # max chars of tool output sent to LLM per call


class ProvAgent:
    """
    Stateful conversational agent with multi-turn memory.

    Usage:
        agent = ProvAgent('prov_output.json')
        result = agent.ask("What caused the latest regression?")
        print(result['answer'])
        print(result['tool_calls'])   # list of {tool, input, output}
    """

    def __init__(
        self,
        prov_path:  str,
        model_name: str  = 'llama3.2',
        base_url:   str  = 'http://localhost:11434',
        provider:   str  = 'ollama',
        api_key:    str  = None,
    ):
        load_provenance(prov_path)
        self._model_name = model_name
        self._base_url   = base_url
        self._provider   = provider.lower()
        self._api_key    = api_key or os.environ.get('GOOGLE_API_KEY')
        self._llm        = None   # created lazily on first ask()
        self.chat_history: list = []
        print(f"[agent] provider={self._provider}  model={model_name}")

    def _get_llm(self):
        """Return the LLM with tools bound, creating it on first call."""
        if self._llm is None:
            if self._provider == 'google':
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                except ImportError:
                    raise ImportError(
                        "Run: pip install langchain-google-genai"
                    )
                if not self._api_key:
                    raise ValueError(
                        "Google API key required. Set GOOGLE_API_KEY in .env "
                        "or pass --api-key."
                    )
                llm = ChatGoogleGenerativeAI(
                    model       = self._model_name,
                    google_api_key = self._api_key,
                    temperature = 0,
                )
            else:
                import requests as _req
                try:
                    _req.get(f'{self._base_url}/api/tags', timeout=5)
                except Exception:
                    raise ConnectionError(
                        f"Ollama is not reachable at {self._base_url}. "
                        "Start it with: ollama serve"
                    )
                from langchain_ollama import ChatOllama
                llm = ChatOllama(
                    model              = self._model_name,
                    base_url           = self._base_url,
                    temperature        = 0,
                    num_ctx            = 4096,
                    num_predict        = 2048,
                    keep_alive         = -1,
                    sync_client_kwargs = {'timeout': 600},
                )
            self._llm = llm.bind_tools(ALL_TOOLS)
        return self._llm

    def ask(self, question: str, on_token=None) -> dict:
        """
        Ask one question. Returns dict:
            answer     : str   — final agent answer
            tool_calls : list  — [{tool, input, output}, ...]
            steps      : int   — number of tool calls made

        on_token: optional callable(str) — called with each text chunk as
                  the model streams the final answer.  When provided, the
                  terminal sees tokens appear live instead of waiting for
                  the full response.
        """
        llm = self._get_llm()

        # Inject per-question tool hints so small models pick the right tool.
        # Each entry: (trigger_phrases, tool_name)  — first match wins, order matters.
        _TOOL_HINTS = [
            # Most specific patterns first to avoid wrong routing.
            (
                # Subcriteria breakdown for a specific QC criterion
                ('subcriteria', 'sub-criteria', 'breakdown of qc', 'detail for qc'),
                'get_subcriteria_detail',
            ),
            (
                # Per-criterion trend (QC.* names are unambiguous)
                ('trend for qc', 'trend of qc',
                 'qc.acc', 'qc.doc', 'qc.lic', 'qc.sec',
                 'qc.sty', 'qc.ver', 'qc.met', 'qc.uni'),
                'get_qc_trend',
            ),
            (
                # General summary / overview of the whole repo
                ('overall summary', 'general summary', 'give me a summary',
                 'summary of this', 'overview of this', 'overview of the',
                 'summarize this', 'summarise this', 'tell me about this repo',
                 'what is this repository', 'about this repository',
                 'history of this', 'repository history',
                 'overall quality', 'quality history', 'quality overview',
                 'how is this repo', 'how has this repo', 'how did this repo'),
                'get_summary',
            ),
            (
                ('how do i fix', 'how to fix', 'how can i fix', 'how can i improve',
                 'how do i improve', 'how to improve', 'how to pass', 'how do i pass',
                 'fix hint', 'fix hints', 'what should i do to fix',
                 'what do i need to fix', 'recommendations for'),
                'get_fix_hints',
            ),
            (
                ('what failed', 'which tools failed', 'tool failures', 'what tools failed',
                 'tools that failed', 'failing tools', 'what is failing'),
                'get_tool_failures',
            ),
            (
                # Badge-path: what is needed to achieve a badge level
                ('what do i need for', 'what do i need to get',
                 'how to get', 'how to achieve',
                 'path to', 'missing for', 'what is missing for',
                 'how to reach', 'requirements for'),
                'get_badge_path',
            ),
            (
                ('regression', 'regressions', 'badge dropped', 'badge fell',
                 'quality dropped', 'went down'),
                'get_regressions',
            ),
            (
                # Overall quality velocity / direction (not a single criterion)
                ('is quality improving', 'is quality getting', 'quality velocity',
                 'rate of change', 'on track to reach',
                 'which criteria are improving', 'criteria improving',
                 'overall improving', 'overall getting'),
                'get_quality_velocity',
            ),
            (
                # Narrative / timeline of badge history
                ('badge journey', 'story of this project', 'story of the project',
                 'first reach', 'first achieved', 'project journey',
                 'when did this repo', 'when did the project',
                 'how long did it take', 'badge progression', 'badge timeline'),
                'get_badge_journey',
            ),
            (
                # Best sustained period / longest gold streak
                ('at its best', 'best quality', 'best period',
                 'longest gold streak', 'when was this project',
                 'when was the project', 'best sustained'),
                'find_best_period',
            ),
            (
                # All assessments for a specific badge level
                ('all gold badge', 'all silver badge', 'all bronze badge',
                 'show all gold', 'show all silver', 'show all bronze',
                 'gold badge assessments', 'silver badge assessments',
                 'bronze badge assessments'),
                'get_badge_history',
            ),
            (
                # Side-by-side comparison of two assessments
                ('compare the first', 'compare first', 'compare assessment',
                 'compare the last', 'first and last assessment',
                 'compare 2', 'compare two', 'differences between assessment',
                 'between assessment'),
                'compare_assessments',
            ),
        ]
        q_lower = question.lower()
        hint_tool = None
        for triggers, tool_name in _TOOL_HINTS:
            if any(t in q_lower for t in triggers):
                hint_tool = tool_name
                break

        if hint_tool:
            guided_question = (
                f'[TOOL HINT: You MUST call {hint_tool} — do not call any other tool first.]\n'
                + question
            )
        else:
            guided_question = question

        # Trim history to avoid growing context blowing up token count
        messages = (
            [SystemMessage(content=SYSTEM_PROMPT)]
            + self.chat_history[-HISTORY_WINDOW:]
            + [HumanMessage(content=guided_question)]
        )

        tool_calls_log: list[dict] = []
        response = AIMessage(content='')

        for _ in range(MAX_ITERATIONS):
            try:
                if on_token:
                    # Stream chunks; display content live, accumulate for tool detection
                    chunks = []
                    tool_call_seen = False
                    for chunk in llm.stream(messages):
                        chunks.append(chunk)
                        if getattr(chunk, 'tool_calls', None):
                            tool_call_seen = True
                        # Only stream text to user when no tool call is being built
                        if chunk.content and not tool_call_seen:
                            on_token(chunk.content)
                    # Merge all chunks into one AIMessage
                    response = chunks[0] if chunks else AIMessage(content='')
                    for c in chunks[1:]:
                        try:
                            response = response + c
                        except Exception:
                            # chunk merge failed — carry on with what we have
                            break
                else:
                    response = llm.invoke(messages)
            except Exception as exc:
                msg = str(exc)
                if 'connect' in msg.lower() or 'connection' in msg.lower() or 'refused' in msg.lower():
                    raise ConnectionError(
                        f"Ollama lost connection at {self._base_url} — "
                        "is it still running? Try: ollama serve"
                    ) from exc
                raise

            messages.append(response)

            # Prefer structured tool_calls; fall back to parsing text for
            # models that output JSON in their content instead of via the
            # function-calling protocol (e.g. smaller Ollama models).
            tool_calls = list(getattr(response, 'tool_calls', None) or [])
            if not tool_calls:
                tool_calls = _extract_text_tool_calls(
                    getattr(response, 'content', '') or '',
                    known_tools=set(_TOOL_MAP.keys()),
                    hint_tool=hint_tool,
                )
                # Filter to known tools only — ignore any hallucinated names
                tool_calls = [tc for tc in tool_calls if tc['name'] in _TOOL_MAP]

            if not tool_calls:
                break   # model is done — final answer ready

            # Execute each tool call, truncate output to keep tokens low
            for tc in tool_calls:
                name    = tc.get('name', '')
                args    = tc.get('args', {})
                tc_id   = tc.get('id',   '')
                tool    = _TOOL_MAP.get(name)

                # Resolve __positional__ placeholder (Format 3 function-call style).
                # Find the tool's first real parameter name and remap.
                if args and '__positional__' in args and tool is not None:
                    try:
                        schema_props = tool.args_schema.schema().get('properties', {})
                        first_param  = next(iter(schema_props), None)
                        if first_param:
                            args = {first_param: args['__positional__']}
                    except Exception:
                        args = {}

                output  = tool.invoke(args) if tool else f"Unknown tool: {name}"
                out_str = str(output)

                tool_calls_log.append({
                    'tool':   name,
                    'input':  args,
                    'output': out_str[:2500] + ('...' if len(out_str) > 2500 else ''),
                })

                # Truncate before sending to LLM — reduces next-round token count
                truncated = out_str[:TOOL_OUT_LIMIT]
                if len(out_str) > TOOL_OUT_LIMIT:
                    truncated += f'\n[... {len(out_str) - TOOL_OUT_LIMIT} chars omitted]'

                messages.append(ToolMessage(
                    content      = truncated,
                    tool_call_id = tc_id,
                    name         = name,
                ))

        answer = getattr(response, 'content', '') or ''

        # Persist only Human + final AI messages — strip ToolMessages and
        # intermediate AIMessages that carried tool calls.  This keeps history
        # tokens small and prevents HISTORY_WINDOW filling up in one turn.
        self.chat_history = [
            m for m in messages[1:]
            if isinstance(m, (HumanMessage, AIMessage))
            and not getattr(m, 'tool_calls', None)
        ][-HISTORY_WINDOW:]

        return {
            'answer':     answer,
            'tool_calls': tool_calls_log,
            'steps':      len(tool_calls_log),
        }

    def reset(self) -> None:
        """Clear conversation history (LLM binding is kept)."""
        self.chat_history = []
        print('[agent] Conversation reset.')