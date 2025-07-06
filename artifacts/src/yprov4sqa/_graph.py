import pathlib, sys
import prov, os, prov.dot as dot, prov.model

def main(argv=None):
    argv = argv or sys.argv[1:]
    prov_file = argv[0]

    out_dir = "Graph_outputs"
    pathlib.Path(out_dir).mkdir(exist_ok=True)

    doc = prov.model.ProvDocument()
    with open(prov_file, 'r') as f:
        doc = prov.model.ProvDocument.deserialize(f)

    dot_path = pathlib.Path(out_dir) / (pathlib.Path(prov_file).stem + ".dot")
    svg_path = pathlib.Path(out_dir) / (pathlib.Path(prov_file).stem + ".svg")

    dot_path.write_text(dot.prov_to_dot(doc).to_string())
    os.system(f"dot -Tsvg {dot_path} > {svg_path}")

if __name__ == "__main__":
    main()