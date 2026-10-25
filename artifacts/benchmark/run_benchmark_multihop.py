"""
Multi-hop benchmark for yProv4SQA.

10 questions that require 2-3 tool calls in sequence.
Target: interTwin-eu/itwinai (279 assessments).
Tests the loop-detection and chaining improvements in agent.py.
"""
import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_URL = "http://localhost:5000"
ITWINAI_PROV = "Provenance_documents/interTwin-eu_itwinai_prov_output.json"


def load_itwinai(base_url: str, model: str = "llama3.2") -> bool:
    resp = requests.post(
        f"{base_url}/api/load-saved",
        json={"path": ITWINAI_PROV, "model": model},
        timeout=30,
    )
    if not resp.ok:
        return False
    data = resp.json()
    return data.get("status") == "ok" or data.get("loaded") is True

QUESTIONS = [
    # ── 2-tool chains ──────────────────────────────────────────────────────────
    {
        "id": "MH01",
        "category": "regression+fix",
        "question": (
            "What regression caused itwinai to drop from gold to silver, "
            "and what should the developers do to fix it?"
        ),
        "expected_tools": ["get_regressions", "get_fix_hints"],
        "ground_truth": "QC.Sty and/or QC.Uni dropped at assessment 270; fix via code style and unit tests",
        "check": lambda ans: (
            ("QC.Sty" in ans or "style" in ans.lower()) and
            ("fix" in ans.lower() or "improve" in ans.lower() or "recommend" in ans.lower())
        ),
    },
    {
        "id": "MH02",
        "category": "trend+fix",
        "question": (
            "What is the current trend for QC.Sty (code style) over the last 10 assessments, "
            "and what should the team do to address it?"
        ),
        "expected_tools": ["get_qc_trend", "get_fix_hints"],
        "ground_truth": "QC.Sty = 0% in last 10 assessments; fix: apply flake8/rubocop or equivalent",
        "check": lambda ans: (
            ("QC.Sty" in ans or "style" in ans.lower()) and
            ("0" in ans or "fail" in ans.lower() or "not pass" in ans.lower()) and
            ("fix" in ans.lower() or "flake" in ans.lower() or "style" in ans.lower())
        ),
    },
    {
        "id": "MH03",
        "category": "badge_path+fix",
        "question": (
            "What criteria are still missing for itwinai to achieve a gold badge, "
            "and what is the recommended fix for each missing criterion?"
        ),
        "expected_tools": ["get_badge_path", "get_fix_hints"],
        "ground_truth": "QC.Sty missing; fix: code style tools (flake8, rubocop)",
        "check": lambda ans: (
            "QC.Sty" in ans and
            ("fix" in ans.lower() or "style" in ans.lower() or "flake" in ans.lower())
        ),
    },
    {
        "id": "MH04",
        "category": "history+compare",
        "question": (
            "When did itwinai first achieve a gold badge, "
            "and what criterion changed to make that possible compared to the previous assessment?"
        ),
        "expected_tools": ["get_badge_history", "compare_assessments"],
        "ground_truth": "First gold at assessment 163 (2024-10-23); QC.Uni went from 0% to 100%",
        "check": lambda ans: (
            ("163" in ans or "2024-10-23" in ans or "october" in ans.lower()) and
            ("QC.Uni" in ans or "unit" in ans.lower() or "testing" in ans.lower())
        ),
    },
    {
        "id": "MH05",
        "category": "assessment+compare",
        "question": (
            "What badge did itwinai hold at assessment 100, "
            "and how does its quality profile compare to the latest assessment?"
        ),
        "expected_tools": ["get_assessment", "compare_assessments"],
        "ground_truth": "Assessment 100: bronze (2024-06-06); latest (279): silver with QC.Sec, QC.Uni passing",
        "check": lambda ans: (
            "bronze" in ans.lower() and
            ("100" in ans) and
            ("silver" in ans.lower() or "279" in ans or "latest" in ans.lower())
        ),
    },
    # ── 3-tool chains ──────────────────────────────────────────────────────────
    {
        "id": "MH06",
        "category": "history+compare+fix",
        "question": (
            "Compare assessment 39 (the first bronze badge) and assessment 163 (the first gold badge). "
            "Which criteria changed, and what was the most important improvement?"
        ),
        "expected_tools": ["compare_assessments", "get_badge_history"],
        "ground_truth": "QC.Sec, QC.Sty, QC.Met, QC.Uni all went from 0% to 100%; bronze->gold",
        "check": lambda ans: (
            ("39" in ans or "bronze" in ans.lower()) and
            ("163" in ans or "gold" in ans.lower()) and
            any(c in ans for c in ["QC.Sec", "QC.Sty", "QC.Met", "QC.Uni"])
        ),
    },
    {
        "id": "MH07",
        "category": "regression+trend+fix",
        "question": (
            "itwinai had a quality regression recently. "
            "Which criteria regressed, what does the trend look like for the worst one, "
            "and what is the recommended fix?"
        ),
        "expected_tools": ["get_regressions", "get_qc_trend", "get_fix_hints"],
        "ground_truth": "QC.Sty regressed; trend: 0% in recent assessments; fix: code style enforcement",
        "check": lambda ans: (
            ("QC.Sty" in ans or "style" in ans.lower()) and
            ("0" in ans or "fail" in ans.lower()) and
            ("fix" in ans.lower() or "improve" in ans.lower() or "recommend" in ans.lower())
        ),
    },
    {
        "id": "MH08",
        "category": "summary+badge_path",
        "question": (
            "Give me an overview of itwinai's quality history, "
            "and then tell me specifically what is blocking it from reaching gold today."
        ),
        "expected_tools": ["get_summary", "get_badge_path"],
        "ground_truth": "279 assessments, bronze->silver->gold->silver progression; QC.Sty blocks gold",
        "check": lambda ans: (
            ("279" in ans or "assessment" in ans.lower() or
             "silver" in ans.lower() or "badge" in ans.lower()) and
            ("QC.Sty" in ans or "style" in ans.lower()) and
            ("gold" in ans.lower() or "missing" in ans.lower())
        ),
    },
    {
        "id": "MH09",
        "category": "tool_failures+fix",
        "question": (
            "What specific tools are currently failing for QC.Sty (code style), "
            "and what would fix them?"
        ),
        "expected_tools": ["get_tool_failures", "get_fix_hints"],
        "ground_truth": "Code style tools failing; fix: configure flake8/rubocop/similar",
        "check": lambda ans: (
            ("QC.Sty" in ans or "style" in ans.lower()) and
            ("fix" in ans.lower() or "flake" in ans.lower() or "configure" in ans.lower()
             or "tool" in ans.lower())
        ),
    },
    {
        "id": "MH10",
        "category": "subcriteria+fix",
        "question": (
            "What are the subcriteria for QC.Uni (unit testing) and "
            "what does itwinai need to do to ensure it keeps passing?"
        ),
        "expected_tools": ["get_subcriteria_detail", "get_fix_hints"],
        "ground_truth": "QC.Uni subcriteria: tests exist, pass, coverage >= 70%; currently passing (100%)",
        "check": lambda ans: (
            ("QC.Uni" in ans or "unit" in ans.lower() or "test" in ans.lower()) and
            len(ans.strip()) > 50
        ),
    },
]


