import streamlit as st 
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Databricks Failure Copilot",
    page_icon="🔥",
    layout="centered",
)

# -------------------------------------------------------------------------
# Custom CSS 
# -------------------------------------------------------------------------
 
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
 
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
 
    .stApp {
        background-color: #0d0d0d;
        color: #e8e8e8;
    }
 
    /* Header */
    .copilot-header {
        border-bottom: 1px solid #2a2a2a;
        padding-bottom: 1.2rem;
        margin-bottom: 2rem;
    }
    .copilot-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.4rem;
        font-weight: 600;
        color: #ff4d4d;
        letter-spacing: 0.04em;
        margin: 0;
    }
    .copilot-sub {
        font-size: 0.82rem;
        color: #555;
        margin-top: 0.3rem;
        font-family: 'IBM Plex Mono', monospace;
    }
 
    /* Input labels */
    .field-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: #666;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }
 
    /* Text areas */
    textarea {
        background-color: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 4px !important;
        color: #e8e8e8 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.82rem !important;
        resize: vertical !important;
    }
    textarea:focus {
        border-color: #ff4d4d !important;
        box-shadow: 0 0 0 1px #ff4d4d22 !important;
    }
 
    /* Candidate card */
    .candidate-card {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-left: 3px solid #ff4d4d;
        border-radius: 4px;
        padding: 1.4rem 1.6rem;
        margin: 1.4rem 0;
        font-family: 'IBM Plex Mono', monospace;
    }
    .candidate-meta {
        display: flex;
        gap: 1.4rem;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }
    .meta-item {
        font-size: 0.75rem;
        color: #666;
    }
    .meta-value {
        color: #e8e8e8;
        font-weight: 600;
    }
    .score-high  { color: #4dff91; }
    .score-mid   { color: #ffd24d; }
    .score-low   { color: #ff4d4d; }
    .resolution-label {
        font-size: 0.7rem;
        color: #444;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }
    .resolution-text {
        font-size: 0.88rem;
        color: #ccc;
        line-height: 1.7;
        white-space: pre-wrap;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .tag-pill {
        display: inline-block;
        background: #1e1e1e;
        border: 1px solid #333;
        border-radius: 2px;
        padding: 1px 8px;
        font-size: 0.7rem;
        color: #888;
        margin-right: 4px;
    }
 
    /* Final resolution */
    .final-card {
        background: #0a1a0a;
        border: 1px solid #1a3a1a;
        border-left: 3px solid #4dff91;
        border-radius: 4px;
        padding: 1.4rem 1.6rem;
        margin-top: 1.4rem;
        font-family: 'IBM Plex Mono', monospace;
    }
    .final-label {
        font-size: 0.7rem;
        color: #4dff91;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.6rem;
    }
    .final-text {
        font-size: 0.88rem;
        color: #ccc;
        line-height: 1.7;
        white-space: pre-wrap;
        font-family: 'IBM Plex Sans', sans-serif;
    }
 
    /* Groq suggestion card */
    .groq-card {
        background: #0d0d1a;
        border: 1px solid #1a1a3a;
        border-left: 3px solid #4d91ff;
        border-radius: 4px;
        padding: 1.4rem 1.6rem;
        margin-top: 1.4rem;
        font-family: 'IBM Plex Mono', monospace;
    }
    .groq-label {
        font-size: 0.7rem;
        color: #4d91ff;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.6rem;
    }
 
    /* Buttons — override streamlit defaults */
    .stButton > button {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.8rem !important;
        border-radius: 3px !important;
        border: 1px solid #2a2a2a !important;
        background: #141414 !important;
        color: #aaa !important;
        padding: 0.4rem 1rem !important;
        transition: all 0.15s !important;
    }
    .stButton > button:hover {
        border-color: #ff4d4d !important;
        color: #ff4d4d !important;
        background: #1a0a0a !important;
    }
 
    /* Progress text */
    .progress-text {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        color: #444;
        margin-bottom: 0.8rem;
    }
 
    /* Error box */
    .error-box {
        background: #1a0a0a;
        border: 1px solid #3a1a1a;
        border-radius: 4px;
        padding: 0.8rem 1rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        color: #ff6666;
        margin-top: 1rem;
    }
 
    /* Hide streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------------------
# Initial State 
# -------------------------------------------------------------------------

for key, default in {
    "session_id":       None,
    "current_candidate": None,
    "status":           "idle",     
    "final_resolution": None,
    "error_msg":        None,
    "is_groq":          False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default
 
# HEADER
st.markdown("""
<div class="copilot-header">
    <p class="copilot-title">// DATABRICKS FAILURE COPILOT</p>
    <p class="copilot-sub">paste error · get resolution · move on</p>
</div>
""", unsafe_allow_html=True)


def call_analyze(error_text, code_text):
    try:
        r = requests.post(f"{API_BASE}/analyze", json={
            "error_text": error_text,
            "code_text":  code_text or None,
        }, timeout=60)
        
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to the analysis server. Please ensure it's running and try again."
    except Exception as e:
        return None, str(e)
    
def call_respond(session_id: str, choice: str):
    try:
        r = requests.post(f"{API_BASE}/respond", json={
            "session_id": session_id,
            "choice":     choice,
        }, timeout=60)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)
    

def score_class(score: float) -> str:
    if score >= 0.75: return "score-high"
    if score >= 0.5:  return "score-mid"
    return "score-low"
 
def render_candidate(c: dict):
    tags_html = "".join(f'<span class="tag-pill">{t.strip()}</span>' for t in (c.get("tags") or []))
    score     = c.get("score", 0.0)
    sc        = score_class(score)
 
    st.markdown(f"""
    <div class="candidate-card">
        <div class="progress-text">match {c.get('index',0)+1} of {c.get('total',1)}</div>
        <div class="candidate-meta">
            <div class="meta-item">ID <span class="meta-value">{c.get('incident_id','N/A')}</span></div>
            <div class="meta-item">SCORE <span class="meta-value {sc}">{score:.2f}</span></div>
            <div class="meta-item">SEVERITY <span class="meta-value">{c.get('severity','N/A').upper()}</span></div>
        </div>
        <div style="margin-bottom:1rem">{tags_html}</div>
        <div class="resolution-label">resolution</div>
        <div class="resolution-text">{c.get('resolution','Not available')}</div>
    </div>
    """, unsafe_allow_html=True)
    

 
if st.session_state.status == "idle":
    st.markdown('<p class="field-label">Error Message</p>', unsafe_allow_html=True)
    error_input = st.text_area(
        label="error_input",
        label_visibility="collapsed",
        placeholder="Paste your Databricks / Spark error here...",
        height=160,
        key="error_input",
    )
 
    st.markdown('<p class="field-label" style="margin-top:1rem">Code Snippet <span style="color:#333">— optional</span></p>', unsafe_allow_html=True)
    code_input = st.text_area(
        label="code_input",
        label_visibility="collapsed",
        placeholder="Paste the relevant code snippet here (optional)...",
        height=120,
        key="code_input",
    )
 
    st.markdown("<div style='margin-top:1.2rem'></div>", unsafe_allow_html=True)
 
    if st.button("⚡  Analyze", use_container_width=True):
        if not error_input.strip():
            st.session_state.error_msg = "Error field cannot be empty."
        else:
            st.session_state.error_msg = None
            with st.spinner("Running pipeline..."):
                data, err = call_analyze(error_input.strip(), code_input.strip())
 
            if err:
                st.session_state.error_msg = err
            elif data["status"] == "resolved":
                st.session_state.status           = "resolved"
                st.session_state.final_resolution = data.get("final_resolution")
                st.session_state.is_groq          = True
                st.rerun()
            else:
                st.session_state.session_id       = data["session_id"]
                st.session_state.current_candidate = data["candidate"]
                st.session_state.status           = "awaiting_input"
                st.rerun()
 
    if st.session_state.error_msg:
        st.markdown(f'<div class="error-box">{st.session_state.error_msg}</div>', unsafe_allow_html=True)
        

@st.fragment
def candidate_fragment():
    c = st.session_state.current_candidate
    if not c:
        return
    
    render_candidate(c)
    
    col1, col2, col3, col4 = st.columns(4)
 
    with col1:
        if st.button("✅  Accept", use_container_width=True):
            with st.spinner("Confirming..."):
                data, err = call_respond(st.session_state.session_id, "y")
            if err:
                st.session_state.error_msg = err
            else:
                st.session_state.status           = "resolved"
                st.session_state.final_resolution = data.get("final_resolution")
                st.session_state.is_groq          = False
                st.rerun()
 
    with col2:
        if st.button("⏭  Next", use_container_width=True):
            with st.spinner("Fetching next match..."):
                data, err = call_respond(st.session_state.session_id, "n")
            if err:
                st.session_state.error_msg = err
            elif data["status"] == "resolved":
                # exhausted all candidates — groq suggest was triggered
                st.session_state.status           = "resolved"
                st.session_state.final_resolution = data.get("final_resolution")
                st.session_state.is_groq          = True
                st.rerun()
            else:
                st.session_state.current_candidate = data["candidate"]
 
    with col3:
        if st.button("🤖  Groq", use_container_width=True):
            with st.spinner("Asking Groq..."):
                data, err = call_respond(st.session_state.session_id, "g")
            if err:
                st.session_state.error_msg = err
            else:
                st.session_state.status           = "resolved"
                st.session_state.final_resolution = data.get("final_resolution")
                st.session_state.is_groq          = True
                st.rerun()
 
    with col4:
        if st.button("🚪  Quit", use_container_width=True):
            call_respond(st.session_state.session_id, "q")
            st.session_state.status = "idle"
            st.session_state.session_id = None
            st.session_state.current_candidate = None
            st.rerun()
 
    if st.session_state.error_msg:
        st.markdown(f'<div class="error-box">{st.session_state.error_msg}</div>', unsafe_allow_html=True)
 
if st.session_state.status == "awaiting_input":
    candidate_fragment()
    
if st.session_state.status == "resolved":
    card_class  = "groq-card"  if st.session_state.is_groq else "final-card"
    label_class = "groq-label" if st.session_state.is_groq else "final-label"
    label_text  = "🤖 groq suggestion" if st.session_state.is_groq else "✅ accepted resolution"
 
    st.markdown(f"""
    <div class="{card_class}">
        <div class="{label_class}">{label_text}</div>
        <div class="final-text">{st.session_state.final_resolution or 'No resolution found.'}</div>
    </div>
    """, unsafe_allow_html=True)
 
    st.markdown("<div style='margin-top:1.4rem'></div>", unsafe_allow_html=True)
 
    if st.button("↩  New Analysis", use_container_width=True):
        for key in ["session_id", "current_candidate", "final_resolution", "error_msg", "is_groq"]:
            st.session_state[key] = None
        st.session_state.status  = "idle"
        st.session_state.is_groq = False
        st.rerun()
 
    
    