#!/usr/bin/env python3
"""
CodeIndexer Semantic API

This module provides an API for semantic queries powered by ADK.
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("semantic_api")

# Check if ADK is available
try:
    import google.adk
    HAS_ADK = True
except ImportError:
    logger.warning("Google ADK not available. Install with pip install google-adk")
    HAS_ADK = False


def run_semantic_api(team_file: str, port: int = 8000) -> None:
    """
    Run the semantic API.
    
    Args:
        team_file: Path to team YAML file
        port: Port to run the API on
    """
    if not HAS_ADK:
        logger.error("Cannot run semantic API without Google ADK")
        return
    
    # Import ADK modules here to avoid import errors if ADK is not installed
    from google.adk import run_api
    
    logger.info(f"Starting semantic API with team file: {team_file}")
    
    # Run the API
    run_api(team_file, port=port)


def main():
    """Main entry point for the semantic API."""
    parser = argparse.ArgumentParser(description="Run the CodeIndexer semantic API")
    parser.add_argument("--team", required=True, help="Path to team YAML file")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the API on")
    
    args = parser.parse_args()
    
    run_semantic_api(args.team, args.port)


if __name__ == "__main__":
    main()