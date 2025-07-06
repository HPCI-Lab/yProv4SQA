import click
from yprov4sqa._graph import main as _graph_main

@click.command()
@click.argument("prov_file")
def main(prov_file: str) -> None:
    _graph_main([prov_file])   # backend expects a list

if __name__ == "__main__":
    main()