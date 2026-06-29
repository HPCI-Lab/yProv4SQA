
import click
from yprov4sqa._provenance import process_all_files

@click.command()
@click.argument("folder_path")
@click.option("--repo", default=None,
              help="Canonical repo name (owner/repo) to keep. "
                   "Defaults to the most frequent repo found in the reports.")
def main(folder_path: str, repo: str) -> None:
    process_all_files(folder_path, repo_filter=repo)

if __name__ == "__main__":
    main()
