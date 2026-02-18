"""No-op Databricks connector stub.

Databricks workspace creation on GCP is blocked by OAuth errors.
All analytics remain in Postgres for the MVP. This stub returns
empty results and logs a warning so callers degrade gracefully.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_STUB_MSG = "Databricks stubbed — returning empty result for %s"


@dataclass
class DatabricksConnector:
    """Stub connector that returns empty data for all queries.

    Attributes:
        host: Placeholder hostname (unused in stub).
    """

    host: str = ""

    async def get_trial(self, trial_id: str) -> dict:
        """Look up trial analytics from Databricks Delta Lake.

        Args:
            trial_id: Trial identifier.

        Returns:
            Empty dict (stubbed).
        """
        logger.warning(_STUB_MSG, f"get_trial({trial_id})")
        return {}

    async def get_participant_ehr(self, mary_id: str) -> dict:
        """Look up participant EHR cross-reference data.

        Args:
            mary_id: Participant HMAC identifier.

        Returns:
            Empty dict (stubbed).
        """
        logger.warning(_STUB_MSG, f"get_participant_ehr({mary_id})")
        return {}

    async def get_conversations_archive(
        self,
        mary_id: str,
    ) -> list[dict]:
        """Retrieve archived conversations for a participant.

        Args:
            mary_id: Participant HMAC identifier.

        Returns:
            Empty list (stubbed).
        """
        logger.warning(
            _STUB_MSG,
            f"get_conversations_archive({mary_id})",
        )
        return []

    async def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Retrieve recent audit log entries.

        Args:
            limit: Maximum entries to return.

        Returns:
            Empty list (stubbed).
        """
        logger.warning(_STUB_MSG, f"get_audit_log(limit={limit})")
        return []
