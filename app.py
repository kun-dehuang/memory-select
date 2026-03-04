"""Memory Comparison Tool - Streamlit Application.

Supports user-isolated memory storage where each user has independent
storage space (separate collections/sessions).

Data persistence:
- Zep: Cloud storage (auto-persisted)
- Mem0 Standard: Qdrant Docker volume (auto-persisted)
- Mem0 Graph: Neo4j Docker volume (auto-persisted)
"""

import asyncio
import json
import os
import time
from io import BytesIO
from typing import Optional, Dict, List
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

from config import config
from models import SearchResult, ComparisonResult
from core import Mem0Standard, Mem0Graph, ZepMemory, ZepGraph
from utils import load_json_file, parse_memory_records, validate_data_format, get_unique_users, get_debug_logger

# Data storage paths
DATA_DIR = Path(config.data_dir)
USER_META_FILE = DATA_DIR / "users_meta.json"

# Page configuration
st.set_page_config(
    page_title="Memory Comparison Tool",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .result-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def save_users_meta():
    """Save users metadata (user list + stats + indexed systems) to disk."""
    try:
        DATA_DIR.mkdir(exist_ok=True)

        # Build indexed systems info per user
        indexed_systems = {}
        for uid, instances in st.session_state.user_instances.items():
            systems = []
            # Check which systems have valid (non-error) instances
            if "mem0_standard" in instances and not isinstance(instances["mem0_standard"], str):
                try:
                    count = instances["mem0_standard"].count()
                    if count > 0:
                        systems.append("Mem0 Standard")
                except:
                    pass
            if "mem0_graph" in instances and not isinstance(instances["mem0_graph"], str):
                try:
                    count = instances["mem0_graph"].count()
                    if count > 0:
                        systems.append("Mem0 Graph")
                except:
                    pass
            if "zep_memory" in instances and not isinstance(instances["zep_memory"], str):
                try:
                    count = instances["zep_memory"].count()
                    if count > 0:
                        systems.append("Zep Memory")
                except:
                    pass
            if "zep_graph" in instances and not isinstance(instances["zep_graph"], str):
                try:
                    count = instances["zep_graph"].count()
                    if count > 0:
                        systems.append("Zep Graph")
                except:
                    pass
            indexed_systems[uid] = systems

        meta = {
            "users": st.session_state.available_users,
            "indexed_systems": indexed_systems,
            "stats": {
                uid: {
                    "record_count": len(st.session_state.user_data_store.get(uid, [])),
                }
                for uid in st.session_state.available_users
            }
        }
        with open(USER_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass


def load_users_meta() -> tuple[List[str], Dict, Dict]:
    """Load users metadata from disk on startup.

    Also auto-detects indexed systems from storage to handle old format.
    """
    try:
        if USER_META_FILE.exists():
            with open(USER_META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                users = meta.get("users", [])
                stats = meta.get("stats", {})
                indexed_systems = meta.get("indexed_systems", {})

                # Auto-detect indexed systems for users who don't have it recorded
                for user_id in users:
                    if user_id not in indexed_systems or not indexed_systems[user_id]:
                        # Check storage and update
                        systems = _detect_indexed_systems(user_id)
                        if systems:
                            indexed_systems[user_id] = systems

                # Save updated meta if we auto-detected
                if indexed_systems != meta.get("indexed_systems", {}):
                    meta["indexed_systems"] = indexed_systems
                    with open(USER_META_FILE, 'w', encoding='utf-8') as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)

                return users, stats, indexed_systems
    except Exception as e:
        pass
    return [], {}, {}


def _detect_indexed_systems(user_id: str) -> List[str]:
    """Detect which memory systems have indexed data for a user."""
    indexed = []

    # Check Mem0 Standard
    try:
        from core.mem0_wrapper import Mem0Standard
        mem0_std = Mem0Standard(collection_name=f"memory_store_{user_id}")
        if mem0_std.count() > 0:
            indexed.append("Mem0 Standard")
    except:
        pass

    # Check Mem0 Graph
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        with driver.session() as session:
            result = session.run("MATCH (m:Memory {uid: $uid}) RETURN count(m) as count", uid=user_id)
            if result.single()["count"] > 0:
                indexed.append("Mem0 Graph")
        driver.close()
    except:
        pass

    # Check Zep
    try:
        from core.zep_wrapper import ZepMemory
        zep_mem = ZepMemory(user_id=user_id)
        if zep_mem.count() > 0:
            indexed.append("Zep Memory")
            indexed.append("Zep Graph")  # Same thread
    except:
        pass

    return indexed


def discover_stored_users() -> List[str]:
    """Discover users from persistent storage systems.

    Checks:
    - Qdrant collections (pattern: memory_store_{user_id})
    - Neo4j (distinct uid values)
    """
    discovered = set()

    # Discover from Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            host=config.mem0.qdrant_host,
            port=int(config.mem0.qdrant_port),
            prefer_grpc=False,
            check_compatibility=False
        )
        collections = client.get_collections().collections
        for coll in collections:
            if coll.name.startswith("memory_store_"):
                user_id = coll.name.replace("memory_store_", "")
                discovered.add(user_id)
    except Exception:
        pass

    # Discover from Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        with driver.session() as session:
            result = session.run("MATCH (m:Memory) RETURN DISTINCT m.uid as uid")
            for record in result:
                if record["uid"]:
                    discovered.add(record["uid"])
        driver.close()
    except Exception:
        pass

    return list(discovered)


def delete_user_from_storage(user_id: str):
    """Delete user data from all storage systems.

    Args:
        user_id: User ID to delete
    """
    # Delete from Qdrant (drop collection)
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            host=config.mem0.qdrant_host,
            port=int(config.mem0.qdrant_port),
            prefer_grpc=False,
            check_compatibility=False
        )
        collection_name = f"memory_store_{user_id}"
        client.delete_collection(collection_name)
    except Exception:
        pass

    # Delete from Neo4j (delete nodes with this uid)
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        with driver.session() as session:
            session.run("MATCH (m:Memory {uid: $uid}) DETACH DELETE m", uid=user_id)
        driver.close()
    except Exception:
        pass

    # Delete from Zep (delete session and user)
    try:
        from zep_python.client import Zep
        client = Zep(
            api_key=config.zep.api_key,
            base_url=config.zep.api_url
        )
        # Delete all sessions for this user first
        try:
            user_sessions = client.user.get_sessions(user_id)
            if user_sessions and user_sessions.sessions:
                for session in user_sessions.sessions:
                    client.memory.delete(session.session_id)
        except:
            pass

        # Delete session (backward compatibility)
        try:
            session_id = f"session_{user_id}"
            client.memory.delete(session_id)
        except:
            pass

        # Delete the user
        try:
            client.user.delete(user_id)
        except:
            pass
    except Exception:
        pass


