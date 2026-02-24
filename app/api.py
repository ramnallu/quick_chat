import os
from app.graph import app_graph, agent_router

CHROMA_PERSIST = os.environ.get("CHROMA_PERSIST_PATH", "./data/chroma")

def process_query(business_id: str, user_query: str, chat_history: list = None, user_id: str = "default_user") -> dict:
    """Process a user query using LangGraph."""
    if chat_history is None:
        chat_history = []
        
    print(f"[DEBUG] Processing query for {business_id} (User: {user_id}): {user_query}")

    # Initialize graph state
    initial_state = {
        "user_id": user_id,
        "business_id": business_id,
        "query": user_query,
        "chat_history": chat_history,
        "rewritten_query": "",
        "context": "",
        "sources": [],
        "answer": ""
    }

    # Run the graph
    try:
        final_state = app_graph.invoke(initial_state)
        
        return {
            "answer": final_state.get("answer", "I couldn't generate a response."),
            "sources": final_state.get("sources", [])
        }
    except Exception as e:
        print(f"[ERROR] Graph execution failed: {e}")
        return {
            "answer": f"An error occurred: {str(e)}",
            "sources": []
        }

def warmup_business_cache(businesses: list):
    """Pre-populate the Router cache for all businesses."""
    from app.graph import agent_router
    print(f"[System] Warming up cache for {len(businesses)} businesses...")
    
    for biz_id in businesses:
        if biz_id not in agent_router.business_context_cache:
            try:
                summary_query = "Give a very brief, one-sentence professional summary of what this business does."
                res = process_query(biz_id, summary_query, [], user_id="system_warmup")
                answer = res.get("answer", "AI support assistant")
                agent_router.set_business_context(biz_id, answer)
            except Exception as e:
                print(f"[WARN] Failed to warm up {biz_id}: {e}")
    print("[System] Warm-up complete.")
