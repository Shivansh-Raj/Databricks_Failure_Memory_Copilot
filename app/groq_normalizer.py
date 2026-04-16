"""
groq_normalizer.py — Uses Groq LLM to normalize raw error text into
a structured format: clean error_message, tags, and severity.
"""

from __future__ import annotations

import json
import logging
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT, GROQ_MAX_TOKENS

logger = logging.getLogger(__name__)

# SYSTEM_PROMPT = """
# You are an expert Databricks and Apache Spark engineer.
# Your job is to analyze a raw error message and return a structured JSON object with exactly these three fields:

# - "error_message": a clean, normalized one or two sentence summary of the core error. 
#   Strip memory addresses, line numbers, file paths, and run-specific IDs. 
#   Keep exception class names and the key reason for failure.
# - "tags": a list of 2-4 lowercase string tags describing the error category.
#   Choose from or model after: delta, schema, oom, memory, shuffle, dbfs, file, 
#   sql, syntax, streaming, kafka, checkpoint, cluster, timeout, permissions, 
#   secrets, api, udf, null, hive, metastore, driver, concurrent, corruption.
# - "severity": one of "low", "medium", "high", or "critical".
#   Use "critical" for data loss or pipeline-blocking issues,
#   "high" for job failures requiring immediate action,
#   "medium" for recoverable or configuration issues,
#   "low" for warnings or minor misconfigurations.

# Return ONLY valid JSON. No explanation, no markdown, no extra text.
# """

# SYSTEM_PROMPT = """ You are an expert Databricks and Apache Spark failure analyst.
# You will be given a Databricks job failure. This may include:
# - An error log (always provided)
# - A code snippet (optionally provided)

# Your job is to return a structured JSON object that normalizes and abstracts the failure for future similarity matching.

# STRICT RULES:
# - Strip all memory addresses, line numbers, and stack frame paths
# - Keep exception class names (they are meaningful signals)
# - Do NOT extract variable names, column names, table names, or any business logic from the code
# - Only extract structural patterns — what operations, what data flow, what API misuse caused the failure
# - If no code is provided, return null for all code_context fields
# - Return ONLY valid JSON, no explanation, no markdown, no backticks

# Return this exact structure:
# {
#   "error_message": "<normalized exception class and cause, no addresses or line numbers>",
#   "tags": ["<2-4 lowercase category labels like oom, shuffle, join, permissions>"],
#   "severity": "<one of: low | medium | high | critical>",
#   "code_context": {
#     "operation_type": "<primary Spark/SQL operation involved e.g. join, groupBy, collect, write>",
#     "apis_used": ["<list of Spark/SQL APIs on the hot path>"],
#     "pattern": "<one sentence describing WHY the specific API usage or data flow pattern 
#              caused the failure — name the wrong API or missing operation explicitly>",
#     "data_scale_hint": "<any structural hint about data size or partitioning, or null if unknown>",
#     "likely_hotspot": "<the specific operation or line pattern most likely responsible, or null if unknown>"
#   }
# }"""

# ---------------------------------------------------------------------------
# Prompt 1 — Error normalization only
# ---------------------------------------------------------------------------

_ERROR_NORMALIZATION_PROMPT = """You are an expert Databricks and Apache Spark failure analyst.

You will be given a raw Databricks job error log.

Your job is to normalize and abstract the error for future similarity matching.

STRICT RULES:
- Strip all memory addresses, line numbers, and stack frame paths
- Keep exception class names — they are meaningful signals
- Return ONLY valid JSON, no explanation, no markdown, no backticks

Return this exact structure:
{
  "error_message": "<normalized exception class and cause, no addresses or line numbers>",
  "tags": ["<2-4 lowercase category labels e.g. oom, shuffle, join, permissions, dlt, schema>"],
  "severity": "<one of: low | medium | high | critical>"
}"""

# ---------------------------------------------------------------------------
# Prompt 2 — Code analysis only
# ---------------------------------------------------------------------------

_CODE_ANALYSIS_PROMPT = """You are an expert Databricks and Apache Spark failure analyst.

You will be given:
- A normalized error message describing what failed
- The actual job code that produced the failure

Your job is to analyze the structural pattern in the code that caused the error.

STRICT RULES:
- Do NOT extract variable names, column names, table names, or any business logic
- Only identify structural patterns — wrong API usage, missing operations, incorrect data flow
- Name the specific wrong API or missing operation explicitly — do not just restate the error
- Return ONLY valid JSON, no explanation, no markdown, no backticks

BAD pattern example  : "reference to a non-existent table" — too vague, restates the error
GOOD pattern example : "spark.table() used inside a DLT pipeline instead of dlt.read(), bypassing the DLT dependency graph"

Return this exact structure:
{
  "operation_type": "<primary Spark/SQL operation involved e.g. join, groupBy, collect, write, read>",
  "apis_used": ["<Spark/SQL APIs on the hot path that caused the failure>"],
  "pattern": "<one sentence: name the wrong API or missing operation and why it fails structurally>",
  "data_scale_hint": "<structural hint about data size or partitioning, or null if not applicable>",
  "likely_hotspot": "<the specific API call or operation most responsible for the failure, or null>"
}"""


