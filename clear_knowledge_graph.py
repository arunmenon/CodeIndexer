#!/usr/bin/env python3
"""
Clear Neo4j Knowledge Graph

This script provides a simple way to completely clear the Neo4j database used by CodeIndexer.
It can be used to reset the database before running new indexing jobs.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j package not found. Please install it with:")
    print("pip install neo4j")
    sys.exit(1)

def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        CLEAR NEO4J KNOWLEDGE GRAPH                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This tool completely clears the Neo4j database used by CodeIndexer.
Use with caution - this operation cannot be undone!
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Neo4j connection options
    neo4j = parser.add_argument_group('🔌 Neo4j Connection')
    neo4j.add_argument('--uri', default=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'), 
                     help='Neo4j URI (default: from env var NEO4J_URI or bolt://localhost:7687)')
    neo4j.add_argument('--user', default=os.environ.get('NEO4J_USER', 'neo4j'), 
                     help='Neo4j username (default: from env var NEO4J_USER or neo4j)')
    neo4j.add_argument('--password', default=os.environ.get('NEO4J_PASSWORD', 'password'), 
                     help='Neo4j password (default: from env var NEO4J_PASSWORD or password)')
    neo4j.add_argument('--database', default=None, 
                     help='Neo4j database name (default: None, uses the default database)')
    
    # Selective clearing options
    operation = parser.add_argument_group('🔄 Operation')
    operation.add_argument('--repository', 
                         help='Clear only data for a specific repository (by name)')
    operation.add_argument('--force', action='store_true',
                         help='Skip confirmation prompt (use with caution)')
    operation.add_argument('--preserve-schema', action='store_true',
                         help='Preserve database schema (constraints and indexes)')
    operation.add_argument('--verbose', action='store_true',
                         help='Enable verbose logging')
                         
    return parser.parse_args()

def clear_database(uri: str, user: str, password: str, 
                   database: Optional[str] = None,
                   repository: Optional[str] = None,
                   preserve_schema: bool = False) -> Dict[str, Any]:
    """
    Clear the Neo4j database.
    
    Args:
        uri: Neo4j URI
        user: Neo4j username
        password: Neo4j password
        database: Neo4j database name (optional)
        repository: Repository name to clear (optional, if None clear everything)
        preserve_schema: Whether to preserve database schema
        
    Returns:
        Dictionary with deletion statistics
    """
    logging.info(f"Connecting to Neo4j at {uri}")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Test the connection
        with driver.session(database=database) as session:
            result = session.run("MATCH () RETURN count(*) as count")
            count = result.single()["count"]
            logging.info(f"Connected to Neo4j database with {count} nodes")
        
        # Prepare the deletion query
        if repository:
            logging.info(f"Clearing data for repository: {repository}")
            
            # Repository-specific deletion
            if preserve_schema:
                query = """
                // Get all nodes for the specific repository
                MATCH (n)
                WHERE n.repository = $repository OR (n:File AND n.repository = $repository)
                // Get connected nodes to delete in a single pass
                OPTIONAL MATCH (n)-[r]-(m)
                WHERE NOT (m:File AND m.repository <> $repository)
                // Delete relationships first, then nodes
                WITH n, r, m
                DETACH DELETE n, m
                RETURN count(*) as deleted_count
                """
            else:
                query = """
                // Get all nodes for the specific repository
                MATCH (n)
                WHERE n.repository = $repository OR (n:File AND n.repository = $repository)
                // Get connected nodes to delete in a single pass
                OPTIONAL MATCH (n)-[r]-(m)
                WHERE NOT (m:File AND m.repository <> $repository)
                // Delete relationships first, then nodes
                WITH n, r, m
                DETACH DELETE n, m
                RETURN count(*) as deleted_count
                """
            
            params = {"repository": repository}
        else:
            logging.info("Clearing all data from the database")
            
            # Full database deletion
            if preserve_schema:
                # Delete all nodes and relationships but preserve schema
                query = """
                MATCH (n)
                DETACH DELETE n
                RETURN count(*) as deleted_count
                """
            else:
                # Delete everything including schema
                # First get all constraints and indexes to drop them manually
                # This approach works without APOC
                with driver.session(database=database) as schema_session:
                    # Drop constraints
                    constraints_query = "SHOW CONSTRAINTS"
                    try:
                        constraints = list(schema_session.run(constraints_query))
                        for constraint in constraints:
                            name = constraint.get('name')
                            if name:
                                logging.info(f"Dropping constraint: {name}")
                                drop_query = f"DROP CONSTRAINT {name}"
                                schema_session.run(drop_query)
                    except Exception as e:
                        logging.warning(f"Error dropping constraints: {e}")
                    
                    # Drop indexes
                    indexes_query = "SHOW INDEXES"
                    try:
                        indexes = list(schema_session.run(indexes_query))
                        for index in indexes:
                            name = index.get('name')
                            if name:
                                logging.info(f"Dropping index: {name}")
                                drop_query = f"DROP INDEX {name}"
                                schema_session.run(drop_query)
                    except Exception as e:
                        logging.warning(f"Error dropping indexes: {e}")
                
                # Then delete all data
                query = """
                MATCH (n)
                DETACH DELETE n
                RETURN count(*) as deleted_count
                """
            
            params = {}
        
        # Execute the deletion
        with driver.session(database=database) as session:
            result = session.run(query, params)
            stats = result.consume().counters
            
            # Get more detailed information about what was deleted
            info_query = "CALL db.schema.visualization()"
            schema_result = session.run(info_query)
            
            # Close the driver
            driver.close()
            
            return {
                "nodes_deleted": stats.nodes_deleted,
                "relationships_deleted": stats.relationships_deleted,
                "properties_set": stats.properties_set,
                "labels_added": stats.labels_added,
                "indexes_added": stats.indexes_added,
                "constraints_added": stats.constraints_added,
                "indexes_removed": stats.indexes_removed,
                "constraints_removed": stats.constraints_removed
            }
            
    except Exception as e:
        logging.error(f"Failed to clear database: {e}")
        if 'driver' in locals():
            driver.close()
        raise

def confirm_action(repository: Optional[str] = None, force: bool = False) -> bool:
    """
    Ask for confirmation before clearing the database.
    
    Args:
        repository: Repository name to clear (optional)
        force: Skip confirmation prompt
        
    Returns:
        Whether the user confirmed the action
    """
    if force:
        return True
        
    if repository:
        prompt = f"⚠️  WARNING: This will delete all data for repository '{repository}' from Neo4j. This cannot be undone! Continue? [y/N]: "
    else:
        prompt = "⚠️  WARNING: This will delete ALL DATA from Neo4j. This cannot be undone! Continue? [y/N]: "
        
    response = input(prompt)
    return response.lower() in ['y', 'yes']

def print_banner(text, style="default"):
    """
    Print a formatted banner with text in different styles.
    
    Args:
        text: The text to display in the banner
        style: The style to use ('default', 'success', 'error', 'info')
    """
    width = 80
    
    # Select style
    if style == "success":
        symbol = "✅"
        border = "═"
        prefix = "SUCCESS: "
    elif style == "error":
        symbol = "❌"
        border = "═"
        prefix = "ERROR: "
    elif style == "info":
        symbol = "ℹ️ "
        border = "─"
        prefix = ""
    elif style == "warning":
        symbol = "⚠️ "
        border = "─"
        prefix = "WARNING: "
    else:  # default
        symbol = "🔶"
        border = "═"
        prefix = ""
    
    print("\n" + border*width)
    print(f"{symbol} {prefix}{text}".center(width))
    print(border*width + "\n")

def main():
    """Main entry point for the script."""
    args = parse_args()
    setup_logging(args.verbose)
    
    # Check if user confirmed the action
    if not confirm_action(args.repository, args.force):
        print("Operation cancelled.")
        return
    
    try:
        # Clear the database
        stats = clear_database(
            uri=args.uri,
            user=args.user,
            password=args.password,
            database=args.database,
            repository=args.repository,
            preserve_schema=args.preserve_schema
        )
        
        # Print summary
        if args.repository:
            print_banner(f"Successfully cleared data for repository '{args.repository}'", "success")
        else:
            print_banner("Successfully cleared all data from the database", "success")
            
        print(f"📊 DELETION STATISTICS")
        print(f"  🗑️  Nodes deleted: {stats['nodes_deleted']}")
        print(f"  🗑️  Relationships deleted: {stats['relationships_deleted']}")
        
        if not args.preserve_schema and not args.repository:
            print(f"  🗑️  Constraints removed: {stats['constraints_removed']}")
            print(f"  🗑️  Indexes removed: {stats['indexes_removed']}")
            
        print("\n💡 TIP: You can now run a fresh indexing job with:")
        if args.repository:
            print(f"  python -m code_indexer.ingestion.cli.run_pipeline --repo-path <path> --full-indexing")
        else:
            print(f"  python -m code_indexer.ingestion.cli.run_pipeline --repo-path <path>")
            
    except Exception as e:
        print_banner(f"Failed to clear database: {str(e)}", "error")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())