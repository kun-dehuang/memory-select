#!/usr/bin/env python3
"""Memory评测脚本 - 测试各系统的搜索和LLM生成能力。

从评测集JSON中读取测试查询，分别调用：
- Mem0 Standard (vector search + LLM)
- Mem0 Graph (graph search + LLM)
- Zep Graph (graph search + LLM)

生成评测结果表格。
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from config import config
from core.mem0_wrapper import Mem0Standard, Mem0Graph
from core.zep_wrapper import ZepGraph
from core.llm import get_llm_client


# 配置
TEST_QUERIES_FILE = "/Users/myles/Projects/Pupixel/update_json/memory_generated_queries.json"
USER_ID = "test_002"
LIMIT = 20
OUTPUT_DIR = Path("/Users/myles/Projects/Pupixel/memory-select/evaluation_results")
OUTPUT_DIR.mkdir(exist_ok=True)


class MemoryEvaluator:
    """记忆系统评测器"""

    def __init__(self, user_id: str = USER_ID):
        self.user_id = user_id
        self.llm_client = None

        # 初始化各系统实例
        print(f"[Init] 初始化评测器，用户ID: {user_id}")

        # Mem0 Standard
        try:
            self.mem0_standard = Mem0Standard(
                user_id=user_id,
                collection_name=f"memory_store_{user_id}"
            )
            count = self.mem0_standard.count()
            print(f"[Init] Mem0 Standard: {count} 条记忆")
        except Exception as e:
            print(f"[Init] Mem0 Standard 初始化失败: {e}")
            self.mem0_standard = None

        # Mem0 Graph
        try:
            self.mem0_graph = Mem0Graph(
                user_id=user_id,
                collection_name=f"memory_store_{user_id}"
            )
            count = self.mem0_graph.count()
            print(f"[Init] Mem0 Graph: {count} 条记忆")
        except Exception as e:
            print(f"[Init] Mem0 Graph 初始化失败: {e}")
            self.mem0_graph = None

        # Zep Graph
        try:
            self.zep_graph = ZepGraph(user_id=user_id)
            count = self.zep_graph.count()
            print(f"[Init] Zep Graph: {count} 条记忆")
        except Exception as e:
            print(f"[Init] Zep Graph 初始化失败: {e}")
            self.zep_graph = None

        # LLM Client
        try:
            self.llm_client = get_llm_client()
            print(f"[Init] LLM Client: {config.gemini.model}")
        except Exception as e:
            print(f"[Init] LLM Client 初始化失败: {e}")

    def search_mem0_standard(self, query: str, limit: int = LIMIT) -> str:
        """Mem0 Standard 搜索，返回原始结果"""
        if not self.mem0_standard:
            return "[系统未初始化]"

        try:
            results = self.mem0_standard.search(query, limit, uid=self.user_id)

            if not results:
                return "[无检索结果]"

            # 返回原始搜索结果
            output_parts = []
            for i, r in enumerate(results):
                metadata_str = ", ".join([f"{k}={v}" for k, v in r.metadata.items()]) if r.metadata else ""
                output_parts.append(f"[{i+1}] {r.content}\n    (score={r.score:.4f}, {metadata_str})")

            return "\n".join(output_parts)
        except Exception as e:
            return f"[错误: {str(e)}]"

    def search_mem0_graph(self, query: str, limit: int = LIMIT) -> str:
        """Mem0 Graph 搜索，返回原始结果"""
        if not self.mem0_graph:
            return "[系统未初始化]"

        try:
            results = self.mem0_graph.search(query, limit, uid=self.user_id)

            if not results:
                return "[无检索结果]"

            # 返回原始搜索结果（包含图关系）
            output_parts = []
            for i, r in enumerate(results):
                metadata_str = ", ".join([f"{k}={v}" for k, v in r.metadata.items()]) if r.metadata else ""

                # 添加图关系信息
                graph_info = ""
                if r.graph_relations:
                    relations = [f"{rel.source}→{rel.relationship}→{rel.destination}" for rel in r.graph_relations]
                    graph_info = f", 图关系: {', '.join(relations)}"

                output_parts.append(f"[{i+1}] {r.content}\n    (score={r.score:.4f}, {metadata_str}{graph_info})")

            return "\n".join(output_parts)
        except Exception as e:
            return f"[错误: {str(e)}]"

    def search_zep_graph(self, query: str, limit: int = LIMIT) -> str:
        """Zep Graph 搜索，返回原始结果"""
        if not self.zep_graph:
            return "[系统未初始化]"

        try:
            results = self.zep_graph.search(query, limit, uid=None)

            if not results:
                return "[无检索结果]"

            # 返回原始搜索结果
            output_parts = []
            for i, r in enumerate(results):
                metadata_str = ", ".join([f"{k}={v}" for k, v in r.metadata.items()]) if r.metadata else ""
                output_parts.append(f"[{i+1}] {r.content}\n    (score={r.score:.4f}, {metadata_str})")

            return "\n".join(output_parts)
        except Exception as e:
            return f"[错误: {str(e)}]"

    def evaluate_single(self, test_case: dict) -> dict:
        """评测单条测试用例"""
        query = test_case["query"]
        difficulty = test_case["difficulty"]
        expected = test_case["expected_answer"]

        print(f"\n[Query] {query}")

        result = {
            "评测方向": difficulty,
            "query": query,
            "预期结果": expected,
        }

        # Mem0 Standard
        print("  → Mem0 Standard...")
        start = time.time()
        result["mem0"] = self.search_mem0_standard(query)
        elapsed = time.time() - start
        print(f"    ✓ ({elapsed:.2f}s)")

        # Mem0 Graph
        print("  → Mem0 Graph...")
        start = time.time()
        result["mem0g"] = self.search_mem0_graph(query)
        elapsed = time.time() - start
        print(f"    ✓ ({elapsed:.2f}s)")

        # Zep Graph
        print("  → Zep Graph...")
        start = time.time()
        result["zep_graph"] = self.search_zep_graph(query)
        elapsed = time.time() - start
        print(f"    ✓ ({elapsed:.2f}s)")

        return result

    def evaluate_batch(
        self,
        test_cases: list,
        start_idx: int = 0,
        end_idx: Optional[int] = None,
        output_file: Optional[str] = None
    ) -> pd.DataFrame:
        """批量评测"""
        if end_idx is None:
            end_idx = len(test_cases)

        results = []
        total = end_idx - start_idx

        print(f"\n{'='*60}")
        print(f"开始评测: {total} 条测试用例 (索引 {start_idx}-{end_idx-1})")
        print(f"{'='*60}")

        for i in range(start_idx, end_idx):
            test_case = test_cases[i]
            print(f"\n[{i+1}/{total}] ", end="")

            try:
                result = self.evaluate_single(test_case)
                results.append(result)
            except Exception as e:
                print(f"\n[ERROR] 测试用例 {i} 失败: {e}")
                # 添加错误记录
                results.append({
                    "评测方向": test_case.get("difficulty", ""),
                    "query": test_case.get("query", ""),
                    "预期结果": test_case.get("expected_answer", ""),
                    "mem0": f"[评测失败: {str(e)}]",
                    "mem0g": f"[评测失败: {str(e)}]",
                    "zep_graph": f"[评测失败: {str(e)}]",
                })

        # 保存结果
        df = pd.DataFrame(results)

        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"evaluation_results_{timestamp}.csv"

        # 同时保存CSV和Excel格式（如果支持）
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n{'='*60}")
        print(f"✅ 评测完成! 结果已保存至: {output_file}")
        print(f"{'='*60}")
        print(f"\n{'='*60}")
        print(f"✅ 评测完成! 结果已保存至: {output_file}")
        print(f"{'='*60}")

        return df


def load_test_cases(file_path: str) -> list:
    """加载测试用例"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("test_queries", [])


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Memory系统评测脚本")
    parser.add_argument("--start", type=int, default=0, help="起始测试用例索引")
    parser.add_argument("--end", type=int, default=None, help="结束测试用例索引（不包含）")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式（只测试前2条）")

    args = parser.parse_args()

    # 加载测试用例
    print(f"[Load] 加载测试用例: {TEST_QUERIES_FILE}")
    test_cases = load_test_cases(TEST_QUERIES_FILE)
    print(f"[Load] 共 {len(test_cases)} 条测试用例")

    # 试运行模式
    if args.dry_run:
        args.end = min(2, len(test_cases))
        print("[Mode] 试运行模式: 只测试前 2 条")

    # 初始化评测器
    evaluator = MemoryEvaluator()

    # 执行评测
    df = evaluator.evaluate_batch(
        test_cases=test_cases,
        start_idx=args.start,
        end_idx=args.end,
        output_file=args.output
    )

    # 打印摘要
    print(f"\n{'='*60}")
    print("评测摘要")
    print(f"{'='*60}")
    print(f"总测试数: {len(df)}")
    print(f"\n预览前5条结果:")
    print(df.head().to_string())


if __name__ == "__main__":
    main()
