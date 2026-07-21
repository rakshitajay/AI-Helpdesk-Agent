"""
frontend/components/ui_helpers.py
----------------------------------
Shared Streamlit UI components used across pages:
  - CSS injection for custom dark/light theme
  - Typing animation effect
  - Confidence score badge
  - Source citation cards
  - PDF export of chat history
"""

import io
import json
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st
from fpdf import FPDF


# ══════════════════════════════════════════════════════════════════════════════
# THEME / CSS
# ══════════════════════════════════════════════════════════════════════════════

DARK_CSS = """
<style>
/* ── Root variables ── */
:root {
  --bg-primary:    #0d1117;
  --bg-secondary:  #161b22;
  --bg-card:       #21262d;
  --accent:        #58a6ff;
  --accent-hover:  #79b8ff;
  --text-primary:  #e6edf3;
  --text-muted:    #8b949e;
  --border:        #30363d;
  --success:       #3fb950;
  --warning:       #d29922;
  --danger:        #f85149;
  --user-bubble:   #1f4e79;
  --ai-bubble:     #21262d;
  --radius:        12px;
  --font:          'Inter', 'Segoe UI', sans-serif;
}

/* ── Global resets ── */
.stApp { background: var(--bg-primary); color: var(--text-primary); font-family: var(--font); }
.block-container { padding: 1.5rem 2rem; max-width: 1200px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--bg-secondary) !important;
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .stMarkdown { color: var(--text-primary); }

/* ── Chat bubbles ── */
.chat-message { display: flex; gap: 12px; margin: 12px 0; align-items: flex-start; }
.chat-message.user  { flex-direction: row-reverse; }
.chat-message .avatar {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.chat-message.user  .avatar { background: var(--accent); }
.chat-message.ai    .avatar { background: var(--bg-card); border: 1px solid var(--border); }
.chat-message .bubble {
  max-width: 78%; padding: 12px 16px; border-radius: var(--radius);
  line-height: 1.6; font-size: 0.95rem;
}
.chat-message.user .bubble {
  background: var(--user-bubble); color: #fff;
  border-top-right-radius: 2px;
}
.chat-message.ai .bubble {
  background: var(--ai-bubble); color: var(--text-primary);
  border: 1px solid var(--border); border-top-left-radius: 2px;
}

/* ── Confidence badge ── */
.confidence-badge {
  display: inline-block; padding: 2px 10px; border-radius: 20px;
  font-size: 0.75rem; font-weight: 600; margin-top: 6px;
}
.confidence-high   { background: #1a3a20; color: var(--success); }
.confidence-medium { background: #3a2d0a; color: var(--warning); }
.confidence-low    { background: #3a1212; color: var(--danger); }

/* ── Source card ── */
.source-card {
  background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 14px; margin: 6px 0;
  font-size: 0.82rem; color: var(--text-muted);
}
.source-card .source-title { color: var(--accent); font-weight: 600; margin-bottom: 4px; }

/* ── Typing indicator ── */
.typing-indicator { display: flex; gap: 5px; align-items: center; padding: 8px 0; }
.typing-dot {
  width: 8px; height: 8px; background: var(--text-muted);
  border-radius: 50%; animation: bounce 1.3s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.15s; }
.typing-dot:nth-child(3) { animation-delay: 0.30s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30%            { transform: translateY(-8px); }
}

/* ── Stat card ── */
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px;
  text-align: center; transition: border-color .2s;
}
.stat-card:hover { border-color: var(--accent); }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 0.85rem; color: var(--text-muted); margin-top: 4px; }

/* ── Input area ── */
.stTextInput > div > div > input,
.stTextArea textarea {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
}

/* ── Buttons ── */
.stButton > button {
  background: var(--accent) !important; color: #000 !important;
  border: none !important; border-radius: 8px !important;
  font-weight: 600 !important; transition: background .2s !important;
}
.stButton > button:hover { background: var(--accent-hover) !important; }

/* ── Scrollable chat container ── */
.chat-container { max-height: 600px; overflow-y: auto; padding: 8px; }
</style>
"""

