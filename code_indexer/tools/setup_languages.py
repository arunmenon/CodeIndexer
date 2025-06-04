#!/usr/bin/env python3
"""
Setup Tree-sitter Languages

This script provides instructions for setting up Tree-sitter language libraries.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup_languages")

def main():
    """Main entry point."""
    # Determine the language libraries directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(script_dir, "tree-sitter-libs")
    os.makedirs(lib_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print("Tree-sitter Language Setup Instructions")
    print(f"{'='*80}")
    print("\nYour version of tree-sitter doesn't support automatic library building.")
    print("To set up language libraries, follow these manual steps:\n")
    
    print("Option 1: Using tree-sitter CLI (recommended):")
    print("1. Install Node.js from https://nodejs.org/")
    print("2. Install tree-sitter CLI:")
    print("   npm install -g tree-sitter-cli")
    print("3. Create language libraries:")
    print(f"   mkdir -p {lib_dir}")
    print("   cd <language-repo>")
    print("   tree-sitter generate")
    print(f"   tree-sitter build-wasm -o {lib_dir}/<language>.wasm")
    print("\nFor each language you want to support (python, javascript, java, etc.):\n")
    print("   git clone https://github.com/tree-sitter/tree-sitter-<language>")
    print("   cd tree-sitter-<language>")
    print("   tree-sitter generate")
    print(f"   tree-sitter build-wasm -o {lib_dir}/<language>.wasm\n")
    
    print("Option 2: Use py-tree-sitter-languages package:")
    print("   pip install tree-sitter-languages")
    print("   Then modify the code to use the pre-built libraries\n")
    
    # Special message for Mac OS users
    if sys.platform == 'darwin':
        print("For Mac OS users, you may need:")
        print("   brew install tree-sitter")
        print("   Then link the system libraries to the Python package\n")
    
    print(f"Language libraries should be placed in: {lib_dir}")
    print(f"{'='*80}\n")
    
    # Provide fallback instructions for immediate use
    print("To continue without Tree-sitter (using fallback parsers):")
    print("Modify code_indexer/ingestion/cli/run_pipeline.py to set:")
    print("   use_treesitter: False")
    print("   ast_extractor_config: {'use_tree_sitter': False}")
    print(f"{'='*80}\n")
    
    return 0
    
if __name__ == "__main__":
    sys.exit(main())