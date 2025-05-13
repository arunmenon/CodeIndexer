"""
Code Chunking Tool

This tool divides code into semantic chunks for embedding.
"""

import os
import re
from typing import Dict, List, Any, Optional, Tuple

from google.adk.agents.llm_agent import BaseTool

class CodeChunkingTool(BaseTool):
    """Tool for dividing code into semantic chunks for embedding."""
    
    def __init__(self, name: str = "code_chunking_tool"):
        """Initialize the Code Chunking Tool."""
        super().__init__(name=name)
        
        # Default chunking configuration
        self.max_chunk_size = 1024  # Maximum token size for a chunk
        self.min_chunk_size = 64    # Minimum token size for a chunk
        self.overlap = 50           # Token overlap between adjacent chunks
    
    def split_into_functions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """
        Split code content into function-level chunks.
        
        Args:
            content: The code content to split
            language: Programming language of the code
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Simple regex-based function detection
        if language == "python":
            # Match Python function definitions
            pattern = r"(def\s+\w+\s*\([^)]*\)\s*(?:->\s*\w+\s*)?:.*?)(?=\n\s*def\s+|\n\s*class\s+|\Z)"
            matches = re.finditer(pattern, content, re.DOTALL)
            
            for match in matches:
                function_code = match.group(1)
                
                # Extract function name
                name_match = re.search(r"def\s+(\w+)", function_code)
                if name_match:
                    function_name = name_match.group(1)
                else:
                    function_name = "unknown_function"
                
                # Get start and end line numbers
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + function_code.count('\n')
                
                chunks.append({
                    "content": function_code,
                    "entity_type": "function",
                    "entity_id": function_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language
                })
                
        elif language in ["javascript", "typescript"]:
            # Match JS/TS function definitions (simplified)
            pattern = r"((?:function\s+\w+|const\s+\w+\s*=\s*function|\w+\s*=\s*function|\w+\s*:\s*function)\s*\([^)]*\)\s*{.*?})(?=\s*(?:function|const|let|var|class)|\Z)"
            matches = re.finditer(pattern, content, re.DOTALL)
            
            for match in matches:
                function_code = match.group(1)
                
                # Extract function name
                name_match = re.search(r"(?:function\s+(\w+)|const\s+(\w+)|let\s+(\w+)|var\s+(\w+)|\s*(\w+)\s*:)", function_code)
                if name_match:
                    # Get the first non-None group
                    function_name = next((g for g in name_match.groups() if g), "anonymous")
                else:
                    function_name = "anonymous"
                
                # Get start and end line numbers
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + function_code.count('\n')
                
                chunks.append({
                    "content": function_code,
                    "entity_type": "function",
                    "entity_id": function_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language
                })
        
        # If no functions found or language not supported, fall back to sliding window
        if not chunks:
            chunks = self.split_with_sliding_window(content, language)
        
        return chunks
    
    def split_into_classes(self, content: str, language: str) -> List[Dict[str, Any]]:
        """
        Split code content into class-level chunks.
        
        Args:
            content: The code content to split
            language: Programming language of the code
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Simple regex-based class detection
        if language == "python":
            # Match Python class definitions
            pattern = r"(class\s+\w+(?:\s*\([^)]*\))?\s*:.*?)(?=\n\s*class\s+|\Z)"
            matches = re.finditer(pattern, content, re.DOTALL)
            
            for match in matches:
                class_code = match.group(1)
                
                # Extract class name
                name_match = re.search(r"class\s+(\w+)", class_code)
                if name_match:
                    class_name = name_match.group(1)
                else:
                    class_name = "unknown_class"
                
                # Get start and end line numbers
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + class_code.count('\n')
                
                chunks.append({
                    "content": class_code,
                    "entity_type": "class",
                    "entity_id": class_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language
                })
                
        elif language in ["javascript", "typescript"]:
            # Match JS/TS class definitions
            pattern = r"(class\s+\w+(?:\s+extends\s+\w+)?\s*{.*?})(?=\s*class|\Z)"
            matches = re.finditer(pattern, content, re.DOTALL)
            
            for match in matches:
                class_code = match.group(1)
                
                # Extract class name
                name_match = re.search(r"class\s+(\w+)", class_code)
                if name_match:
                    class_name = name_match.group(1)
                else:
                    class_name = "unknown_class"
                
                # Get start and end line numbers
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = start_line + class_code.count('\n')
                
                chunks.append({
                    "content": class_code,
                    "entity_type": "class",
                    "entity_id": class_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language
                })
        
        return chunks
    
    def split_with_sliding_window(self, content: str, language: str) -> List[Dict[str, Any]]:
        """
        Split code content using a sliding window approach.
        
        Args:
            content: The code content to split
            language: Programming language of the code
            
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
                chunk_end = min(chunk_start + 10, len(lines))  # At least 10 lines
            
            # Extract chunk content
            chunk_content = "\n".join(lines[chunk_start:chunk_end])
            
            chunks.append({
                "content": chunk_content,
                "entity_type": "code_segment",
                "entity_id": f"segment_{chunk_start}_{chunk_end}",
                "start_line": chunk_start + 1,  # 1-based line numbers
                "end_line": chunk_end,
                "language": language
            })
            
            # Move start position for next chunk, with overlap
            overlap_lines = max(1, int(self.overlap / 5))  # Approximate lines for desired token overlap
            chunk_start = max(chunk_start + 1, chunk_end - overlap_lines)
        
        return chunks
    
    def chunk_code_file(self, file_path: str, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Chunk a code file into semantic parts.
        
        Args:
            file_path: Path to the code file
            language: Programming language (if None, inferred from file extension)
            
        Returns:
            List of chunks with metadata
        """
        # Check if file exists
        if not os.path.isfile(file_path):
            return []
        
        # Infer language from file extension if not provided
        if language is None:
            _, ext = os.path.splitext(file_path)
            language = self._detect_language_from_ext(ext.lower())
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []
        
        # Get file name for metadata
        file_name = os.path.basename(file_path)
        
        # Split into chunks based on language
        all_chunks = []
        
        # Get class chunks
        class_chunks = self.split_into_classes(content, language)
        for chunk in class_chunks:
            chunk["file_path"] = file_path
            chunk["file_name"] = file_name
        
        # Get function chunks
        function_chunks = self.split_into_functions(content, language)
        for chunk in function_chunks:
            chunk["file_path"] = file_path
            chunk["file_name"] = file_name
        
        # Combine and sort by line number
        all_chunks = class_chunks + function_chunks
        all_chunks.sort(key=lambda x: x["start_line"])
        
        return all_chunks
    
    def _detect_language_from_ext(self, ext: str) -> str:
        """
        Detect language from file extension.
        
        Args:
            ext: File extension
            
        Returns:
            Language string
        """
        ext_map = {
            ".py": "python",
            ".pyc": "python",
            ".pyw": "python",
            ".ipynb": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".rs": "rust",
        }
        
        return ext_map.get(ext, "unknown")