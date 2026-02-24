import sys
import os
import pathlib
import chromadb
from datetime import datetime

# Add root to path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import process_query, CHROMA_PERSIST

def run_db_health_check():
    print("--- Database Health Check ---")
    try:
        from app.api import CHROMA_PERSIST
        client = chromadb.PersistentClient(path=CHROMA_PERSIST)
        collections = client.list_collections()
        if not collections:
            print("❌ No collections found. Please run ingestion first.")
            return False
            
        print(f"✅ Found {len(collections)} collections:")
        for col in collections:
            print(f"  - {col.name}: {col.count()} documents")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def run_rag_smoke_test():
    print("\n--- RAG Integration Smoke Test ---")
    try:
        from app.api import CHROMA_PERSIST
        client = chromadb.PersistentClient(path=CHROMA_PERSIST)
        collections = client.list_collections()
        
        if not collections:
            return
            
        # Pick the first business collection
        biz_col = [c for c in collections if c.name.startswith("business__")][0]
        biz_id = biz_col.name.replace("business__", "")
        
        query = "What is the primary service or product offered?"
        print(f"Testing Business: {biz_id}")
        print(f"Query: {query}")
        
        result = process_query(biz_id.replace("_", " ").title(), query)
        answer = result.get('answer', 'No answer returned.')
        
        print("\nAssistant Response:")
        print("-" * 50)
        print(answer)
        print("-" * 50)
        print("✅ RAG Pipeline is functional.")
        
    except Exception as e:
        print(f"❌ RAG Pipeline error: {e}")

if __name__ == "__main__":
    db_ok = run_db_health_check()
    if db_ok:
        run_rag_smoke_test()
