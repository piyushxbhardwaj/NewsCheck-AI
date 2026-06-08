import logging
from typing import Dict, Any, List
from backend.agents.state import AgentState
from backend.agents.utils import get_llm

logger = logging.getLogger(__name__)

# Map verdicts to numerical scores
VERDICT_SCORES = {
    "TRUE": 100,
    "LIKELY TRUE": 80,
    "MISLEADING": 45,
    "UNVERIFIED": 50,
    "LIKELY FALSE": 20,
    "FALSE": 0
}

async def generate_report_node(state: AgentState) -> Dict[str, Any]:
    """
    Report Generation Agent.
    Aggregates all findings, calculates the final credibility score,
    determines the overall article-level verdict, and creates a comprehensive report.
    """
    logger.info("Starting Report Generation Agent...")
    
    claims = state.get("claims", [])
    verdicts = state.get("verdicts", {})
    evidences = state.get("evidences", {})
    bias_rating = state.get("bias_rating", "Unknown")
    tone_rating = state.get("tone_rating", "Unknown")
    bias_explanation = state.get("bias_explanation", "")
    summary = state.get("summary", "")
    title = state.get("article_title", "Untitled Article")
    url = state.get("url", "")
    
    if not claims:
        # Default report if no claims could be processed
        return {
            "final_verdict": "UNVERIFIED",
            "credibility_score": 50,
            "final_report": "## Analysis Failed\nCould not extract or verify any claims from this content."
        }
        
    # 1. Calculate base credibility score from claim verdicts
    total_score = 0
    valid_verdicts_count = 0
    
    for claim in claims:
        claim_id = claim["id"]
        v_info = verdicts.get(claim_id, {})
        v_str = v_info.get("verdict", "UNVERIFIED").upper()
        
        score = VERDICT_SCORES.get(v_str, 50)
        total_score += score
        valid_verdicts_count += 1
        
    base_score = total_score / valid_verdicts_count if valid_verdicts_count > 0 else 50
    
    # 2. Adjustments
    # Penalty for sensationalism or fear-inducing tone
    tone_penalty = 0
    if tone_rating == "Sensational":
        tone_penalty = 8
    elif tone_rating == "Fear-inducing":
        tone_penalty = 12
        
    # Adjust score based on source credibility
    # Find the average credibility of all cited sources
    all_sources_credibility = []
    for claim_id, ev_list in evidences.items():
        for ev in ev_list:
            all_sources_credibility.append(ev.get("source_credibility", 0.5))
            
    source_adjustment = 0
    if all_sources_credibility:
        avg_source_cred = sum(all_sources_credibility) / len(all_sources_credibility)
        # Shift score up or down slightly based on source quality (range -5 to +5)
        source_adjustment = (avg_source_cred - 0.5) * 10
        
    final_score = base_score - tone_penalty + source_adjustment
    final_score = max(0, min(100, int(final_score)))  # Clamp to [0, 100]
    
    # 3. Determine overall verdict based on final score
    if all(verdicts.get(c["id"], {}).get("verdict") == "UNVERIFIED" for c in claims):
        final_verdict = "UNVERIFIED"
    elif final_score >= 85:
        final_verdict = "TRUE"
    elif final_score >= 70:
        final_verdict = "LIKELY TRUE"
    elif final_score >= 40:
        final_verdict = "MISLEADING"
    elif final_score >= 20:
        final_verdict = "LIKELY FALSE"
    else:
        final_verdict = "FALSE"
        
    # 4. Generate the report via LLM for natural, cohesive phrasing
    # Feed all structured results to the LLM to write a comprehensive report
    claims_summary_str = ""
    for idx, claim in enumerate(claims, 1):
        c_id = claim["id"]
        v_info = verdicts.get(c_id, {})
        claims_summary_str += f"Claim {idx}: \"{claim['claim_text']}\"\n"
        claims_summary_str += f"Verdict: {v_info.get('verdict', 'UNVERIFIED')}\n"
        claims_summary_str += f"Explanation: {v_info.get('explanation', 'No explanation')}\n\n"
        
    prompt = (
        f"You are a professional fact-checker. Write a detailed, objective, and comprehensive fact-check report "
        f"based on the following findings:\n\n"
        f"Article Title: {title}\n"
        f"URL: {url if url else 'N/A'}\n"
        f"Summary: {summary}\n\n"
        f"Individual Claims Verified:\n{claims_summary_str}"
        f"Bias Rating: {bias_rating}\n"
        f"Tone Rating: {tone_rating}\n"
        f"Bias/Tone Explanation: {bias_explanation}\n\n"
        f"Final Overall Verdict: {final_verdict}\n"
        f"Calculated Credibility Score: {final_score}/100\n\n"
        f"Structure the final output as a Markdown-formatted document with the following sections:\n"
        f"- ## Executive Summary: A 3-4 sentence high-level overview of the findings.\n"
        f"- ## Credibility & Bias Analysis: Summarize the bias, tone, and overall trustworthiness.\n"
        f"- ## Key Claims and Verdicts: A list or table explaining the major claims, their verdicts, and short explanations.\n"
        f"- ## Sources and Citations: List the primary sources used for verification (including links where available).\n"
        f"Be professional, clear, and objective. Avoid adding extra system notes. Just output the markdown text."
    )
    
    try:
        llm = get_llm(temperature=0.2)
        response = await llm.ainvoke(prompt)
        final_report = response.content.strip()
    except Exception as e:
        logger.error(f"Error generating markdown report: {e}")
        # Fallback manual markdown builder
        final_report = f"""
## Executive Summary
This article titled "{title}" has been reviewed. The overall verdict is **{final_verdict}** with a credibility score of **{final_score}/100**.

## Credibility & Bias Analysis
* **Political Bias:** {bias_rating}
* **Emotional Tone:** {tone_rating}
* **Explanation:** {bias_explanation}

## Key Claims and Verdicts
"""
        for claim in claims:
            v_info = verdicts.get(claim["id"], {})
            final_report += f"- **Claim:** {claim['claim_text']}\n  - *Verdict:* {v_info.get('verdict')}\n  - *Explanation:* {v_info.get('explanation')}\n\n"

    logger.info("Report Generation Agent complete.")
    return {
        "final_verdict": final_verdict,
        "credibility_score": final_score,
        "final_report": final_report
    }
