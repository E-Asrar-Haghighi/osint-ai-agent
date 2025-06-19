# In api/app/graph.py

import json
from typing import List, Literal
from langgraph.graph import StateGraph, END
from . import agents
from .types import InvestigationState

# --- Graph Definition ---
def should_continue(state: InvestigationState) -> Literal["continue", "end"]:
    """Determines whether the investigation should continue or end."""
    retrieval_count = state.get("retrieval_count", 0)
    follow_up_queries = state.get("follow_up_queries", [])
    retrieved_data = state.get("retrieved_data", [])
    
    if retrieval_count >= 15:
        print("[DEBUG] Ending investigation: hit hard limit of 15 retrievals")
        return "end"
        
    valid_data = [item for item in retrieved_data if isinstance(item, dict) and item.get('content')]
    
    if len(valid_data) >= 8:
        print(f"[DEBUG] Ending investigation: sufficient quality data collected ({len(valid_data)} valid items)")
        return "end"
        
    if not follow_up_queries:
        print(f"[DEBUG] Ending investigation: no more queries to pursue.")
        return "end"
        
    print(f"[DEBUG] Continuing investigation...")
    return "continue"

# Create the graph
workflow = StateGraph(InvestigationState)

# Add the nodes by referencing the functions in agents.py
workflow.add_node("orchestrator", agents.orchestrator)  # Uses the new wrapper
workflow.add_node("analyst", agents.pivot_agent_node)
workflow.add_node("cleaner", agents.cleaner_node)
workflow.add_node("writer", agents.report_writer_node)
workflow.add_node("judge", agents.judge_agent_node)

# Build the graph
workflow.set_entry_point("orchestrator")
workflow.add_edge("orchestrator", "analyst")
workflow.add_conditional_edges(
    "analyst",
    should_continue,
    {"continue": "orchestrator", "end": "cleaner"}
)
workflow.add_edge("cleaner", "writer")
workflow.add_edge("writer", "judge")
workflow.add_edge("judge", END)

# Compile the graph
app = workflow.compile()