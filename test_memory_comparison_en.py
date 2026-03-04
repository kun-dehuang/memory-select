#!/usr/bin/env python3
"""Memory System Comparison Test Script.

Tests Zep, Mem0 (Standard), and Mem0Graph with 20 cognitive test cases.
Compares search results across all three systems.

Usage:
    python test_memory_comparison.py
    python test_memory_comparison.py --filter 1-5
    python test_memory_comparison.py --search "巴塞罗那"
    python test_memory_comparison.py --output csv
"""

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.zep_wrapper import ZepMemory, ZepGraph
from core.mem0_wrapper import Mem0Standard, Mem0Graph


@dataclass
class TestCase:
    """Test case definition."""
    id: int
    level: str  # 初级, 中级, 高级, 专家
    type_name: str  # e.g., Entity Linking
    ability: str  # Core ability being tested
    query: str
    expected_keywords: list[str] = field(default_factory=list)
    expected_entities: list[str] = field(default_factory=list)


@dataclass
class SystemResult:
    """Result from a single memory system."""
    system_name: str
    results_count: int
    duration_ms: float
    top_results: list[dict] = field(default_factory=list)
    has_relations: bool = False
    relations: list[dict] = field(default_factory=list)
    keyword_matches: list[str] = field(default_factory=list)
    keyword_match_pct: float = 0.0


@dataclass
class TestResult:
    """Result of running a test case."""
    test_case: TestCase
    system_results: dict[str, SystemResult] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# Test cases based on the 20 cognitive aspects, aligned with phase1_events_en.json data
TEST_CASES = [
    TestCase(
        id=1,
        level="初级",
        type_name="实体关联检索",
        ability="Entity Linking (多地关联)",
        query="In which cities did the protagonist (OuyangbingjieEn) leave her footprints between October and November 2025?",
        expected_keywords=["Barcelona", "Beijing", "Florence", "Singapore", "Bali"],
        expected_entities=["Barcelona", "Beijing", "Florence", "Singapore", "Bali"]
    ),
    TestCase(
        id=2,
        level="初级",
        type_name="属性提取",
        ability="Fact Extraction (饮品)",
        query="What types of drinks does the protagonist (OuyangbingjieEn) usually like to consume? List the specific drinks she has ordered at different occasions.",
        expected_keywords=["Coffee", "Wine", "Beer"],
        expected_entities=["Coffee", "Wine", "Beer"]
    ),
]


