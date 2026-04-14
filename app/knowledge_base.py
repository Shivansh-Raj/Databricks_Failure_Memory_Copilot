"""
knowledge_base.py — Loads and validates the historical incident store.

Keeps all I/O isolated so the matcher never touches the filesystem directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import KNOWLEDGE_BASE_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"id", "error_message", "resolution", "tags", "severity"}


def _validate_incident(incident: dict[str, Any], index: int) -> bool:
    """Return True if the incident record has all required fields."""
    missing = REQUIRED_FIELDS - incident.keys()
    if missing:
        logger.warning("Incident at index %d is missing fields %s — skipping.", index, missing)
        return False
    if not incident["error_message"].strip():
        logger.warning("Incident at index %d has an empty error_message — skipping.", index)
        return False
    return True


# ---------------------------------------------------------------------------
# Internal Helper
# ---------------------------------------------------------------------------
def _load_raw(kb_path: Path) -> list[dict[str, Any]]:
    """Load the raw JSON array without any validation."""
    with kb_path.open("r", encoding = "utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("incidents.json must contain a JSON array at the top level")
    return raw    
    
def _next_id(incidents: list[dict]) -> str:
    nums = []
    for inc in incidents:
        try:
            nums.append(int(inc["id"].split("-")[1]))
        except (KeyError, IndexError, ValueError):
            pass
        
        return f"INC-{(max(nums, default=0) + 1):03d}"
            

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_incidents(path: Path | str | None = None) -> list[dict[str, Any]]:
    """
    Load and validate incidents from the JSON knowledge base.

    Parameters
    ----------
    path:
        Override the default path from config.  Useful in tests.

    Returns
    -------
    list[dict]
        Valid incident records.  Each record is guaranteed to have
        ``error_message`` and ``resolution`` keys.

    Raises
    ------
    FileNotFoundError
        If the knowledge-base file does not exist.
    ValueError
        If the file contains no valid incidents.
    """
    kb_path = Path(path) if path else KNOWLEDGE_BASE_PATH

    if not kb_path.exists():
        raise FileNotFoundError(
            f"Knowledge base not found at {kb_path}. "
            "Create data/incidents.json or pass an explicit path."
        )

    if not kb_path.exists():
        raise FileNotFoundError(
            f"Knowledge base not found at {kb_path}."
            "Create data/incidents.json or pass an explicit path."
        )
        
    raw = _load_raw(kb_path)
    valid = [inc for i, inc in enumerate(raw) if _validate_incident(inc, i)]

    if not valid:
        raise ValueError("No valid incidents found in the knowledge base.")

    logger.info("Loaded %d / %d valid incidents from %s.", len(valid), len(raw), kb_path)
    return valid


def add_incident(
    record: dict[str, Any], 
    path: Path | str | None = None,
) -> None:
    """
    Append a new enriched incident to the knowledge base JSON file.

    Parameters
    ----------
    record:
        Must contain at minimum: error_message, resolution, tags, severity.
        code_context is optional but included when Groq produced it.
        id is auto-assigned — any id in the record is ignored.
    path:
        Override the default knowledge-base path.

    Returns
    -------
    str
        The auto-assigned ID of the new incident (e.g. 'INC-021').

    Raises
    ------
    ValueError
        If the record is missing required fields.
    """ 
        
    kb_path = Path(path) if path else KNOWLEDGE_BASE_PATH

    # validate before touching the file
    required = {"error_message", "resolution", "tags", "severity"}
    missing = required - record.keys()
    if missing:
        raise ValueError(f"Incident record is missing required fields: {missing}")

    # load raw so deletions don't corrupt ID sequence
    existing = _load_raw(kb_path) if kb_path.exists() else []

    new_id = _next_id(existing)

    # build the record in a consistent field order
    new_record: dict[str, Any] = {
        "id":            new_id,
        "error_message": record["error_message"].strip(),
        "resolution":    record["resolution"].strip(),
        "tags":          record["tags"],
        "severity":      record["severity"],
    }

    # include code_context only if present and non-null
    if record.get("code_context"):
        new_record["code_context"] = record["code_context"]

    existing.append(new_record)

    with kb_path.open("w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=4, ensure_ascii=False)

    logger.info("Added incident '%s' to %s.", new_id, kb_path)
    return new_id