def init_session_state():
    """Initialize session state variables and discover users."""
    # Load persisted users metadata
    persisted_users, stats, indexed_systems = load_users_meta()

    # Discover users from storage systems
    discovered_users = discover_stored_users()

    # Merge users
    all_users = list(set(persisted_users + discovered_users))

    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = bool(all_users)
    if "current_data" not in st.session_state:
        st.session_state.current_data = []
    if "available_users" not in st.session_state:
        st.session_state.available_users = all_users
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = all_users[0] if all_users else None
    if "user_data_store" not in st.session_state:
        # Store temporarily uploaded data: {user_id: [records]}
        # This is NOT persisted - data lives in Zep/Qdrant/Neo4j
        st.session_state.user_data_store = {}
    if "user_instances" not in st.session_state:
        # Store memory instances per user: {user_id: {system: instance}}
        st.session_state.user_instances = {}
    if "selected_systems" not in st.session_state:
        st.session_state.selected_systems = ["Mem0 Standard", "Mem0 Graph", "Zep Memory", "Zep Graph"]
    # For search: support all 4 systems
    if "search_systems" not in st.session_state:
        st.session_state.search_systems = ["Mem0 Standard", "Mem0 Graph", "Zep Memory", "Zep Graph"]
    if "indexed_systems" not in st.session_state:
        # Track which systems have been indexed for each user
        st.session_state.indexed_systems = indexed_systems


def get_storage_stats(user_id: str) -> Dict[str, int]:
    """Get actual data count from storage systems for a user."""
    stats = {}

    # Check Mem0 Standard (Qdrant)
    try:
        from core.mem0_wrapper import Mem0Standard
        mem0_std = Mem0Standard(collection_name=f"memory_store_{user_id}")
        stats["Mem0 Standard"] = mem0_std.count()
    except:
        stats["Mem0 Standard"] = 0

    # Check Mem0 Graph (Neo4j)
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        with driver.session() as session:
            result = session.run("MATCH (m:Memory {uid: $uid}) RETURN count(m) as count", uid=user_id)
            stats["Mem0 Graph"] = result.single()["count"]
        driver.close()
    except:
        stats["Mem0 Graph"] = 0

    # Check Zep Memory/Graph (shared thread)
    try:
        from core.zep_wrapper import ZepMemory
        zep_mem = ZepMemory(user_id=user_id)
        count = zep_mem.count()
        stats["Zep Memory"] = count
        stats["Zep Graph"] = count  # Same thread
    except:
        stats["Zep Memory"] = 0
        stats["Zep Graph"] = 0

    return stats


