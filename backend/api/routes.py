from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl, model_validator
from typing import Optional, List, Dict, Any
import uuid
import logging
from datetime import datetime

from backend.agents.workflow import compiled_workflow
from backend.services.db_service import (
    save_article, 
    get_articles_history, 
    get_article_details, 
    get_sources_dict, 
    upsert_source,
    delete_source
)

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for tracking background job statuses
jobs_db: Dict[str, Dict[str, Any]] = {}

class VerifyRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None

    @model_validator(mode="after")
    def validate_input(self):
        if not self.url and not self.text:
            raise ValueError("Either url or text must be provided.")
        return self

class SourceUpdate(BaseModel):
    domain: str
    credibility_score: float
    bias_rating: str
    description: Optional[str] = ""


async def run_verification_job(job_id: str, url: Optional[str], text: Optional[str]):
    """Background worker task that executes the LangGraph workflow."""
    jobs_db[job_id] = {
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "error": None
    }
    
    try:
        initial_state = {
            "url": url,
            "raw_text": text,
            "claims": [],
            "search_results": [],
            "evidences": {},
            "verdicts": {},
            "deep_search_done": False,
            "loop_count": 0,
            "errors": []
        }
        
        # Execute the LangGraph workflow
        logger.info(f"Executing LangGraph workflow for job {job_id}")
        final_state = await compiled_workflow.ainvoke(initial_state)
        
        # Check for critical errors
        if final_state.get("errors") and not final_state.get("article_content"):
            raise ValueError(f"Workflow failed: {'; '.join(final_state['errors'])}")
            
        # Structure the article and claims for saving to the DB
        article_data = {
            "id": job_id,
            "url": url,
            "title": final_state.get("article_title"),
            "content": final_state.get("article_content"),
            "summary": final_state.get("summary"),
            "verdict": final_state.get("final_verdict", "UNVERIFIED"),
            "credibility_score": final_state.get("credibility_score", 50),
            "bias_rating": final_state.get("bias_rating", "Unknown"),
            "tone_rating": final_state.get("tone_rating", "Unknown"),
            "created_at": datetime.now().isoformat()
        }
        
        claims = final_state.get("claims", [])
        verdicts = final_state.get("verdicts", {})
        evidences = final_state.get("evidences", {})
        
        # Map state back to DB format
        db_claims = []
        db_evidences = []
        
        for c in claims:
            c_id = c["id"]
            c_verdict = verdicts.get(c_id, {})
            
            db_claims.append({
                "id": c_id,
                "claim_text": c["claim_text"],
                "verdict": c_verdict.get("verdict", "UNVERIFIED"),
                "explanation": c_verdict.get("explanation", "")
            })
            
            # Map evidence for this claim
            claim_evs = evidences.get(c_id, [])
            for ev in claim_evs:
                db_evidences.append({
                    "id": str(uuid.uuid4()),
                    "claim_id": c_id,
                    "source_domain": ev.get("source_domain"),
                    "source_url": ev.get("source_url"),
                    "source_title": ev.get("source_title"),
                    "snippet": ev.get("snippet"),
                    "type": ev.get("type", "NEUTRAL"), # Default or calculated
                    "relevance_score": ev.get("relevance_score", 0.0)
                })
                
        # Save to database
        save_article(article_data, db_claims, db_evidences)
        
        jobs_db[job_id] = {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "article_id": job_id,
            "result": {
                "title": article_data["title"],
                "verdict": article_data["verdict"],
                "credibility_score": article_data["credibility_score"],
                "bias_rating": article_data["bias_rating"],
                "tone_rating": article_data["tone_rating"],
                "summary": article_data["summary"],
                "report": final_state.get("final_report")
            }
        }
        logger.info(f"Job {job_id} successfully completed and saved to DB.")
        
    except Exception as e:
        logger.exception(f"Error executing verification job {job_id}")
        jobs_db[job_id] = {
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        }

