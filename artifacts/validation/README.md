# Validation Checks — SAC 2027

Validation scripts and results for the completeness, accuracy,
PROV-CONSTRAINTS, and timing checks.

---

## Input Files

| File | Path (relative to `yProv4SQA/`) | SHA-256 |
|------|----------------------------------|---------|
| itwinai Level-1 PROV document | `Provenance_documents/interTwin-eu_itwinai_prov_output.json` | `90912cf3a1854c1248808ce3f77ff5be80b344ddfb3c6f65ef42d1c6fb8f5bde` |
| Raw SQAaaS reports (380 files) | `artifacts/data/itwinai_SQAaaS_reports/` | — (folder) |
| Single-assessment Level-1 doc | `artifacts/paper/One_prov_output_enriched.json` | — |
| Level-2 comparison document | `Compare_commit_provenance/itwinai_commit_provenance_fc45...fd9c_to_4086...54f4.json` | — |

---

## Task 1 — Completeness Check

### 1a. Cypher Queries (Neo4j)

File: `completeness.cypher`

Contains one query per count, using the standard W3C PROV–Neo4j import schema
(`Entity`, `Activity`, `Agent` node labels; `wasGeneratedBy`, `wasDerivedFrom`,
`wasAttributedTo` relationship types; `id` property holding the prefixed IRI).

No Neo4j instance was available during this run; to execute:

```bash
# Start Neo4j, import the PROV document, then run:
cypher-shell -u neo4j -p <password> -f artifacts/validation/completeness.cypher
```

### 1b. Python completeness check (no Neo4j)

File: `completeness_check.py`

```bash
python artifacts/validation/completeness_check.py
# Output: artifacts/validation/completeness_results.json
```

Requirements: Python 3.9+, standard library only.

### Results (all 20 checks PASS)

| Item | Expected | Observed | Status |
|------|----------|----------|--------|
| Total entities | 559 | 559 | PASS |
| Assessment entities | 279 | 279 | PASS |
| Output entities | 279 | 279 | PASS |
| Repository entities | 1 | 1 | PASS |
| Total activities (QC checks) | 2,111 | 2,111 | PASS |
| Total agents | 1 | 1 | PASS |
| wasGeneratedBy | 2,111 | 2,111 | PASS |
| wasDerivedFrom | 558 | 558 | PASS |
| wasAttributedTo | 1 | 1 | PASS |
| Partial runs (is_partial_run=true) | 9 | 9 | PASS |
| Assessments with exactly 8 QC criteria | 212 | 212 | PASS |
| Assessments with fewer than 8 QC criteria | 67 | 67 | PASS |
| Activities QC.Acc | 270 | 270 | PASS |
| Activities QC.Doc | 270 | 270 | PASS |
| Activities QC.Lic | 270 | 270 | PASS |
| Activities QC.Met | 278 | 278 | PASS |
| Activities QC.Sec | 270 | 270 | PASS |
| Activities QC.Sty | 271 | 271 | PASS |
| Activities QC.Uni | 212 | 212 | PASS |
| Activities QC.Ver | 270 | 270 | PASS |

**Badge distribution:** No Badge: 38, bronze: 88, gold: 9, no_badge: 9, silver: 135

**Note on "fewer than 8":** 67 = 9 partial runs (1 criterion each) + 58 assessments
from the Oct 2023 – Nov 2023 period that pre-date the QC.Uni criterion (7 criteria each).

### Partial runs (9 total: 8 QC.Met at 0%, 1 QC.Sty at 100%)

| Assessment # | Date | Criterion | Score |
|---|---|---|---|
| 41 | 2023-11-16 | QC.Met | 0% |
| 42 | 2023-11-16 | QC.Met | 0% |
| 43 | 2023-11-16 | QC.Met | 0% |
| 44 | 2023-11-16 | QC.Met | 0% |
| 71 | 2024-04-16 | QC.Met | 0% |
| 72 | 2024-04-16 | QC.Met | 0% |
| 73 | 2024-04-16 | QC.Met | 0% |
| 106 | 2024-06-11 | QC.Met | 0% |
| 168 | 2024-11-19 | QC.Sty | 100% |

---

## Task 2 — Accuracy Check

File: `accuracy_check.py`

```bash
PYTHONPATH=src python artifacts/validation/accuracy_check.py
# Outputs:
#   artifacts/validation/accuracy_results.csv
#   artifacts/validation/accuracy_summary.json
```

Requirements: Python 3.9+, `yprov4sqa` package (via `PYTHONPATH=src`).

The script:
1. Loads the 380 raw reports from `artifacts/data/itwinai_SQAaaS_reports/`.
2. Applies the same deduplication as the pipeline (by source commit SHA,
   keeping the latest report per unique commit), yielding 279 retained assessments.