def sidebar():
    """Render sidebar with configuration."""
    st.sidebar.title("⚙️ Configuration")

    # User selection section (at the top)
    st.sidebar.subheader("👤 User Selection")

    if st.session_state.available_users:
        current_idx = 0
        if st.session_state.selected_user in st.session_state.available_users:
            current_idx = st.session_state.available_users.index(st.session_state.selected_user)

        selected = st.sidebar.selectbox(
            "Select User",
            st.session_state.available_users,
            index=current_idx,
            key="user_selector"
        )
        st.session_state.selected_user = selected

        # Show indexed systems for this user
        indexed_systems = st.session_state.indexed_systems.get(selected, [])
        if indexed_systems:
            st.sidebar.success(f"✅ Indexed: {', '.join(indexed_systems)}")
        else:
            st.sidebar.info("⏳ Not indexed yet")

        # Show data stats from storage
        storage_stats = get_storage_stats(selected)
        if storage_stats:
            st.sidebar.caption("📊 Storage stats:")
            for system, count in storage_stats.items():
                if count > 0:
                    st.sidebar.caption(f"   • {system}: {count} records")

        # Show user stats from uploaded data
        if selected in st.session_state.user_data_store:
            user_records = st.session_state.user_data_store[selected]
            st.sidebar.caption(f"📁 Uploaded: {len(user_records)} records")
    else:
        st.sidebar.info("📤 Upload data to add users")

    st.sidebar.markdown("---")

    # Data upload section
    st.sidebar.subheader("📁 Data Upload")

    uploaded_file = st.sidebar.file_uploader(
        "Upload JSON file",
        type=["json"],
        help="Upload memory data in JSON format. Each file should contain data for one user."
    )

    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            is_valid, msg = validate_data_format(data)

            if is_valid:
                # Check if data is phase1_events format and convert it
                if data and isinstance(data[0], dict):
                    first_record = data[0]
                    if "event_id" in first_record and "activity" in first_record:
                        # Convert phase1_events to standard format
                        from utils import DataProcessor
                        processor = DataProcessor.from_data(data, user_id="ouyang_bingjie")
                        records = processor.process()

                        # Convert MemoryRecord objects to dict format for import
                        converted_data = [
                            {
                                "uid": r.uid,
                                "text": r.text,
                                "meta": {
                                    "timestamp": r.timestamp,
                                    "category": r.category,
                                    **r.metadata
                                }
                            }
                            for r in records
                        ]
                        data = converted_data
                        st.sidebar.info("📋 Phase1 Events format detected and converted")

                # Extract users from data
                users = get_unique_users(data)

                if len(users) == 0:
                    st.sidebar.error("❌ No user ID (uid) found in data")
                elif len(users) == 1:
                    user_id = users[0]
                    st.session_state.user_data_store[user_id] = data

                    # Update available users list
                    if user_id not in st.session_state.available_users:
                        st.session_state.available_users.append(user_id)

                    # Auto-select this user
                    if not st.session_state.selected_user:
                        st.session_state.selected_user = user_id

                    # Save to disk
                    save_users_meta()
                    st.sidebar.success(f"✅ User '{user_id}': {len(data)} records ready to index")
                else:
                    # Multiple users in one file - split them
                    for user_id in users:
                        user_data = [r for r in data if r.get("uid") == user_id]
                        st.session_state.user_data_store[user_id] = user_data

                        if user_id not in st.session_state.available_users:
                            st.session_state.available_users.append(user_id)

                    # Save to disk
                    save_users_meta()
                    st.sidebar.success(f"✅ {len(users)} users ready to index")

                st.session_state.data_loaded = True

                # Show data summary
                with st.sidebar.expander("📊 Data Summary"):
                    for uid in users:
                        count = len([r for r in data if r.get("uid") == uid])
                        st.write(f"**{uid}:** {count} records")
            else:
                st.sidebar.error(f"❌ {msg}")

        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")

    # Data management section
    if st.session_state.available_users:
        st.sidebar.markdown("---")
        st.sidebar.subheader("💾 Data Management")

        # Delete specific user data from storage systems
        user_to_delete = st.sidebar.selectbox(
            "Delete user from storage",
            ["-- Select --"] + st.session_state.available_users,
            key="delete_user_select"
        )

        if user_to_delete != "-- Select --":
            if st.sidebar.button("🗑️ Delete & Clear", use_container_width=True, key="delete_user_btn"):
                # Clear from memory systems
                delete_user_from_storage(user_to_delete)

                # Remove from session
                if user_to_delete in st.session_state.user_data_store:
                    del st.session_state.user_data_store[user_to_delete]
                if user_to_delete in st.session_state.available_users:
                    st.session_state.available_users.remove(user_to_delete)
                if user_to_delete in st.session_state.user_instances:
                    del st.session_state.user_instances[user_to_delete]

                # Select another user if available
                if st.session_state.selected_user == user_to_delete:
                    st.session_state.selected_user = (
                        st.session_state.available_users[0]
                        if st.session_state.available_users
                        else None
                    )

                save_users_meta()
                st.sidebar.success(f"✅ Deleted '{user_to_delete}' from all storage")
                st.rerun()

        # Delete all data
        if st.sidebar.button("🗑️ Delete All Users", use_container_width=True):
            for user_id in st.session_state.available_users:
                delete_user_from_storage(user_id)

            st.session_state.user_data_store = {}
            st.session_state.available_users = []
            st.session_state.selected_user = None
            st.session_state.user_instances = {}
            st.session_state.data_loaded = False

            # Delete metadata file
            if USER_META_FILE.exists():
                USER_META_FILE.unlink()

            st.sidebar.success("✅ All users deleted from storage")
            st.rerun()

    st.sidebar.markdown("---")

    st.sidebar.subheader("📊 Index Storage Type")

    if "index_systems" not in st.session_state:
        # Index systems: can include both Memory and Graph systems
        st.session_state.index_systems = ["Mem0 Graph", "Zep Graph"]

    st.session_state.index_systems = st.sidebar.multiselect(
        "Select storage types to index",
        ["Mem0 Standard", "Mem0 Graph", "Zep Memory", "Zep Graph"],
        default=st.session_state.index_systems,
        key="index_system_selector"
    )

    st.sidebar.subheader("� Actions")

    col1, col2, col3 = st.sidebar.columns(3)

    with col1:
        if st.button("Index", use_container_width=True):
            with st.spinner("Indexing data..."):
                index_user_data()

    with col2:
        if st.button("Clear", use_container_width=True):
            clear_user_data()

    with col3:
        if st.button("Reset All", use_container_width=True):
            reset_all_data()


