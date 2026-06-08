import logging
from typing import Dict, Any
from backend.agents.state import AgentState
from backend.agents.utils import get_llm
from backend.services.scrape_service import scrape_url

logger = logging.getLogger(__name__)

async def extract_article_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts article text and metadata (title, domain) from a URL 
    or processes raw text. Generates a summary of the content using LLM.
    """
    logger.info("Starting Article Extraction Agent...")
    
    url = state.get("url")
    raw_text = state.get("raw_text")
    errors = state.get("errors", [])
    
    article_title = "User Provided Text"
    article_content = ""
    article_domain = "User Input"
    
    if url:
        logger.info(f"Scraping content from URL: {url}")
        scraped = scrape_url(url)
        if scraped.get("error"):
            errors.append(f"Scraper error: {scraped['error']}")
            # Fallback to raw_text if provided, or use whatever content we retrieved
            article_content = scraped.get("content", "")
        else:
            article_title = scraped.get("title", "Untitled Article")
            article_content = scraped.get("content", "")
            article_domain = scraped.get("domain", "")
    elif raw_text:
        logger.info("Processing raw text input.")
        article_content = raw_text
        # Let LLM generate a title from raw text
        try:
            llm = get_llm(temperature=0)
            prompt = f"Based on the following text, generate a short, descriptive headline or title (maximum 10 words):\n\n{article_content[:1000]}"
            response = await llm.ainvoke(prompt)
            article_title = response.content.strip().replace('"', '')
        except Exception as e:
            logger.error(f"Error generating title for raw text: {e}")
            article_title = "User Text Snippet"
    else:
        errors.append("No URL or text input provided for analysis.")
        return {"errors": errors}
        
    # Generate summary of the content
    summary = ""
    if article_content:
        try:
            llm = get_llm(temperature=0.3)
            prompt = (
                f"You are a professional, neutral fact-checking assistant.\n"
                f"Please write a concise summary (3-5 sentences) of the following article/text:\n\n"
                f"Title: {article_title}\n"
                f"Content:\n{article_content[:6000]}" # Limit to first 6000 chars for summary efficiency
            )
            response = await llm.ainvoke(prompt)
            summary = response.content.strip()
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            summary = "Summary generation failed."
            errors.append(f"Summary generation error: {str(e)}")
            
    return {
        "article_title": article_title,
        "article_content": article_content,
        "article_domain": article_domain,
        "summary": summary,
        "errors": errors
    }
