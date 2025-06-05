#!/usr/bin/env python3
"""
Graph Report Generator

This script connects to Neo4j and generates a comprehensive report about the knowledge graph
created by the CodeIndexer pipeline. It shows node counts, relationship types, and other
useful statistics to help understand the graph structure.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j package not found. Please install it with:")
    print("pip install neo4j")
    sys.exit(1)

class Neo4jReporter:
    """Connects to Neo4j and generates reports about the graph structure."""
    
    def __init__(self, uri: str, user: str, password: str, database: str = None):
        """Initialize the Neo4j connection."""
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None
        
    def connect(self) -> bool:
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test the connection
            with self.driver.session(database=self.database) as session:
                result = session.run("MATCH () RETURN count(*) as count")
                count = result.single()["count"]
                print(f"✅ Connected to Neo4j database with {count} nodes")
            return True
        except Exception as e:
            print(f"❌ Error connecting to Neo4j: {str(e)}")
            return False
            
    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            
    def run_query(self, query: str) -> List[Dict]:
        """Run a Cypher query and return the results."""
        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            return [record.data() for record in result]
            
    def get_node_counts(self) -> List[Dict]:
        """Get counts of each node label in the graph."""
        query = """
        MATCH (n)
        RETURN labels(n) as labels, count(n) as count
        ORDER BY count DESC
        """
        return self.run_query(query)
        
    def get_relationship_counts(self) -> List[Dict]:
        """Get counts of each relationship type in the graph."""
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """
        return self.run_query(query)
        
    def get_repository_stats(self) -> List[Dict]:
        """Get stats for each repository in the graph."""
        query = """
        MATCH (f:File)
        WITH f.repository as repo, count(f) as fileCount
        RETURN repo, fileCount
        ORDER BY fileCount DESC
        """
        return self.run_query(query)
        
    def get_function_stats(self) -> List[Dict]:
        """Get statistics about functions in the graph."""
        query = """
        MATCH (f:Function)
        RETURN 
            count(f) as totalFunctions,
            avg(count { (f)<-[:CONTAINS]-() }) as avgCallers,
            max(count { (f)<-[:CONTAINS]-() }) as maxCallers
        """
        return self.run_query(query)
        
    def get_class_stats(self) -> List[Dict]:
        """Get statistics about classes in the graph."""
        query = """
        MATCH (c:Class)
        RETURN 
            count(c) as totalClasses,
            avg(count { (c)-[:CONTAINS]->(:Function) }) as avgFunctionsPerClass,
            max(count { (c)-[:CONTAINS]->(:Function) }) as maxFunctionsPerClass
        """
        return self.run_query(query)
        
    def get_call_resolution_stats(self) -> List[Dict]:
        """Get statistics about call site resolution."""
        query = """
        MATCH (cs:CallSite)
        WITH count(cs) as totalCallSites
        MATCH (cs:CallSite)-[:RESOLVES_TO]->()
        WITH count(cs) as resolvedCallSites, totalCallSites
        RETURN 
            totalCallSites,
            resolvedCallSites,
            CASE WHEN totalCallSites > 0 
                THEN toFloat(resolvedCallSites) / totalCallSites * 100 
                ELSE 0 
            END as resolutionPercentage
        """
        return self.run_query(query)
        
    def get_import_resolution_stats(self) -> List[Dict]:
        """Get statistics about import site resolution."""
        query = """
        MATCH (is:ImportSite)
        WITH count(is) as totalImportSites
        MATCH (is:ImportSite)-[:RESOLVES_TO]->()
        WITH count(is) as resolvedImportSites, totalImportSites
        RETURN 
            totalImportSites,
            resolvedImportSites,
            CASE WHEN totalImportSites > 0 
                THEN toFloat(resolvedImportSites) / totalImportSites * 100 
                ELSE 0 
            END as resolutionPercentage
        """
        return self.run_query(query)
        
    def get_top_functions_by_callers(self, limit: int = 10) -> List[Dict]:
        """Get the top functions by number of callers."""
        query = f"""
        MATCH (f:Function)<-[:RESOLVES_TO]-(cs:CallSite)
        WITH f, count(cs) as callerCount
        WHERE callerCount > 0
        RETURN f.name as functionName, f.file_id as fileId, callerCount
        ORDER BY callerCount DESC
        LIMIT {limit}
        """
        return self.run_query(query)
        
    def get_top_files_by_functions(self, limit: int = 10) -> List[Dict]:
        """Get the top files by number of functions."""
        query = f"""
        MATCH (file:File)-[:CONTAINS]->(f:Function)
        WITH file, count(f) as functionCount
        RETURN file.path as filePath, functionCount
        ORDER BY functionCount DESC
        LIMIT {limit}
        """
        return self.run_query(query)
        
    def generate_report(self, output_file: str = None) -> Dict:
        """Generate a comprehensive report about the graph."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "node_counts": self.get_node_counts(),
            "relationship_counts": self.get_relationship_counts(),
            "repository_stats": self.get_repository_stats(),
            "function_stats": self.get_function_stats()[0] if self.get_function_stats() else {},
            "class_stats": self.get_class_stats()[0] if self.get_class_stats() else {},
            "call_resolution_stats": self.get_call_resolution_stats()[0] if self.get_call_resolution_stats() else {},
            "import_resolution_stats": self.get_import_resolution_stats()[0] if self.get_import_resolution_stats() else {},
            "top_functions_by_callers": self.get_top_functions_by_callers(),
            "top_files_by_functions": self.get_top_files_by_functions()
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Report saved to {output_file}")
            
        return report
    
    def print_report_summary(self, report: Dict):
        """Print a formatted summary of the report to the console."""
        print("\n" + "="*80)
        print(f"📊 KNOWLEDGE GRAPH REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Node counts
        print("\n📌 NODE COUNTS")
        for item in report['node_counts']:
            labels = ', '.join(item['labels']) if isinstance(item['labels'], list) else item['labels']
            print(f"  {labels}: {item['count']}")
            
        # Relationship counts
        print("\n📌 RELATIONSHIP COUNTS")
        for item in report['relationship_counts']:
            print(f"  {item['type']}: {item['count']}")
            
        # Repository stats
        print("\n📌 REPOSITORY STATISTICS")
        for item in report['repository_stats']:
            print(f"  {item['repo']}: {item['fileCount']} files")
            
        # Function stats
        print("\n📌 FUNCTION STATISTICS")
        func_stats = report['function_stats']
        if func_stats:
            print(f"  Total Functions: {func_stats.get('totalFunctions', 0)}")
            print(f"  Avg Callers per Function: {func_stats.get('avgCallers', 0):.2f}")
            print(f"  Max Callers for a Function: {func_stats.get('maxCallers', 0)}")
            
        # Class stats
        print("\n📌 CLASS STATISTICS")
        class_stats = report['class_stats']
        if class_stats:
            print(f"  Total Classes: {class_stats.get('totalClasses', 0)}")
            print(f"  Avg Functions per Class: {class_stats.get('avgFunctionsPerClass', 0):.2f}")
            print(f"  Max Functions in a Class: {class_stats.get('maxFunctionsPerClass', 0)}")
            
        # Resolution stats
        print("\n📌 RESOLUTION STATISTICS")
        call_stats = report['call_resolution_stats']
        if call_stats:
            print(f"  Call Sites: {call_stats.get('totalCallSites', 0)}")
            print(f"  Resolved Call Sites: {call_stats.get('resolvedCallSites', 0)} " +
                  f"({call_stats.get('resolutionPercentage', 0):.2f}%)")
                  
        import_stats = report['import_resolution_stats']
        if import_stats:
            print(f"  Import Sites: {import_stats.get('totalImportSites', 0)}")
            print(f"  Resolved Import Sites: {import_stats.get('resolvedImportSites', 0)} " +
                  f"({import_stats.get('resolutionPercentage', 0):.2f}%)")
                  
        # Top functions by callers
        print("\n📌 TOP FUNCTIONS BY CALLERS")
        for i, item in enumerate(report['top_functions_by_callers']):
            print(f"  {i+1}. {item['functionName']} ({item['callerCount']} callers)")
            
        # Top files by functions
        print("\n📌 TOP FILES BY FUNCTIONS")
        for i, item in enumerate(report['top_files_by_functions']):
            print(f"  {i+1}. {item['filePath']} ({item['functionCount']} functions)")
            
        print("\n" + "="*80)

def main():
    """Main function to parse arguments and run the report generator."""
    parser = argparse.ArgumentParser(description='Generate a report about the Neo4j knowledge graph.')
    
    parser.add_argument('--uri', default='bolt://localhost:7687', 
                        help='Neo4j connection URI (default: bolt://localhost:7687)')
    parser.add_argument('--user', default='neo4j', 
                        help='Neo4j username (default: neo4j)')
    parser.add_argument('--password', default='password', 
                        help='Neo4j password (default: password)')
    parser.add_argument('--database', default=None, 
                        help='Neo4j database name (default: None)')
    parser.add_argument('--output', default='graph_report.json', 
                        help='Output file for the JSON report (default: graph_report.json)')
    parser.add_argument('--no-output', action='store_true', 
                        help='Do not save the report to a file')
                        
    args = parser.parse_args()
    
    reporter = Neo4jReporter(args.uri, args.user, args.password, args.database)
    
    if not reporter.connect():
        return 1
        
    try:
        output_file = None if args.no_output else args.output
        report = reporter.generate_report(output_file)
        reporter.print_report_summary(report)
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        return 1
    finally:
        reporter.close()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())