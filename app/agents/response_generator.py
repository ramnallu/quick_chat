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

    def generate(self, query: str, raw_documents: str, chat_history: list = None) -> str:
        """Synthesize a natural, conversational response."""
        if not raw_documents or not raw_documents.strip():
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
            "You are a strict Customer Support Assistant for a local business. "
            "Your ONLY source of truth is the 'Context from business documents'.\n\n"
            "### GUIDELINES ###\n"
            "1. PRIORITIZE specific names, prices, and terminology from the context.\n"
            "2. DO NOT generalize or guess. If it's not in the context, say you don't know.\n"
            "3. VERTICAL LISTS: When listing multiple items, you MUST use a vertical markdown list (1., 2., 3.).\n"
            "4. SPACING: Use double newlines between numbered points. DO NOT write items as a single paragraph.\n"
            "5. BOLDING: Bold the names of products or services using **double asterisks**.\n"
            "6. PRICES: You MUST include the price of every item mentioned if it is available in the context.\n"
            "7. PRECISION: Include specific details like full addresses, exact opening hours, and phone numbers if they are present in the context.\n"
            "8. STRICT SUBJECT MATCHING: If the user asks for a specific subject (e.g., 'chicken', 'vegan', '24/7'), DO NOT list items that do not match that exact subject. "
            "For example, if asked for 'chicken starters', EXCLUDE Goat, Lamb, or Shrimp even if they are in the same 'Non-Vegetarian' section.\n"
            "9. COMPLETENESS: When listing products or services, you MUST include EVERY relevant item found in the context that matches the user's request. DO NOT skip valid entries.\n\n"
            "### CONVERSATION HISTORY ###\n"
            f"{history_text}\n"
            "### CONTEXT FROM BUSINESS DOCUMENTS ###\n"
            f"{raw_documents}\n\n"
            f"### NEW CUSTOMER QUESTION ###\n{query}\n\n"
            "Assistant Answer:"
        )

        try:
            response = self.llm.invoke(system_prompt)
            if hasattr(response, "content"):
                return response.content.strip()
            return str(response).strip()
        except Exception as e:
            print(f"[ERROR] Response generation failed: {e}")
            return self._fallback_format(raw_documents)

    def _fallback_format(self, content: str) -> str:
        """Basic formatting fallback."""
        if not isinstance(content, str):
            return "Information is currently unavailable."
        return "Here's what I found in our records:\n\n" + content