# ---------------------------------------------------------------------------
# Prompt 2 — Resolution Normalization
# ---------------------------------------------------------------------------
_RESOLUTION_NORMALIZATION_PROMPT = """You are an expert Databricks and Apache Spark failure analyst.

You will be given a resolution description for a Databricks job failure.

Your job is to rewrite it into a consistent structured prose format for similarity matching.

STRICT RULES:
- Do NOT remove any technical information — every cause and fix must be preserved
- Do NOT summarize or shorten — normalize the structure, not the content
- Remove bullet points, numbered lists, and markdown formatting
- Write in plain prose with two clear parts: root cause, then fix
- Keep all API names, configuration names, and technical terms exactly as-is
- Return ONLY the normalized resolution as plain text — no JSON, no explanation

Output format:
Root cause: <one or two sentences describing why the failure occurs structurally>.
Fix: <one or two sentences describing the concrete steps to resolve it>.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Export it as an environment variable."
        )
    
    return Groq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT)

def _call_groq(system_prompt: str, user_content: str) -> str:
    """Single reusable Groq call. Returns raw response string."""
    client = _get_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=GROQ_MAX_TOKENS,
        messages = [
            {"role":"system", "content": system_prompt},
            {"role":"user", "content": user_content},
        ]
    )
    return response.choices[0].message.content.strip()

def _fallback(error_text: str) -> dict:
    return {
        "error_message": error_text[:500],
        "tags": [],
        "severity": "unknown",
        "code_context": _null_code_context(),   # ← new field
    }
    
def _null_code_context() -> dict:
    return {
        "operation_type": None,
        "apis_used": [],
        "pattern": None,
        "data_scale_hint": None,
        "likely_hotspot": None,
    }


# ---------------------------------------------------------------------------
# Public APIs
# ---------------------------------------------------------------------------

def normalize_error(error_text: str) -> str:
    """
    Call 1 — normalize raw error text into error_message, tags, severity.
    Falls back to safe defaults on any failure — never raises.
    """
    try:
        raw = _call_groq(
            system_prompt=_ERROR_NORMALIZATION_PROMPT,
            user_content=f"Error Log : \n {error_text}"
        )
        logger.debug("Groq error normalization response : %s", raw)
        
        normalized = json.loads(raw)
        
        for key in ("error_message", "tags", "severity"):
            if key not in normalized:
                raise ValueError(f"Groq response missing key: {key}")
        
        logger.info(
            "Normalized — severity: %s  tags: %s",
            normalized["severity"],
            normalized["tags"],
        )
        return normalized
    
    except json.JSONDecodeError as e:
        logger.warning("Groq returned invalid JSON: %s — falling back to raw text.", e)
        return _fallback(error_text)

    except Exception as e:
        logger.warning("Groq API call failed: %s — falling back to raw text.", e)
        return _fallback(error_text)
    
def analyze_code(error_message: str, code_snippet: str) -> dict:
    """ 
    Call 2 — analyze code structure given the normalized error message.
    Only called when a code snippet is provided.
    Falls back to null code_context on any failure — never raises.
    """
    try:
        user_content = (
            f"NORMALIZED ERROR:\n {error_message}\n\n"
            f"CODE SNIPPET:\n{code_snippet}"
        )
        
        
        raw = _call_groq(
            system_prompt=_CODE_ANALYSIS_PROMPT,
            user_content=user_content
        )
        
        logger.debug("Groq code analysis response: %s", raw)
        
        ctx = json.loads(raw)
        
        # Fill any missing sub-keys rather than crash dowenstream
        null_ctx = _null_code_context()
        for sub_key in null_ctx:
            ctx.setdefault(sub_key, null_ctx[sub_key]) 
        
        return ctx
    
    except json.JSONDecodeError as e:
        logger.warning("Groq code analysis returned invalid JSON: %s — falling back.", e)
        return _null_code_context()
    except Exception as e:
        logger.warning("Groq code analysis failed: %s — falling back.", e)
        return _null_code_context()
               
def normalize_resolution(resolution_text: str) -> str:
    """
    Call 3 — normalize resolution prose into consistent structure.
    Falls back to raw resolution text on any failure — never raises.
    """
    try:
        raw = _call_groq(
            system_prompt=_RESOLUTION_NORMALIZATION_PROMPT,
            user_content=f"RESOLUTION:\n{resolution_text}",
        )
        logger.debug("Groq resolution normalization response: %s", raw)
        logger.info("Resolution normalized successfully.")
        return raw.strip()

    except Exception as e:
        logger.warning("Groq resolution normalization failed: %s — using raw text.", e)
        return resolution_text.strip()        

"""
NOTE: The normalize() orchestrator has been removed.
Orchestration is now handled by app/graph.py via LangGraph.
The three functions above are called directly by graph nodes.
"""

# def normalize(
#         raw_error: str, 
#         code_snippet : str | None = None,
#         resolution_text : str | None = None
#     ) -> dict:
#     """
#     Public entry point. Orchestrates both calls and returns a merged dict.

#     Always makes Call 1.
#     Only makes Call 2 if code_snippet is provided.

#     Returns
#     -------
#     dict with keys: error_message, tags, severity, code_context
#     """
#     # Call 1 - always
#     result = normalize_error(raw_error)
    
#     # Call 2 - only if code was provided
#     if code_snippet:
#         result["code_context"] = analyze_code(
#             error_message=result["error_message"],
#             code_snippet=code_snippet
#         )
#     else:
#         result["code_context"] = None 

#     # Call 3 — only if resolution was provided (add_incident flow)
#     if resolution_text:
#         result["resolution"] = normalize_resolution(resolution_text)

#     return result