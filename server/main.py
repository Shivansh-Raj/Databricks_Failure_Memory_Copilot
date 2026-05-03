import uuid
import os
import sys
from langgraph.types import Command
from fastapi import HTTPException, UploadFile, File 
from typing import List


import traceback

# Command to run uvicorn server
# uvicorn server.main:app --reload --port 8000      

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
    from app.graph import pipeline
    
    return pipeline

def _extract_interrupt(result) -> Optional[dict]:
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
        result = pipeline.invoke(initial_state, config=config)
    except Exception as e:
        # Returns full traceback as JSON — not a 500
        return {
            "session_id":       None,
            "status":           "error",
            "error":            str(e),
            "traceback":        traceback.format_exc(),
            "final_resolution": None,
            "candidate":        None,
        }

    
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
def respond(req: RespondRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or already resolved.")

    pipeline = get_pipeline()
    config   = session["config"]
    choice   = req.choice.strip().lower()

    if choice not in ("y", "n", "g", "q"):
        raise HTTPException(status_code=400, detail="Invalid choice. Use: y | n | g | q")

    try:
        result = pipeline.invoke(Command(resume=choice), config=config)
    except Exception as e:
        # Return full traceback as JSON instead of 500
        return {
            "session_id":       req.session_id,
            "status":           "error",
            "error":            str(e),
            "traceback":        traceback.format_exc(),
            "final_resolution": None,
            "candidate":        None,
        }

    interrupt_payload = _extract_interrupt(result)

    if interrupt_payload:
        candidates = result.get("retrieved_candidates") or []
        index      = result.get("current_candidate_index", 0)
        return {
            "session_id": req.session_id,
            "status":     "awaiting_input",
            "candidate":  _format_candidate(interrupt_payload, candidates, index),
        }

    _sessions.pop(req.session_id, None)
    return {
        "session_id":       req.session_id,
        "status":           "resolved",
        "final_resolution": result.get("final_resolution", "No resolution found."),
        "candidate":        None,
    }
    
@app.get("/status/{session_id}")
def status(session_id: str):
    if session_id in _sessions:
        return {"session_id": session_id, "status": "awaiting_input"}
    return {"session_id": session_id, "status": "resolved_or_not_found"}
 
 
@app.get("/health")
def health():
    return {"status": "ok"}
 
@app.post("/extract")
async def extract(files: List[UploadFile] = File(...)): 
    """
    Accepts 1 or 2 screenshot files.
    Returns extracted and separated error_text and code_text.
    """
    from server.ocr_extractor import process_screenshots
    
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 screenshots allowed.")

    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {f.content_type}. Only PNG, JPG, WEBP allowed."
            )    
            
    try:
        image_byte = [await f.read() for f in files]
        result = process_screenshots(image_byte)
        # print("_______________________________")
        # print(result)
        # print("_______________________________")
        return {
            "status" : "Success",
            "error_text": result.get("error_text", ""),
            "code_text":  result.get("code_text",  ""),
            "warning":    result.get("warning"),
        }
    except Exception as e:
        import traceback
        return {
            "status":    "error",
            "error":     str(e),
            "traceback": traceback.format_exc(),
        }