3. Compares each `(assessment, criterion)` pair: `ex:percentage` and `ex:output`
   in the PROV document against `coverage.percentage` and `valid` in the raw report.

### Results

| Item | Value |
|------|-------|
| Raw reports | 380 |
| Retained after deduplication | 279 |
| Total (commit, criterion) pairs | 2,111 |
| Matches | 2,111 |
| Mismatches | 0 |
| Raw-only pairs | 0 |
| PROV-only pairs | 0 |
| **Overall status** | **PASS** |

All 2,111 criterion-score pairs in the PROV document exactly match the
corresponding values in the original SQAaaS reports.

---

## Task 3 — PROV-CONSTRAINTS Validation

Directory: `prov_constraints/`

### Validator: Python `prov` library v2.1.1 (structural check)

The Python `prov` library performs structural validation during load and
serialization: missing references, type inconsistencies, and malformed qualified
names are caught.  It does **not** implement the full W3C PROV-CONSTRAINTS
formal inference rules.

```bash
python artifacts/validation/prov_constraints/validate_prov.py
# Output: artifacts/validation/prov_constraints/prov_library_results.json
# Also writes: single_assessment.provn, full_itwinai.provn, level2_fc45_4086.provn
```

### Results (all three documents PASS structural checks)

| Document | Records | Load | PROV-N | Unification | Status |
|---|---|---|---|---|---|
| Single-assessment Level-1 | 23 | PASS | PASS | PASS | **PASS** |
| Full itwinai Level-1 (279 assessments) | 5,341 | PASS | PASS | PASS | **PASS** |
| Level-2 fc45→4086 | 570 | PASS | PASS | PASS | **PASS** |

### Specific constraint areas (reviewer's questions)

**Entities with multiple `wasGeneratedBy`:**
Each assessment entity has up to 8 `wasGeneratedBy` relations (one per QC activity).
270 entities have multiple `wasGeneratedBy` in the full itwinai document.
This is **not** a PROV-CONSTRAINTS violation: uniqueness of generation
(PROV-CONSTRAINTS §3 "uniq-gen") applies per activity–entity pair, not globally per entity.
The Python `prov` library accepted these without error.

**`wasAttributedTo` (repository → SQAaaS):**
`ex:repository1 ← ex:SQAaaS` — PRESENT in both Level-1 documents (single and full).

**Level-2 relations:**
The fc45→4086 document uses `wasDerivedFrom` (282 relations) to link
file-change activities to commit entities; no `used` relations are present
in this document version.

### Full PROV-CONSTRAINTS validation (ProvToolbox 2.2.1)

ProvToolbox 2.2.1 (`~/ProvToolbox/bin/provconvert`) was run on 2026-11-26 against
PROV-N files generated by the Python `prov` library (see `prov_constraints/commands.txt`
for the exact commands).  Results are in `prov_constraints/provtoolbox_results.md`.

| Document | Output file | Verdict |
|---|---|---|
| Single-assessment Level-1 | `single_assessment_validation.txt` (28 B) | **PASS** |
| Level-2 fc45→4086 | `level2_fc45_4086_validation.txt` (0 B) | **PASS** |
| Full itwinai Level-1 | `full_itwinai_validation.txt` (173 KB) | **INCOMPLETE** |

**Single-assessment** — one informational message (`Parsing not processed for 0`);
no PROV-CONSTRAINTS violations.

**Level-2** — completely empty output; clean PASS.

**Full itwinai** — provconvert crashed with `QualifiedNameException` on
`generic_torch.sh:` (a filename inside a CI stdout log stored in an activity attribute).
Root cause: the Python `prov` library v2.1.1 serializes multi-line string values using
triple-quoted PROV-N syntax (`"""..."""`), which is a non-standard extension.
ProvToolbox's PROV-N parser does not support triple-quoted strings and attempts to parse
their content as QNames, crashing when it encounters a colon-bearing shell filename.
The 3,902 `extensibility: qnameDisabled false <token>` lines before the crash are debug
messages from the same misparsing mode; they are **not** PROV-CONSTRAINTS violations.

No PROV-CONSTRAINTS violations were reported for any document.  The crash is a
ProvToolbox 2.2.1 parser limitation, not a problem with the PROV-JSON document itself
(the document passes all Python `prov` library structural checks above).

### Task D — ProvToolbox directly on the PROV-JSON file

Run on 2026-11-26.  Output: `prov_constraints/full_itwinai_json_validation.txt`.

```bash
export JAVA_HOME=~/projects/MMU/.jdk/jdk-25.0.4.1+1-jre
export PATH=$JAVA_HOME/bin:$PATH
~/ProvToolbox/bin/provconvert \
  -infile Provenance_documents/interTwin-eu_itwinai_prov_output.json \
  -outfile /tmp/full_json_out.provn 2>&1
```

