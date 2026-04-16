from typing import TypedDict, Optional
from app.matcher import Matcher
import groq_normalizer
from app.knowledge_base import load_incidents, add_incident

class IncidentState(TypedDict):
    # inputs
    raw_error:        str
    raw_code:         Optional[str]
    raw_resolution:   Optional[str]

    # after normalize_error
    error_message:    str
    tags:             list[str]
    severity:         str

    # after analyze_code
    code_context:     Optional[dict]

    # after normalize_resolution
    resolution:       Optional[str]

    # after match
    match_results:    Optional[list]
    top_score:        Optional[float]

    # after match_decider
    confidence:       str

    # after groq_suggest
    final_resolution: str
    
def normalize_error_node(state: IncidentState) -> IncidentState:
    result = groq_normalizer.normalize_error(state["raw_error"])
    return {
        **state,
        "error_message": result["error_message"],
        "tags":          result["tags"],
        "severity":      result["severity"],
    }
    
def analyze_code_node(state: IncidentState) -> IncidentState:
    # skip entirely if no code was provided
    if not state.get("raw_code"):
        return {**state, "code_context": None}

    ctx = groq_normalizer.analyze_code(
        error_message=state["error_message"],
        code_snippet=state["raw_code"],
    )
    return {**state, "code_context": ctx}

def normalize_resolution_node(state: IncidentState) -> IncidentState:
    if not state.get("raw_resolution"):
        return {**state, "resolution": None}

    normalized = groq_normalizer.normalize_resolution(state["raw_resolution"])
    return {**state, "resolution": normalized}


def match_node(state: IncidentState) -> IncidentState:
    print(f"\n[DEBUG] match_node running")
    incidents = load_incidents()
    matcher = Matcher(incidents)
    results = matcher.find_matches(
        query=state["error_message"],
        tags=state.get("tags"),
        code_context=state.get("code_context"),
    )
    top_score = results[0]["score"] if results else 0.0
    print(f"[DEBUG] match_node — results: {len(results)}, top_score: {top_score}")
    return {
        **state,
        "match_results": results,
        "top_score":     top_score,
    }
    
def match_decider_node(state: IncidentState) -> IncidentState:
    top_score = state.get("top_score", 0.0)
    confidence = "high" if top_score >= 0.6 else "low"
    print(f"\n[DEBUG] match_decider — top_score: {top_score}, confidence: {confidence}")
    return {**state, "confidence": confidence}


SUGGEST_PROMPT = """You are an expert Databricks and Apache Spark failure analyst.
No similar historical incident was found for this failure.
Based on the error and code context provided, suggest a resolution.
Return only plain text — no JSON, no markdown."""

def groq_suggest_node(state: IncidentState) -> IncidentState:
    final = "No suggestion available — review error manually.---------------------------------------"
    try:
        user_content = f"ERROR:\n{state['error_message']}"
        if state.get("code_context"):
            ctx = state["code_context"]
            user_content += f"\n\nCODE PATTERN: {ctx.get('pattern')}"
            user_content += f"\nHOTSPOT: {ctx.get('likely_hotspot')}"

        suggestion = groq_normalizer._call_groq(SUGGEST_PROMPT, user_content)
        print("------------------------------------------")
        print(suggestion)
        print("------------------------------------------")
        final = suggestion.strip()
    except Exception as e:
        # logger.warning("groq_suggest failed: %s", e)
        final = "No suggestion available — review error manually."

    return {**state, "final_resolution": final}


from langgraph.graph import StateGraph, END

def _route_after_decider(state: IncidentState) -> str:
    return "groq_suggest" if state["confidence"] == "low" else END

def build_graph():
    graph = StateGraph(IncidentState)

    graph.add_node("normalize_error",       normalize_error_node)
    graph.add_node("analyze_code",          analyze_code_node)
    graph.add_node("normalize_resolution",  normalize_resolution_node)
    graph.add_node("match",                 match_node)
    graph.add_node("match_decider",         match_decider_node)
    graph.add_node("groq_suggest",          groq_suggest_node)

    graph.set_entry_point("normalize_error")

    graph.add_edge("normalize_error",      "analyze_code")
    graph.add_edge("analyze_code",         "normalize_resolution")
    graph.add_edge("normalize_resolution", "match")
    graph.add_edge("match",                "match_decider")
    graph.add_edge("groq_suggest",         END)

    graph.add_conditional_edges(
        "match_decider",
        _route_after_decider,
        {"groq_suggest": "groq_suggest", END: END}
    )

    return graph.compile()

pipeline = build_graph()


