import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import requests

PARAPHRASE_GROUPS = [
    {
        "concept": "summary",
        "expected_tool": "get_summary",
        "variants": [
            "How many assessments are in the provenance document?",
            "What is the total number of quality evaluations recorded?",
            "Give me an overview of this repository's assessment history.",
        ],
    },
    {
        "concept": "badge_history",
        "expected_tool": "get_badge_history",
        "variants": [
            "When was the first bronze badge awarded?",
            "At which assessment did this repo first earn a bronze badge?",
            "What was the earliest bronze badge in the history?",
        ],
    },
    {
        "concept": "badge_history_silver",
        "expected_tool": "get_badge_history",
        "variants": [
            "When was the first silver badge awarded?",
            "Which assessment first achieved silver level?",
            "How many silver badges has the repository received in total?",
        ],
    },
    {
        "concept": "assessment_detail",
        "expected_tool": "get_assessment",
        "variants": [
            "What badge was awarded in assessment 64?",
            "What was the result of assessment number 64?",
            "Show me the details of assessment 64.",
        ],
    },
    {
        "concept": "badge_path",
        "expected_tool": "get_badge_path",
        "variants": [
            "What criteria are missing for the repository to achieve a gold badge?",
            "What does this repo need to do to get a gold badge?",
            "Which quality checks are still missing for gold?",
        ],
    },
    {
        "concept": "regressions",
        "expected_tool": "get_regressions",
        "variants": [
            "Are there any quality regressions in the recent assessments?",
            "Has the quality score dropped in any recent evaluations?",
            "Did any badge level go down recently?",
        ],
    },
    {
        "concept": "compare",
        "expected_tool": "compare_assessments",
        "variants": [
            "Compare assessment 64 and assessment 115. What changed?",
            "What is the difference between assessment 64 and assessment 115?",
            "How did the quality evolve from assessment 64 to 115?",
        ],
    },
    {
        "concept": "fix_hints",
        "expected_tool": ["get_fix_hints", "get_tool_failures"],
        "variants": [
            "What should developers do to improve the quality score?",
            "How can the team fix the failing quality checks?",
            "What recommendations do you have for improving QC?",
        ],
    },
]


def ask_agent(base_url: str, question: str, timeout: int = 120):
    t0 = time.perf_counter()
    resp = requests.post(f"{base_url}/api/chat",
                         json={"question": question}, timeout=timeout)
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    return resp.json(), latency


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     default="http://localhost:5000")
    parser.add_argument("--out",     default="benchmark/results")
    parser.add_argument("--model",   default="llama3.2")
    parser.add_argument("--timeout", default=120, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    total_q = sum(len(g["variants"]) for g in PARAPHRASE_GROUPS)
    print(f"\nyProv4SQA Paraphrase Robustness Benchmark — {run_id}")
    print(f"Target: {args.url}   Model: {args.model}")
    print(f"Groups: {len(PARAPHRASE_GROUPS)}  Questions: {total_q}\n")

    rows = []
    group_results = []

    for group in PARAPHRASE_GROUPS:
        concept  = group["concept"]
        expected = group["expected_tool"]
        accepted = expected if isinstance(expected, list) else [expected]

        variant_results = []
        print(f"  Concept: {concept}")
        for i, question in enumerate(group["variants"], 1):
            requests.post(f"{args.url}/api/reset", timeout=10)
            tools_called = []
            latency = 0.0
            error = ""
            tool_match = False
            answer = ""

            try:
                result, latency = ask_agent(args.url, question, args.timeout)
                answer = result.get("answer", "")
                tool_calls = result.get("tool_calls", [])
                tools_called = [tc.get("tool", "") for tc in tool_calls]
                tool_match = any(t in tools_called for t in accepted)
            except Exception as e:
                error = str(e)

            sym = "✅" if tool_match else "❌"
            print(f"    V{i} {sym}  {question[:60]}")
            variant_results.append(tool_match)

            rows.append({
                "concept": concept,
                "variant": i,
                "question": question,
                "expected_tool": "; ".join(accepted),
                "tools_called": "; ".join(tools_called),
                "tool_match": tool_match,
                "latency_s": round(latency, 2),
                "answer": answer[:300],
                "error": error,
            })

        all_correct = all(variant_results)
        n_correct   = sum(variant_results)
        group_results.append({
            "concept": concept,
            "correct": n_correct,
            "total": len(variant_results),
            "robust": all_correct,
        })
        print(f"    → {n_correct}/{len(variant_results)} correct {'(ROBUST ✅)' if all_correct else '(INCONSISTENT ❌)'}\n")

    n_robust = sum(1 for g in group_results if g["robust"])
    n_groups = len(group_results)
    n_correct_q = sum(1 for r in rows if r["tool_match"])
    lats = [r["latency_s"] for r in rows if not r["error"]]
    avg_lat = sum(lats) / len(lats) if lats else 0

    print(f"{'='*70}")
    print(f"  Robust concepts (all 3 variants correct) : {n_robust}/{n_groups} ({100*n_robust//n_groups}%)")
    print(f"  Overall tool selection accuracy          : {n_correct_q}/{total_q} ({100*n_correct_q//total_q}%)")
    print(f"  Average latency                          : {avg_lat:.2f}s")
    print(f"{'='*70}")

    csv_path = out_dir / f"paraphrase_results_{run_id}.csv"
    log_path = out_dir / f"paraphrase_log_{run_id}.jsonl"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(log_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    summary = {
        "run_id": run_id, "model": args.model,
        "n_groups": n_groups, "n_robust": n_robust,
        "n_questions": total_q, "n_correct": n_correct_q,
        "robust_pct": round(100 * n_robust / n_groups, 1),
        "tool_acc_pct": round(100 * n_correct_q / total_q, 1),
        "latency_avg_s": round(avg_lat, 2),
        "per_group": group_results,
    }
    with open(out_dir / f"paraphrase_summary_{run_id}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_group"}, indent=2))
    print(f"\nSaved: {csv_path}")


if __name__ == "__main__":
    main()
