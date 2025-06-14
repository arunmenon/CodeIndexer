#!/usr/bin/env python3
"""
CodeIndexer CLI Pipeline

A comprehensive tool for analyzing code repositories through a multi-stage pipeline:
1. Git Ingestion - Extract files and metadata from git repositories
2. Code Parsing - Generate Abstract Syntax Trees (ASTs) from source code
3. Graph Building - Create a knowledge graph with cross-file code relationships

This pipeline implements the placeholder pattern for resolving references
across files, enabling accurate call site analysis and dependency tracking.
"""

import os
import sys
import json
import logging
import argparse
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import the direct implementations
from code_indexer.ingestion.direct.git_ingestion import DirectGitIngestionRunner
from code_indexer.ingestion.direct.code_parser import DirectCodeParserRunner
from code_indexer.ingestion.stages.graph import process_graph_building


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with intuitive grouping and descriptions."""
    parser = argparse.ArgumentParser(
        description="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              CODE INDEXER CLI                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

A powerful tool for code analysis that extracts semantic information from 
repositories and builds a queryable knowledge graph.

This pipeline follows three main stages:
  1. 📦 Git Ingestion:    Extract files and metadata from repositories
  2. 🔍 Code Parsing:     Generate Abstract Syntax Trees (ASTs) from source code
  3. 🔄 Graph Building:   Create a knowledge graph with code relationships
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═════════════════════════════════ EXAMPLES ═════════════════════════════════════

Basic Usage:
  # Process a local repository:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project

  # Process a remote GitHub repository:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git

Common Workflows:
  # Full indexing (clear existing data) with specific output directory:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project --full-indexing --output-dir ./my_results

  # Run only git and parsing stages (skip graph building):
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project --skip-graph

  # Use cached results and only run graph building:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project --skip-git --skip-parse

Advanced Usage:
  # Specify branch and commit with immediate placeholder resolution:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project --branch develop --commit HEAD --immediate-resolution

  # Use custom Neo4j connection:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_project --neo4j-uri bolt://neo4j-server:7687 --neo4j-user admin --neo4j-password secret
  
  # Use SSH authentication for private repositories:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/org/private-repo.git --ssh-auth

  # Use SSH authentication with a specific SSH key:
  python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/org/private-repo.git --ssh-auth --ssh-key ~/.ssh/id_rsa
        """
    )
    
    # Required arguments
    required = parser.add_argument_group('📌 Required Arguments')
    required.add_argument('--repo-path', required=True, metavar='PATH_OR_URL',
                        help='Path to local repository or URL of remote repository (GitHub, GitLab, etc.)')
    
    # Basic options
    basic = parser.add_argument_group('🔧 Basic Options')
    basic.add_argument('--output-dir', metavar='DIR',
                     help='Directory to store outputs (default: ./output/<repo_name>)')
    basic.add_argument('--branch', default='main', metavar='BRANCH',
                     help='Git branch to process (default: main)')
    basic.add_argument('--commit', default='HEAD', metavar='COMMIT_HASH',
                     help='Git commit to process (default: HEAD)')
    basic.add_argument('--verbose', action='store_true', 
                     help='Enable verbose logging with detailed debug information')
    
    # Processing options
    processing = parser.add_argument_group('🔄 Processing Options')
    processing.add_argument('--full-indexing', action='store_true',
                          help='Perform full indexing (clear existing data and reindex everything)')
    processing.add_argument('--skip-git', action='store_true',
                          help='Skip git ingestion step (use previous results from output directory)')
    processing.add_argument('--skip-parse', action='store_true',
                          help='Skip code parsing step (use previous results from output directory)')
    processing.add_argument('--skip-graph', action='store_true',
                          help='Skip graph building step (stop after parsing)')
    
    # Git authentication options
    git_auth = parser.add_argument_group('🔐 Git Authentication')
    git_auth.add_argument('--ssh-auth', action='store_true',
                        help='Use SSH authentication for Git operations (required for many private repositories)')
    git_auth.add_argument('--ssh-key', metavar='KEY_PATH',
                        help='Path to SSH private key for Git authentication (default: uses SSH agent or CODEINDEXER_SSH_KEY env var)')
    
    # Advanced options
    advanced = parser.add_argument_group('⚙️ Advanced Options')
    advanced.add_argument('--resolution-strategy', choices=['join', 'hashmap', 'sharded'], default='join', metavar='STRATEGY',
                        help="""Strategy for cross-file reference resolution:
                        join - Standard SQL-like joins (default, best for small/medium repos)
                        hashmap - In-memory hashmap (faster for medium repos)
                        sharded - Distributed resolution (best for very large repos)""")
    advanced.add_argument('--immediate-resolution', action='store_true',
                        help='Resolve placeholders immediately rather than in bulk (slower but lower memory usage)')
    
    # Neo4j connection
    neo4j = parser.add_argument_group('🔌 Neo4j Connection')
    neo4j.add_argument('--neo4j-uri', default=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'), metavar='URI',
                     help='Neo4j URI (default: from env var NEO4J_URI or bolt://localhost:7687)')
    neo4j.add_argument('--neo4j-user', default=os.environ.get('NEO4J_USER', 'neo4j'), metavar='USER',
                     help='Neo4j username (default: from env var NEO4J_USER or neo4j)')
    neo4j.add_argument('--neo4j-password', default=os.environ.get('NEO4J_PASSWORD', 'password'), metavar='PASSWORD',
                     help='Neo4j password (default: from env var NEO4J_PASSWORD or password)')
    
    args = parser.parse_args()
    
    # Handle output directory default based on repo name
    if not args.output_dir:
        # More robust repo name extraction
        if args.repo_path.endswith('/'):
            args.repo_path = args.repo_path[:-1]
            
        # Handle both local paths and remote URLs
        if '/' in args.repo_path:
            repo_name = args.repo_path.split('/')[-1]
        else:
            repo_name = args.repo_path
            
        # Remove .git extension if present
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        # Sanitize repo name for directory
        repo_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in repo_name)
        
        # Create path
        args.output_dir = os.path.join('./output', repo_name)
    
    return args


