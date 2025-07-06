"""yProv4SQA – provenance capture for SQAaaS assessments."""
from pathlib import Path
from typing import Optional


from ._fetcher    import fetch_assessment_reports as fetch_sqa_reports
from ._provenance import process_all_files        as generate_provenance
from ._compare    import main                     as compare_assessments
from ._graph      import main                     as provenance_to_svg

__all__ = ["fetch_sqa_reports", "generate_provenance",
           "compare_assessments", "provenance_to_svg"]

def quick_run(repo: str, *, token: Optional[str] = None) -> Path:
    """Download reports, build provenance, return path to JSON."""
    reports = fetch_sqa_reports(repo, token=token)
    return generate_provenance(reports)