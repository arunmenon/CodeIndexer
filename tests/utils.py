"""
Test utilities for Code Indexer tests.

This module contains utility functions for testing.
"""

import os
import json
import tempfile
import numpy as np
from typing import Dict, Any, List, Optional, Union


def create_temp_file(content: str, extension: str = '.py') -> str:
    """
    Create a temporary file with the given content.
    
    Args:
        content: File content
        extension: File extension
        
    Returns:
        Path to the temporary file
    """
    fd, path = tempfile.mkstemp(suffix=extension)
    os.write(fd, content.encode('utf-8'))
    os.close(fd)
    return path


def create_sample_code_file(file_path: str, language: str = 'python') -> str:
    """
    Create a sample code file for testing.
    
    Args:
        file_path: Path to create the file
        language: Programming language
        
    Returns:
        Created file path
    """
    if language == 'python':
        content = """
def sample_function(a, b):
    \"\"\"
    A sample function that adds two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    \"\"\"
    return a + b


class SampleClass:
    \"\"\"A sample class for testing.\"\"\"
    
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        \"\"\"Get the stored value.\"\"\"
        return self.value
    
    def set_value(self, value):
        \"\"\"Set a new value.\"\"\"
        self.value = value
"""
    elif language == 'javascript':
        content = """
/**
 * A sample function that adds two numbers.
 * @param {number} a - First number
 * @param {number} b - Second number
 * @returns {number} Sum of a and b
 */
function sampleFunction(a, b) {
    return a + b;
}

/**
 * A sample class for testing.
 */
class SampleClass {
    /**
     * Create a sample object.
     * @param {any} value - The value to store
     */
    constructor(value) {
        this.value = value;
    }
    
    /**
     * Get the stored value.
     * @returns {any} The stored value
     */
    getValue() {
        return this.value;
    }
    
    /**
     * Set a new value.
     * @param {any} value - The new value to store
     */
    setValue(value) {
        this.value = value;
    }
}
"""
    else:
        # Generic code for other languages
        content = f"// Sample code for {language} testing"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Write the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    return file_path


def create_sample_repo(base_path: str) -> Dict[str, str]:
    """
    Create a sample repository structure for testing.
    
    Args:
        base_path: Base directory for the repository
        
    Returns:
        Dictionary mapping file names to file paths
    """
    # Create base directory
    os.makedirs(base_path, exist_ok=True)
    
    # Create directory structure
    os.makedirs(os.path.join(base_path, 'src'), exist_ok=True)
    os.makedirs(os.path.join(base_path, 'tests'), exist_ok=True)
    os.makedirs(os.path.join(base_path, 'docs'), exist_ok=True)
    
    # Create sample files
    files = {}
    
    # Python files
    files['calculator.py'] = create_sample_code_file(
        os.path.join(base_path, 'src', 'calculator.py'), 'python')
    files['utils.py'] = create_sample_code_file(
        os.path.join(base_path, 'src', 'utils.py'), 'python')
    files['test_calculator.py'] = create_sample_code_file(
        os.path.join(base_path, 'tests', 'test_calculator.py'), 'python')
    
    # JavaScript files
    files['ui.js'] = create_sample_code_file(
        os.path.join(base_path, 'src', 'ui.js'), 'javascript')
    
    # README
    readme_content = """
# Sample Repository

This is a sample repository for testing the Code Indexer.

## Features

- Calculator functionality
- Utility functions
- Web UI
"""
    readme_path = os.path.join(base_path, 'README.md')
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    files['README.md'] = readme_path
    
    return files


def generate_sample_embeddings(count: int, dimension: int = 64) -> List[np.ndarray]:
    """
    Generate sample embeddings for testing.
    
    Args:
        count: Number of embeddings to generate
        dimension: Embedding dimension
        
    Returns:
        List of embedding vectors
    """
    # Use a fixed seed for deterministic results
    np.random.seed(42)
    return [np.random.rand(dimension).astype(np.float32) for _ in range(count)]


def generate_sample_metadata(count: int, 
                           languages: Optional[List[str]] = None,
                           entity_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Generate sample metadata for testing.
    
    Args:
        count: Number of metadata entries to generate
        languages: List of languages to use
        entity_types: List of entity types to use
        
    Returns:
        List of metadata dictionaries
    """
    if not languages:
        languages = ['python', 'javascript', 'java', 'go', 'rust']
    
    if not entity_types:
        entity_types = ['function', 'class', 'method', 'module']
    
    metadata_list = []
    
    for i in range(count):
        language = languages[i % len(languages)]
        entity_type = entity_types[i % len(entity_types)]
        
        metadata = {
            "file_path": f"/src/sample_{i}.{language}",
            "language": language,
            "entity_type": entity_type,
            "entity_id": f"sample_entity_{i}",
            "start_line": i * 10,
            "end_line": i * 10 + 9,
            "chunk_id": f"chunk_{i}",
            "repository": "sample_repo",
            "branch": "main",
            "commit_id": "abc123"
        }
        
        metadata_list.append(metadata)
    
    return metadata_list