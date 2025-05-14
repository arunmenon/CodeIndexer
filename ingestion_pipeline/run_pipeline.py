#!/usr/bin/env python3
"""
Code Indexer Ingestion Pipeline

This script runs the complete ingestion pipeline without any ADK dependencies:
1. Git ingestion - pulls code from a repository
2. Code parsing - creates AST structures
3. Graph building - builds a graph representation in Neo4j

This standalone implementation represents Stage 1 of the CodeIndexer system.
It creates the foundational code structure representation that can later
be enriched with semantic understanding.
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
logger = logging.getLogger("ingestion_pipeline")

# Import direct runners
from direct_git_ingestion import DirectGitIngestionRunner
from direct_code_parser import DirectCodeParserRunner
from direct_graph_builder import DirectGraphBuilderRunner


def run_git_ingestion(repository_url: str, branch: str = "main", mode: str = "incremental",
                     force_reindex: bool = False, output_file: str = None) -> Dict[str, Any]:
    """
    Run git ingestion to pull code from a repository.
    
    Args:
        repository_url: URL of the repository
        branch: Branch to clone
        mode: "incremental" or "full"
        force_reindex: Whether to force reindexing
        output_file: Path to save output
        
    Returns:
        Dictionary with processing results
    """
    # Create git ingestion runner
    config = {
        "repositories": [
            {
                "url": repository_url,
                "branch": branch
            }
        ],
        "mode": mode,
        "force_reindex": force_reindex,
        "workspace_dir": "./workspace"
    }
    
    runner = DirectGitIngestionRunner(config)
    result = runner.run(config)
    
    # Add status field for consistency
    if "error" in result:
        result["status"] = "error"
        result["message"] = result.pop("error")
    else:
        result["status"] = "success"
    
    # Save output if requested
    if output_file and result["status"] == "success":
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
    
    return result


def run_code_parser(input_file: str, output_file: str = None) -> Dict[str, Any]:
    """
    Run code parser to create AST structures.
    
    Args:
        input_file: Path to input file with git ingestion results
        output_file: Path to save output
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Load input from file
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        
        # Get the repository result with file data
        file_data = []
        for repo_result in input_data.get("results", []):
            if repo_result.get("status") == "success":
                if "processed_files" in repo_result:
                    file_data.extend(repo_result.get("processed_files", []))
                elif "file_data" in repo_result:
                    file_data.extend(repo_result.get("file_data", []))
        
        if not file_data:
            return {
                "status": "error",
                "message": "No file data found in input"
            }
        
        # Create input for code parser
        parser_input = {
            "file_data": file_data,
            "repository": file_data[0].get("repository", ""),
            "url": file_data[0].get("url", ""),
            "commit": file_data[0].get("commit", ""),
            "branch": file_data[0].get("branch", "main"),
            "is_full_indexing": input_data.get("mode", "incremental") == "full"
        }
        
        # Create code parser and run it
        parser = DirectCodeParserRunner()
        result = parser.run(parser_input)
        
        # Add status field for consistency
        if "error" in result:
            result["status"] = "error"
            result["message"] = result.pop("error")
        else:
            result["status"] = "success"
        
        # Save output if requested
        if output_file and result["status"] == "success":
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in code parser: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def run_graph_builder(input_file: str, output_file: str = None, neo4j_uri: str = None,
                    neo4j_user: str = None, neo4j_password: str = None) -> Dict[str, Any]:
    """
    Run graph builder to create graph representation.
    
    Args:
        input_file: Path to input file with code parser results
        output_file: Path to save output
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Load input from file
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        
        # Set Neo4j connection parameters
        neo4j_config = {
            "NEO4J_URI": neo4j_uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": neo4j_user or os.environ.get("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": neo4j_password or os.environ.get("NEO4J_PASSWORD", "password")
        }
        
        # Create graph builder and run it
        builder = DirectGraphBuilderRunner({"neo4j_config": neo4j_config})
        result = builder.run(input_data)
        
        # Add status field for consistency
        if "error" in result:
            result["status"] = "error"
            result["message"] = result.pop("error")
        else:
            result["status"] = "success"
        
        # Save output if requested
        if output_file and result["status"] == "success":
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in graph builder: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


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
    parser = argparse.ArgumentParser(description="Run the CodeIndexer ingestion pipeline")
    parser.add_argument("--repo", required=True, help="Repository URL")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--output-dir", help="Directory to save results")
    parser.add_argument("--mode", choices=["incremental", "full"], default="incremental",
                      help="Processing mode")
    parser.add_argument("--force-reindex", action="store_true",
                      help="Force reindexing")
    parser.add_argument("--neo4j-uri", help="Neo4j URI")
    parser.add_argument("--neo4j-user", help="Neo4j username")
    parser.add_argument("--neo4j-password", help="Neo4j password")
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
                print(f"Git files processed: {result['git_ingestion'].get('results', [{}])[0].get('files_processed', 0)}")
                print(f"AST files processed: {result['code_parsing'].get('files_parsed', 0)}")
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
                print(f"Files detected: {result.get('results', [{}])[0].get('files_processed', 0)}")
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
                    print(f"Files processed: {result.get('files_parsed', 0)}")
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