def run_pipeline(
    raw_error: str,
    raw_code: Optional[str] = None,
    raw_resolution: Optional[str] = None,
) -> IncidentState:
    initial_state: IncidentState = {
        "raw_error":       raw_error,
        "raw_code":        raw_code,
        "raw_resolution":  raw_resolution,
        "error_message":   "",
        "tags":            [],
        "severity":        "unknown",
        "code_context":    None,
        "resolution":      None,
        "match_results":   None,
        "top_score":       None,
        "confidence":      "low",
        "final_resolution": "",
    }
    return pipeline.invoke(initial_state)


class AddIncidentState(TypedDict):
    # inputs
    raw_error:          str
    raw_code:           Optional[str]
    raw_resolution:     str           # required in add flow, optional in main flow

    # after normalize_error
    error_message:      str
    tags:               list[str]
    severity:           str

    # after analyze_code
    code_context:       Optional[dict]

    # after normalize_resolution
    resolution:         str

    # after match
    match_results:      Optional[list]
    top_score:          Optional[float]

    # after duplicate_decider
    duplicate_status:   str           # "unique" or "duplicate"
    duplicate_incident: Optional[dict] # the matching incident if duplicate

    # after write_incident
    written_id:         Optional[str]  # e.g. "INC-021" if written, None if blocked
    kb_path:            Optional[str]  # path to KB file
    

DUPLICATE_THRESHOLD = 0.8

# REMOVE write_incident_node entirely
# REPLACE with just setting a flag in duplicate_decider

def duplicate_decider_node(state: AddIncidentState) -> AddIncidentState:
    top_score = state.get("top_score", 0.0)
    results = state.get("match_results") or []

    if top_score >= DUPLICATE_THRESHOLD:
        duplicate_incident = results[0]["incident"]
        return {
            **state,
            "duplicate_status":   "duplicate",
            "duplicate_incident": duplicate_incident,
        }

    return {
        **state,
        "duplicate_status":   "unique",
        "duplicate_incident": None,
    }
    
    
# def write_incident_node(state: AddIncidentState) -> AddIncidentState:
#     record = {
#         "error_message": state["error_message"],
#         "resolution":    state["resolution"],
#         "tags":          state["tags"],
#         "severity":      state["severity"],
#     }
#     if state.get("code_context"):
#         record["code_context"] = state["code_context"]

#     new_id = add_incident(record, path=state.get("kb_path"))
#     # logger.info("Incident written: %s", new_id)
#     return {**state, "written_id": new_id}

def warn_duplicate_node(state: AddIncidentState) -> AddIncidentState:
    print("\n  Incident not added — too similar to existing record.")
    print("  Use --force to override and add anyway.\n")
    return {**state, "written_id": None}

def _route_after_duplicate_decider(state: AddIncidentState) -> str:
    return "END" if state["duplicate_status"] == "unique" else "warn_duplicate"

def build_add_incident_graph():
    graph = StateGraph(AddIncidentState)

    graph.add_node("normalize_error",      normalize_error_node)
    graph.add_node("analyze_code",         analyze_code_node)
    graph.add_node("normalize_resolution", normalize_resolution_node)
    graph.add_node("match",                match_node)
    graph.add_node("duplicate_decider",    duplicate_decider_node)
    # graph.add_node("write_incident",       write_incident_node)
    graph.add_node("warn_duplicate",       warn_duplicate_node)

    graph.set_entry_point("normalize_error")

    graph.add_edge("normalize_error",      "analyze_code")
    graph.add_edge("analyze_code",         "normalize_resolution")
    graph.add_edge("normalize_resolution", "match")
    graph.add_edge("match",                "duplicate_decider")
    # graph.add_edge("write_incident",       END)
    graph.add_edge("warn_duplicate",       END)

    graph.add_conditional_edges(
        "duplicate_decider",
        _route_after_duplicate_decider,
        {
            "END":END,
            "warn_duplicate":  "warn_duplicate",
        }
    )

    return graph.compile()

add_incident_pipeline = build_add_incident_graph()

def run_add_incident_pipeline(
    raw_error:      str,
    raw_code:       Optional[str] = None,
    raw_resolution: str = "",
    kb_path:        Optional[str] = None,
) -> AddIncidentState:
    initial_state: AddIncidentState = {
        "raw_error":          raw_error,
        "raw_code":           raw_code,
        "raw_resolution":     raw_resolution,
        "error_message":      "",
        "tags":               [],
        "severity":           "unknown",
        "code_context":       None,
        "resolution":         "",
        "match_results":      None,
        "top_score":          None,
        "duplicate_status":   "unique",
        "duplicate_incident": None,
        "written_id":         None,
        "kb_path":            str(kb_path) if kb_path else None,
    }
    return add_incident_pipeline.invoke(initial_state)