# In api/app/agents.py

import os
import json
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import Document

from .tools import web_search, AVAILABLE_TOOLS
from .prompts import (
    ORCHESTRATOR_PROMPT,
    RESEARCHER_PROMPT,
    ANALYST_PROMPT,
    CLEANER_PROMPT,
    FINAL_REPORT_PROMPT,
    JUDGE_PROMPT  # Import the new Judge prompt
)
from .types import InvestigationState

# ==============================================================================
# === 1. CENTRALIZED LLM INITIALIZATION ========================================
# ==============================================================================
# All models are defined here, with temperature=0 for factuality.

# Claude Sonnet for fast orchestration
claude_sonnet = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0, max_tokens=2048)

# GPT-4o for nuanced analysis
gpt_4o = ChatOpenAI(model="gpt-4o-2024-08-06", temperature=0, max_tokens=2048)

# Gemini 1.5 Pro for large context cleaning and synthesis
try:
    gemini_1_5 = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest",
        temperature=0,
        max_output_tokens=8192
    )
    print("INFO: Gemini model initialized successfully")
except Exception as e:
    print(f"WARNING: Failed to initialize Gemini. Falling back to GPT-4o. Error: {e}")
    gemini_1_5 = ChatOpenAI(model="gpt-4o-2024-08-06", temperature=0, max_tokens=4096)

# Claude Opus as the high-accuracy Judge
claude_opus = ChatAnthropic(model="claude-opus-4-20250514", temperature=0, max_tokens=4096)


# ==============================================================================
# === 2. AGENT NODE FUNCTIONS ==================================================
# ==============================================================================

def orchestrator(state: InvestigationState) -> InvestigationState:
    """
    The main orchestrator wrapper. It calls the query analyzer on the first step
    and then calls the tool selection orchestrator on every step.
    """
    if state.get('retrieval_count', 0) == 0:
        # On the very first run, analyze the query to find entities.
        state = query_analysis_node(state)
    
    # Now, proceed with the regular orchestration step.
    state = orchestrator_node(state)
    return state

# --- Investigation Loop Nodes ---

def query_analysis_node(state: InvestigationState) -> InvestigationState:
    """Parses the initial query to identify entities."""
    state['log'].append("INFO: Parsing query to identify entities...")
    prompt = PromptTemplate(template=RESEARCHER_PROMPT, input_variables=["query"])
    chain = prompt | claude_sonnet | JsonOutputParser()
    
    try:
        result = chain.invoke({"query": state['query']})
        state['entities'] = result.get('entities', [state['query']])
        state['log'].append(f"SUCCESS: Identified entities: {state['entities']}")
    except Exception as e:
        state['log'].append(f"ERROR: Failed to parse query. Using original query as entity. Error: {e}")
        state['entities'] = [state['query']]
    return state


def orchestrator_node(state: InvestigationState) -> InvestigationState:
    """Decides the next tool to use based on the current state."""
    state['log'].append("INFO: Orchestrator deciding next step...")
    state['retrieval_count'] = state.get('retrieval_count', 0) + 1
    state['log'].append(f"INFO: --- Investigation Step #{state['retrieval_count']} ---")

    # The first query should come from the initial prompt, not a follow-up
    if not state.get('follow_up_queries'):
        queries_for_prompt = [state['query']]
    else:
        queries_for_prompt = state.get('follow_up_queries')

    prompt = PromptTemplate(
        template=ORCHESTRATOR_PROMPT,
        input_variables=["query", "analysis", "follow_up_queries"],
        partial_variables={"tool_names": ", ".join(AVAILABLE_TOOLS.keys())}
    )
    chain = prompt | claude_sonnet | JsonOutputParser()
    
    try:
        result = chain.invoke({
            "query": state['query'],
            "analysis": state['analysis'],
            "follow_up_queries": queries_for_prompt
        })
        
        tool_name = result['tool_name']
        query = result['query']
        
        if tool_name not in AVAILABLE_TOOLS:
            raise ValueError(f"Invalid tool '{tool_name}' selected.")

        state['log'].append(f"INFO: Orchestrator chose tool '{tool_name}' with query '{query}'")
        
        tool_function = AVAILABLE_TOOLS[tool_name]
        retrieved_info = tool_function(query)
        state['retrieved_data'].extend(retrieved_info)
        state['log'].append(f"SUCCESS: Retrieved {len(retrieved_info)} items using {tool_name}.")
            
    except Exception as e:
        state['log'].append(f"ERROR: Orchestrator failed: {e}. Falling back to web search.")
        fallback_query = state['query']
        fallback_info = web_search(fallback_query)
        state['retrieved_data'].extend(fallback_info)
        state['log'].append(f"INFO: Fallback web_search retrieved {len(fallback_info)} items.")
    
    return state


