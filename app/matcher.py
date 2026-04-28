"""
matcher.py — TF-IDF + cosine similarity engine.

Compares an incoming error string against every incident in the knowledge base
and returns the top-N closest matches with their similarity scores.

Designed to be stateless between calls so it can be used in web handlers,
CLI tools, and tests without side effects.
"""

# from __future__ import annotations

# import logging
# from typing import Any

# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

# from config import (
#     MIN_SIMILARITY_THRESHOLD,
#     TFIDF_MAX_FEATURES,
#     TFIDF_NGRAM_RANGE,
#     TFIDF_SUBLINEAR_TF,
#     TOP_N_RESULTS,
# )

# logger = logging.getLogger(__name__)


# class Matcher:
#     """
#     TF-IDF–based incident matcher.

#     Usage
#     -----
#     >>> matcher = Matcher(incidents)          # build once, reuse
#     >>> results = matcher.find_matches(error_text)
#     """

#     def __init__(self, incidents: list[dict[str, Any]]) -> None:
#         """
#         Fit the TF-IDF vectoriser on the knowledge-base corpus.

#         Parameters
#         ----------
#         incidents:
#             List of validated incident dicts (must have ``error_message``).
#         """
#         if not incidents:
#             raise ValueError("Cannot build a Matcher with an empty incident list.")

#         self._incidents = incidents
#         self._vectorizer = TfidfVectorizer(
#             max_features=TFIDF_MAX_FEATURES,
#             ngram_range=TFIDF_NGRAM_RANGE,
#             sublinear_tf=TFIDF_SUBLINEAR_TF,
#             strip_accents="unicode",
#             analyzer="word",
#             token_pattern=r"(?u)\b\w+\b",   # include single-char tokens (e.g. 'e' in 'e.g.')
#         )

#         corpus = [self._build_corpus_text(inc) for inc in incidents]
#         self._corpus_matrix = self._vectorizer.fit_transform(corpus)

#         logger.info(
#             "Matcher fitted on %d incidents | vocab size: %d",
#             len(incidents),
#             len(self._vectorizer.vocabulary_),
#         )

#     # ------------------------------------------------------------------
#     # Public API
#     # ------------------------------------------------------------------

#     def find_matches(
#         self,
#         query: str,
#         top_n: int = TOP_N_RESULTS,
#         threshold: float = MIN_SIMILARITY_THRESHOLD,
#         tags: list[str] | None = None,
#         code_context: dict | None = None,
#     ) -> list[dict[str, Any]]:
#         """
#         Find the most similar historical incidents for a given error string.

#         Parameters
#         ----------
#         query:
#             Cleaned error text from the current failing job.
#         top_n:
#             Maximum number of results to return.
#         threshold:
#             Minimum cosine similarity score to include a result.
#         tags:
#             Optional list of tags from Groq normalization — boosts categorical matching.
#         code_context:
#             Optional code_context dict from Groq — boosts structural pattern matching.

#         Returns
#         -------
#         list[dict]
#             Ranked list of matches, each containing:
#             - ``rank``     (int)   1-based rank
#             - ``score``    (float) cosine similarity 0.0–1.0
#             - ``incident`` (dict)  the matching knowledge-base record
#         """
#         if not query or not query.strip():
#             logger.warning("Empty query passed to find_matches — returning no results.")
#             return []

#         query_parts = [query, query, query]
        
#         if tags:
#             tags_str = " ".join(tags)
#             query_parts += [tags_str, tags_str, tags_str]
        
#         if code_context:
#             if code_context.get("operation_type"):
#                 query_parts.append(code_context["operation_type"])
#             if code_context.get("apis_used"):
#                 query_parts.append(" ".join(code_context["apis_used"]))
#             if code_context.get("pattern"):
#                 query_parts.append(code_context["pattern"])
#             if code_context.get("likely_hotspot"):
#                 query_parts.append(code_context["likely_hotspot"])
        
#         enriched_query = " ".join(filter(None, query_parts))
#         query_vec = self._vectorizer.transform([enriched_query])
            
#         scores: np.ndarray = cosine_similarity(query_vec, self._corpus_matrix).flatten()

#         # Get indices sorted by score descending
#         ranked_indices = np.argsort(scores)[::-1]

#         results: list[dict[str, Any]] = []
#         for idx in ranked_indices:
#             score = float(scores[idx])
#             if score < threshold:
#                 break                           # array is sorted; nothing below will qualify
#             if len(results) >= top_n:
#                 break
#             results.append(
#                 {
#                     "rank": len(results) + 1,
#                     "score": round(score, 4),
#                     "incident": self._incidents[idx],
#                 }
#             )

#         logger.debug(
#             "Query matched %d incidents above threshold %.2f (top score: %.4f).",
#             len(results),
#             threshold,
#             float(scores[ranked_indices[0]]) if len(scores) else 0.0,
#         )
#         return results

#     # ------------------------------------------------------------------
#     # Convenience helpers
#     # ------------------------------------------------------------------

#     @property
#     def incident_count(self) -> int:
#         """Number of incidents the matcher was built on."""
#         return len(self._incidents)

#     @property
#     def vocabulary_size(self) -> int:
#         """TF-IDF vocabulary size after fitting."""
#         return len(self._vectorizer.vocabulary_)

#     def _build_corpus_text(self, inc: dict[str, Any]) -> str:
#         parts = []

#         # error_message — 3x weight (primary match signal)
#         error = inc.get("error_message", "")
#         parts += [error, error, error]

#         # resolution — 2x weight (contains fix keywords that reinforce the error type)
#         # resolution = inc.get("resolution", "")
#         # parts += [resolution, resolution]

#         # tags — 3x weight (short categorical labels, very high TF-IDF signal)
#         tags = " ".join(inc.get("tags", []))
#         parts += [tags, tags, tags]

#         # code_context fields — 1x weight (structural pattern signal)
#         ctx = inc.get("code_context") or {}
#         if ctx.get("operation_type"):
#             parts.append(ctx["operation_type"])
#         if ctx.get("apis_used"):
#             parts.append(" ".join(ctx["apis_used"]))
#         if ctx.get("pattern"):
#             parts.append(ctx["pattern"])
#         if ctx.get("likely_hotspot"):
#             parts.append(ctx["likely_hotspot"])

#         return " ".join(filter(None, parts))