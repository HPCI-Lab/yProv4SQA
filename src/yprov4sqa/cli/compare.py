import sys, click
from yprov4sqa._compare import main as _compare_main

@click.command()
@click.argument("json_path")
@click.argument("id1", type=int)
@click.argument("id2", type=int)
def main(json_path, id1, id2):
    # mimic the old command-line args
    sys.argv = ["compare", json_path, str(id1), str(id2)]
    _compare_main()

if __name__ == "__main__":
    main()