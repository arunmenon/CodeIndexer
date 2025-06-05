"""
Graph Building Stage

This module handles building a graph representation in Neo4j from AST data.
Uses batch operations for optimal performance.
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from code_indexer.ingestion.direct.graph_builder import GraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingestion_graph")


def process_graph_building(
    input_file: str, 
    output_file: Optional[str] = None,
    neo4j_config: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Build a graph representation in Neo4j from AST data.
    
    Args:
        input_file: Path to JSON file with AST data from parse stage
        output_file: Path to save output (optional)
        neo4j_config: Neo4j connection configuration
        
    Returns:
        Dictionary with graph building results
    """
    logger.info(f"Building graph from ASTs in {input_file}")
    
    # Default Neo4j config
    if neo4j_config is None:
        neo4j_config = {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "test"
        }
    
    try:
        # Load input data
        with open(input_file, "r") as f:
            input_data = json.load(f)
        
        # Extract data
        asts = input_data.get("asts", [])
        repository = input_data.get("repository", "unknown")
        
        if not asts:
            return {
                "status": "error",
                "message": "No ASTs found in input"
            }
        
        # Initialize graph builder
        graph_builder = GraphBuilder(neo4j_config)
        
        try:
            # Clear existing data for this repository
            logger.info(f"Clearing existing data for repository: {repository}")
            graph_builder.clear_repository(repository)
            
            # Process ASTs in batches
            start_time = time.time()
            logger.info(f"Processing {len(asts)} ASTs...")
            
            # Convert ASTs to the format expected by process_batch
            files_batch = []
            for ast_info in asts:
                file_path = ast_info.get("file_path", "")
                ast_data = ast_info
                files_batch.append((file_path, ast_data, repository))
            
            batch_results = graph_builder.process_batch(files_batch)
            
            # Resolve placeholders
            logger.info("Resolving placeholders...")
            graph_builder.resolve_placeholders()
            
            processing_time = time.time() - start_time
            
            # Get statistics
            stats = graph_builder.stats
            
            # Prepare results
            result = {
                "status": "success",
                "repository": repository,
                "stats": stats,
                "processing_time": processing_time,
                "files_per_minute": (stats["files"] / processing_time * 60) if processing_time > 0 else 0
            }
            
            logger.info(f"Graph building completed:")
            logger.info(f"  - Files: {stats['files']}")
            logger.info(f"  - Functions: {stats['functions']}")
            logger.info(f"  - Classes: {stats['classes']}")
            logger.info(f"  - Call Sites: {stats['call_sites']}")
            logger.info(f"  - Resolved Calls: {stats['resolved_calls']}")
            logger.info(f"  - Processing time: {processing_time:.2f}s")
            logger.info(f"  - Speed: {result['files_per_minute']:.1f} files/minute")
            
            # Save output if requested
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Results saved to {output_file}")
            
            return result
            
        finally:
            graph_builder.close()
            
    except Exception as e:
        logger.error(f"Error during graph building: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build graph from AST data")
    parser.add_argument("input_file", help="Input JSON file with AST data")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument("--neo4j-password", default="test", help="Neo4j password")
    
    args = parser.parse_args()
    
    neo4j_config = {
        "uri": args.neo4j_uri,
        "user": args.neo4j_user,
        "password": args.neo4j_password
    }
    
    result = process_graph_building(args.input_file, args.output, neo4j_config)
    
    if result["status"] != "success":
        logger.error(f"Graph building failed: {result.get('message', 'Unknown error')}")
        exit(1)