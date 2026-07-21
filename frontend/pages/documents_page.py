"""
documents_page.py
-----------------
Document management page for users and admins.
- Upload PDF, DOCX, TXT files with progress
- View all indexed documents with status badges
- Admin: delete, re-index documents
"""

import streamlit as st
from components.api_client import (
    upload_document, list_documents,
    delete_document, reindex_document
)


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/1024**2:.1f} MB"


def show_documents_page():
    st.markdown("## 📄 Document Library")
    st.markdown("Upload and manage the documents that power the AI knowledge base.")

    is_admin = st.session_state.get("role") == "admin"

    # ── Upload Section ────────────────────────────────────────
    with st.expander("⬆️ Upload New Document", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "Choose a file",
                type=["pdf", "docx", "txt"],
                help="Max 50 MB. Supported: PDF, DOCX, TXT",
                label_visibility="collapsed",
            )
        with col2:
            description = st.text_input("Description (optional)", placeholder="e.g. Company HR Policy 2024")

        if uploaded_file:
            file_size = len(uploaded_file.getvalue())
            st.info(
                f"📎 **{uploaded_file.name}** · {format_size(file_size)} · "
                f"{uploaded_file.type or 'unknown type'}"
            )

            if st.button("🚀 Upload & Index", type="primary"):
                with st.spinner(f"Processing {uploaded_file.name}... This may take a moment."):
                    data, error = upload_document(
                        uploaded_file.getvalue(),
                        uploaded_file.name,
                        description
                    )
                    st.write("UPLOAD RESPONSE:", data)

                if error:
                    st.error(f"❌ Upload failed: {error}")
                else:   
                    st.session_state["selected_document_id"] = data["id"]
                    if data.get("is_indexed"):
                        st.success(f"✅ {data.get('message', 'Uploaded successfully!')}")
                        st.balloons()
                    else:
                        st.warning(f"⚠️ {data.get('message')}")
                    st.rerun()

    st.markdown("---")

    # ── Document List ─────────────────────────────────────────
    docs, error = list_documents()

    if error:
        st.error(f"Failed to load documents: {error}")
        return

    if not docs:
        st.markdown("""
        <div style="text-align:center; padding:60px; opacity:0.4;">
            <div style="font-size:48px;">📭</div>
            <p>No documents uploaded yet. Upload your first document above.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"**{len(docs)} document(s) in knowledge base**")

    # Table header
    cols = st.columns([3, 1, 1, 1, 1, 1.5] if is_admin else [3, 1, 1, 1, 1])
    headers = ["Document", "Type", "Size", "Chunks", "Status"]
    if is_admin:
        headers.append("Actions")
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

    for doc in docs:
        cols = st.columns([3, 1, 1, 1, 1, 1.5] if is_admin else [3, 1, 1, 1, 1])

        with cols[0]:
            icon = {"pdf": "📕", "docx": "📘", "txt": "📄"}.get(doc["file_type"], "📄")
            st.markdown(f"{icon} **{doc['original_name']}**")
            if doc.get("description"):
                st.markdown(f"<span style='font-size:11px;opacity:0.5;'>{doc['description']}</span>",
                            unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"`{doc['file_type'].upper()}`")
        with cols[2]:
            st.markdown(format_size(doc["file_size"]))
        with cols[3]:
            st.markdown(str(doc.get("chunk_count", 0)))
        with cols[4]:
            if doc.get("is_indexed"):
                st.markdown("✅ Indexed")
            else:
                st.markdown("⏳ Pending")

        if is_admin:
            with cols[5]:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔄", key=f"reindex_{doc['id']}", help="Re-index"):
                        with st.spinner("Re-indexing..."):
                            result, err = reindex_document(doc["id"])
                        if err:
                            st.error(err)
                        else:
                            st.success("Re-indexed!")
                            st.rerun()
                with c2:
                    if st.button("🗑️", key=f"delete_{doc['id']}", help="Delete"):
                        result, err = delete_document(doc["id"])
                        if err:
                            st.error(err)
                        else:
                            st.success("Deleted!")
                            st.rerun()

        st.markdown("<hr style='margin:4px 0; opacity:0.1;'>", unsafe_allow_html=True)
