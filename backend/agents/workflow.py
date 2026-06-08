import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from backend.agents.state import AgentState
from backend.agents.article_extractor import extract_article_node
from backend.agents.claim_extractor import extract_claims_node
from backend.agents.search_agent import search_agent_node
from backend.agents.evidence_retriever import retrieve_evidence_node
from backend.agents.fact_verifier import verify_claims_node
from backend.agents.bias_detector import detect_bias_node
from backend.agents.report_generator import generate_report_node

logger = logging.getLogger(__name__)

def prepare_deep_search_node(state: AgentState) -> Dict[str, Any]:
    """
    Intermediate node that increments loop count and enables deep search mode
    before routing back to the Search Agent.
    """
    logger.info("Routing back for Deep Search. Incrementing loop count.")
    return {
        "deep_search_done": True,
        "loop_count": state.get("loop_count", 0) + 1
    }

def route_after_verification(state: AgentState) -> Literal["prepare_deep_search", "detect_bias"]:
    """
    Conditional router that checks if any claims are unverified due to lack of 
    evidence, and loops back if we haven't performed a deep search yet.
    """
    claims = state.get("claims", [])
    verdicts = state.get("verdicts", {})
    evidences = state.get("evidences", {})
    deep_search_done = state.get("deep_search_done", False)
    loop_count = state.get("loop_count", 0)
    
    if not claims:
        return "detect_bias"
        
    needs_more_evidence = False
    for claim in claims:
        claim_id = claim["id"]
        v_info = verdicts.get(claim_id, {})
        claim_ev = evidences.get(claim_id, [])
        
        # If it was unverified due to lack of evidence, try again
        if v_info.get("verdict") == "UNVERIFIED" or len(claim_ev) == 0:
            needs_more_evidence = True
            break
            
    if needs_more_evidence and not deep_search_done and loop_count < 2:
        logger.info("Incomplete evidence. Initiating deep search routing...")
        return "prepare_deep_search"
        
    logger.info("Sufficient evidence gathered or max loops reached. Routing to bias detection.")
    return "detect_bias"

def create_workflow():
    """
    Assembles and compiles the LangGraph StateGraph.
    """
    # Initialize the graph with our State schema
    workflow = StateGraph(AgentState)
    
    # Register all nodes
    workflow.add_node("extract_article", extract_article_node)
    workflow.add_node("extract_claims", extract_claims_node)
    workflow.add_node("search", search_agent_node)
    workflow.add_node("retrieve_evidence", retrieve_evidence_node)
    workflow.add_node("verify_claims", verify_claims_node)
    workflow.add_node("prepare_deep_search", prepare_deep_search_node)
    workflow.add_node("detect_bias", detect_bias_node)
    workflow.add_node("generate_report", generate_report_node)
    
    # Establish execution flow
    workflow.set_entry_point("extract_article")
    
    workflow.add_edge("extract_article", "extract_claims")
    workflow.add_edge("extract_claims", "search")
    workflow.add_edge("search", "retrieve_evidence")
    workflow.add_edge("retrieve_evidence", "verify_claims")
    
    # Add conditional routing after verification
    workflow.add_conditional_edges(
        "verify_claims",
        route_after_verification,
        {
            "prepare_deep_search": "prepare_deep_search",
            "detect_bias": "detect_bias"
        }
    )
    
    # Route back to search from deep search preparation
    workflow.add_edge("prepare_deep_search", "search")
    
    # Complete final stages
    workflow.add_edge("detect_bias", "generate_report")
    workflow.add_edge("generate_report", END)
    
    # Compile the graph
    app = workflow.compile()
    return app

# Shared compiled app instance
compiled_workflow = create_workflow()
