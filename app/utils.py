"""
utils.py — Text cleaning, extraction, and output formatting helpers.

Keeps messy string logic out of the core business modules.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from config import MAX_ERROR_CHARS, TAIL_LINES


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------

# Patterns that commonly signal the start of a meaningful error in Databricks output
_ERROR_ANCHOR_PATTERNS: list[re.Pattern] = [
    re.compile(r"(AnalysisException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(SparkException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(ParseException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(IllegalArgumentException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(FileNotFoundException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(OutOfMemoryError:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(TimeoutException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(java\.lang\.\w+Exception:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(com\.databricks\.\S+Exception:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(StreamingQueryException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(DeltaIllegalStateException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(ConcurrentModificationException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(KafkaException:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(PERMISSION_DENIED:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(RESOURCE_EXHAUSTED:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(Error:.*)", re.IGNORECASE | re.DOTALL),
    re.compile(r"(Exception:.*)", re.IGNORECASE | re.DOTALL),
]

# Noise lines to strip before matching
_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*at\s+[\w\.\$]+\(.*\)\s*$"),          # Java stack frame:  at com.Foo.bar(Foo.java:42)
    re.compile(r"^\s*\.\.\.\s*\d+\s+more\s*$"),            # "... 42 more"
    re.compile(r"^\s*Caused by:.*$"),                       # Duplicate causal chain header (kept in anchor)
    re.compile(r"^\s*$"),                                   # Blank lines
    re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}.*$"),     # Timestamps
    re.compile(r"^\[.*\]\s*(INFO|DEBUG|WARN|ERROR)\s+"),    # Log level prefixes
]


def extract_error_text(raw_output: str) -> str:
    """
    Extract the most relevant error snippet from a raw Databricks run output.

    Strategy
    --------
    1. Take the last ``TAIL_LINES`` lines (errors typically appear at the end).
    2. Try to anchor on a known exception keyword.
    3. Strip Java stack frames and log noise.
    4. Truncate to ``MAX_ERROR_CHARS`` so TF-IDF stays fast.

    Parameters
    ----------
    raw_output:
        The raw stdout/stderr string from a Databricks job run.

    Returns
    -------
    str
        Cleaned error text, ready for similarity matching.
    """
    if not raw_output or not raw_output.strip():
        return ""

    # Work with the tail of the output
    lines = raw_output.splitlines()
    tail = "\n".join(lines[-TAIL_LINES:])

    # Try to anchor on a known exception pattern
    for pattern in _ERROR_ANCHOR_PATTERNS:
        match = pattern.search(tail)
        if match:
            anchored = match.group(1)
            cleaned = _strip_noise(anchored)
            return cleaned[:MAX_ERROR_CHARS]

    # Fallback: strip noise from the whole tail
    cleaned = _strip_noise(tail)
    return cleaned[:MAX_ERROR_CHARS]


def _strip_noise(text: str) -> str:
    """Remove stack frames and log-level prefixes, collapsing blank lines."""
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if any(p.match(line) for p in _NOISE_PATTERNS):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def clean_error_text(text: str) -> str:
    """
    Light normalisation for arbitrary error text supplied directly by the user.

    Does not do anchor detection — use ``extract_error_text`` for raw logs.
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)   # Collapse whitespace
    return text[:MAX_ERROR_CHARS]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_SEPARATOR = "─" * 60


def format_results(results: list[dict[str, Any]], query_text: str) -> str:
    """
    Render the top-N match results as a human-readable string.

    Parameters
    ----------
    results:
        Output of ``Matcher.find_matches()``.
    query_text:
        The cleaned error text that was queried (shown in the header).

    Returns
    -------
    str
        Formatted output suitable for printing to stdout or returning via API.
    """
    lines: list[str] = []
    lines.append(_SEPARATOR)
    lines.append("  DATABRICKS FAILURE MEMORY COPILOT — Results")
    lines.append(_SEPARATOR)

    # Show a brief excerpt of what was queried
    excerpt = textwrap.shorten(query_text, width=120, placeholder=" …")
    lines.append(f"\n  Query error:\n  {excerpt}\n")
    lines.append(_SEPARATOR)

    if not results:
        lines.append("\n  ⚠  No sufficiently similar historical incidents found.")
        lines.append("  Consider adding this failure to the knowledge base.\n")
        lines.append(_SEPARATOR)
        return "\n".join(lines)

    for rank, match in enumerate(results, start=1):
        score_pct = match["score"] * 100
        confidence = _confidence_label(match["score"])
        inc = match["incident"]

        lines.append(f"\n  #{rank}  [{confidence}]  Similarity: {score_pct:.1f}%")
        lines.append(f"  ID: {inc.get('id', 'N/A')}")
        lines.append(f"  Matched error:\n    {textwrap.shorten(inc['error_message'], 100, placeholder=' …')}")
        lines.append(f"\n  Resolution:\n{textwrap.indent(textwrap.fill(inc['resolution'], width=72), '    ')}")
        if inc.get("tags"):
            lines.append(f"\n  Tags: {', '.join(inc['tags'])}")
        lines.append(f"\n{_SEPARATOR}")

    return "\n".join(lines)


def _confidence_label(score: float) -> str:
    """Map a cosine similarity score to a human-readable confidence label."""
    if score >= 0.70:
        return "HIGH confidence"
    if score >= 0.40:
        return "MEDIUM confidence"
    if score >= 0.10:
        return "LOW confidence"
    return "VERY LOW confidence"