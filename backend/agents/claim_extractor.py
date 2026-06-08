import json
import uuid
import logging
import re
from typing import Dict, Any, List
from backend.agents.state import AgentState
from backend.agents.utils import get_llm

logger = logging.getLogger(__name__)

async def extract_claims_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts high-importance, verifiable factual claims from the article.
    Ignores opinions, speculative, and subjective comments.
    """
    logger.info("Starting Claim Extraction Agent...")
    
    article_content = state.get("article_content", "")
    errors = state.get("errors", [])
    
    if not article_content:
        errors.append("No article content available to extract claims.")
        return {"claims": [], "errors": errors}
        
    try:
        llm = get_llm(temperature=0)
        
        prompt = (
            f"You are a professional fact-checker. Extract up to 5 major, specific, and verifiable factual claims "
            f"from the article below. Ignore opinions, predictions, or subjective statements. "
            f"Focus on claims that can be proven true or false using web search, official statistics, or news archives.\n\n"
            f"Article Content:\n{article_content[:8000]}\n\n"
            f"Output your response strictly as a JSON array of objects. Do not include markdown code block formatting (such as ```json) or any explanation. "
            f"Use the following structure for each object in the array:\n"
            f"[\n"
            f"  {{\n"
            f"    \"claim_text\": \"The exact claim to be verified\",\n"
            f"    \"category\": \"Category of the claim (e.g., Health, Politics, Science, Economics, Technology)\"\n"
            f"  }}\n"
            f"]"
        )
        
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        
        # Strip any markdown code blocks if the LLM outputted them despite instructions
        if content.startswith("```"):
            # strip markdown block ticks
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()
            
        try:
            parsed_claims = json.loads(content)
        except json.JSONDecodeError:
            # Fallback regex parser or secondary smaller model query if JSON parsing fails.
            # Let's try to find a JSON list in the response.
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                parsed_claims = json.loads(match.group(0))
            else:
                raise ValueError("LLM response did not contain a valid JSON array.")
                
        # Format the claims with unique IDs
        claims_list = []
        for index, item in enumerate(parsed_claims):
            claim_text = item.get("claim_text", "").strip()
            if claim_text:
                claims_list.append({
                    "id": f"claim_{uuid.uuid4().hex[:8]}",
                    "claim_text": claim_text,
                    "category": item.get("category", "General")
                })
                
        logger.info(f"Extracted {len(claims_list)} claims.")
        return {"claims": claims_list}
        
    except Exception as e:
        logger.error(f"Error in Claim Extraction Agent: {e}")
        errors.append(f"Claim extraction failed: {str(e)}")
        return {"claims": [], "errors": errors}
