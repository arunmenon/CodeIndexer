"""
AST Utilities

Helper functions for working with Abstract Syntax Trees.
"""

import ast
import json
from typing import Dict, List, Any, Optional, Union


def ast_to_dict(node: ast.AST, source_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert a Python AST node to a dictionary representation.
    
    Args:
        node: The AST node to convert
        source_code: Optional source code for extracting text segments
        
    Returns:
        A dictionary representation of the AST node
    """
    if not isinstance(node, ast.AST):
        return node
    
    result = {
        "type": node.__class__.__name__,
    }
    
    # Add position information if available
    if hasattr(node, "lineno"):
        result["start_position"] = {
            "row": node.lineno,
            "column": node.col_offset if hasattr(node, "col_offset") else 0
        }
    
    if hasattr(node, "end_lineno"):
        result["end_position"] = {
            "row": node.end_lineno,
            "column": node.end_col_offset if hasattr(node, "end_col_offset") else 0
        }
    
    # Add source text if source code is provided and position info is available
    if (source_code and hasattr(node, "lineno") and hasattr(node, "end_lineno") 
            and hasattr(node, "col_offset") and hasattr(node, "end_col_offset")):
        lines = source_code.splitlines()
        if node.lineno - 1 < len(lines) and node.end_lineno - 1 < len(lines):
            if node.lineno == node.end_lineno:
                # Single line node
                line = lines[node.lineno - 1]
                result["text"] = line[node.col_offset:node.end_col_offset]
            else:
                # Multi-line node
                text_lines = []
                text_lines.append(lines[node.lineno - 1][node.col_offset:])
                text_lines.extend(lines[node.lineno:node.end_lineno - 1])
                text_lines.append(lines[node.end_lineno - 1][:node.end_col_offset])
                result["text"] = "\n".join(text_lines)
    
    # Process child nodes
    children = []
    for field_name, field_value in ast.iter_fields(node):
        if isinstance(field_value, (list, tuple)):
            # Handle lists of nodes (like body)
            for item in field_value:
                if isinstance(item, ast.AST):
                    children.append(ast_to_dict(item, source_code))
        elif isinstance(field_value, ast.AST):
            # Handle single child nodes
            children.append(ast_to_dict(field_value, source_code))
    
    if children:
        result["children"] = children
    
    return result


def find_entity_in_ast(ast_dict: Dict[str, Any], entity_type: str) -> List[Dict[str, Any]]:
    """
    Find all entities of a specific type in an AST.
    
    Args:
        ast_dict: Dictionary representation of an AST
        entity_type: Type of entity to find (e.g., "FunctionDef", "ClassDef")
        
    Returns:
        List of matching entities
    """
    results = []
    
    if ast_dict["type"] == entity_type:
        results.append(ast_dict)
    
    if "children" in ast_dict:
        for child in ast_dict["children"]:
            results.extend(find_entity_in_ast(child, entity_type))
    
    return results


def get_function_info(func_ast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract useful information about a function from its AST.
    
    Args:
        func_ast: Dictionary representation of a function AST
        
    Returns:
        Dictionary with function information
    """
    info = {
        "name": "",
        "params": [],
        "docstring": None,
        "start_line": func_ast.get("start_position", {}).get("row", 0),
        "end_line": func_ast.get("end_position", {}).get("row", 0),
    }
    
    # Handle both tree-sitter and native AST formats
    func_type = func_ast.get("type", "")
    
    if func_type == "function_definition":
        # Tree-sitter format
        for child in func_ast.get("children", []):
            child_type = child.get("type", "")
            if child_type == "identifier":
                info["name"] = child.get("text", "")
            elif child_type == "parameters":
                # Extract parameter names from parameters node
                info["params"] = _extract_ts_parameters(child)
        
        # Use start_point for line numbers in tree-sitter
        if "start_point" in func_ast:
            info["start_line"] = func_ast["start_point"]["row"] + 1  # Convert to 1-based
        if "end_point" in func_ast:
            info["end_line"] = func_ast["end_point"]["row"] + 1
            
    elif func_type == "FunctionDef":
        # Native Python AST format
        for child in func_ast.get("children", []):
            if child["type"] == "Name":
                info["name"] = child.get("text", "")
                break
        
        # Extract parameters
        for child in func_ast.get("children", []):
            if child["type"] == "arguments":
                for param_child in child.get("children", []):
                    if param_child["type"] == "arg":
                        info["params"].append(param_child.get("text", ""))
        
        # Extract docstring
        if "children" in func_ast:
            body_nodes = [c for c in func_ast["children"] if c["type"] == "body"]
            if body_nodes and "children" in body_nodes[0]:
                first_node = body_nodes[0]["children"][0] if body_nodes[0]["children"] else None
                if first_node and first_node["type"] == "Expr" and "children" in first_node:
                    str_nodes = [c for c in first_node["children"] if c["type"] == "Str"]
                    if str_nodes:
                        info["docstring"] = str_nodes[0].get("text", "")
    
    return info


def _extract_ts_parameters(params_node: Dict[str, Any]) -> List[str]:
    """Extract parameter names from tree-sitter parameters node."""
    params = []
    
    def find_identifiers(node):
        if isinstance(node, dict):
            if node.get("type") == "identifier":
                return [node.get("text", "")]
            elif "children" in node:
                result = []
                for child in node["children"]:
                    result.extend(find_identifiers(child))
                return result
        return []
    
    return find_identifiers(params_node)


def get_class_info(class_ast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract useful information about a class from its AST.
    
    Args:
        class_ast: Dictionary representation of a class AST
        
    Returns:
        Dictionary with class information
    """
    info = {
        "name": "",
        "bases": [],
        "methods": [],
        "docstring": None,
        "start_line": class_ast.get("start_position", {}).get("row", 0),
        "end_line": class_ast.get("end_position", {}).get("row", 0),
    }
    
    # Handle both tree-sitter and native AST formats
    class_type = class_ast.get("type", "")
    
    if class_type == "class_definition":
        # Tree-sitter format
        for child in class_ast.get("children", []):
            child_type = child.get("type", "")
            if child_type == "identifier":
                info["name"] = child.get("text", "")
            elif child_type == "argument_list":
                # Extract base classes from argument list
                info["bases"] = _extract_ts_identifiers(child)
        
        # Use start_point for line numbers in tree-sitter
        if "start_point" in class_ast:
            info["start_line"] = class_ast["start_point"]["row"] + 1
        if "end_point" in class_ast:
            info["end_line"] = class_ast["end_point"]["row"] + 1
            
        # Extract methods - use the enhanced find function
        from code_indexer.ingestion.direct.enhanced_graph_builder import find_entity_in_ast
        for method_ast in find_entity_in_ast(class_ast, "FunctionDef"):
            method_info = get_function_info(method_ast)
            info["methods"].append(method_info)
            
    elif class_type == "ClassDef":
        # Native Python AST format
        for child in class_ast.get("children", []):
            if child["type"] == "Name":
                info["name"] = child.get("text", "")
                break
        
        # Extract base classes
        for child in class_ast.get("children", []):
            if child["type"] == "bases":
                for base_child in child.get("children", []):
                    if base_child["type"] == "Name":
                        info["bases"].append(base_child.get("text", ""))
        
        # Extract docstring
        if "children" in class_ast:
            body_nodes = [c for c in class_ast["children"] if c["type"] == "body"]
            if body_nodes and "children" in body_nodes[0]:
                first_node = body_nodes[0]["children"][0] if body_nodes[0]["children"] else None
                if first_node and first_node["type"] == "Expr" and "children" in first_node:
                    str_nodes = [c for c in first_node["children"] if c["type"] == "Str"]
                    if str_nodes:
                        info["docstring"] = str_nodes[0].get("text", "")
        
        # Extract methods
        for method_ast in find_entity_in_ast(class_ast, "FunctionDef"):
            method_info = get_function_info(method_ast)
            info["methods"].append(method_info)
    
    return info


def _extract_ts_identifiers(node: Dict[str, Any]) -> List[str]:
    """Extract identifier names from tree-sitter node."""
    identifiers = []
    
    def find_identifiers(n):
        if isinstance(n, dict):
            if n.get("type") == "identifier":
                return [n.get("text", "")]
            elif "children" in n:
                result = []
                for child in n["children"]:
                    result.extend(find_identifiers(child))
                return result
        return []
    
    return find_identifiers(node)