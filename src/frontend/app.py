"""
Streamlit UI for the Agentic AI Multi-Agent Chatbot.
Uses a synchronous REST API with SSE streaming for live token updates.
Google OAuth for authentication (no passwords stored).
Enhanced with lively non-technical status feedback and a modern, premium UI.
"""

import os
import json
import time
import streamlit as st
import requests

# Backend URL (for Streamlit backend to FastAPI calls)
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
# Browser-facing URL (for OAuth redirect button in user's browser)
API_BROWSER_URL = os.getenv("API_BROWSER_URL", "http://localhost:8000")
# Frontend URL to redirect back to after OAuth login
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app")


# ─── Custom Premium CSS ───────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* Modern Typography & Container Spacing */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Glassmorphism sidebar elements */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

/* Status Badges */
.badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-right: 6px;
}
.badge-success {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
}
.badge-info {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.3);
}
.badge-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.3);
}
.badge-admin {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.3);
}

/* Animated Thinking Pulse */
@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.95); }
}
.pulse-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.25);
    color: #818cf8;
    font-size: 0.9rem;
    font-weight: 500;
    animation: pulse-dot 2s infinite ease-in-out;
}

/* Storage Meter Container */
.storage-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 16px;
    margin-top: 8px;
    margin-bottom: 8px;
}

/* Chat Message Card Aesthetics */
.stChatMessage {
    border-radius: 14px;
    margin-bottom: 8px;
    transition: all 0.2s ease;
}

