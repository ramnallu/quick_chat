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
        
        # If no documents are found, we still proceed but note the lack of specific context 
        # to allow the LLM to use its domain knowledge for relevant terms.
        has_context = True
        if not raw_documents or not raw_documents.strip():
            has_context = False
            raw_documents = "[No specific records found in the business database for this query.]"

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
            "Your MISSION is to provide 100% accurate information based primarily on the provided context. "
            "However, you ARE expected to use your domain expertise to explain terms, ingredients, "
            "cultural references, or industry-standard concepts related to the business and its name, "
            "even if they are not explicitly defined in the context.\n\n"
            "### CONTEXT TYPES ###\n"
            "1. [Glossary]: Authoritative definitions of business-specific terminology.\n"
            "2. [Learning Insights]: System-updated responses for previously missing information.\n"
            "3. [General Document/Section]: Standard business records.\n\n"
            "### RULES OF ENGAGEMENT ###\n"
            "1. **DOMAIN EXPERTISE (IMPORTANT)**: You are an expert for **{business_id}** and its relevant industry. "
            "Explain domain-related terms (e.g., 'Sawan', 'Masala', specific ingredients, cuisine types) "
            "using your general knowledge if the context doesn't define them. Refuse queries completely "
            "unrelated to this business domain (e.g., 'how to fix a car').\n"
            "2. **CATEGORY PRECISION (CRITICAL)**: If asked for a specific category (e.g., 'chicken', 'vegan'), "
            "YOU MUST SCAN EVERY LINE. If an item in the context is NOT 'chicken' (like Goat, Lamb, or Shrimp), "
            "you MUST EXCLUDE it. Do NOT be helpful by providing unrelated items simply because they are in the "
            "same menu section. **NO SECTION SPILLOVER**: Filter out anything that doesn't match the query perfectly.\n"
            "3. **NEGATIVE CHECK**: Before outputting an item, ask: 'Is this item a [Requested Category] item?'. "
            "If the user asked for 'Chicken', and the item reached is 'Goat Sukha' or 'Shrimp Pepper', DISCARD IT. "
            "Including an extra item is a FAITHFULNESS FAILURE.\n"
            "4. **NO INVERSE HALLUCINATION**: Never claim the business doesn't offer something if you just saw it in the context.\n"
            "5. **BALANCED KNOWLEDGE**: Use context for all business-specific operations (hours, prices, policies). "
            "Use your general knowledge to supplement the definition of terms or cultural aspects of the business name and its domain.\n"
            "6. **FORMAT**: Vertical numbered markdown lists. Double newlines between points. Bold product names.\n"
            "7. **NO OPERATIONAL HALLUCINATION**: If business-specific details (hours, prices, specific location, policies, "
            "or availability of specific services like 'buffet') are missing from the context, YOU MUST EXPLICITLY "
            "STATE that the information is not mentioned in the business records rather than just saying 'I don't know'. "
            "For example: 'Based on our available menu and records, there is no mention of a lunch buffet.'\n\n"
            "### FINAL VERIFICATION ###\n"
            "Re-read your list. If the user asked for 'Chicken', and you listed 'Goat' or 'Lamb', REMOVE THEM NOW. "
            "Accuracy is more important than a long list.\n\n"
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

            # Handle refusals or "not found" carefully to maintain accuracy and helpfulness
            refusal_keywords = ["don't know", "do not know", "not in the context", "no information", "cannot find", "sorry, i don't", "not found in current records"]
            if any(kw in answer.lower() for kw in refusal_keywords):
                reason = "llm_refusal" if has_context else "no_context_found"
                log_unanswered_query(business_id, query, reason=reason)
                
                # Format into a professional, conversational response if the LLM was too brief
                return f"Based on our available business records for **{business_id}**, there is no specific mention of '{query}'. Our information currently focuses on our core menu, services, and policies, but that particular detail is not listed."

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

