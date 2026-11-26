"""
Accuracy check — verifies that every criterion score stored in the
itwinai Level-1 PROV-JSON document matches the score in the original
raw SQAaaS report.

Steps:
  1. Load the 380 raw reports from artifacts/data/itwinai_SQAaaS_reports/.
  2. Apply the same deduplication as the pipeline (by source commit SHA,
     keeping the latest report per commit) to arrive at the 279 retained
     assessments.  The deduplication helpers are imported directly from
     yprov4sqa._provenance; only the high-level process_all_files() is
     skipped because it also writes the PROV document.
  3. For each retained assessment (gindex 1..N), extract from the raw
     report the coverage percentage and validity flag for each QC criterion.
  4. Look up the matching activity ex:qc_{criterion}_{gindex} in the
     PROV document and read ex:percentage and ex:output.
  5. Compare every (commit_id, criterion) pair.

Outputs:
  accuracy_results.csv   — one row per (commit_id, criterion, raw_score,
                            prov_score, match)
  accuracy_summary.json  — total pairs, matches, mismatches, raw-only,
                            prov-only

Usage:
    python accuracy_check.py [--prov PATH] [--reports DIR]
"""

import csv
import json
import os
import re
import argparse
import sys
from pathlib import Path

HERE    = Path(__file__).parent
ROOT    = HERE.parent.parent
DEFAULT_PROV    = ROOT / "Provenance_documents" / "interTwin-eu_itwinai_prov_output.json"
DEFAULT_REPORTS = ROOT / "artifacts" / "data" / "itwinai_SQAaaS_reports"

# ---------------------------------------------------------------------------
# Import helpers from the package (no re-implementation)
# process_all_files() cannot be imported directly because it also writes the
# PROV document; we import the stateless helpers and replicate only the
# file-ordering and deduplication loop (≈ 20 lines of logic from
# _provenance.process_all_files).
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "src"))
try:
    from yprov4sqa._provenance import load_json, _unwrap, _FNAME_DATE_RE
except ImportError as exc:
    sys.exit(f"Cannot import from yprov4sqa: {exc}\n"
             f"Run from the yProv4SQA root or set PYTHONPATH=src.")


# ---------------------------------------------------------------------------
# Deduplication — same logic as _provenance.process_all_files()
# ---------------------------------------------------------------------------

_RUN_IDX_RE = re.compile(r"^report_(\d+)_")


def _sort_key(fp: str):
    fname = os.path.basename(fp)
    if _FNAME_DATE_RE.match(fname):
        return (fname, 0)
    m = _RUN_IDX_RE.match(fname)
    if m:
        return ("", int(m.group(1)))
    return (fname, 0)


def get_retained_files(reports_dir: Path) -> list[str]:
    """
    Return the deduplicated, chronologically-ordered list of report file
    paths — identical to the input list that process_all_files() would use.
    """
    all_files = sorted(
        [str(reports_dir / f)
         for f in os.listdir(reports_dir) if f.endswith(".json")],
        key=_sort_key,
    )

    file_meta: list = []
    for fp in all_files:
        data = load_json(fp)
        repo_list = data.get("repository", [])
        if not repo_list:
            continue
        repo_data  = repo_list[0] if isinstance(repo_list, list) else repo_list
        repo_name  = repo_data.get("name", "")
        commit_id  = _unwrap(repo_data.get("commit_id", ""))
        file_meta.append((fp, repo_name, commit_id))

    commit_to_file: dict[str, str] = {}
    no_commit_files: list[str]     = []
    for fp, _repo_name, commit_id in file_meta:
        if commit_id:
            commit_to_file[commit_id] = fp  # last write = latest chronologically
        else:
            no_commit_files.append(fp)

    retained = sorted(commit_to_file.values(), key=_sort_key) + no_commit_files
    return retained


# ---------------------------------------------------------------------------
# Score extraction helpers
# ---------------------------------------------------------------------------

def raw_score(qc_data: dict) -> str:
    """Return the percentage string from a raw QC block, e.g. '75%'."""
    pct = qc_data.get("coverage", {}).get("percentage", 0)
    return f"{pct}%"


def raw_valid(qc_data: dict) -> bool:
    return bool(qc_data.get("valid", False))


def prov_score(activity: dict) -> str:
    return activity.get("ex:percentage", "")


