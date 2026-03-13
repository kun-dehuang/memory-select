import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_fake_mem0() -> None:
    for name in list(sys.modules):
        if name == "mem0" or name.startswith("mem0."):
            sys.modules.pop(name)

    mem0_module = types.ModuleType("mem0")
    configs_module = types.ModuleType("mem0.configs")
    configs_base_module = types.ModuleType("mem0.configs.base")
    embeddings_module = types.ModuleType("mem0.embeddings")
    embeddings_configs_module = types.ModuleType("mem0.embeddings.configs")
    memory_module = types.ModuleType("mem0.memory")
    graph_memory_module = types.ModuleType("mem0.memory.graph_memory")
    llms_module = types.ModuleType("mem0.llms")
    llms_base_module = types.ModuleType("mem0.llms.base")
    llms_gemini_module = types.ModuleType("mem0.llms.gemini")

    class FakeConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeMemory:
        def __init__(self, config=None):
            self.config = config
            self.enable_graph = False
            self.graph = None

        def close(self):
            return None

    class FakeAsyncMemory:
        def __init__(self, config=None):
            self.config = config

        def close(self):
            return None

    class FakeMemoryGraph:
        def _remove_spaces_from_entities(self, entity_list):
            return entity_list

    class FakeLLMBase:
        def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
            return {"content": None, "tool_calls": []}

    class FakeGeminiLLM:
        def _parse_response(self, response, tools):
            if tools:
                return {"content": None, "tool_calls": []}
            return ""

    mem0_module.Memory = FakeMemory
    mem0_module.AsyncMemory = FakeAsyncMemory
    mem0_module.configs = configs_module
    mem0_module.embeddings = embeddings_module
    mem0_module.memory = memory_module
    mem0_module.llms = llms_module

    configs_base_module.MemoryConfig = FakeConfig
    configs_base_module.VectorStoreConfig = FakeConfig
    configs_base_module.GraphStoreConfig = FakeConfig
    configs_base_module.LlmConfig = FakeConfig
    embeddings_configs_module.EmbedderConfig = FakeConfig

    graph_memory_module.MemoryGraph = FakeMemoryGraph
    memory_module.graph_memory = graph_memory_module

    llms_base_module.LLMBase = FakeLLMBase
    llms_gemini_module.GeminiLLM = FakeGeminiLLM
    llms_module.base = llms_base_module
    llms_module.gemini = llms_gemini_module

    sys.modules["mem0"] = mem0_module
    sys.modules["mem0.configs"] = configs_module
    sys.modules["mem0.configs.base"] = configs_base_module
    sys.modules["mem0.embeddings"] = embeddings_module
    sys.modules["mem0.embeddings.configs"] = embeddings_configs_module
    sys.modules["mem0.memory"] = memory_module
    sys.modules["mem0.memory.graph_memory"] = graph_memory_module
    sys.modules["mem0.llms"] = llms_module
    sys.modules["mem0.llms.base"] = llms_base_module
    sys.modules["mem0.llms.gemini"] = llms_gemini_module


_install_fake_mem0()
import core.mem0_wrapper as mem0_wrapper  # noqa: E402
import api.routes.memory as memory_routes  # noqa: E402
from api.schemas.requests import SearchWithAnswerRequest  # noqa: E402
from models import SearchResult  # noqa: E402

mem0_wrapper = importlib.reload(mem0_wrapper)
memory_routes = importlib.reload(memory_routes)


def _fake_debug_logger():
    sink = lambda *args, **kwargs: None
    return SimpleNamespace(
        logger=SimpleNamespace(info=sink, debug=sink, warning=sink, error=sink),
        log_api_call=sink,
        log_error=sink,
        log_input=sink,
        log_output=sink,
    )