def get_user_instances(user_id: str, systems: Optional[List[str]] = None) -> Dict:
    """Get or create memory system instances for a specific user.
    
    Args:
        user_id: User ID
        systems: List of systems to initialize. If None, initialize all systems.
    """
    if user_id not in st.session_state.user_instances:
        st.session_state.user_instances[user_id] = {}

    instances = st.session_state.user_instances[user_id]
    results = {}
    
    if systems is None:
        systems = ["Mem0 Standard", "Mem0 Graph", "Zep Memory", "Zep Graph"]

    if "Mem0 Standard" in systems:
        if "mem0_standard" not in instances:
            try:
                instances["mem0_standard"] = Mem0Standard(
                    user_id=user_id,
                    collection_name=f"memory_store_{user_id}"
                )
                print(f"[Init] Created Mem0Standard for {user_id}")
            except Exception as e:
                import traceback
                instances["mem0_standard"] = f"❌ Error: {str(e)}"
                print(f"[Init] Mem0Standard ERROR: {str(e)}")
                print(traceback.format_exc())
        results["Mem0 Standard"] = instances.get("mem0_standard")

    if "Mem0 Graph" in systems:
        if "mem0_graph" not in instances:
            try:
                instances["mem0_graph"] = Mem0Graph(
                    collection_name=f"memory_store_{user_id}",
                    user_id=user_id
                )
                print(f"[Init] Created Mem0Graph for {user_id}")
            except Exception as e:
                import traceback
                instances["mem0_graph"] = f"❌ Error: {str(e)}"
                print(f"[Init] Mem0Graph ERROR: {str(e)}")
                print(traceback.format_exc())
        results["Mem0 Graph"] = instances.get("mem0_graph")

    if "Zep Memory" in systems:
        if "zep_memory" not in instances:
            try:
                instances["zep_memory"] = ZepMemory(user_id=user_id)
                print(f"[Init] Created ZepMemory for {user_id}")
            except Exception as e:
                import traceback
                instances["zep_memory"] = f"❌ Error: {str(e)}"
                print(f"[Init] ZepMemory ERROR: {str(e)}")
                print(traceback.format_exc())
        results["Zep Memory"] = instances.get("zep_memory")

    if "Zep Graph" in systems:
        if "zep_graph" not in instances:
            try:
                instances["zep_graph"] = ZepGraph(user_id=user_id)
                print(f"[Init] Created ZepGraph for {user_id}")
            except Exception as e:
                import traceback
                instances["zep_graph"] = f"❌ Error: {str(e)}"
                print(f"[Init] ZepGraph ERROR: {str(e)}")
                print(traceback.format_exc())
        results["Zep Graph"] = instances.get("zep_graph")

    st.session_state.user_instances[user_id] = instances
    return results


