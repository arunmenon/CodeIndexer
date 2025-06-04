#!/usr/bin/env python3
"""
Build Tree-sitter Language Libraries

This script builds Tree-sitter language libraries for AST parsing.
"""

import os
import sys
import logging
import argparse
import tempfile
import shutil
import subprocess
from typing import List, Dict, Any, Set

try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("build_tree_sitter")


def clone_repo(repo_url: str, target_dir: str) -> bool:
    """
    Clone a Git repository.
    
    Args:
        repo_url: URL of the repository
        target_dir: Directory to clone into
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(target_dir):
            logger.info(f"Directory {target_dir} already exists, skipping clone")
            return True
            
        logger.info(f"Cloning {repo_url} to {target_dir}")
        result = subprocess.run(
            ["git", "clone", repo_url, target_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository: {e}")
        logger.error(f"Stderr: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.error(f"Failed to clone repository: {e}")
        return False
        

def build_language_libraries(lib_dir: str, langs: List[str] = None) -> Set[str]:
    """
    Build Tree-sitter language libraries.
    
    Args:
        lib_dir: Directory to store language libraries
        langs: List of languages to build (default: ["python", "javascript"])
        
    Returns:
        Set of successfully built languages
    """
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available. Please install with: pip install tree-sitter")
        return set()
        
    # Define language configurations
    language_configs = {
        "python": {"repo": "https://github.com/tree-sitter/tree-sitter-python"},
        "javascript": {"repo": "https://github.com/tree-sitter/tree-sitter-javascript"},
        "typescript": {"repo": "https://github.com/tree-sitter/tree-sitter-typescript"},
        "java": {"repo": "https://github.com/tree-sitter/tree-sitter-java"},
        "c": {"repo": "https://github.com/tree-sitter/tree-sitter-c"},
        "cpp": {"repo": "https://github.com/tree-sitter/tree-sitter-cpp"},
        "go": {"repo": "https://github.com/tree-sitter/tree-sitter-go"},
        "ruby": {"repo": "https://github.com/tree-sitter/tree-sitter-ruby"},
        "rust": {"repo": "https://github.com/tree-sitter/tree-sitter-rust"},
        "bash": {"repo": "https://github.com/tree-sitter/tree-sitter-bash"}
    }
    
    # Default languages if not specified
    if not langs:
        langs = ["python", "javascript"]
        
    # Filter out unsupported languages
    langs = [lang for lang in langs if lang in language_configs]
    if not langs:
        logger.error("No supported languages specified")
        return set()
        
    # Create lib directory if it doesn't exist
    os.makedirs(lib_dir, exist_ok=True)
    
    # Create temporary directory for cloning repos
    with tempfile.TemporaryDirectory() as temp_dir:
        # Clone repositories and collect paths
        repo_paths = {}
        for lang in langs:
            config = language_configs[lang]
            repo_url = config["repo"]
            repo_dir = os.path.join(temp_dir, f"tree-sitter-{lang}")
            
            if clone_repo(repo_url, repo_dir):
                repo_paths[lang] = repo_dir
                
        if not repo_paths:
            logger.error("Failed to clone any repositories")
            return set()
            
        # Build language libraries
        try:
            # Special handling for TypeScript which has multiple parsers
            if "typescript" in repo_paths:
                ts_path = repo_paths.pop("typescript")
                # Clone without language-specific name
                repo_paths["typescript"] = os.path.join(ts_path, "typescript")
                repo_paths["tsx"] = os.path.join(ts_path, "tsx")
                
            # Build libraries
            repo_list = list(repo_paths.items())
            languages = {}
            built_langs = set()
            
            for lang, path in repo_list:
                if not os.path.exists(path):
                    logger.warning(f"Repository path {path} does not exist, skipping")
                    continue
                    
                try:
                    logger.info(f"Building {lang} language library...")
                    lib_path = os.path.join(lib_dir, f"{lang}.so")
                    
                    # Check if the library already exists
                    if os.path.exists(lib_path):
                        logger.info(f"Library for {lang} already exists at {lib_path}")
                        built_langs.add(lang)
                        continue
                    
                    # Build the language
                    Language.build_library(
                        lib_path,
                        [path]
                    )
                    
                    # Verify that the library was built
                    if os.path.exists(lib_path):
                        logger.info(f"Successfully built {lang} language library")
                        built_langs.add(lang)
                    else:
                        logger.error(f"Failed to build {lang} language library")
                        
                except Exception as e:
                    logger.error(f"Error building {lang} language library: {e}")
            
            return built_langs
            
        except Exception as e:
            logger.error(f"Failed to build language libraries: {e}")
            return set()
            

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build Tree-sitter language libraries")
    parser.add_argument("--lib-dir", default=None, help="Directory to store language libraries")
    parser.add_argument("--languages", default=None, help="Comma-separated list of languages to build")
    parser.add_argument("--all", action="store_true", help="Build all supported languages")
    
    args = parser.parse_args()
    
    # Validate Tree-sitter installation
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available. Please install with: pip install tree-sitter")
        return 1
        
    # Determine lib directory
    lib_dir = args.lib_dir
    if not lib_dir:
        # Default locations
        script_dir = os.path.dirname(os.path.abspath(__file__))
        lib_dir = os.path.join(script_dir, "tree-sitter-libs")
        
    # Determine languages to build
    langs = None
    if args.all:
        langs = ["python", "javascript", "typescript", "java", "c", "cpp", "go", "ruby", "rust", "bash"]
    elif args.languages:
        langs = [lang.strip() for lang in args.languages.split(",")]
        
    # Build language libraries
    built_langs = build_language_libraries(lib_dir, langs)
    
    # Report results
    if built_langs:
        logger.info(f"Successfully built {len(built_langs)} language libraries: {', '.join(built_langs)}")
        logger.info(f"Libraries saved to: {lib_dir}")
        return 0
    else:
        logger.error("Failed to build any language libraries")
        return 1
        

if __name__ == "__main__":
    sys.exit(main())