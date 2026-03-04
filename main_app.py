"""Main Streamlit application for Memory Comparison Tool.

Features:
- JSON file upload with preview
- Batch import to Mem0 (Standard/Graph) and Zep
- Side-by-side search comparison
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit_option_menu import option_menu

from config import config
from models import SearchResult
from core import Mem0Factory, ZepFactory
from utils import DataProcessor, validate_data_format

# ============================================
# Page Configuration
# ============================================
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
        text-align: center;
        padding: 1.5rem 0;
        margin-bottom: 2rem;
        border-bottom: 2px solid #e0e0e0;
    }
    .main-header h1 {
        margin: 0;
        color: #1f77b4;
        font-size: 2.5rem;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        color: #666;
    }
    .result-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .result-card .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #f0f0f0;
    }
    .result-card .system-name {
        font-weight: 600;
        font-size: 1.1rem;
        color: #1f77b4;
    }
    .result-card .latency {
        font-size: 0.85rem;
        color: #666;
        background: #f5f5f5;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
    }
    .result-card .result-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        background: #fafafa;
        border-radius: 4px;
        border-left: 3px solid #1f77b4;
    }
    .result-card .score {
        display: inline-block;
        background: #e3f2fd;
        color: #1565c0;
        padding: 0.15rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin-left: 0.5rem;
    }
    .result-card .timestamp {
        display: block;
        font-size: 0.8rem;
        color: #888;
        margin-top: 0.25rem;
    }
    .metric-box {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 8px;
        color: white;
    }
    .metric-box .value {
        font-size: 2rem;
        font-weight: 700;
    }
    .metric-box .label {
        font-size: 0.85rem;
        opacity: 0.9;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# Session State Initialization
# ============================================
def init_session_state():
    """Initialize session state variables."""
    if "uploaded_data" not in st.session_state:
        st.session_state.uploaded_data = None
    if "processed_records" not in st.session_state:
        st.session_state.processed_records = []
    if "mem0_standard" not in st.session_state:
        st.session_state.mem0_standard = None
    if "mem0_graph" not in st.session_state:
        st.session_state.mem0_graph = None
    if "zep_memory" not in st.session_state:
        st.session_state.zep_memory = None
    if "indexed_count" not in st.session_state:
        st.session_state.indexed_count = {"mem0_std": 0, "mem0_graph": 0, "zep": 0}
    if "import_status" not in st.session_state:
        st.session_state.import_status = {}


init_session_state()


# ============================================
# Sidebar
# ============================================
def render_sidebar():
    """Render sidebar with configuration and status."""
    with st.sidebar:
        st.markdown("## 🧠 Memory Comparison")

        st.markdown("---")

        # Connection Status
        st.markdown("### 📡 Connection Status")

        # Mem0 Status
        mem0_status = check_mem0_connection()
        if mem0_status["qdrant"]:
            st.success("✅ Qdrant (Mem0)")
        else:
            st.warning("⚠️ Qdrant (Mem0)")

        if mem0_status["neo4j"]:
            st.success("✅ Neo4j (Mem0)")
        else:
            st.warning("⚠️ Neo4j (Mem0)")

        # Zep Status
        zep_status = check_zep_connection()
        if zep_status:
            st.success("✅ Zep API")
        else:
            st.warning("⚠️ Zep API")

        st.markdown("---")

        # Current Status
        st.markdown("### 📊 Indexed Data")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Mem0 Std", st.session_state.indexed_count["mem0_std"])
        with col2:
            st.metric("Mem0 Graph", st.session_state.indexed_count["mem0_graph"])

        st.metric("Zep", st.session_state.indexed_count["zep"])

        st.markdown("---")

        # Actions
        st.markdown("### 🛠️ Actions")

        if st.button("🔄 Reset All Data", use_container_width=True):
            reset_all_data()


def check_mem0_connection() -> dict:
    """Check Mem0 connections."""
    status = {"qdrant": False, "neo4j": False}

    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=config.mem0.qdrant_host, port=int(config.mem0.qdrant_port))
        client.get_collections()
        status["qdrant"] = True
    except Exception:
        pass

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        driver.verify_connectivity()
        driver.close()
        status["neo4j"] = True
    except Exception:
        pass

    return status


def check_zep_connection() -> bool:
    """Check Zep connection."""
    try:
        if not config.zep.api_key:
            return False
        from zep_cloud import Zep
        client = Zep(api_key=config.zep.api_key)
        # Simply verify client can be created (API key is validated on first API call)
        return True
    except Exception:
        return False


def reset_all_data():
    """Reset all session data."""
    st.session_state.uploaded_data = None
    st.session_state.processed_records = []
    st.session_state.indexed_count = {"mem0_std": 0, "mem0_graph": 0, "zep": 0}
    st.session_state.import_status = {}

    # Clear memory systems
    if st.session_state.mem0_standard:
        try:
            st.session_state.mem0_standard.clear()
        except Exception:
            pass
    if st.session_state.mem0_graph:
        try:
            st.session_state.mem0_graph.clear()
        except Exception:
            pass
    if st.session_state.zep_memory:
        try:
            st.session_state.zep_memory.clear()
        except Exception:
            pass

    st.success("✅ All data reset!")


# ============================================
# Upload Page
# ============================================
def render_upload_page():
    """Render file upload and preview page."""
    st.markdown("""
    <div class="main-header">
        <h1>📁 Data Upload</h1>
        <p>Upload your JSON memory data file</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose JSON file",
            type=["json"],
            label_visibility="collapsed"
        )

    with col2:
        sample_data = st.checkbox("Use Sample Data")

    with col3:
        if st.session_state.uploaded_data is not None:
            st.success(f"✅ {len(st.session_state.uploaded_data)} records")

    # Process uploaded file
    data = None
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            st.session_state.uploaded_data = data
        except json.JSONDecodeError:
            st.error("❌ Invalid JSON file")
            return
    elif sample_data:
        # Load sample data
        try:
            with open("linmu_realistic_translated_fixed.json", "r") as f:
                data = json.load(f)
                st.session_state.uploaded_data = data
                st.info("📋 Using sample data: linmu_realistic_translated_fixed.json")
        except FileNotFoundError:
            st.warning("Sample file not found")

    if data is None:
        st.info("👆 Upload a JSON file or select 'Use Sample Data'")
        return

    # Validate data
    is_valid, message = validate_data_format(data)
    if not is_valid:
        st.error(f"❌ {message}")
        return

    # Process data
    processor = DataProcessor.from_data(data)
    records = processor.process()
    st.session_state.processed_records = records

    # Display summary
    summary = processor.summary()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", summary["total_records"])
    with col2:
        st.metric("Unique Users", summary["user_count"])
    with col3:
        st.metric("Categories", summary["category_count"])
    with col4:
        if summary["timestamp_range"]:
            st.metric("Date Range",
                     f"{summary['timestamp_range']['earliest'][:10]} ~ "
                     f"{summary['timestamp_range']['latest'][:10]}")

    # Display users and categories
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 👥 Users")
        st.write(", ".join(summary["unique_users"]))
    with col2:
        st.markdown("### 📂 Categories")
        st.write(", ".join(summary["unique_categories"]))

    # Data preview
    st.markdown("---")
    st.markdown("### 📋 Data Preview")

    preview_count = st.slider("Show records", 1, min(20, len(records)), 5)

    for i, record in enumerate(records[:preview_count], 1):
        with st.expander(f"#{i} - {record.uid} | {record.timestamp[:10]} | {record.category}"):
            st.write(record.text)
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Metadata:**")
                st.json(record.metadata)


