import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import requests

QUESTIONS = [
    {
        "id": "Q01",
        "category": "summary",
        "expected_tool": "get_summary",
        "question": "How many assessments are in the provenance document?",
        "ground_truth": "279",
        "check": lambda ans: "279" in ans,
    },
    {
        "id": "Q02",
        "category": "summary",
        "expected_tool": "get_summary",
        "question": "What is the name of the software repository?",
        "ground_truth": "interTwin-eu/itwinai",
        "check": lambda ans: "itwinai" in ans.lower(),
    },
    {
        "id": "Q03",
        "category": "badge",
        "expected_tool": "get_badge_history",
        "question": "When was the first bronze badge awarded?",
        "ground_truth": "assessment 39 / 2023-11-16",
        "check": lambda ans: "39" in ans or "2023-11-16" in ans or "november" in ans.lower(),
    },
    {
        "id": "Q04",
        "category": "badge",
        "expected_tool": "get_badge_history",
        "question": "When was the first silver badge awarded?",
        "ground_truth": "assessment 115 / 2024-06-13",
        "check": lambda ans: "115" in ans or "2024-06-13" in ans or "june" in ans.lower(),
    },
    {
        "id": "Q05",
        "category": "badge",
        "expected_tool": "get_badge_history",
        "question": "When was the first gold badge awarded?",
        "ground_truth": "assessment 163",
        "check": lambda ans: "163" in ans,
    },
    {
        "id": "Q06",
        "category": "badge",
        "expected_tool": "get_badge_history",
        "question": "How many silver badges has itwinai received in total?",
        "ground_truth": "135 silver badges",
        "check": lambda ans: "135" in ans,
    },
    {
        "id": "Q07",
        "category": "assessment",
        "expected_tool": "get_assessment",
        "question": "What badge was awarded in assessment 64?",
        "ground_truth": "bronze",
        "check": lambda ans: "bronze" in ans.lower(),
    },
    {
        "id": "Q08",
        "category": "assessment",
        "expected_tool": "get_assessment",
        "question": "What badge was awarded in assessment 115?",
        "ground_truth": "silver",
        "check": lambda ans: "silver" in ans.lower(),
    },
    {
        "id": "Q09",
        "category": "qc_trend",
        "expected_tool": "get_qc_trend",
        "question": "What is the trend for the QC.Sec (security) criterion over the last 10 assessments?",
        "ground_truth": "0% (security consistently fails)",
        "check": lambda ans: "0" in ans or "sec" in ans.lower(),
    },
    {
        "id": "Q10",
        "category": "qc_trend",
        "expected_tool": ["get_qc_trend", "get_tool_failures", "get_assessment"],
        "question": "What is the current score for QC.Lic (licensing)?",
        "ground_truth": "75% (latest assessment 279)",
        "check": lambda ans: "75" in ans,
    },
    {
        "id": "Q11",
        "category": "regressions",
        "expected_tool": "get_regressions",
        "question": "Are there any quality regressions in the recent assessments?",
        "ground_truth": "regression info from prov doc",
        "check": lambda ans: len(ans.strip()) > 20,
    },
    {
        "id": "Q12",
        "category": "compare",
        "expected_tool": "compare_assessments",
        "question": "Compare assessment 64 and assessment 115. What changed?",
        "ground_truth": "bronze to silver, QC.Met fulfilled",
        "check": lambda ans: "qc.met" in ans.lower(),
    },
    {
        "id": "Q13",
        "category": "badge_path",
        "expected_tool": "get_badge_path",
        "question": "What criteria are missing for itwinai to achieve a gold badge?",
        "ground_truth": "QC.Sty, QC.Uni, QC.Sec",
        "check": lambda ans: any(x in ans for x in ["QC.Sty", "QC.Sec", "QC.Uni", "style", "security", "unit"]),
    },
    {
        "id": "Q14",
        "category": "fix_hints",
        "expected_tool": ["get_fix_hints", "get_tool_failures"],
        "question": "What should the developers do to improve the security (QC.Sec) score?",
        "ground_truth": "SAST / static analysis tools",
        "check": lambda ans: any(x in ans.lower() for x in ["sast", "static", "security", "analysis"]),
    },
    {
        "id": "Q15",
        "category": "quality_velocity",
        "expected_tool": ["get_quality_velocity", "get_summary"],
        "question": "Is the overall quality of itwinai improving or declining recently?",
        "ground_truth": "improving/stable (silver badge)",
        "check": lambda ans: len(ans.strip()) > 20,
    },
]


def reset_agent(base_url: str):
    try:
        requests.post(f"{base_url}/api/reset", timeout=10)
    except Exception:
        pass


