"""
Graph Builder
Builds knowledge graph from AST data using batch operations for performance.
"""

import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase


class GraphBuilder:
    """Graph builder that creates knowledge graph from AST data."""
    
    def __init__(self, neo4j_config: Dict[str, Any]):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            neo4j_config["uri"],
            auth=(neo4j_config["user"], neo4j_config["password"])
        )
        self.batch_size = neo4j_config.get("batch_size", 1000)
        self.stats = {
            "functions": 0,
            "classes": 0,
            "call_sites": 0,
            "files": 0,
            "resolved_calls": 0,
            "resolved_imports": 0
        }
        
    def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            self.driver.close()
            
    def clear_repository(self, repository: str):
        """Clear all nodes for a specific repository."""
        with self.driver.session() as session:
            # Delete in chunks to avoid memory issues
            deleted = 1
            while deleted > 0:
                result = session.run("""
                    MATCH (n)
                    WHERE n.repository = $repository
                    WITH n LIMIT 10000
                    DETACH DELETE n
                    RETURN count(n) as deleted
                """, repository=repository)
                deleted = result.single()["deleted"]
                if deleted > 0:
                    self.logger.info(f"Deleted {deleted} nodes...")
            
    def process_file(self, file_path: str, ast_data: Dict[str, Any], repository: str) -> Dict[str, int]:
        """Process a single file and extract all entities."""
        # Determine AST format
        ast_format = "tree-sitter" if ast_data.get("parser") == "tree-sitter" else "native"
        ast_root = ast_data.get("root", ast_data)
        
        # Generate file ID
        file_id = hashlib.md5(f"{repository}:{file_path}".encode()).hexdigest()
        
        # Collect all entities from this file
        entities = {
            "file": {
                "id": file_id,
                "path": file_path,
                "repository": repository,
                "language": ast_data.get("language", "unknown")
            },
            "functions": [],
            "classes": [],
            "call_sites": []
        }
        
        # Extract entities
        self._extract_functions(ast_root, ast_format, file_id, repository, entities["functions"])
        self._extract_classes(ast_root, ast_format, file_id, repository, entities["classes"])
        self._extract_call_sites(ast_root, ast_format, file_id, repository, entities["call_sites"])
        
        # Return counts
        return {
            "functions": len(entities["functions"]),
            "classes": len(entities["classes"]),
            "call_sites": len(entities["call_sites"])
        }
        
    def process_batch(self, files_batch: List[Tuple[str, Dict[str, Any], str]]):
        """Process a batch of files efficiently."""
        all_entities = {
            "files": [],
            "functions": [],
            "classes": [],
            "call_sites": []
        }
        
        # Collect all entities from all files in the batch
        for file_path, ast_data, repository in files_batch:
            # Determine AST format
            ast_format = "tree-sitter" if ast_data.get("parser") == "tree-sitter" else "native"
            ast_root = ast_data.get("root", ast_data)
            
            # Generate file ID
            file_id = hashlib.md5(f"{repository}:{file_path}".encode()).hexdigest()
            
            # Add file entity
            all_entities["files"].append({
                "id": file_id,
                "path": file_path,
                "repository": repository,
                "language": ast_data.get("language", "unknown")
            })
            
            # Extract entities for this file
            self._extract_functions(ast_root, ast_format, file_id, repository, all_entities["functions"])
            self._extract_classes(ast_root, ast_format, file_id, repository, all_entities["classes"])
            self._extract_call_sites(ast_root, ast_format, file_id, repository, all_entities["call_sites"])
        
        # Create all entities in batch
        self._batch_create_entities(all_entities)
        
        # Update stats
        self.stats["files"] += len(all_entities["files"])
        self.stats["functions"] += len(all_entities["functions"])
        self.stats["classes"] += len(all_entities["classes"])
        self.stats["call_sites"] += len(all_entities["call_sites"])
        
    def _batch_create_entities(self, entities: Dict[str, List[Dict[str, Any]]]):
        """Create all entities in a single batch transaction."""
        with self.driver.session() as session:
            # Create files
            if entities["files"]:
                session.run("""
                    UNWIND $files as file
                    MERGE (f:File {id: file.id})
                    SET f.path = file.path,
                        f.repository = file.repository,
                        f.language = file.language,
                        f.last_updated = timestamp()
                """, files=entities["files"])
            
            # Create functions and relationships
            if entities["functions"]:
                session.run("""
                    UNWIND $functions as func
                    MERGE (f:Function {id: func.id})
                    SET f.name = func.name,
                        f.file_id = func.file_id,
                        f.repository = func.repository,
                        f.last_updated = timestamp()
                    WITH f, func
                    MATCH (file:File {id: func.file_id})
                    MERGE (file)-[:CONTAINS]->(f)
                """, functions=entities["functions"])
            
            # Create classes and relationships
            if entities["classes"]:
                session.run("""
                    UNWIND $classes as cls
                    MERGE (c:Class {id: cls.id})
                    SET c.name = cls.name,
                        c.file_id = cls.file_id,
                        c.repository = cls.repository,
                        c.last_updated = timestamp()
                    WITH c, cls
                    MATCH (file:File {id: cls.file_id})
                    MERGE (file)-[:CONTAINS]->(c)
                """, classes=entities["classes"])
            
            # Create call sites and relationships
            if entities["call_sites"]:
                session.run("""
                    UNWIND $call_sites as cs
                    MERGE (call:CallSite {id: cs.id})
                    SET call.call_name = cs.call_name,
                        call.caller_file_id = cs.file_id,
                        call.repository = cs.repository,
                        call.start_line = cs.start_line,
                        call.last_updated = timestamp()
                    WITH call, cs
                    MATCH (file:File {id: cs.file_id})
                    MERGE (file)-[:CONTAINS]->(call)
                """, call_sites=entities["call_sites"])
    
    def _extract_functions(self, ast_node: Dict[str, Any], ast_format: str, 
                          file_id: str, repository: str, results: List[Dict[str, Any]]):
        """Extract function entities from AST."""
        # Map entity types for tree-sitter - different languages use different node types
        if ast_format == "tree-sitter":
            # Java uses method_declaration and constructor_declaration
            # Python uses function_definition
            # JavaScript uses function_declaration, method_definition, etc.
            search_types = ["function_definition", "function_declaration", 
                          "method_declaration", "method_definition", 
                          "constructor_declaration", "arrow_function"]
        else:
            search_types = ["FunctionDef"]
            
        # Check current node
        if ast_node.get("type") in search_types:
            name = self._extract_name(ast_node, "function", ast_format)
            if name:
                func_id = hashlib.md5(f"{file_id}:{name}".encode()).hexdigest()
                results.append({
                    "id": func_id,
                    "name": name,
                    "file_id": file_id,
                    "repository": repository
                })
        
        # Recurse through children
        for child in ast_node.get("children", []):
            if isinstance(child, dict):
                self._extract_functions(child, ast_format, file_id, repository, results)
    
    def _extract_classes(self, ast_node: Dict[str, Any], ast_format: str,
                        file_id: str, repository: str, results: List[Dict[str, Any]]):
        """Extract class entities from AST."""
        # Map entity types for tree-sitter - different languages use different node types
        if ast_format == "tree-sitter":
            # Java uses class_declaration, interface_declaration, enum_declaration
            # Python uses class_definition
            # JavaScript/TypeScript uses class_declaration
            search_types = ["class_definition", "class_declaration", 
                          "interface_declaration", "enum_declaration"]
        else:
            search_types = ["ClassDef"]
            
        # Check current node
        if ast_node.get("type") in search_types:
            name = self._extract_name(ast_node, "class", ast_format)
            if name:
                class_id = hashlib.md5(f"{file_id}:{name}".encode()).hexdigest()
                results.append({
                    "id": class_id,
                    "name": name,
                    "file_id": file_id,
                    "repository": repository
                })
        
        # Recurse through children
        for child in ast_node.get("children", []):
            if isinstance(child, dict):
                self._extract_classes(child, ast_format, file_id, repository, results)
    
    def _extract_call_sites(self, ast_node: Dict[str, Any], ast_format: str,
                           file_id: str, repository: str, results: List[Dict[str, Any]]):
        """Extract call site entities from AST."""
        # Map entity types for tree-sitter - different languages use different node types
        if ast_format == "tree-sitter":
            # Java uses method_invocation and object_creation_expression
            # Python uses call
            # JavaScript uses call_expression
            search_types = ["call", "call_expression", "method_invocation", 
                          "object_creation_expression", "new_expression"]
        else:
            search_types = ["Call"]
            
        # Check current node
        if ast_node.get("type") in search_types:
            name = self._extract_call_name(ast_node, ast_format)
            if name:
                # Use line number for unique ID
                line = ast_node.get("start", {}).get("row", 0) if ast_format == "tree-sitter" else ast_node.get("lineno", 0)
                call_id = hashlib.md5(f"{file_id}:{name}:{line}".encode()).hexdigest()
                results.append({
                    "id": call_id,
                    "call_name": name,
                    "file_id": file_id,
                    "repository": repository,
                    "start_line": line
                })
        
        # Recurse through children
        for child in ast_node.get("children", []):
            if isinstance(child, dict):
                self._extract_call_sites(child, ast_format, file_id, repository, results)
    
    def _extract_name(self, node: Dict[str, Any], entity_type: str, ast_format: str) -> Optional[str]:
        """Extract name from a node based on AST format."""
        if ast_format == "tree-sitter":
            # For tree-sitter, find the identifier child
            # Skip certain node types that appear before the actual name
            skip_types = ["modifiers", "type_identifier", "void_type", "primitive_type", 
                         "generic_type", "array_type", "scoped_type_identifier"]
            
            for child in node.get("children", []):
                if child.get("type") in skip_types:
                    continue
                if child.get("type") == "identifier" and "text" in child:
                    return child["text"]
                    
            # If not found in direct children, do a deeper search
            # This handles cases where the identifier is nested
            return self._find_first_identifier(node)
        else:
            # For native Python AST
            return node.get("name")
        return None
    
    def _find_first_identifier(self, node: Dict[str, Any]) -> Optional[str]:
        """Recursively find the first identifier in a node."""
        if isinstance(node, dict):
            if node.get("type") == "identifier" and "text" in node:
                return node["text"]
            for child in node.get("children", []):
                result = self._find_first_identifier(child)
                if result:
                    return result
        return None
        
    def _extract_call_name(self, node: Dict[str, Any], ast_format: str) -> Optional[str]:
        """Extract the function name from a call node."""
        if ast_format == "tree-sitter":
            node_type = node.get("type", "")
            
            # For Java method_invocation nodes
            if node_type == "method_invocation":
                # Structure: object.method(args) or method(args)
                # Look for the identifier that is the method name
                for child in node.get("children", []):
                    if child.get("type") == "identifier" and "text" in child:
                        return child["text"]
                    elif child.get("type") == "field_access":
                        # For chained calls like obj.method()
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "identifier" and "text" in subchild:
                                return subchild["text"]
            
            # For Java object_creation_expression (new ClassName())
            elif node_type == "object_creation_expression":
                # Look for the type being instantiated
                for child in node.get("children", []):
                    if child.get("type") in ["type_identifier", "identifier"] and "text" in child:
                        return child["text"]
                    elif child.get("type") == "generic_type":
                        # Handle generic types like new ArrayList<String>()
                        for subchild in child.get("children", []):
                            if subchild.get("type") == "type_identifier" and "text" in subchild:
                                return subchild["text"]
            
            # For other languages (Python, JavaScript)
            else:
                for child in node.get("children", []):
                    if child.get("type") == "identifier" and "text" in child:
                        return child["text"]
                    elif child.get("type") in ["attribute", "member_expression"]:
                        # Handle method calls
                        for attr_child in child.get("children", []):
                            if attr_child.get("type") == "identifier" and "text" in attr_child:
                                return attr_child["text"]
        else:
            # For native Python AST
            func_node = node.get("func", {})
            if func_node.get("type") == "Name":
                return func_node.get("id")
            elif func_node.get("type") == "Attribute":
                return func_node.get("attr")
        return None
        
    def resolve_placeholders(self) -> Dict[str, int]:
        """Resolve CallSites to Functions using efficient batch query."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (cs:CallSite)
                WHERE NOT EXISTS((cs)-[:RESOLVES_TO]->())
                WITH cs
                MATCH (f:Function {name: cs.call_name})
                WHERE f.repository = cs.repository
                WITH cs, f, 
                     CASE WHEN f.file_id = cs.caller_file_id THEN 1.0 ELSE 0.7 END as score
                ORDER BY cs.id, score DESC
                WITH cs, collect({func: f, score: score})[0] as best_match
                WITH cs, best_match.func as target_func, best_match.score as match_score
                WHERE target_func IS NOT NULL
                MERGE (cs)-[r:RESOLVES_TO]->(target_func)
                SET r.score = match_score
                RETURN count(r) as resolved
            """)
            
            resolved = result.single()["resolved"]
            self.stats["resolved_calls"] = resolved
            
        return {
            "resolved_calls": resolved,
            "resolved_imports": 0
        }