def index_user_data():
    """Index data for the currently selected user with progress display."""
    import asyncio

    async def _index_mem0_graph(graph_instance, data, total_records, debug_logger):
        """Index data to Mem0 Graph."""
        results = []
        for i, record in enumerate(data):
            debug_logger.log_indexing_progress("Mem0 Graph", i + 1, total_records, record)
            await graph_instance.add(
                uid=record.get("uid", ""),
                text=record["text"],
                metadata=record.get("meta", {})
            )
            results.append((i + 1, graph_instance.count()))
        return results

    async def _index_zep_graph(zep_graph_instance, data, total_records, debug_logger):
        """Index data to Zep Graph."""
        batch_size = 50
        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            debug_logger.log_indexing_progress("Zep Graph", min(i + batch_size, len(data)), total_records)
            zep_graph_instance.add_batch(batch)
            results.append((min(i + batch_size, len(data)), "batch_complete"))
        return results

    async def _index_async():
        """Internal async function for actual indexing."""
        from utils import get_debug_logger
        # Create a new logger instance for each import to get a fresh log file
        debug_logger = get_debug_logger(force_new=True)

        user_id = st.session_state.selected_user

        if not user_id:
            st.sidebar.warning("⚠️ Please select a user first")
            return

        # Check if user needs to upload data first
        if user_id not in st.session_state.user_data_store:
            # Data might already be indexed, check storage
            storage_stats = get_storage_stats(user_id)
            if any(count > 0 for count in storage_stats.values()):
                st.sidebar.info(f"✅ Data already exists in storage. No need to re-index.")
            else:
                st.sidebar.warning("⚠️ No data for this user. Please upload first.")
            return

        data = st.session_state.user_data_store[user_id]
        total_records = len(data)
        results = {}

        debug_logger.logger.info("=" * 80)
        debug_logger.logger.info(f"[INDEX START] User: {user_id}, Records: {total_records}, Systems: {st.session_state.index_systems}")
        debug_logger.logger.info("=" * 80)

        # Check if selected systems already have data (only check systems being indexed)
        storage_stats = get_storage_stats(user_id)
        selected_systems_with_data = [sys for sys in st.session_state.index_systems if storage_stats.get(sys, 0) > 0]

        if selected_systems_with_data:
            # Inform user that new data will be appended (incremental mode)
            st.sidebar.info(f"📊 Existing data found: {', '.join(selected_systems_with_data)}")
            st.sidebar.info("ℹ️ New data will be **appended** to existing records (incremental mode)")
            debug_logger.logger.info(f"[INDEX MODE] Incremental append to existing: {selected_systems_with_data}")
            if not st.sidebar.checkbox("✓ Confirm to append new data", value=False):
                return

        progress_placeholder = st.sidebar.empty()
        status_placeholder = st.sidebar.empty()

        instances = get_user_instances(user_id, st.session_state.index_systems)

        # Prepare parallel indexing tasks
        tasks = []
        task_names = []

        mem0_instance = instances.get("Mem0 Graph")
        zep_instance = instances.get("Zep Graph")

        # Check for initialization errors
        if "Mem0 Graph" in st.session_state.index_systems:
            if isinstance(mem0_instance, str) and mem0_instance.startswith("❌"):
                results["Mem0 Graph"] = mem0_instance
                debug_logger.logger.error(f"[INDEX] Mem0 Graph initialization failed: {mem0_instance}")
            elif not mem0_instance:
                results["Mem0 Graph"] = "⚠️ Not initialized"
                debug_logger.logger.warning("[MEM0 GRAPH] Instance is None!")
            else:
                task_names.append("Mem0 Graph")

        if "Zep Graph" in st.session_state.index_systems:
            if isinstance(zep_instance, str) and zep_instance.startswith("❌"):
                results["Zep Graph"] = f"❌ {zep_instance}"
                debug_logger.logger.error(f"[INDEX] Zep Graph initialization failed: {zep_instance}")
            elif not zep_instance:
                results["Zep Graph"] = "⚠️ Not initialized"
                debug_logger.logger.warning("[ZEP GRAPH] Instance is None!")
            else:
                task_names.append("Zep Graph")

        # If no valid instances, return early
        if not task_names:
            progress_placeholder.progress(1.0, "✅ No systems to index")
            return

        # Create async tasks with progress tracking
        async def run_mem0_task():
            try:
                print(f"[Mem0 Graph] Starting to index {total_records} records...")
                debug_logger.logger.info(f"[MEM0 GRAPH] Starting to index {total_records} records...")

                if data:
                    sample_record = data[0]
                    debug_logger.logger.debug(f"[MEM0 GRAPH] Sample record: uid={sample_record.get('uid')}, text_length={len(sample_record.get('text', ''))}")

                progress_updates = await _index_mem0_graph(mem0_instance, data, total_records, debug_logger)

                count = mem0_instance.count()
                result_msg = f"✅ {count} memories"
                results["Mem0 Graph"] = result_msg
                print(f"[Mem0 Graph] Complete! Count: {count}")
                debug_logger.logger.info(f"[MEM0 GRAPH] Complete! Total memories: {count}")
                return "Mem0 Graph", result_msg, progress_updates
            except Exception as e:
                import traceback
                error_msg = f"❌ {str(e)}"
                results["Mem0 Graph"] = error_msg
                print(f"[Mem0 Graph] ERROR: {str(e)}")
                print(traceback.format_exc())
                debug_logger.log_error("Mem0 Graph indexing", e, traceback.format_exc())
                return "Mem0 Graph", error_msg, []

        async def run_zep_task():
            try:
                print(f"[Zep Graph] Starting to index {total_records} records...")
                debug_logger.logger.info(f"[ZEP GRAPH] Starting to index {total_records} records...")

                progress_updates = await _index_zep_graph(zep_instance, data, total_records, debug_logger)

                result_msg = "✅ Indexed"
                results["Zep Graph"] = result_msg
                print(f"[Zep Graph] Complete!")
                debug_logger.logger.info("[ZEP GRAPH] Complete!")
                return "Zep Graph", result_msg, progress_updates
            except Exception as e:
                import traceback
                error_msg = f"❌ {str(e)}"
                results["Zep Graph"] = error_msg
                print(f"[Zep Graph] ERROR: {str(e)}")
                print(traceback.format_exc())
                debug_logger.log_error("Zep Graph indexing", e, traceback.format_exc())
                return "Zep Graph", error_msg, []

        # Build task list
        task_list = []
        if "Mem0 Graph" in task_names:
            task_list.append(run_mem0_task())
        if "Zep Graph" in task_names:
            task_list.append(run_zep_task())

        # Run tasks in parallel and monitor progress
        if task_list:
            # Track progress for each system
            system_progress = {name: 0 for name in task_names}

            # Create a wrapper to update progress
            async def run_with_progress(task):
                name, result, updates = await task
                for current, _ in updates:
                    system_progress[name] = current
                return name, result

            # Run all tasks in parallel
            final_results = await asyncio.gather(*[run_with_progress(t) for t in task_list])

            # Update final results
            for name, result in final_results:
                results[name] = result

        # Complete progress
        progress_placeholder.progress(1.0, "✅ Indexing complete!")
        status_placeholder.empty()

        debug_logger.logger.info(f"[INDEX COMPLETE] Results: {results}")
        debug_logger.logger.info("=" * 80)

        # Show results
        with st.sidebar:
            st.subheader("📈 Index Results")
            for system, result in results.items():
                st.write(f"**{system}:** {result}")

        # Update indexed systems state
        successfully_indexed = [sys for sys, res in results.items() if "✅" in str(res)]
        if user_id not in st.session_state.indexed_systems:
            st.session_state.indexed_systems[user_id] = []
        st.session_state.indexed_systems[user_id] = successfully_indexed

        # Save user metadata after successful indexing
        save_users_meta()

    # Run the async indexing function
    asyncio.run(_index_async())