**Result: INCOMPLETE** — provconvert crashed before performing any constraint check.
Error: `NullPointerException: Cannot invoke "Collection.iterator()" because "attributes"
is null` at `Entity.setIndexedAttributes()` while deserialising `ex:repository1`'s
`ex:description` attribute. Root cause: ProvToolbox 2.2.1's PROV-JSON deserialiser
requires all attribute values to use the typed `{"$type":…, "$value":…}` encoding; plain
JSON string values (like `ex:description`'s free-form text) pass null to
`ProvUtilities.distribute()`, causing the crash.  No PROV-CONSTRAINTS check was performed.

This is a different bug from the PROV-N crash: JSON → crash on attribute
deserialization; PROV-N → crash on QName parsing of multi-line string bodies.

See `prov_constraints/commands.txt` for the full command set and
`prov_constraints/provtoolbox_results.md` for the complete analysis.

---

## Task 4 — Timing

Directory: `timing/`

```bash
PYTHONPATH=src python artifacts/validation/timing/time_generation.py
# Outputs:
#   artifacts/validation/timing/timing_results.csv
#   artifacts/validation/timing/timing_results.json
#   artifacts/validation/timing/timing_summary.md
```

Requirements: Python 3.9+, `yprov4sqa` package.

### Machine

| Property | Value |
|---|---|
| OS | Linux 6.18 (WSL2, Microsoft) |
| CPU | Intel Core i5-6300U @ 2.40 GHz, 4 cores |
| RAM | 5.8 GB |
| Python | 3.13.11 (Anaconda) |
| Neo4j | not available |

### Level-1 generation time (3 runs, median)

| Repository | Raw reports | Median (s) | Min (s) | Max (s) | PROV doc (KB) |
|---|---|---|---|---|---|
| interTwin-eu/itwinai | 380 | 2.403 | 2.337 | 2.424 | 6,005.9 |
| indigo-dc/udocker | 42 | 0.194 | 0.192 | 0.213 | 855.0 |
| grycap/im | 36 | 0.562 | 0.552 | 0.896 | 807.9 |
| EOSC-synergy/sqaaas-assessment-action | 39 | 0.301 | 0.253 | 0.305 | 783.9 |
| SeisSol/SeisSol | 8 | 0.059 | 0.057 | 0.060 | 180.6 |
| grycap/oscar | 7 | 0.042 | 0.042 | 0.046 | 157.4 |
| EOSC-synergy/FAIR_eva | 3 | 0.017 | 0.017 | 0.017 | 68.4 |
| galaxyproject/galaxy | 1 | 0.050 | 0.049 | 0.055 | 24.9 |
| EOSC-synergy/o3api | 1 | 0.005 | 0.004 | 0.006 | 19.2 |
| indigo-dc/orchestrator | 1 | 0.003 | 0.003 | 0.005 | 20.6 |

**Note on sqaaas-assessment-action and oscar:**
These repos have mixed-format reports: 28 of 39 (sqaaas-action) and 1 of 7 (oscar)
files store `repository` as a JSON object (old format) rather than a list (new format).
The existing `_SQAaaS_reports_norm` folders already contain the same files with the
`repository` field normalised to a list; the original PROV documents were generated
from these `_norm` folders. The timing wrapper was updated to reference `_norm`
directly, matching the original generation input.
Doc sizes: sqaaas-assessment-action 783.9 KB (paper Table 2: 783.9 KB ✓),
oscar 157.4 KB (paper Table 2: 157.4 KB ✓).

**Upload time:** Not measured (yProv service not available).

**Neo4j query latency:** Not measured (Neo4j instance not available).

**Level-2 generation time:** Not timed automatically (requires live GitHub API calls).
The fc45→4086 document contains 282 file-change activities, 2 commit entities, 2 agents.

---

## Running All Checks

```bash
cd yProv4SQA/

# Task 1 (completeness)
python artifacts/validation/completeness_check.py

# Task 2 (accuracy)
PYTHONPATH=src python artifacts/validation/accuracy_check.py

# Task 3 (structural validation)
python artifacts/validation/prov_constraints/validate_prov.py

# Task 4 (timing)
PYTHONPATH=src python artifacts/validation/timing/time_generation.py
```

Python ≥ 3.9 required for all scripts.
Task 2 and Task 4 also require the `yprov4sqa` package (`PYTHONPATH=src`).
Task 3 requires `pip install prov`.

---

## Differences from Expected Values

None.  All completeness checks (20/20) and all accuracy pairs (2,111/2,111)
match the expected values exactly.