@router.post("/verify")
async def verify_article(request: VerifyRequest, background_tasks: BackgroundTasks):
    """Submits an article for fact-checking. Runs asynchronously."""
    if not request.url and not request.text:
        raise HTTPException(status_code=400, detail="Either a URL or plain text must be provided.")
        
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "error": None
    }
    
    background_tasks.add_task(
        run_verification_job, 
        job_id, 
        str(request.url) if request.url else None, 
        request.text
    )
    
    return {"job_id": job_id, "status": "pending"}

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Retrieves the status and result of a background fact-checking job."""
    if job_id not in jobs_db:
        # Check if it was already saved in DB
        article = get_article_details(job_id)
        if article:
            return {
                "status": "completed",
                "article_id": job_id,
                "result": {
                    "title": article["title"],
                    "verdict": article["verdict"],
                    "credibility_score": article["credibility_score"],
                    "bias_rating": article["bias_rating"],
                    "tone_rating": article["tone_rating"],
                    "summary": article["summary"],
                    "report": article.get("final_report", "No report available")
                }
            }
        raise HTTPException(status_code=404, detail="Job not found.")
    return jobs_db[job_id]

@router.get("/history")
async def get_history():
    """Retrieves the history of all verified articles."""
    try:
        return get_articles_history()
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{article_id}")
async def get_details(article_id: str):
    """Retrieves the full report details including claims and evidence."""
    details = get_article_details(article_id)
    if not details:
        raise HTTPException(status_code=404, detail="Article not found in history.")
    return details

@router.get("/sources")
async def get_sources():
    """Retrieves the list of known news sources and their credibility ratings."""
    try:
        return get_sources_dict()
    except Exception as e:
        logger.error(f"Error fetching sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources")
async def add_source(source: SourceUpdate):
    """Adds or updates a source credibility rating."""
    try:
        upsert_source(source.domain, source.credibility_score, source.bias_rating, source.description)
        return {"status": "success", "message": f"Source {source.domain} updated successfully."}
    except Exception as e:
        logger.error(f"Error updating source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats():
    """Returns overall platform usage and credibility stats."""
    try:
        history = get_articles_history()
        total_checked = len(history)
        if total_checked == 0:
            return {
                "total_checked": 0,
                "average_credibility": 0.0,
                "verdict_breakdown": {}
            }
            
        avg_score = sum(item["credibility_score"] for item in history) / total_checked
        
        verdict_breakdown = {}
        for item in history:
            verdict = item["verdict"]
            verdict_breakdown[verdict] = verdict_breakdown.get(verdict, 0) + 1
            
        return {
            "total_checked": total_checked,
            "average_credibility": round(avg_score, 1),
            "verdict_breakdown": verdict_breakdown
        }
    except Exception as e:
        logger.error(f"Error generating stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/sources/{domain}")
async def update_source(domain: str, source: SourceUpdate):
    """Updates a source credibility rating."""
    try:
        upsert_source(domain, source.credibility_score, source.bias_rating, source.description)
        return {"status": "success", "message": f"Source {domain} updated successfully."}
    except Exception as e:
        logger.error(f"Error updating source {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sources/{domain}")
async def delete_source_route(domain: str):
    """Deletes a source profile."""
    try:
        deleted = delete_source(domain)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Source {domain} not found.")
        return {"status": "success", "message": f"Source {domain} deleted successfully."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting source {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Returns the service health status."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

async def run_evaluation_task():
    from evaluation.run_eval import run_evaluation
    try:
        await run_evaluation()
    except Exception as e:
        logger.error(f"Background evaluation failed: {e}")

@router.post("/evaluate")
async def trigger_evaluation(background_tasks: BackgroundTasks):
    """Triggers the evaluation suite in the background."""
    background_tasks.add_task(run_evaluation_task)
    return {"status": "processing", "message": "Evaluation started in background."}

@router.get("/evaluate")
async def get_evaluation_results():
    """Retrieves the latest evaluation results from disk if they exist."""
    from pathlib import Path
    import json
    report_file = Path(__file__).resolve().parent.parent.parent / "evaluation" / "eval_results.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="No evaluation results found. Run POST /api/evaluate first.")
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)
