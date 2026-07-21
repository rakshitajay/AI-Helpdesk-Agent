"""
profile_page.py
---------------
User profile management: view info, change name, change language preference.
"""

import streamlit as st
from components.api_client import get_profile, update_profile

LANGUAGES = {
    "en": "🇬🇧 English", "hi": "🇮🇳 Hindi",
    "es": "🇪🇸 Spanish", "fr": "🇫🇷 French",
    "de": "🇩🇪 German",  "ar": "🇸🇦 Arabic",
    "zh": "🇨🇳 Chinese", "ja": "🇯🇵 Japanese",
    "pt": "🇧🇷 Portuguese", "ru": "🇷🇺 Russian",
}


def show_profile_page():
    st.markdown("## 👤 My Profile")

    profile, error = get_profile()
    if error:
        st.error(f"Could not load profile: {error}")
        return

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(f"""
        <div style="text-align:center; padding:24px; background:rgba(255,255,255,0.05);
                    border-radius:16px; border:1px solid #30363d;">
            <div style="font-size:72px;">{'👑' if profile['role']=='admin' else '👤'}</div>
            <h3 style="margin:8px 0 4px;">{profile['username']}</h3>
            <p style="opacity:0.5; font-size:13px; margin:0;">{profile['role'].upper()}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Account Details**")
        st.markdown(f"📧 `{profile['email']}`")
        st.markdown(f"📅 Joined: `{profile['created_at'][:10]}`")
        last_login = profile.get("last_login")
        if last_login:
            st.markdown(f"🕐 Last login: `{last_login[:10]}`")
        active = "✅ Active" if profile.get("is_active") else "❌ Inactive"
        st.markdown(f"Status: {active}")

    with col2:
        st.markdown("### ✏️ Update Profile")
        with st.form("update_profile_form"):
            new_name = st.text_input(
                "Full Name",
                value=profile.get("full_name") or "",
                placeholder="Your full name"
            )
            current_lang = profile.get("preferred_language", "en")
            new_lang = st.selectbox(
                "Preferred Language",
                options=list(LANGUAGES.keys()),
                format_func=lambda x: LANGUAGES[x],
                index=list(LANGUAGES.keys()).index(current_lang) if current_lang in LANGUAGES else 0
            )
            save = st.form_submit_button("💾 Save Changes", use_container_width=True)

        if save:
            with st.spinner("Updating..."):
                result, err = update_profile(
                    full_name=new_name if new_name else None,
                    language=new_lang
                )
            if err:
                st.error(f"❌ {err}")
            else:
                st.session_state.language = new_lang
                st.success("✅ Profile updated successfully!")

        st.markdown("---")
        st.markdown("### 🎨 Preferences")
        current_theme = st.session_state.get("theme", "dark")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            if st.button("🌙 Dark Mode",
                         type="primary" if current_theme == "dark" else "secondary",
                         use_container_width=True):
                st.session_state.theme = "dark"
                st.rerun()
        with col_t2:
            if st.button("☀️ Light Mode",
                         type="primary" if current_theme == "light" else "secondary",
                         use_container_width=True):
                st.session_state.theme = "light"
                st.rerun()
