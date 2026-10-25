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
        ans_l = ans.lower()
        return (mon_name in ans_l and day_int in ans and year in ans)
    except Exception:
        return False

PROV_DIR = Path(__file__).parent.parent.parent / "Provenance_documents"


def build_questions(prov_path: Path) -> list[dict]:
    with open(prov_path) as f:
        d = json.load(f)

    entities   = d.get("entity",   {})
    activities = d.get("activity", {})

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

    badge_counts = {}
    for k in outputs:
        b = entities[k].get("ex:badge_won", "")
        if b and b.lower() not in ("no badge", "no_badge", ""):
            badge_counts[b] = badge_counts.get(b, 0) + 1

    first_bronze_num = None
    first_bronze_date = None
    for k in outputs:
        if entities[k].get("ex:badge_won") == "bronze":
            first_bronze_num = int(k.replace("ex:output", ""))
            raw = entities[k].get("ex:Issued_On:str", "")
            first_bronze_date = raw[:10] if raw else None
            break

    first_silver_num = None
    first_silver_date = None
    for k in outputs:
        if entities[k].get("ex:badge_won") == "silver":
            first_silver_num = int(k.replace("ex:output", ""))
            raw = entities[k].get("ex:Issued_On:str", "")
            first_silver_date = raw[:10] if raw else None
            break

    latest_badge = entities.get(outputs[-1], {}).get("ex:badge_won", "unknown") if outputs else "unknown"

    last_idx = n
    qc_latest = {}
    for k, v in activities.items():
        m = re.match(r"ex:qc_(QC\.\w+)_" + str(last_idx) + r"$", k)
        if m:
            qc_latest[m.group(1)] = v.get("ex:percentage", "?")

    questions = []

    questions.append({
        "id": "Q01", "category": "summary",
        "expected_tool": "get_summary",
        "question": "How many assessments are in the provenance document?",
        "ground_truth": str(n),
        "check": lambda ans, n=n: str(n) in ans,
    })

    short_name = repo_name.split("/")[-1].lower() if "/" in repo_name else repo_name.lower()
    questions.append({
        "id": "Q02", "category": "summary",
        "expected_tool": "get_summary",
        "question": "What is the name of the software repository?",
        "ground_truth": repo_name,
        "check": lambda ans, s=short_name: s in ans.lower(),
    })

    if first_bronze_num:
        questions.append({
            "id": "Q03", "category": "badge",
            "expected_tool": "get_badge_history",
            "question": "When was the first bronze badge awarded?",
            "ground_truth": f"assessment {first_bronze_num}" + (f" / {first_bronze_date}" if first_bronze_date else ""),
            "check": lambda ans, num=first_bronze_num, dt=first_bronze_date: (
                str(num) in ans or _date_in_answer(ans, dt)
            ),
        })

    if first_silver_num:
        questions.append({
            "id": "Q04", "category": "badge",
            "expected_tool": "get_badge_history",
            "question": "When was the first silver badge awarded?",
            "ground_truth": f"assessment {first_silver_num}" + (f" / {first_silver_date}" if first_silver_date else ""),
            "check": lambda ans, num=first_silver_num, dt=first_silver_date: (
                str(num) in ans or _date_in_answer(ans, dt)
            ),
        })

    questions.append({
        "id": "Q05", "category": "badge",
        "expected_tool": ["get_badge_history", "get_summary"],
        "question": "What is the current badge level of the repository?",
        "ground_truth": latest_badge,
        "check": lambda ans, b=latest_badge: b.lower() in ans.lower() if b.lower() not in ("no badge", "no_badge", "unknown") else len(ans.strip()) > 10,
    })

    questions.append({
        "id": "Q06", "category": "regressions",
        "expected_tool": "get_regressions",
        "question": "Are there any quality regressions in the recent assessments?",
        "ground_truth": "regression info",
        "check": lambda ans: len(ans.strip()) > 20,
    })

    questions.append({
        "id": "Q07", "category": "assessment",
        "expected_tool": "get_assessment",
        "question": f"What badge was awarded in assessment {n}?",
        "ground_truth": latest_badge,
        "check": lambda ans, b=latest_badge: b.lower() in ans.lower() if b.lower() not in ("no badge", "no_badge", "unknown") else len(ans.strip()) > 10,
    })

    questions.append({
        "id": "Q08", "category": "badge_path",
        "expected_tool": "get_badge_path",
        "question": "What criteria are missing for the repository to achieve a gold badge?",
        "ground_truth": "missing criteria list",
        "check": lambda ans: "QC." in ans or "missing" in ans.lower() or "gold" in ans.lower(),
    })

    questions.append({
        "id": "Q09", "category": "fix_hints",
        "expected_tool": ["get_fix_hints", "get_tool_failures"],
        "question": "What should developers do to improve the quality score?",
        "ground_truth": "improvement recommendations",
        "check": lambda ans: len(ans.strip()) > 30,
    })

    if n >= 2:
        questions.append({
            "id": "Q10", "category": "compare",
            "expected_tool": "compare_assessments",
            "question": f"Compare assessment 1 and assessment {n}. What changed?",
            "ground_truth": "comparison of first and last",
            "check": lambda ans: len(ans.strip()) > 30,
        })

    return questions


