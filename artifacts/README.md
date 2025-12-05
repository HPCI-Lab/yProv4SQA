# Artifact for “A Provenance-Based Architecture for Traceability in Software Quality Assurance Pipelines” (ICSA 2026)

To gain complete insights about software quality evaluation, we introduce the concept of provenance for Software Quality Assurance pipelines called yProv4SQA, which is used for tracking the evolution of software quality over time by generating detailed provenance documents during software development.

## **Example: Using yProv4SQA with the itwinai Repository**

In this example, we demonstrate how to use our library by analyzing the [itwinai GitHub repository](https://github.com/interTwin-eu/itwinai).  
This repository already utilizes SQAaaS and contains existing assessments. We will use it to showcase the capabilities of our library and extract insights related to software quality and provenance.

[See more about SQAaaS](./yProv_and_SQAaaS/SQAaaS/README.md).  

## GitHub API rate-limit notice

GitHub allows:

- **60 requests / hour** for **anonymous** calls (no token).
- **5000 requests / hour** when you supply a **personal-access token**.
If you process many repositories for large histories you will quickly hit the 60/h ceiling and the tool will **pause** (it auto-retries after the reset time). To avoid delays we **strongly recommend** that you authenticate.

### Export it in your shell (temporary)

   ```bash
   export GITHUB_TOKEN= <replace with your GITHUB_TOKEN>
   ```

Verify quota

   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   ```

You should see "limit": 5000

## **Clone the repository and navigate to the directory:**

   ```bash
   git clone <yProv4SQA repo git URL>
   cd yProv4SQA
   ```

## **Set up the environment and install dependencies:**

### 1. Create and activate a virtual environment (recommended)

   ```bash
   # Create a virtual environment
   python3 -m venv yProv4SQA_venv

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

Note: It may take some time to fetch all reports from GitHub. You can skip this step and use the reports we have already downloaded, stored in the `./data/itwinai_SQAaaS_reports` directory.

## **Generate provenance documents:**

   ```bash
   process-provenance ./itwinai_SQAaaS_reports
   ```

This command generates a level-1 provenance document of all assessments available in `itwinai_SQAaaS_reports` directory. It will produce a `.json` file named `interTwin-eu_itwinai_prov_output.json` in `Provenance_documents` directory, which can be further used for exploration and analysis.

## **Comparing Two quality Assessments with yProv4SQA**

   ```bash
   compare ./Provenance_documents/interTwin-eu_itwinai_prov_output.json 59 87
   ```

This command generates a level-2 provenance document that captures the file changes between assessments no. 59 and assessments no. 87, integrates directly with URLs to the corresponding GitHub diff and SQAaaS reports, and stores the graph as `./Compare_commit_provenance/itwinai_commit_provenance_f7a0...3d6c_to_3076...4621.json`

## **Exploration of Provenance graph**

We can use several tools to visualize and analyze the generated provenance documents.

### 1. PROV Library Visualization

#### GraphViz prerequisite

The `json2graph` command needs the **system-level GraphViz** renderer (`dot`) in addition to the Python package:

   ```bash
   sudo apt install graphviz
   ```

This PROV library can be used to check the PROV syntax, convert the provenance document into an SVG graph for standard visualization of PROV documents, and to ensure the compliance with the W3C PROV standard.

   ```bash
   json2graph ./Provenance_documents/interTwin-eu_itwinai_prov_output.json
   json2graph ./Compare_commit_provenance/itwinai_commit_provenance_f7a0...3d6c_to_3076...4621.json
   ```

This command converts the `.json` file into an `.svg` provenance graph and saves it to `./Graph_outputs`.
The figure that appears as `Fig. 4` in the paper was generated using this command and included as an examples in `./results`.

### 2. Using yProv service and yProvExplorer

yProvExplorer is a web-based tool for visualizing and interacting with provenance documents.

Access the explorer here: [https://explorer.yprov.disi.unitn.it/](https://explorer.yprov.disi.unitn.it/)

You can either upload the `interTwin-eu_itwinai_prov_output.json` file into the explorer or drag and drop the file for visualization.  

For convenience, we have already uploaded the graphs that we used in our paper to the yProv server. You can use these URLs as input to yProvExplorer.

For the Level-1 Provenance document (Fig. 5):[http://yprov.disi.unitn.it:3000/api/v0/documents/itwinai](http://yprov.disi.unitn.it:3000/api/v0/documents/itwinai)

For the comparison of two assessments (Fig. 7): [http://yprov.disi.unitn.it:3000/api/v0/documents/gitdif](http://yprov.disi.unitn.it:3000/api/v0/documents/gitdif)

or you can open them without uploading or using the URLs as input:

- **Full assessment history of itwinai (Fig. 5):** [View Graph](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A3000%2Fapi%2Fv0%2Fdocuments%2Fitwinai)  
- **file changes between the two assessments (Fig. 7):** [View Graph](https://explorer.yprov.disi.unitn.it/?file=http%3A%2F%2Fyprov.disi.unitn.it%3A3000%2Fapi%2Fv0%2Fdocuments%2Fgitdif)

We have used the yProv service and a Neo4j database running on our internal service, which is not directly accessible externally.

To run Cypher queries, you need to install the yProv service and Neo4j database locally. To set up the environment (yProv service + Neo4j database), please follow the instructions in: [Running yProv service](./yProv_and_SQAaaS/yProv/README.md)

Once the service is running locally, you will be able to perform the Cypher queries locally.

## **Sample Neo4j Queries**

Below are the Neo4j sample queries we run to extract and analyze the results presented in the paper.

### **Cypher Neo4j Query (Listing 1)**

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

### **Cypher Neo4j Query (Listing 2)**

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

This artifact demonstrates the complete provenance-based SQA workflow from the paper. With yProv4SQA, you can collect SQAaaS reports, generate provenance documents, compare any two assessments, directly navigate to git diff of those assessments, visualize graphs, and explore them through Neo4j and the yProv service. A few examples of Cypher queries are included, and developers can extend them with their own queries as needed.
