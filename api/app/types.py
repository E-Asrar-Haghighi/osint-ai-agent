from typing import TypedDict, List, Optional, Dict, Any

class InvestigationState(TypedDict, total=False):
    """
    Represents the state of our investigation at any given time.
    """
    query: str
    entities: List[str]
    plan: Optional[str]
    retrieved_data: List[Dict[str, str]]  # List of {source: str, content: str}
    log: List[str]
    analysis: str
    follow_up_queries: List[str]
    retrieval_count: int  # Tracks number of retrieval cycles
    cleaned_data: Dict[str, Any]    # Cleaned and structured data before final report
    final_report: str 