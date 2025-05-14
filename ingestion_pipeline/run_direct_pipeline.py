#!/usr/bin/env python3
"""
Run Direct Pipeline

This script runs the complete pipeline using direct implementations without ADK:
1. Git ingestion - pulls code from a repository
2. Code parsing - creates AST structures
3. Graph building - builds a graph representation in Neo4j
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_pipeline")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import direct runners
from direct_git_ingestion import run_git_ingestion
from direct_code_parser import run_code_parser
from direct_graph_builder import run_graph_builder


def run_pipeline(repository_url: str, branch: str = "main",
               output_dir: str = None, mode: str = "incremental",
               force_reindex: bool = False, neo4j_uri: str = None,
               neo4j_user: str = None, neo4j_password: str = None) -> Dict[str, Any]:
    """
    Run the complete pipeline on the given repository.
    
    Args:
        repository_url: URL of the repository
        branch: Branch to clone
        output_dir: Directory to save intermediate results
        mode: "incremental" or "full"
        force_reindex: Whether to force reindexing
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        
    Returns:
        Dictionary with processing results
    """
    # Create output directory if needed
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Set up file paths
    git_output = os.path.join(output_dir, "git_ingestion_output.json") if output_dir else "git_ingestion_output.json"
    parser_output = os.path.join(output_dir, "code_parser_output.json") if output_dir else "code_parser_output.json"
    graph_output = os.path.join(output_dir, "graph_builder_output.json") if output_dir else "graph_builder_output.json"
    
    # Stage 1: Git ingestion
    logger.info("STAGE 1: Git ingestion")
    git_result = run_git_ingestion(
        repository_url=repository_url,
        branch=branch,
        mode=mode,
        force_reindex=force_reindex,
        output_file=git_output
    )
    
    # Check for errors
    if git_result.get("status") != "success":
        logger.error(f"Git ingestion failed: {git_result.get('message')}")
        return {
            "status": "error",
            "stage": "git_ingestion",
            "message": git_result.get("message")
        }
    
    # Stage 2: Code parsing
    logger.info("STAGE 2: Code parsing")
    parser_result = run_code_parser(
        input_file=git_output,
        output_file=parser_output
    )
    
    # Check for errors
    if parser_result.get("status") != "success":
        logger.error(f"Code parsing failed: {parser_result.get('message')}")
        return {
            "status": "error",
            "stage": "code_parsing",
            "message": parser_result.get("message")
        }
    
    # Stage 3: Graph building
    logger.info("STAGE 3: Graph building")
    graph_result = run_graph_builder(
        input_file=parser_output,
        output_file=graph_output,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )
    
    # Check for errors
    if graph_result.get("status") != "success":
        logger.error(f"Graph building failed: {graph_result.get('message')}")
        return {
            "status": "error",
            "stage": "graph_building",
            "message": graph_result.get("message")
        }
    
    # All stages completed successfully
    return {
        "status": "success",
        "git_ingestion": git_result,
        "code_parsing": parser_result,
        "graph_building": graph_result,
        "output_files": {
            "git_output": git_output,
            "parser_output": parser_output,
            "graph_output": graph_output
        }
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the complete pipeline without ADK")
    parser.add_argument("--repo", required=True, help="Repository URL")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--output-dir", help="Directory to save results")
    parser.add_argument("--mode", choices=["incremental", "full"], default="incremental",
                      help="Processing mode")
    parser.add_argument("--force-reindex", action="store_true",
                      help="Force reindexing")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j password")
    parser.add_argument("--step", choices=["git", "parse", "graph", "all"], default="all",
                      help="Run specific step or full pipeline")
    
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
                print(f"Git files detected: {result['git_ingestion'].get('files_detected', 0)}")
                print(f"Code files processed: {result['code_parsing'].get('files_processed', 0)}")
                print(f"Graph files processed: {result['graph_building'].get('files_processed', 0)}")
                print(f"\nOutput files:")
                for name, path in result["output_files"].items():
                    print(f"  {name}: {path}")
            else:
                print(f"\nPipeline failed during {result['stage']}: {result['message']}")
                
        elif args.step == "git":
            # Run git ingestion only
            git_output = os.path.join(args.output_dir, "git_ingestion_output.json") if args.output_dir else "git_ingestion_output.json"
            
            result = run_git_ingestion(
                repository_url=args.repo,
                branch=args.branch,
                mode=args.mode,
                force_reindex=args.force_reindex,
                output_file=git_output
            )
            
            # Print summary
            if result["status"] == "success":
                print(f"\nGit ingestion completed successfully!")
                print(f"Files detected: {result.get('files_detected', 0)}")
                print(f"Output file: {git_output}")
            else:
                print(f"\nGit ingestion failed: {result.get('message')}")
                
        elif args.step == "parse":
            # Run code parser only
            git_output = os.path.join(args.output_dir, "git_ingestion_output.json") if args.output_dir else "git_ingestion_output.json"
            parser_output = os.path.join(args.output_dir, "code_parser_output.json") if args.output_dir else "code_parser_output.json"
            
            if os.path.exists(git_output):
                result = run_code_parser(
                    input_file=git_output,
                    output_file=parser_output
                )
                
                # Print summary
                if result["status"] == "success":
                    print(f"\nCode parsing completed successfully!")
                    print(f"Files processed: {result.get('files_processed', 0)}")
                    print(f"Output file: {parser_output}")
                else:
                    print(f"\nCode parsing failed: {result.get('message')}")
            else:
                print(f"\nInput file {git_output} not found. Run the git step first.")
                
        elif args.step == "graph":
            # Run graph builder only
            parser_output = os.path.join(args.output_dir, "code_parser_output.json") if args.output_dir else "code_parser_output.json"
            graph_output = os.path.join(args.output_dir, "graph_builder_output.json") if args.output_dir else "graph_builder_output.json"
            
            if os.path.exists(parser_output):
                result = run_graph_builder(
                    input_file=parser_output,
                    output_file=graph_output,
                    neo4j_uri=args.neo4j_uri,
                    neo4j_user=args.neo4j_user,
                    neo4j_password=args.neo4j_password
                )
                
                # Print summary
                if result["status"] == "success":
                    print(f"\nGraph building completed successfully!")
                    print(f"Files processed: {result.get('files_processed', 0)}")
                    print(f"Output file: {graph_output}")
                else:
                    print(f"\nGraph building failed: {result.get('message')}")
            else:
                print(f"\nInput file {parser_output} not found. Run the parse step first.")
    
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Return status code
    sys.exit(0 if result.get("status") == "success" else 1)