# ============================================
# Import Page
# ============================================
def render_import_page():
    """Render batch import page."""
    st.markdown("""
    <div class="main-header">
        <h1>🚀 Batch Import</h1>
        <p>Import data into memory systems</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.processed_records:
        st.warning("⚠️ Please upload data first from the 'Upload' page")
        return

    # Convert to dict list for import
    records_dict = [
        {
            "uid": r.uid,
            "text": r.text,
            "meta": {
                "timestamp": r.timestamp,
                "category": r.category,
                **r.metadata
            }
        }
        for r in st.session_state.processed_records
    ]

    # System selection
    st.markdown("### 🎯 Select Target Systems")

    col1, col2, col3 = st.columns(3)

    with col1:
        import_mem0_std = st.checkbox("Mem0 Standard (Qdrant)", value=True)
    with col2:
        import_mem0_graph = st.checkbox("Mem0 Graph (Neo4j)", value=True)
    with col3:
        import_zep = st.checkbox("Zep Memory", value=True)

    if not any([import_mem0_std, import_mem0_graph, import_zep]):
        st.warning("⚠️ Please select at least one system")
        return

    # Sync import option for Mem0 Graph
    if import_mem0_graph:
        use_sync_import = st.checkbox(
            "🔄 Use Synchronous Import for Mem0 Graph",
            value=True,
            help="Synchronous import uses the sync client directly, avoiding async overhead. Recommended for stability."
        )
    else:
        use_sync_import = False

    # Import button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📥 Start Import", use_container_width=True, type="primary"):
            import_data(records_dict, import_mem0_std, import_mem0_graph, import_zep, use_sync_import)

    # Display import status
    if st.session_state.import_status:
        st.markdown("---")
        st.markdown("### 📊 Import Results")

        for system, status in st.session_state.import_status.items():
            if status["success"]:
                st.success(f"✅ {system}: {status['count']} records imported ({status['time']:.2f}s)")
            else:
                st.error(f"❌ {system}: {status['error']}")


def import_data(records: list[dict], mem0_std: bool, mem0_graph: bool, zep: bool, use_sync: bool = True):
    """Import data into selected systems.

    Args:
        records: List of records to import
        mem0_std: Import to Mem0 Standard
        mem0_graph: Import to Mem0 Graph
        zep: Import to Zep
        use_sync: Use synchronous import for Mem0 Graph (default: True)
    """
    st.session_state.import_status = {}

    # Get uid from records (all records should have the same uid for single-user import)
    if not records:
        st.error("❌ No records to import")
        return

    uid = records[0].get("uid", "default")
    collection_name = f"memory_store_{uid}"

    # Progress placeholder
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Calculate progress increments
    total_systems = sum([mem0_std, mem0_graph, zep])
    if total_systems == 0:
        return

    progress_increment = 100 / total_systems
    current_progress = 0

    # Mem0 Standard
    if mem0_std:
        try:
            status_text.text(f"🔄 Importing to Mem0 Standard (collection: {collection_name})...")
            progress_bar.progress(current_progress)

            start_time = time.time()
            st.session_state.mem0_standard = Mem0Factory.create(
                mode="standard",
                user_id=uid,
                collection_name=collection_name
            )

            memory_ids = st.session_state.mem0_standard.add_batch_pure_sync(records)

            elapsed = time.time() - start_time
            st.session_state.indexed_count["mem0_std"] = len(memory_ids)
            st.session_state.import_status["Mem0 Standard"] = {
                "success": True,
                "count": len(memory_ids),
                "time": elapsed
            }
            current_progress += progress_increment
            progress_bar.progress(current_progress)

        except Exception as e:
            st.session_state.import_status["Mem0 Standard"] = {
                "success": False,
                "error": str(e)
            }

    # Mem0 Graph
    if mem0_graph:
        try:
            import_mode = "Sync" if use_sync else "Async"
            status_text.text(f"🔄 Importing to Mem0 Graph ({import_mode} mode, collection: {collection_name})...")
            progress_bar.progress(current_progress)

            start_time = time.time()
            st.session_state.mem0_graph = Mem0Factory.create(
                mode="graph",
                user_id=uid,
                collection_name=collection_name
            )

            if use_sync:
                memory_ids = st.session_state.mem0_graph.add_batch_pure_sync(records)
            else:
                memory_ids = st.session_state.mem0_graph.add_batch_sync(records)

            elapsed = time.time() - start_time
            st.session_state.indexed_count["mem0_graph"] = len(memory_ids)
            st.session_state.import_status["Mem0 Graph"] = {
                "success": True,
                "count": len(memory_ids),
                "time": elapsed
            }
            current_progress += progress_increment
            progress_bar.progress(current_progress)

        except Exception as e:
            st.session_state.import_status["Mem0 Graph"] = {
                "success": False,
                "error": str(e)
            }

    # Zep
    if zep:
        try:
            status_text.text(f"🔄 Importing to Zep (user: {uid})...")
            progress_bar.progress(current_progress)

            start_time = time.time()
            st.session_state.zep_memory = ZepFactory.create("memory", user_id=uid)

            memory_ids = st.session_state.zep_memory.add_batch(records)

            elapsed = time.time() - start_time
            st.session_state.indexed_count["zep"] = len(memory_ids)
            st.session_state.import_status["Zep Memory"] = {
                "success": True,
                "count": len(memory_ids),
                "time": elapsed
            }
            current_progress += progress_increment
            progress_bar.progress(100)

        except Exception as e:
            st.session_state.import_status["Zep Memory"] = {
                "success": False,
                "error": str(e)
            }

    status_text.text("✅ Import complete!")
    progress_bar.empty()


# ============================================
# Search Page
# ============================================
def render_search_page():
    """Render search and comparison page."""
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Search & Compare</h1>
        <p>Compare results across memory systems</p>
    </div>
    """, unsafe_allow_html=True)

    # Check if any system has data
    total_indexed = sum(st.session_state.indexed_count.values())
    if total_indexed == 0:
        st.warning("⚠️ Please import data first from the 'Import' page")
        return

    # Search controls
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    with col1:
        query = st.text_input(
            "Search Query",
            placeholder="Enter your search query...",
            label_visibility="collapsed"
        )

    with col2:
        limit = st.slider("Results", 1, 20, 5)

    with col3:
        user_filter = st.selectbox(
            "User Filter",
            ["All"] + get_unique_users(),
            label_visibility="collapsed"
        )

    with col4:
        if st.button("🔎 Search", use_container_width=True, type="primary"):
            if query:
                perform_search(query, limit, user_filter if user_filter != "All" else None)
            else:
                st.warning("Please enter a search query")


