"""ElevenLabs Conversational AI service client."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

CONVAI_API_URL = "https://api.elevenlabs.io/v1/convai/conversations/initiate-outbound-call"


@dataclass
class CallResult:
    """Result of an outbound call initiation.

    Attributes:
        conversation_id: ElevenLabs conversation identifier.
        status: Call status string.
    """

    conversation_id: str
    status: str


def build_dynamic_variables(
    *,
    participant_name: str,
    trial_name: str,
    site_name: str,
    coordinator_phone: str,
) -> dict:
    """Build dynamic variables for ElevenLabs conversation.

    Args:
        participant_name: Participant display name.
        trial_name: Trial display name.
        site_name: Site display name.
        coordinator_phone: Coordinator phone number.

    Returns:
        Dict of dynamic variable key-value pairs.
    """
    return {
        "participant_name": participant_name,
        "trial_name": trial_name,
        "site_name": site_name,
        "coordinator_phone": coordinator_phone,
    }


def build_system_prompt(
    *,
    trial_name: str,
    site_name: str,
    coordinator_phone: str,
    inclusion_criteria: dict,
    exclusion_criteria: dict,
    visit_templates: dict,
) -> str:
    """Build the per-call system prompt with trial criteria.

    Args:
        trial_name: Trial display name.
        site_name: Site display name.
        coordinator_phone: Coordinator phone number.
        inclusion_criteria: Trial inclusion criteria.
        exclusion_criteria: Trial exclusion criteria.
        visit_templates: Trial visit templates.

    Returns:
        System prompt string for ElevenLabs conversation.
    """
    inclusion_text = _format_criteria(inclusion_criteria)
    exclusion_text = _format_criteria(exclusion_criteria)
    visits_text = _format_visits(visit_templates)

    return (
        f"You are Mary, an AI assistant calling about the "
        f"{trial_name} study at {site_name}.\n\n"
        f"INCLUSION CRITERIA:\n{inclusion_text}\n\n"
        f"EXCLUSION CRITERIA:\n{exclusion_text}\n\n"
        f"VISIT SCHEDULE:\n{visits_text}\n\n"
        f"RULES:\n"
        f"- You MUST disclose that you are an automated assistant "
        f"and that the call may be recorded.\n"
        f"- You MUST get explicit consent to continue.\n"
        f"- You MUST verify identity (DOB year + ZIP) before "
        f"sharing any trial details.\n"
        f"- NEVER give medical advice.\n"
        f"- If the participant reports symptoms or distress, "
        f"transfer to coordinator at {coordinator_phone}.\n"
        f"- If the participant says STOP, end the call immediately."
    )


def _format_criteria(criteria: dict) -> str:
    """Format criteria dict as bullet list.

    Args:
        criteria: Criteria key-value pairs.

    Returns:
        Formatted string with bullet points.
    """
    if not criteria:
        return "- None specified"
    return "\n".join(f"- {k}: {v}" for k, v in criteria.items())


def _format_visits(visits: dict) -> str:
    """Format visit templates as bullet list.

    Args:
        visits: Visit template key-value pairs.

    Returns:
        Formatted string with bullet points.
    """
    if not visits:
        return "- No visit schedule defined"
    return "\n".join(f"- {k}: {v}" for k, v in visits.items())


def build_conversation_config_override(
    *,
    system_prompt: str,
    first_message: str,
) -> dict:
    """Build conversation config override for ElevenLabs.

    Args:
        system_prompt: Agent system prompt text.
        first_message: First message the agent says.

    Returns:
        Config override dict matching ElevenLabs API schema.
    """
    return {
        "agent": {
            "prompt": {"prompt": system_prompt},
            "first_message": first_message,
        },
    }


class ElevenLabsClient:
    """Client for ElevenLabs Conversational AI outbound calls.

    Attributes:
        api_key: ElevenLabs API key.
        agent_id: ElevenLabs agent identifier.
    """

    def __init__(
        self,
        *,
        api_key: str,
        agent_id: str,
        agent_phone_number_id: str,
    ) -> None:
        """Initialize ElevenLabsClient.

        Args:
            api_key: ElevenLabs API key.
            agent_id: ElevenLabs agent identifier.
            agent_phone_number_id: Agent's outbound phone number ID.
        """
        self.api_key = api_key
        self.agent_id = agent_id
        self.agent_phone_number_id = agent_phone_number_id

    async def initiate_outbound_call(
        self,
        *,
        customer_number: str,
        dynamic_variables: dict | None = None,
        config_override: dict | None = None,
        status_callback: str | None = None,
    ) -> CallResult:
        """Initiate an outbound call via ElevenLabs Conversational AI.

        Args:
            customer_number: Participant phone number to call.
            dynamic_variables: Dynamic variables for the conversation.
            config_override: Conversation config override.
            status_callback: Twilio status callback URL with
                conversation_id for CallSid capture.

        Returns:
            CallResult with conversation ID and status.
        """
        payload: dict = {
            "agent_id": self.agent_id,
            "agent_phone_number_id": self.agent_phone_number_id,
            "customer_number": customer_number,
        }
        if dynamic_variables:
            payload["dynamic_variables"] = dynamic_variables
        if config_override:
            payload["conversation_config_override"] = config_override
        if status_callback:
            payload["status_callback"] = status_callback
            payload["status_callback_method"] = "POST"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                CONVAI_API_URL,
                json=payload,
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info(
            "outbound_call_initiated",
            extra={"conversation_id": data.get("conversation_id")},
        )
        return CallResult(
            conversation_id=data["conversation_id"],
            status=data.get("status", "initiated"),
        )
