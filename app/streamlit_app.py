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
    initial_sidebar_state="collapsed"
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
        --bg-glass: rgba(255, 255, 255, 0.03);
        --border-glass: rgba(255, 255, 255, 0.1);
        --card-bg: rgba(30, 41, 59, 0.7);
        
        /* Streamlit Theme Overrides */
        --background-color: #0f172a !important;
        --secondary-background-color: #0f172a !important;
        --text-color: #ffffff !important;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Remove default Streamlit shadows and headers */
    header[data-testid="stHeader"] { background: transparent !important; }
    footer { visibility: hidden; }
    
    .main { 
        background-color: #0f172a;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.1) 0, transparent 50%), 
            radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.1) 0, transparent 50%);
    }

    .biz-label {
        color: #818cf8 !important; /* Brighter Indigo */
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 6px;
        display: block;
    }

    .biz-desc {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
        font-size: 15px;
        font-weight: 500;
        line-height: 1.5;
    }

    /* --- CLEAN FIXED LAYOUT --- */
    /* Hide the global window scrollbar */
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        background-color: #0f172a !important;
    }

    /* Target the sticky header row - simplified */
    div[data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"]) {
        background: #0f172a !important;
        border: 1px solid #475569 !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        margin-bottom: 20px !important;
    }

    /* Unified Chat Board - Single Border for all messages */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #0f172a !important;
        border: 1px solid #475569 !important;
        border-radius: 15px !important;
        padding: 10px !important;
        margin-bottom: 10px !important;
    }

    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding-top: 5px !important;
        padding-bottom: 5px !important;
    }

    div[data-testid="stChatMessageContent"] {
        background-color: transparent !important;
        border: none !important;
        color: #f1f5f9 !important;
        padding: 5px 10px !important;
        font-size: 15px;
    }

    /* Keep icons distinct but without bubbles */
    div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] {
        border-radius: 8px !important;
    }

    /* Custom Scrollbar ONLY for the internal container */
    div[data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar {
        width: 6px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar-thumb {
        background: #334155 !important;
        border-radius: 10px !important;
    }

    /* --- ULTIMATE NO-WHITE BOTTOM FIX --- */
    div[data-testid="stBottom"], 
    div[data-testid="stBottom"] > div,
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] form,
    [data-testid="stChatInputTextArea"] {
        background-color: #0f172a !important;
        background: #0f172a !important;
        color: #ffffff !important;
        border: none !important;
    }

    [data-testid="stChatInput"] > div {
        background-color: #0f172a !important;
        border: 1px solid #475569 !important;
        border-radius: 12px !important;
    }

    [data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #475569 !important;
        -webkit-text-fill-color: #475569 !important;
        opacity: 1 !important;
    }

    [data-testid="stChatInputButton"] svg {
        fill: #6366f1 !important;
    }

    /* Fixed visibility for selectboxes and other standard inputs */
    div[data-baseweb="select"] > div, div[data-testid="stSelectbox"] > div {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #475569 !important;
    }

    div[role="listbox"] {
        background-color: #1e293b !important;
        color: #ffffff !important;
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

# --- TOP NAVIGATION & BUSINESS SELECTION ---
with st.container():
    st.markdown('<div id="sticky-header-anchor"></div>', unsafe_allow_html=True)
    # We use columns to layout the selectbox and the description side-by-side
    col1, col2 = st.columns([1, 2.5])

with col1:
    if businesses:
        st.markdown('<span class="biz-label">BUSINESS</span>', unsafe_allow_html=True)
        selected_business = st.selectbox(
            "Business",
            options=businesses,
            label_visibility="collapsed",
            index=businesses.index(st.session_state.current_business) if st.session_state.current_business in businesses else 0
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

# ALWAYS Render the description in the second column if available
with col2:
    if selected_business:
        # Fetch business description dynamically using RAG if not already loaded in session
        if not st.session_state.business_description:
            # 1. Check Global Router Cache First (Instant)
            cached_context = agent_router.business_context_cache.get(selected_business)
            
            if cached_context:
                st.session_state.business_description = cached_context
            else:
                # 2. Fallback to RAG if cache is cold (Slow, happens only once)
                # Placing the spinner here ensures it appears in col2
                with st.spinner("✨ Loading business context..."):
                    try:
                        summary_query = "Give a very brief, one-sentence professional summary of what this business does."
                        res = process_query(
                            selected_business, 
                            summary_query, 
                            st.session_state.chat_history,
                            user_id=st.session_state.user_id
                        )
                        answer = res.get("answer", "Your AI support assistant • Ask anything")
                        st.session_state.business_description = answer
                        agent_router.set_business_context(selected_business, answer)
                    except Exception:
                        st.session_state.business_description = "Your AI support assistant • Ask anything"

        # Now render the description if it's available
        if st.session_state.business_description:
            st.markdown(f"""
            <span class="biz-label">MISSION & SERVICES</span>
            <div class="biz-desc">{st.session_state.business_description}</div>
            """, unsafe_allow_html=True)

if selected_business:
    # --- SCROLLABLE RESPONSE AREA ---
    # We use a container with a fixed height to provide its own scrollbar
    with st.container(height=500):
        # Render previous messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg.get("role", "assistant")):
                st.markdown(msg.get("text", ""))

        # --- CHAT PROCESSING LOOP ---
        if st.session_state.is_generating and st.session_state.chat_history:
            if st.session_state.chat_history[-1].get("role") == "user":
                last_query = st.session_state.chat_history[-1].get("text", "")
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
                        
                        # Only append the response if the user hasn't stopped the generation
                        if st.session_state.is_generating:
                            st.markdown(answer)
                            st.session_state.chat_history.append({"role": "assistant", "text": answer})
                        
                st.session_state.is_generating = False
                st.rerun()

    # --- SINGLE CHAT INPUT (STAYS AT BOTTOM) ---
    prompt = st.chat_input("Ask anything", key="chat_input_unique")

    if prompt:
        if st.session_state.is_generating:
            st.warning("Please wait...")
        else:
            st.session_state.is_generating = True
            st.session_state.chat_history.append({"role": "user", "text": prompt})
            st.rerun()

# --- THE ABSOLUTE FIX: STOP BUTTON AT FOOTER ---
# By placing this at the very end, it stays out of the chat history (no ghost boxes)
# and we use fixed positioning to put it in the tray.
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
