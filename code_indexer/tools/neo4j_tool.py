"""
Neo4j Tool

Tool for interacting with Neo4j graph database to store code structure.
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from google.adk.agents.llm_agent import BaseTool
from google.adk.agents.llm_agent import ToolContext
from google.adk.tools.google_api_tool import ToolResponse, ToolStatus

# Import Neo4j conditionally to handle environments without it
try:
    from neo4j import GraphDatabase, basic_auth
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    logging.warning("Neo4j driver not installed. Graph functionality will not work.")


class Neo4jTool(BaseTool):
    """
    Tool for Neo4j graph database operations.
    
    Provides functionality to create, update, and query the code knowledge graph
    stored in Neo4j.
    """
    
    def __init__(self):
        """Initialize the Neo4j tool."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.driver = None
        
        # Connection settings from environment variables
        self.uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.environ.get("NEO4J_USER", "neo4j")
        self.password = os.environ.get("NEO4J_PASSWORD", "password")
        self.database = os.environ.get("NEO4J_DATABASE", "neo4j")
        
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
    
    def create_file_node(self, file_id: str, path: str, language: str, 
                        repo_path: Optional[str] = None) -> str:
        """
        Create or update a File node in the graph.
        
        Args:
            file_id: Unique identifier for the file
            path: Path to the file within the repository
            language: Programming language of the file
            repo_path: Path to the repository (optional)
            
        Returns:
            ID of the created/updated node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (f:File {id: $file_id})
        SET f.path = $path,
            f.language = $language,
            f.repo_path = $repo_path,
            f.last_updated = timestamp()
        RETURN f.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                file_id=file_id,
                path=path,
                language=language,
                repo_path=repo_path
            )
            return result.single()[0]
    
    def create_class_node(self, class_id: str, name: str, file_id: str,
                         start_line: int, end_line: int, 
                         docstring: Optional[str] = None) -> str:
        """
        Create or update a Class node in the graph.
        
        Args:
            class_id: Unique identifier for the class
            name: Name of the class
            file_id: ID of the file containing the class
            start_line: Starting line number
            end_line: Ending line number
            docstring: Class documentation string (optional)
            
        Returns:
            ID of the created/updated node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (c:Class {id: $class_id})
        SET c.name = $name,
            c.file_id = $file_id,
            c.start_line = $start_line,
            c.end_line = $end_line,
            c.docstring = $docstring,
            c.last_updated = timestamp()
        RETURN c.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                class_id=class_id,
                name=name,
                file_id=file_id,
                start_line=start_line,
                end_line=end_line,
                docstring=docstring
            )
            return result.single()[0]
    
    def create_function_node(self, function_id: str, name: str, file_id: str,
                           start_line: int, end_line: int, params: List[str],
                           docstring: Optional[str] = None, 
                           class_id: Optional[str] = None,
                           is_method: bool = False) -> str:
        """
        Create or update a Function node in the graph.
        
        Args:
            function_id: Unique identifier for the function
            name: Name of the function
            file_id: ID of the file containing the function
            start_line: Starting line number
            end_line: Ending line number
            params: List of parameter names
            docstring: Function documentation string (optional)
            class_id: ID of the class if it's a method (optional)
            is_method: True if this is a class method
            
        Returns:
            ID of the created/updated node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (f:Function {id: $function_id})
        SET f.name = $name,
            f.file_id = $file_id,
            f.class_id = $class_id,
            f.start_line = $start_line,
            f.end_line = $end_line,
            f.params = $params,
            f.docstring = $docstring,
            f.is_method = $is_method,
            f.last_updated = timestamp()
        RETURN f.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                function_id=function_id,
                name=name,
                file_id=file_id,
                class_id=class_id,
                start_line=start_line,
                end_line=end_line,
                params=params,
                docstring=docstring,
                is_method=is_method
            )
            return result.single()[0]
    
    def create_relationship(self, from_id: str, to_id: str, rel_type: str,
                          properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a relationship between two nodes.
        
        Args:
            from_id: ID of the source node
            to_id: ID of the target node
            rel_type: Type of relationship (e.g., "CONTAINS", "CALLS")
            properties: Optional properties for the relationship
            
        Returns:
            True if relationship was created, False otherwise
        """
        if not self.driver:
            self.connect()
        
        query = f"""
        MATCH (from) WHERE from.id = $from_id
        MATCH (to) WHERE to.id = $to_id
        MERGE (from)-[r:{rel_type}]->(to)
        """
        
        # Add property setting if provided
        if properties:
            props_str = ", ".join(f"r.{k} = ${k}" for k in properties.keys())
            query += f" SET {props_str}"
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    query,
                    from_id=from_id,
                    to_id=to_id,
                    **properties or {}
                )
            return True
        except Exception as e:
            self.logger.error(f"Error creating relationship: {e}")
            return False
    
    def delete_file_and_contents(self, file_id: str) -> bool:
        """
        Delete a file node and all nodes contained within it.
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        if not self.driver:
            self.connect()
        
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:CONTAINS*]->(n)
        DETACH DELETE f, n
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run(query, file_id=file_id)
            return True
        except Exception as e:
            self.logger.error(f"Error deleting file and contents: {e}")
            return False
    
    def find_function_by_name(self, name: str) -> List[str]:
        """
        Find function nodes by name.
        
        Args:
            name: Name of the function to find
            
        Returns:
            List of function IDs matching the name
        """
        if not self.driver:
            self.connect()
        
        query = """
        MATCH (f:Function)
        WHERE f.name = $name
        RETURN f.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(query, name=name)
            return [record[0] for record in result]
    
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
    
    # ADK Tool methods
    def execute_query(self, input_data: Dict[str, Any], context: Optional[ToolContext] = None) -> ToolResponse:
        """
        Execute a Cypher query through the ADK tool interface.
        
        Args:
            input_data: Dictionary with query and parameters
            context: Tool context
            
        Returns:
            ToolResponse with query results
        """
        query = input_data.get("query", "")
        params = input_data.get("params", {})
        database = input_data.get("database", self.database)
        
        if not query:
            return ToolResponse(
                status=ToolStatus.error("No query provided"),
                data={"results": []}
            )
        
        try:
            with self.driver.session(database=database) as session:
                result = session.run(query, params or {})
                results = [dict(record) for record in result]
                
                return ToolResponse(
                    status=ToolStatus.success(),
                    data={"results": results}
                )
        except Exception as e:
            return ToolResponse(
                status=ToolStatus.error(f"Query execution failed: {str(e)}"),
                data={"results": []}
            )
    
    def create_module_node(self, module_id: str, name: str, file_id: str = None) -> str:
        """
        Create or update a Module node in the graph.
        
        Args:
            module_id: Unique identifier for the module
            name: Name of the module
            file_id: ID of the file containing the module (optional)
            
        Returns:
            ID of the created/updated node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (m:Module {id: $module_id})
        SET m.name = $name,
            m.file_id = $file_id,
            m.last_updated = timestamp()
        RETURN m.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                module_id=module_id,
                name=name,
                file_id=file_id
            )
            return result.single()[0]
    
    def create_import_relationship(self, from_file_id: str, to_module: str) -> bool:
        """
        Create an IMPORTS relationship between a file and a module.
        
        Args:
            from_file_id: ID of the file doing the importing
            to_module: Name of the imported module
            
        Returns:
            True if relationship was created, False otherwise
        """
        if not self.driver:
            self.connect()
        
        # Create module node if it doesn't exist
        module_id = to_module.replace(".", "_")
        self.create_module_node(module_id, to_module)
        
        # Create IMPORTS relationship
        return self.create_relationship(
            from_id=from_file_id,
            to_id=module_id,
            rel_type="IMPORTS"
        )
    
    def get_class_methods(self, class_id: str) -> List[Dict[str, Any]]:
        """
        Get all methods of a class.
        
        Args:
            class_id: ID of the class
            
        Returns:
            List of method information
        """
        if not self.driver:
            self.connect()
        
        query = """
        MATCH (c:Class {id: $class_id})-[:CONTAINS]->(m:Function)
        WHERE m.is_method = true
        RETURN m.id as id, m.name as name, m.start_line as start_line, 
               m.end_line as end_line, m.params as params
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, class_id=class_id)
                return [dict(record) for record in result]
        except Exception as e:
            self.logger.error(f"Error getting class methods: {e}")
            return []
    
    def find_call_relationships(self, function_id: str) -> Dict[str, List[str]]:
        """
        Find call relationships for a function.
        
        Args:
            function_id: ID of the function
            
        Returns:
            Dictionary with called_by and calls lists
        """
        if not self.driver:
            self.connect()
        
        result = {
            "called_by": [],
            "calls": []
        }
        
        # Find functions that call this function
        query1 = """
        MATCH (caller:Function)-[:CALLS]->(f:Function {id: $function_id})
        RETURN caller.id as id, caller.name as name
        """
        
        # Find functions that this function calls
        query2 = """
        MATCH (f:Function {id: $function_id})-[:CALLS]->(called:Function)
        RETURN called.id as id, called.name as name
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                # Get called_by relationships
                called_by = session.run(query1, function_id=function_id)
                result["called_by"] = [f"{record['name']} ({record['id']})" for record in called_by]
                
                # Get calls relationships
                calls = session.run(query2, function_id=function_id)
                result["calls"] = [f"{record['name']} ({record['id']})" for record in calls]
                
            return result
        except Exception as e:
            self.logger.error(f"Error finding call relationships: {e}")
            return result
    
    def __del__(self):
        """Close connection when object is destroyed."""
        self.close()