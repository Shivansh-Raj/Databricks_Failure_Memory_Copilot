 
# Command to run streamlit app
# streamlit run ui/streamlit_app.py                                      
import streamlit as st
import requests
import uuid
from datetime import datetime

API_BASE = "http://localhost:8000"

# --------------------------------------------------------------------------- #
#  Page config                                                                 #
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="Databricks Failure Copilot",
    page_icon="🔥",
    layout="wide",
)

# --------------------------------------------------------------------------- #
#  CSS                                                                         #
# --------------------------------------------------------------------------- #

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .stApp { background-color: #0d0d0d; color: #e8e8e8; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a !important;
        border-right: 1px solid #1e1e1e;
    }
    .sidebar-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        color: #ff4d4d;
        letter-spacing: 0.08em;
        padding: 0.8rem 0 1rem 0;
        border-bottom: 1px solid #1e1e1e;
        margin-bottom: 0.8rem;
    }
    .chat-timestamp { font-size: 0.62rem; color: #444; margin-top: 2px; }

    /* ── Chat messages ── */
    .msg-user {
        display: flex;
        justify-content: flex-end;
        margin: 0.8rem 0;
    }
    .msg-user-bubble {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 8px 8px 2px 8px;
        padding: 0.8rem 1rem;
        max-width: 72%;
        font-size: 0.82rem;
        color: #ccc;
        white-space: pre-wrap;
        font-family: 'IBM Plex Mono', monospace;
    }
    .msg-assistant { margin: 0.8rem 0; }
    .msg-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        color: #444;
        margin-bottom: 0.4rem;
        letter-spacing: 0.06em;
    }

    /* ── Candidate card ── */
    .candidate-card {
        background: #111;
        border: 1px solid #2a2a2a;
        border-left: 3px solid #ff4d4d;
        border-radius: 4px;
        padding: 1.1rem 1.3rem;
        max-width: 680px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .card-header {
        display: flex;
        align-items: center;
        gap: 1.2rem;
        margin-bottom: 0.8rem;
        flex-wrap: wrap;
    }
    .card-id    { font-size: 0.88rem; font-weight: 600; color: #e8e8e8; }
    .card-score { font-size: 0.78rem; }
    .score-high { color: #4dff91; }
    .score-mid  { color: #ffd24d; }
    .score-low  { color: #ff6666; }
    .card-badge {
        font-size: 0.68rem;
        padding: 2px 7px;
        border-radius: 2px;
        border: 1px solid #333;
        color: #777;
        background: #1a1a1a;
    }
    .tag-pill {
        display: inline-block;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 2px;
        padding: 1px 7px;
        font-size: 0.68rem;
        color: #666;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .res-label {
        font-size: 0.65rem;
        color: #444;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 0.7rem 0 0.35rem 0;
    }
    .res-text {
        font-size: 0.83rem;
        color: #bbb;
        line-height: 1.7;
        white-space: pre-wrap;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .progress-tag {
        font-size: 0.65rem;
        color: #555;
        font-family: 'IBM Plex Mono', monospace;
        margin-bottom: 0.5rem;
    }

    /* ── Resolution card ── */
    .resolution-card {
        background: #0a150a;
        border: 1px solid #1a3a1a;
        border-left: 3px solid #4dff91;
        border-radius: 4px;
        padding: 1.1rem 1.3rem;
        max-width: 680px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .resolution-card.groq {
        background: #0a0d1a;
        border-color: #1a2a3a;
        border-left-color: #4d91ff;
    }
    .res-card-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.6rem;
        color: #4dff91;
    }
    .resolution-card.groq .res-card-label { color: #4d91ff; }

    /* ── System message ── */
    .sys-msg {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: #444;
        margin: 0.4rem 0;
        font-style: italic;
    }

    /* ── Input area ── */
    .input-area {
        border-top: 1px solid #1e1e1e;
        padding-top: 1rem;
        margin-top: 1rem;
    }
    .field-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        color: #555;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }
    textarea {
        background-color: #111 !important;
        border: 1px solid #222 !important;
        border-radius: 3px !important;
        color: #e8e8e8 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.8rem !important;
    }
    textarea:focus { border-color: #ff4d4d !important; }

    /* ── Input mode toggle ── */
    .stRadio > div {
        gap: 0.5rem !important;
    }
    .stRadio > div > label {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.75rem !important;
        color: #666 !important;
        background: #111 !important;
        border: 1px solid #222 !important;
        border-radius: 3px !important;
        padding: 0.3rem 0.8rem !important;
        cursor: pointer !important;
    }
    .stRadio > div > label[data-checked="true"] {
        border-color: #ff4d4d !important;
        color: #ff4d4d !important;
        background: #180808 !important;
    }

    /* ── Extraction info box ── */
    .extract-info {
        background: #0d1a0d;
        border: 1px solid #1a2a1a;
        border-left: 3px solid #4dff91;
        border-radius: 3px;
        padding: 0.6rem 0.9rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        color: #4dff91;
        margin: 0.6rem 0;
    }

    /* ── Buttons ── */
    .stButton > button {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.75rem !important;
        border-radius: 3px !important;
        border: 1px solid #2a2a2a !important;
        background: #111 !important;
        color: #888 !important;
        transition: all 0.12s !important;
        padding: 0.3rem 0.9rem !important;
    }
    .stButton > button:hover {
        border-color: #ff4d4d !important;
        color: #ff4d4d !important;
        background: #180808 !important;
    }

    /* ── Error box ── */
    .err-box {
        background: #180808;
        border: 1px solid #3a1212;
        border-radius: 3px;
        padding: 0.7rem 0.9rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: #ff6666;
        white-space: pre-wrap;
        margin-top: 0.6rem;
    }

    /* ── Misc ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left !important;
        justify-content: flex-start !important;
    }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
#  Session state bootstrap                                                     #
# --------------------------------------------------------------------------- #

if "chats" not in st.session_state:
    st.session_state.chats = {}

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def new_chat_id() -> str:
    return str(uuid.uuid4())

def get_chat(cid: str) -> dict:
    return st.session_state.chats[cid]

def add_message(cid: str, role: str, content):
    get_chat(cid)["messages"].append({"role": role, "content": content})

def call_analyze(error_text: str, code_text: str):
    try:
        r = requests.post(f"{API_BASE}/analyze", json={
            "error_text": error_text,
            "code_text":  code_text or None,
        }, timeout=120)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach server. Is uvicorn running on port 8000?"
    except Exception as e:
        return None, str(e)

def call_respond(session_id: str, choice: str):
    try:
        r = requests.post(f"{API_BASE}/respond", json={
            "session_id": session_id,
            "choice":     choice,
        }, timeout=120)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)

def call_extract(uploaded_files):
    try:
        files_data = [
            ("files", (f.name, f.getvalue(), f.type))
            for f in uploaded_files
        ]
        r = requests.post(f"{API_BASE}/extract", files=files_data, timeout=120)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach server. Is uvicorn running on port 8000?"
    except Exception as e:
        return None, str(e)

def score_class(score: float) -> str:
    if score >= 0.75: return "score-high"
    if score >= 0.5:  return "score-mid"
    return "score-low"

def candidate_html(c: dict) -> str:
    tags  = c.get("tags") or []
    score = c.get("score", 0.0)
    sc    = score_class(score)
    tags_html = "".join(f'<span class="tag-pill">{t.strip()}</span>' for t in tags)
    return f"""
<div class="candidate-card">
    <div class="progress-tag">match {c.get('index',0)+1} of {c.get('total',1)}</div>
    <div class="card-header">
        <span class="card-id">{c.get('incident_id','N/A')}</span>
        <span class="card-score {sc}">▲ {score:.2f}</span>
        <span class="card-badge">{c.get('severity','?').upper()}</span>
    </div>
    <div style="margin-bottom:0.6rem">{tags_html}</div>
    <div class="res-label">resolution</div>
    <div class="res-text">{c.get('resolution','Not available')}</div>
</div>"""

def resolution_html(text: str, is_groq: bool) -> str:
    cls   = "resolution-card groq" if is_groq else "resolution-card"
    label = "🤖 groq suggestion"    if is_groq else "✅ accepted resolution"
    return f"""
<div class="{cls}">
    <div class="res-card-label">{label}</div>
    <div class="res-text">{text}</div>
</div>"""

def create_new_chat():
    cid = new_chat_id()
    st.session_state.chats[cid] = {
        "title":             "New chat",
        "created_at":        datetime.now().strftime("%H:%M"),
        "messages":          [],
        "session_id":        None,
        "status":            "idle",
        "current_candidate": None,
        "error_msg":         None,
        "is_groq":           False,
    }
    st.session_state.active_chat = cid
    return cid

if not st.session_state.chats:
    create_new_chat()

# --------------------------------------------------------------------------- #
#  Sidebar                                                                     #
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.markdown('<div class="sidebar-title">// FAILURE COPILOT</div>', unsafe_allow_html=True)

    if st.button("＋  New Chat", use_container_width=True):
        create_new_chat()
        st.rerun()

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    sorted_chats = list(reversed(list(st.session_state.chats.keys())))
    for cid_s in sorted_chats:
        chat_s    = st.session_state.chats[cid_s]
        is_active = cid_s == st.session_state.active_chat
        label     = chat_s["title"][:30] + ("…" if len(chat_s["title"]) > 30 else "")
        prefix    = "▸ " if is_active else "  "

        if st.button(f"{prefix}{label}", key=f"chat_{cid_s}", use_container_width=True):
            st.session_state.active_chat = cid_s
            st.rerun()

        st.markdown(
            f'<div class="chat-timestamp" style="padding-left:0.75rem">{chat_s["created_at"]}</div>',
            unsafe_allow_html=True
        )

# --------------------------------------------------------------------------- #
#  Main area                                                                   #
# --------------------------------------------------------------------------- #

cid  = st.session_state.active_chat
chat = get_chat(cid)

# ── Chat history ──────────────────────────────────────────────────────────── #

with st.container():
    if not chat["messages"]:
        st.markdown("""
        <div style="text-align:center; padding: 3rem 0; color: #333;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:1.6rem; margin-bottom:0.5rem">🔥</div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:0.78rem; color:#444">
                paste an error or upload a screenshot below to start
            </div>
        </div>
        """, unsafe_allow_html=True)

    for msg in chat["messages"]:
        role    = msg["role"]
        content = msg["content"]

        if role == "user":
            st.markdown(f"""
            <div class="msg-user">
                <div class="msg-user-bubble">{content}</div>
            </div>""", unsafe_allow_html=True)

        elif role == "candidate":
            st.markdown('<div class="msg-assistant">', unsafe_allow_html=True)
            st.markdown('<div class="msg-label">COPILOT — candidate match</div>', unsafe_allow_html=True)
            st.markdown(candidate_html(content), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif role == "resolution":
            st.markdown('<div class="msg-assistant">', unsafe_allow_html=True)
            st.markdown('<div class="msg-label">COPILOT — resolution</div>', unsafe_allow_html=True)
            st.markdown(resolution_html(content["text"], content["is_groq"]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif role == "system":
            st.markdown(f'<div class="sys-msg">— {content}</div>', unsafe_allow_html=True)

    if chat.get("error_msg"):
        st.markdown(f'<div class="err-box">{chat["error_msg"]}</div>', unsafe_allow_html=True)

# ── Action buttons (only when awaiting input) ─────────────────────────────── #

@st.fragment
def action_buttons():
    chat = get_chat(st.session_state.active_chat)
    if chat["status"] != "awaiting_input":
        return

    def handle(choice: str):
        chat["error_msg"] = None
        labels = {
            "y": "✅ Accepted",
            "n": "⏭ Skipping to next match...",
            "g": "🤖 Asking Groq...",
            "q": "🚪 Exiting"
        }
        add_message(cid, "system", labels.get(choice, choice))

        data, err = call_respond(chat["session_id"], choice)

        if err:
            chat["error_msg"] = err
            st.rerun(scope="fragment")
            return

        if data["status"] == "error":
            chat["error_msg"] = data.get("traceback", data.get("error"))
            st.rerun(scope="fragment")
            return

        if data["status"] == "awaiting_input":
            candidate = data["candidate"]
            chat["current_candidate"] = candidate
            add_message(cid, "candidate", candidate)
            st.rerun(scope="fragment")

        elif data["status"] == "resolved":
            is_groq = (choice == "g") or (not data.get("candidate"))
            chat["status"]            = "resolved"
            chat["current_candidate"] = None
            resolution_text           = data.get("final_resolution", "No resolution found.")
            add_message(cid, "resolution", {"text": resolution_text, "is_groq": is_groq})
            st.rerun()

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("✅  Accept", use_container_width=True, key=f"accept_{cid}"):
            handle("y")
    with col2:
        if st.button("⏭  Next match", use_container_width=True, key=f"next_{cid}"):
            handle("n")
    with col3:
        if st.button("🤖  Groq suggest", use_container_width=True, key=f"groq_{cid}"):
            handle("g")
    with col4:
        if st.button("🚪  Quit", use_container_width=True, key=f"quit_{cid}"):
            handle("q")

    if chat.get("error_msg"):
        st.markdown(
            f'<div class="err-box">{chat["error_msg"]}</div>',
            unsafe_allow_html=True
        )

action_buttons()

# --------------------------------------------------------------------------- #
#  Input area (always visible)                                                 #
# --------------------------------------------------------------------------- #

st.markdown("<div class='input-area'>", unsafe_allow_html=True)

is_awaiting = chat["status"] == "awaiting_input"

# ── Input mode toggle ─────────────────────────────────────────────────────── #

input_mode = st.radio(
    label="input_mode",
    label_visibility="collapsed",
    options=["✏️  Type / Paste", "🖼️  Upload Screenshot"],
    horizontal=True,
    index=0 if st.session_state.get(f"input_mode_val_{cid}") == "✏️  Type / Paste" else 1,
    key=f"input_mode_{cid}",
    disabled=is_awaiting,
)

st.session_state[f"input_mode_val_{cid}"] = input_mode

# ── TEXT INPUT MODE ───────────────────────────────────────────────────────── #
if f"input_mode_{cid}" not in st.session_state:
    st.session_state[f"input_mode_val_{cid}"] = "✏️  Type / Paste"
    
if input_mode == "✏️  Type / Paste":

    st.markdown('<p class="field-label">Error</p>', unsafe_allow_html=True)
    error_input = st.text_area(
        label="error",
        label_visibility="collapsed",
        placeholder="Paste your error log here...",
        height=110,
        key=f"error_input_{cid}",
        value=st.session_state.get(f"extracted_error_{cid}", ""),
        disabled=is_awaiting,
    )

    st.markdown(
        '<p class="field-label" style="margin-top:0.6rem">Code '
        '<span style="color:#2a2a2a">— optional</span></p>',
        unsafe_allow_html=True
    )
    code_input = st.text_area(
        label="code",
        label_visibility="collapsed",
        placeholder="Paste relevant code snippet (optional)...",
        height=80,
        key=f"code_input_{cid}",
        value=st.session_state.get(f"extracted_code_{cid}", ""),
        disabled=is_awaiting,
    )
    if st.session_state.get(f"extracted_error_{cid}"):
        st.markdown(
            '<div class="extract-info">✅ Extracted from screenshot — review and edit above</div>',
            unsafe_allow_html=True
        )
        
# ── SCREENSHOT UPLOAD MODE ────────────────────────────────────────────────── #

else:
    st.markdown(
        '<p class="field-label">Upload Screenshots '
        '<span style="color:#2a2a2a">— max 2, PNG / JPG / WEBP</span></p>',
        unsafe_allow_html=True
    )

    uploaded_files = st.file_uploader(
        label="screenshots",
        label_visibility="collapsed",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"screenshots_{cid}",
        disabled=is_awaiting,
    )

    # Enforce max 2
    if uploaded_files and len(uploaded_files) > 2:
        st.markdown(
            '<div class="err-box">Maximum 2 screenshots allowed. Only the first 2 will be used.</div>',
            unsafe_allow_html=True
        )
        uploaded_files = uploaded_files[:2]

    # Extract button — only shown when files are present
    if uploaded_files and not is_awaiting:
        if st.button("🔍  Extract Text from Screenshot(s)", use_container_width=True, key=f"extract_{cid}"):
            with st.spinner("Running OCR + separating error and code..."):
                data, err = call_extract(uploaded_files)

            if err:
                chat["error_msg"] = err
                st.rerun()
            elif data["status"] == "error":
                chat["error_msg"] = data.get("traceback", data.get("error"))
                st.rerun()
            else:
                # Store extracted text in session state for this chat
                st.session_state[f"extracted_error_{cid}"] = data.get("error_text", "")
                st.session_state[f"extracted_code_{cid}"]  = data.get("code_text",  "")
                st.session_state[f"input_mode_val_{cid}"]  = "✏️  Type / Paste"
                chat["error_msg"] = None
                if data.get("warning"):
                    chat["error_msg"] = f"⚠️ {data['warning']}"
                st.rerun()

    # Editable review areas — shown after extraction
    extracted_error = st.session_state.get(f"extracted_error_{cid}", "")
    extracted_code  = st.session_state.get(f"extracted_code_{cid}",  "")

    if extracted_error or extracted_code:
        st.markdown(
            '<div class="extract-info">✅ Extraction complete — review and edit below before analyzing</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<p class="field-label">Extracted Error '
            '<span style="color:#2a2a2a">— review and edit</span></p>',
            unsafe_allow_html=True
        )
        error_input = st.text_area(
            label="extracted_error",
            label_visibility="collapsed",
            value=extracted_error,
            height=110,
            key=f"review_error_{cid}",
            disabled=is_awaiting,
        )

        st.markdown(
            '<p class="field-label" style="margin-top:0.6rem">Extracted Code '
            '<span style="color:#2a2a2a">— review and edit</span></p>',
            unsafe_allow_html=True
        )
        code_input = st.text_area(
            label="extracted_code",
            label_visibility="collapsed",
            value=extracted_code,
            height=80,
            key=f"review_code_{cid}",
            disabled=is_awaiting,
        )
    else:
        # No extraction yet — keep empty so Analyze button is blocked
        error_input = ""
        code_input  = ""

# ── Analyze button ────────────────────────────────────────────────────────── #

btn_label = (
    "⏳  Awaiting your choice above..."
    if is_awaiting
    else "⚡  Analyze"
)

if st.button(btn_label, use_container_width=True, disabled=is_awaiting, key=f"analyze_{cid}"):
    if not error_input.strip():
        chat["error_msg"] = (
            "Error field cannot be empty."
            if input_mode == "✏️  Type / Paste"
            else "Please upload screenshot(s) and click Extract first."
        )
        st.rerun()
    else:
        chat["error_msg"] = None

        # Set chat title from first chars of error
        if chat["title"] == "New chat":
            chat["title"] = error_input.strip()[:42]

        # Build user message for chat history
        user_msg = error_input.strip()
        if code_input.strip():
            user_msg += f"\n\n```python\n{code_input.strip()}\n```"
        add_message(cid, "user", user_msg)

        with st.spinner("Running pipeline..."):
            data, err = call_analyze(error_input.strip(), code_input.strip())

        if err:
            chat["error_msg"] = err
            st.rerun()
        elif data["status"] == "error":
            chat["error_msg"] = data.get("traceback", data.get("error"))
            st.rerun()
        elif data["status"] == "resolved":
            chat["status"]     = "resolved"
            chat["session_id"] = data.get("session_id")
            add_message(cid, "resolution", {
                "text":    data.get("final_resolution", "No resolution found."),
                "is_groq": True,
            })
            st.rerun()
        elif data["status"] == "awaiting_input":
            chat["status"]            = "awaiting_input"
            chat["session_id"]        = data["session_id"]
            chat["current_candidate"] = data["candidate"]
            add_message(cid, "candidate", data["candidate"])
            st.rerun()
        else:
            chat["error_msg"] = f"Unexpected server response: {data}"
            st.rerun()

# ── New analysis button (shown after resolved) ────────────────────────────── #

if chat["status"] == "resolved":
    st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)
    if st.button("↩  New Analysis in This Chat", use_container_width=True, key=f"reset_{cid}"):
        chat["status"]    = "idle"
        chat["error_msg"] = None
        # Clear extracted text so screenshot mode resets cleanly
        st.session_state.pop(f"extracted_error_{cid}", None)
        st.session_state.pop(f"extracted_code_{cid}",  None)
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)