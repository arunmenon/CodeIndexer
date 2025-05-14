#!/usr/bin/env python3
"""
Tree-sitter Setup Script

This script helps set up Tree-sitter language parsers by downloading
and building the necessary language grammars.

Usage:
    python setup_tree_sitter.py [--languages LANG1,LANG2,...] [--lib-dir PATH]
"""

import os
import sys
import argparse
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("tree_sitter_setup")

# Check if Tree-sitter is available
try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    logger.error("Tree-sitter not available. Please install with: pip install tree-sitter")
    HAS_TREE_SITTER = False

# Default languages to install
DEFAULT_LANGUAGES = [
    "python", "javascript", "typescript", "java", "c", "cpp", "c_sharp", 
    "go", "ruby", "php", "rust"
]

# Language repository mappings
LANGUAGE_REPOS = {
    "python": "https://github.com/tree-sitter/tree-sitter-python",
    "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
    "typescript": "https://github.com/tree-sitter/tree-sitter-typescript",
    "java": "https://github.com/tree-sitter/tree-sitter-java",
    "c": "https://github.com/tree-sitter/tree-sitter-c",
    "cpp": "https://github.com/tree-sitter/tree-sitter-cpp",
    "c_sharp": "https://github.com/tree-sitter/tree-sitter-c-sharp",
    "go": "https://github.com/tree-sitter/tree-sitter-go",
    "ruby": "https://github.com/tree-sitter/tree-sitter-ruby",
    "php": "https://github.com/tree-sitter/tree-sitter-php",
    "rust": "https://github.com/tree-sitter/tree-sitter-rust",
    "bash": "https://github.com/tree-sitter/tree-sitter-bash",
    "json": "https://github.com/tree-sitter/tree-sitter-json",
    "html": "https://github.com/tree-sitter/tree-sitter-html",
    "css": "https://github.com/tree-sitter/tree-sitter-css",
    "yaml": "https://github.com/tree-sitter/tree-sitter-yaml",
    "markdown": "https://github.com/ikatyang/tree-sitter-markdown"
}

def clone_language_repo(language: str, temp_dir: str) -> Optional[str]:
    """
    Clone a Tree-sitter language repository.
    
    Args:
        language: Language name
        temp_dir: Temporary directory to clone into
        
    Returns:
        Path to cloned repository or None if failed
    """
    repo_url = LANGUAGE_REPOS.get(language)
    if not repo_url:
        logger.error(f"No repository URL defined for language: {language}")
        return None
    
    repo_dir = os.path.join(temp_dir, f"tree-sitter-{language}")
    
    try:
        # Check if directory already exists
        if os.path.exists(repo_dir):
            logger.info(f"Repository directory already exists: {repo_dir}")
            return repo_dir
        
        # Clone the repository
        logger.info(f"Cloning {repo_url} into {repo_dir}")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return repo_dir
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository for {language}: {e}")
        logger.error(f"Stderr: {e.stderr.decode('utf-8', errors='replace')}")
        return None
    except Exception as e:
        logger.error(f"Error cloning repository for {language}: {e}")
        return None

def build_language_library(language: str, repo_dir: str, lib_dir: str) -> bool:
    """
    Build a Tree-sitter language library.
    
    Args:
        language: Language name
        repo_dir: Path to cloned repository
        lib_dir: Directory to save compiled library
        
    Returns:
        True if successful, False otherwise
    """
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available. Cannot build language library.")
        return False
    
    try:
        # Special handling for TypeScript which has multiple grammars
        if language == "typescript":
            # TypeScript needs special handling as it has both .tsx and .ts parsers
            ts_dir = os.path.join(repo_dir, "typescript")
            tsx_dir = os.path.join(repo_dir, "tsx")
            
            # Check if both directories exist
            if os.path.exists(ts_dir) and os.path.exists(tsx_dir):
                languages = []
                
                # Build .ts parser
                logger.info(f"Building TypeScript parser")
                Language.build_library(
                    os.path.join(lib_dir, "typescript.so"),
                    [ts_dir]
                )
                
                # Build .tsx parser
                logger.info(f"Building TSX parser")
                Language.build_library(
                    os.path.join(lib_dir, "tsx.so"),
                    [tsx_dir]
                )
                
                return True
        
        # Standard build process for other languages
        logger.info(f"Building {language} parser")
        Language.build_library(
            os.path.join(lib_dir, f"{language}.so"),
            [repo_dir]
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to build {language} library: {e}")
        return False

def setup_languages(languages: List[str], lib_dir: Optional[str] = None) -> int:
    """
    Set up Tree-sitter language parsers.
    
    Args:
        languages: List of languages to set up
        lib_dir: Directory to save compiled libraries
        
    Returns:
        Number of successfully built languages
    """
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available. Please install with: pip install tree-sitter")
        return 0
    
    # Determine library directory
    if not lib_dir:
        # Check common locations
        for path in [
            os.path.join(os.path.dirname(__file__), "tree-sitter-libs"),
            os.path.expanduser("~/.tree-sitter-libs"),
            "/usr/local/share/tree-sitter-libs",
        ]:
            if os.path.exists(path) and os.access(path, os.W_OK):
                lib_dir = path
                break
        
        # If no suitable directory found, create one
        if not lib_dir:
            lib_dir = os.path.join(os.path.dirname(__file__), "tree-sitter-libs")
    
    # Create library directory if it doesn't exist
    os.makedirs(lib_dir, exist_ok=True)
    logger.info(f"Using library directory: {lib_dir}")
    
    # Create temporary directory for cloning repositories
    with tempfile.TemporaryDirectory() as temp_dir:
        success_count = 0
        
        for language in languages:
            logger.info(f"Setting up {language} parser")
            
            # Clone repository
            repo_dir = clone_language_repo(language, temp_dir)
            if not repo_dir:
                logger.error(f"Failed to clone repository for {language}")
                continue
            
            # Build language library
            if build_language_library(language, repo_dir, lib_dir):
                logger.info(f"Successfully built {language} parser")
                success_count += 1
            else:
                logger.error(f"Failed to build {language} parser")
    
    logger.info(f"Successfully built {success_count} out of {len(languages)} language parsers")
    return success_count

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Set up Tree-sitter language parsers")
    parser.add_argument("--languages", help="Comma-separated list of languages to set up")
    parser.add_argument("--lib-dir", help="Directory to save compiled libraries")
    parser.add_argument("--all", action="store_true", help="Set up all supported languages")
    
    args = parser.parse_args()
    
    # Determine languages to set up
    if args.all:
        languages = list(LANGUAGE_REPOS.keys())
    elif args.languages:
        languages = [lang.strip() for lang in args.languages.split(",")]
    else:
        languages = DEFAULT_LANGUAGES
    
    logger.info(f"Setting up Tree-sitter parsers for: {', '.join(languages)}")
    
    # Set up languages
    success_count = setup_languages(languages, args.lib_dir)
    
    # Return appropriate exit code
    return 0 if success_count == len(languages) else 1

if __name__ == "__main__":
    sys.exit(main())