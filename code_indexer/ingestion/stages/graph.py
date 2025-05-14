"""
Graph Building Stage

This module handles building a graph representation in Neo4j from AST data.
"""

import os
import json
import logging
import hashlib
import time
from typing import Dict, Any, List, Optional

# Import Neo4j tool
from code_indexer.ingestion.direct.neo4j_tool import DirectNeo4jTool
from code_indexer.utils.ast_utils import find_entity_in_ast, get_function_info, get_class_info

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_graph")


def process_graph_building(input_file: str, output_file: Optional[str] = None,
                         neo4j_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
    
    try:
        # Load input data
        with open(input_file, "r") as f:
            input_data = json.load(f)
        
        # Extract ASTs
        asts = input_data.get("asts", [])
        if not asts:
            return {
                "status": "error",
                "message": "No ASTs found in input"
            }
        
        # Extract repository info
        repository = input_data.get("repository", "")
        repository_url = input_data.get("url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "")
        is_full_indexing = input_data.get("is_full_indexing", False)
        
        # Initialize Neo4j tool
        neo4j_tool = DirectNeo4jTool(
            uri=neo4j_config.get("uri", "bolt://localhost:7687"),
            user=neo4j_config.get("user", "neo4j"),
            password=neo4j_config.get("password", "password")
        )
        
        # Setup Neo4j schema
        setup_neo4j_schema(neo4j_tool)
        
        # Clear repository data if full indexing
        if is_full_indexing and repository:
            clear_repository_data(neo4j_tool, repository)
        
        # Process each AST
        processed_files = []
        failed_files = []
        
        # Stats tracking
        stats = {
            "files_processed": 0,
            "classes_created": 0,
            "functions_created": 0,
            "methods_created": 0,
            "imports_created": 0,
            "relationships_created": 0
        }
        
        for ast_data in asts:
            file_path = ast_data.get("file_path", "")
            if not file_path:
                continue
            
            try:
                # Create file node
                file_id = create_file_node(
                    neo4j_tool=neo4j_tool,
                    file_path=file_path,
                    language=ast_data.get("language", "unknown"),
                    repository=repository,
                    repository_url=repository_url,
                    commit=commit,
                    branch=branch
                )
                
                if not file_id:
                    logger.error(f"Failed to create file node for {file_path}")
                    failed_files.append({
                        "path": file_path,
                        "error": "Failed to create file node"
                    })
                    continue
                
                # Extract entities
                entity_stats = extract_entities(
                    neo4j_tool=neo4j_tool,
                    ast_data=ast_data,
                    file_id=file_id
                )
                
                # Update stats
                stats["files_processed"] += 1
                stats["classes_created"] += entity_stats.get("classes_created", 0)
                stats["functions_created"] += entity_stats.get("functions_created", 0)
                stats["methods_created"] += entity_stats.get("methods_created", 0)
                stats["imports_created"] += entity_stats.get("imports_created", 0)
                stats["relationships_created"] += entity_stats.get("relationships_created", 0)
                
                processed_files.append(file_path)
                logger.info(f"Successfully processed {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to process AST for {file_path}: {e}")
                failed_files.append({
                    "path": file_path,
                    "error": str(e)
                })
        
        result = {
            "status": "success",
            "repository": repository,
            "url": repository_url,
            "commit": commit,
            "branch": branch,
            "is_full_indexing": is_full_indexing,
            "files_processed": stats["files_processed"],
            "files_failed": len(failed_files),
            "entities_created": (
                stats["classes_created"] + 
                stats["functions_created"] + 
                stats["methods_created"] + 
                stats["imports_created"]
            ),
            "relationships_created": stats["relationships_created"],
            "stats": stats,
            "failed_files": failed_files[:10]  # Include only the first 10 failed files
        }
        
        # Save output if requested
        if output_file:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved output to {output_file}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error building graph: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def setup_neo4j_schema(neo4j_tool: DirectNeo4jTool) -> None:
    """
    Setup Neo4j schema with constraints and indexes.
    
    Args:
        neo4j_tool: Neo4j tool instance
    """
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
            neo4j_tool.execute_cypher(constraint)
        except Exception as e:
            logger.error(f"Error creating schema: {e}")
    
    logger.info("Neo4j schema setup complete")


def clear_repository_data(neo4j_tool: DirectNeo4jTool, repository: str) -> None:
    """
    Clear all data for a specific repository.
    
    Args:
        neo4j_tool: Neo4j tool instance
        repository: Repository name
    """
    query = """
    MATCH (f:File {repository: $repository})
    OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
    DETACH DELETE f, entity
    """
    
    neo4j_tool.execute_cypher(query, {
        "repository": repository
    })
    
    logger.info(f"Cleared data for repository: {repository}")


def create_file_node(neo4j_tool: DirectNeo4jTool, file_path: str, language: str,
                   repository: str, repository_url: str, commit: str, branch: str) -> str:
    """
    Create a file node in the graph.
    
    Args:
        neo4j_tool: Neo4j tool instance
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
    
    result = neo4j_tool.execute_cypher(query, {
        "id": file_id,
        "props": file_props
    })
    
    # Check if file was created successfully
    if result and len(result) > 0:
        return file_id
    
    return ""


def extract_entities(neo4j_tool: DirectNeo4jTool, ast_data: Dict[str, Any],
                   file_id: str) -> Dict[str, int]:
    """
    Extract entities from AST and create nodes in the graph.
    
    Args:
        neo4j_tool: Neo4j tool instance
        ast_data: AST data dictionary
        file_id: ID of the file node
        
    Returns:
        Dictionary with entity statistics
    """
    stats = {
        "classes_created": 0,
        "functions_created": 0,
        "methods_created": 0,
        "imports_created": 0,
        "relationships_created": 0
    }
    
    # Extract entities based on language and AST structure
    language = ast_data.get("language", "unknown")
    file_path = ast_data.get("file_path", "")
    
    # Handle different AST formats
    if "root" in ast_data:
        ast_root = ast_data["root"]
        
        # Extract classes
        class_nodes = find_entity_in_ast(ast_root, "ClassDef")
        for class_node in class_nodes:
            class_info = get_class_info(class_node, language)
            
            if not class_info.get("name"):
                continue
                
            # Create class node
            class_id = create_class_node(
                neo4j_tool=neo4j_tool,
                class_name=class_info.get("name", ""),
                docstring=class_info.get("docstring", ""),
                start_line=class_info.get("start_line", 0),
                end_line=class_info.get("end_line", 0),
                file_id=file_id,
                parents=class_info.get("parents", [])
            )
            
            if class_id:
                stats["classes_created"] += 1
                stats["relationships_created"] += 1  # CONTAINS relationship to file
                
                # Create inheritance relationships
                if class_info.get("parents"):
                    for parent in class_info.get("parents", []):
                        create_inheritance_relationship(
                            neo4j_tool=neo4j_tool,
                            class_id=class_id,
                            parent_name=parent
                        )
                        stats["relationships_created"] += 1
        
        # Extract functions
        function_nodes = find_entity_in_ast(ast_root, "FunctionDef")
        for function_node in function_nodes:
            function_info = get_function_info(function_node, language)
            
            if not function_info.get("name"):
                continue
                
            # Determine if this is a method
            is_method = function_info.get("is_method", False)
            class_id = ""
            
            if is_method:
                class_name = function_info.get("class_name", "")
                if class_name:
                    class_id = hashlib.md5(f"{file_id}:{class_name}".encode()).hexdigest()
            
            # Create function/method node
            function_id = create_function_node(
                neo4j_tool=neo4j_tool,
                function_name=function_info.get("name", ""),
                docstring=function_info.get("docstring", ""),
                start_line=function_info.get("start_line", 0),
                end_line=function_info.get("end_line", 0),
                params=function_info.get("params", []),
                file_id=file_id,
                class_id=class_id,
                is_method=is_method
            )
            
            if function_id:
                if is_method:
                    stats["methods_created"] += 1
                    stats["relationships_created"] += 2  # CONTAINS relationships to class and file
                else:
                    stats["functions_created"] += 1
                    stats["relationships_created"] += 1  # CONTAINS relationship to file
        
        # Extract imports
        if language == "python":
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
                        # Create import relationship
                        if create_import_node(
                            neo4j_tool=neo4j_tool,
                            import_name=name,
                            alias=asname,
                            file_id=file_id
                        ):
                            stats["imports_created"] += 1
                            stats["relationships_created"] += 1
            
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
                        # Create import_from relationship
                        if create_import_from_node(
                            neo4j_tool=neo4j_tool,
                            module=module,
                            name=name,
                            alias=asname,
                            level=level,
                            file_id=file_id
                        ):
                            stats["imports_created"] += 1
                            stats["relationships_created"] += 1
    
    return stats


def create_class_node(neo4j_tool: DirectNeo4jTool, class_name: str, docstring: str,
                    start_line: int, end_line: int, file_id: str,
                    parents: List[str]) -> str:
    """
    Create a class node in the graph.
    
    Args:
        neo4j_tool: Neo4j tool instance
        class_name: Name of the class
        docstring: Class documentation string
        start_line: Starting line number
        end_line: Ending line number
        file_id: ID of the file containing the class
        parents: List of parent class names
        
    Returns:
        ID of the created class node
    """
    # Generate a unique ID for the class
    class_id = hashlib.md5(f"{file_id}:{class_name}".encode()).hexdigest()
    
    # Create class node properties
    class_props = {
        "id": class_id,
        "name": class_name,
        "docstring": docstring,
        "start_line": start_line,
        "end_line": end_line,
        "file_id": file_id,
        "parents": parents
    }
    
    # Create class node and relationship to file
    query = """
    MERGE (c:Class {id: $id})
    ON CREATE SET c = $props, c.created_at = timestamp()
    ON MATCH SET c = $props
    WITH c
    MATCH (f:File {id: $file_id})
    MERGE (f)-[:CONTAINS]->(c)
    RETURN c.id
    """
    
    result = neo4j_tool.execute_cypher(query, {
        "id": class_id,
        "props": class_props,
        "file_id": file_id
    })
    
    # Check if class was created successfully
    if result and len(result) > 0:
        return class_id
    
    return ""


def create_function_node(neo4j_tool: DirectNeo4jTool, function_name: str, docstring: str,
                       start_line: int, end_line: int, params: List[str],
                       file_id: str, class_id: str = None, is_method: bool = False) -> str:
    """
    Create a function node in the graph.
    
    Args:
        neo4j_tool: Neo4j tool instance
        function_name: Name of the function
        docstring: Function documentation string
        start_line: Starting line number
        end_line: Ending line number
        params: List of parameter names
        file_id: ID of the file containing the function
        class_id: ID of the class if it's a method (optional)
        is_method: True if this is a class method
        
    Returns:
        ID of the created function node
    """
    # Generate a unique ID for the function
    function_id = hashlib.md5(
        f"{file_id}:{function_name}:{class_id or ''}".encode()
    ).hexdigest()
    
    # Create function node properties
    function_props = {
        "id": function_id,
        "name": function_name,
        "docstring": docstring,
        "start_line": start_line,
        "end_line": end_line,
        "params": params,
        "file_id": file_id,
        "class_id": class_id,
        "is_method": is_method
    }
    
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
        
        result = neo4j_tool.execute_cypher(query, {
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
        
        result = neo4j_tool.execute_cypher(query, {
            "id": function_id,
            "props": function_props,
            "file_id": file_id
        })
    
    # Check if function was created successfully
    if result and len(result) > 0:
        return function_id
    
    return ""


def create_inheritance_relationship(neo4j_tool: DirectNeo4jTool, class_id: str,
                                 parent_name: str) -> bool:
    """
    Create an inheritance relationship between a class and its parent.
    
    Args:
        neo4j_tool: Neo4j tool instance
        class_id: ID of the child class
        parent_name: Name of the parent class
        
    Returns:
        True if relationship was created, False otherwise
    """
    query = """
    MATCH (child:Class {id: $class_id})
    MATCH (parent:Class {name: $parent_name})
    MERGE (child)-[:INHERITS_FROM]->(parent)
    RETURN count(*)
    """
    
    result = neo4j_tool.execute_cypher(query, {
        "class_id": class_id,
        "parent_name": parent_name
    })
    
    return result and len(result) > 0


def create_import_node(neo4j_tool: DirectNeo4jTool, import_name: str,
                     alias: str, file_id: str) -> bool:
    """
    Create an import node and relationship.
    
    Args:
        neo4j_tool: Neo4j tool instance
        import_name: Name of the imported module
        alias: Alias for the import
        file_id: ID of the file containing the import
        
    Returns:
        True if import was created, False otherwise
    """
    query = """
    MATCH (f:File {id: $file_id})
    MERGE (i:Import {name: $name})
    ON CREATE SET i.created_at = timestamp()
    SET i.alias = $alias
    MERGE (f)-[:IMPORTS]->(i)
    RETURN i.name
    """
    
    result = neo4j_tool.execute_cypher(query, {
        "file_id": file_id,
        "name": import_name,
        "alias": alias if alias else None
    })
    
    return result and len(result) > 0


def create_import_from_node(neo4j_tool: DirectNeo4jTool, module: str, name: str,
                         alias: str, level: int, file_id: str) -> bool:
    """
    Create an import from node and relationship.
    
    Args:
        neo4j_tool: Neo4j tool instance
        module: Name of the module
        name: Name of the imported item
        alias: Alias for the import
        level: Level of relative import
        file_id: ID of the file containing the import
        
    Returns:
        True if import was created, False otherwise
    """
    full_name = f"{module}.{name}"
    
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
    
    result = neo4j_tool.execute_cypher(query, {
        "file_id": file_id,
        "full_name": full_name,
        "module": module,
        "name": name,
        "alias": alias if alias else None,
        "level": level
    })
    
    return result and len(result) > 0