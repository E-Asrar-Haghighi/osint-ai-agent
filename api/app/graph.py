# In api/app/graph.py

import json
from typing import List, Literal
from langgraph.graph import StateGraph, END
from . import agents
from .types import InvestigationState
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from .prompts import CLEANER_PROMPT, FINAL_REPORT_PROMPT, JUDGE_PROMPT
from .agents import gemini_1_5, claude_opus  # Import the LLMs we need

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

def cleaner_node(state: InvestigationState) -> InvestigationState:
    """Cleans data and resolves entities into distinct profiles using Gemini 1.5 Pro."""
    state['log'].append("INFO: Skeptical cleaner resolving entities...")
    
    try:
        context_str = "\n---\n".join([item['content'] for item in state['retrieved_data'] if item.get('content')])
        if not context_str:
            raise ValueError("No content to clean.")

        prompt = PromptTemplate(template=CLEANER_PROMPT, input_variables=["query", "context"])
        chain = prompt | gemini_1_5 | JsonOutputParser()
        
        result = chain.invoke({"query": state['query'], "context": context_str})
        
        state['cleaned_data'] = result
        state['log'].append("SUCCESS: Data cleaned and entities resolved.")
        print("[DEBUG] Data cleaning completed successfully.")
        
    except Exception as e:
        error_msg = f"ERROR: Failed to clean data: {e}"
        state['log'].append(error_msg)
        print(f"[ERROR] {error_msg}")
        state['cleaned_data'] = {"profiles": [{"confidence_score": 0.0, "profile_name": "Error during cleaning", "summary": error_msg, "supporting_facts": []}]}
    
    return state

def report_writer_node(state: InvestigationState) -> InvestigationState:
    """Generates the final report from structured profiles using Gemini 1.5 Pro."""
    state['log'].append("INFO: Generating draft report...")
    
    try:
        if not state.get('cleaned_data') or not state.get('cleaned_data').get('profiles'):
             raise ValueError("No structured profiles available for report generation")

        prompt = PromptTemplate(template=FINAL_REPORT_PROMPT, input_variables=["query", "cleaned_data"])
        # The spec requires Gemini 1.5 Pro for synthesis
        chain = prompt | gemini_1_5 | StrOutputParser()
        
        report_str = chain.invoke({
            "query": state['query'],
            "cleaned_data": json.dumps(state['cleaned_data'], indent=2)
        })
        
        state['final_report'] = report_str
        state['log'].append("SUCCESS: Draft report generated.")
        print("[DEBUG] Draft report generation completed successfully.")
        
    except Exception as e:
        error_msg = f"ERROR: Failed to generate report: {e}"
        state['log'].append(error_msg)
        print(f"[ERROR] {error_msg}")
        state['final_report'] = f"REPORT GENERATION FAILED: {error_msg}"
    
    return state

def judge_agent_node(state: InvestigationState) -> InvestigationState:
    """Final quality check by the 'Judge' LLM (Claude Opus)."""
    state['log'].append("INFO: Judge agent (Claude Opus) reviewing report for accuracy...")

    prompt = PromptTemplate(template=JUDGE_PROMPT, input_variables=["cleaned_data", "final_report"])
    # The spec requires Claude Opus as the Judge
    judge_chain = prompt | claude_opus | JsonOutputParser()

    try:
        result = judge_chain.invoke({
            "cleaned_data": json.dumps(state['cleaned_data'], indent=2),
            "final_report": state['final_report']
        })

        if result.get("is_accurate") is True:
            state['log'].append("SUCCESS: Judge approves the report quality.")
        else:
            reason = result.get('reasoning', 'No reason provided.')
            state['log'].append(f"WARNING: Judge REJECTED report. Reason: {reason}")
            # Overwrite the report with the failure message for the user to see
            state['final_report'] = f"REPORT FAILED QUALITY CHECK\n\nREASON: {reason}\n\n---ORIGINAL DRAFT---\n{state['final_report']}"
            
    except Exception as e:
        error_message = f"ERROR: Judge agent failed: {e}. Report is unverified."
        state['log'].append(error_message)
        state['final_report'] = f"{error_message}\n\n---UNVERIFIED REPORT---\n{state['final_report']}"
        
    return state

# Create the graph
workflow = StateGraph(InvestigationState)

# Add the nodes with correct function names from agents.py
workflow.add_node("orchestrator", agents.orchestrator_node)
workflow.add_node("analyst", agents.pivot_agent_node)
workflow.add_node("cleaner", agents.cleaner_node)
workflow.add_node("writer", agents.report_writer_node)
workflow.add_node("judge", agents.judge_agent_node)

# Build the graph
workflow.set_entry_point("orchestrator")
workflow.add_edge("orchestrator", "analyst")

# Add conditional edges for the analyst
workflow.add_conditional_edges(
    "analyst",
    should_continue,
    {
        "continue": "orchestrator",
        "end": "cleaner"  # When investigation ends, start the reporting process
    }
)

# Set the reporting and verification flow
workflow.add_edge("cleaner", "writer")
workflow.add_edge("writer", "judge")  # Writer's output goes to the Judge
workflow.add_edge("judge", END)       # After the Judge runs, the graph ends.

# Compile the graph without persistence, as per product manager's guidance
app = workflow.compile()