def clear_user_data():
    """Clear data for the currently selected user."""
    user_id = st.session_state.selected_user

    if not user_id:
        st.sidebar.warning("⚠️ Please select a user first")
        return

    if user_id in st.session_state.user_instances:
        instances = st.session_state.user_instances[user_id]

        if "mem0_standard" in instances:
            instances["mem0_standard"].clear()
        if "mem0_graph" in instances:
            instances["mem0_graph"].clear()
        if "zep_memory" in instances:
            instances["zep_memory"].clear()
        if "zep_graph" in instances:
            instances["zep_graph"].clear()

    st.sidebar.success(f"✅ Cleared data for {user_id}")


def reset_all_data():
    """Reset all data for all users."""
    # Clear all instances
    for user_id in st.session_state.user_instances:
        instances = st.session_state.user_instances[user_id]
        if "mem0_standard" in instances:
            try:
                instances["mem0_standard"].clear()
            except:
                pass
        if "mem0_graph" in instances:
            try:
                instances["mem0_graph"].clear()
            except:
                pass
        if "zep_memory" in instances:
            try:
                instances["zep_memory"].clear()
            except:
                pass
        if "zep_graph" in instances:
            try:
                instances["zep_graph"].clear()
            except:
                pass

    # Reset session state
    st.session_state.user_instances = {}
    st.session_state.user_data_store = {}
    st.session_state.available_users = []
    st.session_state.selected_user = None
    st.session_state.data_loaded = False

    # Delete the saved file
    if USER_META_FILE.exists():
        USER_META_FILE.unlink()

    st.sidebar.success("✅ All data reset")



def render_search_page():
    """Render search and comparison page."""
    st.markdown('<div class="main-header">🔍 Search & Compare</div>', unsafe_allow_html=True)

    if st.session_state.selected_user:
        st.info(f"👤 Searching in: **{st.session_state.selected_user}**")
    else:
        st.warning("⚠️ Please select a user and index data first")
        return

    st.markdown("### 🧠 Select Systems to Compare")

    st.session_state.search_systems = st.multiselect(
        "Select memory systems to search (all 4 systems available)",
        ["Mem0 Standard", "Mem0 Graph", "Zep Memory", "Zep Graph"],
        default=st.session_state.search_systems,
        key="search_system_selector"
    )

    with st.expander("🤖 Advanced Options", expanded=False):
        use_llm = st.checkbox("Enable LLM Answer Generation", value=False,
                             help="Use Gemini AI to generate answers based on retrieved memories")

    col1, col2 = st.columns([3, 1])

    with col1:
        query = st.text_input(
            "Search Query",
            placeholder="Enter your search query...",
            label_visibility="collapsed"
        )

    with col2:
        limit = st.slider("Results", 1, 20, 5)

    if st.button("🔎 Search", use_container_width=True, type="primary"):
        if not query:
            st.warning("Please enter a search query")
            return
        
        if not st.session_state.search_systems:
            st.warning("Please select at least one system to search")
            return

        perform_search(query, limit, use_llm=use_llm)


def perform_search(query: str, limit: int, use_llm: bool = False):
    """Execute search across selected systems for the current user."""
    user_id = st.session_state.selected_user
    results = {}
    times = {}
    graph_enhanced_answers = {}  # Store LLM-enhanced answers for graph modes

    search_systems = st.session_state.get("search_systems", ["Mem0 Standard", "Mem0 Graph", "Zep Graph"])

    get_user_instances(user_id, search_systems)

    instances = st.session_state.user_instances.get(user_id, {})

    if "Mem0 Standard" in search_systems and "mem0_standard" in instances:
        start = time.time()
        try:
            results["Mem0 Standard"] = instances["mem0_standard"].search(
                query, limit, uid=None  # No need to filter, already isolated
            )
            times["Mem0 Standard"] = time.time() - start
        except Exception as e:
            results["Mem0 Standard"] = f"Error: {str(e)}"
            times["Mem0 Standard"] = 0

    if "Mem0 Graph" in search_systems and "mem0_graph" in instances:
        start = time.time()
        try:
            # Use search_with_answer for graph-enhanced response
            graph_result = instances["mem0_graph"].search_with_answer(
                query, limit, uid=user_id
            )
            results["Mem0 Graph"] = graph_result["raw_results"]
            times["Mem0 Graph"] = time.time() - start
            # Store the enhanced answer
            graph_enhanced_answers["Mem0 Graph"] = {
                "answer": graph_result["answer"],
                "memories_count": len(graph_result["memories"]),
                "relations_count": len(graph_result["relations"]),
                "memories": graph_result["memories"],
                "relations": graph_result["relations"]
            }
        except Exception as e:
            results["Mem0 Graph"] = f"Error: {str(e)}"
            times["Mem0 Graph"] = 0

    if "Zep Graph" in search_systems and "zep_graph" in instances:
        start = time.time()
        try:
            results["Zep Graph"] = instances["zep_graph"].search(
                query, limit, uid=None  # Already isolated by session
            )
            times["Zep Graph"] = time.time() - start
        except Exception as e:
            results["Zep Graph"] = f"Error: {str(e)}"
            times["Zep Graph"] = 0

    # Display results
    display_search_results(results, times, query, use_llm=use_llm, graph_enhanced_answers=graph_enhanced_answers)


