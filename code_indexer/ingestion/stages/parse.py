"""
Code Parsing Stage

This module handles code parsing and AST generation using Tree-sitter.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

# Import our Tree-sitter AST extractor
from code_indexer.ingestion.direct.ast_extractor import create_tree_sitter_extractor

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_parse")


def process_code_parsing(input_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse code files into AST structures.
    
    Args:
        input_file: Path to JSON file with file data from git stage
        output_file: Path to save output (optional)
        
    Returns:
        Dictionary with parsing results
    """
    logger.info(f"Parsing code files from {input_file}")
    
    try:
        # Load input data
        with open(input_file, "r") as f:
            input_data = json.load(f)
        
        # Extract file data
        file_data = input_data.get("file_data", [])
        if not file_data:
            return {
                "status": "error",
                "message": "No file data found in input"
            }
        
        # Extract repository info
        repository = input_data.get("repository", "")
        repository_url = input_data.get("url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "")
        is_full_indexing = input_data.get("is_full_indexing", False)
        
        # Initialize AST extractor
        ast_extractor = create_tree_sitter_extractor({
            "use_tree_sitter": True
        })
        
        # Process each file
        parsed_files = []
        failed_files = []
        
        for file_data_item in file_data:
            file_path = file_data_item.get("path", "")
            content = file_data_item.get("content", "")
            
            if not file_path or not content:
                logger.warning(f"Skipping file with missing path or content")
                continue
            
            try:
                # Parse file
                ast_dict = ast_extractor.extract_ast(content, file_path=file_path)
                
                # Add metadata
                ast_dict["repository"] = repository
                ast_dict["repository_url"] = repository_url
                ast_dict["commit"] = commit
                ast_dict["branch"] = branch
                ast_dict["file_path"] = file_path
                
                parsed_files.append(ast_dict)
                logger.info(f"Successfully parsed {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                failed_files.append({
                    "path": file_path,
                    "error": str(e)
                })
        
        result = {
            "status": "success",
            "repository": repository,
            "url": repository_url,
            "commit": commit,
            "branch": branch,
            "is_full_indexing": is_full_indexing,
            "files_parsed": len(parsed_files),
            "files_failed": len(failed_files),
            "asts": parsed_files,
            "failed_files": failed_files[:10]  # Include only the first 10 failed files
        }
        
        # Save output if requested
        if output_file:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved output to {output_file}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing code: {e}")
        return {
            "status": "error",
            "message": str(e)
        }