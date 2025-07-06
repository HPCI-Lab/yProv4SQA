# Artifact for “A Provenance-Based Architecture for Traceability in Software Quality Assurance Pipelines” (ICSA 2026)
To gain complete insights about software quality evaluation, we introduce the concept of provenance for Software Quality Assurance pipelines called yProv4SQA, which is used for tracking the evolution of software quality over time by generating detailed provenance documents during software development.

# Example: Using yProv4SQA with the iTwinAI Repository
In this example, we demonstrate how to use our library by analyzing the [iTwinAI GitHub repository](https://github.com/interTwin-eu/itwinai).  
This repository already utilizes SQAaaS and contains existing assessments. We will use it to showcase the capabilities of our library and extract insights related to software quality and provenance.

## GitHub API rate-limit notice
GitHub allows:
* **60 requests / hour** for **anonymous** calls (no token).  
* **5000 requests / hour** when you supply a **personal-access token**.
If you process many repositories for large histories you will quickly hit the 60/h ceiling and the tool will **pause** (it auto-retries after the reset time). To avoid delays we **strongly recommend** that you authenticate.

**Export it in your shell (temporary)**
   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx #<replace with your GITHUB_TOKEN>
   ```
Verify quota
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   ```
You should see "limit": 5000

## **Clone the repository and navigate to the directory:**
   ```bash
   git clone https://github.com/HPCI-Lab/yProv4SQA.git
   cd yProv4SQA
   ```
   
## **Setup the environment and install dependencies:**
### 1. Create and activate a virtual environment (recommended)
   ```bash
   # Create a virtual environment
   python -m venv yProv4SQA_venv

   # Activate the virtual environment
   source yProv4SQA_venv/bin/activate
   ```
This ensures that all dependencies are installed in an isolated environment, preventing conflicts with other Python packages on your system.

### **2. Install the library and required dependencies:**
   ```bash
   pip install -e .
   pip install requests
   ```
This installs the library and also installs the requests library, which is required to run the examples.

## **Fetch SQA reports:**
   ```bash
   fetch-sqa-reports itwinai
   ```
This command fetches all SQAaaS assessments for the `itwinai` repository from the [EOSC-Synergy GitHub space](https://github.com/EOSC-synergy). The library then removes duplicates and outdated assessments, and produces a final cleaned directory used to generate the provenance document. For this example, the output directory will be created as `./itwinai_SQAaaS_reports`.


## **Generate provenance documents:**
   ```bash
   process-provenance ./itwinai_SQAaaS_reports
   ```
This command generates a level-1 provenance document of all assessments available in `itwinai_SQAaaS_reports` directory using W3C PROV-DM standard. It will produce a `.json` file named `interTwin-eu_itwinai_prov_output.json` in `Provenance_documents` directory, which can be further used for exploration and analysis.

## **Comparing Two SQA Assessments with yProv4SQA**
   ```bash
   compare ./Provenance_documents/interTwin-eu_itwinai_prov_output.json 59 87
   ```
This command generates a level-2 provenance document that captures the file changes between assessments no. 59 and assessments no. 87, integrates directly with URLs to the corresponding GitHub diff and SQAaaS reports, and stores the graph as `./Compare_commit_provenance/itwinai_commit_provenance_040b…ea8b_to_96fd…56c0.json`

## **Exploration of Provenance graph**
We can use several tools to visualize and analyze the generated provenance documents.
### 1. PROV Library Visualization
This PROV library can be used to check the PROV syntax, convert the provenance document into an SVG graph for standard visualization, and to ensure the compliance with the W3C PROV standard.
   ```bash
   json2graph ./Provenance_documents/interTwin-eu_itwinai_prov_output.json
   json2graph ./Compare_commit_provenance/itwinai_commit_provenance_040b…ea8b_to_96fd…56c0.json
   ```
This command converts the `.json` file into an `.svg` provenance graph and saves it to `./Graph_outputs`.
The figure that appears as `Fig. 4` in the paper was generated using this command and  included as an example in `./results`.

### 2. Using yProvExplorer
You can either upload the `interTwin-eu_itwinai_prov_output.json` file into the explorer or drag and drop the file for  visualization.  
Access the explorer here: [https://explorer.yprov.disi.unitn.it/](https://explorer.yprov.disi.unitn.it/)

For convenience, we have already uploaded the graphs that we used in our paper to the yProv server. You can directly open them without uploading the `.json` file:

- **Full assessment history (Fig. 5):** [View Graph](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A3000%2Fapi%2Fv0%2Fdocuments%2Fitwinai)  
- **file changes between the two assessments (Fig. 7):** [View Graph](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A3000%2Fapi%2Fv0%2Fdocuments%2Fgitdif)


### 3. Using yProv and Neo4j for Provenance Visualization and Data Exploration
We use the [yProv service](./Pre_requisites/yProv/README.md) to connect with a Neo4j database for exploring the provenance graph. After registering with the service, provenance documents can be uploaded and automatically synchronized with a Neo4j graph database for exploration.
To set up the environment (yProv service + Neo4j database), please follow the instructions in: [Running yProv service](./Pre_requisites/yProv/README.md)
Once both containers are running, you can interact with the yProv REST API as shown below.

Register to the yProv service and replace the "..." with your own username and password.
   ```bash
   curl -X POST http://localhost:3000/api/v0/auth/register -H 'Content-Type: application/json' -d '{"user": "...", "password": "..."}'
   ```

Log in to the service to get a valid token for performing all the other operations
   ```bash
   curl -X POST http://localhost:3000/api/v0/auth/login -H 'Content-Type: application/json' -d '{"user": "...", "password": "..."}'
   ```

Load the JSON document associated with itwinai use case
   ```bash
   curl -X PUT  http://localhost:3000/api/v0/documents/itwinai -H "Content-Type: application/json" -H 'Authorization: Bearer <token>' -d @./Provenance_documents/interTwin-eu_itwinai_prov_output.json
   ```
- This command will upload the `./Provenance_documents/interTwin-eu_itwinai_prov_output.json` to the yProv service.
- Replace `<token>` with the actual token you obtained in the previous step.

After uploading the provenance document, open Neo4j in your browser using the mapped ports, typically:
http://localhost:7474/browser/

## **Sample Neo4j Queries**
Below are the Neo4j queries we ran to extract and analyze the results presented in the paper.

**Cypher Neo4j Query (Listing 1)**
   ```cypher
   MATCH (e:Entity)-[:wasGeneratedBy]->(a:Activity)
   WHERE a.`ex:percentage` IS NOT NULL
   RETURN
      e.`ex:commit_id` AS CommitID,
      e.`ex:commit_date` AS CommitDate,
      a.`ex:description` AS QualityCriteria,
      a.`ex:percentage` AS PercentagePassed
   ORDER BY e.`ex:commit_date`
   ```
The query exports the raw data behind Fig. 6; the CSV file and the Excel line-chart we plotted are archived in [Results](./results/Cypher_query_results) 


**Cypher Neo4j Query (Listing 2)**
   ```cypher
   // Earliest Bronze badge
   MATCH (bronze:Entity)-[:wasDerivedFrom]->(bronze_ass:Entity)
   WHERE bronze.`ex:badge_won` = "bronze"
   WITH bronze , bronze_ass
   ORDER BY bronze_ass.`ex:commit_date` ASC
   LIMIT 1
   // Earliest Silver badge
   MATCH (silver:Entity)-[:wasDerivedFrom]->(silver_ass:Entity)
   WHERE silver.`ex:badge_won` = "silver"
   WITH bronze , bronze_ass, silver , silver_ass
   ORDER BY silver_ass.`ex:commit_date` ASC
   LIMIT 1
   RETURN 
   bronze_ass.`ex:commit_id` AS BronzeCommitID,
   bronze_ass.`ex:commit_date` AS BronzeCommitDate,
   bronze.`ex:badge_won` AS BronzeBadge,
   bronze_ass.id,
   silver_ass.`ex:commit_id` AS SilverCommitID,
   silver_ass.`ex:commit_date` AS SilverCommitDate,
   silver.`ex:badge_won` AS SilverBadge,
   silver_ass.id
   ```
The query in Listing 2 returns the last assessment ID that earned a bronze badge and the first one that achieved silver; the resulting [level-2 provenance graph](./results/Compare_commit_provenance). (Fig. 7) and query result is stored in [Results](./results/Cypher_query_results).

## **Summary**
This artifact demonstrates the complete provenance based SQA workflow from the paper. With yProv4SQA, you can collect SQAaaS reports, generate provenance documents, compare any two assessments, visualize graphs, and explore them through Neo4j and the yProv service.
A few example Cypher queries are included, and developers can extend them with their own queries as needed.