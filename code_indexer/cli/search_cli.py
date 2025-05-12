"""
Search CLI

Command-line interface for the Code Indexer search functionality.
"""

import argparse
import sys
import os
import json
import logging
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from code_indexer.api.search_api import CodeSearchAPI
from code_indexer.utils.vector_store_utils import load_vector_store_config

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("search_cli")


def setup_argparse() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.
    
    Returns:
        Argument parser
    """
    parser = argparse.ArgumentParser(description="Code Indexer Search CLI")
    
    # Base options
    parser.add_argument("--query", "-q", type=str, help="Natural language query")
    parser.add_argument("--file", "-f", type=str, help="Search by file path")
    parser.add_argument("--function", "-fn", type=str, help="Search by function name")
    parser.add_argument("--class", "-c", dest="class_name", type=str, help="Search by class name")
    parser.add_argument("--explain", "-e", type=str, help="Explain code entity")
    
    # Search options
    parser.add_argument("--search-type", type=str, default="hybrid", 
                        choices=["hybrid", "vector", "graph"], 
                        help="Type of search to perform")
    parser.add_argument("--max-results", type=int, default=10, 
                        help="Maximum number of results to return")
    parser.add_argument("--filter", action="append", 
                        help="Filters in format key=value")
    
    # Output options
    parser.add_argument("--json", action="store_true", 
                        help="Output results as JSON")
    parser.add_argument("--output", "-o", type=str, 
                        help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose output")
    
    return parser


def parse_filters(filter_args: Optional[List[str]]) -> Dict[str, Any]:
    """
    Parse filter arguments.
    
    Args:
        filter_args: List of filter strings in format key=value
        
    Returns:
        Dictionary of filters
    """
    filters = {}
    
    if not filter_args:
        return filters
    
    for filter_arg in filter_args:
        if "=" in filter_arg:
            key, value = filter_arg.split("=", 1)
            
            # Try to convert value to appropriate type
            if value.lower() == "true":
                filters[key] = True
            elif value.lower() == "false":
                filters[key] = False
            elif value.isdigit():
                filters[key] = int(value)
            elif value.replace(".", "", 1).isdigit() and value.count(".") == 1:
                filters[key] = float(value)
            else:
                filters[key] = value
    
    return filters


def format_text_output(result: Dict[str, Any]) -> str:
    """
    Format search result as text.
    
    Args:
        result: Search result
        
    Returns:
        Formatted text
    """
    output = []
    
    if result.get("success", False):
        # Add query
        output.append(f"Query: {result.get('query', '')}")
        output.append("")
        
        # Add answer
        answer = result.get("answer", "")
        if answer:
            output.append("Answer:")
            output.append("-" * 80)
            output.append(answer)
            output.append("-" * 80)
            output.append("")
        
        # Add code snippets
        snippets = result.get("code_snippets", [])
        if snippets:
            output.append("Code Snippets:")
            output.append("-" * 80)
            
            for i, snippet in enumerate(snippets, 1):
                entity_id = snippet.get("entity_id", "")
                entity_type = snippet.get("entity_type", "")
                file_path = snippet.get("file_path", "")
                language = snippet.get("language", "")
                code = snippet.get("code", "")
                
                output.append(f"Snippet {i}: {entity_type} '{entity_id}'")
                output.append(f"File: {file_path}")
                output.append(f"Language: {language}")
                output.append("")
                output.append("```")
                output.append(code)
                output.append("```")
                output.append("")
        
        # Add result counts
        output.append(f"Total results: {result.get('total_results', 0)}")
    else:
        # Add error message
        output.append(f"Error: {result.get('error', 'Unknown error')}")
    
    return "\n".join(output)


def main():
    """Run the search CLI."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Check if at least one search option was provided
    if not any([args.query, args.file, args.function, args.class_name, args.explain]):
        parser.print_help()
        sys.exit(1)
    
    # Set up verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse filters
    filters = parse_filters(args.filter)
    
    try:
        # Initialize the search API
        # Note: In a real implementation, this would create a proper AgentContext
        # For this example, we'll just simulate the API usage
        
        # Simulate search results based on the provided arguments
        if args.query:
            # Simulate query search
            result = {
                "success": True,
                "query": args.query,
                "answer": f"Here's what I found for '{args.query}':\n\nThe search would return relevant code snippets from the codebase based on the similarity to your query.",
                "code_snippets": [
                    {
                        "entity_id": "example_function",
                        "entity_type": "function",
                        "file_path": "/src/example.py",
                        "language": "python",
                        "code": "def example_function():\n    # This is an example function\n    return 'Hello, world!'"
                    }
                ],
                "total_results": 1,
                "search_type": args.search_type
            }
        elif args.file:
            # Simulate file search
            result = {
                "success": True,
                "query": f"Find all code related to the file {args.file}",
                "answer": f"I found code related to the file '{args.file}'.",
                "code_snippets": [
                    {
                        "entity_id": "example_function",
                        "entity_type": "function",
                        "file_path": args.file,
                        "language": "python",
                        "code": "def example_function():\n    # This is an example function\n    return 'Hello, world!'"
                    }
                ],
                "total_results": 1,
                "search_type": args.search_type
            }
        elif args.function:
            # Simulate function search
            result = {
                "success": True,
                "query": f"Find the definition and usages of the function {args.function}",
                "answer": f"I found the definition and usages of the function '{args.function}'.",
                "code_snippets": [
                    {
                        "entity_id": args.function,
                        "entity_type": "function",
                        "file_path": "/src/example.py",
                        "language": "python",
                        "code": f"def {args.function}():\n    # Function definition\n    return 'Hello, world!'"
                    }
                ],
                "total_results": 1,
                "search_type": args.search_type
            }
        elif args.class_name:
            # Simulate class search
            result = {
                "success": True,
                "query": f"Find the definition, methods, and inheritance of the class {args.class_name}",
                "answer": f"I found the definition, methods, and inheritance of the class '{args.class_name}'.",
                "code_snippets": [
                    {
                        "entity_id": args.class_name,
                        "entity_type": "class",
                        "file_path": "/src/example.py",
                        "language": "python",
                        "code": f"class {args.class_name}:\n    # Class definition\n    def __init__(self):\n        pass\n\n    def example_method(self):\n        return 'Hello, world!'"
                    }
                ],
                "total_results": 1,
                "search_type": args.search_type
            }
        elif args.explain:
            # Simulate explain
            result = {
                "success": True,
                "query": f"Explain what {args.explain} does and how it works",
                "answer": f"The {args.explain} is responsible for processing data and returning results. It functions by taking input parameters, processing them through several steps, and generating output based on the processed data.",
                "code_snippets": [
                    {
                        "entity_id": args.explain,
                        "entity_type": "function",
                        "file_path": "/src/example.py",
                        "language": "python",
                        "code": f"def {args.explain}(param1, param2):\n    # This function processes data\n    result = param1 + param2\n    return result"
                    }
                ],
                "total_results": 1,
                "search_type": args.search_type
            }
        
        # Format output
        if args.json:
            output = json.dumps(result, indent=2)
        else:
            output = format_text_output(result)
        
        # Write output
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()