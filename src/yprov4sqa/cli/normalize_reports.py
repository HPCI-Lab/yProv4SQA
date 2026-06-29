import click
from yprov4sqa._fetcher import normalize_reports

@click.command()
@click.argument("repo_name")
@click.option("--src", default=None,
              help="Source folder. Defaults to ./{repo_name}_SQAaaS_reports_all")
@click.option("--dest", default=None,
              help="Output folder. Defaults to ./{repo_name}_SQAaaS_reports_normalized")
def main(repo_name: str, src: str, dest: str) -> None:
    """Normalize all SQAaaS reports for REPO_NAME to list-format schema.

    Converts old dict-format  {"repository": {...}}
    to new list-format        {"repository": [{...}]}
    so the provenance pipeline processes all reports without errors.

    \b
    Default folders (following fetch-all-reports naming convention):
      source : ./{repo_name}_SQAaaS_reports_all
      output : ./{repo_name}_SQAaaS_reports_normalized
    """
    source = src  or f"./{repo_name}_SQAaaS_reports_all"
    dest   = dest or f"./{repo_name}_SQAaaS_reports_normalized"
    normalize_reports(source, dest_folder=dest)

if __name__ == "__main__":
    main()
