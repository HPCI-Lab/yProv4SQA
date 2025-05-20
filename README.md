# yProv4SQA: Quick Start Guide
`yProv4SQA` is a Python library used to generate provenance documents for software quality assurance processes.
## Installation
1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/yProv4SQA.git
   cd yProv4SQA
2. **Install the library:**
   ```bash
   pip install -e .
3. **Install dependencies**
   ```bash
   pip install requests
## Usage
1. **Fetch SQA Reports**
   To fetch SQA reports for a specific repository:
   ```bash
   fetch-sqa-reports [RepoName].git
This will download all the assessment reports and save them in the <RepoName>_reports folder.

2. ""Generate Provenance""
   ```bash
   process-provenance [folder path]

3. ""Compare Commits""
   ```bash
   compare [Prov file path]  AssessmentNo1 AssessmentNo2
To compare two Code changes between two Assesments and generate provenance data:

#Cmmit data in Assesment
#also add the 
