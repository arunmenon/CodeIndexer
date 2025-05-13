# Changelog

## 0.2.0 (2024-05-14)

### Features
- Updated to use Google ADK v0.6.0+
- Added support for Neo4j 5.9 for graph database
- Added support for Milvus 2.4 for vector storage
- Created Docker compose setup for local development
- Implemented core indexing pipeline with Git ingestion, parsing, and embedding
- Implemented search with both vector and graph-based approaches
- Added dead code detection capability

### Infrastructure
- Docker compose configuration for Neo4j and Milvus
- Team YAML files for ADK Runner
- Entry point script with dependency waiting
- Simplified vector store support to focus exclusively on Milvus

## 0.1.0 (2024-03-01)

### Features
- Initial project structure
- Basic agent interfaces