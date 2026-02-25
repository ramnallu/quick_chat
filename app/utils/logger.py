import json
import os
from datetime import datetime

LOG_FILE = "./data/unanswered_queries.json"

def log_unanswered_query(business_id: str, query: str, reason: str = "no_context"):
    """
    Logs a query that the system could not answer into a JSON file for future tuning.
    
    Args:
        business_id (str): The ID of the business the query was for.
        query (str): The user's original query.
        reason (str): Why it was unanswered ('no_context', 'llm_refusal', etc.)
    """
    # Ensure directories exist
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "business_id": business_id,
        "query": query,
        "reason": reason
    }
    
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # If file is corrupt or empty, start fresh
            data = []
            
    data.append(log_entry)
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"[Logger] Logged unanswered query for {business_id}: {query}")