def get_unique_users() -> list[str]:
    """Get unique users from processed records."""
    return sorted(set(r.uid for r in st.session_state.processed_records))


def perform_search(query: str, limit: int, uid_filter: Optional[str]):
    """Execute search across all systems."""
    results = {}
    latencies = {}

    uid = uid_filter if uid_filter else None

    # Mem0 Standard
    if st.session_state.mem0_standard:
        start = time.time()
        try:
            results["Mem0 Standard"] = st.session_state.mem0_standard.search(query, limit, uid)
            latencies["Mem0 Standard"] = (time.time() - start) * 1000  # ms
        except Exception as e:
            results["Mem0 Standard"] = f"Error: {str(e)}"
            latencies["Mem0 Standard"] = 0

    # Mem0 Graph
    if st.session_state.mem0_graph:
        start = time.time()
        try:
            results["Mem0 Graph"] = st.session_state.mem0_graph.search(query, limit, uid)
            latencies["Mem0 Graph"] = (time.time() - start) * 1000
        except Exception as e:
            results["Mem0 Graph"] = f"Error: {str(e)}"
            latencies["Mem0 Graph"] = 0

    # Zep
    if st.session_state.zep_memory:
        start = time.time()
        try:
            results["Zep Memory"] = st.session_state.zep_memory.search(query, limit, uid)
            latencies["Zep Memory"] = (time.time() - start) * 1000
        except Exception as e:
            results["Zep Memory"] = f"Error: {str(e)}"
            latencies["Zep Memory"] = 0

    # Display results
    display_comparison_results(query, results, latencies)