class MemorySearchStabilityTests(unittest.TestCase):
    def test_gemini_tool_parse_never_returns_none_content(self):
        llm = mem0_wrapper.mem0_gemini.GeminiLLM()
        parsed = llm._parse_response(response=object(), tools=[{"function": {"name": "extract_entities"}}])

        self.assertEqual(parsed["content"], "")
        self.assertEqual(parsed["tool_calls"], [])

    def test_mem0_graph_search_skips_internal_memory_search(self):
        instance = object.__new__(mem0_wrapper.Mem0Graph)
        instance.user_id = "user-1"
        instance._sync_client = SimpleNamespace(
            _search_vector_store=MagicMock(return_value=[
                {"id": "m1", "memory": "alpha", "score": 0.9, "metadata": {"timestamp": 10}}
            ]),
            search=MagicMock(side_effect=AssertionError("Memory.search should not be called")),
            enable_graph=True,
            graph=SimpleNamespace(search=MagicMock(return_value=[
                {"source": "alice", "relationship": "likes", "destination": "tea"}
            ])),
        )

        with patch.object(mem0_wrapper, "_get_debug_logger", return_value=_fake_debug_logger()):
            results = instance.search(query="alpha", limit=1, uid="user-1")

        instance._sync_client.search.assert_not_called()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "alpha")
        self.assertEqual(results[0].graph_relations[0].source, "alice")

    def test_graph_search_refreshes_sync_client_once_on_broken_pipe(self):
        first_client = SimpleNamespace(
            _search_vector_store=MagicMock(return_value=[
                {"id": "m1", "memory": "alpha", "score": 0.9, "metadata": {}}
            ]),
            enable_graph=True,
            graph=SimpleNamespace(search=MagicMock(side_effect=BrokenPipeError("Broken pipe"))),
        )
        second_client = SimpleNamespace(
            _search_vector_store=MagicMock(return_value=[
                {"id": "m1", "memory": "alpha", "score": 0.9, "metadata": {}}
            ]),
            enable_graph=True,
            graph=SimpleNamespace(search=MagicMock(return_value=[
                {"source": "alice", "relationship": "likes", "destination": "tea"}
            ])),
        )

        instance = object.__new__(mem0_wrapper.Mem0Graph)
        instance.user_id = "user-1"
        instance._sync_client = first_client

        def refresh_client():
            instance._sync_client = second_client

        instance._refresh_sync_client = MagicMock(side_effect=refresh_client)

        with patch.object(mem0_wrapper, "_get_debug_logger", return_value=_fake_debug_logger()):
            results, graph_info = instance._search_with_graph_context(query="alpha", limit=1, uid="user-1")

        instance._refresh_sync_client.assert_called_once()
        self.assertEqual(graph_info["graph_status"], "ok")
        self.assertEqual(graph_info["graph_retry_count"], 1)
        self.assertEqual(results[0].graph_relations[0].destination, "tea")

    def test_graph_search_degrades_after_retry_failure(self):
        first_client = SimpleNamespace(
            _search_vector_store=MagicMock(return_value=[
                {"id": "m1", "memory": "alpha", "score": 0.9, "metadata": {}}
            ]),
            enable_graph=True,
            graph=SimpleNamespace(search=MagicMock(side_effect=BrokenPipeError("Broken pipe"))),
        )
        second_client = SimpleNamespace(
            _search_vector_store=MagicMock(return_value=[
                {"id": "m1", "memory": "alpha", "score": 0.9, "metadata": {}}
            ]),
            enable_graph=True,
            graph=SimpleNamespace(search=MagicMock(side_effect=RuntimeError("graph extraction failed"))),
        )

        instance = object.__new__(mem0_wrapper.Mem0Graph)
        instance.user_id = "user-1"
        instance._sync_client = first_client

        def refresh_client():
            instance._sync_client = second_client

        instance._refresh_sync_client = MagicMock(side_effect=refresh_client)

        with patch.object(mem0_wrapper, "_get_debug_logger", return_value=_fake_debug_logger()):
            results, graph_info = instance._search_with_graph_context(query="alpha", limit=1, uid="user-1")

        self.assertEqual(graph_info["graph_status"], "degraded")
        self.assertEqual(graph_info["graph_retry_count"], 1)
        self.assertIn("graph extraction failed", graph_info["graph_error"])
        self.assertEqual(results[0].graph_relations, [])


class MemorySearchRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_with_answer_returns_200_shape_when_graph_is_degraded(self):
        fake_memory = SimpleNamespace()
        fake_memory.search_with_answer = MagicMock(return_value={
            "answer": "Based on memory, alpha is relevant.",
            "memories": ["alpha"],
            "relations": [],
            "raw_results": [
                SearchResult(
                    memory_id="m1",
                    content="alpha",
                    score=0.9,
                    metadata={},
                    graph_relations=[],
                )
            ],
            "timings": {
                "search": 1.0,
                "llm": 2.0,
                "core_total": 3.0,
                "graph_status": "degraded",
                "graph_retry_count": 1,
                "graph_error": "Broken pipe",
            },
        })
        request = SearchWithAnswerRequest(query="alpha", limit=1, uid="user-1")
        raw_request = SimpleNamespace(state=SimpleNamespace(request_start_time=0.0))

        dummy_logger = SimpleNamespace(
            log_api_request=lambda **kwargs: None,
            log_search_results=lambda **kwargs: None,
            log_api_response=lambda **kwargs: None,
        )

        with patch.object(memory_routes, "get_memory_instance", return_value=fake_memory), \
             patch.object(memory_routes, "run_in_thread_pool", AsyncMock(return_value=(fake_memory.search_with_answer(), 0.0))), \
             patch.object(memory_routes, "debug_logger", dummy_logger):
            response = await memory_routes.search_with_answer(request, raw_request)

        self.assertEqual(response.answer, "Based on memory, alpha is relevant.")
        self.assertEqual(response.relations, [])
        self.assertEqual(response.raw_results[0].graph_relations, [])
        self.assertEqual(response.timings["server"]["graph_status"], "degraded")
        self.assertEqual(response.timings["server"]["graph_retry_count"], 1)
        self.assertEqual(response.timings["server"]["graph_error"], "Broken pipe")


if __name__ == "__main__":
    unittest.main()
