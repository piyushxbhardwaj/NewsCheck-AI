import json
import logging
import re
from typing import Dict, Any
from backend.agents.state import AgentState
from backend.agents.utils import get_llm

logger = logging.getLogger(__name__)

async def detect_bias_node(state: AgentState) -> Dict[str, Any]:
    """
    Bias & Tone Detection Agent.
    Analyzes the text for political alignment (Left, Center-Left, Center, Center-Right, Right)
    and emotional tone (Neutral, Sensational, Fear-inducing) with details on findings.
    """
    logger.info("Starting Bias Detection Agent...")
    
    article_content = state.get("article_content", "")
    errors = state.get("errors", [])
    
    if not article_content:
        return {
            "bias_rating": "Unknown",
            "tone_rating": "Unknown",
            "bias_explanation": "No article content available for bias analysis."
        }
        
    prompt = (
        f"You are an expert media analyst trained in identifying political bias and emotional tone in text.\n\n"
        f"Analyze the following text and determine:\n"
        f"1. Political Bias (select one from: Left, Center-Left, Center, Center-Right, Right)\n"
        f"2. Emotional Tone (select one from: Neutral, Sensational, Fear-inducing)\n"
        f"3. A brief explanation (2-3 sentences) detailing your assessment, citing any loaded words or biased framing.\n\n"
        f"Text to analyze:\n{article_content[:8000]}\n\n"
        f"Output your response strictly as a JSON object. Do not include markdown formatting or extra text. "
        f"Use the following structure:\n"
        f"{{\n"
        f"  \"bias_rating\": \"Center/Left/Right/etc.\",\n"
        f"  \"tone_rating\": \"Neutral/Sensational/Fear-inducing\",\n"
        f"  \"bias_explanation\": \"Explanation of your choice with specific examples if any.\"\n"
        f"}}"
    )
    
    try:
        llm = get_llm(temperature=0)
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()
            
        parsed = json.loads(content)
        
        return {
            "bias_rating": parsed.get("bias_rating", "Center"),
            "tone_rating": parsed.get("tone_rating", "Neutral"),
            "bias_explanation": parsed.get("bias_explanation", "")
        }
    except Exception as e:
        logger.error(f"Error in Bias Detection Agent: {e}")
        errors.append(f"Bias detection failed: {str(e)}")
        return {
            "bias_rating": "Unknown",
            "tone_rating": "Unknown",
            "bias_explanation": f"Bias analysis failed due to error: {str(e)}",
            "errors": errors
        }
