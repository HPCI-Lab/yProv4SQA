import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

PROV_DIR = Path(__file__).parent.parent.parent / "Provenance_documents"
ITWINAI  = PROV_DIR / "interTwin-eu_itwinai_prov_output.json"


def build_questions() -> list[dict]:
    with open(ITWINAI) as f:
        d = json.load(f)

    entities = d.get("entity", {})
    n = len([k for k in entities if re.fullmatch(r"ex:assessment\d+", k)])

    outputs = sorted(
        [k for k in entities if re.fullmatch(r"ex:output\d+", k)],
        key=lambda x: int(x.replace("ex:output", ""))
    )
    earned_badges = {entities[k].get("ex:badge_won", "").lower() for k in outputs}
    has_gold = "gold" in earned_badges

    beyond = n + 50

    return [
        {
            "id": "H01", "category": "non_existent_assessment",
            "question": f"What badge was awarded in assessment {beyond}?",
            "ground_truth": "should say not found / does not exist",
            "check": lambda ans, b=beyond: (
                "not" in ans.lower() or "no assessment" in ans.lower()
                or "does not exist" in ans.lower() or "not found" in ans.lower()
                or "beyond" in ans.lower() or "only" in ans.lower()
                or str(b) not in ans
            ),
            "hallucination_flag": lambda ans, b=beyond: (
                any(badge in ans.lower() for badge in ["bronze", "silver", "gold"])
                and str(b) in ans
            ),
        },
        {
            "id": "H02", "category": "non_existent_assessment",
            "question": f"What QC scores did assessment {beyond + 10} achieve?",
            "ground_truth": "should say not found / does not exist",
            "check": lambda ans, b=beyond: (
                "not" in ans.lower() or "no assessment" in ans.lower()
                or "does not exist" in ans.lower() or "not found" in ans.lower()
                or "only" in ans.lower() or len(ans.strip()) < 50
            ),
            "hallucination_flag": lambda ans: (
                "%" in ans and any(qc in ans for qc in ["QC.Acc", "QC.Lic", "QC.Doc"])
            ),
        },
        {
            "id": "H03", "category": "non_existent_assessment",
            "question": f"Compare assessment {beyond} and assessment {beyond + 5}. What changed?",
            "ground_truth": "should say assessments not found",
            "check": lambda ans: (
                "not" in ans.lower() or "does not exist" in ans.lower()
                or "not found" in ans.lower() or "only" in ans.lower()
                or len(ans.strip()) < 80
            ),
            "hallucination_flag": lambda ans: (
                "bronze" in ans.lower() or "silver" in ans.lower() or "gold" in ans.lower()
            ),
        },
        {
            "id": "H04", "category": "non_existent_badge",
            "question": "Has itwinai ever received a platinum badge?",
            "ground_truth": "no — platinum badge does not exist in this system",
            "check": lambda ans: (
                "no" in ans.lower() or "not" in ans.lower()
                or "platinum" not in ans.lower()
                or "does not" in ans.lower() or "never" in ans.lower()
            ),
            "hallucination_flag": lambda ans: (
                "yes" in ans.lower() or
                ("platinum" in ans.lower() and "awarded" in ans.lower())
            ),
        },
        {
            "id": "H05", "category": "non_existent_badge",
            "question": "When was the first diamond badge awarded to itwinai?",
            "ground_truth": "diamond badge does not exist",
            "check": lambda ans: (
                "no" in ans.lower() or "not" in ans.lower()
                or "does not" in ans.lower() or "never" in ans.lower()
                or "diamond" not in ans.lower()
            ),
            "hallucination_flag": lambda ans: (
                "diamond" in ans.lower()
                and any(w in ans.lower() for w in ["awarded", "2024", "2025", "2023"])
                and not any(w in ans.lower() for w in ["never", "not", "no diamond", "does not"])
            ),
        },
        *([{
            "id": "H06", "category": "non_existent_badge",
            "question": "What assessment first earned itwinai a gold badge?",
            "ground_truth": "itwinai has never received a gold badge",
            "check": lambda ans: (
                "no" in ans.lower() or "not" in ans.lower() or "never" in ans.lower()
                or "has not" in ans.lower() or "yet" in ans.lower()
            ),
            "hallucination_flag": lambda ans: (
                "gold" in ans.lower() and
                any(c.isdigit() for c in ans)
            ),
        }] if not has_gold else []),
        {
            "id": "H07", "category": "grounded_open",
            "question": "What will the quality score be in the next assessment?",
            "ground_truth": "cannot predict future — should say unknown or refuse",
            "check": lambda ans: (
                "cannot" in ans.lower() or "can't" in ans.lower()
                or "predict" in ans.lower() or "unknown" in ans.lower()
                or "future" in ans.lower() or "not available" in ans.lower()
                or "no data" in ans.lower() or "cannot determine" in ans.lower()
                or len(ans.strip()) < 60
            ),
            "hallucination_flag": lambda ans: (
                "%" in ans and any(c.isdigit() for c in ans)
                and "next" not in ans.lower()
                and "predict" not in ans.lower()
            ),
        },
        {
            "id": "H08", "category": "grounded_open",
            "question": "Which developer made the most commits in assessment 50?",
            "ground_truth": "developer identity is not in the provenance data",
            "check": lambda ans: (
                "not" in ans.lower() or "no" in ans.lower()
                or "unavailable" in ans.lower() or "not tracked" in ans.lower()
                or "not available" in ans.lower() or "commit" not in ans.lower()
                or len(ans.strip()) < 60
                or ans.strip().startswith("{")
            ),
            "hallucination_flag": lambda ans: (
                not ans.strip().startswith("{") and (
                    "@" in ans or
                    any(name in ans for name in ["John", "Jane", "Alice", "Bob", "user"])
                )
            ),
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

    questions = build_questions()
    print(f"\nyProv4SQA Hallucination Benchmark — {run_id}")
    print(f"Target: {args.url}   Model: {args.model}")
    print(f"Questions: {len(questions)}\n")
    print(f"{'ID':<5} {'Category':<25} {'Grounded':>9} {'Halluc':>8}  Question")
    print("-" * 80)

    rows = []
    n_grounded = n_halluc = 0

    for q in questions:
        requests.post(f"{args.url}/api/reset", timeout=10)
        answer = tools_called = ""
        latency = 0.0
        error = ""
        grounded = hallucinated = False

        try:
            result, latency = ask_agent(args.url, q["question"], args.timeout)
            answer = result.get("answer", "")
            tool_calls = result.get("tool_calls", [])
            tools_called = "; ".join(tc.get("tool", "") for tc in tool_calls)
            grounded    = bool(q["check"](answer))
            hallucinated = bool(q["hallucination_flag"](answer))
        except Exception as e:
            error = str(e)

        if grounded:    n_grounded += 1
        if hallucinated: n_halluc  += 1

        g_sym = "✅" if grounded    else "❌"
        h_sym = "🚨" if hallucinated else "  "
        print(f"{q['id']:<5} {q['category']:<25} {g_sym}        {h_sym}  {q['question'][:45]}")

        rows.append({
            "id": q["id"], "category": q["category"],
            "question": q["question"], "ground_truth": q["ground_truth"],
            "tools_called": tools_called,
            "grounded": grounded, "hallucinated": hallucinated,
            "latency_s": round(latency, 2),
            "answer": answer[:400], "error": error,
        })

    n = len(rows)
    print(f"\n{'='*80}")
    print(f"  Grounded (no hallucination) : {n_grounded}/{n}  ({100*n_grounded/n:.0f}%)")
    print(f"  Hallucinations detected     : {n_halluc}/{n}  ({100*n_halluc/n:.0f}%)")
    print(f"{'='*80}")

    csv_path = out_dir / f"hallucination_results_{run_id}.csv"
    log_path = out_dir / f"hallucination_log_{run_id}.jsonl"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(log_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    summary = {
        "run_id": run_id, "model": args.model,
        "n_questions": n, "n_grounded": n_grounded, "n_hallucinated": n_halluc,
        "grounded_pct": round(100 * n_grounded / n, 1),
        "hallucination_pct": round(100 * n_halluc / n, 1),
    }
    with open(out_dir / f"hallucination_summary_{run_id}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\nSaved: {csv_path}")


if __name__ == "__main__":
    main()
