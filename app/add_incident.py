"""
add_incident.py — CLI tool to add a new enriched incident to the knowledge base.

Usage
-----
# Full flow — error file + code file + resolution
python app/add_incident.py \
  --error-file error.log \
  --code-file job.py \
  --resolution "Increased executor memory and added repartition before join"

# Inline text
python app/add_incident.py \
  --error-text "OutOfMemoryError: Java heap space during shuffle" \
  --resolution "Increase executor memory to 16g"

# Dry run — see what Groq produces without writing
python app/add_incident.py \
  --error-file error.log \
  --resolution "Fixed by..." \
  --dry-run

# Skip Groq — store raw text directly
python app/add_incident.py \
  --error-text "OutOfMemoryError: Java heap space" \
  --resolution "Increase executor memory" \
  --no-groq
"""


from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# from app.groq_normalizer import normalize
from app.graph import run_add_incident_pipeline
from app.knowledge_base import add_incident
from config import KNOWLEDGE_BASE_PATH, LOG_LEVEL

def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
    )

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog = "add-incident",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python add_incident.py --error-text 'AnalysisException' --resolution 'Fix schema'"
    )
    
    #  # --- error source (mutually exclusive, one required) ---
    error_source = parser.add_mutually_exclusive_group(required=True)
    error_source.add_argument(
        "--error-text",
        metavar="TEXT",
        help="Raw error text as a string.",
    )
    error_source.add_argument(
        "--error-file",
        metavar="PATH",
        type=Path,
        help="Path to a file containing the error log.",
    )
    
    # --- optional code snippet ---
    code_source = parser.add_mutually_exclusive_group()
    code_source.add_argument(
        "--code-text",
        metavar="TEXT",
        help="Inline code snippet to analyze alongside the error.",
    )
    code_source.add_argument(
        "--code-file",
        metavar="PATH",
        type=Path,
        help="Path to .py/.scala/.sql file to analyze alongside the error.",
    )
    
    # --- resolution (always required) ---
    resolution_log = parser.add_mutually_exclusive_group(required=True)
    resolution_log.add_argument(
        "--resolution",
        metavar="TEXT",
        help="The fix that resolved this incident.",
    )
    resolution_log.add_argument(
        "--resolution-file",
        metavar="PATH",
        type=Path,
        help="Path to the .txt file containing the resolution.",
    )
    
    # --- optional flags ---
    parser.add_argument(
        "--knowledge-base",
        type=Path,
        default=KNOWLEDGE_BASE_PATH,
        metavar="PATH",
        help=f"Path to incidents.json to append to (default: {KNOWLEDGE_BASE_PATH}).",
    )
    parser.add_argument(
        "--no-groq",
        action="store_true",
        help="Skip Groq normalization — store raw error text directly.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the record without writing to incidents.json.",
    )
    parser.add_argument(
        "--log-level",
        default=LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Log verbosity (default: {LOG_LEVEL}).",
    )

    return parser

def _preview(record: dict, raw_resolution : str, dry_run: bool) -> None:
    """Print a human-readable preview of the record about to be written."""
    label = "── Dry run preview ──" if dry_run else "── New incident preview ──"
    print(f"\n  {label}────────────────────────────")
    print(f"  Severity   : {record.get('severity', 'unknown')}")
    print(f"  Tags       : {', '.join(record.get('tags', [])) or 'none'}")
    print(f"  Error      : {record['error_message'][:120]}")
    print(f"  Raw Resolution : {raw_resolution[:120]}")
    print(f"  Resolution : {record['resolution'][:]}")
    print(f"  Resolution (normalized) : {record['resolution'][:120]}")

    ctx = record.get("code_context")
    if ctx:
        print("\n  ── Code analysis ─────────────────────────────────")
        if ctx.get("operation_type"):
            print(f"  Operation  : {ctx['operation_type']}")
        if ctx.get("apis_used"):
            print(f"  APIs       : {', '.join(ctx['apis_used'])}")
        if ctx.get("pattern"):
            print(f"  Pattern    : {ctx['pattern']}")
        if ctx.get("likely_hotspot"):
            print(f"  Hotspot    : {ctx['likely_hotspot']}")
        if ctx.get("data_scale_hint"):
            print(f"  Data hint  : {ctx['data_scale_hint']}")
    print()
