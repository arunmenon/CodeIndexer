#!/usr/bin/env python
"""Update ADK imports in all Python files."""

import os
import re

# Define import replacements
replacements = [
    (
        r'from google\.adk\.api\.agent import Agent, AgentContext, HandlerResponse',
        'from google.adk import Agent\nfrom google.adk.tools.google_api_tool import AgentContext, HandlerResponse'
    ),
    (
        r'from google\.adk\.api\.agent import Agent, AgentContext',
        'from google.adk import Agent\nfrom google.adk.tools.google_api_tool import AgentContext'
    ),
    (
        r'from google\.adk\.api\.agent import AgentContext',
        'from google.adk.tools.google_api_tool import AgentContext'
    ),
    (
        r'from google\.adk\.api\.tool import ToolContext, ToolResponse, ToolStatus',
        'from google.adk.agents.llm_agent import ToolContext\nfrom google.adk.tools.google_api_tool import ToolResponse, ToolStatus'
    ),
    (
        r'from google\.adk\.api\.tool import ToolResponse, ToolStatus',
        'from google.adk.tools.google_api_tool import ToolResponse, ToolStatus'
    ),
    (
        r'from google\.adk\.api\.tool import ToolResponse',
        'from google.adk.tools.google_api_tool import ToolResponse'
    ),
    (
        r'from google\.adk\.tooling import BaseTool',
        'from google.adk.agents.llm_agent import BaseTool'
    ),
]

def update_file(file_path):
    """Update imports in a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Apply all replacements
    updated_content = content
    for old_import, new_import in replacements:
        updated_content = re.sub(old_import, new_import, updated_content)
    
    # Write back if changed
    if updated_content != content:
        with open(file_path, 'w') as f:
            f.write(updated_content)
        print(f"Updated: {file_path}")
        return True
    return False

def main():
    """Update imports in all Python files."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    code_dir = os.path.join(root_dir, 'code_indexer')
    
    files_updated = 0
    for root, _, files in os.walk(code_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if update_file(file_path):
                    files_updated += 1
    
    print(f"Total files updated: {files_updated}")

if __name__ == "__main__":
    main()