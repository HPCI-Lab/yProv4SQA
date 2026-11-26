"""
Completeness check — reads the itwinai Level-1 PROV-JSON document directly
and verifies that every expected node and relationship is present.

Outputs completeness_results.json in the same directory as this script.

Usage:
    python completeness_check.py [--prov PATH]

Default PROV path resolves automatically relative to this script.
"""

import json
import re
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent  # yProv4SQA/

DEFAULT_PROV = ROOT / "Provenance_documents" / "interTwin-eu_itwinai_prov_output.json"

EXPECTED = {
    "total_entities":               559,
    "assessment_entities":          279,
    "output_entities":              279,
    "repository_entities":            1,
    "total_activities":            2111,
    "total_agents":                   1,
    "total_wasGeneratedBy":        2111,
    "total_wasDerivedFrom":         558,
    "total_wasAttributedTo":          1,
    "partial_run_assessments":        9,
    # Reviewer also asks for counts by number of QC criteria per assessment
    "assessments_with_8_checks":    212,  # all 8 criteria present (includes QC.Uni era)
    "assessments_fewer_than_8":      67,  # 9 partial (1 crit) + 58 pre-QC.Uni (7 crits)
    "activities_QC.Acc":            270,
    "activities_QC.Doc":            270,
    "activities_QC.Lic":            270,
    "activities_QC.Met":            278,
    "activities_QC.Sec":            270,
    "activities_QC.Sty":            271,
    "activities_QC.Uni":            212,
    "activities_QC.Ver":            270,
}


def _strip_prefix(key: str) -> str:
    """Return the local name after the first colon, e.g. 'ex:foo1' → 'foo1'."""
    return key.split(":", 1)[-1]


