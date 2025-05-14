"""
Pipeline Stages

This package contains the individual stages of the CodeIndexer ingestion pipeline:
1. git - Repository cloning and file extraction
2. parse - Code parsing and AST generation
3. graph - Graph database integration
4. chunk - Code chunking for embeddings
5. embed - Vector embedding generation
"""