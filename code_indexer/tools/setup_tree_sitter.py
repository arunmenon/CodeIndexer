#!/usr/bin/env python3
"""
Tree-sitter Language Setup

This script properly sets up tree-sitter languages by following the 
recommended approach in the tree-sitter documentation. It builds a
shared library containing all language parsers.
"""

import os
import sys
import logging
import tempfile
import subprocess
from pathlib import Path

# Set up logging
logger = logging.getLogger("tree_sitter_setup")

def setup_tree_sitter_languages():
    """
    Set up tree-sitter languages by building them from source.
    
    Returns:
        tuple: (success, languages_dir, message)
    """
    try:
        from tree_sitter import Language
        
        # Create dirs for the language repos and the compiled language file
        build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tree-sitter-libs")
        os.makedirs(build_dir, exist_ok=True)
        
        languages_file = os.path.join(build_dir, "languages.so")
        
        # Clone the repositories if they don't exist
        language_repos = {
            "python": "https://github.com/tree-sitter/tree-sitter-python",
            "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
            "java": "https://github.com/tree-sitter/tree-sitter-java"
        }
        
        repo_paths = {}
        
        for lang, repo_url in language_repos.items():
            repo_path = os.path.join(build_dir, f"tree-sitter-{lang}")
            
            if not os.path.exists(repo_path):
                logger.info(f"Cloning {lang} grammar repository...")
                subprocess.run(["git", "clone", repo_url, repo_path], check=True)
            else:
                logger.info(f"Using existing {lang} grammar repository at {repo_path}")
            
            repo_paths[lang] = repo_path
        
        # Build the languages library
        logger.info("Building tree-sitter languages library...")
        Language.build_library(
            languages_file,
            list(repo_paths.values())
        )
        
        logger.info(f"Successfully built tree-sitter languages at {languages_file}")
        
        return True, languages_file, "Successfully set up tree-sitter languages"
        
    except ImportError:
        return False, None, "tree-sitter not installed. Install with: pip install tree-sitter"
    except subprocess.CalledProcessError as e:
        return False, None, f"Error running git command: {e}"
    except Exception as e:
        return False, None, f"Error setting up tree-sitter languages: {e}"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success, lib_path, message = setup_tree_sitter_languages()
    if success:
        print(f"Successfully set up tree-sitter languages at: {lib_path}")
    else:
        print(f"Failed to set up tree-sitter languages: {message}")