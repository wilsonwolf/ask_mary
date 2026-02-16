"""ElevenLabs Conversational AI service client."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

CONVAI_API_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
CONVAI_CONVERSATION_URL = "https://api.elevenlabs.io/v1/convai/conversations"


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
    participant_id: str = "",
    trial_id: str = "",
) -> dict:
    """Build dynamic variables for ElevenLabs conversation.

    Args:
        participant_name: Participant display name.
        trial_name: Trial display name.
        site_name: Site display name.
        coordinator_phone: Coordinator phone number.
        participant_id: Participant UUID string.
        trial_id: Trial identifier string.

    Returns:
        Dict of dynamic variable key-value pairs.
    """
    return {
        "participant_name": participant_name,
        "trial_name": trial_name,
        "site_name": site_name,
        "coordinator_phone": coordinator_phone,
        "participant_id": participant_id,
        "trial_id": trial_id,
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
        f"CONVERSATION FLOW:\n"
        f"1. DISCLOSE: Tell the participant you are an automated AI "
        f"assistant and that the call may be recorded.\n"
        f"2. CONSENT: Ask for explicit consent to continue. If they "
        f"refuse, end the call politely.\n"
        f"3. VERIFY IDENTITY: Ask for their year of birth (4 digits) "
        f"and ZIP code (5 digits). You MUST call the verify_identity "
        f"tool with these values. Do NOT proceed until the tool "
        f"returns verified=true.\n"
        f"4. SCREENING: For each inclusion/exclusion criterion, ask "
        f"the relevant question. After each answer, call the "
        f"record_screening_answer tool. When all questions are asked, "
        f"call check_eligibility.\n"
        f"5. SCHEDULING: If eligible, call check_availability to find "
        f"open slots. Offer the participant dates. When they choose, "
        f"call book_appointment.\n"
        f"6. TRANSPORT: Ask if they need a ride. If yes, confirm their "
        f"pickup address and call book_transport.\n\n"
        f"TOOL USAGE — MANDATORY:\n"
        f"- You have server tools available. You MUST call them — do "
        f"NOT try to handle verification, screening, scheduling, or "
        f"booking conversationally.\n"
        f"- verify_identity: call after collecting DOB year and ZIP\n"
        f"- record_screening_answer: call after each screening answer\n"
        f"- check_eligibility: call after all screening answers\n"
        f"- check_availability: call to find open appointment slots\n"
        f"- book_appointment: call when participant picks a slot\n"
        f"- book_transport: call when participant needs a ride\n"
        f"- safety_check: call if participant mentions symptoms or "
        f"distress\n\n"
        f"RULES:\n"
        f"- NEVER share trial details before identity is verified.\n"
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
            "to_number": customer_number,
        }
        client_data: dict = {}
        if dynamic_variables:
            client_data["dynamic_variables"] = dynamic_variables
        if config_override:
            client_data["conversation_config_override"] = config_override
        if client_data:
            payload["conversation_initiation_client_data"] = client_data
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

        conversation_id = data.get(
            "conversation_id",
            data.get("callSid", ""),
        )
        logger.info(
            "outbound_call_initiated",
            extra={
                "conversation_id": conversation_id,
                "call_sid": data.get("callSid"),
            },
        )
        return CallResult(
            conversation_id=conversation_id,
            status=data.get("status", "initiated"),
        )

    async def get_conversation(
        self,
        conversation_id: str,
    ) -> dict:
        """Fetch conversation details including transcript.

        Calls GET /v1/convai/conversations/{conversation_id} to
        retrieve the full transcript after a call completes.

        Args:
            conversation_id: ElevenLabs conversation ID.

        Returns:
            Dict with transcript and conversation metadata.
        """
        url = f"{CONVAI_CONVERSATION_URL}/{conversation_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"xi-api-key": self.api_key},
                    timeout=15.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            logger.warning(
                "get_conversation_failed",
                extra={"conversation_id": conversation_id},
            )
            return {"conversation_id": conversation_id, "transcript": []}
