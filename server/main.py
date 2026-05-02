import uuid
import os
import sys
from click import Command
from fastapi import HTTPException

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), 
            ".."
        )
    )
)

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title = "Databricks Failure Memory Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    error_text : str
    code_text : Optional[str] = None
    
class RespondRequest(BaseModel):
    session_id : str
    choice: str 
    
# -------------------------------------------------------------------------------------
# In Memory Store
# -------------------------------------------------------------------------------------

_sessions : dict[str, dict] = {}


def get_pipeline():
    from app.graph import run_pipeline
    
    return run_pipeline

def _extract_interrupt(interrupt_payload: dict, retrieved_candidates: list, index: int) -> dict:
    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value          
    return None
 
def _format_candidate(interrupt_payload: dict, retrieved_candidates: list, index: int) -> dict:
    
    if index >= len(retrieved_candidates):
        return {}
    
    candidate = retrieved_candidates[index]
    metadata = candidate.get("metadata", {})
    tags = metadata.get("tags", {})
    return {
        "incident_id":  candidate.get("incident_id", "N/A"),
        "score":        round(candidate.get("score", 0.0), 4),
        "severity":     metadata.get("severity", "unknown"),
        "tags":         tags if isinstance(tags, list) else tags.split(","),
        "resolution":   candidate.get("resolution") or _extract_resolution_from_doc(candidate.get("document", "")),
        # "resolution":   candidate.get("resolution"),
        "index":        index,
        "total":        len(retrieved_candidates),
    }
    
def _extract_resolution_from_doc(document: str) -> str:
    for line in document.splitlines():
        if line.strip().startswith("Resolution:"):
            return line.split("Resolution:", 1)[-1].strip()
    return "Not available"
    

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    pipeline = get_pipeline()
    session_id = str(uuid.uuid4())
    thread_id = session_id
    config = {"configurable": {"thread_id" : thread_id}}
    initial_state = {
        "raw_error":               request.error_text,
        "raw_code":                request.code_text,
        "raw_resolution":          None,
        "error_message":           "",
        "tags":                    [],
        "severity":                "unknown",
        "code_context":            None,
        "resolution":              None,
        "top_score":               None,
        "confidence":              "low",
        "final_resolution":        "",
        "retrieved_candidates":    None,
        "rag_confidence_result":   None,
        "current_candidate_index": 0,
    }
    
    try:
        result = pipeline.invoke(config=config, state=initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
    
    interrupt_payload = _extract_interrupt(result)
    
    if not interrupt_payload:
        return {
            "session_id":        session_id,
            "status":            "resolved",
            "final_resolution":  result.get("final_resolution", "No resolution found."),
            "candidate":         None,
        }
    
    _sessions[session_id] = {
        "thread_id": thread_id,
        "config" : config
    }
    
    candidates = result.get("retrieved_candidates") or []
    index      = result.get("current_candidate_index", 0)
 
    return {
        "session_id": session_id,
        "status":     "awaiting_input",
        "candidate":  _format_candidate(interrupt_payload, candidates, index),
    }
    
@app.post("/respond")
def respond(request: RespondRequest):
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    pipeline = get_pipeline()
    config = session["config"]
    choice = request.choice.strip().lower()
    
    if choice not in ("y", "n", "g", "q"):
        raise HTTPException(status_code=400, detail="Invalid choice. Use: y | n | g | q")
    
    try:
        result = pipeline.invoke(Command(resume = choice), config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
    
    interrupt_payload = _extract_interrupt(result)
    
    
    if interrupt_payload:
        candidates = result.get("retrieved_candidates") or []
        index      = result.get("current_candidate_index", 0)
        
        return {
            "session_id": request.session_id,
            "status":     "awaiting_input",
            "candidate":  _format_candidate(interrupt_payload, candidates, index),
        }  
    
    _sessions.pop(request.session_id, None)
    
    return {
        "session_id": request.session_id,
        "status":     "resolved",
        "final_resolution": result.get("final_resolution", "No resolution found."),
        "candidate": None
    }
    
@app.get("/status/{session_id}")
def status(session_id: str):
    if session_id in _sessions:
        return {"session_id": session_id, "status": "awaiting_input"}
    return {"session_id": session_id, "status": "resolved_or_not_found"}
 
 
@app.get("/health")
def health():
    return {"status": "ok"}
 