def run_git_ingestion(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Run the git ingestion step.
    
    Args:
        args: Command line arguments
        
    Returns:
        Dictionary with git ingestion results
    """
    logging.info(f"Starting git ingestion from {args.repo_path}")
    
    # Check if the repository path is a URL or a local path
    is_remote_url = args.repo_path.startswith(('http://', 'https://', 'git://'))
    
    if is_remote_url:
        # For remote repositories, use the URL directly
        repo_url = args.repo_path
        
        # Extract repo name from the URL
        if args.repo_path.endswith('/'):
            repo_path = args.repo_path[:-1]
        else:
            repo_path = args.repo_path
            
        repo_name = repo_path.split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        logging.info(f"Remote repository URL: {repo_url}")
    else:
        # For local repositories, get the absolute path
        repo_url = os.path.abspath(args.repo_path)
        repo_name = os.path.basename(repo_url)
        logging.info(f"Local repository path: {repo_url}")
    
    # Configure git ingestion
    git_config = {
        "excluded_paths": [
            ".git", "node_modules", "venv", "__pycache__", 
            "*.pyc", "*.pyo", "*.pyd", "*.so", "*.o", "*.a"
        ],
        # Add commit_history_file to ensure we use the same file as previously
        "commit_history_file": "commit_history.json",
        "git_tool_config": {
            # Pass SSH authentication settings if enabled
            "use_ssh": args.ssh_auth,
            "ssh_key_path": args.ssh_key if args.ssh_auth else None,
            "workspace_dir": "./workspace"
        }
    }
    
    # Log SSH authentication status
    if args.ssh_auth:
        logging.info("SSH authentication enabled for Git operations")
        if args.ssh_key:
            logging.info(f"Using custom SSH key: {args.ssh_key}")
        else:
            logging.info("Using default SSH key or SSH agent")
    
    git_runner = DirectGitIngestionRunner(git_config)
    
    # The DirectGitIngestionRunner expects a list of repositories in a specific format
    git_input = {
        "repositories": [
            {
                "url": repo_url,  # Use URL or absolute path
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
            "repository_url": repo_url,  # Use repo_url instead of repo_path_abs
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
    
    # Use repository path from git results
    repo_path = git_result.get("repository_url", "")
    
    parser_input = {
        "repository": git_result.get("repository_name", ""),
        "repository_path": repo_path,  # Use the path from git results
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
    Run the SIMPLE graph builder step.
    
    Args:
        args: Command line arguments
        parser_result: Results from code parsing
        
    Returns:
        Dictionary with graph building results
    """
    logging.info("Starting SIMPLE graph building")
    
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
    
    # Use the OPTIMIZED graph builder with larger batch size
    neo4j_config = {
        "uri": args.neo4j_uri,
        "user": args.neo4j_user,
        "password": args.neo4j_password,
        "batch_size": 1000  # Process 1000 files per batch
    }
    
    # Save parser output for the simple graph builder
    parser_output_file = os.path.join(args.output_dir, "parser_output.json")
    graph_output_file = os.path.join(args.output_dir, "graph_output.json")
    
    # The simple graph builder expects the parser result with ASTs
    parser_result["is_full_indexing"] = args.full_indexing
    
    # Run the simple graph builder
    try:
        graph_result = process_graph_building(
            input_file=parser_output_file,
            output_file=graph_output_file,
            neo4j_config=neo4j_config
        )
        
        # Log results
        stats = graph_result.get("graph_stats", {})
        logging.info(f"Graph building complete: {stats}")
        logging.info(f"Created {stats.get('functions', 0)} functions")
        logging.info(f"Created {stats.get('classes', 0)} classes") 
        logging.info(f"Created {stats.get('call_sites', 0)} call sites")
        logging.info(f"Resolved {stats.get('resolved_calls', 0)} function calls")
        
        return graph_result
    except Exception as e:
        logging.error(f"Graph building failed: {e}", exc_info=True)
        error_result = {
            "repository": parser_result.get("repository", ""),
            "files_processed": 0,
            "files_failed": len(asts),
            "error": str(e),
            "graph_stats": {
                "functions": 0,
                "classes": 0,
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


def print_banner(text, style="default"):
    """
    Print a formatted banner with text in different styles.
    
    Args:
        text: The text to display in the banner
        style: The style to use ('default', 'success', 'error', 'info')
    """
    width = 80
    
    # Select style
    if style == "success":
        symbol = "✅"
        border = "═"
        prefix = "SUCCESS: "
    elif style == "error":
        symbol = "❌"
        border = "═"
        prefix = "ERROR: "
    elif style == "info":
        symbol = "ℹ️ "
        border = "─"
        prefix = ""
    elif style == "warning":
        symbol = "⚠️ "
        border = "─"
        prefix = "WARNING: "
    else:  # default
        symbol = "🔶"
        border = "═"
        prefix = ""
    
    print("\n" + border*width)
    print(f"{symbol} {prefix}{text}".center(width))
    print(border*width + "\n")

def format_time(seconds):
    """Format time in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours"

def display_summary(stage, args, results, timings=None):
    """
    Display a summary of processing results with improved formatting.
    
    Args:
        stage: The pipeline stage to display ('git', 'parse', 'graph')
        args: Command line arguments
        results: Dictionary with results from each stage
        timings: Optional dictionary with timing information
    """
    # Get timing information if available
    timing_info = ""
    if timings and stage in timings:
        timing_info = f" in {format_time(timings[stage])}"
    
    if stage == "graph":
        git_result = results["git"]
        graph_result = results["graph"]
        
        print_banner(f"KNOWLEDGE GRAPH GENERATION COMPLETED{timing_info}", "success")
        
        # Repository information
        print("📊 REPOSITORY SUMMARY")
        print(f"  📦 Repository: {git_result.get('repository_name', '')}")
        print(f"  🔖 Branch: {args.branch}")
        print(f"  🔒 Commit: {args.commit}")
        
        # Processing statistics
        print("\n📈 PROCESSING STATISTICS")
        print(f"  📄 Files Processed: {graph_result.get('files_processed', 0)}")
        if graph_result.get('files_failed', 0) > 0:
            print(f"  ⚠️  Files Failed: {graph_result.get('files_failed', 0)}")
        
        # Graph statistics
        print("\n🔄 GRAPH STATISTICS")
        stats = graph_result.get('graph_stats', {})
        if 'nodes_created' in stats:
            print(f"  📍 Nodes Created: {stats['nodes_created']:,}")
        if 'relationships_created' in stats:
            print(f"  🔗 Relationships Created: {stats['relationships_created']:,}")
        if 'call_sites' in stats:
            print(f"  📞 Call Sites: {stats['call_sites']:,}")
        if 'resolved_calls' in stats:
            success_rate = 0
            if stats.get('call_sites', 0) > 0:
                success_rate = (stats['resolved_calls'] / stats['call_sites']) * 100
            print(f"  ✓ Resolved Calls: {stats['resolved_calls']:,} ({success_rate:.1f}%)")
        if 'imported_modules' in stats:
            print(f"  📦 Imported Modules: {stats['imported_modules']:,}")
        
        # Results location
        print("\n💾 RESULTS LOCATION")
        print(f"  📁 Output Directory: {os.path.abspath(args.output_dir)}")
        print(f"  📄 Graph Output: {os.path.join(args.output_dir, 'graph_output.json')}")
        
        # Next steps
        print("\n⏩ NEXT STEPS")
        print("  • Query the knowledge graph using Neo4j Browser at http://localhost:7474/")
        print("  • Run semantic search on the code using the search API")
        print("  • Visualize code relationships with the graph explorer")
    
    elif stage == "parse":
        git_result = results["git"]
        parser_result = results["parser"]
        
        if args.skip_graph:
            print_banner(f"CODE PARSING COMPLETED (GRAPH BUILDING SKIPPED){timing_info}", "success")
        else:
            print_banner(f"CODE PARSING COMPLETED{timing_info}", "success")
        
        # Repository information
        print("📊 REPOSITORY SUMMARY")
        print(f"  📦 Repository: {git_result.get('repository_name', '')}")
        print(f"  🔖 Branch: {args.branch}")
        print(f"  🔒 Commit: {args.commit}")
        
        # Parsing statistics
        print("\n📈 PARSING STATISTICS")
        asts = parser_result.get('asts', [])
        print(f"  🌳 ASTs Generated: {len(asts):,}")
        print(f"  📄 Files Processed: {parser_result.get('files_processed', 0):,}")
        if parser_result.get('files_failed', 0) > 0:
            print(f"  ⚠️  Files Failed: {parser_result.get('files_failed', 0):,}")
        
        # Count ASTs by language if available
        languages = {}
        for ast in asts:
            lang = ast.get('language')
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        
        if languages:
            print("\n🔤 LANGUAGE BREAKDOWN")
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(asts)) * 100
                print(f"  • {lang}: {count:,} ASTs ({percentage:.1f}%)")
        
        # Results location
        print("\n💾 RESULTS LOCATION")
        print(f"  📁 Output Directory: {os.path.abspath(args.output_dir)}")
        print(f"  📄 Parser Output: {os.path.join(args.output_dir, 'parser_output.json')}")
        
        # Next steps
        if args.skip_graph:
            print("\n⏩ NEXT STEPS")
            print("  • Run with --skip-git --skip-parse to build the graph from these results")
            print("  • Or inspect the ASTs directly in the parser output file")
    
    elif stage == "git":
        git_result = results["git"]
        
        if args.skip_parse:
            print_banner(f"GIT INGESTION COMPLETED (PARSING & GRAPH BUILDING SKIPPED){timing_info}", "success")
        else:
            print_banner(f"GIT INGESTION COMPLETED{timing_info}", "success")
        
        # Repository information
        print("📊 REPOSITORY SUMMARY")
        print(f"  📦 Repository: {git_result.get('repository_name', '')}")
        print(f"  🔖 Branch: {args.branch}")
        print(f"  🔒 Commit: {args.commit}")
        
        # File statistics
        files = git_result.get('files', [])
        print("\n📈 FILE STATISTICS")
        print(f"  📄 Files Extracted: {len(files):,}")
        
        # Count files by extension if available
        extensions = {}
        for file in files:
            path = file.get('path', '')
            ext = os.path.splitext(path)[1].lower()
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1
            else:
                extensions['(no extension)'] = extensions.get('(no extension)', 0) + 1
        
        if extensions:
            print("\n🔤 FILE TYPE BREAKDOWN")
            # Show top 5 extensions
            for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(files)) * 100
                print(f"  • {ext}: {count:,} files ({percentage:.1f}%)")
        
        # Results location
        print("\n💾 RESULTS LOCATION")
        print(f"  📁 Output Directory: {os.path.abspath(args.output_dir)}")
        print(f"  📄 Git Output: {os.path.join(args.output_dir, 'git_output.json')}")
        
        # Next steps
        if args.skip_parse:
            print("\n⏩ NEXT STEPS")
            print("  • Run with --skip-git to parse these files")
            print("  • Or inspect the file metadata directly in the git output file")

def main() -> None:
    """Main entry point for the CodeIndexer pipeline."""
    # Track total execution time
    pipeline_start_time = time.time()
    
    # Parse arguments and setup logging
    args = parse_args()
    setup_logging(args.verbose)
    
    # Welcome banner
    print_banner("CodeIndexer Pipeline", "info")
    print(f"📦 Repository: {args.repo_path}")
    print(f"📂 Output Directory: {args.output_dir}")
    print(f"🔖 Branch: {args.branch}")
    print(f"🔒 Commit: {args.commit}")
    
    # Display authentication mode
    if args.ssh_auth:
        ssh_key_info = f" (using key: {args.ssh_key})" if args.ssh_key else " (using default key or SSH agent)"
        print(f"🔐 Authentication: SSH{ssh_key_info}")
    else:
        print("🔐 Authentication: Default (no SSH)")
    
    if args.full_indexing:
        print("⚠️  Full indexing mode: Existing data will be cleared")
    
    # Create pipeline status display
    stages = ["Git Ingestion", "Code Parsing", "Graph Building"]
    stage_status = []
    
    # Mark stages as skipped based on arguments
    if args.skip_git:
        stage_status.append("⏩ SKIP")
    else:
        stage_status.append("⏳ PENDING")
        
    if args.skip_parse:
        stage_status.append("⏩ SKIP")
    else:
        stage_status.append("⏳ PENDING")
        
    if args.skip_graph:
        stage_status.append("⏩ SKIP")
    else:
        stage_status.append("⏳ PENDING")
    
    # Print initial pipeline status
    print("\n" + "─" * 80)
    print("PIPELINE STATUS")
    for i, (stage, status) in enumerate(zip(stages, stage_status)):
        print(f"  {i+1}. {stage}: {status}")
    print("─" * 80 + "\n")
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Keep track of results and timing for summary
        results = {}
        timings = {}
        
        # ────────────────────────────────────────────────────────────────────────────────
        # Step 1: Git Ingestion
        # ────────────────────────────────────────────────────────────────────────────────
        git_result = {}
        if not args.skip_git:
            # Update status
            stage_status[0] = "🔄 RUNNING"
            print("\n" + "─" * 80)
            print(f"STAGE 1/3: 📦 GIT INGESTION")
            print("─" * 80)
            print(f"📂 Processing repository: {args.repo_path}")
            
            # Start timer
            git_start_time = time.time()
            
            # Run git ingestion
            git_result = run_git_ingestion(args)
            results["git"] = git_result
            
            # Stop timer and store
            git_end_time = time.time()
            timings["git"] = git_end_time - git_start_time
            
            # Update status
            stage_status[0] = f"✅ DONE ({format_time(timings['git'])})"
            
            # Print real-time file counts
            files_count = len(git_result.get('files', []))
            print(f"📊 Extracted {files_count:,} files in {format_time(timings['git'])}")
        else:
            # Load previous git results if available
            git_output_file = os.path.join(args.output_dir, "git_output.json")
            if os.path.exists(git_output_file):
                try:
                    with open(git_output_file, 'r') as f:
                        git_result = json.load(f)
                    files_count = len(git_result.get('files', []))
                    logging.info(f"Loaded previous git results: {files_count} files")
                    results["git"] = git_result
                    
                    print("\n" + "─" * 80)
                    print(f"STAGE 1/3: 📦 GIT INGESTION (CACHED)")
                    print("─" * 80)
                    print(f"⚡ Using cached git results: {files_count:,} files")
                    
                    # Update status
                    stage_status[0] = "🔄 CACHED"
                except Exception as e:
                    print_banner(f"Failed to load git results: {str(e)}", "error")
                    logging.error(f"Failed to load git results: {e}", exc_info=True)
                    print("💡 Try removing the --skip-git option to start fresh")
                    sys.exit(1)
            else:
                print_banner("No previous git results found", "error")
                logging.error("Skipping git but no previous git results found")
                print("💡 Try removing the --skip-git option to start fresh")
                sys.exit(1)
        
        # If only git was requested, show summary and exit
        if args.skip_parse and args.skip_graph:
            # Update status
            print("\n" + "─" * 80)
            print("FINAL PIPELINE STATUS")
            for i, (stage, status) in enumerate(zip(stages, stage_status)):
                print(f"  {i+1}. {stage}: {status}")
            print("─" * 80 + "\n")
            
            # Display detailed summary
            display_summary("git", args, results, timings)
            
            # Log completion
            pipeline_end_time = time.time()
            total_time = pipeline_end_time - pipeline_start_time
            logging.info(f"Pipeline completed successfully (git stage only) in {format_time(total_time)}")
            return
        
        # ────────────────────────────────────────────────────────────────────────────────
        # Step 2: Code Parsing
        # ────────────────────────────────────────────────────────────────────────────────
        parser_result = {}
        if not args.skip_parse:
            # Update status
            stage_status[1] = "🔄 RUNNING"
            print("\n" + "─" * 80)
            print(f"STAGE 2/3: 🔍 CODE PARSING")
            print("─" * 80)
            
            files_count = len(git_result.get('files', []))
            print(f"🔍 Parsing {files_count:,} files...")
            
            # Start timer
            parse_start_time = time.time()
            
            # Run code parser
            parser_result = run_code_parser(args, git_result)
            results["parser"] = parser_result
            
            # Stop timer and store
            parse_end_time = time.time()
            timings["parse"] = parse_end_time - parse_start_time
            
            # Update status
            stage_status[1] = f"✅ DONE ({format_time(timings['parse'])})"
            
            # Print real-time AST counts
            ast_count = len(parser_result.get('asts', []))
            print(f"📊 Generated {ast_count:,} ASTs in {format_time(timings['parse'])}")
            
            # Print processing rate
            if timings["parse"] > 0 and files_count > 0:
                files_per_second = files_count / timings["parse"]
                print(f"⚡ Processing rate: {files_per_second:.1f} files/second")
        else:
            # Load previous parser results if available
            parser_output_file = os.path.join(args.output_dir, "parser_output.json")
            if os.path.exists(parser_output_file):
                try:
                    with open(parser_output_file, 'r') as f:
                        parser_result = json.load(f)
                    ast_count = len(parser_result.get('asts', []))
                    logging.info(f"Loaded previous parser results: {ast_count} ASTs")
                    results["parser"] = parser_result
                    
                    print("\n" + "─" * 80)
                    print(f"STAGE 2/3: 🔍 CODE PARSING (CACHED)")
                    print("─" * 80)
                    print(f"⚡ Using cached parser results: {ast_count:,} ASTs")
                    
                    # Update status
                    stage_status[1] = "🔄 CACHED"
                except Exception as e:
                    print_banner(f"Failed to load parser results: {str(e)}", "error")
                    logging.error(f"Failed to load parser results: {e}", exc_info=True)
                    print("💡 Try removing the --skip-parse option to start fresh")
                    sys.exit(1)
            else:
                print_banner("No previous parser results found", "error")
                logging.error("Skipping parse but no previous parser results found")
                print("💡 Try removing the --skip-parse option to start fresh")
                sys.exit(1)
        
        # If only git+parse was requested, show summary and exit
        if args.skip_graph:
            # Update status
            print("\n" + "─" * 80)
            print("FINAL PIPELINE STATUS")
            for i, (stage, status) in enumerate(zip(stages, stage_status)):
                print(f"  {i+1}. {stage}: {status}")
            print("─" * 80 + "\n")
            
            # Display detailed summary
            display_summary("parse", args, results, timings)
            
            # Log completion
            pipeline_end_time = time.time()
            total_time = pipeline_end_time - pipeline_start_time
            logging.info(f"Pipeline completed successfully (git + parse stages) in {format_time(total_time)}")
            return
        
        # ────────────────────────────────────────────────────────────────────────────────
        # Step 3: Enhanced Graph Building
        # ────────────────────────────────────────────────────────────────────────────────
        # Update status
        stage_status[2] = "🔄 RUNNING"
        print("\n" + "─" * 80)
        print(f"STAGE 3/3: 🔄 GRAPH BUILDING")
        print("─" * 80)
        
        ast_count = len(parser_result.get('asts', []))
        print(f"🔄 Building knowledge graph from {ast_count:,} ASTs...")
        
        if args.resolution_strategy:
            print(f"🔍 Using {args.resolution_strategy} resolution strategy")
        
        if args.immediate_resolution:
            print("⚙️ Using immediate resolution for placeholders")
        
        # Start timer
        graph_start_time = time.time()
        
        # Run graph builder
        graph_result = run_graph_builder(args, parser_result)
        results["graph"] = graph_result
        
        # Stop timer and store
        graph_end_time = time.time()
        timings["graph"] = graph_end_time - graph_start_time
        
        # Update status
        stage_status[2] = f"✅ DONE ({format_time(timings['graph'])})"
        
        # Print real-time stats
        stats = graph_result.get('graph_stats', {})
        if 'nodes_created' in stats and 'relationships_created' in stats:
            print(f"📊 Created {stats['nodes_created']:,} nodes and {stats['relationships_created']:,} relationships")
        
        if 'call_sites' in stats and 'resolved_calls' in stats:
            resolution_rate = 0
            if stats['call_sites'] > 0:
                resolution_rate = (stats['resolved_calls'] / stats['call_sites']) * 100
            print(f"📞 Resolved {stats['resolved_calls']:,} of {stats['call_sites']:,} call sites ({resolution_rate:.1f}%)")
        
        # Update final pipeline status
        print("\n" + "─" * 80)
        print("FINAL PIPELINE STATUS")
        for i, (stage, status) in enumerate(zip(stages, stage_status)):
            print(f"  {i+1}. {stage}: {status}")
        print("─" * 80 + "\n")
        
        # Show final summary
        display_summary("graph", args, results, timings)
        
        # Calculate and show total time
        pipeline_end_time = time.time()
        total_time = pipeline_end_time - pipeline_start_time
        print(f"\n⏱️ Total pipeline execution time: {format_time(total_time)}")
        
    except KeyboardInterrupt:
        print_banner("Process interrupted by user", "warning")
        logging.info("Pipeline interrupted by user")
        
        # Show partial pipeline status
        print("\n" + "─" * 80)
        print("PIPELINE STATUS AT INTERRUPTION")
        for i, (stage, status) in enumerate(zip(stages, stage_status)):
            print(f"  {i+1}. {stage}: {status}")
        print("─" * 80 + "\n")
        
        print("💡 You can resume from where you left off with appropriate --skip-* options")
        sys.exit(130)
    except Exception as e:
        print_banner(f"Pipeline failed: {str(e)}", "error")
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        
        # Show error details
        print("\n❌ ERROR DETAILS")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        print("\n💡 TROUBLESHOOTING")
        print("  • Check log files for detailed error information")
        print("  • Verify Neo4j connection if using graph building")
        print("  • Try with --verbose for more detailed logging")
        print("  • Make sure required languages are installed for tree-sitter")
        
        sys.exit(1)
    
    # Final success message
    print_banner("Pipeline completed successfully", "success")
    logging.info(f"Pipeline completed successfully in {format_time(total_time)}")


if __name__ == "__main__":
    main()