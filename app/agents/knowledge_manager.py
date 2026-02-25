import os
import json
from typing import List, Dict
from langchain_ollama import OllamaLLM
from langchain_groq import ChatGroq

class KnowledgeManagerAgent:
    """Agent responsible for maintaining and expanding the business knowledge base."""

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

    def generate_glossary(self, business_id: str, combined_text: str) -> List[Dict]:
        """
        Analyzes business documents to identify and define specialized terms.
        Returns a list of section objects ready for RAG ingestion.
        """
        print(f"[KnowledgeManager] Generating Auto-Glossary for {business_id}...")
        
        prompt = (
            "### INSTRUCTION ###\n"
            f"You are a Knowledge Acquisition Expert for the business '{business_id}'.\n"
            "Review the following text from the business documents. Identify regional specialties, "
            "technical jargon, or unique terminology that a customer might ask about (e.g., 'What is Andhra?', 'What is masala?').\n\n"
            "### TEXT TO ANALYZE ###\n"
            f"{combined_text[:6000]}\n\n" # Truncate to avoid context window issues
            "### OUTPUT FORMAT ###\n"
            "Produce a valid JSON list of objects. Each object must have 'term' and 'definition'.\n"
            "Example: [{\"term\": \"Masala\", \"definition\": \"A blend of ground spices used in Indian cooking.\"}]\n"
            "ONLY return the JSON list. No other text."
        )

        try:
            response = self.llm.invoke(prompt)
            # Basic cleanup if LLM includes backticks
            content = response.content if hasattr(response, "content") else str(response)
            clean_json = content.strip().replace("```json", "").replace("```", "").strip()
            
            glossary_data = json.loads(clean_json)
            
            # Convert to RAG sections
            sections = []
            for item in glossary_data:
                term = item.get("term", "")
                definition = item.get("definition", "")
                if term and definition:
                    sections.append({
                        "id": f"glossary__{term.lower().replace(' ', '_')}",
                        "text": f"Glossary Entry for {business_id}: **{term}** - {definition}",
                        "metadata": {
                            "business_id": business_id,
                            "section": "Glossary",
                            "source": "Auto-Glossary Agent"
                        }
                    })
            return sections
        except Exception as e:
            print(f"[KnowledgeManager] Glossary generation failed: {e}")
            return []

    def teach_from_unanswered(self, business_id: str, unanswered_queries: List[Dict]) -> List[Dict]:
        """
        Analyzes failed queries to generate new RAG knowledge (FAQs).
        """
        if not unanswered_queries:
            return []

        print(f"[KnowledgeManager] Teacher-Agent analyzing {len(unanswered_queries)} queries for {business_id}...")
        
        queries_text = "\n".join([f"- {q['query']}" for q in unanswered_queries])
        
        prompt = (
            "### INSTRUCTION ###\n"
            f"You are an AI Teacher for the business '{business_id}'.\n"
            "The following queries were recently asked by customers but the system could not answer them "
            "because the information was missing or unclear in the documents.\n\n"
            "### FAILED QUERIES ###\n"
            f"{queries_text}\n\n"
            "### TASK ###\n"
            "Based on your general knowledge and the context of this business, generate clear, helpful FAQ-style "
            "answers. If you are unsure, provide a professional generic placeholder but try to be as specific "
            "to the business domain as possible.\n\n"
            "### OUTPUT FORMAT ###\n"
            "Produce a valid JSON list of objects. Each object must have 'question' and 'suggested_answer'.\n"
            "ONLY return the JSON list. No other text."
        )

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            clean_json = content.strip().replace("```json", "").replace("```", "").strip()
            
            faq_data = json.loads(clean_json)
            
            sections = []
            for item in faq_data:
                q = item.get("question", "")
                a = item.get("suggested_answer", "")
                if q and a:
                    sections.append({
                        "id": f"learning__{hash(q)}",
                        "text": f"Learning Insight (FAQ) for {business_id}:\nQuestion: {q}\nAnswer: {a}",
                        "metadata": {
                            "business_id": business_id,
                            "section": "Learning Insights",
                            "source": "Teacher Agent"
                        }
                    })
            return sections
        except Exception as e:
            print(f"[KnowledgeManager] Teaching failed: {e}")
            return []
