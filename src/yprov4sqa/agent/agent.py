"""
yprov4sqa/agent/agent.py
========================
Lightweight tool-calling agent using ChatOllama.bind_tools().
"""

import os
import re
import json
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage,
)

from .tools import ALL_TOOLS
from .loader import load_provenance


def _extract_text_tool_calls(content: str, known_tools: set | None = None) -> list[dict]:
    """
    Fallback parser: extract tool calls from model text output.
    Handles three formats that smaller/Ollama models produce:

    1. JSON object:
         {"name": "compare_assessments", "parameters": {"num1_num2": "50,100"}}

    2. LangChain object repr (seen in some Ollama builds):
         {object <nil> {compare_assessments} [50,100] {"num1_num2":{"type":"string"}}}

    3. Python-style function call:
         compare_assessments("50,100")   or   compare_assessments(50, 100)
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
                    # Normalize Python literals that smaller models emit
                    fragment_json = re.sub(r'\bNone\b', 'null', fragment)
                    fragment_json = re.sub(r'\bTrue\b', 'true', fragment_json)
                    fragment_json = re.sub(r'\bFalse\b', 'false', fragment_json)
                    obj = json.loads(fragment_json)
                    if isinstance(obj, dict) and 'name' in obj:
                        name = obj['name']
                        args = obj.get('parameters',
                               obj.get('args',
                               obj.get('input', {})))
                        if not isinstance(args, dict):
                            args = {}
                        # Strip malformed keys (empty string, "[0]", "{}", etc.)
                        args = {k: v for k, v in args.items()
                                if k and re.match(r'^[a-zA-Z_]\w*$', k)}
                        calls.append({'name': name, 'args': args,
                                      'id': f'txt_{len(calls)}'})
                except (json.JSONDecodeError, ValueError):
                    pass
                start = -1

    if calls:
        return calls

    # ── Format 2: {object <nil> {tool_name} [pos_args] {schema}} ──────────
    # e.g. {object <nil> {compare_assessments} [50,100] {"num1_num2":{"type":"string"}}}
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

    return calls

SYSTEM_PROMPT = """You are an expert Software Quality Assurance (SQA) analyst.
You have access to tools that query a real W3C PROV-compliant provenance
document for a GitHub repository assessed by the SQAaaS platform.

AVAILABLE TOOLS — you may ONLY call these 16, never invent tool names:

  Core analysis:
    get_summary          — repo overview, badge counts, recent/all-time QC averages,
                           latest assessment QC scores. Call this first for overviews.
    get_assessment       — full details of one assessment (badge, QC scores, date).
    get_badge_history    — full badge progression over time (bronze/silver/gold dates).
    get_regressions      — recent badge drops and QC score drops (criteria that got worse).
    get_qc_trend         — score trend for a single criterion over last N assessments.
    compare_assessments  — diff two assessments: which criteria improved or degraded.
    find_best_period     — find the assessment range with the highest quality scores.

  Actionable guidance:
    get_tool_failures    — specific tools/checks that failed for a criterion.
    get_fix_hints        — actionable fix recommendations for failing criteria.
    get_badge_path       — criteria still missing to reach the next badge level.

  Extended analysis:
    get_branch_analysis  — QC scores and badge distribution broken down by branch.
    get_subcriteria_detail — subcriteria breakdown for a specific QC criterion.
    get_ci_provenance    — CI/pipeline provenance details for a criterion.
    get_quality_velocity — rate of quality improvement over a sliding window.
    get_partial_runs     — assessments flagged as partial (incomplete) runs.
    get_badge_journey    — narrative of how the repo progressed through badge levels.

MULTI-TOOL CHAINING — use multiple tool calls in sequence when the question has
more than one part, or when the answer to step 1 determines the arguments for step 2.
Examples of correct chaining patterns:

  Q: "What caused the latest regression and how do I fix it?"
  → Step 1: get_regressions()           (find which criteria regressed)
  → Step 2: get_fix_hints("QC.Sty")    (get fix recommendations for that criterion)
  → Answer: combine both results.

  Q: "What changed when itwinai went from bronze to silver, and what still blocks gold?"
  → Step 1: get_badge_history()         (find the assessment where silver was first earned)
  → Step 2: compare_assessments(N-1, N) (diff that transition)
  → Step 3: get_badge_path("gold")      (list remaining blockers)
  → Answer: combine all three.

  Q: "What is the trend for QC.Sec and what should devs do about it?"
  → Step 1: get_qc_trend("QC.Sec")     (get recent score history)
  → Step 2: get_fix_hints("QC.Sec")    (get recommendations)
  → Answer: combine both.

  Q: "Compare assessment 64 and 115."
  → Step 1: compare_assessments(64, 115)
  → Answer: report the diff directly.

RULES — follow these strictly:
1. Always call at least one tool before answering. Never guess or invent data.
2. If a question has two parts (e.g., "X and how to fix it"), call tools for both parts.
3. Do NOT call the same tool with the same arguments twice — that is a loop.
   If a tool returns insufficient data, call a DIFFERENT tool to get more context.
