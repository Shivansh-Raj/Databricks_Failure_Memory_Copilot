"""
main.py — CLI entry point for the Databricks Failure Memory Copilot.

Usage
-----
# Option A: fetch a failed run from Databricks by run ID
python app/main.py --run-id 123456789

# Option B: pipe in raw error text (no Databricks credentials needed)
python app/main.py --error-text "AnalysisException: unresolved column revenue"

# Option C: read error text from a file
python app/main.py --error-file /path/to/error.log

# Extra flags
--top-n 5                   Return up to 5 results (default: 3)
--threshold 0.15             Override minimum similarity threshold
--knowledge-base /path/to/incidents.json  Use a custom KB file
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is on the path when running `python app/main.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

# from app.databricks_client import DatabricksClient, DatabricksConfigError
from app.knowledge_base import load_incidents
# from app.matcher import Matcher
from app.utils import clean_error_text, extract_error_text, format_results
from config import LOG_LEVEL, MIN_SIMILARITY_THRESHOLD, TOP_N_RESULTS

# Importing Groq Normalizer
# from app.groq_normalizer import normalize

from app.graph import run_pipeline


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot",
        description="Databricks Failure Memory Copilot — find historical fixes for Databricks job failures.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--run-id",
        metavar="RUN_ID",
        help="Databricks job run ID. Requires DATABRICKS_HOST and DATABRICKS_TOKEN env vars.",
    )
    source.add_argument(
        "--error-text",
        metavar="TEXT",
        help="Raw error text or log snippet as a string.",
    )
    source.add_argument(
        "--error-file",
        metavar="PATH",
        type=Path,
        help="Path to a file containing the error log.",
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=TOP_N_RESULTS,
        metavar="N",
        help=f"Number of results to return (default: {TOP_N_RESULTS}).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=MIN_SIMILARITY_THRESHOLD,
        metavar="SCORE",
        help=f"Minimum similarity score 0.0–1.0 (default: {MIN_SIMILARITY_THRESHOLD}).",
    )
    parser.add_argument(
        "--knowledge-base",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a custom incidents.json file.",
    )
    parser.add_argument(
        "--log-level",
        default=LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Log verbosity (default: {LOG_LEVEL}).",
    )
    parser.add_argument(
        "--no-groq",
        action = "store_true",
        help="Skip Groq normalization and match on raw cleaned error text."
    )
    parser.add_argument(
        "--code-file",
        help="Path to .py/.scala/.sql file to analyze alongside the error"
    )
    parser.add_argument(
        "--code-text",
        help="Inline code snippet to analyze alongside the error"
    )
    return parser


def run(args: argparse.Namespace) -> int:
    """
    Core pipeline:
      1. Get raw error text (from Databricks API or user input)
      2. Clean and extract the meaningful error fragment
      3. Load the knowledge base
      4. Run TF-IDF similarity matching
      5. Print formatted results

    Returns
    -------
    int
        Exit code: 0 = success, 1 = error.
    """
    logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Step 1 — Obtain raw error text
    # ------------------------------------------------------------------
    raw_text: str = ""

    if args.run_id:
        # logger.info("Fetching run output for run ID: %s", args.run_id)
        # try:
        #     # ------------------------------------------------------------------    
        #     #  Basically for now The entire databricks_client.py is effectively dead code for you right now.
        #     #  Because you are not using the Databricks API.
        #     # ------------------------------------------------------------------    
        #     client = DatabricksClient()  
        #     raw_text = client.get_failed_error_text(args.run_id)
        # except DatabricksConfigError as exc:
        #     print(f"\n[CONFIG ERROR] {exc}\n", file=sys.stderr)
        #     return 1
        # except Exception as exc:  # noqa: BLE001
        #     print(f"\n[API ERROR] {exc}\n", file=sys.stderr)
        #     return 1
        pass

    elif args.error_text:
        raw_text = args.error_text

    elif args.error_file:
        if not args.error_file.exists():
            print(f"\n[ERROR] File not found: {args.error_file}\n", file=sys.stderr)
            return 1
        raw_text = args.error_file.read_text(encoding="utf-8", errors="replace")

    if not raw_text.strip():
        print("\n[ERROR] No error text could be retrieved. Nothing to match.\n", file=sys.stderr)
        return 1
    
    
    # ------------------------------------------------------------------
    # Step 1b — after parsing args, resolving the code snippet:
    # ------------------------------------------------------------------
    
    code_snippet = None
    if args.code_text:
        code_snippet = args.code_text
    elif args.code_file:
        with open(args.code_file, "r") as f:
            code_snippet = f.read()

    # ------------------------------------------------------------------
    # Step 2 — Extract and clean the error fragment
    # ------------------------------------------------------------------
    if args.run_id:
        # raw_text already has TAIL_LINES applied; just anchor + clean
        error_text = extract_error_text(raw_text)
    else:
        # User-supplied text: light clean (no log-level stripping needed)
        error_text = clean_error_text(raw_text)

    if not error_text:
        logger.warning("Could not extract a meaningful error fragment from the input.")
        error_text = raw_text.strip()[:2000]   # fallback: use whatever we have

    logger.debug("Cleaned error text (%d chars):\n%s", len(error_text), error_text[:300])
    
# ------------------------------------------------------------------
    # Step 2b — Run LangGraph pipeline (optional)
    # ------------------------------------------------------------------
    state = None
    if not args.no_groq:
        logger.info(
            "Running pipeline%s",
            " + code analysis" if code_snippet else "",
        )
        state = run_pipeline(
            raw_error=error_text,
            raw_code=code_snippet,
        )
        error_text = state["error_message"]
        logger.info("Normalized error: %s", error_text)

    # ------------------------------------------------------------------
    # Step 3 — Load knowledge base
    # ------------------------------------------------------------------
    try:
        incidents = load_incidents(args.knowledge_base)
    except (FileNotFoundError, ValueError) as exc:
        print(f"\n[KB ERROR] {exc}\n", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 4 — Match (skipped if graph already matched)
    # ------------------------------------------------------------------
    if state:
        # graph already ran match_node internally — read directly from state
        results = state.get("match_results") or []
    # else:
    #     # --no-groq path — run matcher standalone
    #     matcher = Matcher(incidents)
    #     results = matcher.find_matches(
    #         query=error_text,
    #         top_n=args.top_n,
    #         threshold=args.threshold,
    #     )

    # ------------------------------------------------------------------
    # Step 5 — Output
    # ------------------------------------------------------------------
    if state:
        print(f"\n  Severity : {state['severity']}")
        print(f"  Tags     : {', '.join(state['tags']) if state['tags'] else 'none'}")

        ctx = state.get("code_context")
        if ctx:
            print("\n  ── Code analysis ─────────────────────────────")
            if ctx.get("operation_type"):
                print(f"  Operation : {ctx['operation_type']}")
            if ctx.get("apis_used"):
                print(f"  APIs      : {', '.join(ctx['apis_used'])}")
            if ctx.get("pattern"):
                print(f"  Pattern   : {ctx['pattern']}")
            if ctx.get("likely_hotspot"):
                print(f"  Hotspot   : {ctx['likely_hotspot']}")
            if ctx.get("data_scale_hint"):
                print(f"  Data hint : {ctx['data_scale_hint']}")
        print()

    print(format_results(
        results=results,
        query_text=error_text,
        confidence=state.get("confidence", "high") if state else "high",
        final_resolution=state.get("final_resolution") if state else None,
    ))

    return 0


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    _configure_logging(args.log_level)
    sys.exit(run(args))


if __name__ == "__main__":
    main()