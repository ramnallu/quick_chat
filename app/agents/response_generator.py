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
            "You are a helpful Customer Support Assistant for a local business. "
            "Your main source of truth is the 'Context from business documents'.\n\n"
            "### CONTEXT TYPES ###\n"
            "1. [Glossary]: Authoritative definitions of business-specific terminology or regional concepts.\n"
            "2. [Learning Insights]: Recent updates or frequently asked questions that were specifically teacher-approved.\n"
            "3. [General Document/Section]: Standard business information.\n\n"
            "### GUIDELINES ###\n"
            "1. PRIORITIZE information labeled as [Glossary] or [Learning Insights] for definitions and edge cases.\n"
            "2. DO NOT generalize or guess if info is missing. However, you MUST use [Glossary] entries to explain terms to the customer.\n"
            "3. VERTICAL LISTS: When listing multiple items, you MUST use a vertical markdown list (1., 2., 3.).\n"
            "4. SPACING: Use double newlines between numbered points. DO NOT write items as a single paragraph.\n"
            "5. BOLDING: Bold the names of products or services using **double asterisks**.\n"
            "6. PRICES: Include the price of every item mentioned if it is available in the context.\n"
            "7. PRECISION: Include specific details like addresses and opening hours if they are present.\n"
            "8. STRICT SUBJECT MATCHING: If the user asks for a specific subject, DO NOT list irrelevant items.\n"
            "9. COMPLETENESS: Include EVERY relevant item found in the context for list requests.\n\n"
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