def display_comparison_results(query: str, results: dict, latencies: dict):
    """Display side-by-side comparison results."""
    st.markdown("---")

    # Query summary
    st.markdown(f"### 📝 Query: \"{query}\"")

    # Latency comparison
    systems = list(latencies.keys())
    latency_values = list(latencies.values())

    if latency_values and max(latency_values) > 0:
        col1, col2, col3 = st.columns(3)

        for i, (system, latency) in enumerate(latencies.items()):
            if i % 3 == 0:
                with col1:
                    render_latency_card(system, latency)
            elif i % 3 == 1:
                with col2:
                    render_latency_card(system, latency)
            else:
                with col3:
                    render_latency_card(system, latency)

    st.markdown("---")

    # Results grid
    num_systems = len(results)
    if num_systems == 0:
        st.warning("No search results available")
        return

    # Create columns for each system
    columns = st.columns(num_systems)

    for idx, (system_name, system_results) in enumerate(results.items()):
        with columns[idx]:
            st.markdown(f"""
            <div class="result-card">
                <div class="header">
                    <span class="system-name">{system_name}</span>
                    <span class="latency">{latencies.get(system_name, 0):.1f}ms</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Display results
            if isinstance(system_results, str):
                st.error(system_results)
            elif len(system_results) == 0:
                st.info("🔍 No results found")
            else:
                for i, result in enumerate(system_results, 1):
                    # Extract timestamp from metadata
                    timestamp = result.metadata.get("timestamp", "N/A")
                    if timestamp and len(timestamp) > 10:
                        timestamp = timestamp[:10]

                    st.markdown(f"""
                    <div class="result-item">
                        <strong>#{i}</strong>
                        <span class="score">{result.score:.3f}</span>
                        <p>{result.content[:200]}{'...' if len(result.content) > 200 else ''}</p>
                        <span class="timestamp">📅 {timestamp}</span>
                    </div>
                    """, unsafe_allow_html=True)

    # Comparison table
    st.markdown("---")
    st.markdown("### 📊 Comparison Table")

    comparison_data = []
    for system_name, system_results in results.items():
        if isinstance(system_results, list) and system_results:
            top_result = system_results[0]
            comparison_data.append({
                "System": system_name,
                "Results": len(system_results),
                "Top Score": f"{top_result.score:.4f}",
                "Latency (ms)": f"{latencies.get(system_name, 0):.1f}",
                "Timestamp": top_result.metadata.get("timestamp", "N/A")[:10]
            })
        elif isinstance(system_results, list):
            comparison_data.append({
                "System": system_name,
                "Results": 0,
                "Top Score": "N/A",
                "Latency (ms)": f"{latencies.get(system_name, 0):.1f}",
                "Timestamp": "N/A"
            })

    st.dataframe(
        comparison_data,
        use_container_width=True,
        hide_index=True
    )


def render_latency_card(system: str, latency: float):
    """Render a latency metric card."""
    color = "#4caf50" if latency < 500 else "#ff9800" if latency < 1500 else "#f44336"
    st.markdown(f"""
    <div style="text-align: center; padding: 0.5rem; background: {color}20;
                border-radius: 8px; border-left: 4px solid {color};">
        <div style="font-size: 1.5rem; font-weight: 700; color: {color};">
            {latency:.1f}ms
        </div>
        <div style="font-size: 0.8rem; color: #666;">{system}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================
# Main Application
# ============================================
def main():
    """Main application entry point."""
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Navigation
    page = option_menu(
        None,
        ["📁 Upload", "🚀 Import", "🔍 Search"],
        icons=["upload", "database-add", "search"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0rem"},
            "nav-link": {
                "font-size": "1rem",
                "text-align": "center",
                "margin": "0rem",
                "padding": "0.75rem 1rem",
            }
        }
    )

    # Route to page
    if page == "📁 Upload":
        render_upload_page()
    elif page == "🚀 Import":
        render_import_page()
    elif page == "🔍 Search":
        render_search_page()


if __name__ == "__main__":
    main()
