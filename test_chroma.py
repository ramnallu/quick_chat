#!/usr/bin/env python3
"""Quick test to check if Chroma harvested documents."""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chromadb

# Try to connect and check collections
try:
    client = chromadb.PersistentClient(path="./data/chroma")
    collections = client.list_collections()
    print(f"Collections: {[c.name for c in collections]}")
    for col in collections:
        count = col.count()
        print(f"  {col.name}: {count} documents")
except Exception as e:
    print(f"Error: {e}")
