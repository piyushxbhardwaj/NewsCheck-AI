import asyncio
import logging
from typing import Dict, Any, List
from backend.agents.state import AgentState
from backend.services.search_service import search_query, search_fact_check_sites

logger = logging.getLogger(__name__)

async def search_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Search agent that gathers evidence for each claim.
    Executes in parallel using asyncio.gather.
    """
    logger.info("Starting Search Agent...")
    
    claims = state.get("claims", [])
    errors = state.get("errors", [])
    is_deep_search = state.get("deep_search_done", False)
    existing_results = state.get("search_results", [])
    
    if not claims:
        logger.warning("No claims to search for.")
        return {"search_results": []}
        
    tasks = []
    
    # Define search worker
    async def search_for_claim(claim: Dict[str, Any]) -> List[Dict[str, Any]]:
        claim_text = claim["claim_text"]
        claim_results = []
        
        try:
            if not is_deep_search:
                # 1. Fact-check lookup first
                logger.info(f"Performing fact-check lookup for: '{claim_text}'")
                fc_results = await search_fact_check_sites(claim_text, max_results=3)
                claim_results.extend(fc_results)
                
                # 2. General web search
                logger.info(f"Performing general web search for: '{claim_text}'")
                gen_results = await search_query(claim_text, max_results=4)
                claim_results.extend(gen_results)
            else:
                # Deep search: expand query, target different angles
                # Generate alternative queries like "claim_text hoax" or "claim_text fact check"
                logger.info(f"Performing DEEP search for: '{claim_text}'")
                deep_queries = [
                    f"{claim_text} true or false",
                    f"{claim_text} fact check factcheck",
                    f"is it true that {claim_text}"
                ]
                # Run them
                for q in deep_queries:
                    res = await search_query(q, max_results=3)
                    claim_results.extend(res)
                    
        except Exception as e:
            logger.error(f"Error searching for claim {claim.get('id')}: {e}")
            errors.append(f"Search failed for claim: {claim_text}. Error: {str(e)}")
            
        return claim_results

    # Run searches for all claims in parallel
    results_lists = await asyncio.gather(*[search_for_claim(c) for c in claims])
    
    # Flatten and deduplicate by URL
    new_results = []
    seen_urls = {res["url"] for res in existing_results if res.get("url")}
    
    for r_list in results_lists:
        for r in r_list:
            url = r.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                new_results.append(r)
                
    combined_results = existing_results + new_results
    logger.info(f"Search Agent completed. Found {len(new_results)} new results (Total: {len(combined_results)}).")
    
    return {
        "search_results": combined_results,
        "errors": errors
    }
