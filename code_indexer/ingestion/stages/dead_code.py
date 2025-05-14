"""
Dead Code Detection Stage

This module handles detection of unused code in the codebase.
"""

import logging
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_dead_code")


def detect_dead_code(neo4j_config: Dict[str, str], repository: str) -> Dict[str, Any]:
    """
    Detect unused code in the repository.
    
    Args:
        neo4j_config: Neo4j connection configuration
        repository: Repository name
        
    Returns:
        Dictionary with dead code detection results
    """
    logger.info(f"Detecting dead code in repository: {repository}")
    
    try:
        # Initialize Neo4j connection
        from ingestion_pipeline.direct_neo4j_tool import DirectNeo4jTool
        
        neo4j_tool = DirectNeo4jTool(
            uri=neo4j_config.get("uri", "bolt://localhost:7687"),
            user=neo4j_config.get("user", "neo4j"),
            password=neo4j_config.get("password", "password")
        )
        
        # Detect dead functions (functions that are not called)
        dead_functions_query = """
        MATCH (f:Function)
        WHERE f.repository = $repository
        AND NOT EXISTS { MATCH ()-[:CALLS]->(f) }
        AND NOT f.name STARTS WITH "test_"
        RETURN count(f) as count, collect({name: f.name, file: f.file_path})[..10] as samples
        """
        
        dead_functions_result = neo4j_tool.execute_cypher(dead_functions_query, {
            "repository": repository
        })
        
        # Detect dead classes (classes that are not instantiated or inherited from)
        dead_classes_query = """
        MATCH (c:Class)
        WHERE c.repository = $repository
        AND NOT EXISTS { MATCH ()-[:INSTANTIATES]->(c) }
        AND NOT EXISTS { MATCH ()-[:INHERITS_FROM]->(c) }
        AND NOT EXISTS { MATCH ()-[:REFERENCES]->(c) }
        AND NOT c.name STARTS WITH "Test"
        RETURN count(c) as count, collect({name: c.name, file: c.file_path})[..10] as samples
        """
        
        dead_classes_result = neo4j_tool.execute_cypher(dead_classes_query, {
            "repository": repository
        })
        
        # Extract results
        dead_functions_count = 0
        dead_functions_samples = []
        if dead_functions_result and len(dead_functions_result) > 0:
            dead_functions_count = dead_functions_result[0].get("count", 0)
            dead_functions_samples = dead_functions_result[0].get("samples", [])
        
        dead_classes_count = 0
        dead_classes_samples = []
        if dead_classes_result and len(dead_classes_result) > 0:
            dead_classes_count = dead_classes_result[0].get("count", 0)
            dead_classes_samples = dead_classes_result[0].get("samples", [])
        
        return {
            "status": "success",
            "repository": repository,
            "dead_functions": dead_functions_count,
            "dead_classes": dead_classes_count,
            "dead_functions_samples": dead_functions_samples,
            "dead_classes_samples": dead_classes_samples
        }
        
    except Exception as e:
        logger.error(f"Error detecting dead code: {e}")
        return {
            "status": "error",
            "message": str(e),
            "dead_functions": 0,
            "dead_classes": 0
        }