def run(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Step 1 — Resolve error text
    # ------------------------------------------------------------------
    if args.error_text:
        error_text = args.error_text
    else:
        if not args.error_file.exists():
            print(f"\n[ERROR] File not found: {args.error_file}\n", file=sys.stderr)
            return 1
        error_text = args.error_file.read_text(encoding="utf-8", errors="replace")

    if not error_text.strip():
        print("\n[ERROR] Error text is empty.\n", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 2 — Resolve optional code snippet
    # ------------------------------------------------------------------
    code_snippet = None
    if args.code_text:
        code_snippet = args.code_text
    elif args.code_file:
        if not args.code_file.exists():
            print(f"\n[ERROR] Code file not found: {args.code_file}\n", file=sys.stderr)
            return 1
        code_snippet = args.code_file.read_text(encoding="utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Step 3 — Resolve resolution text
    # ------------------------------------------------------------------
    if args.resolution:
        resolution_text = args.resolution.strip()
    else:
        resolution_text = args.resolution_file.read_text().strip()

    if not resolution_text:
        print("\n[ERROR] Resolution text is empty.\n", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 4 — Run pipeline or skip Groq
    # ------------------------------------------------------------------
    if args.no_groq:
        logger.info("Skipping Groq normalization — storing raw text.")

        # build record manually — no graph
        record = {
            "error_message": error_text.strip()[:500],
            "resolution":    resolution_text,
            "tags":          [],
            "severity":      "unknown",
        }
        _preview(record, raw_resolution=resolution_text, dry_run=args.dry_run)

        if args.dry_run:
            print("  Dry run — nothing written.\n")
            return 0

        answer = input("  Append to incidents.json? [y/N]: ").strip().lower()
        if answer != "y":
            print("  Aborted — nothing written.\n")
            return 0

        new_id = add_incident(record, path=args.knowledge_base)
        print(f"\n  Added {new_id} to {args.knowledge_base}\n")
        return 0

    # ------------------------------------------------------------------
    # Step 5 — Run LangGraph add_incident pipeline
    # ------------------------------------------------------------------
    logger.info(
        "Running add_incident pipeline%s",
        " + code analysis" if code_snippet else "",
    )

    state = run_add_incident_pipeline(
        raw_error=error_text,
        raw_code=code_snippet,
        raw_resolution=resolution_text,
        kb_path=args.knowledge_base,
    )

    # ------------------------------------------------------------------
    # Step 6 — Preview
    # ------------------------------------------------------------------
    record = {
        "error_message": state["error_message"],
        "resolution":    state["resolution"],
        "tags":          state["tags"],
        "severity":      state["severity"],
    }
    if state.get("code_context"):
        record["code_context"] = state["code_context"]
# ------------------------------------------------------------------
    # Step 6 — Preview
    # ------------------------------------------------------------------
    _preview(record, raw_resolution=resolution_text, dry_run=args.dry_run)

    if args.dry_run:
        print("  Dry run — nothing written.\n")
        return 0

    # ------------------------------------------------------------------
    # Step 7 — Warn if duplicate
    # ------------------------------------------------------------------
    if state.get("duplicate_status") == "duplicate":
        dup = state.get("duplicate_incident", {})
        print(f"\n  ⚠  Similar incident already exists (similarity: {state['top_score']*100:.1f}%)")
        print(f"  ID        : {dup.get('id')}")
        print(f"  Error     : {dup.get('error_message', '')[:100]}")
        print(f"  Resolution: {dup.get('resolution', '')[:100]}")
        answer = input("\n  Add anyway? [y/N]: ").strip().lower()
        if answer != "y":
            print("  Aborted — nothing written.\n")
            return 0

    # ------------------------------------------------------------------
    # Step 8 — Confirm and write (both unique and force-duplicate paths)
    # ------------------------------------------------------------------
    answer = input("\n  Append to incidents.json? [y/N]: ").strip().lower()
    if answer != "y":
        print("  Aborted — nothing written.\n")
        return 0

    new_id = add_incident(record, path=args.knowledge_base)
    print(f"\n  Added {new_id} to {args.knowledge_base}\n")
    return 0

def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    _configure_logging(args.log_level)
    sys.exit(run(args))


if __name__ == "__main__":
    main()