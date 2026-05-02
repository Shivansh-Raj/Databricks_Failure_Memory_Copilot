from typing import TypedDict, Optional

from langgraph import graph
from app import groq_normalizer
# from app.matcher import Matcher
# from app.knowledge_base import load_incidents, add_incident
from .rag.retriever import retrieve_candidates
from app.rag.rag_ranker import rank_candidates
from app.utils import _SEPARATOR

from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

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
    
    # rag results
    retrieved_candidates: Optional[list]
    rag_confidence_result: Optional[float]
    
    # to keep track of the incident index\
    current_candidate_index: int
    
    
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


# def match_node(state: IncidentState) -> IncidentState:
#     print(f"\n----------------------- match_node running")
#     incidents = load_incidents()
#     matcher = Matcher(incidents)
#     results = matcher.find_matches(
#         query=state["error_message"],
#         tags=state.get("tags"),
#         code_context=state.get("code_context"),
#     )
#     top_score = results[0]["score"] if results else 0.0
#     print(f"----------------------- match_node — results: {len(results)}, top_score: {top_score}")
#     return {
#         **state,
#         "match_results": results,
#         "top_score":     top_score,
#     }
    
def retrieve_candidates_node(state: IncidentState) -> IncidentState:
    print(_SEPARATOR)
    print("retrieve_candidates_node running")
    print(_SEPARATOR)

    candidates = retrieve_candidates(
        error_text=state["error_message"],
        n_results=5
    )
    # print(_SEPARATOR)
    # print(f"retrieved {len(candidates)} candidates")
    # print(candidates)
    # print(_SEPARATOR)
    return {
        **state,
        "retrieved_candidates": candidates
    }


def rag_rank_candidates_node(state: IncidentState) -> IncidentState:
    print(_SEPARATOR)
    print("rag_rank_candidates_node running")
    print(_SEPARATOR)
    
    resolution, score, best_id = rank_candidates(
        error_text=state["error_message"],
        code_text=state.get("code_context"),
        candidates=state.get("retrieved_candidates", [])
    )
    
    candidates = state.get("retrieved_candidates", [])
    
    best = next((c for c in candidates if c["incident_id"] == best_id), None)
    rest = sorted(
        [c for c in candidates if ["incident_id"] != best_id],
        key = lambda c : c["score"],
        reverse = True
    )
    
    reordered = ([best] + rest) if best else candidates
    
    # print(_SEPARATOR)
    # print(f"RAG ranking completed. Top score: {score}, Resolution: {resolution}, id: {best_id}")
    # print(reordered)
    # print(f"rag confidence score: {score}")
    # print(_SEPARATOR)

    return {
        **state,
        "top_score": score,
        "final_resolution": resolution or "",
        "retrieved_candidates": reordered
    }   

def match_decider_node(state: IncidentState) -> IncidentState:

    print("\n----------------------- match_decider_node running ")
    score = state.get("top_score", 0.0)
    print(f"\n----------------------- match_decider_node running with confidence {score}")
    if float(score) >= 0.6:
        print("----------------------- high confidence match")
        return {
            **state,
            "confidence": "high"
        }
    else:
        print("----------------------- low confidence match — routing to groq_suggest")
        return {
            **state,
            "confidence": "low"
        }

def present_and_confirm(state: IncidentState) -> IncidentState:
    candidates = state["retrieved_candidates"] or []
    index = state.get("current_candidate_index", 0)
    
    if index >= len(candidates):
        print(_SEPARATOR)
        print("No more candidates to confirm")
        print(_SEPARATOR)
        return {
            **state,
            "confidence": "low",
        }
    
    candidate = candidates[index]
    score = candidate["score"] or 0.0
    incident = candidate
    # print(_SEPARATOR)
    # print(candidates)
    # print(_SEPARATOR)
    # print(incident)
    # print(_SEPARATOR)

    severity = incident.get("metadata", {}).get("severity", "unknown")
    tags = incident.get("metadata", {}).get("tags", [])
    def extract_resolution(doc: str):
        if not doc:
            return "Not available"
        
        if "Resolution:" in doc:
            return doc.split("Resolution:")[-1].strip()
        
        return "Not available"


    resolution = extract_resolution(incident.get("document", ""))

    print(_SEPARATOR)
    print(f"📋 MATCH {index + 1} of {len(candidates)}")
    print(f"   Incident ID : {incident['incident_id']}")
    print(f"   Confidence  : {score:.2f}")
    print(f"   Severity    : {severity}")
    print(f"   Tags        : {', '.join(tags) if isinstance(tags, list) else tags}")
    print(f"\n   RESOLUTION:\n   {resolution}")
    print(_SEPARATOR)
    
    if score < 0.4:
        print(f"\n⚠️  Low confidence match ({score:.2f}).")

    # Interrupt and wait for user's input
    user_input = interrupt({
        "prompt": "\nOptions: [y] Accept  [n] Next match  [g] Groq suggestion  [q] Quit\nYour choice: ",
        "candidate_index": index,
        "incident_id": incident.get("incident_id"),
        "score": score
    })

    user_input = user_input.strip().lower()
    
    if user_input == "y":
        print(f"\n✅ Accepted resolution from {incident.get('incident_id')}")

        # Normalize the incident shape to match what format_results expects
        normalized_incident = {
            "id": incident.get("incident_id"),
            "resolution": resolution,           # already extracted above via extract_resolution()
            "tags": tags if isinstance(tags, list) else tags.split(","),
            "error_message": incident.get("document", ""),
        }

        results = [
            {
                "score": score,             
                "incident": normalized_incident,
            }
        ]

        # formatted = format_results(
        #     results=results,
        #     query_text=state.get("error_message", ""),
        #     confidence="accepted",
        #     final_resolution=None,
        # )
        # print(formatted)

        return {
            **state,
            "match_results": results,
            "final_resolution": resolution,
            "confidence": "accepted",
            "current_candidate_index": index,
        }

    elif user_input == "n":
        print(f"\n Skipping to next match...")
        return {
            **state,
            "current_candidate_index": index + 1,
            "confidence": "pending"
        }

    elif user_input == "g":
        print(f"\n Routing to Groq suggestion...")
        return {
            **state,
            "confidence": "low",
            "current_candidate_index": index
        }

    elif user_input == "q":
        print(f"\n Exiting pipeline.")
        return {
            **state,
            "final_resolution": "Exited pipeline.",
            "confidence": "accepted" 
        }

    else:
        print("\n Invalid input. Please enter y / n / g / q")
        return {
            **state,
            "current_candidate_index": index,
            "confidence": "pending"  
        }