def pivot_agent_node(state: InvestigationState) -> InvestigationState:
    """Analyzes retrieved data and suggests next steps."""
    state['log'].append("INFO: Pivot agent analyzing new data...")
    
    # Format the most recent data for the analyst
    # This logic needs to be careful not to re-process old data.
    # A simple way is to pass only the newest items. Let's assume the calling
    # logic handles what's "new", but here we will just format all data.
    context_str = "\n---\n".join([item['content'] for item in state['retrieved_data'] if item.get('content')])

    prompt = PromptTemplate(
        template=ANALYST_PROMPT, 
        input_variables=["query", "context", "analysis"]
    )
    chain = prompt | gpt_4o | JsonOutputParser()
    
    try:
        result = chain.invoke({
            "query": state['query'],
            "context": context_str,
            "analysis": state['analysis']
        })
        
        state['analysis'] = result.get('analysis', state['analysis'])
        state['follow_up_queries'] = result.get('follow_up_queries', [])
            
        state['log'].append("SUCCESS: Pivot agent updated analysis and follow-up queries.")
    except Exception as e:
        state['log'].append(f"ERROR: Pivot agent failed: {e}")
        state['follow_up_queries'] = []
        
    return state


# --- Reporting & Verification Nodes (Moved from graph.py) ---

def cleaner_node(state: InvestigationState) -> InvestigationState:
    """Cleans data and resolves entities into distinct profiles using Gemini 1.5 Pro."""
    state['log'].append("INFO: Skeptical cleaner resolving entities...")
    
    try:
        context_str = "\n---\n".join([item['content'] for item in state['retrieved_data'] if item.get('content')])
        if not context_str:
            raise ValueError("No content to clean.")

        prompt = ChatPromptTemplate.from_template(CLEANER_PROMPT)
        chain = prompt | gemini_1_5 | JsonOutputParser()
        
        result = chain.invoke({"query": state['query'], "context": context_str})
        
        state['cleaned_data'] = result
        state['log'].append("SUCCESS: Data cleaned and entities resolved.")
        
    except Exception as e:
        error_msg = f"ERROR: Failed to clean data: {e}"
        state['log'].append(error_msg)
        state['cleaned_data'] = {"profiles": [{"confidence_score": 0.0, "profile_name": "Error during cleaning", "summary": error_msg, "supporting_facts": []}]}
    
    return state


def report_writer_node(state: InvestigationState) -> InvestigationState:
    """Generates the final report from structured profiles using Gemini 1.5 Pro."""
    state['log'].append("INFO: Generating draft report...")
    
    try:
        if not state.get('cleaned_data') or not state.get('cleaned_data').get('profiles'):
             raise ValueError("No structured profiles for report generation")

        prompt = ChatPromptTemplate.from_template(FINAL_REPORT_PROMPT)
        chain = prompt | gemini_1_5 | StrOutputParser()
        
        report_str = chain.invoke({
            "query": state['query'],
            "cleaned_data": json.dumps(state['cleaned_data'], indent=2)
        })
        
        state['final_report'] = report_str
        state['log'].append("SUCCESS: Draft report generated.")
        
    except Exception as e:
        error_msg = f"ERROR: Failed to generate report: {e}"
        state['log'].append(error_msg)
        state['final_report'] = f"REPORT GENERATION FAILED: {error_msg}"
    
    return state


def judge_agent_node(state: InvestigationState) -> InvestigationState:
    """Final quality check on the report's accuracy using Claude Opus."""
    state['log'].append("INFO: Judge agent (Claude Opus) reviewing report for accuracy...")

    prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT)
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
            state['final_report'] = f"REPORT FAILED QUALITY CHECK\n\nREASON: {reason}\n\n---ORIGINAL DRAFT---\n{state['final_report']}"
            
    except Exception as e:
        error_message = f"ERROR: Judge agent failed: {e}. Report is unverified."
        state['log'].append(error_message)
        state['final_report'] = f"{error_message}\n\n---UNVERIFIED REPORT---\n{state['final_report']}"
        
    return state