/* Clean Button Styling */
div.stButton > button {
    border-radius: 10px;
    font-weight: 500;
    transition: all 0.15s ease-in-out;
}
div.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
"""


# ─── Session State ───────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "user_id": "",
        "email": "",
        "display_name": "",
        "avatar_url": "",
        "messages": [],
        "uploaded_docs": [],
        "shared_docs": [],
        "last_trace": "",
        "token": "",
        "authenticated": False,
        "uploader_key": 0,
        "current_session_id": None,   # None = no active session yet
        "pending_prompt": None,        # message waiting to be sent to backend
        "sessions_cache": [],
        "sessions_last_fetch": 0.0,
        "docs_fetched": False,
        "has_api_key": False,
        "masked_api_key": "",
        "is_super_admin": False,
        "include_shared": True,
        "storage_used_mb": 0.0,
        "storage_quota_mb": 0,
        "langsmith_enabled": False,
        "langsmith_api_key": "",
        "langsmith_project": "genai_chat_project",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── Backend Calls ───────────────────────────────────────────────────────────

def fetch_api_key_status() -> tuple[bool, str]:
    """Fetch user's API key status from backend."""
    try:
        resp = requests.get(f"{API_BASE}/user/{st.session_state.user_id}/api-key", timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.has_api_key = data.get("has_api_key", False)
            st.session_state.masked_api_key = data.get("masked_key", "")
            return st.session_state.has_api_key, st.session_state.masked_api_key
    except Exception:
        pass
    return st.session_state.get("has_api_key", False), st.session_state.get("masked_api_key", "")


def save_api_key(api_key: str) -> tuple[bool, str]:
    """Validate with Google AI Studio and securely save user's API key."""
    try:
        resp = requests.post(
            f"{API_BASE}/user/{st.session_state.user_id}/api-key",
            json={"api_key": api_key.strip()},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.has_api_key = True
            st.session_state.masked_api_key = data.get("masked_key", "")
            return True, "API Key successfully validated & saved!"
        try:
            err = resp.json().get("detail", "Failed to save key")
        except Exception:
            err = resp.text or f"Status {resp.status_code}"
        return False, err
    except Exception as e:
        return False, f"Connection error: {e}"


def delete_api_key() -> bool:
    """Delete user's stored API key."""
    try:
        resp = requests.delete(f"{API_BASE}/user/{st.session_state.user_id}/api-key", timeout=4)
        if resp.status_code == 200:
            st.session_state.has_api_key = False
            st.session_state.masked_api_key = ""
            return True
    except Exception:
        pass
    return False


def refresh_documents():
    """Fetch user's documents, shared documents, and storage quota."""
    try:
        resp = requests.get(f"{API_BASE}/documents/{st.session_state.user_id}", timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.uploaded_docs = data.get("documents", [])
            st.session_state.shared_docs = data.get("shared_documents", [])
            st.session_state.storage_used_mb = data.get("storage_used_mb", 0.0)
            st.session_state.storage_quota_mb = data.get("storage_quota_mb", 0)
            st.session_state.is_super_admin = data.get("is_super_admin", st.session_state.get("is_super_admin", False))
            st.session_state.docs_fetched = True
    except Exception:
        pass


def fetch_sessions(force: bool = False) -> list:
    """Fetch session list, cached for 10s to avoid blocking every render."""
    now = time.time()
    if force or (now - st.session_state.sessions_last_fetch > 10):
        try:
            resp = requests.get(f"{API_BASE}/sessions/{st.session_state.user_id}", timeout=4)
            if resp.status_code == 200:
                st.session_state.sessions_cache = resp.json().get("sessions", [])
                st.session_state.sessions_last_fetch = now
        except Exception:
            pass
    return st.session_state.sessions_cache


def load_session_history(session_id: str):
    """Load a session's message history into the chat view."""
    try:
        resp = requests.get(
            f"{API_BASE}/sessions/{st.session_state.user_id}/{session_id}/history",
            timeout=4,
        )
        if resp.status_code == 200:
            msgs = resp.json().get("messages", [])
            st.session_state.messages = [
                {"role": m["role"], "content": m["content"]} for m in msgs
            ]
        else:
            st.session_state.messages = []
    except Exception:
        st.session_state.messages = []


def stream_chat(message: str, status_placeholder):
    """
    Stream a chat message via SSE with lively non-technical status updates.
    Returns the final result dict.
    """
    result = {"answer": "", "session_id": st.session_state.current_session_id, "trace": ""}
    try:
        resp = requests.post(
            f"{API_BASE}/chat/stream",
            json={
                "user_id": st.session_state.user_id,
                "message": message,
                "session_id": st.session_state.current_session_id,
                "include_shared": st.session_state.get("include_shared", True),
                "langsmith_tracing": st.session_state.get("langsmith_enabled", False),
                "langsmith_api_key": st.session_state.get("langsmith_api_key", ""),
                "langsmith_project": st.session_state.get("langsmith_project", "genai_chat_project"),
            },
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data: "):
                continue
            json_str = line[6:]  # Remove "data: " prefix
            try:
                data = json.loads(json_str)
            except Exception:
                continue

            dtype = data.get("type", "")
            if dtype == "status":
                status_text = data.get("content", "Reasoning...")
                status_placeholder.markdown(
                    f'<div class="pulse-status">✨ {status_text}</div>',
                    unsafe_allow_html=True,
                )
            elif dtype == "session":
                result["session_id"] = data.get("session_id")
            elif dtype == "answer":
                result["answer"] = data.get("content", "")
                result["session_id"] = data.get("session_id", result["session_id"])
                result["trace"] = data.get("trace", "")

        return result
    except requests.exceptions.Timeout:
        result["answer"] = (
            "### 🌐 Network Timeout\n\n"
            "The AI request took longer than expected to finish. "
            "Please give it a quick moment and tap ask again."
        )
        return result
    except requests.exceptions.ConnectionError:
        result["answer"] = (
            "### 🔌 Service Connecting\n\n"
            "Unable to reach the backend service. If the server is restarting, "
            "it will be back online in about 30 seconds."
        )
        return result
    except Exception as e:
        result["answer"] = f"### ⚠️ Unexpected Notice\n\n{e}\n\nPlease try asking your question again."
        return result


def logout():
    """Reset all state."""
    for key in [
        "authenticated", "user_id", "email", "display_name", "avatar_url",
        "token", "messages", "uploaded_docs", "shared_docs", "current_session_id",
        "pending_prompt", "sessions_cache", "docs_fetched", "is_super_admin",
    ]:
        if key in st.session_state:
            st.session_state[key] = [] if key in ("messages", "uploaded_docs", "shared_docs", "sessions_cache") else (
                None if key in ("current_session_id", "pending_prompt") else
                (False if key in ("authenticated", "docs_fetched", "is_super_admin") else "")
            )


def authenticate_with_backend(id_token: str) -> bool:
    """Send Google ID token to backend, get JWT back."""
    try:
        resp = requests.post(
            f"{API_BASE}/auth/google",
            json={"id_token": id_token},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.user_id = data["user_id"]
            st.session_state.email = data["email"]
            st.session_state.display_name = data["display_name"]
            st.session_state.avatar_url = data.get("avatar_url", "")
            st.session_state.token = data["token"]
            st.session_state.has_api_key = data.get("has_api_key", False)
            st.session_state.masked_api_key = data.get("masked_key", "")
            st.session_state.is_super_admin = data.get("is_super_admin", False)
            st.session_state.authenticated = True
            st.session_state.messages = []
            st.session_state.current_session_id = None
            refresh_documents()
            return True
        else:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text or f"Status {resp.status_code}"
            st.error(f"❌ Auth failed: {detail}")
            return False
    except Exception as e:
        st.error(f"❌ Connection error: {e}")
        return False


def authenticate_direct_user(user_identifier: str) -> bool:
    """Authenticate directly with user_id or email via backend /connect endpoint."""
    clean_id = user_identifier.strip().lower()
    if not clean_id:
        st.warning("Please enter a valid email or username.")
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/connect",
            json={"user_id": clean_id},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.user_id = data["user_id"]
            st.session_state.email = clean_id if "@" in clean_id else f"{clean_id}@app.local"
            st.session_state.display_name = clean_id.split("@")[0].capitalize()
            st.session_state.avatar_url = ""
            st.session_state.token = data.get("token", "")
            st.session_state.authenticated = True
            st.session_state.messages = []
            st.session_state.current_session_id = None
            fetch_api_key_status()
            refresh_documents()
            return True
        else:
            st.error(f"❌ Connection failed (Status {resp.status_code})")
            return False
    except Exception as e:
        st.error(f"❌ Cannot connect to backend: {e}")
        return False


# ─── Login Page ──────────────────────────────────────────────────────────────

def login_page():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    col_c1, col_c2, col_c3 = st.columns([1, 2.5, 1])
    with col_c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🤖 Agentic AI Multi-Agent Chat")
        st.markdown(
            "Enterprise RAG & SQL intelligence powered by **Gemini Flash Lite** "
            "with specialized autonomous agents:"
        )
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("🎯 **Smart Router Agent**  \n📊 **SQL Analyst Agent**")
        with col_f2:
            st.markdown("📄 **Document Expert Agent**  \n✨ **Response Synthesizer**")
            
        st.divider()

        query_params = st.query_params
        google_token = query_params.get("credential", None)

        if google_token:
            with st.spinner("✨ Signing in with Google securely..."):
                success = authenticate_with_backend(google_token)
                if success:
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.query_params.clear()
                    st.error("❌ Authentication failed. Please try again.")
            return

        st.subheader("🔐 Sign in with Google")
        st.caption("Zero passwords stored — authenticated directly with Google Identity.")
        st.markdown("")
        login_url = f"{API_BROWSER_URL}/auth/google/login"
        if FRONTEND_URL:
            login_url = f"{login_url}?redirect_to={FRONTEND_URL}"

        st.link_button(
            "🚀 Sign in with Google",
            url=login_url,
            use_container_width=True,
            type="primary",
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("⚡ *Each user has isolated, encrypted storage and private API key management (BYOK).*")


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        if st.session_state.avatar_url:
            st.image(st.session_state.avatar_url, width=54)
        
        display = st.session_state.display_name or st.session_state.user_id
        st.markdown(f"### {display}")
        st.caption(st.session_state.email)
        
        # User badges
        badges_html = '<div style="margin-bottom: 12px;">'
        if st.session_state.get("is_super_admin", False):
            badges_html += '<span class="badge-pill badge-admin">👑 Super Admin</span>'
        if st.session_state.has_api_key:
            badges_html += '<span class="badge-pill badge-success">🟢 BYOK Active</span>'
        else:
            badges_html += '<span class="badge-pill badge-warning">⚡ Shared Key</span>'
        badges_html += '<span class="badge-pill badge-info">Flash-Lite</span></div>'
        st.markdown(badges_html, unsafe_allow_html=True)

        st.divider()

        # ─── Google Gemini API Key (BYOK) ───────────────────────────
        st.subheader("🔑 Gemini API Key")
        has_key = st.session_state.has_api_key
        masked = st.session_state.masked_api_key

        if has_key:
            st.success(f"🟢 Active Key: `{masked}`")
            if st.button("🗑️ Remove / Change Key", use_container_width=True):
                delete_api_key()
                st.rerun()
        else:
            st.caption("Bring Your Own Key — encrypted with AES-128 at rest for isolated quotas.")
            user_input_key = st.text_input(
                "API Key",
                type="password",
                placeholder="AIzaSy...",
                help="Validated with Google and stored securely.",
                key="input_gemini_key",
            )
            if st.button("💾 Save Key", type="primary", use_container_width=True):
                if user_input_key:
                    with st.spinner("Validating with Google AI Studio..."):
                        success, msg = save_api_key(user_input_key)
                        if success:
                            st.success(msg)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                else:
                    st.warning("Please enter an API key.")
            st.markdown(
                "[👉 Get free API key from Google AI Studio](https://aistudio.google.com/apikey)"
            )

        st.divider()

        # ─── LangSmith Tracing & Observability ───────────────────────
        st.subheader("🔬 LangSmith Tracing")
        with st.expander("🛠️ Trace Name & Settings", expanded=st.session_state.get("langsmith_enabled", False)):
            tracing_on = st.checkbox(
                "Enable LangSmith Tracing",
                value=st.session_state.get("langsmith_enabled", False),
                help="Stream live LLM runs, agent thought graphs, and tool invocations to LangSmith.",
                key="chk_langsmith_enabled",
            )
            st.session_state.langsmith_enabled = tracing_on

            ls_key = st.text_input(
                "LangSmith API Key",
                value=st.session_state.get("langsmith_api_key", ""),
                type="password",
                placeholder="lsv2_pt_...",
                help="Starts with lsv2_pt_ from smith.langchain.com (optional if set on server)",
                key="input_langsmith_key",
            )
            st.session_state.langsmith_api_key = ls_key

            ls_project = st.text_input(
                "Project / Trace Name",
                value=st.session_state.get("langsmith_project", "genai_chat_project"),
                placeholder="e.g. genai_chat_project",
                help="Name of the project dashboard in LangSmith where your traces are recorded.",
                key="input_langsmith_project",
            )
            st.session_state.langsmith_project = ls_project.strip() or "genai_chat_project"

            st.markdown(
                '<a href="https://smith.langchain.com" target="_blank" style="text-decoration:none;">'
                '<button style="width:100%; padding:7px 12px; margin-top:8px; border-radius:8px; background:rgba(99,102,241,0.15); '
                'color:#6366f1; border:1px solid rgba(99,102,241,0.3); font-weight:600; cursor:pointer;">'
                '📊 Open LangSmith Dashboard ↗'
                '</button></a>',
                unsafe_allow_html=True,
            )
            st.caption("[👉 Get free API key from LangSmith](https://smith.langchain.com)")

        st.divider()

        # ─── Chat Sessions ──────────────────────────────────────────
        st.subheader("💬 Chat Sessions")
        col_new, col_ref = st.columns([3, 1])
        with col_new:
            if st.button("➕ New Chat", use_container_width=True, type="primary"):
                st.session_state.current_session_id = None
                st.session_state.messages = []
                fetch_sessions(force=True)
                st.rerun()
        with col_ref:
            if st.button("🔄", help="Refresh session list"):
                fetch_sessions(force=True)
                st.rerun()

        sessions = fetch_sessions()
        for sess in sessions:
            sess_id = sess["id"]
            title = sess.get("title", "New Chat") or "New Chat"
            is_active = (sess_id == st.session_state.current_session_id)
            label = f"👉 {title[:20]}" if is_active else title[:22]

            col_s, col_d = st.columns([5, 1])
            with col_s:
                if st.button(label, key=f"sess_{sess_id}", use_container_width=True):
                    st.session_state.current_session_id = sess_id
                    load_session_history(sess_id)
                    st.rerun()
            with col_d:
                if st.button("🗑", key=f"del_{sess_id}"):
                    try:
                        requests.delete(
                            f"{API_BASE}/sessions/{st.session_state.user_id}/{sess_id}",
                            timeout=4,
                        )
                    except Exception:
                        pass
                    if st.session_state.current_session_id == sess_id:
                        st.session_state.current_session_id = None
                        st.session_state.messages = []
                    fetch_sessions(force=True)
                    st.rerun()

        st.divider()

        # ─── Shared Demo Knowledge Base ─────────────────────────────
        st.subheader("🌐 Knowledge Base")
        st.session_state.include_shared = st.checkbox(
            "Include Shared Demo Documents",
            value=st.session_state.get("include_shared", True),
            help="When enabled, the agent answers using pre-loaded demo knowledge bases without requiring you to upload files.",
            key="chk_include_shared",
        )

        st.divider()

        # ─── Document Upload ────────────────────────────────────────
        st.subheader("📄 Document Upload")
        st.caption("Upload files to ask questions about them (PDF, DOCX, CSV, TXT, MD).")

        uploaded_file = st.file_uploader(
            "Upload a document",
            type=["txt", "docx", "md", "csv", "log", "pdf"],
            help="Supported: .txt, .docx, .md, .csv, .log, .pdf (max 30MB)",
            key=f"file_uploader_{st.session_state.uploader_key}",
        )

        upload_as_shared = False
        if st.session_state.get("is_super_admin", False):
            upload_as_shared = st.checkbox(
                "👑 Upload as Shared Demo Document",
                value=False,
                help="Super Admin: This document will be accessible to all users without vector duplication.",
                key="chk_upload_as_shared",
            )

        if uploaded_file is not None:
            if st.button("📤 Process & Store", type="primary", use_container_width=True):
                with st.spinner(f"✨ Ingesting and embedding {uploaded_file.name}..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {
                            "user_id": st.session_state.user_id,
                            "is_shared": str(upload_as_shared).lower(),
                        }
                        resp = requests.post(f"{API_BASE}/upload", files=files, data=data, timeout=300)
                        if resp.status_code == 200:
                            st.success(f"✅ {resp.json()['message']}")
                            refresh_documents()
                            st.session_state.uploader_key += 1
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            try:
                                err = resp.json().get("detail", "Upload failed")
                            except Exception:
                                err = f"Status {resp.status_code}"
                            st.error(f"❌ {err}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Cannot reach backend service. Please try again.")
                    except Exception as e:
                        st.error(f"❌ Upload error: {e}")

        st.divider()
        st.subheader("📚 Your Documents")

        # Storage quota visual meter
        used_mb = st.session_state.get("storage_used_mb", 0.0)
        quota_mb = st.session_state.get("storage_quota_mb", 0)
        if quota_mb > 0 and not st.session_state.get("is_super_admin", False):
            pct = min(1.0, used_mb / max(quota_mb, 1))
            st.progress(pct)
            st.caption(f"💾 Storage: **{used_mb:.1f} MB** of **{quota_mb} MB** ({pct*100:.0f}% used)")
        elif st.session_state.get("is_super_admin", False):
            st.caption(f"💾 Storage: **{used_mb:.1f} MB** used (👑 Super Admin Unlimited)")
        else:
            st.caption(f"💾 Storage: **{used_mb:.1f} MB** used")

        if st.button("🔄 Refresh Documents", use_container_width=True):
            refresh_documents()
            st.rerun()

        if st.session_state.uploaded_docs:
            for doc in st.session_state.uploaded_docs:
                col_doc, col_del = st.columns([4, 1])
                with col_doc:
                    st.text(f"📎 {doc}")
                with col_del:
                    actual = doc.split(" — ")[0].replace("📊 ", "").replace("📄 ", "").strip()
                    if st.button("🗑️", key=f"deldoc_{doc}"):
                        try:
                            r = requests.delete(
                                f"{API_BASE}/documents/{st.session_state.user_id}/{actual}",
                                timeout=10,
                            )
                            if r.status_code == 200:
                                refresh_documents()
                                st.rerun()
                        except Exception:
                            pass
        else:
            st.caption("No private documents uploaded yet.")

        # Display shared demo documents
        if st.session_state.get("shared_docs"):
            st.markdown("---")
            st.markdown("**🌐 Shared Demo Documents**")
            for sdoc in st.session_state.shared_docs:
                col_sdoc, col_sdel = st.columns([4, 1] if st.session_state.get("is_super_admin", False) else [1, 0.01])
                with col_sdoc:
                    st.text(f"📎 {sdoc}")
                if st.session_state.get("is_super_admin", False):
                    with col_sdel:
                        actual = sdoc.split(" — ")[0].replace("📊 ", "").replace("📄 ", "").strip()
                        if st.button("🗑️", key=f"delsdoc_{sdoc}"):
                            try:
                                r = requests.delete(
                                    f"{API_BASE}/documents/{st.session_state.user_id}/{actual}?is_shared=true",
                                    timeout=10,
                                )
                                if r.status_code == 200:
                                    refresh_documents()
                                    st.rerun()
                            except Exception:
                                pass


# ─── Chat Page ───────────────────────────────────────────────────────────────

def chat_page():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("🤖 Agentic AI Multi-Agent Chat")
        display = st.session_state.display_name or st.session_state.user_id
        st.caption(f"**{display}** ({st.session_state.email}) | Model: **Gemini 3.5 Flash Lite**")
    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()

    st.divider()

    if not st.session_state.has_api_key:
        st.info(
            "💡 **Tip: Add Your Personal Gemini API Key**  \n"
            "To enjoy isolated quotas and higher speed limits, save your Google Gemini API key in the sidebar.  \n"
            "Free keys can be created in seconds at [Google AI Studio](https://aistudio.google.com/apikey)."
        )

    # Render all messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Process pending prompt with LIVE streaming updates
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            status_placeholder.markdown(
                '<div class="pulse-status">✨ Reasoning across multi-agent graph...</div>',
                unsafe_allow_html=True,
            )
            result = stream_chat(prompt, status_placeholder)
            status_placeholder.empty()

        if result.get("session_id") and st.session_state.current_session_id is None:
            st.session_state.current_session_id = result["session_id"]
        st.session_state.last_trace = result.get("trace", "")
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"] or "⚠️ No response received.",
        })
        fetch_sessions(force=True)
        st.rerun()

    if st.session_state.last_trace:
        with st.expander("🔍 Agent Reasoning Trace", expanded=False):
            st.code(st.session_state.last_trace, language=None)
            st.caption("💡 Multi-agent orchestration step trace across Router, SQL Analyst, and Document Expert.")

    # Chat input
    if prompt := st.chat_input("Ask anything about your documents, data, or general knowledge...", disabled=bool(st.session_state.pending_prompt)):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_prompt = prompt
        st.rerun()

    # Sidebar rendered LAST so chat area renders first
    render_sidebar()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Agentic AI Multi-Agent Chat",
        page_icon="🤖",
        layout="wide",
    )
    init_state()

    if st.session_state.authenticated:
        chat_page()
    else:
        login_page()


if __name__ == "__main__":
    main()
