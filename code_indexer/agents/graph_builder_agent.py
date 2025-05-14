"""
Graph Builder Agent

This agent builds a knowledge graph from code ASTs using Neo4j.
"""

import os
import logging
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union

from google.adk import Agent
from google.adk.decorators import init_agent
from google.adk.api.agent import AgentContext, HandlerResponse
from google.adk.api.tool import ToolResponse, ToolStatus

from code_indexer.tools.neo4j_tool import Neo4jTool
from code_indexer.utils.ast_utils import find_entity_in_ast, get_function_info, get_class_info


@init_agent(name="graph_builder_agent")
class GraphBuilderAgent(Agent):
    """
    Agent responsible for building and updating the code knowledge graph.
    
    This agent takes AST structures from the CodeParserAgent and creates
    a graph representation in Neo4j, capturing code entities and their relationships.
    """
    
    def __init__(self, name: str = "graph_builder_agent", **kwargs):
        """
        Initialize the Graph Builder Agent.
        
        Args:
            name: Agent name
            **kwargs: Additional parameters including config
        """
        super().__init__(name=name)
        self.config = kwargs.get("config", {})
        self.logger = logging.getLogger(name)
        
        # Configure defaults
        self.use_imports = self.config.get("use_imports", True)
        self.use_inheritance = self.config.get("use_inheritance", True)
        self.detect_calls = self.config.get("detect_calls", True)
        
        # State
        self.neo4j_tool = None
        self.graph_stats = {
            "files": 0,
            "classes": 0,
            "functions": 0,
            "relationships": 0
        }
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get Neo4j tool
        self.neo4j_tool = Neo4jTool()
        
        # Setup Neo4j connection
        try:
            # Check if we can connect and create constraints if needed
            if self.neo4j_tool.connect():
                self._setup_schema()
                self.logger.info("Successfully connected to Neo4j")
            else:
                self.logger.error("Failed to connect to Neo4j database")
        except Exception as e:
            self.logger.error(f"Error initializing Neo4j: {e}")
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Build the knowledge graph from AST structures.
        
        Args:
            input_data: Dictionary containing AST structures
            
        Returns:
            HandlerResponse with graph building results
        """
        self.logger.info("Starting graph builder agent")
        
        # Extract ASTs from input
        asts = input_data.get("asts", [])
        if not asts:
            return HandlerResponse.error("No ASTs to process")
        
        repository = input_data.get("repository", "")
        repository_url = input_data.get("repository_url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "")
        is_full_indexing = input_data.get("is_full_indexing", False)
        
        # If full indexing, clear repository data
        if is_full_indexing and repository:
            self._clear_repository_data(repository)

        # Process each AST
        processed_files = []
        failed_files = []
        
        for ast_data in asts:
            file_path = ast_data.get("file_path", "")
            if not file_path:
                continue
                
            try:
                # Build graph for this AST
                result = self._process_ast(
                    ast_data=ast_data,
                    repository=repository,
                    repository_url=repository_url,
                    commit=commit,
                    branch=branch
                )
                
                if result.get("status") == "success":
                    processed_files.append(file_path)
                else:
                    failed_files.append({
                        "path": file_path,
                        "error": result.get("error", "Unknown error")
                    })
            except Exception as e:
                self.logger.error(f"Error processing AST for {file_path}: {e}")
                failed_files.append({
                    "path": file_path,
                    "error": str(e)
                })
        
        return HandlerResponse.success({
            "repository": repository,
            "files_processed": len(processed_files),
            "files_failed": len(failed_files),
            "graph_stats": self.graph_stats,
            "failed_files": failed_files[:10]  # Include only the first 10 failed files
        })
    
    def _process_ast(self, ast_data: Dict[str, Any], repository: str,
                   repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process a single AST and build corresponding graph.
        
        Args:
            ast_data: AST data dictionary
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract AST data
            file_path = ast_data.get("file_path", "")
            language = ast_data.get("language", "unknown")
            ast_root = ast_data.get("root", {})
            
            if not file_path or not ast_root:
                return {
                    "status": "error",
                    "error": "Missing file path or AST root"
                }
            
            # Create file node
            file_id = self._create_file_node(
                file_path=file_path,
                language=language,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            if not file_id:
                return {
                    "status": "error",
                    "error": "Failed to create file node"
                }
            
            # Extract and create entities (classes, functions, etc.)
            entity_count = self._extract_entities(
                ast_root=ast_root,
                file_id=file_id,
                file_path=file_path,
                language=language
            )
            
            # Create relationships between entities
            relationship_count = self._create_relationships(
                ast_root=ast_root,
                file_id=file_id
            )
            
            # Update stats
            self.graph_stats["files"] += 1
            
            return {
                "status": "success",
                "file_id": file_id,
                "entity_count": entity_count,
                "relationship_count": relationship_count
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _create_file_node(self, file_path: str, language: str, repository: str,
                       repository_url: str, commit: str, branch: str) -> str:
        """
        Create a file node in the graph.
        
        Args:
            file_path: Path to the file
            language: Programming language
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            ID of the created file node
        """
        # Generate a unique ID for the file
        file_id = hashlib.md5(f"{repository}:{file_path}".encode()).hexdigest()
        
        # Create file node properties
        file_props = {
            "id": file_id,
            "path": file_path,
            "name": os.path.basename(file_path),
            "language": language,
            "repository": repository,
            "repository_url": repository_url,
            "commit": commit,
            "branch": branch,
            "last_updated": int(time.time())
        }
        
        # Create or update file node
        query = """
        MERGE (f:File {id: $id})
        ON CREATE SET f = $props, f.created_at = timestamp()
        ON MATCH SET f = $props
        RETURN f.id
        """
        
        result = self.neo4j_tool.execute_cypher(query, {
            "id": file_id,
            "props": file_props
        })
        
        # Check if file was created successfully
        if result and len(result) > 0:
            return file_id
        
        return ""
    
    def _extract_entities(self, ast_root: Dict[str, Any], file_id: str,
                      file_path: str, language: str) -> int:
        """
        Extract entities from the AST and create nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            file_path: Path to the file
            language: Programming language
            
        Returns:
            Number of entities extracted
        """
        entity_count = 0
        
        # Process classes and functions in the AST
        classes = self._extract_classes(ast_root, file_id, file_path, language)
        entity_count += len(classes)
        self.graph_stats["classes"] += len(classes)
        
        functions = self._extract_functions(ast_root, file_id, file_path, language)
        entity_count += len(functions)
        self.graph_stats["functions"] += len(functions)
        
        # Extract other entities for specific languages
        if language == "python":
            # Extract imports for Python
            if self.use_imports:
                imports = self._extract_imports(ast_root, file_id)
                entity_count += len(imports)
        
        return entity_count
    
    def _extract_classes(self, ast_root: Dict[str, Any], file_id: str,
                      file_path: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract classes from the AST and create nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of created class nodes
        """
        classes = []
        
        # Find class nodes in the AST
        class_nodes = find_entity_in_ast(ast_root, "ClassDef")
        
        for class_node in class_nodes:
            # Extract class information
            class_info = get_class_info(class_node, language)
            
            if not class_info.get("name"):
                continue
                
            # Generate a unique ID for the class
            class_id = hashlib.md5(f"{file_id}:{class_info['name']}".encode()).hexdigest()
            
            # Create class node properties
            class_props = {
                "id": class_id,
                "name": class_info.get("name", ""),
                "docstring": class_info.get("docstring", ""),
                "start_line": class_info.get("start_line", 0),
                "end_line": class_info.get("end_line", 0),
                "file_id": file_id,
                "parents": class_info.get("parents", [])
            }
            
            # Create class node
            query = """
            MERGE (c:Class {id: $id})
            ON CREATE SET c = $props, c.created_at = timestamp()
            ON MATCH SET c = $props
            WITH c
            MATCH (f:File {id: $file_id})
            MERGE (f)-[:CONTAINS]->(c)
            RETURN c.id
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "id": class_id,
                "props": class_props,
                "file_id": file_id
            })
            
            if result and len(result) > 0:
                # Add class inheritance relationships if available
                if self.use_inheritance and class_info.get("parents"):
                    for parent in class_info["parents"]:
                        # For simplicity, just connect by name - in a real system
                        # you'd need to resolve the parent class more accurately
                        self._create_inheritance_relationship(class_id, parent)
                
                # Add the class to the result list
                classes.append({
                    "id": class_id,
                    "name": class_info.get("name", ""),
                    "file_id": file_id
                })
        
        return classes
    
    def _extract_functions(self, ast_root: Dict[str, Any], file_id: str,
                        file_path: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract functions from the AST and create nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of created function nodes
        """
        functions = []
        
        # Find function nodes in the AST
        function_nodes = find_entity_in_ast(ast_root, "FunctionDef")
        
        for function_node in function_nodes:
            # Extract function information
            function_info = get_function_info(function_node, language)
            
            if not function_info.get("name"):
                continue
                
            # Determine if this is a method (within a class)
            is_method = function_info.get("is_method", False)
            class_id = ""
            
            if is_method:
                class_name = function_info.get("class_name", "")
                if class_name:
                    class_id = hashlib.md5(f"{file_id}:{class_name}".encode()).hexdigest()
            
            # Generate a unique ID for the function
            function_id = hashlib.md5(
                f"{file_id}:{function_info['name']}:{class_id}".encode()
            ).hexdigest()
            
            # Create function node properties
            function_props = {
                "id": function_id,
                "name": function_info.get("name", ""),
                "docstring": function_info.get("docstring", ""),
                "start_line": function_info.get("start_line", 0),
                "end_line": function_info.get("end_line", 0),
                "params": function_info.get("params", []),
                "return_type": function_info.get("return_type", ""),
                "file_id": file_id,
                "class_id": class_id,
                "is_method": is_method
            }
            
            # Create function node
            if is_method and class_id:
                # Connect to both file and class if it's a method
                query = """
                MERGE (f:Function {id: $id})
                ON CREATE SET f = $props, f.created_at = timestamp()
                ON MATCH SET f = $props
                WITH f
                MATCH (c:Class {id: $class_id})
                MERGE (c)-[:CONTAINS]->(f)
                WITH f
                MATCH (file:File {id: $file_id})
                MERGE (file)-[:CONTAINS]->(f)
                RETURN f.id
                """
                
                result = self.neo4j_tool.execute_cypher(query, {
                    "id": function_id,
                    "props": function_props,
                    "class_id": class_id,
                    "file_id": file_id
                })
            else:
                # Only connect to file if it's a standalone function
                query = """
                MERGE (f:Function {id: $id})
                ON CREATE SET f = $props, f.created_at = timestamp()
                ON MATCH SET f = $props
                WITH f
                MATCH (file:File {id: $file_id})
                MERGE (file)-[:CONTAINS]->(f)
                RETURN f.id
                """
                
                result = self.neo4j_tool.execute_cypher(query, {
                    "id": function_id,
                    "props": function_props,
                    "file_id": file_id
                })
            
            if result and len(result) > 0:
                # Add the function to the result list
                functions.append({
                    "id": function_id,
                    "name": function_info.get("name", ""),
                    "is_method": is_method,
                    "class_id": class_id,
                    "file_id": file_id
                })
        
        return functions
    
    def _extract_imports(self, ast_root: Dict[str, Any], file_id: str) -> List[Dict[str, Any]]:
        """
        Extract imports from the AST and create nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            
        Returns:
            List of created import nodes
        """
        imports = []
        
        # Find import nodes in the AST
        import_nodes = find_entity_in_ast(ast_root, "Import")
        import_from_nodes = find_entity_in_ast(ast_root, "ImportFrom")
        
        # Process Import statements
        for import_node in import_nodes:
            if "names" not in import_node.get("attributes", {}):
                continue
                
            for alias in import_node["attributes"]["names"]:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name:
                    # Generate a unique ID for the import
                    import_id = hashlib.md5(f"{file_id}:import:{name}".encode()).hexdigest()
                    
                    # Create import relationship
                    query = """
                    MATCH (f:File {id: $file_id})
                    MERGE (i:Import {name: $name})
                    ON CREATE SET i.created_at = timestamp()
                    SET i.alias = $alias
                    MERGE (f)-[:IMPORTS]->(i)
                    RETURN i.name
                    """
                    
                    result = self.neo4j_tool.execute_cypher(query, {
                        "file_id": file_id,
                        "name": name,
                        "alias": asname if asname else None
                    })
                    
                    if result and len(result) > 0:
                        imports.append({
                            "name": name,
                            "alias": asname,
                            "type": "import"
                        })
        
        # Process ImportFrom statements
        for import_from_node in import_from_nodes:
            if "names" not in import_from_node.get("attributes", {}):
                continue
                
            module = import_from_node["attributes"].get("module", "")
            level = import_from_node["attributes"].get("level", 0)
            
            for alias in import_from_node["attributes"]["names"]:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name and module:
                    # Generate a unique ID for the import
                    import_id = hashlib.md5(
                        f"{file_id}:import_from:{module}.{name}".encode()
                    ).hexdigest()
                    
                    # Create import_from relationship
                    query = """
                    MATCH (f:File {id: $file_id})
                    MERGE (i:Import {name: $full_name})
                    ON CREATE SET i.created_at = timestamp()
                    SET i.module = $module,
                        i.member = $name,
                        i.alias = $alias,
                        i.level = $level
                    MERGE (f)-[:IMPORTS]->(i)
                    RETURN i.name
                    """
                    
                    result = self.neo4j_tool.execute_cypher(query, {
                        "file_id": file_id,
                        "full_name": f"{module}.{name}",
                        "module": module,
                        "name": name,
                        "alias": asname if asname else None,
                        "level": level
                    })
                    
                    if result and len(result) > 0:
                        imports.append({
                            "module": module,
                            "name": name,
                            "alias": asname,
                            "type": "import_from"
                        })
        
        return imports
    
    def _create_relationships(self, ast_root: Dict[str, Any], file_id: str) -> int:
        """
        Create relationships between entities in the graph.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            
        Returns:
            Number of relationships created
        """
        relationship_count = 0
        
        if self.detect_calls:
            # Extract function calls from AST and create CALLS relationships
            call_relationships = self._extract_function_calls(ast_root, file_id)
            relationship_count += call_relationships
            self.graph_stats["relationships"] += call_relationships
        
        return relationship_count
    
    def _extract_function_calls(self, ast_root: Dict[str, Any], file_id: str) -> int:
        """
        Extract function calls from the AST and create CALLS relationships.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            
        Returns:
            Number of call relationships created
        """
        call_count = 0
        
        # Find Call nodes in the AST
        call_nodes = find_entity_in_ast(ast_root, "Call")
        
        for call_node in call_nodes:
            # Get the function being called
            if "func" not in call_node.get("attributes", {}):
                continue
                
            func = call_node["attributes"]["func"]
            
            # Handle different call patterns
            if func.get("type") == "Name":
                # Simple function call: function_name()
                callee_name = func.get("attributes", {}).get("id", "")
                if callee_name:
                    self._create_call_relationship(file_id, callee_name, "")
                    call_count += 1
                    
            elif func.get("type") == "Attribute":
                # Method call: object.method()
                callee_name = func.get("attributes", {}).get("attr", "")
                value = func.get("attributes", {}).get("value", {})
                if callee_name and value.get("type") == "Name":
                    # Get the object name
                    object_name = value.get("attributes", {}).get("id", "")
                    if object_name:
                        self._create_call_relationship(file_id, callee_name, object_name)
                        call_count += 1
        
        return call_count
    
    def _create_call_relationship(self, file_id: str, function_name: str, 
                               class_name: str = "") -> None:
        """
        Create a CALLS relationship between a file and a function.
        
        Args:
            file_id: ID of the calling file
            function_name: Name of the called function
            class_name: Name of the class (if a method call)
        """
        if class_name:
            # This is a method call
            query = """
            MATCH (caller:File {id: $file_id})
            MATCH (callee:Function)
            WHERE callee.name = $function_name
              AND EXISTS((callee)<-[:CONTAINS]-(:Class {name: $class_name}))
            MERGE (caller)-[:CALLS]->(callee)
            """
            
            self.neo4j_tool.execute_cypher(query, {
                "file_id": file_id,
                "function_name": function_name,
                "class_name": class_name
            })
        else:
            # This is a function call
            query = """
            MATCH (caller:File {id: $file_id})
            MATCH (callee:Function {name: $function_name})
            MERGE (caller)-[:CALLS]->(callee)
            """
            
            self.neo4j_tool.execute_cypher(query, {
                "file_id": file_id,
                "function_name": function_name
            })
    
    def _create_inheritance_relationship(self, class_id: str, parent_name: str) -> None:
        """
        Create an INHERITS_FROM relationship between a class and its parent.
        
        Args:
            class_id: ID of the child class
            parent_name: Name of the parent class
        """
        query = """
        MATCH (child:Class {id: $class_id})
        MATCH (parent:Class {name: $parent_name})
        MERGE (child)-[:INHERITS_FROM]->(parent)
        """
        
        self.neo4j_tool.execute_cypher(query, {
            "class_id": class_id,
            "parent_name": parent_name
        })
    
    def _clear_repository_data(self, repository: str) -> None:
        """
        Clear all data for a specific repository.
        
        Args:
            repository: Repository name
        """
        query = """
        MATCH (f:File {repository: $repository})
        OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
        DETACH DELETE f, entity
        """
        
        self.neo4j_tool.execute_cypher(query, {
            "repository": repository
        })
        
        self.logger.info(f"Cleared data for repository: {repository}")
    
    def _setup_schema(self) -> None:
        """Setup Neo4j schema with constraints and indexes for better performance."""
        # Create constraints
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Function) REQUIRE f.id IS UNIQUE",
            
            # Add indexes for commonly queried properties
            "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)",
            "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.repository)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name)"
        ]
        
        for constraint in constraints:
            try:
                self.neo4j_tool.execute_cypher(constraint)
            except Exception as e:
                self.logger.error(f"Error creating schema: {e}")
        
        self.logger.info("Neo4j schema setup complete")
        
