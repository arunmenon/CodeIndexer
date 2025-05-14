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
    
    # Configure git ingestion
    git_config = {
        "excluded_paths": [
            ".git", "node_modules", "venv", "__pycache__", 
            "*.pyc", "*.pyo", "*.pyd", "*.so", "*.o", "*.a"
        ]
    }
    
    git_runner = DirectGitIngestionRunner(git_config)
    
    git_input = {
        "repository_path": args.repo_path,
        "repository_url": "",  # Could be determined from git config
        "repository_name": os.path.basename(os.path.abspath(args.repo_path)),
        "branch": args.branch,
        "commit": args.commit,
        "output_file": os.path.join(args.output_dir, "git_output.json")
    }
    
    git_result = git_runner.run(git_input)
    
    # Save output
    os.makedirs(args.output_dir, exist_ok=True)
    with open(git_input["output_file"], 'w') as f:
        json.dump(git_result, f, indent=2)
    
    logging.info(f"Git ingestion complete, processed {len(git_result.get('files', []))} files")
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
    
    # Configure code parser
    parser_config = {
        "max_workers": 4,  # Adjust based on your system
        "use_treesitter": True,
        "treesitter_langs": ["python", "javascript", "typescript", "java", "c", "cpp", "go"]
    }
    
    parser_runner = DirectCodeParserRunner(parser_config)
    
    parser_input = {
        "repository": git_result.get("repository_name", ""),
        "repository_path": args.repo_path,
        "files": git_result.get("files", []),
        "output_file": os.path.join(args.output_dir, "parser_output.json")
    }
    
    parser_result = parser_runner.run(parser_input)
    
    # Save output
    with open(parser_input["output_file"], 'w') as f:
        json.dump(parser_result, f, indent=2)
    
    logging.info(f"Code parsing complete, generated ASTs for {len(parser_result.get('asts', []))} files")
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
    
    graph_runner = EnhancedGraphBuilderRunner(graph_config)
    
    graph_input = {
        "repository": parser_result.get("repository", ""),
        "repository_url": parser_result.get("repository_url", ""),
        "commit": args.commit,
        "branch": args.branch,
        "asts": parser_result.get("asts", []),
        "is_full_indexing": args.full_indexing
    }
    
    graph_result = graph_runner.run(graph_input)
    
    # Save output
    output_file = os.path.join(args.output_dir, "graph_output.json")
    with open(output_file, 'w') as f:
        json.dump(graph_result, f, indent=2)
    
    logging.info(f"Graph building complete, processed {graph_result.get('files_processed', 0)} files")
    logging.info(f"Created {graph_result.get('graph_stats', {}).get('call_sites', 0)} call sites")
    logging.info(f"Resolved {graph_result.get('graph_stats', {}).get('resolved_calls', 0)} function calls")
    
    return graph_result


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
        graph_result = run_graph_builder(args, parser_result)
        
        # Print summary
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
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
    
    logging.info("Pipeline completed successfully")


if __name__ == "__main__":
    main()