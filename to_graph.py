
import prov
import os
import prov.dot as dot
import prov.model

prov_file = "prov_output.json"

doc = prov.model.ProvDocument()
with open(prov_file, 'r') as f:
    doc = prov.model.ProvDocument.deserialize(f)

dot_filename = os.path.basename(prov_file).replace(".json", ".dot")
path_dot = os.path.join("./", dot_filename)
with open(path_dot, 'w') as prov_dot:
    prov_dot.write(dot.prov_to_dot(doc).to_string())

svg_filename = os.path.basename(prov_file).replace(".json", ".svg")
path_svg = os.path.join("./", svg_filename)
os.system(f"dot -Tsvg {path_dot} > {path_svg}")