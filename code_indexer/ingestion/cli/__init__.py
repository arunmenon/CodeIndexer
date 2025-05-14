"""
Ingestion CLI Package

This package provides command-line interfaces for running the ingestion pipeline.
"""

from code_indexer.ingestion.cli.run_pipeline import main as run_pipeline_main

def main():
    """
    Main entry point for the ingestion CLI.
    This function is used by the console_scripts entry point in setup.py.
    """
    run_pipeline_main()