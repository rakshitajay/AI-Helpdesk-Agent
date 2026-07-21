"""
chat_page.py
------------
Main ChatGPT-style chat interface.
Features:
  - Scrollable message history with user/AI bubbles
  - Typing animation while waiting for response
  - Source citations with relevance scores
  - Confidence badge
  - Suggested follow-up questions
  - Language selector
  - Export chat to PDF
  - Voice input placeholder
"""

import time
import streamlit as st

from components.api_client import (
    ask_question, 
    export_chat_pdf,
    list_documents,
)
LANGUAGES = {
    "en": "🇬🇧 English", "hi": "🇮🇳 Hindi",
    "es": "🇪🇸 Spanish", "fr": "🇫🇷 French",
    "de": "🇩🇪 German",  "ar": "🇸🇦 Arabic",
    "zh": "🇨🇳 Chinese", "ja": "🇯🇵 Japanese",
    "pt": "🇧🇷 Portuguese", "ru": "🇷🇺 Russian",
}


def confidence_badge(score: float) -> str:
    pct = int(score * 100)
    if score >= 0.75:
        cls, label = "confidence-high", "High"
    elif score >= 0.45:
        cls, label = "confidence-med", "Medium"
    else:
        cls, label = "confidence-low", "Low"
    return f'<span class="confidence-badge {cls}">🎯 {label} {pct}%</span>'


def render_message(msg: dict):
    """Render a single chat message bubble."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    sources = msg.get("sources", [])
    conf = msg.get("confidence_score")

    if role == "user":
        st.markdown(
            f'<div class="user-message">{content}</div><div style="clear:both;"></div>',
            unsafe_allow_html=True
        )
    else:
        badge = confidence_badge(conf) if conf is not None else ""
        st.markdown(
            f'<div class="ai-message">'
            f'<div style="font-size:11px; opacity:0.5; margin-bottom:6px;">🤖 AI Assistant {badge}</div>'
            f'{content}'
            f'</div><div style="clear:both;"></div>',
            unsafe_allow_html=True
        )

        # Source citations
        if sources:
            with st.expander(f"📚 {len(sources)} Source(s) Used", expanded=False):
                for i, src in enumerate(sources, 1):
                    score = src.get("relevance_score", 0)
                    page = src.get("page_number")
                    page_str = f" | Page {page}" if page is not None else ""
                    st.markdown(f"""
                    <div class="source-card">
                        <b>📄 {src.get('document_name', 'Unknown')}</b>{page_str}
                        &nbsp;· Relevance: <b>{score:.0%}</b><br>
                        <span style="opacity:0.7; font-size:11px;">"{src.get('chunk_text', '')[:200]}..."</span>
                    </div>
                    """, unsafe_allow_html=True)


def show_welcome():
    """Empty state / welcome screen."""
    st.markdown("""
    <div style="text-align:center; padding: 80px 20px;">
        <div style="font-size:64px; margin-bottom:16px;">🤖</div>
        <h2 style="font-weight:600; margin-bottom:8px;">How can I help you today?</h2>
        <p style="opacity:0.5; max-width:400px; margin:0 auto; font-size:14px;">
            Ask me anything about the uploaded documents.<br>
            I'll find the answer and show you exactly where it came from.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**💡 Try asking:**")
    sample_questions = [
        "What are the main topics covered in the documents?",
        "Summarize the key points from the uploaded files.",
        "What are the requirements mentioned?",
        "Explain the process described in the documents.",
    ]
    cols = st.columns(2)
    for i, q in enumerate(sample_questions):
        with cols[i % 2]:
            if st.button(q, key=f"sample_{i}", use_container_width=True):
                st.session_state["pending_question"] = q
                st.rerun()


def show_chat_page():
    st.success("CHAT PAGE IS RUNNING")
    # ── Header ────────────────────────────────────────────────
    col_title, col_lang, col_export = st.columns([4, 1.5, 1])
    with col_title:
        session_id = st.session_state.get("current_session_id")
        title = "New Conversation" if not session_id else "Active Conversation"
        st.markdown(f"## 💬 {title}")
    with col_lang:
        selected_lang = st.selectbox(
            "Language",
            options=list(LANGUAGES.keys()),
            format_func=lambda x: LANGUAGES[x],
            index=list(LANGUAGES.keys()).index(st.session_state.get("language", "en")),
            label_visibility="collapsed",
            key="lang_select"
        )
        st.session_state.language = selected_lang
    with col_export:
        if session_id:
            if st.button("⬇️ PDF", help="Download chat as PDF"):
                with st.spinner("Generating PDF..."):
                    pdf_bytes = export_chat_pdf(session_id)
                if pdf_bytes:
                    st.download_button(
                        "📥 Download",
                        data=pdf_bytes,
                        file_name=f"chat_{session_id[:8]}.pdf",
                        mime="application/pdf",
                        key="dl_pdf"
                    )
                else:
                    st.error("PDF generation failed.")

    # ── Messages ──────────────────────────────────────────────
    messages = st.session_state.get("chat_messages", [])

    if not messages:
        show_welcome()
    else:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in messages:
            render_message(msg)
        st.markdown('</div>', unsafe_allow_html=True)

        # Suggested follow-ups (from last AI message)
        last_ai = next(
            (m for m in reversed(messages) if m.get("role") == "assistant"),
            None
        )
        if last_ai and last_ai.get("suggested_questions"):
            st.markdown("**💡 You might also ask:**")
            cols = st.columns(len(last_ai["suggested_questions"]))
            for i, sq in enumerate(last_ai["suggested_questions"]):
                with cols[i]:
                    if st.button(sq, key=f"sq_{i}_{len(messages)}", use_container_width=True):
                        st.session_state["pending_question"] = sq
                        st.rerun()

    # ── Input Area ────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_input,  col_send = st.columns(
        [10,2],
         vertical_alignment="center")

    pending = st.session_state.pop("pending_question", None)

    with col_input:
        user_input = st.text_area(
            "Ask a question...",
            value=pending or "",
            height=68,
            placeholder="Type your question here... (Shift+Enter for new line)",
            label_visibility="collapsed",
            key="chat_input",
        )
    

    
    with col_send:
        st.markdown("<br>", unsafe_allow_html=True)
        send_clicked = st.button("Send →", use_container_width=True, type="primary")


    # ── Submit logic ──────────────────────────────────────────
    question = (pending or user_input or "").strip()
    if (send_clicked or pending) and question:
        # Append user message immediately
        st.session_state.chat_messages.append({
            "role": "user",
            "content": question,
        })

        # Show typing animation
        typing_placeholder = st.empty()
        typing_placeholder.markdown("""
        <div class="ai-message" style="width:80px;">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Call API
        st.write("Selected document:", st.session_state.get("selected_document_id"))
        data, error = ask_question(
            question=question,
            session_id=st.session_state.get("current_session_id"),
            language=st.session_state.get("language", "en"),
            document_id=st.session_state.get("selected_document_id"),
        )

        typing_placeholder.empty()

        if error:
            st.error(f"❌ {error}")
            st.session_state.chat_messages.pop()  # Remove user msg on error
        else:
            # Update session ID
            st.session_state.current_session_id = data.get("session_id")

            # Append AI message
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": data.get("answer", ""),
                "sources": data.get("sources", []),
                "confidence_score": data.get("confidence_score", 0),
                "suggested_questions": data.get("suggested_questions", []),
            })

            response_ms = data.get("response_time_ms", 0)
            st.toast(f"✅ Answered in {response_ms:.0f}ms", icon="⚡")

        st.rerun()