LIGHT_CSS = """
<style>
:root {
  --bg-primary: #ffffff; --bg-secondary: #f6f8fa; --bg-card: #f1f3f5;
  --accent: #0969da; --text-primary: #24292f; --text-muted: #57606a;
  --border: #d0d7de; --success: #1a7f37; --warning: #9a6700;
  --danger: #cf222e; --user-bubble: #dbeafe; --ai-bubble: #f6f8fa;
}
.stApp { background: var(--bg-primary); color: var(--text-primary); }
[data-testid="stSidebar"] { background: var(--bg-secondary) !important; }
.chat-message.user .bubble { background: var(--user-bubble); color: var(--text-primary); }
.chat-message.ai .bubble { background: var(--ai-bubble); border: 1px solid var(--border); }
.stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
.source-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
</style>
"""


def inject_css(dark_mode: bool = True) -> None:
    """Inject theme CSS into the Streamlit page."""
    st.markdown(DARK_CSS if dark_mode else LIGHT_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CHAT COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def render_user_message(content: str) -> None:
    """Render a user chat bubble."""
    st.markdown(
        f"""<div class="chat-message user">
              <div class="avatar">👤</div>
              <div class="bubble">{content}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def render_ai_message(
    content: str,
    confidence: Optional[float] = None,
    sources: Optional[List[Dict]] = None,
) -> None:
    """Render an AI response bubble with confidence badge and sources."""
    # Confidence badge
    badge_html = ""
    if confidence is not None:
        pct = int(confidence * 100)
        cls = "high" if pct >= 70 else "medium" if pct >= 40 else "low"
        badge_html = f'<div class="confidence-badge confidence-{cls}">Confidence: {pct}%</div>'

    st.markdown(
        f"""<div class="chat-message ai">
              <div class="avatar">🤖</div>
              <div class="bubble">
                {content}
                {badge_html}
              </div>
            </div>""",
        unsafe_allow_html=True,
    )

    # Source citations
    if sources:
        with st.expander(f"📚 {len(sources)} Source(s) used", expanded=False):
            for i, src in enumerate(sources, 1):
                filename = src.get("filename", "Unknown")
                page = src.get("page_number")
                page_str = f" · Page {page}" if page else ""
                score = src.get("relevance_score", 0)
                preview = src.get("content_preview", "")
                st.markdown(
                    f"""<div class="source-card">
                          <div class="source-title">📄 {filename}{page_str}
                            &nbsp;·&nbsp; {int(score * 100)}% relevant
                          </div>
                          <div>{preview}</div>
                        </div>""",
                    unsafe_allow_html=True,
                )


def render_typing_indicator() -> None:
    """Show animated typing dots while waiting for the AI response."""
    st.markdown(
        """<div class="chat-message ai">
             <div class="avatar">🤖</div>
             <div class="bubble">
               <div class="typing-indicator">
                 <div class="typing-dot"></div>
                 <div class="typing-dot"></div>
                 <div class="typing-dot"></div>
               </div>
             </div>
           </div>""",
        unsafe_allow_html=True,
    )


def render_stat_card(label: str, value: str) -> None:
    """A simple stat card for the dashboard."""
    st.markdown(
        f"""<div class="stat-card">
              <div class="stat-value">{value}</div>
              <div class="stat-label">{label}</div>
            </div>""",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def export_chat_to_pdf(messages: List[Dict], session_id: str) -> bytes:
    """
    Convert chat history to a downloadable PDF.

    Args:
        messages: List of message dicts with 'role', 'content', 'created_at'.
        session_id: Session identifier for the PDF title.

    Returns:
        PDF as bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AI Helpdesk – Chat Export", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Session: {session_id}", ln=True)
    pdf.cell(0, 8, f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        ts = msg.get("created_at", "")

        # Role header
        pdf.set_font("Helvetica", "B", 10)
        label = "You" if role == "user" else "AI Assistant"
        pdf.cell(0, 8, f"{label}  [{ts[:19]}]", ln=True)

        # Message body
        pdf.set_font("Helvetica", "", 10)
        # Encode to latin-1 to avoid FPDF unicode issues
        safe_content = content.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_content)
        pdf.ln(4)

    return bytes(pdf.output())
