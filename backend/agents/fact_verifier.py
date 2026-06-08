import asyncio
import json
import logging
import re
from typing import Dict, Any, List
from backend.agents.state import AgentState
from backend.agents.utils import get_llm

logger = logging.getLogger(__name__)

async def verify_claims_node(state: AgentState) -> Dict[str, Any]:
    """
    Fact Verification Agent.
    Evaluates claims against retrieved evidence in parallel and determines a 6-point verdict.
    """
    logger.info("Starting Fact Verification Agent...")
    
    claims = state.get("claims", [])
    evidences = state.get("evidences", {})
    errors = state.get("errors", [])
    
    if not claims:
        logger.warning("No claims available for verification.")
        return {"verdicts": {}}
        
    verdicts = {}
    tasks = []
    
    async def verify_single_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
        claim_id = claim["id"]
        claim_text = claim["claim_text"]
        claim_evidence = evidences.get(claim_id, [])
        
        if not claim_evidence:
            return {
                "claim_id": claim_id,
                "verdict": "UNVERIFIED",
                "explanation": "No relevant evidence could be retrieved to support or refute this claim."
            }
            
        # Format evidence for the prompt
        evidence_str = ""
        for i, ev in enumerate(claim_evidence, 1):
            evidence_str += (
                f"[{i}] Source: {ev['source_title']} ({ev['source_url']})\n"
                f"    Domain Credibility: {ev['source_credibility']:.2f}, Confidence: {ev['confidence_score']:.2f}\n"
                f"    Snippet: {ev['snippet']}\n\n"
            )
            
        prompt = (
            f"You are an expert, unbiased fact-checking AI. Your task is to evaluate the following claim "
            f"against the provided search evidence.\n\n"
            f"Claim: \"{claim_text}\"\n\n"
            f"Evidence:\n{evidence_str}"
            f"Analyze the evidence and select the most appropriate verdict from this 6-point scale:\n"
            f"- TRUE: The claim is fully accurate and supported by high-credibility sources.\n"
            f"- LIKELY TRUE: The claim is supported by credible sources, but minor details or context could be elaborated.\n"
            f"- MISLEADING: The claim contains some factual elements but is presented out of context, exaggerated, or mixed with false information.\n"
            f"- UNVERIFIED: There is not enough evidence to make a determination, or sources are heavily in conflict without resolution.\n"
            f"- LIKELY FALSE: The claim is contradicted by credible sources or lacks any supporting evidence while containing major falsehood indicators.\n"
            f"- FALSE: The claim is demonstrably false and explicitly contradicted by highly credible sources.\n\n"
            f"Provide your verdict and a detailed, objective explanation (2-3 sentences) referencing the specific sources (e.g. [1], [2]).\n\n"
            f"Output your response strictly as a JSON object. Do not include markdown code block formatting (such as ```json) or any pre/post text. "
            f"Use the following structure:\n"
            f"{{\n"
            f"  \"verdict\": \"TRUE / LIKELY TRUE / MISLEADING / UNVERIFIED / LIKELY FALSE / FALSE\",\n"
            f"  \"explanation\": \"Your detailed explanation here...\"\n"
            f"}}"
        )
        
        try:
            llm = get_llm(temperature=0)
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Strip potential markdown formatting
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n", "", content)
                content = re.sub(r"\n```$", "", content)
                content = content.strip()
                
            parsed = json.loads(content)
            
            # Normalize verdict
            verdict = parsed.get("verdict", "UNVERIFIED").strip().upper()
            if verdict not in ["TRUE", "LIKELY TRUE", "MISLEADING", "UNVERIFIED", "LIKELY FALSE", "FALSE"]:
                verdict = "UNVERIFIED"
                
            return {
                "claim_id": claim_id,
                "verdict": verdict,
                "explanation": parsed.get("explanation", "Verification completed with no detailed explanation.")
            }
        except Exception as e:
            logger.error(f"Error verifying claim {claim_id}: {e}")
            return {
                "claim_id": claim_id,
                "verdict": "UNVERIFIED",
                "explanation": f"Failed to verify this claim due to an internal error: {str(e)}"
            }
            
    # Run all verifications in parallel
    results = await asyncio.gather(*[verify_single_claim(c) for c in claims])
    
    for r in results:
        verdicts[r["claim_id"]] = {
            "verdict": r["verdict"],
            "explanation": r["explanation"]
        }
        
    logger.info("Fact Verification Agent completed.")
    return {"verdicts": verdicts}
