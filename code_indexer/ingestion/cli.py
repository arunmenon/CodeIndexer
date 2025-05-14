#!/usr/bin/env python3
"""
CodeIndexer Ingestion CLI

Command-line interface for running the CodeIndexer ingestion pipeline.
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any, List, Optional

from code_indexer.ingestion.pipeline import run_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingestion_cli")


def main():
    """Main entry point for the ingestion CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the CodeIndexer ingestion pipeline")
    parser.add_argument("--repo", required=True, help="Repository URL or local path")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--output-dir", help="Directory to save results")
    parser.add_argument("--mode", choices=["incremental", "full"], default="incremental",
                       help="Processing mode")
    parser.add_argument("--force-reindex", action="store_true",
                       help="Force reindexing")
    parser.add_argument("--neo4j-uri", help="Neo4j URI", 
                       default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", help="Neo4j username",
                       default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", help="Neo4j password",
                       default=os.environ.get("NEO4J_PASSWORD", "password"))
    parser.add_argument("--vector-store", choices=["milvus", "qdrant"], default="milvus",
                       help="Vector store to use")
    parser.add_argument("--vector-store-uri", help="Vector store URI",
                       default=os.environ.get("VECTOR_STORE_URI", "localhost:19530"))
    parser.add_argument("--step", choices=["git", "parse", "graph", "chunk", "embed", "all"], 
                       default="all", help="Run specific step or full pipeline")

    # Add options for detection of dead code
    parser.add_argument("--detect-dead-code", action="store_true",
                       help="Run dead code detection during ingestion")
    
    args = parser.parse_args()
    
    try:
        # Create pipeline configuration
        config = {
            "repository_url": args.repo,
            "branch": args.branch,
            "output_dir": args.output_dir,
            "mode": args.mode,
            "force_reindex": args.force_reindex,
            "neo4j_uri": args.neo4j_uri,
            "neo4j_user": args.neo4j_user,
            "neo4j_password": args.neo4j_password,
            "vector_store": args.vector_store,
            "vector_store_uri": args.vector_store_uri,
            "step": args.step,
            "detect_dead_code": args.detect_dead_code
        }
        
        # Run the pipeline
        result = run_pipeline(config)
        
        # Print summary
        if result["status"] == "success":
            print("\nPipeline completed successfully!")
            print(f"Files processed: {result.get('files_processed', 0)}")
            if args.output_dir:
                print(f"Results saved to: {args.output_dir}")
            
            # Print stage-specific stats
            for stage, stats in result.get("stage_stats", {}).items():
                print(f"\n{stage.capitalize()} stage:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
        else:
            print(f"\nPipeline failed during {result.get('stage', 'unknown')}: {result.get('message', 'Unknown error')}")
            return 1
    
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())