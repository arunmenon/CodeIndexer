#!/usr/bin/env python3
"""
Run Code Indexer Ingestion Pipeline

This is the main entry point for the non-agentic Code Indexer ingestion pipeline.
It represents Stage 1 of the system - creating a foundational code structure representation
without requiring LLM intelligence or ADK dependencies.
"""

import sys
import os

# Add this script's directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the pipeline runner
from ingestion_pipeline.run_pipeline import run_pipeline

if __name__ == "__main__":
    # We're just importing and executing the main pipeline script
    from ingestion_pipeline.run_pipeline import parser, logger
    
    args = parser.parse_args()
    
    try:
        if args.step == "all":
            # Run full pipeline
            result = run_pipeline(
                repository_url=args.repo,
                branch=args.branch,
                output_dir=args.output_dir,
                mode=args.mode,
                force_reindex=args.force_reindex,
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password
            )
            
            # Print summary
            if result["status"] == "success":
                print("\nPipeline completed successfully!")
                print(f"Git files processed: {result['git_ingestion'].get('results', [{}])[0].get('files_processed', 0)}")
                print(f"AST files processed: {result['code_parsing'].get('files_parsed', 0)}")
                print(f"Graph files processed: {result['graph_building'].get('files_processed', 0)}")
                print(f"\nOutput files:")
                for name, path in result["output_files"].items():
                    print(f"  {name}: {path}")
            else:
                print(f"\nPipeline failed during {result['stage']}: {result['message']}")
                sys.exit(1)
        else:
            # Execute the specific step from the imported module
            # The implementation is already in the imported module
            pass
    
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    sys.exit(0)