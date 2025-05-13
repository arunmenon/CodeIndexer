# Running the End-to-End Tests

This document explains how to run the end-to-end tests for the CodeIndexer project.

## Prerequisites

The CodeIndexer project uses Google's Agent Development Kit (ADK). There is a version compatibility issue that needs to be addressed before running the tests.

### Issues Identified

The current codebase imports from:
- `google.adk.api.agent` for `Agent`, `AgentContext`, `HandlerResponse`
- `google.adk.api.tool` for `ToolResponse`, `ToolStatus`

However, the latest google-adk package (v0.5.0) has a different structure without the `api` submodule.

## Option 1: Install the Compatible ADK Version

The simplest solution is to install the specific version of google-adk that matches our code structure:

```bash
# Create a virtual environment (recommended)
python -m venv codeindexer_venv
source codeindexer_venv/bin/activate

# Install the compatible version of google-adk
# Note: You may need to try different versions until you find one with the api.agent module
pip install google-adk==0.4.0  # Try this version first

# Install other dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt
```

## Option 2: Modify Import Statements

If you want to use the latest version of google-adk, you'll need to update the import statements in multiple files:

1. Locate all import statements using:
```bash
grep -r "from google.adk.api" --include="*.py" ./code_indexer/
```

2. Update each file to use the new structure:
   - Change `from google.adk.api.agent import ...` to `from google.adk import ...`
   - Change `from google.adk.api.tool import ...` to `from google.adk.tools import ...` (verify correct location)

## Running the Tests

Once the dependency issues are resolved:

```bash
# Activate the virtual environment
source codeindexer_venv/bin/activate

# Run the end-to-end test
pytest tests/integration/test_end_to_end_pipeline.py::test_end_to_end_pipeline -v

# Run all integration tests
pytest -m integration -v

# Run a specific test
pytest tests/integration/test_search_pipeline.py -v
```

## Expected Test Flow

The end-to-end test:

1. Creates a mock environment with sample repositories
2. Initializes the Git ingestion agent, code parser, graph builder, and other components
3. Processes a sample repository through the entire pipeline
4. Executes search queries on the indexed code
5. Runs the dead code detector to find unused functions and classes
6. Verifies that each step returns the expected results

## Troubleshooting

If you encounter import errors:
- Double-check that you're using the correct version of google-adk
- Verify that all required dependencies are installed
- Check if any other import paths need to be updated

If you encounter test failures:
- The mock data might not match what the code expects
- Some components might need to be initialized differently
- The test might be expecting different response formats

## Running with Docker

You can also run the tests in a Docker container to ensure a clean environment:

```bash
# Build the Docker image
docker build -t code-indexer-tests -f Dockerfile.tests .

# Run the tests
docker run code-indexer-tests pytest -m integration -v
```

Note: You may need to create a separate Dockerfile.tests that installs the correct version of dependencies.