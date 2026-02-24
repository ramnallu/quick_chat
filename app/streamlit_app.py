import os
import sys
import pathlib
import uuid
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
    layout="wide"
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hide default elements */
    footer { visibility: hidden; }
    header { visibility: hidden; }
    .main { padding: 0; }
    
    /* Message styling */
    .message-container {
        display: flex;
        margin-bottom: 20px;
        animation: slideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-message { justify-content: flex-end; }
    
    .message-bubble {
        padding: 14px 20px;
        border-radius: 20px;
        max-width: 75%;
        word-wrap: break-word;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        font-size: 15px;
        line-height: 1.5;
    }
    
    .user-bubble {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border-bottom-right-radius: 4px;
    }
    
    .assistant-bubble {
        background-color: #f3f4f6;
        color: #1f2937;
        border-bottom-left-radius: 4px;
        border: 1px solid #e5e7eb;
    }
    
    /* Business header - Ribbon Style */
    .business-header {
        padding: 24px 30px;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: white;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px -5px rgba(0, 0, 0, 0.2);
        text-align: center;
    }
    
    .business-header h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: #ffffff; /* Solid white for maximum clarity on ribbon */
    }
    
    .business-header p {
        margin: 8px 0 0 0;
        font-size: 14px;
        font-weight: 400;
        opacity: 0.9;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Input area styling */
    /* Chat Input Premium Styling */
    div[data-testid="stChatInput"] {
        padding-bottom: 20px !important;
    }
    
    div[data-testid="stChatInput"] > div {
        background-color: #f9fafb !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 26px !important;
        padding: 4px 8px !important;
    }

    button[data-testid="stChatInputButton"] {
        background-color: #111827 !important;
        border-radius: 50% !important;
        width: 32px !important;
        height: 32px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: white !important;
        border: none !important;
        margin-right: 4px !important;
    }
    
    button[data-testid="stChatInputButton"]:hover {
        background-color: #374151 !important;
    }

    /* General Button styling */
    .stButton button {
        border-radius: 12px !important;
        padding: 10px 20px !important;
        font-weight: 500 !important;
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
    with st.sidebar:
        with st.status("🚀 Warming up agents...", expanded=False) as status:
            perform_global_warmup(businesses)
            status.update(label="✅ Operators are ready!", state="complete", expanded=False)

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

# Sidebar business selector
st.sidebar.markdown("# 🤖 QuickChat")
if businesses:
    selected_business = st.sidebar.selectbox(
        "Choose a Business",
        options=businesses,
        help="Select which business you want to chat with"
    )
    
    # Clear session if business changes
    if selected_business != st.session_state.current_business:
        st.session_state.chat_history = []
        st.session_state.current_business = selected_business
        st.session_state.msg_input = ""
        st.session_state.business_description = ""
        st.session_state.is_generating = False # Reset blocking state
        st.rerun()
else:
    selected_business = None
    st.sidebar.info("📍 No businesses found. Run the ingestion script to add business data.")

# Fetch business description dynamically using RAG if not already loaded in session
if selected_business and not st.session_state.business_description:
    # 1. Check Global Router Cache First (Instant)
    cached_context = agent_router.business_context_cache.get(selected_business)
    
    if cached_context:
        st.session_state.business_description = cached_context
    else:
        # 2. Fallback to RAG if cache is cold (Slow, happens only once)
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

# Main header - Single block to ensure containment inside the styled ribbon
if selected_business:
    header_html = f"""
    <div class="business-header">
        <h1>💬 {selected_business}</h1>
        <p>{st.session_state.business_description}</p>
    </div>
    """
else:
    header_html = """
    <div class="business-header">
        <h1>QuickChat</h1>
        <p>Intelligent customer support powered by RAG</p>
    </div>
    """
st.markdown(header_html, unsafe_allow_html=True)

if selected_business:
    # --- CONSOLIDATED CHAT UI LOGIC ---
    # Render previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("text", ""))


    # 1. Global CSS for the Pill Tray
    st.markdown("""
        <style>
            div[data-testid="stChatInput"] { padding-bottom: 20px !important; }
            div[data-testid="stChatInput"] > div {
                border-radius: 28px !important;
                border: 1px solid #e5e7eb !important;
                background-color: #ffffff !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
            }
            /* Styling for the Send/Stop button */
            button[data-testid="stChatInputButton"] {
                background-color: #000000 !important;
                border-radius: 50% !important;
                width: 32px !important;
                height: 32px !important;
                min-width: 32px !important;
                border: none !important;
                padding: 0 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            button[data-testid="stChatInputButton"] svg { display: none !important; }
            button[data-testid="stChatInputButton"]::after {
                content: '↑';
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- SINGLE CHAT INPUT LOOP ---
    prompt = st.chat_input("Ask anything", key="chat_input_unique")

    if prompt:
        if st.session_state.is_generating:
            st.warning("Please wait...")
        else:
            st.session_state.is_generating = True
            st.session_state.chat_history.append({"role": "user", "text": prompt})
            st.rerun()

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

