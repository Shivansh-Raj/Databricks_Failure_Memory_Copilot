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

REQUIRED_FIELDS = {"error_message", "resolution"}


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

    with kb_path.open("r", encoding="utf-8") as fh:
        raw: list[dict[str, Any]] = json.load(fh)

    if not isinstance(raw, list):
        raise ValueError("incidents.json must contain a JSON array at the top level.")

    valid = [inc for i, inc in enumerate(raw) if _validate_incident(inc, i)]

    if not valid:
        raise ValueError("No valid incidents found in the knowledge base.")

    logger.info("Loaded %d / %d valid incidents from %s.", len(valid), len(raw), kb_path)
    return valid


def add_incident(
    error_message: str,
    resolution: str,
    extra: dict[str, Any] | None = None,
    path: Path | str | None = None,
) -> None:
    """
    Append a new incident to the knowledge base JSON file.

    This is a lightweight helper for the feedback loop (v2).
    It round-trips the JSON file so manual edits are preserved.

    Parameters
    ----------
    error_message:
        The cleaned error text.
    resolution:
        The human-verified resolution that worked.
    extra:
        Optional extra fields (e.g. ``tags``, ``severity``, ``id``).
    path:
        Override the default knowledge-base path.
    """
    kb_path = Path(path) if path else KNOWLEDGE_BASE_PATH

    incidents = load_incidents(kb_path) if kb_path.exists() else []

    new_record: dict[str, Any] = {
        "id": f"INC-{len(incidents) + 1:03d}",
        "error_message": error_message.strip(),
        "resolution": resolution.strip(),
    }
    if extra:
        new_record.update(extra)

    incidents.append(new_record)

    with kb_path.open("w", encoding="utf-8") as fh:
        json.dump(incidents, fh, indent=2, ensure_ascii=False)

    logger.info("Added new incident '%s' to %s.", new_record["id"], kb_path)