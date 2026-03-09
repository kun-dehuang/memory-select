"""Online Streamlit application for Memory Comparison Tool.

This version uses the remote HTTP API instead of local services.

Features:
- JSON file upload with preview
- Batch import to remote Memory API
- Search with AI-generated answers
- Graph visualization support
"""

import json
import time
from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit_option_menu import option_menu

from config import config
from models import SearchResult, GraphVisualization
from core.remote_memory_client import RemoteMemoryFactory
from utils import DataProcessor, validate_data_format

# ============================================
# Page Configuration
# ============================================
st.set_page_config(
    page_title="Memory Tool (Online)",
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
    .answer-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-left: 4px solid #7c4dff;
    }
    .answer-box .answer-label {
        font-weight: 600;
        color: #7c4dff;
        margin-bottom: 0.5rem;
    }
    .answer-box .answer-text {
        font-size: 1.1rem;
        line-height: 1.6;
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
    .api-badge {
        display: inline-block;
        background: #ff9800;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 0.5rem;
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
    if "remote_client" not in st.session_state:
        st.session_state.remote_client = None
    if "current_uid" not in st.session_state:
        st.session_state.current_uid = None
    if "indexed_count" not in st.session_state:
        st.session_state.indexed_count = 0
    if "import_status" not in st.session_state:
        st.session_state.import_status = {}


init_session_state()


# ============================================
# Sidebar
# ============================================
def render_sidebar():
    """Render sidebar with configuration and status."""
    with st.sidebar:
        st.markdown("## 🧠 Memory Tool (Online)")

        st.markdown("---")

        # API Configuration
        st.markdown("### 🌐 Remote API")

        api_url = st.text_input(
            "API URL",
            value=config.remote_api_url,
            help="Base URL of the remote Memory API"
        )

        # Update config if changed
        if api_url != config.remote_api_url:
            config.remote_api_url = api_url

        # Connection Status
        st.markdown("### 📡 Connection Status")

        api_status = check_api_connection(api_url)
        if api_status:
            st.success("✅ Remote API")
        else:
            st.warning("⚠️ Remote API")

        st.markdown("---")

        # Current Status
        st.markdown("### 📊 Indexed Data")

        st.metric("Memories", st.session_state.indexed_count)

        # Current User
        if st.session_state.current_uid:
            st.metric("User ID", st.session_state.current_uid)

        st.markdown("---")

        # Actions
        st.markdown("### 🛠️ Actions")

        if st.button("🔄 Reset All Data", use_container_width=True):
            reset_all_data()


def check_api_connection(api_url: str) -> bool:
    """Check remote API connection."""
    try:
        import httpx
        # Try to hit a simple endpoint
        client = httpx.Client(timeout=5.0)
        response = client.get(f"{api_url.rstrip('/')}/api/v1/memory/count?uid=test")
        # 404 or 200 is okay, we just want to know the server is up
        client.close()
        return response.status_code in [200, 404, 422]
    except Exception:
        return False


def reset_all_data():
    """Reset all session data."""
    st.session_state.uploaded_data = None
    st.session_state.processed_records = []
    st.session_state.indexed_count = 0
    st.session_state.import_status = {}
    st.session_state.current_uid = None

    if st.session_state.remote_client:
        try:
            st.session_state.remote_client.close()
        except Exception:
            pass
        st.session_state.remote_client = None

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
        <p>Import data to remote Memory API</p>
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

    # User ID selection
    st.markdown("### 👤 User ID")

    unique_users = sorted(set(r.uid for r in st.session_state.processed_records))
    selected_user = st.selectbox("Select user to import for", unique_users)

    # Filter records for selected user
    user_records = [r for r in records_dict if r["uid"] == selected_user]

    st.info(f"📊 {len(user_records)} records will be imported for user: {selected_user}")

    # Import options
    st.markdown("---")
    st.markdown("### ⚙️ Import Options")

    col1, col2 = st.columns(2)
    with col1:
        show_progress = st.checkbox("Show detailed progress", value=True)
    with col2:
        verify_import = st.checkbox("Verify after import", value=True)

    # Import button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📥 Start Import", use_container_width=True, type="primary"):
            import_data(user_records, selected_user, show_progress, verify_import)

    # Display import status
    if st.session_state.import_status:
        st.markdown("---")
        st.markdown("### 📊 Import Results")

        status = st.session_state.import_status
        if status.get("success"):
            st.success(f"✅ Import complete: {status['count']} records imported ({status['time']:.2f}s)")
        else:
            st.error(f"❌ Import failed: {status.get('error', 'Unknown error')}")


def import_data(records: list[dict], uid: str, show_progress: bool, verify: bool):
    """Import data to remote API.

    Args:
        records: List of records to import
        uid: User ID
        show_progress: Whether to show progress bar
        verify: Whether to verify count after import
    """
    st.session_state.import_status = {}

    if not records:
        st.error("❌ No records to import")
        return

    # Create client with extended timeout for LLM operations
    try:
        st.session_state.remote_client = RemoteMemoryFactory.create(
            base_url=config.remote_api_url,
            user_id=uid,
            timeout=180.0  # 3 minutes for search-with-answer with LLM
        )
        st.session_state.current_uid = uid
    except Exception as e:
        st.session_state.import_status = {
            "success": False,
            "error": f"Failed to create client: {str(e)}"
        }
        return

    # Progress UI
    if show_progress:
        progress_bar = st.progress(0)
        status_text = st.empty()
    else:
        progress_bar = None
        status_text = None

    start_time = time.time()

    try:
        # Import in batches
        batch_size = 10
        total = len(records)
        memory_ids = []

        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]

            if show_progress:
                status_text.text(f"🔄 Importing records {i + 1}-{min(i + batch_size, total)}...")

            batch_ids = st.session_state.remote_client.add_batch(batch)
            memory_ids.extend(batch_ids)

            if show_progress:
                progress = min((i + batch_size) / total, 1.0)
                progress_bar.progress(progress)

        elapsed = time.time() - start_time
        st.session_state.indexed_count = len(memory_ids)

        # Verify import
        if verify:
            if show_progress:
                status_text.text("✅ Verifying import...")

            count = st.session_state.remote_client.count(uid)
            st.session_state.indexed_count = count

        st.session_state.import_status = {
            "success": True,
            "count": len(memory_ids),
            "time": elapsed
        }

        if show_progress:
            status_text.text("✅ Import complete!")

    except Exception as e:
        elapsed = time.time() - start_time
        st.session_state.import_status = {
            "success": False,
            "error": str(e)
        }

    if show_progress:
        progress_bar.empty()
        status_text.empty()


# ============================================
# Search Page
# ============================================
def render_search_page():
    """Render search and results page."""
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Search Memory</h1>
        <p>Search the remote Memory API</p>
    </div>
    """, unsafe_allow_html=True)

    # Check if client exists
    if not st.session_state.remote_client:
        st.warning("⚠️ Please import data first from the 'Import' page")
        return

    if st.session_state.indexed_count == 0:
        st.warning("⚠️ No memories indexed. Please import data first.")
        return

    # Search controls
    col1, col2, col3 = st.columns([3, 1, 2])

    with col1:
        query = st.text_input(
            "Search Query",
            placeholder="Enter your search query...",
            label_visibility="collapsed"
        )

    with col2:
        limit = st.slider("Results", 1, 20, 5)

    with col3:
        search_type = st.selectbox(
            "Search Type",
            ["Standard", "With AI Answer"],
            label_visibility="collapsed"
        )

    # Search button
    col1, col2, col3 = st.columns([2, 2, 2])
    with col2:
        if st.button("🔎 Search", use_container_width=True, type="primary"):
            if query:
                if search_type == "Standard":
                    perform_search(query, limit)
                else:
                    perform_search_with_answer(query, limit)
            else:
                st.warning("Please enter a search query")

    # User ID filter for search
    if st.session_state.current_uid:
        st.info(f"👤 Searching for user: {st.session_state.current_uid}")


def perform_search(query: str, limit: int):
    """Execute standard search."""
    results = []
    latency = 0

    try:
        start = time.time()
        results = st.session_state.remote_client.search(
            query=query,
            limit=limit,
            uid=st.session_state.current_uid
        )
        latency = (time.time() - start) * 1000
    except Exception as e:
        st.error(f"❌ Search failed: {str(e)}")
        return

    display_search_results(query, results, latency)


def perform_search_with_answer(query: str, limit: int):
    """Execute search with AI-generated answer."""
    result = {}
    latency = 0

    try:
        start = time.time()
        result = st.session_state.remote_client.search_with_answer(
            query=query,
            limit=limit,
            uid=st.session_state.current_uid
        )
        latency = (time.time() - start) * 1000
    except Exception as e:
        st.error(f"❌ Search failed: {str(e)}")
        return

    display_search_with_answer_results(query, result, latency)


def display_search_results(query: str, results: list[SearchResult], latency: float):
    """Display standard search results."""
    st.markdown("---")

    # Query summary
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### 📝 Query: \"{query}\"")
    with col2:
        st.markdown(f"<div style='text-align: right;'>{latency:.1f}ms</div>", unsafe_allow_html=True)

    # Results
    if not results:
        st.info("🔍 No results found")
        return

    for i, result in enumerate(results, 1):
        # Extract timestamp from metadata
        timestamp = result.metadata.get("timestamp", "N/A")
        if timestamp and len(timestamp) > 10:
            timestamp = timestamp[:10]

        st.markdown(f"""
        <div class="result-card">
            <div class="header">
                <span class="system-name">Result #{i}</span>
                <span class="latency">Score: {result.score:.3f}</span>
            </div>
            <div class="result-item">
                <p>{result.content[:500]}{'...' if len(result.content) > 500 else ''}</p>
                <span class="timestamp">📅 {timestamp}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show graph relations if available
        if result.graph_relations:
            st.markdown("**Graph Relations:**")
            for relation in result.graph_relations[:3]:  # Show max 3
                st.text(f"  {relation.source} --[{relation.relationship}]--> {relation.destination}")


def display_search_with_answer_results(query: str, result: dict, latency: float):
    """Display search results with AI-generated answer."""
    st.markdown("---")
    timings = result.get("timings", {}) or {}
    server_timings = timings.get("server", {}) or {}
    client_timings = timings.get("client", {}) or {}
    displayed_latency = client_timings.get("round_trip", latency)

    # Query summary
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### 📝 Query: \"{query}\"")
    with col2:
        st.markdown(f"<div style='text-align: right;'>{displayed_latency:.1f}ms</div>", unsafe_allow_html=True)

    timing_metrics = [
        ("客户端总耗时", client_timings.get("round_trip")),
        ("服务端总耗时", server_timings.get("request_total")),
        ("实例初始化", server_timings.get("instance_init")),
        ("线程等待", server_timings.get("thread_wait")),
        ("Search", server_timings.get("search")),
        ("LLM", server_timings.get("llm")),
        ("网络/客户端开销", client_timings.get("network_overhead")),
    ]
    metric_columns = st.columns(len(timing_metrics))
    for col, (label, value) in zip(metric_columns, timing_metrics):
        with col:
            if isinstance(value, (int, float)):
                st.metric(label, f"{value:.1f}ms")
            else:
                st.metric(label, "N/A")

    # AI Answer
    answer = result.get("answer", "")
    if answer:
        st.markdown(f"""
        <div class="answer-box">
            <div class="answer-label">🤖 AI Answer</div>
            <div class="answer-text">{answer}</div>
        </div>
        """, unsafe_allow_html=True)

    # Relations
    relations = result.get("relations", [])
    if relations:
        st.markdown("### 🔗 Graph Relations")
        for relation in relations[:5]:  # Show max 5
            source = relation.get("source", "")
            rel_type = relation.get("relationship", "")
            dest = relation.get("destination", "")
            st.text(f"  {source} --[{rel_type}]--> {dest}")

    # Raw results
    raw_results = result.get("raw_results", [])
    if raw_results:
        st.markdown("### 📋 Source Memories")

        for i, result in enumerate(raw_results, 1):
            # Extract timestamp from metadata
            timestamp = result.metadata.get("timestamp", "N/A")
            if timestamp and len(timestamp) > 10:
                timestamp = timestamp[:10]

            st.markdown(f"""
            <div class="result-card">
                <div class="header">
                    <span class="system-name">Memory #{i}</span>
                    <span class="latency">Score: {result.score:.3f}</span>
                </div>
                <div class="result-item">
                    <p>{result.content[:300]}{'...' if len(result.content) > 300 else ''}</p>
                    <span class="timestamp">📅 {timestamp}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ============================================
# Graph Page
# ============================================
def render_graph_page():
    """Render graph visualization page."""
    st.markdown("""
    <div class="main-header">
        <h1>🕸️ Knowledge Graph</h1>
        <p>Visualize entity relationships</p>
    </div>
    """, unsafe_allow_html=True)

    # Check if client exists
    if not st.session_state.remote_client:
        st.warning("⚠️ Please import data first from the 'Import' page")
        return

    if st.session_state.indexed_count == 0:
        st.warning("⚠️ No memories indexed. Please import data first.")
        return

    try:
        # Get graph data
        graph_data = st.session_state.remote_client.get_graph_data(
            uid=st.session_state.current_uid
        )

        # Display summary
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Entities", graph_data.node_count)
        with col2:
            st.metric("Relations", graph_data.edge_count)

        if graph_data.node_count == 0:
            st.info("📊 No graph data available yet. Graph entities are extracted during memory import.")
            return

        # Display entities
        st.markdown("---")
        st.markdown("### 🏷️ Entities")

        # Group by type
        entities_by_type: dict[str, list] = {}
        for entity in graph_data.nodes[:50]:  # Limit to 50
            entity_type = entity.type or "Unknown"
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity.name)

        for entity_type, entities in sorted(entities_by_type.items()):
            with st.expander(f"{entity_type} ({len(entities)})"):
                st.write(", ".join(entities))

        # Display relations
        st.markdown("---")
        st.markdown("### 🔗 Relations")

        for i, relation in enumerate(graph_data.edges[:50], 1):
            st.text(f"{i}. {relation.source} --[{relation.relation_type}]--> {relation.target}")

    except Exception as e:
        st.error(f"❌ Failed to load graph data: {str(e)}")


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
        ["📁 Upload", "🚀 Import", "🔍 Search", "🕸️ Graph"],
        icons=["upload", "database-add", "search", "diagram-3"],
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
    elif page == "🕸️ Graph":
        render_graph_page()


if __name__ == "__main__":
    main()