def run_checks(prov_path: Path) -> dict:
    with open(prov_path, encoding="utf-8") as fh:
        prov = json.load(fh)

    entities   = prov.get("entity",           {})
    activities = prov.get("activity",          {})
    agents     = prov.get("agent",             {})
    wgb        = prov.get("wasGeneratedBy",    {})
    wdf        = prov.get("wasDerivedFrom",    {})
    wat        = prov.get("wasAttributedTo",   {})

    # --- entity sub-types ---------------------------------------------------
    n_assessment = sum(1 for k in entities if re.search(r"assessment\d+$", _strip_prefix(k)))
    n_output     = sum(1 for k in entities if re.search(r"output\d+$",     _strip_prefix(k)))
    n_repo       = sum(1 for k in entities if re.search(r"repository\d+$", _strip_prefix(k)))

    # --- partial runs -------------------------------------------------------
    n_partial = sum(
        1 for v in entities.values()
        if v.get("ex:is_partial_run") is True
    )

    # --- QC activities by criterion -----------------------------------------
    qc_counts: dict[str, int] = {}
    for k in activities:
        local = _strip_prefix(k)          # e.g. "qc_QC.Acc_1"
        parts = local.split("_")          # ["qc", "QC.Acc", "1"]
        if len(parts) >= 3 and parts[0] == "qc":
            criterion = parts[1]          # "QC.Acc"
            qc_counts[criterion] = qc_counts.get(criterion, 0) + 1

    # --- QC activities per assessment index ---------------------------------
    # Count how many QC activities exist for each assessment index
    per_assessment: dict[int, int] = {}
    for k in activities:
        local = _strip_prefix(k)          # e.g. "qc_QC.Acc_1"
        parts = local.split("_")
        if len(parts) >= 3 and parts[0] == "qc":
            try:
                idx = int(parts[-1])
            except ValueError:
                continue
            per_assessment[idx] = per_assessment.get(idx, 0) + 1

    n_exactly_8  = sum(1 for c in per_assessment.values() if c == 8)
    n_fewer_than_8 = sum(1 for c in per_assessment.values() if c < 8)

    # --- badge distribution -------------------------------------------------
    badge_dist: dict[str, int] = {}
    for v in entities.values():
        if "ex:badge_won" in v:
            bw = str(v["ex:badge_won"])
            badge_dist[bw] = badge_dist.get(bw, 0) + 1

    # --- partial run detail -------------------------------------------------
    partial_detail = []
    for k, v in entities.items():
        if v.get("ex:is_partial_run") is True:
            local = _strip_prefix(k)
            m = re.search(r"\d+$", local)
            idx = int(m.group()) if m else None
            # Find its QC activities
            qcs = []
            if idx is not None:
                for ak in activities:
                    al = _strip_prefix(ak)
                    parts = al.split("_")
                    if len(parts) >= 3 and parts[0] == "qc" and parts[-1] == str(idx):
                        criterion = parts[1]
                        pct = activities[ak].get("ex:percentage", "?")
                        qcs.append({"criterion": criterion, "percentage": pct})
            partial_detail.append({
                "entity_id":    k,
                "index":        idx,
                "commit_date":  v.get("ex:commit_date", ""),
                "qc_checks":    qcs,
            })
    partial_detail.sort(key=lambda x: x["index"] or 0)

    # --- assemble observed counts -------------------------------------------
    observed = {
        "total_entities":               len(entities),
        "assessment_entities":          n_assessment,
        "output_entities":              n_output,
        "repository_entities":          n_repo,
        "total_activities":             len(activities),
        "total_agents":                 len(agents),
        "total_wasGeneratedBy":         len(wgb),
        "total_wasDerivedFrom":         len(wdf),
        "total_wasAttributedTo":        len(wat),
        "partial_run_assessments":      n_partial,
        "assessments_with_8_checks":    n_exactly_8,
        "assessments_fewer_than_8":     n_fewer_than_8,
    }
    for crit, cnt in sorted(qc_counts.items()):
        observed[f"activities_{crit}"] = cnt

    # --- compare against expected -------------------------------------------
    checks = []
    all_pass = True
    for key, exp in EXPECTED.items():
        obs = observed.get(key, 0)
        status = "PASS" if obs == exp else "FAIL"
        if status == "FAIL":
            all_pass = False
        checks.append({
            "check":    key,
            "expected": exp,
            "observed": obs,
            "status":   status,
        })

    result = {
        "prov_document":        str(prov_path),
        "overall_status":       "PASS" if all_pass else "FAIL",
        "checks":               checks,
        "badge_distribution":   dict(sorted(badge_dist.items())),
        "partial_run_detail":   partial_detail,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prov", default=str(DEFAULT_PROV),
                        help="Path to the PROV-JSON document")
    args = parser.parse_args()

    prov_path = Path(args.prov)
    if not prov_path.exists():
        print(f"ERROR: PROV document not found: {prov_path}", file=sys.stderr)
        sys.exit(1)

    result = run_checks(prov_path)

    out_path = HERE / "completeness_results.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"Overall status : {result['overall_status']}")
    print(f"Checks         : {len(result['checks'])}")
    fails = [c for c in result["checks"] if c["status"] == "FAIL"]
    if fails:
        print(f"Failures       : {len(fails)}")
        for f in fails:
            print(f"  {f['check']}: expected {f['expected']}, observed {f['observed']}")
    else:
        print("All checks passed.")

    obs = {c["check"]: c["observed"] for c in result["checks"]}
    print(f"  Assessments with exactly 8 checks : {obs.get('assessments_with_8_checks', '?')}")
    print(f"  Assessments with fewer than 8     : {obs.get('assessments_fewer_than_8', '?')}")
    print(f"  Badge distribution: {result['badge_distribution']}")

    print(f"\nPartial runs ({len(result['partial_run_detail'])}):")
    for pr in result["partial_run_detail"]:
        qcs_str = ", ".join(f"{q['criterion']}={q['percentage']}" for q in pr["qc_checks"])
        print(f"  assessment{pr['index']:>3}  {pr['commit_date'][:10]}  {qcs_str}")

    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