def prov_valid(activity: dict) -> bool:
    return bool(activity.get("ex:output", False))


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def run_accuracy_check(prov_path: Path, reports_dir: Path) -> tuple[list, dict]:
    # Load PROV document
    with open(prov_path, encoding="utf-8") as fh:
        prov = json.load(fh)
    activities = prov.get("activity", {})

    # Build a lookup: (gindex, criterion) → activity dict
    # Key format: "ex:qc_{criterion}_{gindex}"
    act_lookup: dict[tuple[int, str], dict] = {}
    for k, v in activities.items():
        local = k.split(":", 1)[-1]        # strip "ex:"
        parts = local.split("_")           # ["qc", "QC.Acc", "1"]
        if len(parts) >= 3 and parts[0] == "qc":
            try:
                gindex = int(parts[-1])
            except ValueError:
                continue
            criterion = parts[1]
            act_lookup[(gindex, criterion)] = v

    # Retained files in pipeline order
    retained = get_retained_files(reports_dir)
    n_retained = len(retained)

    rows: list[dict] = []
    raw_pairs:  set[tuple[str, str]] = set()
    prov_pairs: set[tuple[str, str]] = set()

    for gindex, fp in enumerate(retained, start=1):
        data = load_json(fp)
        repo_list = data.get("repository", [])
        if not repo_list:
            continue
        repo_data = repo_list[0] if isinstance(repo_list, list) else repo_list
        commit_id = str(_unwrap(repo_data.get("commit_id", "")) or "")

        report = data.get("report", {})

        for criterion, qc_data in report.items():
            r_score = raw_score(qc_data)
            r_valid = raw_valid(qc_data)
            raw_pairs.add((commit_id, criterion))

            act = act_lookup.get((gindex, criterion))
            if act is None:
                rows.append({
                    "gindex":     gindex,
                    "commit_id":  commit_id,
                    "criterion":  criterion,
                    "raw_score":  r_score,
                    "raw_valid":  r_valid,
                    "prov_score": "",
                    "prov_valid": "",
                    "match":      False,
                    "note":       "activity missing in PROV",
                })
                continue

            p_score = prov_score(act)
            p_valid = prov_valid(act)
            match   = (r_score == p_score) and (r_valid == p_valid)
            prov_pairs.add((commit_id, criterion))

            rows.append({
                "gindex":     gindex,
                "commit_id":  commit_id,
                "criterion":  criterion,
                "raw_score":  r_score,
                "raw_valid":  r_valid,
                "prov_score": p_score,
                "prov_valid": p_valid,
                "match":      match,
                "note":       "" if match else f"score: {r_score}≠{p_score}" if r_score != p_score else f"valid: {r_valid}≠{p_valid}",
            })

    # Pairs present only in PROV (not in any retained raw report)
    prov_only_pairs = set()
    for (gi, crit), _act in act_lookup.items():
        # Find commit_id for this gindex
        if gi <= len(retained):
            data = load_json(retained[gi - 1])
            repo_list = data.get("repository", [])
            if repo_list:
                rd = repo_list[0] if isinstance(repo_list, list) else repo_list
                cid = str(_unwrap(rd.get("commit_id", "")) or "")
                if (cid, crit) not in raw_pairs:
                    prov_only_pairs.add((cid, crit))

    matches    = sum(1 for r in rows if r["match"])
    mismatches = sum(1 for r in rows if not r["match"] and r["prov_score"] != "")
    raw_only   = sum(1 for r in rows if r["prov_score"] == "")

    summary = {
        "prov_document":        str(prov_path),
        "reports_folder":       str(reports_dir),
        "total_raw_reports":    380,
        "retained_reports":     n_retained,
        "total_pairs":          len(rows),
        "matches":              matches,
        "mismatches":           mismatches,
        "raw_only":             raw_only,
        "prov_only":            len(prov_only_pairs),
        "overall_status":       "PASS" if mismatches == 0 and raw_only == 0 and len(prov_only_pairs) == 0 else "FAIL",
    }
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prov",    default=str(DEFAULT_PROV),    help="PROV-JSON path")
    parser.add_argument("--reports", default=str(DEFAULT_REPORTS), help="Raw reports folder")
    args = parser.parse_args()

    prov_path   = Path(args.prov)
    reports_dir = Path(args.reports)

    for p in (prov_path, reports_dir):
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            sys.exit(1)

    print("Running accuracy check …")
    rows, summary = run_accuracy_check(prov_path, reports_dir)

    # --- Write CSV ----------------------------------------------------------
    csv_path = HERE / "accuracy_results.csv"
    fieldnames = ["gindex", "commit_id", "criterion", "raw_score", "raw_valid",
                  "prov_score", "prov_valid", "match", "note"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Write JSON summary -------------------------------------------------
    json_path = HERE / "accuracy_summary.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"Overall status  : {summary['overall_status']}")
    print(f"Retained reports: {summary['retained_reports']}")
    print(f"Total pairs     : {summary['total_pairs']}")
    print(f"Matches         : {summary['matches']}")
    print(f"Mismatches      : {summary['mismatches']}")
    print(f"Raw-only        : {summary['raw_only']}")
    print(f"PROV-only       : {summary['prov_only']}")
    if summary["mismatches"] > 0:
        print("\nMismatch details (first 20):")
        shown = 0
        for r in rows:
            if not r["match"] and r["prov_score"] != "":
                print(f"  assessment{r['gindex']:>3}  {r['criterion']}  "
                      f"raw={r['raw_score']}/{r['raw_valid']}  "
                      f"prov={r['prov_score']}/{r['prov_valid']}")
                shown += 1
                if shown >= 20:
                    break
    print(f"\nResults saved → {csv_path}")
    print(f"Summary  saved → {json_path}")


if __name__ == "__main__":
    main()
