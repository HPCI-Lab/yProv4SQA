"""
Timing wrapper for Level-1 PROV document generation.

Measures the time taken by process_all_files() (from retrieved JSON reports
to written PROV-JSON) for each available repository.  GitHub/SQAaaS API
download time is NOT included; we start from already-retrieved reports.

Each repository is timed 3 times; median is reported.

Outputs:
  timing_results.csv   — one row per (repo, run_index, time_s, doc_size_kb)
  timing_summary.md    — table per repository + machine details

Usage:
    python time_generation.py [--runs N]
"""

import csv
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from io import StringIO

HERE = Path(__file__).parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from yprov4sqa._provenance import process_all_files  # noqa: E402

# --- Repository → report folder mapping ------------------------------------
# Only repos with locally available reports are timed.
# "prov_doc" is the previously generated PROV document for size comparison.

BASE = ROOT

REPOS = [
    {
        "name":     "interTwin-eu/itwinai",
        "reports":  BASE / "artifacts" / "data" / "itwinai_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "interTwin-eu_itwinai_prov_output.json",
    },
    {
        "name":     "indigo-dc/udocker",
        "reports":  BASE / "results" / "udocker_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "indigo-dc_udocker_prov_output.json",
    },
    {
        "name":     "grycap/im",
        "reports":  BASE / "results" / "im_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "grycap_im_prov_output.json",
    },
    {
        "name":     "EOSC-synergy/sqaaas-assessment-action",
        "reports":  BASE / "results" / "sqaaas-assessment-action_SQAaaS_reports_norm",
        "prov_doc": BASE / "Provenance_documents" / "EOSC-synergy_sqaaas-assessment-action_prov_output.json",
    },
    {
        "name":     "SeisSol/SeisSol",
        "reports":  BASE / "results" / "SeisSol_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "SeisSol_SeisSol_prov_output.json",
    },
    {
        "name":     "grycap/oscar",
        "reports":  BASE / "results" / "oscar_SQAaaS_reports_norm",
        "prov_doc": BASE / "Provenance_documents" / "grycap_oscar_prov_output.json",
    },
    {
        "name":     "EOSC-synergy/FAIR_eva",
        "reports":  BASE / "results" / "FAIR_eva_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "EOSC-synergy_FAIR_eva_prov_output.json",
    },
    {
        "name":     "galaxyproject/galaxy",
        "reports":  BASE / "results" / "galaxy_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "galaxyproject_galaxy_prov_output.json",
    },
    {
        "name":     "EOSC-synergy/o3api",
        "reports":  BASE / "results" / "o3api_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "EOSC-synergy_o3api_prov_output.json",
    },
    {
        "name":     "indigo-dc/orchestrator",
        "reports":  BASE / "results" / "orchestrator_SQAaaS_reports",
        "prov_doc": BASE / "Provenance_documents" / "indigo-dc_orchestrator_prov_output.json",
    },
]

# Silence stdout during timed runs (process_all_files prints progress)
class _SuppressStdout:
    def __enter__(self):
        self._old = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        return self
    def __exit__(self, *_):
        sys.stdout.close()
        sys.stdout = self._old


