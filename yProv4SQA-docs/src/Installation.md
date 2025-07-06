# yProv4SQA Installation

This section provides the necessary steps to install **yProv4SQA** and its dependencies, ensuring that the library is ready to use in your development environment.

### **Prerequisites**
Before installing **yProv4SQA**, ensure that you have the following installed:
- **Python 3.x** (Recommended: 3.7 or higher)
- **Git** (for version control and integration with GitHub)
- **pip** (Python package manager)


### Installation

Follow these steps to install **yProv4SQA** and its dependencies.

### 1. Clone the Repository

First, clone the repository to your local machine:

```bash
git clone https://github.com/yourusername/yProv4SQA.git
cd yProv4SQA
```

### 2. Install the Library

After cloning the repository, install **yProv4SQA** by running:

```bash
pip install -e .
```

This will install **yProv4SQA** in editable mode.

### 3. Install Dependencies

Next, install the required dependencies for the library:

```bash
pip install requests
```

These dependencies are necessary for fetching and processing reports.

---

## Usage

Once you've installed **yProv4SQA**, you can start using it to fetch SQA reports, generate provenance documents, and compare commits.

### 1. Fetch SQA Reports

To fetch the SQA reports for a specific repository, use the following command:

```bash
fetch-sqa-reports yprov.git
```

This will download all the assessment reports related to the repository and save them in a folder named `<RepoName>_reports`.

### 2. Generate Provenance

Once the SQA reports are fetched, you can generate the provenance document for the assessments:

```bash
process-provenance [folder_path]
```

This command will process the fetched reports and generate provenance data for the selected assessments. Replace `[folder_path]` with the path to the folder containing your reports.

### 3. Compare Commits

To compare code changes between two assessments and generate provenance data, use the following command:

```bash
compare [Prov_file_path] AssessmentNo1 AssessmentNo2
```

This command will compare the changes between the two assessments (identified by their respective numbers) and generate provenance data showing the difference in code between those assessments.

---

## Example

Here’s an example of how the commands would work together:

1. Clone the repository and navigate to the directory:
   ```bash
   git clone https://github.com/yourusername/yProv4SQA.git
   cd yProv4SQA
   ```

2. Install the library and dependencies:
   ```bash
   pip install -e .
   pip install requests
   ```

3. Fetch SQA reports:
   ```bash
   fetch-sqa-reports yprov.git
   ```

4. Generate provenance documents:
   ```bash
   process-provenance ./yprov.git_reports
   ```

5. Compare two assessments:
   ```bash
   compare ./provenance.json 1 2
   ```
This will give you a structured view of how the software quality has changed between the first and second assessments.