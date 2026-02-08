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
    ) -> CallResult:
        """Initiate an outbound call via ElevenLabs Conversational AI.

        Args:
            customer_number: Participant phone number to call.
            dynamic_variables: Dynamic variables for the conversation.
            config_override: Conversation config override.

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
