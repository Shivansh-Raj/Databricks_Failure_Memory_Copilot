"""
config.py — Central configuration for the Databricks Failure Memory Copilot.

All tuneable parameters and environment bindings live here.
Nothing else in the codebase should read environment variables directly.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_BASE_PATH = DATA_DIR / "incidents.json"

# ---------------------------------------------------------------------------
# Databricks connection  (set via environment variables or .env file)
# ---------------------------------------------------------------------------
DATABRICKS_HOST: str = os.getenv("DATABRICKS_HOST", "")          # e.g. https://adb-<workspace-id>.azuredatabricks.net
DATABRICKS_TOKEN: str = os.getenv("DATABRICKS_TOKEN", "")        # Personal Access Token

# ---------------------------------------------------------------------------
# Matcher / similarity settings
# ---------------------------------------------------------------------------

# Number of top results to return
TOP_N_RESULTS: int = 3

# Minimum cosine similarity score to surface a result (0.0 – 1.0)
# Results below this threshold are treated as "no match found"
MIN_SIMILARITY_THRESHOLD: float = 0.15

# TF-IDF vectoriser settings
TFIDF_MAX_FEATURES: int = 5_000        # Vocabulary cap — fine for a JSON knowledge base
TFIDF_NGRAM_RANGE: tuple = (1, 2)      # Unigrams + bigrams catch "heap space", "file not found" etc.
TFIDF_SUBLINEAR_TF: bool = True        # log(1+tf) dampens high-frequency noise terms

# ---------------------------------------------------------------------------
# Log extraction
# ---------------------------------------------------------------------------

# Maximum characters of raw Databricks output to feed into the matcher.
# Keeps vectorisation fast and avoids flooding the TF-IDF space with stack frames.
MAX_ERROR_CHARS: int = 4_000

# Lines at the *end* of a run output to inspect when hunting for the error.
# Databricks task output typically ends with the traceback.
TAIL_LINES: int = 100

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")   # DEBUG | INFO | WARNING | ERROR

# ---------------------------------------------------------------------------
# Groq LLM — error normalization
# ---------------------------------------------------------------------------
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = "llama-3.1-8b-instant"         
GROQ_MODEL_2: str = "llama-3.3-70b-versatile"         
GROQ_TIMEOUT: int = 60
GROQ_MAX_TOKENS: int = 800                 