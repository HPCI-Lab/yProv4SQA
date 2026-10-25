"""
No-tools baseline benchmark.

Asks the same 88 multi-repo questions to llama3.2 via Ollama directly,
with NO tools and NO provenance data — the model must answer from training
knowledge alone.  Expected result: near-zero accuracy on factual lookups,
demonstrating the value of the tool-augmented architecture.
"""
import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

_MONTH_NAMES = [
    "january","february","march","april","may","june",
    "july","august","september","october","november","december",
]

def _date_in_answer(ans: str, iso_date: str | None) -> bool:
    if not iso_date:
        return False
    if iso_date in ans:
        return True
    try:
        year, mon, day = iso_date.split("-")
        mon_name = _MONTH_NAMES[int(mon) - 1]
        day_int = str(int(day))
        return (mon_name in ans.lower() and day_int in ans and year in ans)
    except Exception:
        return False

PROV_DIR = Path(__file__).parent.parent.parent / "Provenance_documents"

# ── Reuse question builder from the multi-repo benchmark ──────────────────────
def build_questions(prov_path: Path) -> list[dict]:
    with open(prov_path) as f:
        d = json.load(f)

    entities   = d.get("entity",   {})

    assessments = sorted(
        [k for k in entities if re.fullmatch(r"ex:assessment\d+", k)],
        key=lambda x: int(x.replace("ex:assessment", ""))
    )
    outputs = sorted(
        [k for k in entities if re.fullmatch(r"ex:output\d+", k)],
        key=lambda x: int(x.replace("ex:output", ""))
    )
    n = len(assessments)
    repo_name = entities.get("ex:repository1", {}).get("ex:name", "unknown")

    first_bronze_num = first_bronze_date = None
    for k in outputs:
        if entities[k].get("ex:badge_won") == "bronze":
            first_bronze_num = int(k.replace("ex:output", ""))
            raw = entities[k].get("ex:Issued_On:str", "")
            first_bronze_date = raw[:10] if raw else None
            break

    first_silver_num = first_silver_date = None
    for k in outputs:
        if entities[k].get("ex:badge_won") == "silver":
            first_silver_num = int(k.replace("ex:output", ""))
            raw = entities[k].get("ex:Issued_On:str", "")
            first_silver_date = raw[:10] if raw else None
            break

    latest_badge = entities.get(outputs[-1], {}).get("ex:badge_won", "unknown") if outputs else "unknown"

    questions = []

    questions.append({
        "id": "Q01", "category": "summary",
        "question": "How many assessments are in the provenance document?",
        "ground_truth": str(n),
        "check": lambda ans, n=n: str(n) in ans,
    })

    short_name = repo_name.split("/")[-1].lower() if "/" in repo_name else repo_name.lower()
    questions.append({
        "id": "Q02", "category": "summary",
        "question": "What is the name of the software repository?",
        "ground_truth": repo_name,
        "check": lambda ans, s=short_name: s in ans.lower(),
    })

    if first_bronze_num:
        questions.append({
            "id": "Q03", "category": "badge",
            "question": "When was the first bronze badge awarded?",
            "ground_truth": f"assessment {first_bronze_num}" + (f" / {first_bronze_date}" if first_bronze_date else ""),
            "check": lambda ans, num=first_bronze_num, dt=first_bronze_date: (
                str(num) in ans or _date_in_answer(ans, dt)
            ),
        })

    if first_silver_num:
        questions.append({
            "id": "Q04", "category": "badge",
            "question": "When was the first silver badge awarded?",
            "ground_truth": f"assessment {first_silver_num}" + (f" / {first_silver_date}" if first_silver_date else ""),
            "check": lambda ans, num=first_silver_num, dt=first_silver_date: (
                str(num) in ans or _date_in_answer(ans, dt)
            ),
        })

    questions.append({
        "id": "Q05", "category": "badge",
        "question": "What is the current badge level of the repository?",
        "ground_truth": latest_badge,
        "check": lambda ans, b=latest_badge: b.lower() in ans.lower() if b.lower() not in ("no badge","no_badge","unknown") else len(ans.strip()) > 10,
    })

    questions.append({
        "id": "Q06", "category": "regressions",
        "question": "Are there any quality regressions in the recent assessments?",
        "ground_truth": "regression info",
        "check": lambda ans: len(ans.strip()) > 20,
    })

    questions.append({
        "id": "Q07", "category": "assessment",
        "question": f"What badge was awarded in assessment {n}?",
        "ground_truth": latest_badge,
        "check": lambda ans, b=latest_badge: b.lower() in ans.lower() if b.lower() not in ("no badge","no_badge","unknown") else len(ans.strip()) > 10,
    })

    questions.append({
        "id": "Q08", "category": "badge_path",
        "question": "What criteria are missing for the repository to achieve a gold badge?",
        "ground_truth": "missing criteria list",
        "check": lambda ans: "QC." in ans or "missing" in ans.lower() or "gold" in ans.lower(),
    })

    questions.append({
        "id": "Q09", "category": "fix_hints",
        "question": "What should developers do to improve the quality score?",
        "ground_truth": "improvement recommendations",
        "check": lambda ans: len(ans.strip()) > 30,
    })

    if n >= 2:
        questions.append({
            "id": "Q10", "category": "compare",
            "question": f"Compare assessment 1 and assessment {n}. What changed?",
            "ground_truth": "comparison of first and last",
            "check": lambda ans: len(ans.strip()) > 30,
        })

    return questions


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's questions concisely "
    "and honestly. If you do not know something, say so."
)


