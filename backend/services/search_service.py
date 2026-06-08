import urllib.parse
from typing import List, Dict, Any, Optional
import logging
from duckduckgo_search import DDGS
import httpx

from backend.config import settings
from backend.services.cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)

# List of trusted fact-checking domains
FACT_CHECK_DOMAINS = [
    "snopes.com",
    "factcheck.org",
    "politifact.com",
    "reuters.com/fact-check",
    "apnews.com/hub/ap-fact-check",
    "fullfact.org"
]

async def _search_tavily(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Helper to query the Tavily Search API."""
    if not settings.tavily_api_key:
        return []
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "max_results": max_results
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                for result in data.get("results", []):
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("content", ""),
                        "domain": urllib.parse.urlparse(result.get("url", "")).netloc.replace("www.", "")
                    })
                return results
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
    return []

async def _search_ddg(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Helper to query DuckDuckGo Search (no API key required)."""
    try:
        # DDG library can block on high-frequency async, so we do it carefully
        # It's better to run this inside a thread pool or run it synchronously
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
        formatted_results = []
        for r in results:
            url = r.get("href", "")
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
            formatted_results.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("body", ""),
                "domain": domain
            })
        return formatted_results
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

async def search_query(query: str, max_results: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Executes a web search, first checking local cache. Fallback structure:
    Tavily API (if configured) -> DuckDuckGo Search.
    """
    cache_key = f"search:{query}:{max_results}"
    if use_cache:
        cached = get_cached(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for search query: '{query}'")
            return cached
            
    logger.info(f"Executing live search for: '{query}'")
    results = []
    
    # 1. Try Tavily
    if settings.tavily_api_key:
        results = await _search_tavily(query, max_results)
        
    # 2. Try DuckDuckGo
    if not results:
        results = await _search_tavily(query, max_results) # Double check or fall back
        results = await _search_ddg(query, max_results)
        
    if use_cache and results:
        set_cached(cache_key, results)
        
    return results

async def search_fact_check_sites(claim: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Search specifically on known fact-check sites (Snopes, FactCheck, Politifact)
    using targeted site syntax (e.g. site:snopes.com OR site:factcheck.org "claim")
    """
    # Create structured search queries
    # To prevent query truncation or parsing issues, we query a couple of sites at a time or in general
    queries = [
        f"site:snopes.com {claim}",
        f"site:factcheck.org {claim}",
        f"site:politifact.com {claim}"
    ]
    
    combined_results = []
    # Query them in parallel or sequentially (sequential is safer for DDG to avoid rate limits, but we can do it fast)
    for query in queries[:2]:  # query the top 2 combinations to avoid rate limits on DDG
        res = await search_query(query, max_results=max_results)
        combined_results.extend(res)
        if len(combined_results) >= max_results:
            break
            
    return combined_results[:max_results]