class TablePrinter:
    """Print formatted tables."""

    @staticmethod
    def print_header(text: str, width: int = 80) -> None:
        """Print a section header."""
        colors = {
            "header": "\033[95m",
            "cyan": "\033[96m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "end": "\033[0m",
            "bold": "\033[1m",
        }
        border = colors["cyan"] + "=" * width + colors["end"]
        print(f"\n{border}")
        print(f"{colors['bold']}{colors['header']}{text.center(width)}{colors['end']}")
        print(f"{border}")

    @staticmethod
    def print_subheader(text: str) -> None:
        """Print a subsection header."""
        colors = {
            "cyan": "\033[96m",
            "end": "\033[0m",
        }
        print(f"\n{colors['cyan']}{'─' * 80}{colors['end']}")
        print(f"{text}")
        print(f"{colors['cyan']}{'─' * 80}{colors['end']}")

    @staticmethod
    def print_table(headers: list[str], rows: list[list[str]], alignments: list[str] = None) -> None:
        """Print a formatted table.

        Args:
            headers: Column headers
            rows: Table rows (list of lists)
            alignments: List of 'left', 'right', or 'center' for each column
        """
        if alignments is None:
            alignments = ["left"] * len(headers)

        # Calculate column widths
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(header)
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(max_width + 2)

        # Print header
        header_line = ""
        for i, (header, width) in enumerate(zip(headers, col_widths)):
            align = alignments[i] if i < len(alignments) else "left"
            if align == "center":
                header_line += header.center(width)
            elif align == "right":
                header_line += header.rjust(width)
            else:
                header_line += header.ljust(width)
        print(header_line)

        # Print separator
        separator = "-" * sum(col_widths)
        print(separator)

        # Print rows
        for row in rows:
            row_line = ""
            for i, (cell, width) in enumerate(zip(row, col_widths)):
                align = alignments[i] if i < len(alignments) else "left"
                cell_str = str(cell)[:width-2]  # Truncate if too long
                if align == "center":
                    row_line += cell_str.center(width)
                elif align == "right":
                    row_line += cell_str.rjust(width)
                else:
                    row_line += cell_str.ljust(width)
            print(row_line)

    @staticmethod
    def get_color(name: str) -> str:
        """Get ANSI color code."""
        colors = {
            "header": "\033[95m",
            "cyan": "\033[96m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "end": "\033[0m",
            "bold": "\033[1m",
        }
        return colors.get(name, "")

    @staticmethod
    def colorize(text: str, color: str) -> str:
        """Apply color to text."""
        return f"{TablePrinter.get_color(color)}{text}{TablePrinter.get_color('end')}"


class MemoryTestRunner:
    """Run comparison tests across memory systems."""

    def __init__(self, user_id: str = "OuyangbingjieEn"):
        """Initialize test runner.

        Args:
            user_id: User ID for memory systems
        """
        self.user_id = user_id
        self.systems = {}
        self.results: list[TestResult] = []

    def init_systems(self) -> None:
        """Initialize all memory systems."""
        TablePrinter.print_header("INITIALIZING MEMORY SYSTEMS")

        try:
            print(f"\n{TablePrinter.colorize('→ Initializing Zep Memory...', 'cyan')}")
            self.systems["zep_memory"] = ZepMemory(user_id=self.user_id)
            print(f"   Thread ID: {self.systems['zep_memory'].thread_id}")
            print(f"   Count: {self.systems['zep_memory'].count()} memories")
        except Exception as e:
            print(f"   {TablePrinter.colorize(f'Failed: {e}', 'red')}")
            self.systems["zep_memory"] = None

        try:
            print(f"\n{TablePrinter.colorize('→ Initializing Zep Graph...', 'cyan')}")
            self.systems["zep_graph"] = ZepGraph(user_id=self.user_id)
            print(f"   Thread ID: {self.systems['zep_graph'].thread_id}")
            print(f"   Count: {self.systems['zep_graph'].count()} memories")
        except Exception as e:
            print(f"   {TablePrinter.colorize(f'Failed: {e}', 'red')}")
            self.systems["zep_graph"] = None

        try:
            print(f"\n{TablePrinter.colorize('→ Initializing Mem0 Standard...', 'cyan')}")
            self.systems["mem0_standard"] = Mem0Standard(user_id=self.user_id)
            print(f"   Collection: {self.systems['mem0_standard'].collection_name}")
            print(f"   Count: {self.systems['mem0_standard'].count()} memories")
        except Exception as e:
            print(f"   {TablePrinter.colorize(f'Failed: {e}', 'red')}")
            self.systems["mem0_standard"] = None

        try:
            print(f"\n{TablePrinter.colorize('→ Initializing Mem0 Graph...', 'cyan')}")
            self.systems["mem0_graph"] = Mem0Graph(user_id=self.user_id)
            print(f"   Collection: {self.systems['mem0_graph'].collection_name}")
            print(f"   Count: {self.systems['mem0_graph'].count()} memories")
        except Exception as e:
            print(f"   {TablePrinter.colorize(f'Failed: {e}', 'red')}")
            self.systems["mem0_graph"] = None

        active_systems = [k for k, v in self.systems.items() if v is not None]
        print(f"\n{TablePrinter.colorize(f'Active systems: {len(active_systems)}/{len(self.systems)}', 'green')}")
        for name in active_systems:
            print(f"   - {name}")

    def search_system(
        self,
        system_name: str,
        system,
        query: str,
        expected_keywords: list[str],
        limit: int = 5
    ) -> SystemResult:
        """Search a single memory system.

        Args:
            system_name: Name of the system
            system: The memory system instance
            query: Search query
            expected_keywords: Keywords to check for
            limit: Max results

        Returns:
            SystemResult with search results
        """
        if system is None:
            return SystemResult(
                system_name=system_name,
                results_count=0,
                duration_ms=0,
                top_results=[]
            )

        start_time = time.time()
        try:
            results = system.search(query=query, limit=limit, uid=self.user_id)
            duration_ms = (time.time() - start_time) * 1000

            # Check for graph relations
            has_relations = False
            relations = []
            if results and hasattr(results[0], 'graph_relations') and results[0].graph_relations:
                has_relations = True
                relations = [
                    {
                        "source": r.source,
                        "relationship": r.relationship,
                        "destination": r.destination
                    }
                    for r in results[0].graph_relations[:5]
                ]

            top_results = []
            all_content = ""
            for i, r in enumerate(results[:5]):
                content = r.content
                all_content += content + " "
                top_results.append({
                    "rank": i + 1,
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "score": round(r.score, 3),
                    "metadata": {
                        k: v for k, v in r.metadata.items()
                        if k in ["event_id", "category", "city", "country", "location", "timestamp"]
                    }
                })

            # Calculate keyword matches
            keyword_matches = []
            if expected_keywords:
                all_content_lower = all_content.lower()
                for kw in expected_keywords:
                    if kw.lower() in all_content_lower:
                        keyword_matches.append(kw)

            keyword_match_pct = len(keyword_matches) / len(expected_keywords) * 100 if expected_keywords else 0

            return SystemResult(
                system_name=system_name,
                results_count=len(results),
                duration_ms=round(duration_ms, 2),
                top_results=top_results,
                has_relations=has_relations,
                relations=relations,
                keyword_matches=keyword_matches,
                keyword_match_pct=round(keyword_match_pct, 1)
            )
        except Exception as e:
            return SystemResult(
                system_name=system_name,
                results_count=0,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                top_results=[{"error": str(e)}]
            )

    def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case across all systems.

        Args:
            test_case: TestCase to run

        Returns:
            TestResult with all system results
        """
        result = TestResult(test_case=test_case)

        for system_name, system in self.systems.items():
            system_result = self.search_system(
                system_name=system_name,
                system=system,
                query=test_case.query,
                expected_keywords=test_case.expected_keywords,
                limit=5
            )
            result.system_results[system_name] = system_result

        return result

    def print_test_result(self, result: TestResult, verbose: bool = False) -> None:
        """Print formatted test result.

        Args:
            result: TestResult to print
            verbose: Whether to show full content
        """
        tc = result.test_case

        # Header
        level_colors = {
            "初级": "green",
            "中级": "yellow",
            "高级": "red",
            "专家": "blue"
        }
        level_color = level_colors.get(tc.level, "white")

        TablePrinter.print_subheader(
            f"[{tc.id:02d}] {TablePrinter.colorize(tc.level, level_color)} - {tc.type_name}"
        )

        print(f"\n{TablePrinter.colorize('考察能力:', 'bold')} {tc.ability}")
        print(f"{TablePrinter.colorize('查询语句:', 'bold')} {tc.query}")
        print(f"{TablePrinter.colorize('期望关键词:', 'bold')} {', '.join(tc.expected_keywords[:5])}")

        # Results table
        headers = ["System", "Results", "Time", "Relations", "Keywords", "Top Result"]
        rows = []

        for sys_name, sys_result in result.system_results.items():
            display_name = sys_name.replace("_", " ").title()

            if sys_result.top_results and "error" in sys_result.top_results[0]:
                rows.append([
                    display_name,
                    TablePrinter.colorize("ERROR", "red"),
                    f"{sys_result.duration_ms}ms",
                    "-",
                    "-",
                    sys_result.top_results[0]["error"][:40]
                ])
            else:
                # Relations indicator
                rel_str = TablePrinter.colorize("Yes", "green") if sys_result.has_relations else "No"

                # Keywords with color
                kw_pct = sys_result.keyword_match_pct
                kw_color = "green" if kw_pct > 60 else "yellow" if kw_pct > 30 else "red"
                kw_str = TablePrinter.colorize(f"{kw_pct:.0f}%", kw_color)

                # Top result preview
                top = sys_result.top_results[0] if sys_result.top_results else {}
                content = top.get("content", "")[:50]
                if not content and "error" in top:
                    content = top["error"][:50]

                rows.append([
                    display_name,
                    str(sys_result.results_count),
                    f"{sys_result.duration_ms:.0f}ms",
                    rel_str,
                    kw_str,
                    content
                ])

        print()
        TablePrinter.print_table(headers, rows)

        # Show graph relations if available
        for sys_name, sys_result in result.system_results.items():
            if sys_result.has_relations and sys_result.relations:
                print(f"\n{TablePrinter.colorize(f'{sys_name} Relations:', 'yellow')}")
                for rel in sys_result.relations[:5]:
                    print(f"  • {rel.get('source', '')} → {rel.get('relationship', '')} → {rel.get('destination', '')}")

    def print_results_table(self) -> None:
        """Print a comprehensive results table for all tests."""
        TablePrinter.print_header("COMPREHENSIVE RESULTS TABLE")

        # Prepare table data
        headers = ["ID", "Level", "Type", "mem0", "mem0g", "zep", "Best"]
        rows = []
        system_names = ["mem0_standard", "mem0_graph", "zep_graph"]

        for result in self.results:
            tc = result.test_case

            # Short type name
            type_short = tc.type_name[:8]

            # Get results for each system
            system_scores = []
            for sys_name in system_names:
                sys_result = result.system_results.get(sys_name)
                if sys_result and sys_result.results_count > 0:
                    score_str = f"{sys_result.keyword_match_pct:.0f}%"
                    if sys_result.keyword_match_pct >= 60:
                        score_str = TablePrinter.colorize(score_str, "green")
                    elif sys_result.keyword_match_pct >= 30:
                        score_str = TablePrinter.colorize(score_str, "yellow")
                    else:
                        score_str = TablePrinter.colorize(score_str, "red")
                    system_scores.append(score_str)
                else:
                    system_scores.append(TablePrinter.colorize("—", "cyan"))

            # Find best system
            best_sys = "-"
            best_pct = 0
            for sys_name in system_names:
                sys_result = result.system_results.get(sys_name)
                if sys_result and sys_result.keyword_match_pct > best_pct:
                    best_pct = sys_result.keyword_match_pct
                    best_sys = sys_name.replace("_", " ").replace("mem0_standard", "mem0").replace("mem0_graph", "mem0g").replace("zep_graph", "zep")

            rows.append([
                f"{tc.id:02d}",
                tc.level,
                type_short,
                system_scores[0],
                system_scores[1],
                system_scores[2],
                best_sys
            ])

        TablePrinter.print_table(headers, rows, alignments=["right", "left", "left", "center", "center", "center", "left"])

    def print_detailed_table(self) -> None:
        """Print detailed results with counts and times."""
        TablePrinter.print_header("DETAILED PERFORMANCE TABLE")

        headers = ["ID", "Test", "mem0", "mem0g", "zep"]
        rows = []

        for result in self.results:
            tc = result.test_case
            test_name = tc.type_name[:10]

            row = [f"{tc.id:02d}", test_name]

            for sys_name in ["mem0_standard", "mem0_graph", "zep_graph"]:
                sys_result = result.system_results.get(sys_name)
                if sys_result and sys_result.results_count > 0:
                    info = f"{sys_result.results_count}r/{sys_result.duration_ms:.0f}ms"
                    row.append(info)
                else:
                    row.append("—")

            rows.append(row)

        TablePrinter.print_table(headers, rows, alignments=["right", "left", "center", "center", "center"])

    def print_summary(self) -> None:
        """Print test summary statistics."""
        if not self.results:
            print(f"\n{TablePrinter.colorize('No results to summarize.', 'yellow')}")
            return

        TablePrinter.print_header("TEST SUMMARY")

        # Calculate stats per system
        system_stats = {}
        for sys_name in self.systems.keys():
            stats = {
                "total_tests": 0,
                "no_results": 0,
                "has_relations": 0,
                "avg_duration": 0,
                "avg_results": 0,
                "avg_keyword_match": 0,
                "total_duration": 0,
                "total_results": 0,
                "total_match_pct": 0
            }
            system_stats[sys_name] = stats

        for result in self.results:
            for sys_name, sys_result in result.system_results.items():
                if sys_name not in system_stats:
                    continue
                stats = system_stats[sys_name]
                stats["total_tests"] += 1
                stats["total_duration"] += sys_result.duration_ms
                stats["total_results"] += sys_result.results_count

                if sys_result.results_count == 0:
                    stats["no_results"] += 1
                if sys_result.has_relations:
                    stats["has_relations"] += 1

                stats["total_match_pct"] += sys_result.keyword_match_pct

        # Print stats table
        headers = ["System", "Tests", "No Res", "Avg Res", "Avg Time", "Relations", "Kw Match"]
        rows = []

        for sys_name, stats in system_stats.items():
            if stats["total_tests"] == 0:
                continue

            avg_results = stats["total_results"] / stats["total_tests"]
            avg_duration = stats["total_duration"] / stats["total_tests"]
            avg_match = stats["total_match_pct"] / stats["total_tests"]

            relations_str = f"{stats['has_relations']}/{stats['total_tests']}"

            # Color code the match percentage
            match_color = "green" if avg_match > 40 else "yellow" if avg_match > 20 else ""
            match_str = f"{avg_match:.1f}%"
            if match_color:
                match_str = TablePrinter.colorize(match_str, match_color)

            display_name = sys_name.replace("_", " ").replace("mem0", "Mem0 ").replace("zep", "Zep ").title()

            rows.append([
                display_name,
                str(stats["total_tests"]),
                str(stats["no_results"]),
                f"{avg_results:.1f}",
                f"{avg_duration:.0f}ms",
                relations_str,
                match_str
            ])

        TablePrinter.print_table(headers, rows, alignments=["left", "right", "right", "right", "right", "center", "left"])

        # Best performer analysis
        print()
        print(TablePrinter.colorize("Performance Analysis:", "bold"))

        # Filter systems that actually ran tests
        valid_systems = {k: v for k, v in system_stats.items() if v["total_tests"] > 0}

        if valid_systems:
            fastest = min(valid_systems.items(), key=lambda x: x[1]["total_duration"] / x[1]["total_tests"])
            avg_time = fastest[1]["total_duration"] / fastest[1]["total_tests"]
            print(f"  {TablePrinter.colorize('⚡', 'yellow')} Fastest: {fastest[0]} (avg {avg_time:.0f}ms)")

            most_results = max(valid_systems.items(), key=lambda x: x[1]["total_results"] / x[1]["total_tests"])
            avg_res = most_results[1]["total_results"] / most_results[1]["total_tests"]
            print(f"  {TablePrinter.colorize('📊', 'cyan')} Most Results: {most_results[0]} (avg {avg_res:.1f} per query)")

            best_match = max(valid_systems.items(), key=lambda x: x[1]["total_match_pct"] / x[1]["total_tests"])
            avg_match = best_match[1]["total_match_pct"] / best_match[1]["total_tests"]
            print(f"  {TablePrinter.colorize('🎯', 'green')} Best Keyword Match: {best_match[0]} ({avg_match:.1f}%)")

    def save_results(self, output_path: str = "test_results") -> None:
        """Save test results to CSV file.

        Args:
            output_path: Base path for output files (without extension)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Only save CSV
        csv_path = f"{output_path}_{timestamp}.csv"
        self._save_csv(csv_path)

        # Also save a simple text table for quick viewing
        txt_path = f"{output_path}_{timestamp}.txt"
        self._save_text_table(txt_path)

    def _save_csv(self, path: str) -> None:
        """Save results as CSV with actual search results - matching evaluate_test_queries.py format."""
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # Header matching evaluate_test_queries.py format
            headers = [
                "评测方向", "query", "预期结果",
                "mem0", "mem0g", "zep_graph"
            ]
            writer.writerow(headers)

            # Rows
            for result in self.results:
                tc = result.test_case

                # Format mem0 result
                mem0_std = result.system_results.get("mem0_standard")
                if mem0_std and mem0_std.top_results:
                    mem0_lines = []
                    for i, r in enumerate(mem0_std.top_results):
                        content = r.get("content", "")
                        score = r.get("score", 0)
                        metadata = r.get("metadata", {})
                        metadata_str = ", ".join([f"{k}={v}" for k, v in metadata.items()]) if metadata else ""
                        mem0_lines.append(f"[{i+1}] {content}\n    (score={score:.4f}, {metadata_str})")
                    mem0_value = "\n".join(mem0_lines)
                else:
                    mem0_value = "[无检索结果]"

                # Format mem0g result (with relations)
                mem0_graph = result.system_results.get("mem0_graph")
                if mem0_graph and mem0_graph.top_results:
                    mem0g_lines = []
                    for i, r in enumerate(mem0_graph.top_results):
                        content = r.get("content", "")
                        score = r.get("score", 0)
                        metadata = r.get("metadata", {})
                        metadata_str = ", ".join([f"{k}={v}" for k, v in metadata.items()]) if metadata else ""

                        # Add graph relations info
                        graph_info = ""
                        if mem0_graph.relations:
                            relations = [f"{rel['source']}→{rel['relationship']}→{rel['destination']}" for rel in mem0_graph.relations[:5]]
                            graph_info = f", 图关系: {', '.join(relations)}"

                        mem0g_lines.append(f"[{i+1}] {content}\n    (score={score:.4f}, {metadata_str}{graph_info})")
                    mem0g_value = "\n".join(mem0g_lines)
                else:
                    mem0g_value = "[无检索结果]"

                # Format zep result
                zep_result = result.system_results.get("zep_graph") or result.system_results.get("zep_memory")
                if zep_result and zep_result.top_results:
                    zep_lines = []
                    for i, r in enumerate(zep_result.top_results):
                        content = r.get("content", "")
                        score = r.get("score", 0)
                        metadata = r.get("metadata", {})
                        metadata_str = ", ".join([f"{k}={v}" for k, v in metadata.items()]) if metadata else ""
                        zep_lines.append(f"[{i+1}] {content}\n    (score={score:.4f}, {metadata_str})")
                    zep_value = "\n".join(zep_lines)
                else:
                    zep_value = "[无检索结果]"

                row = [
                    tc.level,  # 评测方向 (使用 level)
                    tc.query,  # query
                    ", ".join(tc.expected_keywords[:3]) if tc.expected_keywords else "",  # 预期结果 (简化)
                    mem0_value,  # mem0
                    mem0g_value,  # mem0g
                    zep_value   # zep_graph
                ]

                writer.writerow(row)

        print(f"{TablePrinter.colorize(f'CSV saved to {path}', 'green')}")

    def _save_text_table(self, path: str) -> None:
        """Save results as plain text table."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("MEMORY SYSTEM COMPARISON TEST RESULTS\n")
            f.write("=" * 100 + "\n")
            f.write(f"User ID: {self.user_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Total Tests: {len(self.results)}\n")
            f.write("\n")

            # Summary table - matching evaluate_test_queries.py format
            f.write("-" * 100 + "\n")
            f.write("SUMMARY TABLE\n")
            f.write("-" * 100 + "\n\n")

            headers = ["ID", "评测方向", "Type", "mem0", "mem0g", "zep", "Best"]
            f.write(f"{headers[0]:<4} {headers[1]:<8} {headers[2]:<20} {headers[3]:<8} {headers[4]:<8} {headers[5]:<8} {headers[6]:<10}\n")
            f.write("-" * 100 + "\n")

            system_names = ["mem0_standard", "mem0_graph", "zep_graph"]

            for result in self.results:
                tc = result.test_case
                type_short = tc.type_name[:18]

                system_scores = []
                best_sys = "-"
                best_pct = 0

                for sys_name in system_names:
                    sys_result = result.system_results.get(sys_name)
                    if sys_result and sys_result.results_count > 0:
                        score_str = f"{sys_result.keyword_match_pct:.0f}%"
                        system_scores.append(f"{score_str:<8}")
                        if sys_result.keyword_match_pct > best_pct:
                            best_pct = sys_result.keyword_match_pct
                            best_sys = sys_name
                    else:
                        system_scores.append(f"{'—':<8}")

                best_short = best_sys.replace("mem0_standard", "mem0").replace("mem0_graph", "mem0g").replace("zep_memory", "zep").replace("zep_graph", "zep")

                f.write(f"{tc.id:<4} {tc.level:<8} {type_short:<20} {system_scores[0]} {system_scores[1]} {system_scores[2]} {best_short:<10}\n")

            f.write("\n")
            f.write("=" * 100 + "\n")
            f.write("LEGEND: mem0=Mem0 Standard, mem0g=Mem0 Graph, zep=Zep Graph\n")
            f.write("Numbers indicate keyword match percentage (higher is better)\n")
            f.write("=" * 100 + "\n")

        print(f"{TablePrinter.colorize(f'Text table saved to {path}', 'green')}")

    def run_tests(
        self,
        test_filter: Optional[str] = None,
        custom_query: Optional[str] = None,
        verbose: bool = False,
        show_tables: bool = True
    ) -> None:
        """Run all tests.

        Args:
            test_filter: Filter like "1-5" or "1,3,5" to run specific tests
            custom_query: Custom search query (ignores test cases)
            verbose: Whether to show full content
            show_tables: Whether to show result tables
        """
        self.init_systems()

        # Determine which tests to run
        tests_to_run = TEST_CASES.copy()

        if test_filter:
            tests_to_run = self._parse_filter(test_filter, tests_to_run)

        if custom_query:
            # Run custom query
            TablePrinter.print_header(f"CUSTOM QUERY: {custom_query}")

            tc = TestCase(
                id=0,
                level="CUSTOM",
                type_name="Custom Query",
                ability="Custom Search",
                query=custom_query,
                expected_keywords=[]
            )
            result = self.run_test(tc)
            self.print_test_result(result, verbose=verbose)
            self.results.append(result)
        else:
            # Run all selected test cases
            TablePrinter.print_header(f"RUNNING {len(tests_to_run)} TEST CASES")

            for tc in tests_to_run:
                result = self.run_test(tc)
                self.print_test_result(result, verbose=verbose)
                self.results.append(result)

        self.print_summary()

        if show_tables and not custom_query:
            self.print_results_table()
            self.print_detailed_table()

        self.save_results()

    def _parse_filter(self, filter_str: str, test_cases: list[TestCase]) -> list[TestCase]:
        """Parse test filter string.

        Args:
            filter_str: Filter like "1-5" or "1,3,5"
            test_cases: All test cases

        Returns:
            Filtered list of test cases
        """
        selected_ids = set()

        for part in filter_str.split(','):
            part = part.strip()
            if '-' in part:
                # Range like "1-5"
                try:
                    start, end = part.split('-')
                    selected_ids.update(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            else:
                # Single number
                try:
                    selected_ids.add(int(part))
                except ValueError:
                    pass

        return [tc for tc in test_cases if tc.id in selected_ids]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare memory systems across cognitive test cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_memory_comparison.py              Run all 20 tests
  python test_memory_comparison.py --filter 1-5 Run tests 1 through 5
  python test_memory_comparison.py --filter 1,3,5 Run tests 1, 3, and 5
  python test_memory_comparison.py --search "巴塞罗那" Custom search
        """
    )
    parser.add_argument(
        "--filter",
        help="Filter tests (e.g., '1-5' or '1,3,5')"
    )
    parser.add_argument(
        "--search",
        help="Run a custom search query instead of tests"
    )
    parser.add_argument(
        "--user-id",
        default="OuyangbingjieEn",
        help="User ID for memory systems (default: OuyangbingjieEn)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full content in results"
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Don't show result tables (only save to files)"
    )

    args = parser.parse_args()

    runner = MemoryTestRunner(user_id=args.user_id)
    runner.run_tests(
        test_filter=args.filter,
        custom_query=args.search,
        verbose=args.verbose,
        show_tables=not args.no_tables
    )


if __name__ == "__main__":
    main()
