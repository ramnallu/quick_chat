import os
import sys
import pathlib
import uuid

# Ensure the project root is in the python path for cloud deployments
root_path = pathlib.Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

import streamlit as st
from dotenv import load_dotenv

import chromadb
from app.api import process_query, warmup_business_cache
from app.graph import agent_router

CHROMA_PERSIST = os.environ.get("CHROMA_PERSIST_PATH", "./data/chroma")

# Page configuration
st.set_page_config(
    page_title="QuickChat | AI Support",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* Global Styles & Variable Definitions */
    :root {
        --primary: #6366f1;
        --primary-glow: rgba(99, 102, 241, 0.4);
        --bg-glass: rgba(255, 255, 255, 0.1);
        --bg-glass-bot: rgba(99, 102, 241, 0.15);
        --border-glass: rgba(255, 255, 255, 0.15);
        --sidebar-bg: #1e293b;
        
        /* Streamlit Theme Overrides */
        --background-color: #0f172a !important;
        --secondary-background-color: #0f172a !important;
        --text-color: #ffffff !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        line-height: 1.6;
        color: #ffffff !important;
    }

    /* Remove default Streamlit shadows and headers */
    header[data-testid="stHeader"] { background: transparent !important; }
    footer { visibility: hidden; }
    
    .main { 
        background-color: #0f172a;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0, transparent 50%), 
            radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.15) 0, transparent 50%);
    }

    /* --- SIDEBAR STYLING --- */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid var(--border-glass) !important;
    }
    
    section[data-testid="stSidebar"] div.stVerticalBlock {
        padding-top: 3.5rem !important;
    }

    /* Aggressive styling for sidebar toggle buttons */
    button[data-testid="stSidebarCollapse"] {
        background-color: #6366f1 !important;
        color: white !important;
        opacity: 1 !important;
        visibility: visible !important;
        border-radius: 8px !important;
        z-index: 100000 !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        box-shadow: 0 0 15px rgba(99, 102, 241, 0.8) !important;
    }

    button[data-testid="stSidebarCollapse"] svg {
        fill: white !important;
        color: white !important;
        transform: scale(1.2) !important;
    }

    button[data-testid="stSidebarCollapse"]:hover {
        background-color: #4f46e5 !important;
        transform: scale(1.05) !important;
    }

    /* Target the cache classes specifically as a fallback */
    .st-emotion-cache-1aplgmp, .st-emotion-cache-6q9sum {
        background-color: #6366f1 !important;
    }

    .sidebar-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid var(--border-glass);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }

    /* --- BRANDED TOP HEADER --- */
    .top-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border-glass);
        margin-bottom: 1rem;
    }
    .brand-container { display: flex; align-items: center; gap: 10px; }
    .brand-logo { font-size: 18px; font-weight: 700; color: white !important; letter-spacing: -0.5px; }
    .status-badge {
        font-size: 9px;
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80 !important;
        padding: 3px 8px;
        border-radius: 20px;
        border: 1px solid rgba(34, 197, 94, 0.25);
        display: flex; align-items: center; gap: 5px;
    }
    .status-dot { width: 5px; height: 5px; background: #4ade80; border-radius: 50%; box-shadow: 0 0 6px #4ade80; }

    .biz-label {
        color: #a5b4fc !important; /* Lighter Indigo */
        font-size: 10px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        margin-bottom: 12px;
        display: block;
    }

    .biz-desc {
        color: #f8fafc !important; /* Brighter White */
        font-size: 13px;
        font-weight: 500;
        line-height: 1.6;
        opacity: 0.9;
    }

    /* --- MESSAGE BUBBLES --- */
    div[data-testid="stChatMessageContent"] * {
        color: #ffffff !important;
    }
    
    div[data-testid="stChatMessageContent"] p {
        margin-bottom: 0 !important;
    }

    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0.5rem 0 !important;
        margin: 0 !important;
    }

    div[data-testid="stChatMessage"]:has(img[alt*="user"]) [data-testid="stChatMessageContent"] {
        background: var(--bg-glass) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: 18px 18px 0 18px !important;
        padding: 12px 20px !important;
    }
    
    div[data-testid="stChatMessage"]:has(svg), 
    div[data-testid="stChatMessage"]:has(img[alt*="assistant"]) [data-testid="stChatMessageContent"] {
        background: var(--bg-glass-bot) !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 0 18px 18px 18px !important;
        padding: 12px 20px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }

    /* --- CLEAN LAYOUT --- */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0f172a !important;
    }

    /* Custom Scrollbar */
    div[data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar { width: 4px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.2) !important;
        border-radius: 10px !important;
    }

    /* --- MOBILE RESPONSIVENESS --- */
    @media (max-width: 768px) {
        div[data-testid="stVerticalBlockBorderWrapper"] { height: 400px !important; }
    }

    /* --- ULTIMATE NO-WHITE BOTTOM FIX --- */
    div[data-testid="stBottom"], 
    div[data-testid="stBottom"] > div,
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] form,
    [data-testid="stChatInputTextArea"] {
        background-color: #0f172a !important;
        border: none !important;
    }

    [data-testid="stChatInput"] > div {
        background-color: rgba(30, 41, 59, 0.6) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: 14px !important;
        padding: 4px 12px !important;
    }

    [data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        font-weight: 500 !important;
        caret-color: #ffffff !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
    }

    /* Hide placeholder on focus */
    [data-testid="stChatInput"] textarea:focus::placeholder {
        color: transparent !important;
        -webkit-text-fill-color: transparent !important;
    }

    /* Buttons & Status Indicators */
    .stButton button {
        border-radius: 14px !important;
        background: var(--primary) !important;
        color: white !important;
        border: none !important;
        transition: all 0.2s ease;
    }

    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px var(--primary-glow);
    }

    /* Prompt Bubbles styling */
    .prompt-bubble {
        background: rgba(99, 102, 241, 0.1) !important;
        border: 1px solid rgba(99, 102, 241, 0.2) !important;
        border-radius: 12px !important;
        padding: 8px 12px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        font-size: 11px !important;
        color: #a5b4fc !important;
        margin-bottom: 8px !important;
        text-align: left !important;
        display: block !important;
        width: 100% !important;
    }

    .prompt-bubble:hover {
        background: rgba(99, 102, 241, 0.2) !important;
        border-color: var(--primary) !important;
        transform: translateX(4px) !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Business discovery
def list_businesses(chroma_persist_path: str):
    """List available businesses from Chroma collections."""
    try:
        client = chromadb.PersistentClient(path=chroma_persist_path)
        collections = client.list_collections()
        items = []
        for col in collections:
            name = col.name
            if name.startswith("business__"):
                name = name.replace("business__", "").replace("_", " ").title()
            items.append(name)
        return sorted(items)
    except Exception as e:
        print(f"Error listing businesses: {e}")
        return []

# Get businesses
businesses = list_businesses(CHROMA_PERSIST)

# Global App Warmup - Happens only once per server start
@st.cache_resource
def perform_global_warmup(biz_list):
    warmup_business_cache(biz_list)
    return True

if businesses:
    # Silent warmup
    perform_global_warmup(businesses)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_business" not in st.session_state:
    st.session_state.current_business = None
if "msg_input" not in st.session_state:
    st.session_state.msg_input = ""
if "business_description" not in st.session_state:
    st.session_state.business_description = ""
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

# --- SIDEBAR: BUSINESS SELECTION & MISSION ---
with st.sidebar:
    st.markdown('<div class="brand-logo" style="margin-bottom: 1rem;">🤖 QuickChat</div>', unsafe_allow_html=True)
    
    # Status Indicators in Sidebar
    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding: 0 5px;">
            <div class="status-badge">
                <div class="status-dot"></div>
                Concierge Active
            </div>
            <div style="font-size: 8px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;">PREMIUM AI</div>
        </div>
    """, unsafe_allow_html=True)
    
    if businesses:
        st.markdown('<span class="biz-label">ACTIVE BUSINESS</span>', unsafe_allow_html=True)
        # Handle initial selection if None
        default_biz = st.session_state.current_business if st.session_state.current_business else businesses[0]
        
        selected_business = st.selectbox(
            "Business",
            options=businesses,
            label_visibility="collapsed",
            index=businesses.index(default_biz) if default_biz in businesses else 0
        )
            
        # Clear session if business changes
        if selected_business != st.session_state.current_business:
            st.session_state.chat_history = []
            st.session_state.current_business = selected_business
            st.session_state.msg_input = ""
            st.session_state.business_description = ""
            st.session_state.is_generating = False
            st.rerun()
    else:
        selected_business = None
        st.error("📍 No businesses found.")

    if selected_business:
        if not st.session_state.business_description:
            cached_context = agent_router.business_context_cache.get(selected_business)
            if cached_context:
                st.session_state.business_description = cached_context
            else:
                with st.spinner("✨ Loading context..."):
                    try:
                        summary_query = "Give a very brief, one-sentence professional summary of what this business does."
                        res = process_query(
                            selected_business, 
                            summary_query, 
                            [], # Warmup query, no history needed
                            user_id=st.session_state.user_id
                        )
                        answer = res.get("answer", "Your AI support assistant • Ask anything about the business")
                        st.session_state.business_description = answer
                        agent_router.set_business_context(selected_business, answer)
                    except Exception:
                        st.session_state.business_description = "Your AI support assistant • Ask anything about the business"

        if st.session_state.business_description:
            st.markdown(f"""
            <div class="sidebar-card">
                <span class="biz-label">OUR MISSION</span>
                <div class="biz-desc">{st.session_state.business_description}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Generic Prompt Bubbles
        st.markdown('<span class="biz-label">QUICK COMMANDS</span>', unsafe_allow_html=True)
        
        prompts = [
            ("🕒 Business Hours", "What are your operational hours?"),
            ("📍 Location & Directions", "Where is the business located?"),
            ("✨ Services & Offerings", "What services or products do you offer?"),
            ("📞 Contact Details", "How can I get in touch with you?")
        ]
        
        for label, p_text in prompts:
            if st.button(label, key=f"prompt_{label}", use_container_width=True):
                st.session_state.is_generating = True
                st.session_state.chat_history.append({"role": "user", "text": p_text})
                st.rerun()

# Main header removed to maximize chat space.

# --- CHAT HISTORY CONTAINER ---
# Render the scrollable area first
with st.container(height=650):
    # Render previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("text", ""))

    # --- CHAT PROCESSING LOOP ---
    if st.session_state.is_generating and st.session_state.chat_history:
        if st.session_state.chat_history[-1].get("role") == "user":
            last_query = st.session_state.chat_history[-1].get("text", "")
            # We need the selected business here, so we must calculate it or move it up
            # For now, let's ensure we have a current_business in session_state
            selected_business = st.session_state.current_business
            if selected_business:
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            response = process_query(
                                selected_business, 
                                last_query, 
                                st.session_state.chat_history[:-1],
                                user_id=st.session_state.user_id
                            )
                            answer = response.get("answer", "I couldn't generate a response.")
                        except Exception as e:
                            answer = f"Error: {str(e)}"
                        
                        if st.session_state.is_generating:
                            st.markdown(answer)
                            st.session_state.chat_history.append({"role": "assistant", "text": answer})
                        
                st.session_state.is_generating = False
                st.rerun()

# Redundant bottom nav removed.

# --- SINGLE CHAT INPUT (STAYS AT BOTTOM) ---
if selected_business:
    prompt = st.chat_input("Ask anything about the business", key="chat_input_unique")

    if prompt:
        if st.session_state.is_generating:
            st.warning("Please wait...")
        else:
            st.session_state.is_generating = True
            st.session_state.chat_history.append({"role": "user", "text": prompt})
            st.rerun()

# --- THE ABSOLUTE FIX: STOP BUTTON AT FOOTER ---
if st.session_state.get("is_generating"):
    st.markdown("""
        <style>
            /* 1. Hide the native Send button */
            button[data-testid="stChatInputButton"] {
                visibility: hidden !important;
            }

            /* 2. Anchor our STOP button to the tray */
            .fixed-stop-container {
                position: fixed !important;
                bottom: 34px !important;
                right: 32px !important;
                z-index: 999999 !important;
            }

            button[key="stop_btn_absolute_final"] {
                background-color: #000000 !important;
                color: white !important;
                width: 32px !important;
                height: 32px !important;
                min-width: 32px !important;
                border-radius: 50% !important;
                border: none !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 0 !important;
            }

            button[key="stop_btn_absolute_final"] p { display: none !important; }
            button[key="stop_btn_absolute_final"]::after {
                content: '■';
                font-size: 11px;
                color: white;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="fixed-stop-container">', unsafe_allow_html=True)
    if st.button(" ", key="stop_btn_absolute_final"):
        st.session_state.is_generating = False
        st.session_state.chat_history.append({"role": "assistant", "text": "Stopped."})
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
