"""
Repository Utilities

Helper functions for working with code repositories.
"""

import os
import hashlib
from typing import Dict, List, Any, Optional


def get_file_hash(file_path: str) -> str:
    """
    Get a hash of a file's contents.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 hash of the file contents
    """
    if not os.path.exists(file_path):
        return ""
    
    hasher = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            buf = f.read(65536)  # Read in 64kb chunks
            while buf:
                hasher.update(buf)
                buf = f.read(65536)
        
        return hasher.hexdigest()
    except Exception:
        return ""


def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is likely binary.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file appears to be binary, False otherwise
    """
    if not os.path.exists(file_path):
        return False
    
    # Check file extension first
    binary_extensions = {
        '.pyc', '.pyo', '.so', '.dll', '.obj', '.exe', '.bin',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.tar', '.gz', '.tgz', '.jar', '.war', '.ear',
        '.class', '.o'
    }
    
    if os.path.splitext(file_path)[1].lower() in binary_extensions:
        return True
    
    # Read the start of the file to check for binary content
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            
        # Check for null bytes and high proportion of non-ASCII
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)))
        return bool(chunk.translate(None, text_chars))
    except Exception:
        # If we can't read the file, assume it's not binary
        return False


def count_lines_of_code(file_path: str) -> Dict[str, int]:
    """
    Count lines of code, comments, and blanks in a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with counts for 'code', 'comment', and 'blank' lines
    """
    if not os.path.exists(file_path) or is_binary_file(file_path):
        return {'code': 0, 'comment': 0, 'blank': 0, 'total': 0}
    
    counts = {'code': 0, 'comment': 0, 'blank': 0, 'total': 0}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Determine comment markers based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        
        line_comment_markers = {
            '.py': '#',
            '.java': '//',
            '.js': '//',
            '.jsx': '//',
            '.ts': '//',
            '.tsx': '//',
            '.c': '//',
            '.cpp': '//',
            '.h': '//',
            '.hpp': '//',
            '.cs': '//',
            '.php': '//',
            '.rb': '#',
            '.pl': '#',
            '.sh': '#',
            '.bash': '#',
            '.go': '//',
            '.swift': '//',
            '.kt': '//',
            '.rs': '//'
        }
        
        block_comment_start = {
            '.py': '"""',
            '.java': '/*',
            '.js': '/*',
            '.jsx': '/*',
            '.ts': '/*',
            '.tsx': '/*',
            '.c': '/*',
            '.cpp': '/*',
            '.h': '/*',
            '.hpp': '/*',
            '.cs': '/*',
            '.php': '/*',
            '.rb': '=begin',
            '.go': '/*',
            '.swift': '/*',
            '.kt': '/*',
            '.rs': '/*'
        }
        
        block_comment_end = {
            '.py': '"""',
            '.java': '*/',
            '.js': '*/',
            '.jsx': '*/',
            '.ts': '*/',
            '.tsx': '*/',
            '.c': '*/',
            '.cpp': '*/',
            '.h': '*/',
            '.hpp': '*/',
            '.cs': '*/',
            '.php': '*/',
            '.rb': '=end',
            '.go': '*/',
            '.swift': '*/',
            '.kt': '*/',
            '.rs': '*/'
        }
        
        # Default to Python-like comments if extension not recognized
        line_comment = line_comment_markers.get(ext, '#')
        block_start = block_comment_start.get(ext, '"""')
        block_end = block_comment_end.get(ext, '"""')
        
        in_block_comment = False
        
        for line in lines:
            line = line.strip()
            counts['total'] += 1
            
            if not line:
                counts['blank'] += 1
            elif in_block_comment:
                counts['comment'] += 1
                if block_end in line:
                    in_block_comment = False
            elif line.startswith(line_comment):
                counts['comment'] += 1
            elif block_start in line:
                counts['comment'] += 1
                if block_end not in line:
                    in_block_comment = True
                else:
                    in_block_comment = False
            else:
                counts['code'] += 1
        
        return counts
    except Exception:
        return {'code': 0, 'comment': 0, 'blank': 0, 'total': 0}