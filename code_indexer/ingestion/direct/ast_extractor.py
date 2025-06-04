"""
AST Extractor Factory

Factory module that creates AST extractors for the pipeline,
now using the decoupled implementation.
"""

import logging
from typing import Dict, Any

# Import our decoupled AST extractor
from code_indexer.tools.ast_extractor import ASTExtractor

# Configure logging
logger = logging.getLogger(__name__)

def create_tree_sitter_extractor(config: Dict[str, Any] = None) -> ASTExtractor:
    """
    Create a Tree-sitter AST extractor.
    
    This is a factory function that maintains backward compatibility
    with the existing pipeline code.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured ASTExtractor instance
    """
    try:
        # Create the new decoupled AST extractor
        return ASTExtractor(config)
    except ImportError as e:
        # Log error and re-raise
        logger.error(f"Failed to create AST extractor: {e}")
        raise