def reset_agent(base_url: str):
    try:
        requests.post(f"{base_url}/api/reset", timeout=10)
    except Exception:
        pass


def ask_agent(base_url: str, question: str, timeout: int = 180) -> tuple[dict, float]:
    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/api/chat",
        json={"question": question},
        timeout=timeout,
    )
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    return resp.json(), latency


def check_tool_chain(tools_called: list[str], expected: list[str]) -> bool:
    """True if ALL expected tools were called (order-independent)."""
    return all(t in tools_called for t in expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     default="http://localhost:5000")
    parser.add_argument("--model",   default="llama3.2")
    parser.add_argument("--out",     default="benchmark/results")
    parser.add_argument("--timeout", default=180, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\nyProv4SQA Multi-Hop Benchmark — {run_id}")
    print(f"Target: {args.url}   Model: {args.model}")
    print(f"Questions: {len(QUESTIONS)}  (itwinai, 279 assessments)\n")

    if not load_itwinai(args.url, model=args.model):
        print(f"ERROR: could not load {ITWINAI_PROV} — aborting")
        return
    print(f"Loaded: {ITWINAI_PROV}\n")
    time.sleep(1)

    print(f"{'ID':<6} {'Tools':>5} {'Correct':<9} {'Latency':>8}  Question")
    print("-" * 80)

    rows = []
    for q in QUESTIONS:
        reset_agent(args.url)
        answer = error = ""
        tools_called: list[str] = []
        latency = 0.0
        correct = chain_ok = False

        try:
            result, latency = ask_agent(args.url, q["question"], timeout=args.timeout)
            answer       = result.get("answer", "")
            tool_calls   = result.get("tool_calls", [])
            tools_called = [tc.get("tool", tc.get("name", "")) for tc in tool_calls]
            chain_ok     = check_tool_chain(tools_called, q["expected_tools"])
            correct      = bool(q["check"](answer))
        except Exception as e:
            error = str(e)

        row = {
            "id":             q["id"],
            "category":       q["category"],
            "question":       q["question"],
            "expected_tools": "; ".join(q["expected_tools"]),
            "tools_called":   "; ".join(tools_called),
            "chain_complete": chain_ok,
            "correct":        correct,
            "latency_s":      round(latency, 2),
            "ground_truth":   q["ground_truth"],
            "answer":         answer[:400],
            "error":          error,
        }
        rows.append(row)

        status = "✅" if correct else "❌"
        chain_mark = "⛓️" if chain_ok else "🔗❌"
        n_tools = len(tools_called)
        print(f"{q['id']:<6} #{n_tools:<3} {status} {chain_mark:<6} {latency:>6.1f}s  {q['question'][:55]}")

    # Summary
    n_correct    = sum(1 for r in rows if r["correct"])
    n_chain      = sum(1 for r in rows if r["chain_complete"])
    n_q          = len(rows)
    lats         = [r["latency_s"] for r in rows if not r["error"]]
    avg_lat      = sum(lats) / len(lats) if lats else 0
    avg_tools    = sum(len(r["tools_called"].split(";")) for r in rows if r["tools_called"]) / n_q

    print("\n" + "=" * 80)
    print(f"  Task accuracy      : {n_correct}/{n_q}  ({100*n_correct//n_q}%)")
    print(f"  Full chain used    : {n_chain}/{n_q}  ({100*n_chain//n_q}%)")
    print(f"  Avg latency        : {avg_lat:.2f}s")
    print(f"  Avg tools/question : {avg_tools:.1f}")
    print("=" * 80)

    # Save
    csv_path = out_dir / f"multihop_results_{run_id}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "run_id":            run_id,
        "model":             args.model,
        "benchmark":         "multi_hop_v3",
        "n_questions":       n_q,
        "n_correct":         n_correct,
        "n_chain_complete":  n_chain,
        "accuracy_pct":      round(100 * n_correct / n_q, 1),
        "chain_pct":         round(100 * n_chain / n_q, 1),
        "latency_avg_s":     round(avg_lat, 2),
        "avg_tool_calls":    round(avg_tools, 1),
        "per_question": [
            {k: v for k, v in r.items() if k != "answer"} for r in rows
        ],
    }
    summary_path = out_dir / f"multihop_summary_{run_id}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved: {csv_path}")
    print(f"       {summary_path}")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_question"}, indent=2))


if __name__ == "__main__":
    main()
