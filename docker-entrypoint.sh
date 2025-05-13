#!/bin/bash
set -e

# Wait for dependencies to be available
echo "Waiting for Neo4j..."
timeout=60
until curl -s http://neo4j:7474 > /dev/null || [ $timeout -le 0 ]; do
    echo "Neo4j not available yet, waiting..."
    sleep 2
    ((timeout--))
done

if [ $timeout -le 0 ]; then
    echo "Neo4j did not start in time, continuing anyway..."
fi

echo "Waiting for Milvus..."
timeout=60
until curl -s http://milvus:9091/healthz > /dev/null || [ $timeout -le 0 ]; do
    echo "Milvus not available yet, waiting..."
    sleep 2
    ((timeout--))
done

if [ $timeout -le 0 ]; then
    echo "Milvus did not start in time, continuing anyway..."
fi

# Create default vector store collection if it doesn't exist
echo "Setting up vector store..."
python -m code_indexer.utils.setup_vector_store

# Check if a command was provided
if [ $# -gt 0 ]; then
    # Execute the provided command
    echo "Starting Code Indexer with command: $@"
    exec "$@"
else
    # Default to running the API with ADK Runner
    echo "Starting Code Indexer API with ADK Runner..."
    exec adk run api --team teams/query_team.yaml --port 8000
fi