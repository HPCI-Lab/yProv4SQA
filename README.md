
<div align="center">
  <h3 align="center">yProv4SQA</h3>

  <p align="center">
    A provenance-based framework for traceability in Software Quality Assurance pipelines — tracking the evolution of software quality over time using W3C PROV-compliant documents.
    <br />
    <a href="docs/"><strong>Explore the docs »</strong></a>
  </p>
</div>

This library is part of the yProv suite, and provides a provenance-based architecture for traceability in Software Quality Assurance (SQA) pipelines. It integrates with [SQAaaS](https://docs.sqaaas.eosc-synergy.eu/) to collect quality assessment reports and generate W3C PROV-compliant provenance documents that capture the full quality evolution of a software project over time.

It allows users to generate provenance graphs, compare any two assessments at the commit level, publish documents to [yProvStore](http://yprov.disi.unitn.it:8000), visualize them in [yProvExplorer](https://explorer.yprov.disi.unitn.it), and interact with the provenance data through a conversational AI agent.

## Overview

![App Overview](docs/images/app_overview.png)

## Architecture

![yProv4SQA Architecture](docs/images/architecture.png)

## Provenance Graph (Level-1)

![Level-1 Provenance in yProvExplorer](docs/images/provenance_graph_level1.png)

## Commit Comparison (Level-2)

![Level-2 Provenance — Commit Diff](docs/images/provenance_graph_level2.png)

## Data Model

![Data Model](docs/images/data_model.png)

## Chat Agent

![Chat Interface](docs/images/chat_interface.png)

## Compare Assessments

![Compare Tab](docs/images/compare_tab.png)

## Quick Example

```bash
# 1 — fetch SQAaaS assessment reports from GitHub
fetch-sqa-reports itwinai

# 2 — generate a Level-1 provenance document (full quality history)
process-provenance ./itwinai_SQAaaS_reports

# 3 — compare two assessments (generates a Level-2 provenance document)
compare ./Provenance_documents/interTwin-eu_itwinai_prov_output.json 59 87

# 4 — chat with your provenance data
prov-chat ./Provenance_documents/interTwin-eu_itwinai_prov_output.json --web --port 5000
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## What it does

- **Fetches** SQAaaS assessment reports from the EOSC-Synergy GitHub space
- **Generates Level-1 provenance documents** — full quality history of a repository, W3C PROV compliant
- **Generates Level-2 provenance documents** — commit-level diff between any two assessments, with direct links to GitHub diffs and SQAaaS reports
- **Visualizes** provenance graphs using the PROV library (SVG) or yProvExplorer (interactive)
- **Publishes** provenance documents to yProvStore for persistent storage and sharing
- **Chat agent** — ask natural language questions about your provenance data using a local (Ollama) or cloud (Google Gemini) LLM

# Documentation

For detailed information, please refer to the [Documentation](docs/).

# Contributors

- Anonymous (to be revealed at camera-ready)
