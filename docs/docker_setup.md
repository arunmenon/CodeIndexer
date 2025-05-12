# Docker Setup Guide

This guide explains how to set up and run the Code Indexer using Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- At least 8GB of RAM available for Docker
- At least 20GB of disk space

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/yourusername/CodeIndexer.git
cd CodeIndexer
```

2. Start the services:

```bash
docker-compose up -d
```

This will start all the required services:
- Neo4j (graph database)
- Milvus (vector database and its dependencies)
- Code Indexer API
- Code Indexer CLI (for interactive use)

3. Check that services are running:

```bash
docker-compose ps
```

## Accessing Services

### Neo4j Browser

The Neo4j browser is available at [http://localhost:7474](http://localhost:7474).
- Username: `neo4j`
- Password: `password`

### Milvus Console

The Milvus console is available at [http://localhost:9001](http://localhost:9001).
- Username: `minioadmin`
- Password: `minioadmin`

### Code Indexer API

The API is available at [http://localhost:8000](http://localhost:8000).

## Using the Code Indexer

### Indexing a Repository

You can index a Git repository by making a POST request to the API:

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{
    "repositories": [
      {
        "url": "https://github.com/example/repo",
        "branch": "main",
        "name": "example-repo"
      }
    ],
    "mode": "full"
  }'
```

### Searching Code

You can search the indexed code by making a GET request to the API:

```bash
curl -X GET http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does authentication work?",
    "search_type": "hybrid",
    "max_results": 5
  }'
```

### Using the CLI

You can connect to the CLI container for interactive use:

```bash
docker-compose exec code-indexer-cli bash
```

From there, you can run the CLI tool:

```bash
python -m code_indexer.cli.search_cli --help
```

## Environment Variables

The following environment variables can be set in the `docker-compose.yml` file:

### Database Configuration

- `NEO4J_URI`: URI for the Neo4j database (default: `bolt://neo4j:7687`)
- `NEO4J_USER`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password (default: `password`)
- `NEO4J_DATABASE`: Neo4j database name (default: `neo4j`)
- `MILVUS_HOST`: Milvus host (default: `milvus`)
- `MILVUS_PORT`: Milvus port (default: `19530`)
- `VECTOR_STORE`: Vector store type (default: `milvus`)

### Embedding Configuration

- `EMBEDDING_MODEL_TYPE`: Type of embedding model (default: `sentence_transformers`)
- `EMBEDDING_MODEL_NAME`: Name of the embedding model (default: `all-MiniLM-L6-v2`)
- `EMBEDDING_DIMENSION`: Dimension of the embedding vectors (default: `384`)

### Other Configuration

- `WORKSPACE_DIR`: Directory for storing temporary files (default: `/app/workspace`)
- `MAX_FILE_SIZE`: Maximum file size to process in bytes (default: `1048576` - 1MB)
- `API_PORT`: Port for the API server (default: `8000`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Data Persistence

The following directories are mounted as volumes to persist data:

- `./volumes/neo4j`: Neo4j database files
- `./volumes/milvus`: Milvus database files
- `./volumes/etcd`: etcd data for Milvus
- `./volumes/minio`: MinIO data for Milvus
- `./volumes/workspace`: Workspace directory for the Code Indexer
- `./volumes/config`: Configuration files
- `./volumes/logs`: Log files

## Shutting Down

To stop all services:

```bash
docker-compose down
```

To stop and remove all data:

```bash
docker-compose down -v
```

## Troubleshooting

### Service Fails to Start

If a service fails to start, check the logs:

```bash
docker-compose logs [service-name]
```

For example:

```bash
docker-compose logs neo4j
docker-compose logs milvus
docker-compose logs code-indexer
```

### Resource Constraints

If you're experiencing issues with performance, make sure Docker has enough resources:

- Increase the memory allocation in Docker settings
- Increase the CPU allocation in Docker settings

### Database Connection Issues

If the Code Indexer fails to connect to Neo4j or Milvus:

- Check that the services are running:
  ```bash
  docker-compose ps
  ```
- Check the logs for connection errors:
  ```bash
  docker-compose logs code-indexer
  ```
- Try restarting the services:
  ```bash
  docker-compose restart neo4j milvus code-indexer
  ```