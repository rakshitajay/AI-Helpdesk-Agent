"""
auth_ui.py
----------
Login and Registration UI pages.
Stores JWT token and user info in st.session_state on success.
"""

import streamlit as st
from components.api_client import login_user, register_user

LANGUAGES = {
    "en": "🇬🇧 English",
    "hi": "🇮🇳 Hindi",
    "es": "🇪🇸 Spanish",
    "fr": "🇫🇷 French",
    "de": "🇩🇪 German",
    "ar": "🇸🇦 Arabic",
    "zh": "🇨🇳 Chinese",
    "ja": "🇯🇵 Japanese",
}


def show_login_page():
    """Full-page login / register form with branding."""
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px 0;">
            <div style="font-size:48px;">🤖</div>
            <h1 style="font-size:28px; font-weight:700; margin:8px 0 4px;">AI Helpdesk Agent</h1>
            <p style="opacity:0.5; font-size:13px; letter-spacing:1px; text-transform:uppercase;">
                RAG-Powered Support Assistant
            </p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🔐 Sign In", "✨ Create Account"])

        with tab_login:
            _render_login_form()

        with tab_register:
            _render_register_form()

        st.markdown("""
        <div style="text-align:center; margin-top:30px; opacity:0.4; font-size:11px;">
            Powered by Google Gemini 2.5 Flash + ChromaDB + LangChain
        </div>
        """, unsafe_allow_html=True)


def _render_login_form():
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("📧 Email", placeholder="you@example.com")
        password = st.text_input("🔒 Password", type="password", placeholder="Your password")
        language = st.selectbox("🌐 Language", options=list(LANGUAGES.keys()),
                                format_func=lambda x: LANGUAGES[x])
        submit = st.form_submit_button("Sign In →", use_container_width=True)

    if submit:
        if not email or not password:
            st.error("Please enter both email and password.")
            return

        with st.spinner("Authenticating..."):
            data, error = login_user(email, password)

        if error:
            st.error(f"❌ {error}")
        else:
            st.session_state.token = data["access_token"]
            st.session_state.user_id = data["user_id"]
            st.session_state.username = data["username"]
            st.session_state.role = data["role"]
            st.session_state.language = language
            st.success(f"✅ Welcome back, {data['username']}!")
            st.rerun()


def _render_register_form():
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("register_form"):
        full_name = st.text_input("👤 Full Name", placeholder="John Doe")
        username = st.text_input("🏷️ Username", placeholder="johndoe")
        email = st.text_input("📧 Email", placeholder="you@example.com")
        password = st.text_input("🔒 Password", type="password",
                                  placeholder="Min 8 chars, 1 uppercase, 1 number")
        confirm = st.text_input("🔒 Confirm Password", type="password")
        submit = st.form_submit_button("Create Account →", use_container_width=True)

    if submit:
        if password != confirm:
            st.error("Passwords do not match.")
            return
        if not all([full_name, username, email, password]):
            st.error("Please fill in all fields.")
            return

        with st.spinner("Creating account..."):
            data, error = register_user(email, username, password, full_name)

        if error:
            st.error(f"❌ {error}")
        else:
            st.success("✅ Account created! Please sign in.")
