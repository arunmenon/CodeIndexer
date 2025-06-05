"""
Ingestion CLI Package

This package provides command-line interfaces for running the ingestion pipeline.
"""

# Don't import modules here to avoid circular imports and runtime warnings
# Instead, import specific functions only when needed

def main():
    """
    Main entry point for the ingestion CLI.
    This function is used by the console_scripts entry point in setup.py.
    """
    # Import the main function only when needed to avoid import issues
    from code_indexer.ingestion.cli.run_pipeline import main as run_pipeline_main
    run_pipeline_main()