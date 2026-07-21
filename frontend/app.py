"""
app.py
------
Streamlit entry point.
Handles:
  - Session state initialization
  - JWT token management (stored in st.session_state)
  - Page routing based on auth state
  - Theme (dark/light) toggle
"""

import streamlit as st
from components.auth_ui import show_login_page
from components.sidebar import show_sidebar
from pages.chat_page import show_chat_page
from pages.admin_page import show_admin_page
from pages.profile_page import show_profile_page
from pages.documents_page import show_documents_page

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="AI Helpdesk Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        "token": None,
        "user_id": None,
        "username": None,
        "role": None,
        "current_page": "chat",
        "current_session_id": None,
        "chat_messages": [],
        "theme": "dark",
        "language": "en",
        "sessions": [],
         "selected_document_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_theme():
    """Inject CSS for dark/light theme and ChatGPT-style interface."""
    is_dark = st.session_state.get("theme", "dark") == "dark"

    bg_color = "#0d1117" if is_dark else "#ffffff"
    sidebar_bg = "#161b22" if is_dark else "#f6f8fa"
    card_bg = "#1c2128" if is_dark else "#f0f2f5"
    text_color = "#e6edf3" if is_dark else "#1c1e21"
    border_color = "#30363d" if is_dark else "#d0d7de"
    accent = "#2ea043"
    user_bubble = "#1f4068" if is_dark else "#dcf8c6"
    ai_bubble = "#1c2128" if is_dark else "#f0f2f5"
    input_bg = "#21262d" if is_dark else "#ffffff"

    st.markdown(f"""
    <style>
    /* ── Global Reset ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        background-color: {bg_color};
        color: {text_color};
    }}

    /* ── Main Container ── */
    .main .block-container {{
        padding: 1rem 2rem;
        max-width: 1400px;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        border-right: 1px solid {border_color};
        padding-top: 0;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding: 1rem;
    }}

    /* ── Chat Bubbles ── */
    .user-message {{
        background: {user_bubble};
        padding: 12px 16px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0 8px 15%;
        max-width: 80%;
        float: right;
        clear: both;
        font-size: 14px;
        line-height: 1.5;
        word-wrap: break-word;
    }}

    .ai-message {{
        background: {ai_bubble};
        border: 1px solid {border_color};
        padding: 14px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 15% 8px 0;
        max-width: 80%;
        float: left;
        clear: both;
        font-size: 14px;
        line-height: 1.6;
        word-wrap: break-word;
    }}

    .chat-container {{
        min-height: 400px;
        max-height: 62vh;
        overflow-y: auto;
        padding: 16px;
        border: 1px solid {border_color};
        border-radius: 12px;
        background: {bg_color};
        margin-bottom: 12px;
    }}

    /* ── Source Citation Card ── */
    .source-card {{
        background: {card_bg};
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 12px;
        border-left: 3px solid {accent};
    }}

    .confidence-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 8px;
    }}

    .confidence-high {{ background: #1a472a; color: #4ade80; }}
    .confidence-med  {{ background: #3d2b00; color: #fbbf24; }}
    .confidence-low  {{ background: #3d1515; color: #f87171; }}

    /* ── Stat Cards ── */
    .stat-card {{
        background: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }}
    .stat-number {{
        font-size: 32px;
        font-weight: 700;
        color: {accent};
    }}
    .stat-label {{
        font-size: 13px;
        color: {text_color};
        opacity: 0.7;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: {accent};
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }}
    .stButton > button:hover {{
        background: #3fb950;
        transform: translateY(-1px);
    }}

    /* ── Input ── */
    .stTextInput > div > input,
    .stTextArea > div > textarea {{
        background: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif;
    }}

    /* ── Hide Streamlit default chrome ── */
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}

    /* ── Logo & Branding ── */
    .brand-title {{
        font-size: 22px;
        font-weight: 700;
        color: {accent};
        letter-spacing: -0.5px;
    }}
    .brand-sub {{
        font-size: 11px;
        opacity: 0.5;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    /* ── Typing animation ── */
    .typing-indicator {{
        display: flex;
        gap: 4px;
        padding: 10px 16px;
        width: fit-content;
    }}
    .typing-dot {{
        width: 8px;
        height: 8px;
        background: {accent};
        border-radius: 50%;
        animation: typing-bounce 1.2s infinite;
    }}
    .typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
    .typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
    @keyframes typing-bounce {{
        0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }}
        30% {{ transform: translateY(-6px); opacity: 1; }}
    }}

    /* ── Suggested Questions ── */
    .suggested-btn {{
        background: {card_bg};
        border: 1px solid {border_color};
        border-radius: 20px;
        padding: 6px 14px;
        font-size: 12px;
        cursor: pointer;
        display: inline-block;
        margin: 4px;
        transition: all 0.2s;
    }}
    .suggested-btn:hover {{
        border-color: {accent};
        color: {accent};
    }}

    /* ── Session history item ── */
    .session-item {{
        padding: 8px 12px;
        border-radius: 8px;
        cursor: pointer;
        margin: 2px 0;
        font-size: 13px;
        border: 1px solid transparent;
        transition: all 0.15s;
    }}
    .session-item:hover {{
        background: {card_bg};
        border-color: {border_color};
    }}
    .session-active {{
        background: {card_bg};
        border-color: {accent} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def main():
    init_session_state()
    apply_theme()

    # ── Not logged in → show auth page ───────────────────────
    if not st.session_state.token:
        show_login_page()
        return

    # ── Logged in → show sidebar + page router ────────────────
    show_sidebar()
    st.write("Current page:", st.session_state.current_page)

    page = st.session_state.current_page

    if page == "chat":
        show_chat_page()
    elif page == "documents":
        show_documents_page()
    elif page == "profile":
        show_profile_page()
    elif page == "admin" and st.session_state.role == "admin":
        show_admin_page()
    else:
        show_chat_page()


if __name__ == "__main__":
    main()
