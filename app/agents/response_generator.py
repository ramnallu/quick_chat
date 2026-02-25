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
            "Your MISSION is to provide accurate information based SOLELY on the provided context.\n\n"
            "### CONTEXT TYPES ###\n"
            "1. [Glossary]: Authoritative definitions of business-specific terminology.\n"
            "2. [Learning Insights]: System-updated responses for previously missing information.\n"
            "3. [General Document/Section]: Standard business records.\n\n"
            "### GUIDELINES ###\n"
            "1. **STRICT DOMAIN BOUNDARY**: You are ONLY an expert for **{business_id}**. If a user asks a question unrelated to this business or its industry (e.g., asking about food at a gym), politely state you can only assist with **{business_id}**.\n"
            "2. **STRICT SUBJECT MATCHING**: When asked for specific categories (e.g., 'chicken', 'vegan', '24/7'), you MUST exclude items that do not match. For example, if asked for 'chicken starters', EXCLUDE Goat, Lamb, or Shrimp even if they are in the same section.\n"
            "3. **SOURCE OF TRUTH**: Use the provided context as your only source. You MUST use [Glossary] entries for business-related terminology.\n"
            "4. **VERTICAL LISTS**: Use numbered markdown lists (1., 2., 3.) for multi-item responses.\n"
            "5. **SPACING**: Use double newlines between points.\n"
            "6. **BOLDING**: Bold product/service names using **double asterisks**.\n"
            "7. **COMPLETENESS**: Include EVERY relevant item found in the context that matches the user's request.\n"
            "8. **NO GUESSING**: If the answer is not in the context or glossary for this business, say you don't know.\n\n"
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

