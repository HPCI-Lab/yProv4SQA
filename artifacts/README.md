# Artifact for “A Provenance-Based Architecture for Traceability in Software Quality Assurance Pipelines” (ICSA 2026)

To gain complete insights about software quality evaluation, we introduce the concept of provenance for Software Quality Assurance pipelines called yProv4SQA, which is used for tracking the evolution of software quality over time by generating detailed provenance documents during software development.

In this example, we demonstrate how to use our library by analyzing the [itwinai GitHub repository](https://github.com/interTwin-eu/itwinai).  
This repository already utilizes [SQAaaS](https://docs.sqaaas.eosc-synergy.eu/) and contains existing assessments. We will use it to showcase the capabilities of our library and extract insights related to software quality and provenance.


## 1. GitHub API rate-limit notice

GitHub allows:

- **60 requests / hour** for **anonymous** calls (no token).
- **5000 requests / hour** when you supply a **personal-access token**.
If you process many repositories for large histories you will quickly hit the 60/h ceiling and the tool will **pause** (it auto-retries after the reset time). To avoid delays we **strongly recommend** that you authenticate.

### 1.1. Export it in your shell (temporary)

   ```bash
   export GITHUB_TOKEN= <replace with your GITHUB_TOKEN>
   ```

Verify quota

   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   ```

You should see "limit": 5000

## **2. Clone the repository and navigate to the directory:**

   ```bash
   git clone <yProv4SQA repo git URL>
   cd yProv4SQA
   ```

## **3. Set up the environment and install dependencies:**

### 3.1. Create and activate a virtual environment (recommended)

   ```bash
   # Create a virtual environment
   python3 -m venv yProv4SQA_venv

   # Activate the virtual environment
   source yProv4SQA_venv/bin/activate
   ```

This ensures that all dependencies are installed in an isolated environment, preventing conflicts with other Python packages on your system.

### **3.2. Install the library and required dependencies:**

   ```bash
   pip install -e .
   pip install requests
   ```

This installs the library and also installs the requests library, which is required to run the examples.

## **4. Fetch SQA reports:**

   ```bash
   fetch-sqa-reports itwinai
   ```

This command fetches all SQAaaS assessments for the `itwinai` repository from the [EOSC-Synergy GitHub space](https://github.com/EOSC-synergy). The library then removes duplicates and outdated assessments, and produces a final cleaned directory used to generate the provenance document. For this example, the output directory will be created as `./itwinai_SQAaaS_reports`.

Note: It may take some time to fetch all reports from GitHub. You can skip this step and use the reports we have already downloaded, stored in the `./data/itwinai_SQAaaS_reports` directory.

## **5. Generate provenance documents:**

   ```bash
   process-provenance ./itwinai_SQAaaS_reports
   ```

This command generates a level-1 provenance document of all assessments available in `itwinai_SQAaaS_reports` directory. It will produce a `.json` file named `interTwin-eu_itwinai_prov_output.json` in `Provenance_documents` directory, which can be further used for exploration and analysis.

## **6. Comparing Two quality Assessments with yProv4SQA**

   ```bash
   compare ./Provenance_documents/interTwin-eu_itwinai_prov_output.json 59 87
   ```

This command generates a level-2 provenance document that captures the file changes between assessments no. 59 and assessments no. 87, integrates directly with URLs to the corresponding GitHub diff and SQAaaS reports, and stores the graph as `./Compare_commit_provenance/itwinai_commit_provenance_f7a0...3d6c_to_3076...4621.json`

## **7. Exploration of Provenance graph**

We can use several tools to visualize and analyze the generated provenance documents.

### 7.1. PROV Library Visualization

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

### 7.2. Using yProv service and yProvExplorer

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

To run Cypher queries, you need to install the yProv service and Neo4j database locally (Step 8). To set up the environment (yProv service + Neo4j database). Once the service is running locally, you will be able to perform the Cypher queries locally reported below.

## **8. Running yProv Service**

yProv is a provenance service allows scientists to manage provenance information compliant with the [W3C PROV standard](https://www.w3.org/TR/prov-overview/).

The deployment consists of two Docker containers:

- **yProv** Web Service front-end
- **Neo4J** graph database engine back-end

### **8.1. Preliminary setup**

- Create a named volume to make Neo4j data persistent

```bash
docker volume create neo4j_data
```

- Create a named volume to export logs to the host machine

```bash
docker volume create neo4j_logs
```

- Create a named volume to make yProv configuration and data persistent to the host machine

```bash
docker volume create yprov_data
```

Create a Docker network to enable communication between the two Docker containers

- Create a Docker network

```bash
docker network create yprov_net
```

### 8.2. Deployment from DockerHub

- **8.2.1. Run the Neo4j container**

```bash
    docker run \
        --name db \
        --network=yprov_net \
        -p 7474:7474 -p 7687:7687 \
        -d \
        -v neo4j_data:/data \
        -v neo4j_logs:/logs \
        -v $HOME/neo4j/import:/var/lib/neo4j/import \
        -v $HOME/neo4j/plugins:/plugins \
        --env NEO4J_AUTH=neo4j/password \
        --env NEO4J_ACCEPT_LICENSE_AGREEMENT=eval \
        -e NEO4J_apoc_export_file_enabled=true \
        -e NEO4J_apoc_import_file_enabled=true \
        -e NEO4J_apoc_import_file_use__neo4j__config=true \
        -e NEO4J_PLUGINS=\[\"apoc\"\] \
        neo4j:enterprise
```

- **8.2.2. Run the yProv container**

```bash
    docker run \
        --restart on-failure \
        --name web \
        --network=yprov_net \
        -p 3000:3000 \
        -d \
        -v yprov_data:/app/conf \
        --env USER=neo4j \
        --env PASSWORD=password \
        hpci/yprov:latest
```

### **8.3. Neo4j for Provenance Visualization and Data Exploration**

After registering with the service, provenance documents can be uploaded and automatically synchronized with a Neo4j graph database for exploration.

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
[http://localhost:7474/browser](http://localhost:7474/browser)

**NOTE** – before running the queries below, select the database **"itwinai"** in the Neo4j browser and use the following credentials while login:  

- **Username**: `neo4j`
- **Password**: `password` (default set in docker-compose)


## **9. Sample Neo4j Queries**

Below are the Neo4j sample queries we run to extract and analyze the results presented in the paper.

### **9.1. Cypher Neo4j Query (Listing 1)**

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

### **9.2. Cypher Neo4j Query (Listing 2)**

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
