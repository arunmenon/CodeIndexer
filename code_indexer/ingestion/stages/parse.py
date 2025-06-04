"""
Code Parsing Stage

This module handles code parsing and AST generation using Tree-sitter.
Now supports direct file processing without requiring git stage first.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

# Import our Tree-sitter AST extractor
from code_indexer.ingestion.direct.ast_extractor import create_tree_sitter_extractor

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_parse")


def process_code_parsing(input_file: Optional[str] = None, 
                         file_paths: Optional[List[str]] = None,
                         directory_path: Optional[str] = None,
                         output_file: Optional[str] = None,
                         repository: str = "",
                         repository_url: str = "",
                         commit: str = "",
                         branch: str = "") -> Dict[str, Any]:
    """
    Parse code files into AST structures.
    
    This function supports multiple input methods:
    1. From git stage output file (input_file)
    2. Direct file paths (file_paths)
    3. Directory scanning (directory_path)
    
    Args:
        input_file: Path to JSON file with file data from git stage (optional)
        file_paths: List of file paths to parse directly (optional)
        directory_path: Directory to scan for files to parse (optional)
        output_file: Path to save output (optional)
        repository: Repository name for direct file processing (optional)
        repository_url: Repository URL for direct file processing (optional)
        commit: Commit hash for direct file processing (optional)
        branch: Branch name for direct file processing (optional)
        
    Returns:
        Dictionary with parsing results
    """
    logger.info("Starting code parsing stage")
    
    # Validate input - need at least one input source
    if not input_file and not file_paths and not directory_path:
        return {
            "status": "error",
            "message": "No input sources provided. Need either input_file, file_paths, or directory_path."
        }
    
    try:
        # Initialize AST extractor
        ast_extractor = create_tree_sitter_extractor({
            "use_tree_sitter": True
        })
        
        # Prepare to store parsing results
        parsed_files = []
        failed_files = []
        is_full_indexing = False
        
        # Determine processing method based on input
        if input_file:
            # Process from git stage output
            logger.info(f"Parsing code files from git stage output: {input_file}")
            
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
            repository = input_data.get("repository", repository)
            repository_url = input_data.get("url", repository_url)
            commit = input_data.get("commit", commit)
            branch = input_data.get("branch", branch)
            is_full_indexing = input_data.get("is_full_indexing", False)
            
            # Process each file from git stage output
            for file_data_item in file_data:
                file_path = file_data_item.get("path", "")
                content = file_data_item.get("content", "")
                
                if not file_path or not content:
                    logger.warning(f"Skipping file with missing path or content")
                    continue
                
                try:
                    # Parse file content
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
                    
        elif file_paths:
            # Process direct file paths
            logger.info(f"Parsing {len(file_paths)} files directly")
            
            for file_path in file_paths:
                try:
                    # Parse file
                    ast_dict = ast_extractor.extract_ast_from_file(file_path)
                    
                    # Add metadata
                    ast_dict["repository"] = repository
                    ast_dict["repository_url"] = repository_url
                    ast_dict["commit"] = commit
                    ast_dict["branch"] = branch
                    
                    parsed_files.append(ast_dict)
                    logger.info(f"Successfully parsed {file_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to parse {file_path}: {e}")
                    failed_files.append({
                        "path": file_path,
                        "error": str(e)
                    })
                    
        elif directory_path:
            # Process all files in directory
            logger.info(f"Scanning directory for files to parse: {directory_path}")
            
            # Scan directory for files
            scanned_files = []
            for root, _, files in os.walk(directory_path):
                for file in files:
                    # Skip hidden files
                    if file.startswith('.'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    # Skip binary files and very large files
                    if _is_text_file(file_path) and os.path.getsize(file_path) < 10 * 1024 * 1024:  # 10MB limit
                        scanned_files.append(file_path)
            
            logger.info(f"Found {len(scanned_files)} files to parse")
            
            # Process each file
            for file_path in scanned_files:
                try:
                    # Parse file
                    ast_dict = ast_extractor.extract_ast_from_file(file_path)
                    
                    # Add metadata
                    ast_dict["repository"] = repository
                    ast_dict["repository_url"] = repository_url
                    ast_dict["commit"] = commit
                    ast_dict["branch"] = branch
                    
                    # Add relative path for consistency
                    rel_path = os.path.relpath(file_path, directory_path)
                    ast_dict["file_path"] = rel_path
                    
                    parsed_files.append(ast_dict)
                    logger.info(f"Successfully parsed {rel_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to parse {file_path}: {e}")
                    failed_files.append({
                        "path": file_path,
                        "error": str(e)
                    })
        
        # Prepare result
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
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
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


def _is_text_file(file_path: str) -> bool:
    """
    Check if a file is a text file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is a text file, False otherwise
    """
    # Check file extension first for performance
    text_extensions = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
        '.cs', '.go', '.rb', '.php', '.rs', '.swift', '.kt', '.scala', '.m',
        '.sh', '.hs', '.ml', '.sql', '.html', '.css', '.json', '.yaml', '.yml',
        '.xml', '.md', '.txt', '.rst', '.csv', '.log'
    }
    
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in text_extensions:
        return True
    
    # Try to read a few bytes to check if it's binary
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return not _is_binary_string(chunk)
    except:
        return False


def _is_binary_string(bytes_data: bytes) -> bool:
    """
    Check if a bytes string contains binary data.
    
    Args:
        bytes_data: Bytes to check
        
    Returns:
        True if the data is binary, False otherwise
    """
    # Count non-ASCII characters
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
    return bool(bytes_data.translate(None, text_chars))