def _route_after_decider(state: IncidentState) -> str:
    confidence = state.get("confidence")
    if confidence == "accepted":
        return END
    elif confidence == "low":
        return "groq_suggest"
    elif confidence == "pending":
        return "present_and_confirm"
    else:
        return END
    
    
SUGGEST_PROMPT = """You are an expert Databricks and Apache Spark failure analyst.
No similar historical incident was found for this failure.
Based on the error and code context provided, suggest a resolution.
Return only plain text — no JSON, no markdown."""

def groq_suggest_node(state: IncidentState) -> IncidentState:
    print(_SEPARATOR)
    print("Running GROQ Suggest node")
    print(_SEPARATOR)
    final = "No suggestion available — review error manually.---------------------------------------"
    try:
        user_content = f"ERROR:\n{state['error_message']}"
        if state.get("code_context"):
            ctx = state["code_context"]
            user_content += f"\n\nCODE PATTERN: {ctx.get('pattern')}"
            user_content += f"\nHOTSPOT: {ctx.get('likely_hotspot')}"

        suggestion = groq_normalizer._call_groq(SUGGEST_PROMPT, user_content)
        # print("------------------------------------------")
        # print(suggestion)
        # print("------------------------------------------")
        final = suggestion.strip()
    except Exception as e:
        # logger.warning("groq_suggest failed: %s", e)
        final = "No suggestion available — review error manually."

    return {**state, "final_resolution": final}


from langgraph.graph import StateGraph, END

# def _route_after_decider(state: IncidentState) -> str:
#     print(_SEPARATOR)
#     print(state["top_score"], state["confidence"])
#     print(_SEPARATOR)
#     return "groq_suggest" if state["confidence"] == "low" else END

