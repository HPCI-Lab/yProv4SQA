"""
Standalone normalization script for old-format SQAaaS JSON reports.

Old format: "repository" field is a JSON object  {"repository": {...}}
New format: "repository" field is a JSON array   {"repository": [{...}]}

The yProv4SQA provenance pipeline expects the new (list) format.
Two repositories had reports in the old format:
  - EOSC-synergy/sqaaas-assessment-action  (28 of 39 files)
  - grycap/oscar                            (1 of 7 files)

Pre-normalized copies are already in the _SQAaaS_reports_norm folders;
this script reproduces that normalization from scratch.

Usage:
    python normalize_reports.py <source_folder> [--dest <dest_folder>]

If --dest is omitted the normalized files are written back to <source_folder>
(in-place conversion).  When a file is already in the new format it is
copied without modification (or left unchanged for in-place mode).

Requirements: Python 3.6+, standard library only.
"""

import argparse
import json
import os
import sys


def normalize_folder(source_folder: str, dest_folder: str) -> dict:
    """Normalize all JSON reports in source_folder and write to dest_folder.

    Returns a stats dict: {converted, already_ok, skipped, total}.
    """
    if not os.path.isdir(source_folder):
        sys.exit(f"Error: source folder not found: {source_folder}")

    if dest_folder != source_folder:
        os.makedirs(dest_folder, exist_ok=True)

    files = sorted(f for f in os.listdir(source_folder) if f.endswith(".json"))
    stats = {"converted": 0, "already_ok": 0, "skipped": 0, "total": len(files)}

    for fname in files:
        src_path  = os.path.join(source_folder, fname)
        dest_path = os.path.join(dest_folder,   fname)

        try:
            with open(src_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  SKIP  {fname}  ({exc})")
            stats["skipped"] += 1
            continue

        repo = data.get("repository")

        if isinstance(repo, list):
            if dest_folder != source_folder:
                with open(dest_path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
            stats["already_ok"] += 1

        elif isinstance(repo, dict):
            data["repository"] = [repo]
            with open(dest_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            stats["converted"] += 1

        else:
            print(f"  SKIP  {fname}  (unexpected repository type: {type(repo).__name__})")
            stats["skipped"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="Folder containing SQAaaS JSON reports")
    parser.add_argument("--dest", default=None,
                        help="Output folder (default: in-place, same as source)")
    args = parser.parse_args()

    dest = args.dest or args.source
    inplace = dest == args.source

    print(f"Source : {args.source}")
    print(f"Dest   : {dest}  {'(in-place)' if inplace else ''}")

    stats = normalize_folder(args.source, dest)

    print(f"\nResults ({stats['total']} files):")
    print(f"  Converted  (dict→list) : {stats['converted']}")
    print(f"  Already OK (list)      : {stats['already_ok']}")
    print(f"  Skipped                : {stats['skipped']}")


if __name__ == "__main__":
    main()
