"""
admin_page.py
-------------
Admin dashboard with:
  - Summary stat cards
  - Daily query chart
  - Top queries table
  - User management table
  - Document index rebuild
  - Query logs viewer
"""

import streamlit as st
import pandas as pd
from components.api_client import (
    get_analytics, get_users, toggle_user,
    rebuild_index, get_vector_stats, get_query_logs
)


def show_stat_card(label: str, value, icon: str):
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:28px;">{icon}</div>
        <div class="stat-number">{value}</div>
        <div class="stat-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def show_admin_page():
    st.markdown("## ⚙️ Admin Dashboard")

    tabs = st.tabs(["📊 Analytics", "👥 Users", "🔧 Vector DB", "📋 Query Logs"])

    # ── Tab 1: Analytics ──────────────────────────────────────
    with tabs[0]:
        data, error = get_analytics()
        if error:
            st.error(f"Analytics error: {error}")
        else:
            summary = data["summary"]

            # Stat cards
            cols = st.columns(6)
            stats = [
                ("Total Users", summary["total_users"], "👥"),
                ("Documents", summary["total_documents"], "📄"),
                ("Total Queries", summary["total_queries"], "💬"),
                ("Sessions", summary["total_sessions"], "🗂️"),
                ("Avg Confidence", f"{summary['avg_confidence_score']:.0%}", "🎯"),
                ("Avg Response", f"{summary['avg_response_time_ms']:.0f}ms", "⚡"),
            ]
            for col, (label, value, icon) in zip(cols, stats):
                with col:
                    show_stat_card(label, value, icon)

            st.markdown("---")
            col1, col2 = st.columns([3, 2])

            with col1:
                st.markdown("**📈 Daily Queries (Last 7 Days)**")
                daily = data.get("daily_queries", [])
                if daily:
                    df = pd.DataFrame(daily)
                    st.bar_chart(df.set_index("date")["count"])
                else:
                    st.info("No query data yet.")

            with col2:
                st.markdown("**🔥 Top 10 Most Asked Questions**")
                top_qs = data.get("top_queries", [])
                if top_qs:
                    for i, q in enumerate(top_qs[:10], 1):
                        st.markdown(
                            f"`{i:02d}` {q['query'][:55]}{'...' if len(q['query'])>55 else ''} "
                            f"— **{q['count']}x**"
                        )
                else:
                    st.info("No queries logged yet.")

    # ── Tab 2: Users ──────────────────────────────────────────
    with tabs[1]:
        st.markdown("**👥 All Registered Users**")
        users, err = get_users()
        if err:
            st.error(f"Error: {err}")
        elif users:
            for u in users:
                cols = st.columns([2, 2, 1, 1, 1])
                with cols[0]:
                    st.markdown(f"**{u['username']}** ({u.get('full_name','—')})")
                with cols[1]:
                    st.markdown(f"`{u['email']}`")
                with cols[2]:
                    st.markdown(f"{'👑 Admin' if u['role']=='admin' else '👤 User'}")
                with cols[3]:
                    st.markdown("✅ Active" if u['is_active'] else "❌ Inactive")
                with cols[4]:
                    label = "Deactivate" if u['is_active'] else "Activate"
                    if st.button(label, key=f"toggle_{u['id']}"):
                        result, terr = toggle_user(u['id'])
                        if terr:
                            st.error(terr)
                        else:
                            st.rerun()
                st.markdown("<hr style='margin:4px 0;opacity:0.1;'>", unsafe_allow_html=True)

    # ── Tab 3: Vector DB ──────────────────────────────────────
    with tabs[2]:
        st.markdown("**🔧 ChromaDB Vector Store Management**")
        stats, _ = get_vector_stats()
        if stats:
            st.metric("Total Indexed Chunks", stats.get("total_chunks", 0))

        st.markdown("---")
        st.warning("⚠️ Rebuilding the index will re-process all documents. This may take several minutes.")
        if st.button("🔄 Rebuild Entire Vector Index", type="primary"):
            with st.spinner("Rebuilding index... please wait..."):
                result, err = rebuild_index()
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ {result.get('message', 'Index rebuilt.')}")

    # ── Tab 4: Query Logs ─────────────────────────────────────
    with tabs[3]:
        st.markdown("**📋 Recent Query Logs**")
        logs, err = get_query_logs()
        if err:
            st.error(f"Error: {err}")
        elif logs:
            df = pd.DataFrame(logs)[["created_at", "query", "confidence_score",
                                      "response_time_ms", "sources_count", "user_id"]]
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            df["confidence_score"] = df["confidence_score"].apply(
                lambda x: f"{x:.0%}" if x else "—"
            )
            df["response_time_ms"] = df["response_time_ms"].apply(
                lambda x: f"{x:.0f}ms" if x else "—"
            )
            df.columns = ["Time", "Query", "Confidence", "Response Time", "Sources", "User ID"]
            st.dataframe(df, use_container_width=True, height=500)
        else:
            st.info("No query logs yet.")
            # -----------------------------
# Standalone Page Preview
# -----------------------------
if __name__ == "__main__":

    st.set_page_config(
        page_title="AI Helpdesk Admin",
        page_icon="⚙️",
        layout="wide"
    )

    st.title("⚙️ AI Helpdesk Admin Dashboard")

    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("👥 Users", "--")
    c2.metric("📄 Documents", "--")
    c3.metric("💬 Queries", "--")
    c4.metric("⚡ Status", "Ready")

    st.markdown("---")

    st.info(
        "This dashboard is a part of the AI Helpdesk Agent.\n"
        "Please login through the main application to access live analytics."
    )

    if "token" in st.session_state:
        show_admin_page()
       

