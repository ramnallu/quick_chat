# Local Business Support - MVP

Quickstart for the MVP (Streamlit UI + LangChain + Chroma ingestion).

Requirements
```
python -m venv .venv
.\.venv\Scripts\activate    # Windows
source .venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
pip install langgraph langchain-ollama langchain-groq
```

Ingest documents (example):
```
Remove-Item -Path ".\data\chroma" -Recurse -Force 2>$null; .\.venv\Scripts\python.exe scripts/ingest_documents.py --source-dir ./data --chroma-persist ./data/chroma --model sentence-transformers/all-MiniLM-L6-v2
```

Run Streamlit app:
```
taskkill /f /im streamlit.exe 2>$null; .\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

## Configuration (Ollama)

The system uses **LangGraph** for orchestration and **LangChain** for LLM integration, supporting both **Ollama** (local) and **Groq** (cloud).

### Local Testing Customization
You can customize the LLM connection using environment variables:

- `LLM_PROVIDER`: choice of `ollama` or `groq` (default: `ollama`)
- `OLLAMA_URL`: The API endpoint (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: The model name to use (default: `qwen2.5-coder:7b`)
- `GROQ_API_KEY`: Required if using Groq
- `GROQ_MODEL`: Groq model name (default: `llama-3.3-70b-versatile`)

Example for Windows PowerShell:
```powershell
$env:LLM_PROVIDER="groq"
$env:GROQ_API_KEY="your_key_here"
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

## Deployment to Hugging Face Spaces

1. Create a new Space (Streamlit) under your HF account.
2. Push this repo to the Space remote (see `scripts/deploy_hf_space.sh`).

## Notes
- For multi-user or production, consider using hosted vector DB (Pinecone, Chroma Cloud) and running backend separately.
- Update `CHROMA_PERSIST_PATH`, `EMBEDDING_MODEL`, `OLLAMA_URL`, and `OLLAMA_MODEL` via environment variables as needed.
