import click
from yprov4sqa._fetcher import fetch_all_reports_unfiltered

@click.command()
@click.argument("repo_name")
@click.option("--token", envvar="GITHUB_TOKEN", default=None,
              help="GitHub personal access token (or set GITHUB_TOKEN env var).")
def main(repo_name: str, token: str) -> None:
    """Download ALL SQAaaS assessment reports for REPO_NAME with no filtering.

    Saves every report regardless of internal format (list or dict schema,
    missing fields, etc.). Useful for analysing the full history including
    old-format reports that fetch-sqa-reports skips.
    """
    fetch_all_reports_unfiltered(repo_name, token=token)

if __name__ == "__main__":
    main()
