import logging
from typing import Dict, Any, List
from backend.agents.state import AgentState
from backend.rag.faiss_store import build_vector_store, retrieve_relevant_evidence
from backend.services.db_service import get_sources_dict

logger = logging.getLogger(__name__)

async def retrieve_evidence_node(state: AgentState) -> Dict[str, Any]:
    """
    RAG-based Evidence Retrieval Agent.
    Creates a temporary FAISS index of search results,
    queries it for each claim, and scores/ranks sources.
    """
    logger.info("Starting Evidence Retrieval Agent...")
    
    claims = state.get("claims", [])
    search_results = state.get("search_results", [])
    errors = state.get("errors", [])
    
    if not claims:
        logger.warning("No claims to retrieve evidence for.")
        return {"evidences": {}}
        
    if not search_results:
        logger.warning("No search results available for RAG.")
        # Prepopulate empty evidence dict per claim
        return {"evidences": {c["id"]: [] for c in claims}}
        
    # Build the FAISS vector store
    vector_store = build_vector_store(search_results)
    
    # Get known source profiles for credibility lookup
    try:
        sources_map = get_sources_dict()
    except Exception as e:
        logger.error(f"Error loading sources map: {e}")
        sources_map = {}
        
    evidences = {}
    
    for claim in claims:
        claim_id = claim["id"]
        claim_text = claim["claim_text"]
        
        # Retrieve raw evidence from FAISS
        raw_evidence = retrieve_relevant_evidence(vector_store, claim_text, top_k=4)
        
        # Enhance each piece of evidence with source credibility scoring
        enhanced_evidence = []
        for ev in raw_evidence:
            domain = ev.get("source_domain", "")
            
            # Lookup domain credibility. Default to 0.5 for unknown sources.
            source_profile = sources_map.get(domain, {})
            credibility = source_profile.get("credibility_score", 0.5)
            bias = source_profile.get("bias_rating", "Unknown")
            
            ev["source_credibility"] = credibility
            ev["source_bias"] = bias
            
            # Weighted score combining FAISS semantic similarity (relevance) and source credibility
            # Relevance score is between 0 and 1 (usually cosine similarity)
            relevance = ev.get("relevance_score", 0.5)
            # Ensure it is bounded
            relevance = max(0.0, min(1.0, relevance))
            
            # Calculate final confidence score for this specific piece of evidence
            ev["confidence_score"] = round((relevance * 0.4) + (credibility * 0.6), 3)
            
            enhanced_evidence.append(ev)
            
        # Sort evidence by confidence score descending
        enhanced_evidence.sort(key=lambda x: x["confidence_score"], reverse=True)
        evidences[claim_id] = enhanced_evidence
        
    logger.info("Evidence Retrieval completed successfully.")
    return {"evidences": evidences}
