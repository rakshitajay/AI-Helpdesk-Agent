"""
sidebar.py
----------
Left sidebar: branding, nav menu, chat session list, theme toggle.
"""

import streamlit as st
from components.api_client import get_sessions, delete_session


def show_sidebar():
    with st.sidebar:
        # ── Branding ──────────────────────────────────────────
        st.markdown("""
        <div style="padding: 16px 0 8px 0;">
            <div class="brand-title">🤖 AI Helpdesk</div>
            <div class="brand-sub">RAG Support Assistant</div>
        </div>
        <hr style="border-color:#30363d; margin: 8px 0 16px;">
        """, unsafe_allow_html=True)

        # ── User Info ─────────────────────────────────────────
        username = st.session_state.get("username", "User")
        role = st.session_state.get("role", "user")
        role_badge = "👑 Admin" if role == "admin" else "👤 User"
        st.markdown(f"""
        <div style="padding:8px; border-radius:8px; background:rgba(255,255,255,0.05);
                    margin-bottom:16px; font-size:13px;">
            <b>{username}</b> &nbsp; <span style="opacity:0.6;">{role_badge}</span>
        </div>
        """, unsafe_allow_html=True)

        # ── New Chat ──────────────────────────────────────────
        if st.button("✏️  New Chat", use_container_width=True, key="new_chat_btn"):
            st.session_state.current_session_id = None
            st.session_state.chat_messages = []
            st.session_state.current_page = "chat"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Navigation ────────────────────────────────────────
        nav_items = [
            ("💬", "Chat", "chat"),
            ("📄", "Documents", "documents"),
            ("👤", "Profile", "profile"),
        ]
        if role == "admin":
            nav_items.append(("⚙️", "Admin Panel", "admin"))

        for icon, label, page in nav_items:
            active = st.session_state.current_page == page
            if st.button(
                f"{icon}  {label}",
                use_container_width=True,
                key=f"nav_{page}",
                type="primary" if active else "secondary",
            ):
                st.session_state.current_page = page
                st.rerun()

        st.markdown("<hr style='border-color:#30363d; margin: 16px 0;'>", unsafe_allow_html=True)

        # ── Chat History ──────────────────────────────────────
        st.markdown("**💬 Recent Chats**")
        sessions_data, _ = get_sessions()
        if sessions_data:
            for s in sessions_data[:15]:
                sid = s["session_id"]
                title = s.get("title") or "Untitled Chat"
                title_short = title[:28] + "…" if len(title) > 28 else title
                count = s.get("message_count", 0)
                is_active = sid == st.session_state.current_session_id

                col_a, col_b = st.columns([5, 1])
                with col_a:
                    if st.button(
                        f"{'▶ ' if is_active else ''}{title_short}",
                        key=f"session_{sid}",
                        use_container_width=True,
                        help=f"{count} messages"
                    ):
                        st.session_state.current_session_id = sid
                        st.session_state.current_page = "chat"
                        # Load history
                        from components.api_client import get_session_history
                        hist, _ = get_session_history(sid)
                        if hist:
                            st.session_state.chat_messages = hist.get("messages", [])
                        st.rerun()
                with col_b:
                    if st.button("🗑", key=f"del_{sid}", help="Delete session"):
                        delete_session(sid)
                        if st.session_state.current_session_id == sid:
                            st.session_state.current_session_id = None
                            st.session_state.chat_messages = []
                        st.rerun()
        else:
            st.markdown(
                "<div style='opacity:0.4; font-size:12px;'>No conversations yet.</div>",
                unsafe_allow_html=True
            )

        # ── Bottom Controls ───────────────────────────────────
        st.markdown("<br>" * 2, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            current_theme = st.session_state.get("theme", "dark")
            if st.button("🌙" if current_theme == "light" else "☀️", use_container_width=True,
                         help="Toggle theme"):
                st.session_state.theme = "light" if current_theme == "dark" else "dark"
                st.rerun()
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