def ask_agent(base_url: str, question: str, timeout: int = 120) -> tuple[dict, float]:
    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/api/chat",
        json={"question": question},
        timeout=timeout,
    )
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    return resp.json(), latency


def evaluate(answer: str, check_fn) -> bool:
    try:
        return bool(check_fn(answer))
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",   default="http://localhost:5000")
    parser.add_argument("--out",   default="benchmark/results")
    parser.add_argument("--model", default="unknown")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = out_dir / f"benchmark_log_{run_id}.jsonl"
    csv_path = out_dir / f"benchmark_results_{run_id}.csv"

    print(f"\nyProv4SQA Agent Benchmark — {run_id}")
    print(f"Target: {args.url}   Model: {args.model}")
    print(f"Questions: {len(QUESTIONS)}\n")
    print(f"{'ID':<5} {'Category':<16} {'Correct':<9} {'Latency':>9}  Question")
    print("-" * 80)

    rows = []

    with open(log_path, "w") as log_f, open(csv_path, "w", newline="") as csv_f:
        writer = csv.DictWriter(csv_f, fieldnames=[
            "id", "category", "question", "expected_tool",
            "tools_called", "tool_match", "correct",
            "latency_s", "answer", "ground_truth", "error",
        ])
        writer.writeheader()

        for q in QUESTIONS:
            reset_agent(args.url)
            error = ""
            answer = ""
            tools_called = []
            latency = 0.0
            correct = False
            tool_match = False
            result = {"tool_calls": []}

            try:
                result, latency = ask_agent(args.url, q["question"])
                answer       = result.get("answer", "")
                tool_calls   = result.get("tool_calls", [])
                tools_called = [tc.get("tool", tc.get("name", "")) for tc in tool_calls]
                expected = q["expected_tool"]
                accepted = expected if isinstance(expected, list) else [expected]
                tool_match = any(t in tools_called for t in accepted)
                correct      = evaluate(answer, q["check"])
            except Exception as e:
                error = str(e)

            row = {
                "id":            q["id"],
                "category":      q["category"],
                "question":      q["question"],
                "expected_tool": "; ".join(q["expected_tool"]) if isinstance(q["expected_tool"], list) else q["expected_tool"],
                "tools_called":  "; ".join(tools_called),
                "tool_match":    tool_match,
                "correct":       correct,
                "latency_s":     round(latency, 2),
                "answer":        answer[:500],
                "ground_truth":  q["ground_truth"],
                "error":         error,
            }
            rows.append(row)
            writer.writerow(row)
            csv_f.flush()

            log_f.write(json.dumps({
                "run_id": run_id, "model": args.model,
                **row,
                "answer_full": answer,
                "tool_calls_full": result.get("tool_calls", []),
            }) + "\n")
            log_f.flush()

            status = "✅" if correct else "❌"
            tm     = "✓" if tool_match else "✗"
            print(f"{q['id']:<5} {q['category']:<16} {status} tm={tm}  {latency:>6.1f}s  {q['question'][:60]}")

    n          = len(rows)
    n_correct  = sum(1 for r in rows if r["correct"])
    n_toolmatch= sum(1 for r in rows if r["tool_match"])
    n_error    = sum(1 for r in rows if r["error"])
    latencies  = [r["latency_s"] for r in rows if not r["error"]]
    avg_lat    = sum(latencies) / len(latencies) if latencies else 0
    max_lat    = max(latencies) if latencies else 0
    min_lat    = min(latencies) if latencies else 0

    print("\n" + "=" * 80)
    print(f"  Task completion rate : {n_correct}/{n}  ({100*n_correct/n:.0f}%)")
    print(f"  Tool selection acc.  : {n_toolmatch}/{n}  ({100*n_toolmatch/n:.0f}%)")
    print(f"  Errors               : {n_error}/{n}")
    print(f"  Latency  avg={avg_lat:.1f}s  min={min_lat:.1f}s  max={max_lat:.1f}s")
    print("=" * 80)

    summary = {
        "run_id":        run_id,
        "model":         args.model,
        "url":           args.url,
        "n_questions":   n,
        "n_correct":     n_correct,
        "n_tool_match":  n_toolmatch,
        "n_errors":      n_error,
        "accuracy_pct":  round(100 * n_correct / n, 1),
        "tool_acc_pct":  round(100 * n_toolmatch / n, 1),
        "latency_avg_s": round(avg_lat, 2),
        "latency_min_s": round(min_lat, 2),
        "latency_max_s": round(max_lat, 2),
    }
    with open(out_dir / f"benchmark_summary_{run_id}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