4. Be precise: use exact assessment numbers, percentages, dates from tool results.
5. For overview/summary questions always call get_summary first.
6. Use qc_recent_10_averages from get_summary for recent trends.
   Use qc_all_time_averages for long-term history. Do NOT call get_qc_trend for this.
7. When a question asks about a specific criterion (e.g., "QC.Sec"), extract the
   criterion name from the question and pass it directly to the relevant tool.
8. After calling get_regressions, if it identifies a specific criterion, immediately
   call get_fix_hints with that criterion to complete a "cause + remedy" answer.

PROVENANCE MODEL CONTEXT (W3C PROV standard):
- Entity:   Repository, Assessment (one per commit), Output (badge result)
- Activity: QualityCheck — 8 per assessment (QC.Acc, QC.Doc, QC.Lic, QC.Sec,
                                               QC.Sty, QC.Ver, QC.Met, QC.Uni)
- Agent:    SQAaaS (automated assessment platform)
- Relations: wasGeneratedBy, wasDerivedFrom, wasAttributedTo

QUALITY CRITERION GLOSSARY (SQAaaS official names):
- QC.Acc = Code Accessibility   : source code open, public, in a VCS.
- QC.Doc = Documentation        : docs treated as code; README, CONTRIBUTING required.
- QC.Lic = Licensing            : OSI-compliant open-source license required.
- QC.Sec = Security             : SAST tools applied; no known vulnerabilities.
- QC.Sty = Code Style           : community style standards (flake8, rubocop…).
- QC.Ver = Semantic Versioning  : release tags follow SemVer (e.g. v1.2.0).
- QC.Met = Code Metadata        : CITATION.cff or codemeta.json required.
- QC.Uni = Unit Testing         : unit tests exist, pass, reach 70%+ coverage.

BADGE LEVELS:
- Bronze: QC.Acc + QC.Doc + QC.Lic
- Silver: Bronze + QC.Ver + QC.Met
- Gold:   Silver + QC.Sec + QC.Sty + QC.Uni

QC SCORE MEANING:
- 100% = criterion FULLY PASSED.  0% = COMPLETELY FAILED (BAD).
- assessment_id is a sequential index (e.g. 110 = the 110th run), NOT a score.

