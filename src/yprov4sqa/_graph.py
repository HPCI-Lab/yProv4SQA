"""
yprov4sqa/_graph.py
===================
Generate DOT + SVG graph from a W3C PROV-JSON document.

Bypasses prov.dot / pydot entirely — generates DOT source directly from
the JSON so no pydot installation is needed.  Renders via subprocess with
a LIST argument (not a shell string) so the dot binary is found correctly
inside conda/venv environments where shutil.which may fail.
"""

import json
import pathlib
import re
import subprocess
import sys


def prov_to_dot_source(prov_doc: dict) -> str:
    """
    Generate a DOT graph string directly from a W3C PROV-JSON document.
    No dependency on pydot or the graphviz python package.
    """

    def short(key: str) -> str:
        s = key.replace('ex:', '').replace('_:', '')
        return (s[:32] + '…') if len(s) > 32 else s

    def nid(key: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_]', '_', key)

    lines = [
        'digraph provenance {',
        '  rankdir=LR;',
        '  graph [fontname="Helvetica" bgcolor="#fafaf7"];',
        '  node  [fontname="Helvetica" fontsize=11];',
        '  edge  [fontsize=9];',
        '',
    ]

    # Agents — ellipse, steel blue
    for k in prov_doc.get('agent', {}):
        lines.append(
            f'  {nid(k)} [label="{short(k)}" shape=ellipse '
            f'style=filled fillcolor="#4a8fc1" fontcolor=white];'
        )

    # Entities — rounded box, gold
    for k in prov_doc.get('entity', {}):
        lines.append(
            f'  {nid(k)} [label="{short(k)}" shape=box '
            f'style="rounded,filled" fillcolor="#f5d76e" fontcolor=black];'
        )

    # Activities — diamond, green
    for k, v in prov_doc.get('activity', {}).items():
        label = v.get('ex:filename', short(k))
        label = (label[:28] + '…') if len(label) > 28 else label
        lines.append(
            f'  {nid(k)} [label="{label}" shape=diamond '
            f'style=filled fillcolor="#5cba7d" fontcolor=white];'
        )

    lines.append('')

    # wasGeneratedBy: activity → entity  (dashed)
    for v in prov_doc.get('wasGeneratedBy', {}).values():
        e = nid(v.get('prov:entity',   ''))
        a = nid(v.get('prov:activity', ''))
        if e and a:
            lines.append(f'  {a} -> {e} [style=dashed label="wasGeneratedBy"];')

    # wasDerivedFrom: usedEntity → generatedEntity
    for v in prov_doc.get('wasDerivedFrom', {}).values():
        gen  = nid(v.get('prov:generatedEntity', ''))
        used = nid(v.get('prov:usedEntity',      ''))
        if gen and used:
            lines.append(f'  {used} -> {gen} [label="wasDerivedFrom"];')

    # wasAttributedTo: agent → entity  (dotted)
    for v in prov_doc.get('wasAttributedTo', {}).values():
        e     = nid(v.get('prov:entity', ''))
        agent = nid(v.get('prov:agent',  ''))
        if e and agent:
            lines.append(f'  {agent} -> {e} [style=dotted label="wasAttributedTo"];')

    # wasAssociatedWith
    for v in prov_doc.get('wasAssociatedWith', {}).values():
        a     = nid(v.get('prov:activity', ''))
        agent = nid(v.get('prov:agent',    ''))
        if a and agent:
            lines.append(f'  {agent} -> {a} [style=dotted label="wasAssociatedWith"];')

    lines.append('}')
    return '\n'.join(lines)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: json2graph [--dot-only] <prov-file>")
        return 2

    dot_only = '--dot-only' in argv
    if dot_only:
        argv = [a for a in argv if a != '--dot-only']

    if not argv:
        print("Error: provenance file required")
        return 2

    prov_file = argv[0]
    out_dir   = pathlib.Path("Graph_outputs")
    out_dir.mkdir(exist_ok=True)

    # Load JSON
    try:
        with open(prov_file, encoding='utf-8') as f:
            prov_doc = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {prov_file}")
        return 2
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        return 3

    stem     = pathlib.Path(prov_file).stem
    dot_path = out_dir / (stem + ".dot")
    svg_path = out_dir / (stem + ".svg")

    # Generate DOT source — no pydot needed
    dot_src = prov_to_dot_source(prov_doc)
    dot_path.write_text(dot_src, encoding='utf-8')
    print(f"DOT file  → {dot_path}  ({len(dot_src.splitlines())} lines)")

    if dot_only:
        print("(SVG rendering skipped — --dot-only)")
        return 0

    # Render SVG — use subprocess LIST form (works in conda/venv without shutil.which)
    try:
        with open(svg_path, 'wb') as svg_fh:
            subprocess.run(
                ['dot', '-Tsvg', str(dot_path)],
                stdout=svg_fh,
                check=True,
                stderr=subprocess.PIPE,
            )
        print(f"SVG file  → {svg_path}")
    except FileNotFoundError:
        print("Error: Graphviz 'dot' binary not found.")
        print("  Install:  sudo apt install graphviz")
        print("  Or conda: conda install -c conda-forge graphviz")
        print(f"  Manual:   dot -Tsvg {dot_path} > {svg_path}")
        return 4
    except subprocess.CalledProcessError as e:
        print(f"Error: Graphviz failed: {e.stderr.decode()[:200]}")
        return 5

    return 0


if __name__ == '__main__':
    sys.exit(main())