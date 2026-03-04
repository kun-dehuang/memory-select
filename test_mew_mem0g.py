#!/usr/bin/env python3
"""Mem0Graph Query Test Script for Mew.

Simple test script to query mem0g data for user_id = Mew.

Usage:
    python test_mew_mem0g.py
    python test_mew_mem0g.py --search "查询语句"
    python test_mew_mem0g.py --limit 10
"""

import argparse
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.mem0_wrapper import Mem0Graph


@dataclass
class QueryCase:
    """Query test case."""
    id: int
    category: str
    query: str
    expected_keywords: list[str] = field(default_factory=list)


QUERY_CASES = [
    QueryCase(
        id=1,
        category="日常活动",
        query="Mew最近在做什么？有哪些日常活动？",
        expected_keywords=[]
    ),
    QueryCase(
        id=2,
        category="人际关系",
        query="Mew有哪些朋友或社交关系？",
        expected_keywords=[]
    ),
    QueryCase(
        id=3,
        category="兴趣爱好",
        query="Mew有什么兴趣爱好？",
        expected_keywords=[]
    ),
    QueryCase(
        id=4,
        category="位置轨迹",
        query="Mew去过哪些地方？",
        expected_keywords=[]
    ),
    QueryCase(
        id=5,
        category="位置轨迹",
        query="Where did Mew go?",
        expected_keywords=[]
    ),
    QueryCase(
        id=6,
        category="位置轨迹",
        query="Mew去日本做了什么？",
        expected_keywords=[]
    ),
    QueryCase(
        id=7,
        category="位置轨迹",
        query="Mew去了哪里？",
        expected_keywords=[]
    ),
    QueryCase(
        id=8,
        category="位置轨迹",
        query="Mew去了哪些国家？",
        expected_keywords=[]
    ),
    QueryCase(
        id=8,
        category="位置轨迹",
        query="Mew去了哪些国家？",
        expected_keywords=[]
    ),
]


class Colors:
    """ANSI color codes."""
    HEADER = "\033[95m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def colorize(text: str, color: str) -> str:
    """Apply color to text."""
    color_code = getattr(Colors, color.upper(), "")
    return f"{color_code}{text}{Colors.END}"


def print_header(text: str, width: int = 80) -> None:
    """Print a section header."""
    border = Colors.CYAN + "=" * width + Colors.END
    print(f"\n{border}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(width)}{Colors.END}")
    print(f"{border}")


def print_subheader(text: str) -> None:
    """Print a subsection header."""
    print(f"\n{Colors.CYAN}{'─' * 80}{Colors.END}")
    print(f"{text}")
    print(f"{Colors.CYAN}{'─' * 80}{Colors.END}")