def display_search_results(results: dict, times: dict, query: str, use_llm: bool = False, graph_enhanced_answers: dict = None):
    """Display search results in comparison view."""
    num_systems = len(results)

    if num_systems == 0:
        st.warning("No systems available for search. Please index data first.")
        return

    if graph_enhanced_answers is None:
        graph_enhanced_answers = {}

    # Generate LLM answers for each system if enabled
    llm_answers = {}
    if use_llm:
        with st.spinner("🤖 Generating AI answers..."):
            from core.llm import get_llm_client
            llm_client = get_llm_client()

            for system_name, system_results in results.items():
                if isinstance(system_results, str) or not system_results:
                    continue

                # Skip Mem0 Graph for standard LLM answer (it has its own enhanced answer)
                if system_name == "Mem0 Graph":
                    continue

                # Extract memory contents from search results
                memory_fragments = []
                for result in system_results:
                    if hasattr(result, 'content'):
                        content = result.content
                        # Only add non-empty content
                        if content:  # This filters out empty strings
                            memory_fragments.append(content)
                    elif isinstance(result, dict):
                        memory_fragments.append(result.get('content', str(result)))
                    else:
                        memory_fragments.append(str(result))

                # Generate answer using LLM
                start = time.time()
                answer = llm_client.generate_answer(query, memory_fragments)
                llm_time = time.time() - start
                llm_answers[system_name] = {
                    "answer": answer,
                    "time": llm_time,
                    "fragments_count": len(memory_fragments)
                }

    if llm_answers:
        st.markdown("---")
        st.markdown("### 🤖 AI-Generated Answers")
        cols = st.columns(len(llm_answers))
        for idx, (system_name, answer_data) in enumerate(llm_answers.items()):
            with cols[idx]:
                st.markdown(f"**{system_name}**")
                st.markdown(f"""<div style='background: #f0f7ff; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #1f77b4; color: #1a1a1a;'>
                    <p style='color: #1a1a1a; margin: 0;'>{answer_data['answer']}</p>
                </div>""", unsafe_allow_html=True)
                st.caption(f"⏱️ LLM: {answer_data['time']:.2f}s | 📊 Based on {answer_data['fragments_count']} fragments")
        st.markdown("---")

    columns = st.columns(num_systems)

    for idx, (system_name, system_results) in enumerate(results.items()):
        with columns[idx]:
            st.subheader(f"🧠 {system_name}")

            # Query time
            if system_name in times:
                st.caption(f"⏱️ Query time: {times[system_name]:.3f}s")

            # Results
            if isinstance(system_results, str):
                st.error(system_results)
            elif len(system_results) == 0:
                st.info("No results found")
            else:
                # Determine the search type and data source
                is_zep_graph = system_name == "Zep Graph"
                is_mem0_graph = system_name == "Mem0 Graph"
                has_zep_facts = False
                has_graph_relations = False
                graph_relations = []
                zep_facts = []

                # Analyze results structure
                for result in system_results:
                    # Check for Zep graph facts
                    if is_zep_graph and result.metadata.get("source") == "zep_graph":
                        has_zep_facts = True
                        relation_type = result.metadata.get("relation_type", "RELATED")
                        zep_facts.append({
                            "content": result.content,
                            "relation_type": relation_type,
                            "score": result.score
                        })

                    # Check for Mem0 graph relations
                    if hasattr(result, 'graph_relations') and result.graph_relations:
                        has_graph_relations = True
                        graph_relations = result.graph_relations
                        break

                # === Zep Graph: Display facts as graph relationships ===
                if is_zep_graph and has_zep_facts:
                    st.markdown(f"**🕸️ Extracted Facts** ({len(zep_facts)} found)")

                    # Group by relation type
                    by_type = {}
                    for fact in zep_facts:
                        rel_type = fact["relation_type"]
                        if rel_type not in by_type:
                            by_type[rel_type] = []
                        by_type[rel_type].append(fact)

                    # Display grouped by relation type
                    for rel_type, facts in sorted(by_type.items()):
                        with st.expander(f"[{rel_type}] ({len(facts)} facts)", expanded=(len(by_type) == 1)):
                            for fact in facts[:5]:
                                st.markdown(f"- {fact['content']}")
                                st.caption(f"   Score: {fact['score']:.3f}")
                            if len(facts) > 5:
                                st.caption(f"   ... and {len(facts) - 5} more")

                    st.markdown("---")

                # === Mem0 Graph: Display LLM-enhanced answer ===
                elif is_mem0_graph:
                    # Show the LLM-enhanced answer if available
                    if system_name in graph_enhanced_answers:
                        answer_data = graph_enhanced_answers[system_name]
                        st.markdown(f"**🤖 Graph-Enhanced Answer**")
                        st.markdown(f"""<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1rem; border-radius: 0.5rem; color: white;'>
                            <p style='color: white; margin: 0; font-size: 1.05rem;'>{answer_data['answer']}</p>
                        </div>""", unsafe_allow_html=True)
                        st.caption(f"📊 Based on {answer_data['memories_count']} memories + {answer_data['relations_count']} relations")
                        st.markdown("---")

                    # Show graph relations if available
                    if has_graph_relations and graph_relations:
                        st.markdown(f"**🕸️ Graph Relations** ({len(graph_relations)} found)")
                        with st.expander("View entity relationships", expanded=False):
                            for rel in graph_relations[:10]:
                                st.markdown(f"`{rel.source}` —**[{rel.relationship}]**→ `{rel.destination}`")
                            if len(graph_relations) > 10:
                                st.caption(f"... and {len(graph_relations) - 10} more relations")
                        st.markdown("---")

                # === Display search results ===
                # For Zep Graph, facts are already displayed above
                if is_zep_graph and has_zep_facts:
                    st.markdown("**📝 Original Messages** (thread search)")
                    # Filter out zep_graph results, show only original messages
                    original_msgs = [r for r in system_results if r.metadata.get("source") != "zep_graph"]
                    if original_msgs:
                        for i, result in enumerate(original_msgs[:5], 1):
                            with st.expander(f"#{i} (Score: {result.score:.3f})"):
                                st.write(result.content)
                    else:
                        st.caption("(No original messages matched, showing extracted facts only)")
                else:
                    # Standard display for other systems
                    display_title = "**📝 Search Results**"
                    if is_mem0_graph:
                        display_title = "**📝 Vector Search Results**"
                    st.markdown(display_title)

                    for i, result in enumerate(system_results, 1):
                        with st.expander(f"#{i} (Score: {result.score:.3f})"):
                            st.write(result.content)
                            if result.metadata:
                                with st.expander("Metadata"):
                                    st.json(result.metadata)


