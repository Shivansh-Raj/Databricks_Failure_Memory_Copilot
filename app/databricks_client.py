"""
databricks_client.py — Thin wrapper around the Databricks Jobs REST API.

Responsibilities
----------------
* Fetch run metadata for a given job run ID
* Retrieve the run output (stdout/stderr) from Databricks
* Surface clear, actionable errors when credentials or connectivity fail

This module deliberately has no similarity logic — it only knows how to
talk to Databricks.

Authentication
--------------
Reads ``DATABRICKS_HOST`` and ``DATABRICKS_TOKEN`` from config (which in turn
reads from environment variables).  Never hard-code credentials.

Offline / test mode
-------------------
If both config values are empty strings the client raises ``DatabricksConfigError``
so callers can fall back to accepting raw error text directly (the CLI does this).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from config import DATABRICKS_HOST, DATABRICKS_TOKEN, TAIL_LINES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DatabricksConfigError(Exception):
    """Raised when host/token are not configured."""


class DatabricksAPIError(Exception):
    """Raised when the Databricks REST API returns a non-2xx response."""


class RunNotFoundError(Exception):
    """Raised when the requested run ID does not exist in the workspace."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DatabricksClient:
    """
    Minimal Databricks Jobs API client for the Failure Memory Copilot.

    Parameters
    ----------
    host:
        Databricks workspace URL, e.g. ``https://adb-<id>.azuredatabricks.net``.
        Defaults to ``DATABRICKS_HOST`` from config.
    token:
        Personal Access Token.  Defaults to ``DATABRICKS_TOKEN`` from config.
    timeout:
        HTTP request timeout in seconds.
    """

    _RUNS_GET_ENDPOINT = "/api/2.1/jobs/runs/get"
    _RUNS_OUTPUT_ENDPOINT = "/api/2.1/jobs/runs/get-output"

    def __init__(
        self,
        host: str = DATABRICKS_HOST,
        token: str = DATABRICKS_TOKEN,
        timeout: int = 30,
    ) -> None:
        host = host.rstrip("/")
        if not host or not token:
            raise DatabricksConfigError(
                "DATABRICKS_HOST and DATABRICKS_TOKEN must be set as environment variables "
                "before using the Databricks client.\n"
                "  export DATABRICKS_HOST=https://<workspace>.azuredatabricks.net\n"
                "  export DATABRICKS_TOKEN=dapi...\n"
                "Alternatively, pass raw error text directly to skip the API fetch."
            )
        self._host = host
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout
        logger.debug("DatabricksClient initialised for host: %s", self._host)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_run_metadata(self, run_id: int | str) -> dict[str, Any]:
        """
        Fetch high-level metadata for a job run.

        Returns
        -------
        dict
            Raw Databricks run object (state, task info, cluster, etc.)
        """
        resp = self._get(self._RUNS_GET_ENDPOINT, params={"run_id": str(run_id)})
        logger.debug("Run %s state: %s", run_id, resp.get("state", {}).get("life_cycle_state"))
        return resp

    def get_run_output(self, run_id: int | str) -> str:
        """
        Fetch the combined stdout/stderr output for a single-task run.

        For multi-task runs this returns the output of the *first* failed task.

        Returns
        -------
        str
            Raw output text (may be empty if the job produced no output).

        Raises
        ------
        RunNotFoundError
            If the run ID is unknown.
        DatabricksAPIError
            For other API-level errors.
        """
        resp = self._get(self._RUNS_OUTPUT_ENDPOINT, params={"run_id": str(run_id)})

        # Single-task runs return output directly
        notebook_result = resp.get("notebook_output", {}).get("result", "")
        logs = resp.get("logs", "")
        error = resp.get("error", "")

        # Combine all available output, favouring error fields
        combined = "\n".join(filter(None, [error, logs, notebook_result]))

        if not combined:
            logger.warning("Run %s returned empty output from the API.", run_id)

        # For multi-task runs, also check tasks array
        if not combined and "tasks" in resp:
            combined = self._extract_task_output(resp["tasks"])

        return combined

    def get_failed_error_text(self, run_id: int | str) -> str:
        """
        High-level helper: fetch run output and return the tail lines.

        This is the single method most callers need.

        Parameters
        ----------
        run_id:
            Databricks job run ID (integer or string).

        Returns
        -------
        str
            Raw output text, truncated to the last ``TAIL_LINES`` lines.
        """
        run_id = int(run_id)
        metadata = self.get_run_metadata(run_id)
        state = metadata.get("state", {})
        life_cycle = state.get("life_cycle_state", "UNKNOWN")
        result_state = state.get("result_state", "UNKNOWN")

        logger.info(
            "Run %d — life_cycle_state: %s  result_state: %s",
            run_id,
            life_cycle,
            result_state,
        )

        if result_state not in ("FAILED", "TIMEDOUT", "CANCELED"):
            logger.warning(
                "Run %d has result_state '%s' (not FAILED). "
                "Proceeding anyway — the output may not contain an error.",
                run_id,
                result_state,
            )

        raw_output = self.get_run_output(run_id)
        lines = raw_output.splitlines()
        return "\n".join(lines[-TAIL_LINES:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self._host}{endpoint}"
        try:
            response = requests.get(url, headers=self._headers, params=params, timeout=self._timeout)
        except requests.exceptions.ConnectionError as exc:
            raise DatabricksAPIError(
                f"Cannot reach Databricks at {self._host}. "
                "Check your network connectivity and DATABRICKS_HOST value."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise DatabricksAPIError(
                f"Request to {url} timed out after {self._timeout}s."
            ) from exc

        if response.status_code == 404:
            raise RunNotFoundError(f"Run not found (HTTP 404) for params {params}.")
        if not response.ok:
            raise DatabricksAPIError(
                f"Databricks API error {response.status_code}: {response.text[:500]}"
            )

        return response.json()

    @staticmethod
    def _extract_task_output(tasks: list[dict[str, Any]]) -> str:
        """Pull error info from the first failed task in a multi-task run."""
        for task in tasks:
            if task.get("state", {}).get("result_state") == "FAILED":
                return task.get("state", {}).get("state_message", "")
        return ""