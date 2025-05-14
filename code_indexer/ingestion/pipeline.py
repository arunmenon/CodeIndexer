"""
CodeIndexer Ingestion Pipeline

This module contains the main pipeline orchestration logic for the ingestion process.
"""

import os
import logging
import json
import tempfile
from typing import Dict, Any, List, Optional

# Import pipeline stages
from code_indexer.ingestion.stages.git import process_git_repository
from code_indexer.ingestion.stages.parse import process_code_parsing
from code_indexer.ingestion.stages.graph import process_graph_building
from code_indexer.ingestion.stages.chunk import process_code_chunking
from code_indexer.ingestion.stages.embed import process_embedding
from code_indexer.ingestion.stages.dead_code import detect_dead_code

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingestion_pipeline")


def run_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the complete ingestion pipeline.
    
    Args:
        config: Pipeline configuration dictionary
        
    Returns:
        Dictionary with processing results
    """
    # Extract configuration values
    repository_url = config.get("repository_url")
    branch = config.get("branch", "main")
    output_dir = config.get("output_dir")
    mode = config.get("mode", "incremental")
    force_reindex = config.get("force_reindex", False)
    step = config.get("step", "all")
    detect_dead_code_flag = config.get("detect_dead_code", False)
    
    # Neo4j configuration
    neo4j_config = {
        "uri": config.get("neo4j_uri", "bolt://localhost:7687"),
        "user": config.get("neo4j_user", "neo4j"),
        "password": config.get("neo4j_password", "password")
    }
    
    # Vector store configuration
    vector_store_config = {
        "type": config.get("vector_store", "milvus"),
        "uri": config.get("vector_store_uri", "localhost:19530")
    }
    
    # Create temporary directory if output_dir not specified
    if not output_dir:
        output_dir = tempfile.mkdtemp(prefix="codeindexer_")
        logger.info(f"Created temporary directory for outputs: {output_dir}")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # Setup file paths for intermediate results
    git_output = os.path.join(output_dir, "git_output.json")
    parser_output = os.path.join(output_dir, "parser_output.json")
    graph_output = os.path.join(output_dir, "graph_output.json")
    chunk_output = os.path.join(output_dir, "chunk_output.json")
    embed_output = os.path.join(output_dir, "embed_output.json")
    
    # Initialize result tracking
    result = {
        "status": "success",
        "files_processed": 0,
        "stage_stats": {},
        "output_dir": output_dir
    }
    
    # Run through pipeline stages based on 'step' parameter
    try:
        # Stage 1: Git repository processing
        if step in ["git", "all"]:
            logger.info("STAGE 1: Git repository processing")
            git_result = process_git_repository(
                repository_url=repository_url,
                branch=branch,
                mode=mode,
                force_reindex=force_reindex,
                output_file=git_output
            )
            
            result["stage_stats"]["git"] = {
                "files_detected": git_result.get("files_detected", 0),
                "files_processed": git_result.get("files_processed", 0)
            }
            
            result["files_processed"] = git_result.get("files_processed", 0)
            
            if git_result.get("status") != "success":
                return {
                    "status": "error",
                    "stage": "git",
                    "message": git_result.get("message", "Git processing failed")
                }
        
        # Stage 2: Code parsing
        if step in ["parse", "all"] and (step != "parse" or os.path.exists(git_output)):
            logger.info("STAGE 2: Code parsing")
            parser_result = process_code_parsing(
                input_file=git_output if step == "all" else config.get("input_file", git_output),
                output_file=parser_output
            )
            
            result["stage_stats"]["parse"] = {
                "files_parsed": parser_result.get("files_parsed", 0),
                "files_failed": parser_result.get("files_failed", 0)
            }
            
            if parser_result.get("status") != "success":
                return {
                    "status": "error",
                    "stage": "parse",
                    "message": parser_result.get("message", "Code parsing failed")
                }
        
        # Stage 3: Graph building
        if step in ["graph", "all"] and (step != "graph" or os.path.exists(parser_output)):
            logger.info("STAGE 3: Graph building")
            graph_result = process_graph_building(
                input_file=parser_output if step == "all" else config.get("input_file", parser_output),
                output_file=graph_output,
                neo4j_config=neo4j_config
            )
            
            result["stage_stats"]["graph"] = {
                "files_processed": graph_result.get("files_processed", 0),
                "entities_created": graph_result.get("entities_created", 0),
                "relationships_created": graph_result.get("relationships_created", 0)
            }
            
            if graph_result.get("status") != "success":
                return {
                    "status": "error",
                    "stage": "graph",
                    "message": graph_result.get("message", "Graph building failed")
                }
            
            # Optional: Dead code detection
            if detect_dead_code_flag:
                logger.info("Running dead code detection")
                dead_code_result = detect_dead_code(
                    neo4j_config=neo4j_config,
                    repository=graph_result.get("repository", "")
                )
                
                result["stage_stats"]["dead_code"] = {
                    "dead_functions_detected": dead_code_result.get("dead_functions", 0),
                    "dead_classes_detected": dead_code_result.get("dead_classes", 0)
                }
        
        # Stage 4: Code chunking
        if step in ["chunk", "all"] and (step != "chunk" or os.path.exists(graph_output)):
            logger.info("STAGE 4: Code chunking")
            chunk_result = process_code_chunking(
                input_file=graph_output if step == "all" else config.get("input_file", graph_output),
                output_file=chunk_output,
                neo4j_config=neo4j_config
            )
            
            result["stage_stats"]["chunk"] = {
                "chunks_created": chunk_result.get("chunks_created", 0),
                "files_processed": chunk_result.get("files_processed", 0)
            }
            
            if chunk_result.get("status") != "success":
                return {
                    "status": "error",
                    "stage": "chunk",
                    "message": chunk_result.get("message", "Code chunking failed")
                }
        
        # Stage 5: Embedding generation
        if step in ["embed", "all"] and (step != "embed" or os.path.exists(chunk_output)):
            logger.info("STAGE 5: Embedding generation")
            embed_result = process_embedding(
                input_file=chunk_output if step == "all" else config.get("input_file", chunk_output),
                output_file=embed_output,
                vector_store_config=vector_store_config
            )
            
            result["stage_stats"]["embed"] = {
                "embeddings_created": embed_result.get("embeddings_created", 0),
                "chunks_processed": embed_result.get("chunks_processed", 0)
            }
            
            if embed_result.get("status") != "success":
                return {
                    "status": "error",
                    "stage": "embed",
                    "message": embed_result.get("message", "Embedding generation failed")
                }
        
        return result
    
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "error",
            "stage": "pipeline",
            "message": str(e)
        }