def switch_doc(base_url: str, prov_path: Path, model: str | None = None) -> bool:
    # Server only accepts paths relative to its own working directory.
    # Try relative first; fall back to filename-only inside Provenance_documents/.
    rel = f"Provenance_documents/{prov_path.name}"
    payload: dict = {"path": rel}
    if model:
        payload["model"] = model
    resp = requests.post(
        f"{base_url}/api/load-saved",
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        return False
    data = resp.json()
    return data.get("status") == "ok" or data.get("loaded") is True


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
    parser.add_argument("--url",     default="http://localhost:5000")
    parser.add_argument("--out",     default="benchmark/results")
    parser.add_argument("--model",   default="llama3.2")
    parser.add_argument("--timeout", default=120, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_rows = []
    repo_summaries = []

    prov_files = sorted(PROV_DIR.glob("*_prov_output.json"))
    prov_files = [p for p in prov_files if "yProv4SQA" not in p.name and "example" not in p.name and "new.json" not in p.name]

    print(f"\nyProv4SQA Multi-Repo Benchmark — {run_id}")
    print(f"Target: {args.url}   Model: {args.model}")
    print(f"Repos : {len(prov_files)}\n")

    master_csv = out_dir / f"all_repos_results_{run_id}.csv"
    master_log = out_dir / f"all_repos_log_{run_id}.jsonl"

    with open(master_csv, "w", newline="") as csv_f, open(master_log, "w") as log_f:
        writer = None

        for prov_path in prov_files:
            repo_label = prov_path.stem.replace("_prov_output", "")
            print(f"{'='*60}")
            print(f"Repo: {repo_label}")

            if not switch_doc(args.url, prov_path, model=args.model or None):
                print(f"  ERROR: could not load {prov_path.name} — skipping")
                continue

            time.sleep(1)

            questions = build_questions(prov_path)
            print(f"Questions: {len(questions)}")
            print(f"{'ID':<5} {'Correct':<9} {'Latency':>8}  Question")
            print("-" * 60)

            repo_rows = []
            for q in questions:
                reset_agent(args.url)
                error = answer = ""
                tools_called = []
                latency = 0.0
                correct = tool_match = False

                try:
                    result, latency = ask_agent(args.url, q["question"], timeout=args.timeout)
                    answer       = result.get("answer", "")
                    tool_calls   = result.get("tool_calls", [])
                    tools_called = [tc.get("tool", tc.get("name", "")) for tc in tool_calls]
                    expected     = q["expected_tool"]
                    accepted     = expected if isinstance(expected, list) else [expected]
                    tool_match   = any(t in tools_called for t in accepted)
                    correct      = evaluate(answer, q["check"])
                except Exception as e:
                    error = str(e)

                row = {
                    "repo":          repo_label,
                    "id":            q["id"],
                    "category":      q["category"],
                    "question":      q["question"],
                    "expected_tool": "; ".join(q["expected_tool"]) if isinstance(q["expected_tool"], list) else q["expected_tool"],
                    "tools_called":  "; ".join(tools_called),
                    "tool_match":    tool_match,
                    "correct":       correct,
                    "latency_s":     round(latency, 2),
                    "answer":        answer[:300],
                    "ground_truth":  q["ground_truth"],
                    "error":         error,
                }
                repo_rows.append(row)
                all_rows.append(row)

                if writer is None:
                    writer = csv.DictWriter(csv_f, fieldnames=list(row.keys()))
                    writer.writeheader()
                writer.writerow(row)
                csv_f.flush()

                log_f.write(json.dumps({**row, "answer_full": answer,
                    "tool_calls_full": result.get("tool_calls", []) if not error else []}) + "\n")
                log_f.flush()

                status = "✅" if correct else "❌"
                print(f"{q['id']:<5} {status}  {latency:>6.1f}s  {q['question'][:55]}")

            nq  = len(repo_rows)
            nc  = sum(1 for r in repo_rows if r["correct"])
            ntm = sum(1 for r in repo_rows if r["tool_match"])
            lats = [r["latency_s"] for r in repo_rows if not r["error"]]
            avg  = sum(lats) / len(lats) if lats else 0
            repo_summaries.append({
                "repo": repo_label, "questions": nq,
                "correct": nc, "tool_match": ntm,
                "accuracy_pct": round(100 * nc / nq, 1) if nq else 0,
                "tool_acc_pct": round(100 * ntm / nq, 1) if nq else 0,
                "latency_avg_s": round(avg, 2),
            })
            print(f"  → {nc}/{nq} correct ({100*nc//nq}%)  tool_acc={100*ntm//nq}%  avg_lat={avg:.1f}s\n")

    print("\n" + "=" * 70)
    print(f"{'Repo':<40} {'Correct':>8} {'Tool%':>7} {'Lat(s)':>7}")
    print("-" * 70)
    for s in repo_summaries:
        print(f"{s['repo']:<40} {s['correct']}/{s['questions']}={s['accuracy_pct']:>4}%  {s['tool_acc_pct']:>4}%  {s['latency_avg_s']:>5.1f}s")

    total_q = sum(s["questions"] for s in repo_summaries)
    total_c = sum(s["correct"]   for s in repo_summaries)
    total_t = sum(s["tool_match"] for s in repo_summaries)
    all_lats = [r["latency_s"] for r in all_rows if not r["error"]]
    overall_avg = sum(all_lats) / len(all_lats) if all_lats else 0

    print("-" * 70)
    print(f"{'OVERALL':<40} {total_c}/{total_q}={100*total_c//total_q:>3}%  {100*total_t//total_q:>3}%  {overall_avg:>5.1f}s")
    print("=" * 70)

    summary = {
        "run_id": run_id, "model": args.model,
        "repos": len(repo_summaries),
        "total_questions": total_q,
        "total_correct": total_c,
        "total_tool_match": total_t,
        "overall_accuracy_pct": round(100 * total_c / total_q, 1),
        "overall_tool_acc_pct": round(100 * total_t / total_q, 1),
        "overall_latency_avg_s": round(overall_avg, 2),
        "per_repo": repo_summaries,
    }
    summary_path = out_dir / f"all_repos_summary_{run_id}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {master_csv}\n       {master_log}\n       {summary_path}")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_repo"}, indent=2))


if __name__ == "__main__":
    main()
