# In api/app/tools.py

import os
from tavily import TavilyClient
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables from .env file
load_dotenv()

# --- REAL TOOL INITIALIZATION ---
try:
    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    print("INFO: Tavily client initialized successfully")
except KeyError:
    print("WARNING: TAVILY_API_KEY not found. Web search will use a mock fallback.")
    tavily = None

def web_search(query: str) -> List[Dict[str, str]]:
    """Performs a real web search using Tavily and returns the results."""
    print(f"INFO: Performing web search for: {query}")
    try:
        if tavily is not None:
            # Use the real Tavily client if available
            results = tavily.search(query=query, search_depth="advanced", max_results=5)
            if "results" not in results:
                return []
            return [{"source": "web_search", "content": r["content"]} for r in results["results"]]
        else:
            # Provide a mock response ONLY if Tavily is not configured
            print("INFO: Using MOCK web_search.")
            return [
                {"source": "web_search_mock", "content": f"A news article from Example.com mentions {query} in the context of a recent tech conference."},
                {"source": "web_search_mock", "content": f"A blog post discusses a project attributed to {query}."}
            ]
    except Exception as e:
        print(f"ERROR: Web search failed: {e}")
        return []

# --- NEUTRAL, DYNAMIC MOCKED TOOLS ---
# These functions now generate plausible, generic data that incorporates the entity_name.
# This prevents the hardcoded data contamination.

def social_media_search(entity_name: str) -> List[Dict[str, str]]:
    """MOCK: Searches social media for an entity."""
    print(f"MOCK: Searching social media for {entity_name}")
    # Return plausible but generic findings.
    return [
        {"source": "social_media_mock", "content": f"A public LinkedIn profile for an individual named {entity_name} was found. The profile lists a position as 'Software Engineer' at 'TechCorp'."},
        {"source": "social_media_mock", "content": f"A Twitter/X account with the handle @{entity_name.replace(' ', '')}_dev was found. It frequently posts about software development."}
    ]

def company_database_search(entity_name: str) -> List[Dict[str, str]]:
    """MOCK: Searches company registration database."""
    print(f"MOCK: Searching company database for {entity_name}")
    return [
        {"source": "company_db_mock", "content": f"No public records found listing {entity_name} as a director or officer in major company registries."}
    ]

def academic_search(entity_name: str) -> List[Dict[str, str]]:
    """MOCK: Searches academic publications and records."""
    print(f"MOCK: Searching academic papers for {entity_name}")
    return [
        {"source": "academic_mock", "content": f"Found a publication on arXiv authored by someone named {entity_name}, titled 'A Study on Abstract Systems'."},
        {"source": "academic_mock", "content": f"The University of Example's website lists a student named {entity_name} in their computer science program alumni directory."}
    ]

# --- TOOL REGISTRY ---
# List of all available tools for the orchestrator
AVAILABLE_TOOLS = {
    "web_search": web_search,
    "social_media_search": social_media_search,
    "company_database_search": company_database_search,
    "academic_search": academic_search,
}