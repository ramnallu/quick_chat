from app.agents.operator import OperatorAgent

class RouterAgent:
    """Intelligent Router Agent.
    
    Manages a pool of OperatorAgents and maintains a persistent cache of 
    business context to speed up operator onboarding.
    """

    def __init__(self):
        # registry: agent_id -> operator_instance
        self.registry = {}
        # user_assignments: user_id -> agent_id
        self.user_assignments = {}
        # business_context_cache: business_id -> context_string
        self.business_context_cache = {}

    def set_business_context(self, business_id: str, context: str):
        """Pre-populate the cache with essential business information."""
        self.business_context_cache[business_id] = context
        print(f"[Router] Cached context for: {business_id}")

    def get_or_create_operator(self, user_id: str, business_id: str = None) -> OperatorAgent:
        """Find the operator assigned to this user, or assign a new idle one."""
        
        # 1. Check if user already has an assigned operator
        if user_id in self.user_assignments:
            agent_id = self.user_assignments[user_id]
            operator = self.registry[agent_id]
        else:
            # 2. Find an idle operator
            operator = None
            for agent_id, op in self.registry.items():
                if op.status == "idle":
                    op.status = "busy"
                    op.current_user = user_id
                    self.user_assignments[user_id] = agent_id
                    operator = op
                    break

            # 3. No idle operators found, create a NEW operator instance
            if not operator:
                new_id = f"operator_{len(self.registry) + 1}"
                operator = OperatorAgent(new_id)
                operator.status = "busy"
                operator.current_user = user_id
                self.registry[new_id] = operator
                self.user_assignments[user_id] = new_id
                print(f"[Router] Created new operator: {new_id} for user: {user_id}")

        # 4. "Onboard" the operator with cached business context if available
        if business_id and business_id in self.business_context_cache:
            operator.onboarding_context = self.business_context_cache[business_id]
            print(f"[Router] Handed over cached context of {business_id} to {operator.agent_id}")
        
        return operator

    def release_operator(self, user_id: str):
        """Mark an operator as idle once the conversation/task is complete."""
        if user_id in self.user_assignments:
            agent_id = self.user_assignments[user_id]
            operator = self.registry[agent_id]
            operator.status = "idle"
            operator.current_user = None
            operator.onboarding_context = None # Clear context on release
            del self.user_assignments[user_id]
            print(f"[Router] Released operator: {agent_id} from user: {user_id}")
