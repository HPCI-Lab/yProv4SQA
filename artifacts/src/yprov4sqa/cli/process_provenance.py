
import click
from yprov4sqa._provenance import process_all_files

@click.command()
@click.argument("folder_path")
def main(folder_path: str) -> None:
    process_all_files(folder_path)

if __name__ == "__main__":
    main()