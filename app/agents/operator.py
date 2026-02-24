# --- GLOBAL SINGLETONS ---
# These ensure models are loaded once per application instance, not once per agent.
_GLOBAL_EMBEDDINGS = None
_GLOBAL_CHROMA_CLIENT = None

class OperatorAgent:
    """AI Operator Agent that handles customer queries using RAG.

    Uses similarity search on business documents to provide relevant answers.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.status = "idle" # idle or busy
        self.current_user = None
        self.onboarding_context = None

    def _get_embeddings(self):
        """Lazy initialization of embeddings as a global singleton."""
        global _GLOBAL_EMBEDDINGS
        if _GLOBAL_EMBEDDINGS is None:
            print(f"[System] Loading Embedding Model for {self.agent_id}...")
            try:
                from langchain.embeddings import HuggingFaceEmbeddings
            except Exception:
                try:
                    from langchain.embeddings.huggingface import HuggingFaceEmbeddings
                except Exception:
                    from sentence_transformers import SentenceTransformer
                    class HuggingFaceEmbeddings:
                        def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
                            self.model = SentenceTransformer(model_name)
                        def embed_documents(self, texts):
                            embs = self.model.encode(texts, convert_to_numpy=True)
                            return [emb.tolist() for emb in embs]
                        def embed_query(self, text: str):
                            emb = self.model.encode([text], convert_to_numpy=True)[0]
                            return emb.tolist()

            _GLOBAL_EMBEDDINGS = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return _GLOBAL_EMBEDDINGS

    def _get_chroma_client(self):
        """Lazy initialization of Chroma client as a global singleton."""
        global _GLOBAL_CHROMA_CLIENT
        if _GLOBAL_CHROMA_CLIENT is None:
            import chromadb
            try:
                _GLOBAL_CHROMA_CLIENT = chromadb.PersistentClient(path="./data/chroma")
            except Exception:
                _GLOBAL_CHROMA_CLIENT = chromadb.Client()
        return _GLOBAL_CHROMA_CLIENT

    def _sanitize_collection_name(self, name: str) -> str:
        """Convert a business name into a valid Chroma collection name."""
        import re
        name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
        name = name.strip('_')
        if len(name) < 3:
            name = name + '_' * (3 - len(name))
        return name[:512]

    def handle_task(self, task: dict) -> dict:
        """Handle a customer query using RAG (Retrieval-Augmented Generation).

        Args:
            task: dict with 'query' and 'business_id' keys

        Returns:
            dict with 'agent_id', 'answer', and 'sources'
        """
        query = task.get("query", "")
        business_id = task.get("business_id", "")

        if not query or not business_id:
            return {
                "agent_id": self.agent_id,
                "answer": "Missing query or business information.",
                "sources": []
            }

        try:
            # Convert display name to collection name format
            folder_name = business_id.lower().replace(' ', '_')
            collection_name = self._sanitize_collection_name(f"business__{folder_name}")

            # Get Chroma collection
            client = self._get_chroma_client()
            collection = client.get_collection(collection_name)

            # Perform similarity search
            embeddings = self._get_embeddings()
            query_embedding = embeddings.embed_query(query)

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=4,
                include=["documents", "metadatas", "distances"]
            )

            # Extract retrieved documents
            retrieved_docs = []
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    retrieved_docs.append({
                        "content": doc,
                        "metadata": results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {},
                        "distance": results.get("distances", [[]])[0][i] if results.get("distances") else None
                    })

            # Generate answer from retrieved context
            answer = self._generate_answer_from_context(query, retrieved_docs)

            return {
                "agent_id": self.agent_id,
                "answer": answer,
                "sources": retrieved_docs
            }

        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "answer": f"Sorry, I encountered an error while processing your query: {str(e)}",
                "sources": []
            }

    def _generate_answer_from_context(self, query: str, retrieved_docs: list) -> str:
        """Generate an answer from retrieved documents.
        
        This is a completely generic method that works for ANY business.
        It only performs RAG (Retrieval Augmented Generation):
        1. Retrieve relevant documents
        2. Return the most relevant content
        3. Optionally combine multiple sections if needed
        
        NOTE: Response formatting, natural language generation, and context-aware
        logic (like extracting "today's" schedule) should be handled by a separate
        Response Generation layer, not in this generic Operator.
        """
        if not retrieved_docs:
            return "I couldn't find information to answer that question."

        # Sort by relevance (lowest distance first)
        sorted_docs = sorted(retrieved_docs, key=lambda x: x.get("distance", 1.0))

        # Combine all retrieved documents into a single context string
        # This gives the LLM the maximum amount of information to work with.
        combined_context = []
        for i, doc in enumerate(sorted_docs):
            content = doc["content"].strip()
            if content:
                combined_context.append(f"[Document {i+1}]:\n{content}")

        return "\n\n---\n\n".join(combined_context)
