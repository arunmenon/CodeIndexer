#!/usr/bin/env python3
"""
Run Enhanced Graph Builder

A script that demonstrates how to run the enhanced graph builder with
the placeholder pattern for call sites and imports.
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, Any, List, Optional

# Import the direct implementations
from code_indexer.ingestion.direct.git_ingestion import DirectGitIngestionRunner
from code_indexer.ingestion.direct.code_parser import DirectCodeParserRunner
from code_indexer.ingestion.direct.enhanced_graph_builder import EnhancedGraphBuilderRunner


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run Enhanced Graph Builder with placeholder pattern')
    
    parser.add_argument('--repo-path', required=True, help='Path to the repository to process')
    parser.add_argument('--output-dir', default='./temp', help='Directory to store intermediate outputs')
    parser.add_argument('--neo4j-uri', default=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
                        help='Neo4j URI (default: from env var NEO4J_URI or bolt://localhost:7687)')
    parser.add_argument('--neo4j-user', default=os.environ.get('NEO4J_USER', 'neo4j'),
                        help='Neo4j username (default: from env var NEO4J_USER or neo4j)')
    parser.add_argument('--neo4j-password', default=os.environ.get('NEO4J_PASSWORD', 'password'),
                        help='Neo4j password (default: from env var NEO4J_PASSWORD or password)')
    parser.add_argument('--branch', default='main', 
                        help='Git branch to process (default: main)')
    parser.add_argument('--commit', default='HEAD',
                        help='Git commit to process (default: HEAD)')
    parser.add_argument('--full-indexing', action='store_true',
                        help='Perform full indexing (clear existing data)')
    parser.add_argument('--skip-git', action='store_true',
                        help='Skip git ingestion step')
    parser.add_argument('--skip-parse', action='store_true',
                        help='Skip code parsing step')
    parser.add_argument('--skip-graph', action='store_true',
                        help='Skip graph building step')
    parser.add_argument('--resolution-strategy', choices=['join', 'hashmap', 'sharded'], default='join',
                        help='Strategy for cross-file resolution (default: join)')
    parser.add_argument('--immediate-resolution', action='store_true',
                        help='Resolve placeholders immediately (vs. bulk resolution)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    return parser.parse_args()


def run_git_ingestion(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Run the git ingestion step.
    
    Args:
        args: Command line arguments
        
    Returns:
        Dictionary with git ingestion results
    """
    logging.info(f"Starting git ingestion from {args.repo_path}")
    
    # Get absolute path for local repository
    repo_path_abs = os.path.abspath(args.repo_path)
    logging.info(f"Absolute repository path: {repo_path_abs}")
    
    # Configure git ingestion
    git_config = {
        "excluded_paths": [
            ".git", "node_modules", "venv", "__pycache__", 
            "*.pyc", "*.pyo", "*.pyd", "*.so", "*.o", "*.a"
        ],
        # Add commit_history_file to ensure we use the same file as previously
        "commit_history_file": "commit_history.json"
    }
    
    git_runner = DirectGitIngestionRunner(git_config)
    
    # The DirectGitIngestionRunner expects a list of repositories in a specific format
    repo_name = os.path.basename(repo_path_abs)
    
    git_input = {
        "repositories": [
            {
                "url": repo_path_abs,  # Use absolute path
                "branch": args.branch,
                "name": repo_name
            }
        ],
        "mode": "full" if args.full_indexing else "incremental",
        "force_reindex": args.full_indexing,
        "output_file": os.path.join(args.output_dir, "git_output.json")
    }
    
    logging.info(f"Running git ingestion with input: {git_input}")
    git_result = git_runner.run(git_input)
    
    # Save output
    os.makedirs(args.output_dir, exist_ok=True)
    with open(git_input["output_file"], 'w') as f:
        json.dump(git_result, f, indent=2)
    
    # Extract files from the first result in the results array
    if git_result.get("results") and len(git_result.get("results", [])) > 0:
        repo_result = git_result["results"][0]
        files = repo_result.get("file_data", [])
        logging.info(f"Git ingestion complete, processed {len(files)} files")
        
        # Restructure the result for compatibility with the parser stage
        git_result = {
            "repository_name": repo_result.get("repository", ""),
            "repository_url": repo_result.get("url", ""),
            "files": files,
            "branch": args.branch,
            "commit": args.commit,
            "is_full_indexing": args.full_indexing or repo_result.get("is_full_indexing", False)
        }
        
        # Log details about the repository processing
        logging.info(f"Repository: {git_result['repository_name']}")
        logging.info(f"URL: {git_result['repository_url']}")
        logging.info(f"Branch: {git_result['branch']}")
        logging.info(f"Files processed: {len(files)}")
        logging.info(f"Full indexing: {git_result['is_full_indexing']}")
    else:
        logging.warning("No results found in Git ingestion output")
        # Create an empty result structure to avoid None returns
        git_result = {
            "repository_name": repo_name,
            "repository_url": repo_path_abs,
            "files": [],
            "branch": args.branch,
            "commit": args.commit,
            "is_full_indexing": args.full_indexing,
            "error": "No repository results found"
        }
    return git_result