def render_graph_page():
    """Render graph visualization page."""
    st.markdown('<div class="main-header">🕸️ Graph Visualization</div>', unsafe_allow_html=True)

    # Show current user context
    if st.session_state.selected_user:
        st.info(f"👤 Viewing graph for: **{st.session_state.selected_user}**")
    else:
        st.warning("⚠️ Please select a user and index data first")
        return

    user_id = st.session_state.selected_user

    if user_id not in st.session_state.user_instances:
        st.warning(f"No indexed data for user '{user_id}'. Please click 'Index' first.")
        return

    instances = st.session_state.user_instances.get(user_id, {})

    system_select = st.selectbox(
        "Select Graph System",
        ["Mem0 Graph", "Zep Graph"]
    )

    if st.button("Load Graph", use_container_width=True):
        if system_select == "Mem0 Graph" and "mem0_graph" in instances:
            graph_data = instances["mem0_graph"].get_graph_data(user_id)
            display_graph(graph_data)
        elif system_select == "Zep Graph" and "zep_graph" in instances:
            graph_data = instances["zep_graph"].get_graph_data(uid=None)
            display_graph(graph_data)
        else:
            st.warning("Please index data for this system first")


def display_graph(graph_data):
    """Display graph visualization."""
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Nodes", len(graph_data.nodes))

    with col2:
        st.metric("Edges", len(graph_data.edges))

    if not graph_data.nodes:
        st.info("No graph data available")
        return

    # Display nodes and edges
    tab1, tab2 = st.tabs(["Nodes", "Edges"])

    with tab1:
        for node in graph_data.nodes:
            st.write(f"**{node.name}** ({node.type})")

    with tab2:
        for edge in graph_data.edges:
            st.write(f"{edge.source} --[{edge.relation_type}]--> {edge.target}")


def render_metrics_page():
    """Render metrics comparison page."""
    st.markdown('<div class="main-header">📊 Metrics Comparison</div>', unsafe_allow_html=True)

    # Show current user context
    if st.session_state.selected_user:
        st.info(f"👤 Metrics for: **{st.session_state.selected_user}**")
    else:
        st.warning("⚠️ Please select a user and index data first")
        return

    user_id = st.session_state.selected_user

    if user_id not in st.session_state.user_instances:
        st.info("No indexed data for this user. Please click 'Index' first.")
        return

    instances = st.session_state.user_instances.get(user_id, {})
    metrics_data = []

    if "mem0_standard" in instances:
        try:
            metrics_data.append({
                "User": user_id,
                "System": "Mem0 Standard",
                "Type": "Vector",
                "Total Memories": instances["mem0_standard"].count()
            })
        except:
            pass

    if "mem0_graph" in instances:
        try:
            metrics_data.append({
                "User": user_id,
                "System": "Mem0 Graph",
                "Type": "Graph",
                "Total Memories": instances["mem0_graph"].count()
            })
        except:
            pass

    # Display table
    if metrics_data:
        st.dataframe(metrics_data, use_container_width=True)

        # User-level summary
        st.markdown("---")
        st.subheader("📈 Summary")
        total_memories = sum(m["Total Memories"] for m in metrics_data)
        st.metric("Total Memories Across All Systems", total_memories)
    else:
        st.info("No indexed data for this user. Please click 'Index' first.")


def main():
    """Main application entry point."""
    init_session_state()

    # Render sidebar
    with st.sidebar:
        st.title("🧠 Memory Comparison")
        st.markdown("---")
        sidebar()

    # Navigation
    page = option_menu(
        None,
        ["🔍 Search", "🕸️ Graph", "📊 Metrics"],
        icons=["search", "diagram-3", "bar-chart"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal"
    )

    # Route to page
    if page == "🔍 Search":
        render_search_page()
    elif page == "🕸️ Graph":
        render_graph_page()
    elif page == "📊 Metrics":
        render_metrics_page()


if __name__ == "__main__":
    main()
