import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

BASE_DIR     = Path(__file__).parent.parent.parent
PROV_DIR     = BASE_DIR / "Provenance_documents"
BENCH_SCRIPT = Path(__file__).parent / "run_benchmark_all_repos.py"


def restart_server(model: str, hints: bool, port: int = 5000):
    subprocess.run(["pkill", "-f", "prov-chat"], capture_output=True)
    time.sleep(2)

    prov_doc = str(PROV_DIR / "interTwin-eu_itwinai_prov_output.json")
    env = os.environ.copy()
    if not hints:
        env["DISABLE_TOOL_HINTS"] = "1"
    elif "DISABLE_TOOL_HINTS" in env:
        del env["DISABLE_TOOL_HINTS"]

    proc = subprocess.Popen(
        ["prov-chat", prov_doc, "--web", "--port", str(port), "--model", model],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import requests
    print(f"  Waiting for server (hints={'ON' if hints else 'OFF'})...", end="", flush=True)
    for _ in range(30):
        try:
            requests.get(f"http://localhost:{port}/api/app-status", timeout=2)
            print(" ready.")
            return proc
        except Exception:
            time.sleep(2)
            print(".", end="", flush=True)
    print(" (timeout)")
    return proc


def run_bench(url: str, model: str, out_dir: Path, label: str, timeout: int) -> dict:
    result = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT),
         "--url", url, "--model", f"{model}_{label}",
         "--out", str(out_dir), "--timeout", str(timeout)],
        capture_output=True, text=True,
    )
    lines = result.stdout.strip().splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "}":
            try:
                summary = json.loads("\n".join(lines[i - 10:i + 1]))
                return summary
            except Exception:
                pass
    summaries = sorted(out_dir.glob("all_repos_summary_*.json"))
    if summaries:
        return json.loads(summaries[-1].read_text())
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     default="http://localhost:5000")
    parser.add_argument("--model",   default="llama3.2")
    parser.add_argument("--out",     default="benchmark/results/ablation")
    parser.add_argument("--timeout", default=120, type=int)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {}

    for hints in [True, False]:
        label = "with_hints" if hints else "no_hints"
        print(f"\n{'='*60}")
        print(f"  Running: {label.upper()}")
        print(f"{'='*60}")

        proc = restart_server(args.model, hints)
        time.sleep(2)

        import requests
        try:
            requests.post(f"{args.url}/api/chat",
                          json={"question": "How many assessments?"},
                          timeout=60)
            requests.post(f"{args.url}/api/reset", timeout=10)
        except Exception:
            pass

        summary = run_bench(args.url, args.model, out_dir, label, args.timeout)
        results[label] = summary
        proc.terminate()

    print(f"\n{'='*70}")
    print(f"  ABLATION RESULTS — Model: {args.model}")
    print(f"{'='*70}")
    print(f"{'Condition':<20} {'Task Acc':>10} {'Tool Acc':>10} {'Latency':>10}")
    print("-" * 55)
    for label, s in results.items():
        print(f"{label:<20} {s.get('overall_accuracy_pct',0):>9.1f}%"
              f" {s.get('overall_tool_acc_pct',0):>9.1f}%"
              f" {s.get('overall_latency_avg_s',0):>9.2f}s")
    print("=" * 55)

    output = {
        "run_id": run_id,
        "model": args.model,
        "results": results,
    }
    out_path = out_dir / f"ablation_summary_{run_id}.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
