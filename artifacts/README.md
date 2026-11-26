# Artifact for "yProv4SQA: A Provenance-Based Architecture with an AI Agent for Traceability in Software Quality Assurance Pipelines" (SAC 2027)

We introduce **yProv4SQA**, a W3C PROV-DM provenance framework for Software Quality
Assurance (SQA) pipelines, with a ReAct-style LLM agent for natural-language querying.
In this example we analyse the [iTwinAI GitHub repository](https://github.com/interTwin-eu/itwinai).

The paper validates yProv4SQA across **11 open-source repositories** (469 unique assessments),
spanning Python, C++, Go, and Java projects.

---

## Contents of this branch

| Path | Description |
|------|-------------|
| `Provenance_documents/` | Level-1 PROV-JSON files for all 11 repositories (see §PIDs below) |
| `Compare_commit_provenance/itwinai_commit_provenance_fc45...fd9c_to_4086...54f4.json` | Level-2 commit-comparison document (Fig. 6) |
| `artifacts/data/itwinai_SQAaaS_reports/` | 380 raw SQAaaS JSON reports for itwinai |
| `artifacts/data/Figure5_data.csv` | Listing 1 output: quality evolution data |
| `artifacts/paper/One_prov_output_enriched.svg` | Fig. 3: single-assessment Level-1 SVG provenance graph |
| `artifacts/validation/` | Completeness, accuracy, PROV-CONSTRAINTS, timing checks |

---

## GitHub API rate-limit notice

GitHub allows:
* **60 requests / hour** for **anonymous** calls (no token).
* **5000 requests / hour** when you supply a **personal-access token**.

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx   # replace with your token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```

---

## Setup

```bash
git clone https://github.com/HPCI-Lab/yProv4SQA.git
cd yProv4SQA
git checkout yProv4SQA_SAC2027
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install requests
```

---

## Fetch SQA reports

```bash
fetch-sqa-reports itwinai
```

Fetches all SQAaaS assessments for `itwinai` from the
[EOSC-Synergy GitHub space](https://github.com/EOSC-synergy), deduplicates by commit
SHA, and writes the cleaned set to `./itwinai_SQAaaS_reports`.

You can skip this step and use the reports already downloaded in
`./artifacts/data/itwinai_SQAaaS_reports` (380 raw reports, 279 retained after
deduplication).

---

## Generate provenance documents

```bash
process-provenance ./itwinai_SQAaaS_reports
```

Generates a Level-1 provenance document
(`Provenance_documents/interTwin-eu_itwinai_prov_output.json`) conforming to W3C PROV-DM.

---

## Compare two assessments (Level-2)

```bash
compare ./Provenance_documents/interTwin-eu_itwinai_prov_output.json 64 115
```

Generates the Level-2 document that captures file changes between assessments 64 and 115,
archived at `Compare_commit_provenance/itwinai_commit_provenance_fc45...fd9c_to_4086...54f4.json`.

---

## Visualise and explore provenance graphs

### 1. PROV library (SVG, Fig. 3)

```bash
json2graph ./Provenance_documents/interTwin-eu_itwinai_prov_output.json
```

The figure that appears as **Fig. 3** in the paper was generated using this command and
is included in `./artifacts/paper/One_prov_output_enriched.svg`.

### 2. yProvExplorer (interactive)

Upload any `.json` file at [https://explorer.yprov.disi.unitn.it/](https://explorer.yprov.disi.unitn.it/)
or use the pre-uploaded documents (see §PIDs below):

- **Full assessment history (Fig. 4):**  
  [View graph](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fde35c9af-31d4-4fe8-b571-72f4c1bca8dd%3Fstream%3Dfalse)
- **File changes between assessments 64 and 115 (Fig. 6):**  
  Generate locally (see step above) and drag-and-drop the `.json` into the explorer.

### 3. yProv + Neo4j

Follow [Pre_requisites/yProv/README.md](Pre_requisites/yProv/README.md) to start the
yProv service and a Neo4j database.  Then load the Level-1 document:

```bash
# Register and log in, then:
curl -X PUT http://localhost:3000/api/v0/documents/itwinai \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d @./Provenance_documents/interTwin-eu_itwinai_prov_output.json
```

Open Neo4j at http://localhost:7474/browser/

---

## AI Agent

```bash
prov-chat ./Provenance_documents/interTwin-eu_itwinai_prov_output.json --web --port 5000
```

Open http://localhost:5000 in your browser.  Requires [Ollama](https://ollama.com/) with
`llama3.2` installed, or a Google Gemini API key (set `GEMINI_API_KEY`).

---

## Sample Neo4j Queries

**Cypher Neo4j Query (Listing 1)**
```cypher
MATCH (e:Entity)-[:wasGeneratedBy]->(a:Activity)
WHERE a.`ex:percentage` IS NOT NULL
RETURN
   e.`ex:commit_id`   AS CommitID,
   e.`ex:commit_date` AS CommitDate,
   a.`ex:description` AS QualityCriteria,
   a.`ex:percentage`  AS PercentagePassed
ORDER BY e.`ex:commit_date`
```

The query exports the raw data behind **Fig. 5**; the result CSV is archived in
[artifacts/data/Figure5_data.csv](data/Figure5_data.csv).

**Cypher Neo4j Query (Listing 2)**
```cypher
// Find the earliest Silver badge assessment
MATCH (silver:Entity)-[:wasDerivedFrom]->(silver_ass:Entity)
WHERE silver.`ex:badge_won` = "silver"
WITH silver, silver_ass
ORDER BY silver_ass.`ex:commit_date` ASC
LIMIT 1

// Find all Bronze badge assessments that precede it
MATCH (bronze:Entity)-[:wasDerivedFrom]->(bronze_ass:Entity)
WHERE bronze.`ex:badge_won` = "bronze"
  AND bronze_ass.`ex:commit_date` < silver_ass.`ex:commit_date`
RETURN
  silver_ass.`ex:commit_id`   AS SilverCommitID,
  silver_ass.`ex:commit_date` AS SilverCommitDate,
  bronze_ass.`ex:commit_id`   AS BronzeCommitID,
  bronze_ass.`ex:commit_date` AS BronzeCommitDate,
  bronze.`ex:badge_won`       AS BronzeBadge
ORDER BY bronze_ass.`ex:commit_date` ASC
```

The query in Listing 2 returns the earliest Silver assessment and all Bronze assessments
that precede it, motivating the Level-2 comparison shown in **Fig. 6**.
The resulting Level-2 graph is at
`Compare_commit_provenance/itwinai_commit_provenance_fc45...fd9c_to_4086...54f4.json`.

---

## Badge labels in the PROV document

The Level-1 document contains two distinct badge labels in `ex:badge_won`:

| Label | Count | Meaning |
|-------|-------|---------|
| `No Badge` | 38 | Full assessment run; badge criteria not satisfied |
| `no_badge` | 9 | Partial run (`ex:is_partial_run=true`); assessment aborted before all criteria ran |
| `bronze` | 88 | Bronze badge awarded |
| `silver` | 135 | Silver badge awarded |
| `gold` | 9 | Gold badge awarded |

The lowercase `no_badge` label (9 occurrences) always co-occurs with
`ex:is_partial_run=true` in the corresponding assessment entity — verified in
`artifacts/validation/completeness_results.json`.

---

## Paper — Figure and Listing index

| Paper ref | Description | File(s) in artifact |
|-----------|-------------|---------------------|
| Fig. 3 | Single-assessment Level-1 provenance graph (SVG) | `artifacts/paper/One_prov_output_enriched.svg` |
| Fig. 4 | Full itwinai assessment history in yProvExplorer | pre-uploaded at yProv server (see §PIDs) |
| Fig. 5 | Quality evolution chart (Listing 1 output) | `artifacts/data/Figure5_data.csv` |
| Fig. 6 | Level-2 commit-comparison graph | `Compare_commit_provenance/itwinai_commit_provenance_fc45...fd9c_to_4086...54f4.json` |
| Listing 1 | Cypher query for quality evolution data | this README, section "Sample Neo4j Queries" |
| Listing 2 | Cypher query for first-silver + preceding-bronze | this README, section "Sample Neo4j Queries" |

---

## Persistent identifiers (PIDs)

All 11 Level-1 provenance documents are stored in the yProv service
(http://yprov.disi.unitn.it:8000) and assigned persistent identifiers via the
ePIC Handle service.

| Repository | PID | Explorer link |
|------------|-----|---------------|
| interTwin-eu/itwinai | `21.T11961/de35c9af-31d4-4fe8-b571-72f4c1bca8dd` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fde35c9af-31d4-4fe8-b571-72f4c1bca8dd%3Fstream%3Dfalse) |
| grycap/im | `21.T11961/4a3cddf7-a1e5-41d3-9e8f-4a46506cdaa2` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2F4a3cddf7-a1e5-41d3-9e8f-4a46506cdaa2%3Fstream%3Dfalse) |
| HPCI-Lab/yProv | `21.T11961/a044e1b6-58a2-40e7-ad01-a3aab86a3a4c` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fa044e1b6-58a2-40e7-ad01-a3aab86a3a4c%3Fstream%3Dfalse) |
| indigo-dc/udocker | `21.T11961/c38bfb85-abbc-442c-a0a4-63af3e064ce8` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fc38bfb85-abbc-442c-a0a4-63af3e064ce8%3Fstream%3Dfalse) |
| EOSC-synergy/sqaaas-assessment-action | `21.T11961/c6da4c59-2d18-479c-9f40-5f10d9432130` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fc6da4c59-2d18-479c-9f40-5f10d9432130%3Fstream%3Dfalse) |
| SeisSol/SeisSol | `21.T11961/c074c13f-a1ce-4b2b-ab3a-c24e29b42c5e` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fc074c13f-a1ce-4b2b-ab3a-c24e29b42c5e%3Fstream%3Dfalse) |
| grycap/oscar | `21.T11961/052fbfa2-fedd-4ac5-9446-e1274dcebfae` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2F052fbfa2-fedd-4ac5-9446-e1274dcebfae%3Fstream%3Dfalse) |
| EOSC-synergy/FAIR\_eva | `21.T11961/12bdd31c-262d-4869-8689-f655dc798389` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2F12bdd31c-262d-4869-8689-f655dc798389%3Fstream%3Dfalse) |
| galaxyproject/galaxy | `21.T11961/cb00c83e-63c9-402f-a393-291b139c8439` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2Fcb00c83e-63c9-402f-a393-291b139c8439%3Fstream%3Dfalse) |
| EOSC-synergy/o3api | `21.T11961/41223a47-cdf1-4f8c-aa76-300174d63181` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2F41223a47-cdf1-4f8c-aa76-300174d63181%3Fstream%3Dfalse) |
| indigo-dc/orchestrator | `21.T11961/26b7e356-ef7d-4c6c-9e45-048ec2a24d62` | [Open](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A8000%2Fdocuments%2F21.T11961%2F26b7e356-ef7d-4c6c-9e45-048ec2a24d62%3Fstream%3Dfalse) |

---

## Normalization of old-format SQAaaS reports

Two repositories (`sqaaas-assessment-action`, `oscar`) have reports where the `repository`
field is a JSON object instead of a list.  Pre-normalized copies are in the
`results/*_SQAaaS_reports_norm` folders.  To normalize from scratch:

```bash
python artifacts/validation/normalize_reports.py results/sqaaas-assessment-action_SQAaaS_reports \
  --dest results/sqaaas-assessment-action_SQAaaS_reports_norm
```

Requirements: Python 3.6+, standard library only.

---

## Multi-Repository Evaluation

The paper validates yProv4SQA across 11 open-source repositories.
Pre-generated provenance documents are in `./Provenance_documents/`.

To regenerate all documents from scratch:

```bash
python artifacts/multi_repo_evaluation/run_all_repos.py
```

---

## Validation checks

Completeness, accuracy, structural (PROV-CONSTRAINTS), and timing checks are
documented in [artifacts/validation/README.md](validation/README.md).

---

## Summary

This artifact demonstrates the complete provenance-based SQA workflow from the paper.
With yProv4SQA you can collect SQAaaS reports, generate Level-1 and Level-2 provenance
documents, visualise graphs, explore via Neo4j, and ask natural-language questions
through the AI agent.
