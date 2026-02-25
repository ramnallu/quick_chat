import os
import json
import sys
import pathlib
import chromadb
from datetime import datetime
from langchain_huggingface import HuggingFaceEmbeddings

# Ensure the project root is in the python path
root_path = pathlib.Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from app.agents.knowledge_manager import KnowledgeManagerAgent

LOG_FILE = "./data/unanswered_queries.json"
CHROMA_PATH = os.environ.get("CHROMA_PERSIST_PATH", "./data/chroma")

def sanitize_collection_name(name: str) -> str:
    import re
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    name = name.strip('_')
    if len(name) < 3:
        name = name + '_' * (3 - len(name))
    return name[:512]

def tune_from_logs():
    """Reads unanswered queries and uses the Teacher Agent to generate new knowledge."""
    if not os.path.exists(LOG_FILE):
        print("[System] No unanswered queries found to learn from.")
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        print(f"[Error] Failed to read logs: {e}")
        return

    if not logs:
        print("[System] Log file is empty.")
        return

    # Group logs by business
    business_logs = {}
    for entry in logs:
        biz_id = entry.get("business_id", "unknown")
        if biz_id not in business_logs:
            business_logs[biz_id] = []
        business_logs[biz_id].append(entry)

    km_agent = KnowledgeManagerAgent()
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    except Exception:
        client = chromadb.Client()

    for biz_id, entries in business_logs.items():
        print(f"\n[Learning] Processing {len(entries)} gaps for business: {biz_id}")
        
        # 1. Generate new FAQs from the gaps
        new_sections = km_agent.teach_from_unanswered(biz_id, entries)
        
        if not new_sections:
            print(f"[WARN] Teacher Agent returned no sections for {biz_id}")
            continue

        # 2. Ingest into ChromaDB
        collection_name = sanitize_collection_name(f"business__{biz_id.lower().replace(' ', '_')}")
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            collection = client.create_collection(name=collection_name)

        ids = [f"{biz_id}::learning::{i}" for i in range(len(new_sections))]
        texts = [s["text"] for s in new_sections]
        metadatas = [s["metadata"] for s in new_sections]
        embs = embeddings.embed_documents(texts)

        collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embs)
        print(f"[Success] Added {len(ids)} new learning insights to {collection_name}")

    # 3. Archive/Clear logs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = f"./data/unanswered_queries_archived_{timestamp}.json"
    os.rename(LOG_FILE, archive_path)
    print(f"\n[System] Original logs archived to: {archive_path}")

if __name__ == "__main__":
    tune_from_logs()