class MewMem0GTester:
    """Test Mem0Graph for Mew user."""

    def __init__(self, user_id: str = "Mew"):
        self.user_id = user_id
        self.mem0g: Mem0Graph = None

    def init_system(self) -> None:
        """Initialize Mem0Graph."""
        print_header("INITIALIZING MEM0GRAPH")

        try:
            print(f"\n{colorize('→ Initializing Mem0Graph...', 'cyan')}")
            self.mem0g = Mem0Graph(user_id=self.user_id)
            print(f"   Collection: {self.mem0g.collection_name}")
            print(f"   Count: {self.mem0g.count()} memories")

            graph_data = self.mem0g.get_graph_data()
            print(f"   Graph nodes: {len(graph_data.nodes)}")
            print(f"   Graph edges: {len(graph_data.edges)}")

        except Exception as e:
            print(f"   {colorize(f'Failed: {e}', 'red')}")
            raise

    def search(self, query: str, limit: int = 5) -> dict:
        """Search Mem0Graph.

        Args:
            query: Search query
            limit: Max results

        Returns:
            Search results dict
        """
        if self.mem0g is None:
            raise RuntimeError("Mem0Graph not initialized")

        start_time = time.time()
        results = self.mem0g.search(query=query, limit=limit, uid=self.user_id)
        duration_ms = (time.time() - start_time) * 1000

        graph_data = self.mem0g.get_graph_data()

        return {
            "query": query,
            "results": results,
            "duration_ms": round(duration_ms, 2),
            "graph_nodes": len(graph_data.nodes),
            "graph_edges": len(graph_data.edges),
            "graph_data": graph_data
        }

    def print_search_result(self, result: dict, show_graph: bool = True) -> None:
        """Print search result.

        Args:
            result: Search result dict
            show_graph: Whether to show graph data
        """
        print_subheader(f"QUERY: {result['query']}")

        print(f"\n{colorize('Duration:', 'bold')} {result['duration_ms']:.2f}ms")
        print(f"{colorize('Results:', 'bold')} {len(result['results'])} items")

        if result['results']:
            print(f"\n{colorize('Search Results:', 'yellow')}")
            for i, r in enumerate(result['results']):
                print(f"\n  [{i+1}] {colorize(f'score={r.score:.3f}', 'cyan')}")
                content = r.content
                if len(content) > 300:
                    content = content[:300] + "..."
                print(f"      {content}")

                if r.metadata:
                    meta_str = ", ".join([f"{k}={v}" for k, v in r.metadata.items() if k not in ['data', 'hash']])
                    if meta_str:
                        print(f"      {colorize('metadata:', 'cyan')} {meta_str}")

                if r.graph_relations:
                    print(f"      {colorize('graph relations:', 'cyan')}")
                    for rel in r.graph_relations[:5]:
                        print(f"        • {rel.source} → {rel.relationship} → {rel.destination}")
        else:
            print(f"\n  {colorize('No results found', 'yellow')}")

        if show_graph:
            self._print_graph_summary(result)

    def _print_graph_summary(self, result: dict) -> None:
        """Print graph summary."""
        print(f"\n{colorize('Graph Summary:', 'yellow')}")
        print(f"  Nodes: {result['graph_nodes']}, Edges: {result['graph_edges']}")

        graph_data = result.get('graph_data')
        if graph_data and graph_data.edges:
            print(f"\n  {colorize('Sample Relations:', 'cyan')}")
            for edge in graph_data.edges[:10]:
                print(f"    • {edge.source} → {edge.relation} → {edge.target}")

    def print_all_graph_data(self) -> None:
        """Print all graph data."""
        print_header("ALL GRAPH DATA")

        graph_data = self.mem0g.get_graph_data()

        print(f"\n{colorize('Nodes:', 'yellow')} ({len(graph_data.nodes)})")
        for node in graph_data.nodes[:20]:
            print(f"  • {node.name} ({node.type})")
        if len(graph_data.nodes) > 20:
            print(f"  ... and {len(graph_data.nodes) - 20} more")

        print(f"\n{colorize('Edges:', 'yellow')} ({len(graph_data.edges)})")
        for edge in graph_data.edges[:20]:
            print(f"  • {edge.source} → {edge.relation} → {edge.target}")
        if len(graph_data.edges) > 20:
            print(f"  ... and {len(graph_data.edges) - 20} more")

    def run_query_cases(self, limit: int = 5) -> None:
        """Run predefined query cases."""
        print_header(f"RUNNING {len(QUERY_CASES)} QUERY CASES")

        for qc in QUERY_CASES:
            result = self.search(qc.query, limit=limit)
            self.print_search_result(result, show_graph=False)

    def run_interactive(self, limit: int = 5) -> None:
        """Run interactive query mode."""
        print_header("INTERACTIVE QUERY MODE")
        print(f"User ID: {self.user_id}")
        print("Type 'quit' to exit, 'graph' to show all graph data\n")

        while True:
            try:
                query = input(f"{colorize('Query>', 'cyan')} ").strip()

                if query.lower() == 'quit':
                    print("Goodbye!")
                    break

                if query.lower() == 'graph':
                    self.print_all_graph_data()
                    continue

                if not query:
                    continue

                result = self.search(query, limit=limit)
                self.print_search_result(result)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"{colorize(f'Error: {e}', 'red')}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query Mem0Graph for Mew user",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_mew_mem0g.py                     Run predefined queries
  python test_mew_mem0g.py --search "爱好"     Custom search
  python test_mew_mem0g.py --interactive       Interactive mode
  python test_mew_mem0g.py --graph             Show all graph data
        """
    )
    parser.add_argument(
        "--search",
        help="Run a custom search query"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max results per query (default: 5)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Show all graph data"
    )
    parser.add_argument(
        "--user-id",
        default="Mew",
        help="User ID (default: Mew)"
    )

    args = parser.parse_args()

    tester = MewMem0GTester(user_id=args.user_id)
    tester.init_system()

    if args.graph:
        tester.print_all_graph_data()
    elif args.search:
        result = tester.search(args.search, limit=args.limit)
        tester.print_search_result(result)
    elif args.interactive:
        tester.run_interactive(limit=args.limit)
    else:
        tester.run_query_cases(limit=args.limit)


if __name__ == "__main__":
    main()
