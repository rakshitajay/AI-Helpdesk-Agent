"""
frontend/pages/history_page.py
------------------------------
Displays all previous chat sessions and allows the user
to view message history.
"""

import streamlit as st

from components.api_client import (
    get_sessions,
    get_session_history,
)


def render_history_page():
    st.title("📜 Chat History")
    st.markdown("---")

    # -------------------------------
    # Load all chat sessions
    # -------------------------------
    data, error = get_sessions()

    if error:
        st.error(error)
        return

    if not data:
        st.info("No previous conversations found.")
        return

    st.subheader("Previous Conversations")

    for session in data:

        session_id = session.get("session_id")
        title = session.get("title", "New Chat")
        updated = session.get("updated_at", "")
        count = session.get("message_count", 0)

        with st.expander(f"💬 {title} ({count} messages)"):

            st.caption(f"Updated: {updated}")

            if st.button(
                "Load Conversation",
                key=f"load_{session_id}"
            ):

                history, err = get_session_history(session_id)

                if err:
                    st.error(err)

                else:
                    st.session_state[f"history_{session_id}"] = history

            if f"history_{session_id}" in st.session_state:

                messages = st.session_state[f"history_{session_id}"]

                for msg in messages:

                    if msg["role"] == "user":

                        st.chat_message("user").write(
                            msg["content"]
                        )

                    else:

                        st.chat_message("assistant").write(
                            msg["content"]
                        )

                        if msg.get("sources"):

                            with st.expander("📄 Sources"):

                                for src in msg["sources"]:

                                    st.markdown(
                                        f"""
**Document:** {src.get("document_name","Unknown")}

**Page:** {src.get("page_number","-")}

**Score:** {src.get("relevance_score",0):.2f}

> {src.get("chunk_text","")}
"""
                                    )