def run_code_parser(args: argparse.Namespace, git_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code parsing step.
    
    Args:
        args: Command line arguments
        git_result: Results from git ingestion
        
    Returns:
        Dictionary with code parsing results
    """
    logging.info("Starting code parsing")
    
    # Get file data from git results
    file_data = git_result.get("files", [])
    
    # Check if we have any files to process
    if not file_data:
        logging.warning("No files to parse from git ingestion output")
        # Return an empty result structure
        empty_result = {
            "repository": git_result.get("repository_name", ""),
            "repository_url": git_result.get("repository_url", ""),
            "asts": [],
            "errors": ["No files to parse from git ingestion"],
            "files_processed": 0,
            "files_failed": 0
        }
        
        # Save the empty result
        output_file = os.path.join(args.output_dir, "parser_output.json")
        with open(output_file, 'w') as f:
            json.dump(empty_result, f, indent=2)
            
        return empty_result
    
    # Configure code parser with Tree-sitter using unified parser
    parser_config = {
        "max_workers": 4,  # Adjust based on your system
        "use_treesitter": True,
        "ast_extractor_config": {
            "use_tree_sitter": True,
            "parser_name": "unified_tree_sitter",  # Use our unified tree-sitter parser
            "tree_sitter_config": {
                "languages": ["python", "javascript", "typescript", "java"]
            }
        }
    }
    
    parser_runner = DirectCodeParserRunner(parser_config)
    
    # Get absolute path for repository
    repo_path_abs = os.path.abspath(args.repo_path)
    
    parser_input = {
        "repository": git_result.get("repository_name", ""),
        "repository_path": repo_path_abs,  # Use absolute path
        "file_data": file_data,  # Use the file_data from git results
        "url": git_result.get("repository_url", ""),
        "commit": args.commit,
        "branch": args.branch,
        "is_full_indexing": git_result.get("is_full_indexing", args.full_indexing),
        "output_file": os.path.join(args.output_dir, "parser_output.json")
    }
    
    logging.info(f"Running code parser with {len(file_data)} files")
    parser_result = parser_runner.run(parser_input)
    
    # Save output
    with open(parser_input["output_file"], 'w') as f:
        json.dump(parser_result, f, indent=2)
    
    # Log details about the parsing
    ast_count = len(parser_result.get('asts', []))
    logging.info(f"Code parsing complete, generated ASTs for {ast_count} files")
    logging.info(f"Files processed: {parser_result.get('files_processed', 0)}")
    logging.info(f"Files failed: {parser_result.get('files_failed', 0)}")
    
    return parser_result


def run_graph_builder(args: argparse.Namespace, parser_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the enhanced graph builder step.
    
    Args:
        args: Command line arguments
        parser_result: Results from code parsing
        
    Returns:
        Dictionary with graph building results
    """
    logging.info("Starting enhanced graph building with placeholder pattern")
    
    # Get ASTs from parser results
    asts = parser_result.get("asts", [])
    
    # Check if we have any ASTs to process
    if not asts:
        logging.warning("No ASTs to process from parser output")
        # Return an empty result structure
        empty_result = {
            "repository": parser_result.get("repository", ""),
            "repository_url": parser_result.get("repository_url", ""),
            "files_processed": 0,
            "files_failed": 0,
            "errors": ["No ASTs to process from parser output"],
            "graph_stats": {
                "nodes_created": 0,
                "relationships_created": 0,
                "call_sites": 0,
                "resolved_calls": 0,
                "imported_modules": 0
            }
        }
        
        # Save the empty result
        output_file = os.path.join(args.output_dir, "graph_output.json")
        with open(output_file, 'w') as f:
            json.dump(empty_result, f, indent=2)
            
        return empty_result
    
    # Configure enhanced graph builder
    graph_config = {
        "neo4j_config": {
            "NEO4J_URI": args.neo4j_uri,
            "NEO4J_USER": args.neo4j_user,
            "NEO4J_PASSWORD": args.neo4j_password
        },
        "create_placeholders": True,
        "immediate_resolution": args.immediate_resolution,
        "resolution_strategy": args.resolution_strategy,
        "use_inheritance": True,
        "detect_calls": True,
        "use_imports": True
    }
    
    # Validate Neo4j connection before proceeding
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            args.neo4j_uri, 
            auth=(args.neo4j_user, args.neo4j_password)
        )
        # Test the connection
        with driver.session() as session:
            result = session.run("RETURN 1")
            result.single()
        driver.close()
        logging.info("Neo4j connection successful")
    except Exception as e:
        logging.error(f"Failed to connect to Neo4j: {e}")
        # Return an error result
        error_result = {
            "repository": parser_result.get("repository", ""),
            "repository_url": parser_result.get("repository_url", ""),
            "files_processed": 0,
            "files_failed": 0,
            "errors": [f"Neo4j connection failed: {str(e)}"],
            "graph_stats": {
                "nodes_created": 0,
                "relationships_created": 0,
                "call_sites": 0,
                "resolved_calls": 0,
                "imported_modules": 0
            }
        }
        
        # Save the error result
        output_file = os.path.join(args.output_dir, "graph_output.json")
        with open(output_file, 'w') as f:
            json.dump(error_result, f, indent=2)
            
        return error_result
    
    # Create graph builder instance
    graph_runner = EnhancedGraphBuilderRunner(graph_config)
    
    # Prepare input for graph builder
    graph_input = {
        "repository": parser_result.get("repository", ""),
        "repository_url": parser_result.get("repository_url", ""),
        "commit": args.commit,
        "branch": args.branch,
        "asts": asts,
        "is_full_indexing": parser_result.get("is_full_indexing", args.full_indexing)
    }
    
    logging.info(f"Running graph builder with {len(asts)} ASTs")
    
    try:
        graph_result = graph_runner.run(graph_input)
        
        # Save output
        output_file = os.path.join(args.output_dir, "graph_output.json")
        with open(output_file, 'w') as f:
            json.dump(graph_result, f, indent=2)
        
        # Log detailed results
        logging.info(f"Graph building complete, processed {graph_result.get('files_processed', 0)} files")
        logging.info(f"Created {graph_result.get('graph_stats', {}).get('call_sites', 0)} call sites")
        logging.info(f"Resolved {graph_result.get('graph_stats', {}).get('resolved_calls', 0)} function calls")
        logging.info(f"Imported {graph_result.get('graph_stats', {}).get('imported_modules', 0)} modules")
        
        return graph_result
    except Exception as e:
        logging.error(f"Graph building failed: {e}", exc_info=True)
        # Return an error result
        error_result = {
            "repository": parser_result.get("repository", ""),
            "repository_url": parser_result.get("repository_url", ""),
            "files_processed": 0,
            "files_failed": len(asts),
            "errors": [f"Graph building failed: {str(e)}"],
            "graph_stats": {
                "nodes_created": 0,
                "relationships_created": 0,
                "call_sites": 0,
                "resolved_calls": 0,
                "imported_modules": 0
            }
        }
        
        # Save the error result
        output_file = os.path.join(args.output_dir, "graph_output.json")
        with open(output_file, 'w') as f:
            json.dump(error_result, f, indent=2)
            
        return error_result


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)
    
    logging.info("Starting enhanced graph building pipeline")
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Step 1: Git Ingestion
        git_result = {}
        if not args.skip_git:
            git_result = run_git_ingestion(args)
        else:
            # Load previous git results if available
            git_output_file = os.path.join(args.output_dir, "git_output.json")
            if os.path.exists(git_output_file):
                with open(git_output_file, 'r') as f:
                    git_result = json.load(f)
                logging.info(f"Loaded previous git results: {len(git_result.get('files', []))} files")
            else:
                logging.error("Skipping git but no previous git results found")
                sys.exit(1)
        
        # Step 2: Code Parsing
        parser_result = {}
        if not args.skip_parse:
            parser_result = run_code_parser(args, git_result)
        else:
            # Load previous parser results if available
            parser_output_file = os.path.join(args.output_dir, "parser_output.json")
            if os.path.exists(parser_output_file):
                with open(parser_output_file, 'r') as f:
                    parser_result = json.load(f)
                logging.info(f"Loaded previous parser results: {len(parser_result.get('asts', []))} ASTs")
            else:
                logging.error("Skipping parse but no previous parser results found")
                sys.exit(1)
        
        # Step 3: Enhanced Graph Building
        graph_result = {}
        if not args.skip_graph:
            graph_result = run_graph_builder(args, parser_result)
            
            # Print graph building summary
            print("\n" + "="*80)
            print("ENHANCED GRAPH BUILDING COMPLETED SUCCESSFULLY")
            print("="*80)
            print(f"Repository: {git_result.get('repository_name', '')}")
            print(f"Branch: {args.branch}")
            print(f"Commit: {args.commit}")
            print(f"Files Processed: {graph_result.get('files_processed', 0)}")
            print(f"Files Failed: {graph_result.get('files_failed', 0)}")
            print("\nGraph Statistics:")
            for key, value in graph_result.get('graph_stats', {}).items():
                print(f"  {key}: {value}")
            print("\nResults saved to:")
            print(f"  {os.path.join(args.output_dir, 'graph_output.json')}")
            print("="*80)
        else:
            # Print parsing summary
            print("\n" + "="*80)
            print("CODE PARSING COMPLETED SUCCESSFULLY (Skipped Graph Building)")
            print("="*80)
            print(f"Repository: {git_result.get('repository_name', '')}")
            print(f"Branch: {args.branch}")
            print(f"Commit: {args.commit}")
            print(f"ASTs Generated: {len(parser_result.get('asts', []))}")
            print("\nResults saved to:")
            print(f"  {os.path.join(args.output_dir, 'parser_output.json')}")
            print("="*80)
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
    
    logging.info("Pipeline completed successfully")


if __name__ == "__main__":
    main()