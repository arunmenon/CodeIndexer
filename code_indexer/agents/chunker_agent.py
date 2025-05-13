"""
Chunker Agent

This agent divides code into meaningful chunks for embedding.
"""

import os
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple

from google.adk import Agent, AgentContext
from google.adk.agents.llm_agent import BaseTool

from code_indexer.tools.neo4j_tool import Neo4jTool


class ChunkerAgent(Agent):
    """
    Agent responsible for dividing code into semantic chunks for embedding.
    
    This agent takes code entities from the graph and divides them into 
    appropriately sized chunks that preserve semantic meaning for effective
    vector embeddings.
    """
    
    def __init__(self):
        """Initialize the Chunker Agent."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Default chunking configuration
        self.max_chunk_size = 1024  # Maximum token size for a chunk
        self.min_chunk_size = 64    # Minimum token size for a chunk
        self.overlap = 50           # Token overlap between adjacent chunks
    
    def initialize(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Initialize the Neo4j tool
        self.neo4j_tool = Neo4jTool()
        
        # Load chunking configuration if provided
        config = context.state.get("config", {}).get("chunking", {})
        if config:
            self.max_chunk_size = config.get("max_size", self.max_chunk_size)
            self.min_chunk_size = config.get("min_size", self.min_chunk_size)
            self.overlap = config.get("overlap", self.overlap)
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create meaningful code chunks for embedding.
        
        Args:
            inputs: Dictionary with file paths or entity IDs to chunk
            
        Returns:
            Dictionary with chunks and their metadata
        """
        # Extract inputs
        file_paths = inputs.get("file_paths", [])
        entity_ids = inputs.get("entity_ids", [])
        repo_path = inputs.get("repo_path", "")
        
        # Track results
        all_chunks = []
        
        # Process by file paths if provided
        if file_paths:
            for file_path in file_paths:
                file_chunks = self._chunk_file(file_path, repo_path)
                all_chunks.extend(file_chunks)
        
        # Process by entity IDs if provided
        if entity_ids:
            for entity_id in entity_ids:
                entity_chunks = self._chunk_entity(entity_id)
                all_chunks.extend(entity_chunks)
        
        # If neither provided, get recent files from graph
        if not file_paths and not entity_ids:
            recent_files = self._get_recent_files(limit=10)
            for file_info in recent_files:
                file_chunks = self._chunk_entity(file_info["id"])
                all_chunks.extend(file_chunks)
        
        self.logger.info(f"Created {len(all_chunks)} chunks from {len(file_paths)} files "
                        f"and {len(entity_ids)} entities")
        
        return {
            "chunks": all_chunks,
            "count": len(all_chunks)
        }
    
    def _chunk_file(self, file_path: str, repo_path: str) -> List[Dict[str, Any]]:
        """
        Chunk a file from the filesystem.
        
        Args:
            file_path: Path to the file
            repo_path: Base path of the repository
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                self.logger.warning(f"File not found: {file_path}")
                return []
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Get relative path if repo_path provided
            relative_path = file_path
            if repo_path and file_path.startswith(repo_path):
                relative_path = os.path.relpath(file_path, repo_path)
            
            # Determine language from file extension
            _, ext = os.path.splitext(file_path)
            language = self._detect_language_from_ext(ext)
            
            # Create file entity in graph if not exists
            file_id = self._ensure_file_node(relative_path, language)
            
            # Create chunks based on content structure
            if language in ['python', 'java', 'javascript']:
                # Use structure-aware chunking for known languages
                chunks = self._structure_aware_chunking(content, language, file_id, relative_path)
            else:
                # Fall back to sliding window for unknown languages
                chunks = self._sliding_window_chunking(content, file_id, relative_path, language)
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"Error chunking file {file_path}: {e}")
            return []
    
    def _chunk_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Chunk a code entity from the graph.
        
        Args:
            entity_id: ID of the entity (file, class, or function)
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        try:
            # Get entity type
            entity_type = self._get_entity_type(entity_id)
            
            if entity_type == "File":
                # Get file content and metadata
                file_info = self._get_file_content(entity_id)
                
                if file_info and "content" in file_info:
                    language = file_info.get("language", "unknown")
                    path = file_info.get("path", "")
                    
                    # Create chunks based on content structure
                    if language in ['python', 'java', 'javascript']:
                        chunks = self._structure_aware_chunking(
                            file_info["content"], language, entity_id, path
                        )
                    else:
                        chunks = self._sliding_window_chunking(
                            file_info["content"], entity_id, path, language
                        )
            
            elif entity_type == "Class":
                # Get class code and metadata
                class_info = self._get_class_info(entity_id)
                
                if class_info and "content" in class_info:
                    # Create one chunk for the class
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "entity_id": entity_id,
                        "entity_type": "Class",
                        "file_id": class_info.get("file_id", ""),
                        "language": class_info.get("language", "unknown"),
                        "file_path": class_info.get("file_path", ""),
                        "start_line": class_info.get("start_line", 0),
                        "end_line": class_info.get("end_line", 0),
                        "content": class_info["content"],
                        "content_type": "class"
                    })
            
            elif entity_type == "Function":
                # Get function code and metadata
                function_info = self._get_function_info(entity_id)
                
                if function_info and "content" in function_info:
                    # Create one chunk for the function
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "entity_id": entity_id,
                        "entity_type": "Function",
                        "file_id": function_info.get("file_id", ""),
                        "language": function_info.get("language", "unknown"),
                        "file_path": function_info.get("file_path", ""),
                        "start_line": function_info.get("start_line", 0),
                        "end_line": function_info.get("end_line", 0),
                        "content": function_info["content"],
                        "content_type": "function"
                    })
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"Error chunking entity {entity_id}: {e}")
            return []
    
    def _structure_aware_chunking(self, content: str, language: str, 
                                file_id: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Create chunks based on code structure (classes, functions, etc).
        
        Args:
            content: The code content
            language: Programming language
            file_id: ID of the file
            file_path: Path to the file
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Get functions and classes from the graph
        entities = self._get_file_entities(file_id)
        
        if not entities:
            # Fall back to sliding window if no entities found
            return self._sliding_window_chunking(content, file_id, file_path, language)
        
        lines = content.splitlines()
        
        # Process classes and functions
        for entity in entities:
            entity_type = entity.get("type")
            start_line = entity.get("start_line", 0)
            end_line = entity.get("end_line", 0)
            
            # Skip if invalid line numbers
            if start_line <= 0 or end_line <= 0 or start_line > len(lines) or end_line > len(lines):
                continue
            
            # Extract entity content
            entity_lines = lines[start_line-1:end_line]
            entity_content = "\n".join(entity_lines)
            
            # Create chunk for this entity
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "entity_id": entity.get("id", ""),
                "entity_type": entity_type,
                "file_id": file_id,
                "language": language,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "content": entity_content,
                "content_type": entity_type.lower()
            })
        
        # Add file header as a chunk (includes imports, global variables)
        if entities:
            min_start_line = min(e.get("start_line", float('inf')) for e in entities)
            if min_start_line > 1:
                header_content = "\n".join(lines[:min_start_line-1])
                if header_content.strip():  # Only add if not empty
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "entity_id": file_id,
                        "entity_type": "File",
                        "file_id": file_id,
                        "language": language,
                        "file_path": file_path,
                        "start_line": 1,
                        "end_line": min_start_line - 1,
                        "content": header_content,
                        "content_type": "header"
                    })
        
        return chunks
    
    def _sliding_window_chunking(self, content: str, file_id: str, 
                               file_path: str, language: str) -> List[Dict[str, Any]]:
        """
        Chunk content using a sliding window approach.
        
        Args:
            content: The code content
            file_id: ID of the file
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        lines = content.splitlines()
        
        # Simple approach: create chunks of roughly max_chunk_size tokens
        # with overlap
        chunk_start = 0
        
        while chunk_start < len(lines):
            # Estimate token count based on characters (rough approximation)
            token_count = 0
            chunk_end = chunk_start
            
            while chunk_end < len(lines) and token_count < self.max_chunk_size:
                # Roughly estimate tokens in line (words plus symbols)
                line = lines[chunk_end]
                line_tokens = len(line.split()) + line.count('(') + line.count(')') + \
                             line.count('.') + line.count(',') + line.count(';')
                token_count += max(1, line_tokens)
                chunk_end += 1
            
            # Ensure minimum chunk size
            if token_count < self.min_chunk_size and chunk_end < len(lines):
                continue
            
            # Extract chunk content
            chunk_content = "\n".join(lines[chunk_start:chunk_end])
            
            # Create chunk
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "entity_id": file_id,
                "entity_type": "File",
                "file_id": file_id,
                "language": language,
                "file_path": file_path,
                "start_line": chunk_start + 1,  # 1-based line numbers
                "end_line": chunk_end,
                "content": chunk_content,
                "content_type": "window"
            })
            
            # Move start position for next chunk, with overlap
            overlap_lines = int(self.overlap / 5)  # Approximate lines for desired token overlap
            chunk_start = max(chunk_start + 1, chunk_end - overlap_lines)
        
        return chunks
    
    def _get_entity_type(self, entity_id: str) -> str:
        """
        Get the type of an entity from the graph.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Entity type ("File", "Class", "Function", or "Unknown")
        """
        query = """
        MATCH (n {id: $entity_id})
        RETURN labels(n)[0] as type
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"entity_id": entity_id})
            if results:
                return results[0].get("type", "Unknown")
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def _get_file_content(self, file_id: str) -> Dict[str, Any]:
        """
        Get file content and metadata from the filesystem.
        
        Args:
            file_id: ID of the file
            
        Returns:
            Dictionary with file content and metadata
        """
        # First get file path from graph
        query = """
        MATCH (f:File {id: $file_id})
        RETURN f.path, f.language, f.repo_path
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"file_id": file_id})
            if not results:
                return {}
            
            file_info = results[0]
            file_path = file_info.get("f.path", "")
            language = file_info.get("f.language", "unknown")
            repo_path = file_info.get("f.repo_path", "")
            
            # Construct full path
            full_path = file_path
            if repo_path and not os.path.isabs(file_path):
                full_path = os.path.join(repo_path, file_path)
            
            # Read file content
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                return {
                    "content": content,
                    "path": file_path,
                    "language": language,
                    "repo_path": repo_path
                }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting file content for {file_id}: {e}")
            return {}
    
    def _get_class_info(self, class_id: str) -> Dict[str, Any]:
        """
        Get class content and metadata.
        
        Args:
            class_id: ID of the class
            
        Returns:
            Dictionary with class content and metadata
        """
        # Get class metadata from graph
        query = """
        MATCH (c:Class {id: $class_id})
        MATCH (f:File {id: c.file_id})
        RETURN c.name, c.start_line, c.end_line, c.docstring, c.file_id,
               f.path as file_path, f.language, f.repo_path
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"class_id": class_id})
            if not results:
                return {}
            
            class_info = results[0]
            file_id = class_info.get("c.file_id", "")
            start_line = class_info.get("c.start_line", 0)
            end_line = class_info.get("c.end_line", 0)
            file_path = class_info.get("file_path", "")
            language = class_info.get("f.language", "unknown")
            repo_path = class_info.get("f.repo_path", "")
            
            # Construct full path
            full_path = file_path
            if repo_path and not os.path.isabs(file_path):
                full_path = os.path.join(repo_path, file_path)
            
            # Read file and extract class content
            if os.path.exists(full_path) and start_line > 0 and end_line > 0:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                if start_line <= len(lines) and end_line <= len(lines):
                    class_content = "".join(lines[start_line-1:end_line])
                    
                    return {
                        "content": class_content,
                        "name": class_info.get("c.name", ""),
                        "docstring": class_info.get("c.docstring", ""),
                        "file_id": file_id,
                        "file_path": file_path,
                        "language": language,
                        "start_line": start_line,
                        "end_line": end_line
                    }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting class info for {class_id}: {e}")
            return {}
    
    def _get_function_info(self, function_id: str) -> Dict[str, Any]:
        """
        Get function content and metadata.
        
        Args:
            function_id: ID of the function
            
        Returns:
            Dictionary with function content and metadata
        """
        # Get function metadata from graph
        query = """
        MATCH (func:Function {id: $function_id})
        MATCH (f:File {id: func.file_id})
        OPTIONAL MATCH (c:Class {id: func.class_id})
        RETURN func.name, func.start_line, func.end_line, func.docstring, 
               func.params, func.file_id, func.class_id, func.is_method,
               f.path as file_path, f.language, f.repo_path,
               c.name as class_name
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"function_id": function_id})
            if not results:
                return {}
            
            func_info = results[0]
            file_id = func_info.get("func.file_id", "")
            start_line = func_info.get("func.start_line", 0)
            end_line = func_info.get("func.end_line", 0)
            file_path = func_info.get("file_path", "")
            language = func_info.get("f.language", "unknown")
            repo_path = func_info.get("f.repo_path", "")
            
            # Construct full path
            full_path = file_path
            if repo_path and not os.path.isabs(file_path):
                full_path = os.path.join(repo_path, file_path)
            
            # Read file and extract function content
            if os.path.exists(full_path) and start_line > 0 and end_line > 0:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                if start_line <= len(lines) and end_line <= len(lines):
                    func_content = "".join(lines[start_line-1:end_line])
                    
                    return {
                        "content": func_content,
                        "name": func_info.get("func.name", ""),
                        "docstring": func_info.get("func.docstring", ""),
                        "params": func_info.get("func.params", []),
                        "file_id": file_id,
                        "file_path": file_path,
                        "language": language,
                        "start_line": start_line,
                        "end_line": end_line,
                        "class_id": func_info.get("func.class_id", ""),
                        "class_name": func_info.get("class_name", ""),
                        "is_method": func_info.get("func.is_method", False)
                    }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting function info for {function_id}: {e}")
            return {}
    
    def _get_file_entities(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Get classes and functions in a file.
        
        Args:
            file_id: ID of the file
            
        Returns:
            List of entity metadata
        """
        query = """
        MATCH (f:File {id: $file_id})
        MATCH (f)-[:CONTAINS]->(entity)
        WHERE entity:Class OR entity:Function
        RETURN entity.id as id, labels(entity)[0] as type, 
               entity.name as name, entity.start_line as start_line, 
               entity.end_line as end_line
        ORDER BY entity.start_line
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"file_id": file_id})
            return results
        except Exception:
            return []
    
    def _get_recent_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recently updated files from the graph.
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of file metadata
        """
        query = f"""
        MATCH (f:File)
        RETURN f.id as id, f.path as path, f.language as language
        ORDER BY f.last_updated DESC
        LIMIT {limit}
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query)
            return results
        except Exception:
            return []
    
    def _ensure_file_node(self, file_path: str, language: str) -> str:
        """
        Ensure a file node exists in the graph.
        
        Args:
            file_path: Path to the file
            language: Programming language
            
        Returns:
            ID of the file node
        """
        # Generate file ID
        import hashlib
        file_id = hashlib.md5(file_path.encode()).hexdigest()
        
        # Create file node
        self.neo4j_tool.create_file_node(
            file_id=file_id,
            path=file_path,
            language=language
        )
        
        return file_id
    
    def _detect_language_from_ext(self, ext: str) -> str:
        """
        Detect language from file extension.
        
        Args:
            ext: File extension (including dot)
            
        Returns:
            Language string
        """
        ext_map = {
            ".py": "python",
            ".java": "java",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".rs": "rust"
        }
        
        return ext_map.get(ext.lower(), "unknown")