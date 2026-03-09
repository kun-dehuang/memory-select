"""Debug logging configuration for memory operations.

This module provides detailed logging for:
- Fact extraction from text
- Entity/relationship extraction (graph)
- Memory comparison operations
- API calls and responses
- API request/response logging
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List
import json
import threading
from collections import deque


class DebugLogger:
    """Enhanced logger for debugging memory operations."""

    # Class-level storage for logs shared across all instances
    _api_logs: deque = deque(maxlen=1000)  # Store up to 1000 log entries
    _logs_lock = threading.Lock()

    def __init__(self, name: str = "memory_debug", log_dir: Optional[Path] = None):
        """Initialize debug logger.

        Args:
            name: Logger name
            log_dir: Directory to store log files (default: project_root/logs)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create log directory
        if log_dir is None:
            project_root = Path(__file__).parent.parent
            log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"debug_{timestamp}.log"

        # File handler - DEBUG level
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler - INFO level (less verbose)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Store log file path for reference
        self.log_file = log_file

        self.logger.info("=" * 80)
        self.logger.info(f"Debug logging initialized. Log file: {log_file}")
        self.logger.info("=" * 80)

    def log_input(self, context: str, data: Any):
        """Log input data with context.

        Args:
            context: Description of the input (e.g., "User input for fact extraction")
            data: The input data (will be JSON serialized if possible)
        """
        self.logger.debug(f"[INPUT] {context}")
        try:
            if isinstance(data, (dict, list)):
                self.logger.debug(f"  Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                self.logger.debug(f"  Data: {data}")
        except Exception as e:
            self.logger.debug(f"  Data: {data} (serialization error: {e})")

    def log_output(self, context: str, data: Any):
        """Log output data with context.

        Args:
            context: Description of the output (e.g., "Extracted facts")
            data: The output data (will be JSON serialized if possible)
        """
        self.logger.debug(f"[OUTPUT] {context}")
        try:
            if isinstance(data, (dict, list)):
                self.logger.debug(f"  Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                self.logger.debug(f"  Data: {data}")
        except Exception as e:
            self.logger.debug(f"  Data: {data} (serialization error: {e})")

    def log_fact_extraction(self, text: str, extracted_facts: Any, metadata: Dict = None):
        """Log fact extraction details.

        Args:
            text: Original input text
            extracted_facts: Extracted facts from mem0
            metadata: Additional metadata
        """
        self.logger.info("[FACT EXTRACTION]")
        self.logger.debug(f"  Input text: {text}")  # No truncation

        if extracted_facts:
            if isinstance(extracted_facts, dict):
                self.logger.debug(f"  Extracted facts (dict): {json.dumps(extracted_facts, ensure_ascii=False, indent=2)}")
            elif isinstance(extracted_facts, list):
                self.logger.debug(f"  Extracted facts (list, {len(extracted_facts)} items)")
                for i, fact in enumerate(extracted_facts):
                    self.logger.debug(f"    [{i}] {fact}")
            elif isinstance(extracted_facts, str):
                self.logger.debug(f"  Extracted fact: {extracted_facts}")
            else:
                self.logger.debug(f"  Extracted facts: {extracted_facts}")
        else:
            self.logger.warning("  No facts extracted!")

        if metadata:
            self.logger.debug(f"  Metadata: {json.dumps(metadata, ensure_ascii=False)}")

    def log_graph_extraction(self, entities: Any, relations: Any):
        """Log graph (entities/relations) extraction details.

        Args:
            entities: Extracted entities
            relations: Extracted relationships
        """
        self.logger.info("[GRAPH EXTRACTION]")

        if entities:
            if isinstance(entities, list):
                self.logger.debug(f"  Entities ({len(entities)}):")
                for i, entity in enumerate(entities[:10]):  # Limit to first 10
                    self.logger.debug(f"    [{i}] {entity}")
                if len(entities) > 10:
                    self.logger.debug(f"    ... and {len(entities) - 10} more")
            else:
                self.logger.debug(f"  Entities: {entities}")
        else:
            self.logger.debug("  No entities extracted")

        if relations:
            if isinstance(relations, list):
                self.logger.debug(f"  Relations ({len(relations)}):")
                for i, rel in enumerate(relations[:10]):  # Limit to first 10
                    self.logger.debug(f"    [{i}] {rel}")
                if len(relations) > 10:
                    self.logger.debug(f"    ... and {len(relations) - 10} more")
            else:
                self.logger.debug(f"  Relations: {relations}")
        else:
            self.logger.debug("  No relations extracted")

    def log_comparison(self, query: str, existing_memories: Any, new_memory: str,
                      comparison_result: Any):
        """Log memory comparison/deduplication details.

        Args:
            query: Search query used for comparison
            existing_memories: Existing memories found
            new_memory: New memory being compared
            comparison_result: Result of comparison (duplicate/similar/new)
        """
        self.logger.info("[COMPARISON]")
        self.logger.debug(f"  Query: {query}")
        self.logger.debug(f"  New memory: {new_memory}")  # No truncation

        if existing_memories:
            if isinstance(existing_memories, list):
                self.logger.debug(f"  Existing memories found: {len(existing_memories)}")
                for i, mem in enumerate(existing_memories):  # Show all
                    if isinstance(mem, dict):
                        self.logger.debug(f"    [{i}] score={mem.get('score', 'N/A')}: {mem.get('memory', str(mem))}")  # No truncation
                    else:
                        self.logger.debug(f"    [{i}] {str(mem)}")  # No truncation
            else:
                self.logger.debug(f"  Existing memories: {existing_memories}")
        else:
            self.logger.debug("  No existing memories found")

        self.logger.debug(f"  Comparison result: {comparison_result}")

    def log_api_call(self, api_name: str, endpoint: str, request_data: Any,
                    response_data: Any, duration_ms: float = None):
        """Log API call details.

        Args:
            api_name: Name of the API (e.g., "Gemini LLM")
            endpoint: API endpoint or method
            request_data: Request data sent
            response_data: Response data received
            duration_ms: Request duration in milliseconds
        """
        self.logger.debug(f"[API CALL] {api_name} - {endpoint}")
        if duration_ms is not None:
            self.logger.debug(f"  Duration: {duration_ms:.2f}ms")

        try:
            if request_data:
                req_str = json.dumps(request_data, ensure_ascii=False, indent=2)
                # No truncation - log full request
                self.logger.debug(f"  Request: {req_str}")

            if response_data:
                resp_str = json.dumps(response_data, ensure_ascii=False, indent=2)
                # No truncation - log full response
                self.logger.debug(f"  Response: {resp_str}")
        except Exception as e:
            self.logger.debug(f"  Request/Response: (serialization error: {e})")

    def log_error(self, context: str, error: Exception, traceback_str: str = None):
        """Log error with context.

        Args:
            context: Description of what was being done
            error: The exception
            traceback_str: Optional traceback string
        """
        self.logger.error(f"[ERROR] {context}: {type(error).__name__}: {error}")
        if traceback_str:
            self.logger.debug(f"  Traceback:\n{traceback_str}")

    def log_indexing_progress(self, system: str, current: int, total: int,
                             record_data: Dict = None):
        """Log indexing progress.

        Args:
            system: System name (e.g., "Mem0 Graph")
            current: Current record number
            total: Total records
            record_data: Optional record data being indexed
        """
        self.logger.info(f"[INDEXING] {system}: {current}/{total} ({current*100//total if total > 0 else 0}%)")
        if record_data and self.logger.isEnabledFor(logging.DEBUG):
            # Only log record data in DEBUG mode to avoid too much output
            text = record_data.get("text", "")[:100]
            uid = record_data.get("uid", "")
            self.logger.debug(f"  Record uid={uid}, text={text}...")

    def log_search(self, query: str, system: str, results: Any, filters: Dict = None):
        """Log search operation.

        Args:
            query: Search query
            system: System name
            results: Search results
            filters: Optional filters applied
        """
        self.logger.info(f"[SEARCH] {system} - query: '{query}'")
        if filters:
            self.logger.debug(f"  Filters: {filters}")

        if results:
            if isinstance(results, list):
                self.logger.debug(f"  Results: {len(results)} items")
                for i, r in enumerate(results[:5]):
                    self.logger.debug(f"    [{i}] {r}")
            else:
                self.logger.debug(f"  Results: {results}")
        else:
            self.logger.debug("  No results found")

    def log_api_request(
        self,
        endpoint: str,
        method: str = "POST",
        uid: str = None,
        request_data: Dict = None,
        **kwargs
    ):
        """Log API request details and store in memory for API querying.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            uid: User ID
            request_data: Request body data
            **kwargs: Additional request parameters
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "api_request",
            "level": "INFO",
            "endpoint": endpoint,
            "method": method,
            "uid": uid,
            "request_data": DebugLogger._sanitize_for_logging(request_data),
        }
        log_entry.update(kwargs)

        self.logger.info(f"[API REQUEST] {method} {endpoint}")
        if uid:
            self.logger.info(f"  User: {uid}")
        if request_data:
            # Log request body at INFO level to show in console
            self.logger.info(f"  Request: {json.dumps(request_data, ensure_ascii=False, indent=2)}")

        self._store_log(log_entry)

    def log_api_response(
        self,
        endpoint: str,
        status: str = "success",
        response_data: Dict = None,
        duration_ms: float = None,
        error: str = None,
        **kwargs
    ):
        """Log API response details and store in memory for API querying.

        Args:
            endpoint: API endpoint path
            status: Response status ('success' or 'error')
            response_data: Response data
            duration_ms: Request duration in milliseconds
            error: Error message if status is 'error'
            **kwargs: Additional response parameters
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "api_response",
            "level": "ERROR" if status == "error" else "INFO",
            "endpoint": endpoint,
            "status": status,
            "response_data": DebugLogger._sanitize_for_logging(response_data),
            "duration_ms": duration_ms,
            "error": error,
        }
        log_entry.update(kwargs)

        if status == "error":
            self.logger.error(f"[API RESPONSE] {endpoint} - ERROR: {error}")
        else:
            self.logger.info(f"[API RESPONSE] {endpoint} - SUCCESS")
            if duration_ms is not None:
                self.logger.info(f"  Duration: {duration_ms:.2f}ms")
            if response_data:
                self.logger.debug(f"  Response: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

        self._store_log(log_entry)

    def log_fact_split(self, text: str, facts: list, entities: list = None, relations: list = None):
        """Log fact extraction and split results from mem0 add operation.

        Args:
            text: Original input text
            facts: List of extracted facts
            entities: List of extracted entities (from graph)
            relations: List of extracted relations (from graph)
        """
        self.logger.info("[FACT SPLIT]")
        self.logger.info(f"  Input: {text}")

        if facts:
            self.logger.info(f"  Facts extracted: {len(facts)}")
            for i, fact in enumerate(facts):
                self.logger.debug(f"    [{i}] {fact}")
        else:
            self.logger.warning("  No facts extracted")

        if entities:
            self.logger.info(f"  Entities extracted: {len(entities)}")
            for i, entity in enumerate(entities[:10]):
                self.logger.debug(f"    [{i}] {entity}")
        else:
            self.logger.debug("  No entities extracted")

        if relations:
            self.logger.info(f"  Relations extracted: {len(relations)}")
            for i, rel in enumerate(relations[:10]):
                self.logger.debug(f"    [{i}] {rel}")
        else:
            self.logger.debug("  No relations extracted")

        # Store in memory for API querying
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "fact_split",
            "level": "INFO",
            "input_text": text[:500],  # Limit stored text length
            "facts": facts,
            "entities": entities[:20] if entities else [],  # Limit stored entities
            "relations": relations[:20] if relations else [],  # Limit stored relations
        }
        self._store_log(log_entry)

    def log_search_results(self, query: str, results: list, relations: list = None, **kwargs):
        """Log search results with full details for API querying.

        Args:
            query: Search query
            results: Raw search results with all fields
            relations: Graph relations returned
            **kwargs: Additional search parameters
        """
        self.logger.info("[SEARCH RESULTS]")
        self.logger.info(f"  Query: {query}")
        self.logger.info(f"  Results count: {len(results)}")

        for i, r in enumerate(results[:5]):
            if isinstance(r, dict):
                self.logger.debug(f"    [{i}] score={r.get('score', 'N/A')}: {r.get('content', str(r))}")
            else:
                self.logger.debug(f"    [{i}] {r}")

        if relations:
            self.logger.info(f"  Relations count: {len(relations)}")
            for i, rel in enumerate(relations[:5]):
                self.logger.debug(f"    [{i}] {rel}")

        # Store in memory for API querying
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "search_results",
            "level": "INFO",
            "query": query,
            "results_count": len(results),
            "results": results[:10],  # Limit stored results
            "relations": relations[:20] if relations else [],  # Limit stored relations
        }
        log_entry.update(kwargs)
        self._store_log(log_entry)

    @staticmethod
    def _sanitize_for_logging(data: Any) -> Any:
        """Sanitize data for logging (remove sensitive fields, limit sizes).

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data
        """
        if not data:
            return data

        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Skip sensitive fields
                if key.lower() in ["api_key", "password", "token", "secret"]:
                    sanitized[key] = "***"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = DebugLogger._sanitize_for_logging(value)
                elif isinstance(value, str) and len(value) > 1000:
                    sanitized[key] = value[:1000] + "... (truncated)"
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [DebugLogger._sanitize_for_logging(item) for item in data[:100]]  # Limit list size
        elif isinstance(data, str) and len(data) > 1000:
            return data[:1000] + "... (truncated)"
        return data

    def _store_log(self, log_entry: Dict):
        """Store log entry in memory for API querying.

        Args:
            log_entry: Log entry dictionary
        """
        with self._logs_lock:
            self._api_logs.append(log_entry)

    @classmethod
    def get_recent_logs(
        cls,
        level: str = None,
        limit: int = 100,
        search: str = None,
        log_type: str = None
    ) -> List[Dict]:
        """Get recent logs from memory storage.

        Args:
            level: Filter by log level (INFO, DEBUG, ERROR)
            limit: Maximum number of logs to return (default 100)
            search: Search keyword filter
            log_type: Filter by log type (api_request, api_response, fact_split, search_results)

        Returns:
            List of log entries
        """
        with cls._logs_lock:
            logs = list(cls._api_logs)

        # Apply filters
        if level:
            logs = [log for log in logs if log.get("level") == level.upper()]
        if log_type:
            logs = [log for log in logs if log.get("type") == log_type]
        if search:
            search_lower = search.lower()
            logs = [
                log for log in logs
                if search_lower in json.dumps(log, ensure_ascii=False).lower()
            ]

        # Sort by timestamp descending and limit
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]

    @classmethod
    def clear_logs(cls):
        """Clear all stored logs from memory."""
        with cls._logs_lock:
            cls._api_logs.clear()


# Global logger instance
_global_logger: Optional[DebugLogger] = None


def get_debug_logger(force_new: bool = False) -> DebugLogger:
    """Get the global debug logger instance.

    Args:
        force_new: If True, create a new logger instance with a new log file.
                   This is useful for generating separate logs for each operation.
    """
    global _global_logger
    if _global_logger is None or force_new:
        _global_logger = DebugLogger()
    return _global_logger


def setup_logging(log_level: str = "INFO"):
    """Setup standard logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Set specific loggers
    logging.getLogger("mem0").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Initialize logging on import
setup_logging("DEBUG")
