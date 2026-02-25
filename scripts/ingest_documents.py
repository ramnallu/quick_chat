import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings
import PyPDF2
from langchain_huggingface import HuggingFaceEmbeddings

MANIFEST_NAME = "ingest_manifest.json"


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_text_from_file(path: Path) -> str:
    if path.suffix.lower() in (".md", ".txt"):
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".pdf" and PyPDF2 is not None:
        text = []
        with path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text.append(page.extract_text() or "")
                except Exception:
                    continue
        return "\n".join(text)
    # fallback
    return path.read_text(encoding="utf-8", errors="ignore")


def list_top_level_dirs(source_dir: Path) -> List[Path]:
    return [p for p in source_dir.iterdir() if p.is_dir()]


def load_docs_from_dir(business_dir: Path) -> List[dict]:
    docs = []
    for p in business_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".md", ".txt", ".pdf"):
            try:
                content = load_text_from_file(p)
                # Split content into semantic sections for better RAG
                sections = split_into_sections(content, str(p))
                docs.extend(sections)
            except Exception as e:
                print(f"warning: failed to load {p}: {e}")
    return docs


def split_into_sections(content: str, source_path: str) -> List[dict]:
    """Split document into semantic sections based on headers."""
    sections = []
    lines = content.split('\n')
    current_section = {"title": "General", "content": [], "source": source_path}

    for line in lines:
        line = line.strip()
        if line.startswith('# '):  # Main header
            # Save previous section if it has content
            if current_section["content"]:
                current_section["content"] = '\n'.join(current_section["content"]).strip()
                if current_section["content"]:
                    sections.append({
                        "path": source_path,
                        "text": current_section["content"],
                        "section": current_section["title"],
                        "metadata": {"section": current_section["title"], "source": source_path}
                    })

            # Start new section
            current_section = {
                "title": line[2:].strip(),  # Remove '# '
                "content": [],
                "source": source_path
            }
        elif line.startswith('## '):  # Sub-header
            # Save previous subsection if it has content
            if current_section["content"]:
                current_section["content"] = '\n'.join(current_section["content"]).strip()
                if current_section["content"]:
                    sections.append({
                        "path": source_path,
                        "text": current_section["content"],
                        "section": current_section["title"],
                        "metadata": {"section": current_section["title"], "source": source_path}
                    })

            # Start new subsection
            current_section = {
                "title": line[3:].strip(),  # Remove '## '
                "content": [],
                "source": source_path
            }
        else:
            current_section["content"].append(line)

    # Add the last section
    if current_section["content"]:
        current_section["content"] = '\n'.join(current_section["content"]).strip()
        if current_section["content"]:
            sections.append({
                "path": source_path,
                "text": current_section["content"],
                "section": current_section["title"],
                "metadata": {"section": current_section["title"], "source": source_path}
            })

    # If no sections were found, treat the whole document as one section
    if not sections:
        sections.append({
            "path": source_path,
            "text": content.strip(),
            "section": "General",
            "metadata": {"section": "General", "source": source_path}
        })

    return sections


def sanitize_collection_name(name: str) -> str:
    """Convert a business name into a valid Chroma collection name.
    Chroma allows: a-zA-Z0-9._- , must be 3-512 chars, start/end with [a-zA-Z0-9]
    """
    # Replace spaces and invalid chars with underscores
    import re
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    # trim underscores at start/end
    name = name.strip('_')
    # ensure at least 3 chars
    if len(name) < 3:
        name = name + '_' * (3 - len(name))
    # truncate to 512 if too long
    return name[:512]


def ensure_manifest(chroma_persist: Path):
    chroma_persist.mkdir(parents=True, exist_ok=True)
    manifest_path = chroma_persist / MANIFEST_NAME
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {}


def save_manifest(chroma_persist: Path, manifest: dict):
    (chroma_persist / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def ingest_folder(source_dir: Path, chroma_persist: Path, model_name: str, batch_size: int = 256):
    settings = Settings(persist_directory=str(chroma_persist), chroma_db_impl="duckdb+parquet")
    try:
        client = chromadb.Client(settings)
    except Exception:
        try:
            client = chromadb.PersistentClient(path=str(chroma_persist))
        except Exception:
            client = chromadb.Client()

    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    from app.agents.knowledge_manager import KnowledgeManagerAgent
    km_agent = KnowledgeManagerAgent()

    manifest = ensure_manifest(chroma_persist)

    for business_dir in list_top_level_dirs(source_dir):
        business_id = business_dir.name
        collection_name = sanitize_collection_name(f"business__{business_id}")
        print(f"Ingesting business: {business_id} (collection: {collection_name})")
        docs = load_docs_from_dir(business_dir)
        to_index = []

        # --- AUTO-GLOSSARY GENERATION ---
        # We concatenate all text to give the agent full context
        combined_text = "\n\n".join([d["text"] for d in docs])
        glossary_sections = km_agent.generate_glossary(business_id, combined_text)
        
        # Add glossary sections to the end of the doc list
        for g_sec in glossary_sections:
            to_index.append({
                "id": f"{business_id}::auto_glossary::{g_sec['id']}",
                "text": g_sec["text"],
                "metadata": g_sec["metadata"]
            })

        # Group docs by file path to check manifest once per file
        docs_by_file = {}
        for d in docs:
            path = d["path"]
            if path not in docs_by_file:
                docs_by_file[path] = []
            docs_by_file[path].append(d)

        to_index = []
        for file_path, file_docs in docs_by_file.items():
            p = Path(file_path)
            chksum = checksum(p)
            prev = manifest.get(business_id, {}).get(file_path) if manifest.get(business_id) else None
            if prev == chksum:
                continue

            # Process all sections from this file
            for d in file_docs:
                section_id = f"{business_id}::{p.name}::{d['section']}"
                # Prepend business name to the text for better global context during retrieval
                enhanced_text = f"Business: {business_id}\nSection: {d['section']}\nContent: {d['text']}"
                to_index.append({
                    "id": section_id,
                    "text": enhanced_text,
                    "metadata": {
                        "source": str(p),
                        "business_id": business_id,
                        "section": d["section"],
                        **d.get("metadata", {})
                    },
                })

            # update manifest once per file
            manifest.setdefault(business_id, {})[file_path] = chksum

        if not to_index:
            print(f"No new docs for {business_id}")
            continue

        texts = [t["text"] for t in to_index]
        metadatas = [t["metadata"] for t in to_index]
        ids = [t["id"] for t in to_index]

        # embed in batches
        embeddings_list = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            emb = embeddings.embed_documents(batch)
            embeddings_list.extend(emb)

        # Use sanitized collection name
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            collection = client.create_collection(name=collection_name)

        # upsert ensures we update existing documents if IDs match
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings_list)
        print(f"Upserted {len(ids)} vectors into {collection_name}")

    save_manifest(chroma_persist, manifest)
    print("Ingestion complete")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--chroma-persist", required=True)
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    ingest_folder(Path(args.source_dir), Path(args.chroma_persist), args.model, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