"""

# Lookup map: tool name → callable (built once at module load, lightweight)
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}

MAX_ITERATIONS  = 12    # max tool-call rounds per question (raised for multi-hop)
HISTORY_WINDOW  = 8     # keep last 4 turns (human+AI pairs) to limit token count
TOOL_OUT_LIMIT  = int(os.environ.get('TOOL_OUT_LIMIT', '1500'))


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
                from langchain_ollama import ChatOllama
                _is_large = any(x in self._model_name for x in ('70b', '72b', '65b', '34b'))
                llm = ChatOllama(
                    model       = self._model_name,
                    base_url    = self._base_url,
                    temperature = 0,
                    num_predict = 2048 if _is_large else 512,
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
        # Multi-hop hints describe a full chain; single hints point to the first tool.
        # Each entry: (trigger_phrases, hint_text)
        _TOOL_HINTS = [
            # ── Multi-hop chains (checked first — more specific) ─────────────
            (
                ('regression', 'regressions', 'badge dropped', 'badge fell',
                 'quality dropped', 'went down', 'score dropped', 'quality fallen',
                 'badge level go down', 'badge level dropped',
                 'has the quality', 'did any badge', 'quality score dropped'),
                (
                    'get_regressions first to identify which criteria regressed. '
                    'Then, if the question asks what to do or how to fix it, '
                    'call get_fix_hints with the affected criterion.'
                ),
            ),
            (
                ('what caused', 'why did', 'what changed', 'what happened',
                 'what led to', 'what made'),
                (
                    'compare_assessments(N1, N2) to diff the two assessments. '
                    'If the question also asks for a fix, follow with get_fix_hints.'
                ),
            ),
            (
                ('how do i fix', 'how to fix', 'how can i fix', 'how can i improve',
                 'how do i improve', 'how to improve', 'what should developers do',
                 'what should i do to fix', 'recommendations for', 'fix hint'),
                (
                    'get_fix_hints with the specific criterion name (e.g. "QC.Sec"). '
                    'If you do not know which criterion is failing, call get_regressions first.'
                ),
            ),
            (
                ('path to gold', 'missing for gold', 'how to achieve gold',
                 'what do i need for gold', 'how to get gold',
                 'missing for silver', 'how to achieve silver', 'path to silver',
                 'missing for', 'what is missing for', 'requirements for badge',
                 'criteria missing', 'criteria are missing', 'achieve a gold',
                 'achieve gold', 'achieve a silver', 'achieve silver'),
                (
                    'Use get_badge_path — it returns the criteria still missing for '
                    'the next badge level. Do NOT use get_badge_history; that tool '
                    'only shows dates when past badges were awarded, not what is missing.'
                ),
            ),
            # ── Single-tool hints ────────────────────────────────────────────
            (
                ('assessment number', 'assessment no', 'assessment #',
                 'what badge was awarded in assessment', 'details of assessment',
                 'show assessment', 'look at assessment', 'check assessment',
                 'what happened in assessment', 'result of assessment',
                 'score in assessment', 'info on assessment',
                 'hold at assessment', 'badge at assessment',
                 'held at assessment', 'have at assessment'),
                'get_assessment',
            ),
            (
                ('overall summary', 'general summary', 'give me a summary',
                 'summary of this', 'overview of this', 'overview of the',
                 'summarize this', 'summarise this', 'tell me about this repo',
                 'what is this repository', 'about this repository',
                 'overall quality', 'quality history', 'quality overview',
                 'how is this repo', 'how has this repo',
                 'current badge level', 'current badge', 'what badge level',
                 'what is the current badge', 'what is the badge'),
                'get_summary',
            ),
            (
                ('what failed', 'which tools failed', 'tool failures',
                 'tools that failed', 'failing tools', 'what is failing'),
                'get_tool_failures',
            ),
            (
                ('first badge', 'badge history',
                 'when did', 'when was the first', 'badge awarded',
                 'how many badges', 'how many silver', 'how many bronze', 'how many gold',
                 'first bronze', 'first silver', 'first gold'),
                'get_badge_history',
            ),
            (
                ('trend', 'score over', 'score trend', 'how has qc', 'recent score',
                 'last 10', 'last 20', 'over the last', 'over time'),
                'get_qc_trend',
            ),
        ]
        q_lower = question.lower()
        hint_text = None
        for triggers, hint in _TOOL_HINTS:
            if any(t in q_lower for t in triggers):
                hint_text = hint
                break

        import os as _os
        if hint_text and not _os.environ.get('DISABLE_TOOL_HINTS'):
            guided_question = (
                f'[TOOL HINT: {hint_text}]\n'
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
        _seen_calls: set = set()   # (name, frozen_args) — loop detection
        _empty_rounds = 0          # consecutive rounds with no successful tool calls

        for _ in range(MAX_ITERATIONS):
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

            messages.append(response)

            # Prefer structured tool_calls; fall back to parsing text for
            # models that output JSON in their content instead of via the
            # function-calling protocol (e.g. smaller Ollama models).
            tool_calls = list(getattr(response, 'tool_calls', None) or [])
            if not tool_calls:
                tool_calls = _extract_text_tool_calls(
                    getattr(response, 'content', '') or '',
                    known_tools=set(_TOOL_MAP.keys()),
                )
                # Filter to known tools only — ignore any hallucinated names
                tool_calls = [tc for tc in tool_calls if tc['name'] in _TOOL_MAP]

            if not tool_calls:
                break   # model is done — final answer ready

            # Dead-end guard: if 3 consecutive rounds produce zero new tool calls
            # (all were duplicates or all failed), stop looping.
            round_new_calls = 0

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

                # Loop detection: skip if this exact (tool, args) was already called.
                _call_key = (name, tuple(sorted(str(args).split())))
                if _call_key in _seen_calls:
                    messages.append(ToolMessage(
                        content=(
                            f"[LOOP DETECTED] You already called {name} with these "
                            f"arguments. Do NOT call it again. Use the result you "
                            f"already received, or call a DIFFERENT tool."
                        ),
                        tool_call_id=tc_id,
                        name=name,
                    ))
                    continue
                _seen_calls.add(_call_key)
                round_new_calls += 1

                # Coerce args: 70B sometimes passes {"type":"integer","value":N}
                # instead of a plain integer — extract the value before invoking.
                if tool is not None and args:
                    try:
                        schema_props = tool.args_schema.schema().get('properties', {})
                        coerced = {}
                        for k, v in args.items():
                            expected = schema_props.get(k, {}).get('type', '')
                            if expected == 'integer' and isinstance(v, dict):
                                for candidate in ('value', 'default'):
                                    if candidate in v:
                                        try:
                                            coerced[k] = int(v[candidate]); break
                                        except (TypeError, ValueError):
                                            pass
                                else:
                                    coerced[k] = v
                            elif expected == 'integer' and isinstance(v, str):
                                try:
                                    coerced[k] = int(v)
                                except ValueError:
                                    coerced[k] = v
                            else:
                                coerced[k] = v
                        args = coerced
                    except Exception:
                        pass

                try:
                    output = tool.invoke(args) if tool else f"Unknown tool: {name}"
                except Exception as exc:
                    output = (
                        f"Tool call failed: {exc}. "
                        f"Please retry {name} with correct argument types "
                        f"(integer arguments must be plain numbers, not objects)."
                    )
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

            # Dead-end: if this whole round produced no new calls, increment counter.
            if round_new_calls == 0:
                _empty_rounds += 1
                if _empty_rounds >= 3:
                    # Inject a message telling the model to synthesise from what it has.
                    messages.append(ToolMessage(
                        content=(
                            "[AGENT] You have made no new tool calls for 3 rounds. "
                            "Stop calling tools and provide your final answer using "
                            "the information already gathered."
                        ),
                        tool_call_id='__dead_end__',
                        name='__agent__',
                    ))
                    break
            else:
                _empty_rounds = 0

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