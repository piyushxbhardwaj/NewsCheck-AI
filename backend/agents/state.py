from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    """
    Represents the state of the fact-checking agent workflow.
    """
    # Inputs
    url: Optional[str]
    raw_text: Optional[str]
    
    # Article Extraction results
    article_title: Optional[str]
    article_content: Optional[str]
    article_domain: Optional[str]
    summary: Optional[str]
    
    # Claims Extraction results
    # Each claim: {"id": str, "claim_text": str, "category": str}
    claims: List[Dict[str, Any]] 
    
    # Search & Evidence Retrieval
    # List of raw search result dicts
    search_results: List[Dict[str, Any]] 
    # Mapped evidence: {claim_id: [{"snippet": str, "source_url": str, "source_title": str, "source_domain": str, "relevance_score": float}]}
    evidences: Dict[str, List[Dict[str, Any]]] 
    
    # Fact Verification results
    # Mapped verdicts: {claim_id: {"verdict": str, "explanation": str}}
    verdicts: Dict[str, Dict[str, Any]]
    
    # Bias and Tone Analysis results
    bias_rating: Optional[str]        # 'Left', 'Center', 'Right', etc.
    tone_rating: Optional[str]        # 'Neutral', 'Sensational', 'Fear-inducing'
    bias_explanation: Optional[str]
    
    # Final Output Report
    final_verdict: Optional[str]      # 'TRUE', 'LIKELY TRUE', 'MISLEADING', 'UNVERIFIED', 'LIKELY FALSE', 'FALSE'
    credibility_score: Optional[int]  # 0 to 100
    final_report: Optional[str]       # Markdown formatted full report
    
    # Flow Control flags
    deep_search_done: bool            # Flag to indicate if deep search was executed
    loop_count: int                   # Prevent infinite loops in case of repeated routing
    errors: List[str]                 # Track errors during processing
