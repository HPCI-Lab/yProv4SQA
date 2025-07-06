# Provenance as a Service
yProv is a provenance service allows scientists to manage provenance information compliant with the [W3C PROV standard](https://www.w3.org/TR/prov-overview/).

The deployment consists of two Docker containers:
- **yProv** Web Service front-end
- **Neo4J** graph database engine back-end

### Preliminary setup 
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

- Run the Neo4j container
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
- Run the yProv container
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

## Get started
You can find some ready to use examples to get started with [yProv](https://github.com/HPCI-Lab/yProv)under the [examples](https://github.com/HPCI-Lab/yProv/tree/main/examples/pta) folder.

