import click
from yprov4sqa._fetcher import fetch_assessment_reports

@click.command()
@click.argument("repo_name")
def main(repo_name: str) -> None:
    fetch_assessment_reports(repo_name)

if __name__ == "__main__":
    main()