def build_graph():
    graph = StateGraph(IncidentState)

    graph.add_node("normalize_error",       normalize_error_node)
    graph.add_node("analyze_code",          analyze_code_node)
    graph.add_node("normalize_resolution",  normalize_resolution_node)
    # graph.add_node("match",                 match_node)
    # graph.add_node("match_decider",         match_decider_node)
    graph.add_node("retrieve_candidates", retrieve_candidates_node)
    graph.add_node("rag_rank_candidates", rag_rank_candidates_node)
    graph.add_node("match_decider", match_decider_node)
    graph.add_node("present_and_confirm",   present_and_confirm)
    graph.add_node("groq_suggest",          groq_suggest_node)

    graph.set_entry_point("normalize_error")

    graph.add_edge("normalize_error",      "analyze_code")
    graph.add_edge("analyze_code",         "normalize_resolution")
    # graph.add_edge("normalize_resolution", "match")
    # graph.add_edge("match",                "match_decider")
    graph.add_edge("normalize_resolution", "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "rag_rank_candidates")
    graph.add_edge("rag_rank_candidates",  "present_and_confirm")
    # graph.add_edge("rag_rank_candidates", "match_decider")
    
    graph.add_edge("groq_suggest",         END)

    graph.add_conditional_edges(
        "present_and_confirm",
        _route_after_decider,
        {
            "present_and_confirm": "present_and_confirm",
            "groq_suggest":        "groq_suggest",
            END:                   END
        }
    )

    return graph.compile(checkpointer=MemorySaver())

pipeline = build_graph()

'''
def run_pipeline(
    raw_error: str,
    raw_code: Optional[str] = None,
    raw_resolution: Optional[str] = None,
) -> IncidentState:
    initial_state: IncidentState = {
    "raw_error":              raw_error,
    "raw_code":               raw_code,
    "raw_resolution":         raw_resolution,
    "error_message":          "",
    "tags":                   [],
    "severity":               "unknown",
    "code_context":           None,
    "resolution":             None,
    "top_score":              None,
    "confidence":             "low",
    "final_resolution":       "",
    "retrieved_candidates":   None,
    "rag_confidence_result":  None,
    "current_candidate_index": 0,
    }

    return pipeline.invoke(initial_state)
'''

def run_pipeline(
    raw_error: str,
    raw_code: Optional[str] = None,
    raw_resolution: Optional[str] = None,
) -> IncidentState:
    config = {"configurable" : {"thread_id":"Session1"}}

    initial_state: IncidentState = {
        "raw_error":               raw_error,
        "raw_code":                raw_code,
        "raw_resolution":          raw_resolution,
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
    
    result = pipeline.invoke(initial_state, config=config)
    
    while result.get("__interrupt__"):
        
        print(_SEPARATOR)
        print("pipeline interrupted for user input:")
        interrupt_payload = result.get("__interrupt__")[0]
        user_input = input(interrupt_payload.value.get("prompt"))
        print(_SEPARATOR)
        result = pipeline.invoke(Command(resume = user_input), config=config)
    
    print(_SEPARATOR)
    print("🏁 FINAL RESOLUTION:")
    print(result.get("final_resolution", "No resolution found."))
    print(_SEPARATOR)
    
    return result

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
    # match_results:      Optional[list]
    # top_score:          Optional[float]

    # after duplicate_decider
    duplicate_status:   str           # "unique" or "duplicate"
    duplicate_incident: Optional[dict] # the matching incident if duplicate

    # after write_incident
    written_id:         Optional[str]  # e.g. "INC-021" if written, None if blocked
    kb_path:            Optional[str]  # path to KB file
    
    # Rag based fields
    retrieved_candidates:   Optional[list]
    rag_confidence_result:  Optional[float]
    top_score:              Optional[float]

DUPLICATE_THRESHOLD = 0.8

# REMOVE write_incident_node entirely
# REPLACE with just setting a flag in duplicate_decider

# def duplicate_decider_node(state: AddIncidentState) -> AddIncidentState:
#     top_score = state.get("top_score", 0.0)
#     results = state.get("match_results") or []

#     if top_score >= DUPLICATE_THRESHOLD:
#         duplicate_incident = results[0]["incident"]
#         return {
#             **state,
#             "duplicate_status":   "duplicate",
#             "duplicate_incident": duplicate_incident,
#         }

#     return {
#         **state,
#         "duplicate_status":   "unique",
#         "duplicate_incident": None,
#     }
    
    
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
def rag_duplicate_decider_node(state: AddIncidentState) -> AddIncidentState:
    candidates = retrieve_candidates(
        error_text =state["error_message"],
        n_results=5
    )
    # print(_SEPARATOR)
    # print("DUPLUCATE CANDIDATES:", candidates)
    # print(_SEPARATOR)
    resolution, score, incident_id = rank_candidates(
        error_text=state["error_message"],
        code_text=state.get("code_context"),
        candidates=candidates
    )
    if score >= DUPLICATE_THRESHOLD:
        duplicate_incident = candidates[0] if candidates else None
        return {
            **state,
            "top_score":          score,
            "retrieved_candidates": candidates,
            "duplicate_status":   "duplicate",
            "duplicate_incident": duplicate_incident,
        }
    return {
        **state,
        "top_score":          score,
        "retrieved_candidates": candidates,
        "duplicate_status":   "unique",
        "duplicate_incident": None,
    }
    
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
    # graph.add_node("match",                match_node)
    # graph.add_node("duplicate_decider",    duplicate_decider_node)
    # graph.add_node("write_incident",       write_incident_node)
    graph.add_node("warn_duplicate",       warn_duplicate_node)
    
    # Rag-based duplicate decider
    graph.add_node("rag_duplicate_decider", rag_duplicate_decider_node)

    graph.set_entry_point("normalize_error")

    graph.add_edge("normalize_error",      "analyze_code")
    graph.add_edge("analyze_code",         "normalize_resolution")
    # graph.add_edge("normalize_resolution", "match")
    # graph.add_edge("match",                "duplicate_decider")
    # graph.add_edge("write_incident",       END)
    
    graph.add_edge("normalize_resolution",  "rag_duplicate_decider")
    
    graph.add_edge("warn_duplicate",       END)

    graph.add_conditional_edges(
        "rag_duplicate_decider",
        _route_after_duplicate_decider,
        {
            "END": END,
            "warn_duplicate": "warn_duplicate",
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
        # "match_results":      None,
        "retrieved_candidates" : None,
        "top_score":          None,
        "duplicate_status":   "unique",
        "duplicate_incident": None,
        "written_id":         None,
        "kb_path":            str(kb_path) if kb_path else None,
        
        "rag_confidence_result": None,
    }
    return add_incident_pipeline.invoke(initial_state)