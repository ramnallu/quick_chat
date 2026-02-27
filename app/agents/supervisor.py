import os
from langchain_ollama import OllamaLLM
from langchain_groq import ChatGroq

class SupervisorAgent:
    """Intelligent Supervisor Agent.
    
    Now handles Query Rewriting to ensure conversational context
    is resolved into a standalone search query.
    """

    def __init__(self):
        self.metrics = {}
        self.provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
        
        if self.provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY")
            model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.llm = ChatGroq(api_key=api_key, model_name=model, temperature=0.0)
        else:
            url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
            model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
            self.llm = OllamaLLM(base_url=url, model=model, temperature=0.0)

    def rewrite_query(self, query: str, chat_history: list) -> str:
        """Rewrite a potentially contextual query into a standalone search query."""
        if not chat_history:
            return query

        history_text = ""
        # Guard against sliding if chat_history might be typed incorrectly
        truncated_history = chat_history[-3:] if len(chat_history) >= 3 else chat_history
        for msg in truncated_history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('text', '')}\n"

        prompt = (
            "### TASK ###\n"
            "Rewrite the user's 'New Question' into a standalone search query for a vector database.\n\n"
            "### CRITICAL RULES ###\n"
            "1. RESOLVE NUMBERS: Identify exact names from history.\n"
            "2. PRESERVE SUBJECT: Use specific entity names.\n"
            "3. BE DESCRIPTIVE: Output a complete sentence.\n"
            "4. MAINTAIN CATEGORY: If the user asks for a specific category (e.g., 'chicken', 'vegan'), ensure the rewritten query explicitly mentions it.\n\n"
            "### CONVERSATION HISTORY ###\n"
            f"{history_text}\n"
            f"### NEW QUESTION ###\n{query}\n\n"
            "Rewritten Standalone Query:"
        )

        try:
            response = self.llm.invoke(prompt)
            if hasattr(response, "content"):
                return response.content.strip().strip('"')
            return str(response).strip().strip('"')
        except Exception as e:
            print(f"[WARN] Supervisor failed to rewrite query: {e}")
            return query

    def assign_task(self, task, router, chat_history: list = None):
        """Coordinate the task, potentially rewriting the query first."""
        if chat_history:
            original_query = task.get("query", "")
            task["query"] = self.rewrite_query(original_query, chat_history)
            
        return router.assign(task)

    def report(self, agent_id, info):
        self.metrics[agent_id] = info

    def get_metrics(self):
        return self.metrics
