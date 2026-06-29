# yProv4SQA Documentation

**yProv4SQA** is a provenance-based tool for traceability in Software Quality Assurance (SQA) pipelines. It tracks the evolution of software quality over time by generating W3C PROV-compliant provenance documents from [SQAaaS](https://docs.sqaaas.eosc-synergy.eu/) assessment reports.

![yProv4SQA Architecture](images/architecture.png)

## Data Model

![Data Model](images/data_model.png)

---

## What it does

- Fetches SQAaaS assessment reports from GitHub
- Generates **Level-1 provenance documents** — full quality history of a repository
- Generates **Level-2 provenance documents** — commit-level diff between any two assessments
- Lets you **chat with your provenance data** using a local or cloud LLM
- Publishes provenance to **yProvStore** and visualizes it in **yProvExplorer**

---

## Sections

| Page | What you will find |
|------|--------------------|
| [Installation](installation.md) | Setup, dependencies, virtual environment |
| [Quickstart](quickstart.md) | Fetch reports → generate provenance → explore |
| [Chat Agent](chat_agent.md) | Run the web UI, ask questions, choose your LLM |
| [yProvStore & Explorer](yprovstore.md) | Publish and visualize your provenance graphs |
| [HPC Setup](hpc_setup.md) | Run on an HPC cluster with Ollama on GPU |
| [Tools Reference](tools_reference.md) | All 7 agent tools explained |
| [Troubleshooting](troubleshooting.md) | Common errors and fixes |

---

## Quick example

```bash
# 1 — fetch reports for a repository
fetch-sqa-reports itwinai

# 2 — generate provenance document
process-provenance ./itwinai_SQAaaS_reports

# 3 — chat with it
prov-chat ./Provenance_documents/interTwin-eu_itwinai_prov_output.json --web --port 5000
```

Open [http://localhost:5000](http://localhost:5000) in your browser.
