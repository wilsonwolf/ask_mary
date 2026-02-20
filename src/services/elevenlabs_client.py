"""ElevenLabs Conversational AI service client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from src.services.elevenlabs_workflows import WorkflowDefinition

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
    screening_qs = _build_screening_questions(
        inclusion_criteria,
        exclusion_criteria,
    )

    return (
        f"You are Mary, an AI assistant calling about the "
        f"{trial_name} study at {site_name}.\n\n"
        f"CRITICAL SAFETY RULE: You MUST call the safety_check tool "
        f"before delivering ANY response to the participant. "
        f"No exceptions.\n\n"
        f"INCLUSION CRITERIA:\n{inclusion_text}\n\n"
        f"EXCLUSION CRITERIA:\n{exclusion_text}\n\n"
        f"VISIT SCHEDULE:\n{visits_text}\n\n"
        f"CONVERSATION FLOW — FOLLOW THIS EXACT ORDER:\n"
        f"1. DISCLOSE: Tell the participant you are an automated AI "
        f"assistant and that the call may be recorded. Do NOT skip this.\n"
        f'2. CONSENT: Ask "Is it okay to continue?" Then WAIT. '
        f"Do NOT call capture_consent until the participant has verbally "
        f"responded. Listen for a clear yes, okay, sure, or similar agreement. "
        f"If they say yes, call capture_consent with consent_to_continue=true. "
        f"If they say no, call capture_consent with consent_to_continue=false "
        f"and end the call politely. "
        f"Do NOT assume consent. Do NOT proceed without hearing their answer.\n"
        f"3. VERIFY IDENTITY: Ask for their year of birth (4 digits), wait for answer. "
        f"Then ask for their ZIP code (5 digits), wait for answer. "
        f"You MUST call verify_identity with both values. "
        f"Do NOT call verify_identity with empty values. "
        f"Do NOT proceed until the tool returns verified=true.\n"
        f"4. SCREENING: Ask the following questions ONE AT A TIME. "
        f"Wait for the answer. Call record_screening_answer after EACH "
        f"answer using the EXACT question_key listed below. "
        f"NEVER ask multiple questions in a single turn. "
        f"NEVER combine or batch questions.\n\n"
        f"SCREENING QUESTIONS — use these exact question_key values:\n"
        f"{screening_qs}\n\n"
        f"When ALL questions above are asked, call check_eligibility.\n"
        f"5. ELIGIBILITY RESULT: The check_eligibility tool returns a "
        f"definitive result with eligible=true or eligible=false. "
        f"Read the result and act on it directly. "
        f"YOU decide eligibility — do NOT transfer to a "
        f"coordinator for this. Do NOT second-guess the tool result. "
        f"If eligible=true: congratulate the participant and move to step 6. "
        f"If eligible=false: thank them for their time, let them know they "
        f"do not qualify for this particular study, express empathy, and "
        f"end the call. Do NOT transfer. Do NOT apologize excessively.\n"
        f"6. SCHEDULING: Call check_availability to find open slots. "
        f"Offer the available dates to the participant. When they choose, "
        f"call book_appointment. Confirm the date and time back to them.\n"
        f"7. TRANSPORT: After the appointment is booked, tell the participant "
        f"we offer a complimentary Uber ride to and from the appointment. "
        f"Ask if they would like us to arrange that. If yes, confirm their "
        f"pickup address and call book_transport. If they decline, that is fine.\n"
        f"8. WRAP-UP: Thank the participant. Summarize what was scheduled. "
        f"Let them know a confirmation will be sent. Say goodbye warmly.\n\n"
        f"STRICT ORDERING RULES:\n"
        f"- Complete each step fully before moving to the next.\n"
        f"- NEVER skip a step. NEVER reorder steps.\n"
        f"- If the participant interrupts or asks a question, address it "
        f'briefly, then say "Let me continue where we left off" and '
        f"resume the current step.\n\n"
        f"WARM TRANSFER RULES — READ CAREFULLY:\n"
        f"You can transfer to a human coordinator at {coordinator_phone}. "
        f"But you must ONLY do so in these two situations:\n"
        f"TIER 1 — MEDICAL EMERGENCY: If the participant reports chest pain, "
        f"difficulty breathing, suicidal thoughts, or any life-threatening "
        f"symptom, transfer IMMEDIATELY. Say only: \"I'm connecting you with "
        f'our coordinator right now. Please stay on the line." Do NOT delay.\n'
        f"TIER 2 — PARTICIPANT IS STUCK: If the participant cannot answer "
        f"screening questions after 3 attempts due to confusion or missing "
        f'information, ask: "Would you like me to connect you with a '
        f'coordinator who can help?" ONLY transfer if they say yes.\n'
        f"NEVER transfer for any other reason. Specifically:\n"
        f"- Do NOT transfer to determine eligibility. YOU determine eligibility.\n"
        f"- Do NOT transfer because a screening answer is unclear. Ask again.\n"
        f"- Do NOT transfer because the participant mentions a health condition "
        f"during screening. That is normal — record the answer and continue.\n"
        f"- Do NOT offer to transfer unless Tier 1 or Tier 2 applies.\n\n"
        f"TOOL USAGE — MANDATORY:\n"
        f"- You have server tools available. You MUST call them — do "
        f"NOT try to handle verification, screening, scheduling, or "
        f"booking conversationally.\n"
        f"- capture_consent: call ONLY after participant verbally responds in step 2\n"
        f"- verify_identity: call after collecting BOTH dob_year and zip_code "
        f"(never call with empty values)\n"
        f"- record_screening_answer: call after each screening answer\n"
        f"- check_eligibility: call after all screening answers are recorded\n"
        f"- check_availability: call to find open appointment slots\n"
        f"- book_appointment: call when participant picks a slot\n"
        f"- book_transport: call when participant wants a ride\n"
        f"- check_geo_eligibility: call after confirming participant "
        f"address to verify distance to trial site\n"
        f"- verify_teach_back: call after booking to verify participant "
        f"can repeat date, time, and location\n"
        f"- hold_slot: call to temporarily hold a slot before final booking\n"
        f"- mark_wrong_person: call if you determine you are speaking "
        f"to the wrong person\n"
        f"- mark_call_outcome: call before ending the call to record "
        f"the result (completed, no_answer, voicemail, early_hangup, "
        f"wrong_person, refused, consent_denied)\n"
        f"- safety_check: MANDATORY — call before EVERY response to the "
        f"participant. This is a non-negotiable safety requirement. "
        f"The tool returns instantly (<200ms) and will flag if your "
        f"response needs modification.\n\n"
        f"RULES:\n"
        f"- NEVER share trial details before identity is verified.\n"
        f"- NEVER give medical advice.\n"
        f"- NEVER transfer to a coordinator except per WARM TRANSFER RULES above.\n"
        f"- NEVER assume the participant said something they did not say.\n"
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


def _build_screening_questions(
    inclusion: dict,
    exclusion: dict,
) -> str:
    """Build screening questions with exact question_keys for the agent.

    Groups min_/max_ pairs into a single question (e.g. min_age +
    max_age become one "age" question). Tells the agent exactly which
    ``question_key`` to pass to ``record_screening_answer``.

    Args:
        inclusion: Inclusion criteria dict.
        exclusion: Exclusion criteria dict.

    Returns:
        Formatted string listing each screening question and its key.
    """
    questions: list[str] = []
    seen_bases: set[str] = set()

    for key, _value in inclusion.items():
        base = _get_base_key(key)
        if base in seen_bases:
            continue
        seen_bases.add(base)
        label = base.replace("_", " ")
        partner_keys = [k for k in inclusion if _get_base_key(k) == base]
        constraints = []
        for pk in partner_keys:
            pv = inclusion[pk]
            if "min" in pk:
                constraints.append(f"at least {pv}")
            elif "max" in pk:
                constraints.append(f"at most {pv}")
            else:
                constraints.append(str(pv))
        constraint_text = ", ".join(constraints)
        questions.append(f'- question_key="{base}": Ask about their {label}. [{constraint_text}]')

    for key in exclusion:
        label = key.replace("_", " ")
        questions.append(f'- question_key="{key}": Ask if they have/are {label}. [EXCLUDE if yes]')

    if not questions:
        return "- No screening questions defined"
    return "\n".join(questions)


def _get_base_key(key: str) -> str:
    """Strip min_/max_ prefix or _min/_max suffix from a key.

    Args:
        key: Criterion key.

    Returns:
        Base key name.
    """
    for prefix in ("min_", "max_"):
        if key.startswith(prefix):
            return key[len(prefix) :]
    for suffix in ("_min", "_max"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


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

    async def get_conversation_audio(
        self,
        conversation_id: str,
    ) -> bytes | None:
        """Fetch conversation audio recording.

        Calls GET /v1/convai/conversations/{conversation_id}/audio to
        retrieve the raw audio bytes after a call completes.

        Args:
            conversation_id: ElevenLabs conversation ID.

        Returns:
            Raw audio bytes or None on error.
        """
        url = f"{CONVAI_CONVERSATION_URL}/{conversation_id}/audio"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"xi-api-key": self.api_key},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.content
        except Exception:
            logger.warning(
                "get_conversation_audio_failed",
                extra={"conversation_id": conversation_id},
            )
            return None

    async def create_workflow_agent(
        self,
        workflow: WorkflowDefinition,
    ) -> str:
        """Create an ElevenLabs agent from a workflow definition.

        Delegates to the standalone create_workflow_agent function
        and returns the workflow_id.

        Args:
            workflow: Workflow definition with nodes and edges.

        Returns:
            Agent ID string from ElevenLabs.
        """
        # TODO: Replace with real HTTP client call when API is GA
        from src.services.elevenlabs_workflows import (
            create_workflow_agent as _create,
        )

        result = await _create(workflow)
        return result["workflow_id"]

    async def update_workflow_agent(
        self,
        agent_id: str,
        workflow: WorkflowDefinition,
    ) -> bool:
        """Update an existing ElevenLabs agent with new workflow.

        Delegates to the standalone update_workflow_agent function.

        Args:
            agent_id: Existing ElevenLabs agent ID.
            workflow: Updated workflow definition.

        Returns:
            True if update succeeded.
        """
        # TODO: Replace with real HTTP client call when API is GA
        from src.services.elevenlabs_workflows import (
            update_workflow_agent as _update,
        )

        result = await _update(agent_id, workflow)
        return result["status"] == "updated"

    async def get_workflow_status(
        self,
        agent_id: str,
    ) -> dict:
        """Get the current workflow status for an agent.

        Args:
            agent_id: ElevenLabs agent ID.

        Returns:
            Dict with workflow status and node states.

        Raises:
            NotImplementedError: Pending ElevenLabs workflow API GA.
        """
        raise NotImplementedError(
            "Workflow status pending ElevenLabs API GA",
        )