def ask_ollama(base_url: str, model: str, question: str, repo_name: str,
               timeout: int = 60) -> tuple[str, float]:
    """Call Ollama directly — no tools, no provenance data."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content":
                f"Regarding the GitHub repository '{repo_name}': {question}"},
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 512},
    }
    t0 = time.perf_counter()
    resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    msg = resp.json().get("message", {})
    return msg.get("content", ""), latency


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model",      default="llama3.2")
    parser.add_argument("--out",        default="benchmark/results")
    parser.add_argument("--timeout",    default=60, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    prov_files = sorted(PROV_DIR.glob("*_prov_output.json"))
    prov_files = [p for p in prov_files
                  if "yProv4SQA" not in p.name
                  and "example" not in p.name
                  and "new.json" not in p.name]

    print(f"\nyProv4SQA No-Tools Baseline — {run_id}")
    print(f"Ollama: {args.ollama_url}   Model: {args.model}")
    print(f"Repos : {len(prov_files)}  (no tools, no provenance data)\n")

    all_rows = []
    repo_summaries = []
    csv_path = out_dir / f"no_tools_results_{run_id}.csv"
    log_path = out_dir / f"no_tools_log_{run_id}.jsonl"

    with open(csv_path, "w", newline="") as csv_f, open(log_path, "w") as log_f:
        writer = None

        for prov_path in prov_files:
            repo_label = prov_path.stem.replace("_prov_output", "")
            repo_name  = json.load(open(prov_path)).get("entity", {}).get(
                "ex:repository1", {}).get("ex:name", repo_label.replace("_", "/", 1))

            print(f"{'='*60}")
            print(f"Repo: {repo_label}  ({repo_name})")

            questions = build_questions(prov_path)
            print(f"Questions: {len(questions)}")
            print(f"{'ID':<5} {'Correct':<9} {'Latency':>8}  Question")
            print("-" * 60)

            repo_rows = []
            for q in questions:
                answer = error = ""
                latency = 0.0
                correct = False

                try:
                    answer, latency = ask_ollama(
                        args.ollama_url, args.model, q["question"],
                        repo_name, timeout=args.timeout
                    )
                    correct = bool(q["check"](answer))
                except Exception as e:
                    error = str(e)

                row = {
                    "repo":         repo_label,
                    "id":           q["id"],
                    "category":     q["category"],
                    "question":     q["question"],
                    "ground_truth": q["ground_truth"],
                    "correct":      correct,
                    "latency_s":    round(latency, 2),
                    "answer":       answer[:300],
                    "error":        error,
                }
                repo_rows.append(row)
                all_rows.append(row)

                if writer is None:
                    writer = csv.DictWriter(csv_f, fieldnames=list(row.keys()))
                    writer.writeheader()
                writer.writerow(row)
                csv_f.flush()
                log_f.write(json.dumps({**row, "answer_full": answer}) + "\n")
                log_f.flush()

                status = "✅" if correct else "❌"
                print(f"{q['id']:<5} {status}  {latency:>6.1f}s  {q['question'][:55]}")

            nq  = len(repo_rows)
            nc  = sum(1 for r in repo_rows if r["correct"])
            lats = [r["latency_s"] for r in repo_rows if not r["error"]]
            avg  = sum(lats) / len(lats) if lats else 0
            repo_summaries.append({
                "repo": repo_label, "questions": nq, "correct": nc,
                "accuracy_pct": round(100 * nc / nq, 1) if nq else 0,
                "latency_avg_s": round(avg, 2),
            })
            print(f"  → {nc}/{nq} correct ({100*nc//nq if nq else 0}%)  avg_lat={avg:.1f}s\n")

    print("\n" + "=" * 60)
    total_q = sum(s["questions"] for s in repo_summaries)
    total_c = sum(s["correct"]   for s in repo_summaries)
    all_lats = [r["latency_s"] for r in all_rows if not r["error"]]
    overall_avg = sum(all_lats) / len(all_lats) if all_lats else 0

    for s in repo_summaries:
        print(f"{s['repo']:<42} {s['correct']}/{s['questions']}={s['accuracy_pct']:>4}%  {s['latency_avg_s']:>5.1f}s")
    print("-" * 60)
    print(f"{'OVERALL':<42} {total_c}/{total_q}={100*total_c//total_q if total_q else 0:>3}%  {overall_avg:>5.1f}s")
    print("=" * 60)

    summary = {
        "run_id":               run_id,
        "model":                args.model,
        "mode":                 "no_tools_baseline",
        "repos":                len(repo_summaries),
        "total_questions":      total_q,
        "total_correct":        total_c,
        "overall_accuracy_pct": round(100 * total_c / total_q, 1) if total_q else 0,
        "overall_latency_avg_s": round(overall_avg, 2),
        "per_repo":             repo_summaries,
    }
    summary_path = out_dir / f"no_tools_summary_{run_id}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {csv_path}\n       {summary_path}")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_repo"}, indent=2))


if __name__ == "__main__":
    main()
