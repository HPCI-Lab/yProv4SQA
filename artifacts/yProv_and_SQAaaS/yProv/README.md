# **Provenance as a Service**

yProv is a provenance service allows scientists to manage provenance information compliant with the [W3C PROV standard](https://www.w3.org/TR/prov-overview/).

The deployment consists of two Docker containers:

- **yProv** Web Service front-end
- **Neo4J** graph database engine back-end

## **Preliminary setup**

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

### Deployment from DockerHub

- **Run the Neo4j container**

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

- **Run the yProv container**

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

### **Neo4j for Provenance Visualization and Data Exploration**

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
- 
