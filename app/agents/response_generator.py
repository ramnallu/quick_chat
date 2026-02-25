import os
from langchain_ollama import OllamaLLM
from langchain_groq import ChatGroq

class ResponseGenerator:
    """Converts raw retrieved documents into natural responses using LangChain."""

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
        
        if self.provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY")
            model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.llm = ChatGroq(api_key=api_key, model_name=model, temperature=0.0)
        else:
            url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
            model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
            self.llm = OllamaLLM(base_url=url, model=model, temperature=0.0)

    def generate(self, query: str, raw_documents: str, chat_history: list = None, business_id: str = "unknown") -> str:
        """Synthesize a natural, conversational response."""
        from app.utils.logger import log_unanswered_query
        
        if not raw_documents or not raw_documents.strip():
            log_unanswered_query(business_id, query, reason="no_context_found")
            return "I couldn't find information to answer that question. Could you rephrase or try another question?"

        if chat_history is None:
            chat_history = []

        history_text = ""
        # Truncate history and use .get() for type safety with the linter
        truncated = chat_history[-3:] if len(chat_history) >= 3 else chat_history
        for msg in truncated:
            role = "Customer" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('text', '')}\n"

        system_prompt = (
            "### INSTRUCTION ###\n"
            f"You are a professional Customer Support Assistant for the business: **{business_id}**.\n"
            "Your MISSION is to provide 100% accurate information based ONLY on the provided context.\n\n"
            "### CONTEXT TYPES ###\n"
            "1. [Glossary]: Authoritative definitions of business-specific terminology.\n"
            "2. [Learning Insights]: System-updated responses for previously missing information.\n"
            "3. [General Document/Section]: Standard business records.\n\n"
            "### RULES OF ENGAGEMENT ###\n"
            "1. **STRICT DOMAIN BOUNDARY**: You are ONLY an expert for **{business_id}**. Refuse unrelated queries.\n"
            "2. **CATEGORY PRECISION (CRITICAL)**: If asked for a specific category (e.g., 'chicken', 'vegan'), YOU MUST SCAN EVERY LINE. If an item in the context is NOT 'chicken' (like Goat, Lamb, or Shrimp), you MUST EXCLUDE it. Even if 'Goat Sukha' is in the same 'Appetizers' section as 'Chilli Chicken', only include 'Chilli Chicken'. Do NOT be helpful by providing unrelated items.\n"
            "3. **NEGATIVE CHECK**: Before outputting an item, ask: 'Does this item explicitly contain the subject requested?'. If the user asked for 'Chicken', and the item is 'Shrimp Manchurian', DISCARD IT.\n"
            "4. **NO INVERSE HALLUCINATION**: Never claim the business doesn't offer something (like Goat) if you just saw it in the context. If you previously made a mistake, simply apologize for the error without denying the item's existence.\n"
            "5. **SOURCE OF TRUTH**: Use context ONLY. Use [Glossary] for terminology.\n"
            "6. **FORMAT**: Vertical numbered markdown lists. Double newlines between points. Bold product names.\n"
            "7. **NO GUESSING**: If information is missing, say you don't know.\n\n"
            "### CONVERSATION HISTORY ###\n"
            f"{history_text}\n"
            "### CONTEXT FROM BUSINESS DOCUMENTS ###\n"
            f"{raw_documents}\n\n"
            f"### NEW CUSTOMER QUESTION ###\n{query}\n\n"
            "Assistant Answer:"
        )

        try:
            response = self.llm.invoke(system_prompt)
            answer = ""
            if hasattr(response, "content"):
                answer = response.content.strip()
            else:
                answer = str(response).strip()

            # Check if LLM explicitly said it doesn't know
            refusal_keywords = ["don't know", "do not know", "not in the context", "no information", "cannot find", "sorry, i don't"]
            if any(kw in answer.lower() for kw in refusal_keywords):
                log_unanswered_query(business_id, query, reason="llm_refusal")

            return answer

        except Exception as e:
            print(f"[ERROR] Response generation failed: {e}")
            log_unanswered_query(business_id, query, reason=f"error: {str(e)}")
            return self._fallback_format(raw_documents)

    def _fallback_format(self, content: str) -> str:
        """Basic formatting fallback."""
        if not isinstance(content, str):
            return "Information is currently unavailable."
        return "Here's what I found in our records:\n\n" + content

