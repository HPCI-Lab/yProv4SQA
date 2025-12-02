# yProv4SQA: Quick Start Guide
`yProv4SQA` is a Python library used to generate provenance documents for software quality assurance pipelines.

## Installation
1. **Clone the Repository:**
```bash
   git clone <Repo_URL/yProv4SQA>
   cd yProv4SQA
```
2. **Install the library:**
```bash
   pip install -e .
``` 
3. **Install dependencies**
```bash
   pip install requests
``` 

## Usage
1. **Fetch SQA Reports**
To fetch SQA reports for a specific repository:
```bash
   fetch-sqa-reports <RepoName>
``` 
This will download all the assessment reports and save them in the <RepoName>_SQAaaS_reports folder.

2. **Generate Provenance**
```bash
   process-provenance 'folder_path'
``` 
This command generates a level-1 provenance document of all assessments available in folder_path directory using W3C PROV-DM standard. 

3. **Compare Commits**
```bash
   compare 'Prov_file_path' AssessmentNo1 AssessmentNo2
``` 
This command generates a level-2 provenance document that captures the file changes between two Assessments.

## Get started
You can find detailed ready-to-use examples to get started with yProv4SQA under the [artifacts](./artifacts) folder.