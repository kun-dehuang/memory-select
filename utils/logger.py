"""Debug logging configuration for memory operations.

This module provides detailed logging for:
- Fact extraction from text
- Entity/relationship extraction (graph)
- Memory comparison operations
- API calls and responses
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import json


class DebugLogger:
    """Enhanced logger for debugging memory operations."""

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
