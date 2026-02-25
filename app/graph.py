from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END
from app.agents.supervisor import SupervisorAgent
from app.agents.operator import OperatorAgent
from app.agents.response_generator import ResponseGenerator
from app.agents.router import RouterAgent

# Global router instance to maintain state across graph executions
# In a distributed system, this would be a persistent database/cache.
agent_router = RouterAgent()

# Define the state object
class AgentState(TypedDict):
    user_id: str
    business_id: str
    query: str
    chat_history: List[dict]
    rewritten_query: str
    context: str
    sources: List[dict]
    answer: str

def rewrite_query_node(state: AgentState):
    """Rewrite the user query for better retrieval."""
    supervisor = SupervisorAgent()
    rewritten = supervisor.rewrite_query(state["query"], state["chat_history"])
    return {"rewritten_query": rewritten}

def retrieve_node(state: AgentState):
    """Retrieve documents using a stateful Operator assigned by the Router."""
    user_id = state.get("user_id", "default_user")
    query = state.get("rewritten_query") or state["query"]
    
    # The Router handles the "busy" logic and context handoff:
    operator = agent_router.get_or_create_operator(user_id, business_id=state["business_id"])
    print(f"[Graph] User {user_id} assigned to Operator: {operator.agent_id} (Status: {operator.status})")
    
    # The operator carries out the direct task
    result = operator.handle_task({"query": query, "business_id": state["business_id"]})
    
    return {
        "context": result.get("answer", ""),
        "sources": result.get("sources", [])
    }

def generate_node(state: AgentState):
    """Generate the final response."""
    rg = ResponseGenerator()
    answer = rg.generate(
        state["query"], 
        state["context"], 
        state["chat_history"],
        business_id=state["business_id"]
    )
    return {"answer": answer}

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("rewriter", rewrite_query_node)
    workflow.add_node("retriever", retrieve_node)
    workflow.add_node("generator", generate_node)
    
    workflow.set_entry_point("rewriter")
    workflow.add_edge("rewriter", "retriever")
    workflow.add_edge("retriever", "generator")
    workflow.add_edge("generator", END)
    
    return workflow.compile()

app_graph = create_graph()
