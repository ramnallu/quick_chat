import chromadb
import os

persist_path = "./data/chroma"
client = chromadb.PersistentClient(path=persist_path)
collections = client.list_collections()

for coll in collections:
    print(f"Collection: {coll.name}")
    results = coll.get(limit=1)
    if results["documents"]:
        print(f"Sample Doc: {results['documents'][0][:200]}...")
    print("-" * 20)
