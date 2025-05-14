"""
Direct Neo4j Tool

Direct implementation of the Neo4j tool without ADK dependencies.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

# Conditional import for Neo4j
try:
    from neo4j import GraphDatabase, basic_auth
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    logging.warning("Neo4j driver not installed. Graph functionality will not work.")


class DirectNeo4jTool:
    """
    Direct Neo4j tool without ADK dependencies.
    
    Provides functionality to interact with Neo4j graph database.
    """
    
    def __init__(self, uri=None, user=None, password=None, database=None):
        """
        Initialize the Neo4j tool.
        
        Args:
            uri: Neo4j URI (default: from env var NEO4J_URI or "bolt://localhost:7687")
            user: Neo4j username (default: from env var NEO4J_USER or "neo4j")
            password: Neo4j password (default: from env var NEO4J_PASSWORD or "password")
            database: Neo4j database (default: from env var NEO4J_DATABASE or "neo4j")
        """
        self.logger = logging.getLogger(__name__)
        self.driver = None
        
        # Connection settings from parameters or environment variables
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self.database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        
        # Connect to Neo4j
        self.connect()
    
    def connect(self) -> bool:
        """
        Connect to Neo4j database.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        if not HAS_NEO4J:
            self.logger.error("Neo4j driver not installed")
            return False
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=basic_auth(self.user, self.password)
            )
            # Test connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            self.logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            self.driver = None
            return False
    
    def close(self) -> None:
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None
    
    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom Cypher query.
        
        Args:
            query: Cypher query string
            params: Query parameters
            
        Returns:
            List of results as dictionaries
        """
        if not self.driver:
            self.connect()
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            self.logger.error(f"Error executing Cypher query: {e}")
            raise
    
    def __del__(self):
        """Close connection when object is destroyed."""
        self.close()