def count_reports(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len([f for f in folder.iterdir() if f.suffix == ".json"])



def time_generation(repo: dict, n_runs: int = 3) -> dict:
    folder = repo["reports"]
    if not folder.exists() or count_reports(folder) == 0:
        return {"repo": repo["name"], "status": "SKIP", "reason": "no data"}

    n_reports = count_reports(folder)
    times: list[float] = []

    import tempfile
    # output dir for generated PROV (goes to <cwd>/Provenance_documents/)
    with tempfile.TemporaryDirectory() as tmp_dir:
        # process_all_files writes to "./Provenance_documents/" relative to cwd.
        # Run from a temp dir so the output goes there and not into the project.
        orig_dir = os.getcwd()
        os.chdir(tmp_dir)
        try:
            for run in range(n_runs):
                with _SuppressStdout():
                    t0 = time.perf_counter()
                    try:
                        process_all_files(str(folder))
                    except Exception as exc:
                        return {"repo": repo["name"], "status": "SKIP",
                                "reason": f"processing error: {exc}"}
                    t1 = time.perf_counter()
                times.append(t1 - t0)
        finally:
            os.chdir(orig_dir)

    # Existing document size (from pre-generated file)
    prov_doc = repo.get("prov_doc")
    doc_size_kb = round(prov_doc.stat().st_size / 1024, 1) if prov_doc and prov_doc.exists() else None

    median_s = round(statistics.median(times), 3)

    return {
        "repo":          repo["name"],
        "status":        "OK",
        "n_reports":     n_reports,
        "n_runs":        n_runs,
        "run_times_s":   [round(t, 3) for t in times],
        "median_s":      median_s,
        "min_s":         round(min(times), 3),
        "max_s":         round(max(times), 3),
        "doc_size_kb":   doc_size_kb,
    }


def machine_info() -> dict:
    info = {
        "os":           platform.platform(),
        "python":       platform.python_version(),
        "cpu":          "",
        "cpu_cores":    0,
        "ram_gb":       0.0,
    }
    try:
        with open("/proc/cpuinfo") as f:
            lines = f.readlines()
        model = next((l for l in lines if "model name" in l), "")
        info["cpu"] = model.split(":")[-1].strip() if model else "unknown"
        info["cpu_cores"] = sum(1 for l in lines if "processor" in l)
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = next((l for l in lines if "MemTotal" in l), "")
        kb = int(total.split()[1]) if total else 0
        info["ram_gb"] = round(kb / 1024 / 1024, 1)
    except Exception:
        pass
    return info


def write_csv(results: list[dict], path: Path):
    fieldnames = ["repo", "run", "time_s", "doc_size_kb", "n_reports"]
    rows = []
    for r in results:
        if r["status"] == "SKIP":
            rows.append({"repo": r["repo"], "run": "N/A", "time_s": "N/A",
                         "doc_size_kb": "N/A", "n_reports": 0})
            continue
        for i, t in enumerate(r["run_times_s"], start=1):
            rows.append({
                "repo":        r["repo"],
                "run":         i,
                "time_s":      t,
                "doc_size_kb": r["doc_size_kb"],
                "n_reports":   r["n_reports"],
            })
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(results: list[dict], machine: dict, path: Path):
    lines = ["# Level-1 Generation Timing", "",
             "## Machine Details", ""]
    lines += [
        f"| Property | Value |",
        f"|---|---|",
        f"| OS | {machine['os']} |",
        f"| Python | {machine['python']} |",
        f"| CPU | {machine['cpu']} |",
        f"| CPU cores | {machine['cpu_cores']} |",
        f"| RAM | {machine['ram_gb']} GB |",
        "",
        "## Level-1 Generation Time (3 runs, median)",
        "",
        "| Repository | Reports (raw) | Retained | Median (s) | Min (s) | Max (s) | Doc size (KB) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["status"] == "SKIP":
            lines.append(f"| {r['repo']} | N/A | N/A | N/A (no data) | | | |")
        else:
            # Approximate retained ≈ reports with unique commit_id (we don't
            # re-run dedup here; use n_reports as upper bound)
            lines.append(
                f"| {r['repo']} | {r['n_reports']} | see note | "
                f"{r['median_s']} | {r['min_s']} | {r['max_s']} | "
                f"{r['doc_size_kb'] or 'N/A'} |"
            )
    lines += [
        "",
        "Note: 'Retained' = raw reports minus duplicate commit SHAs.",
        "For itwinai: 380 raw → 279 retained (see accuracy check).",
        "",
        "## Upload Time",
        "",
        "Not measured: yProv service was not available during testing.",
        "",
        "## Neo4j Query Latency",
        "",
        "Not measured: Neo4j instance was not available during testing.",
        "",
        "## Level-2 Generation Time",
        "",
        "Not timed automatically: Level-2 generation requires live GitHub API calls",
        "to compare file trees between two commits.  Run the compare CLI manually:",
        "",
        "```",
        "time python -m yprov4sqa compare \\",
        "  Provenance_documents/interTwin-eu_itwinai_prov_output.json \\",
        "  <gindex_1> <gindex_2>",
        "```",
        "",
        "The fc45...fd9c → 4086...54f4 Level-2 document contains:",
        "  - 2 commit entities",
        "  - 282 file-change activities",
        "  - 2 agents (GitHub users)",
        "  - 282 wasDerivedFrom relations",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of timing runs per repository (default: 3)")
    args = parser.parse_args()

    machine = machine_info()
    print(f"Machine: {machine['cpu']}, {machine['cpu_cores']} cores, "
          f"{machine['ram_gb']} GB RAM, Python {machine['python']}")
    print()

    results = []
    for repo in REPOS:
        n = count_reports(repo["reports"])
        print(f"Timing {repo['name']} ({n} reports, {args.runs} runs)…")
        r = time_generation(repo, args.runs)
        results.append(r)
        if r["status"] == "SKIP":
            print(f"  → SKIP: {r['reason']}")
        else:
            print(f"  → median={r['median_s']}s  min={r['min_s']}s  max={r['max_s']}s  "
                  f"doc={r['doc_size_kb']}KB")

    # Save outputs
    csv_path = HERE / "timing_results.csv"
    md_path  = HERE / "timing_summary.md"
    json_path = HERE / "timing_results.json"

    write_csv(results, csv_path)
    write_summary_md(results, machine, md_path)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"machine": machine, "results": results}, fh, indent=2)

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
