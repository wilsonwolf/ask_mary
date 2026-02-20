"""ElevenLabs Workflows scaffold for pipeline gate migration.

Defines the workflow graph that decomposes the monolithic voice agent
into per-gate subagent nodes, each with focused system prompts,
scoped tools, and safety guardrails. Designed for the ElevenLabs
Agent Workflows API (launched January 2026).

Architecture:
    Disclosure -> Consent -> Identity -> Screening -> Eligibility
    -> Scheduling -> Transport -> WrapUp

Each node is a WorkflowSubagentNode with:
    - Focused system prompt (extracted from monolithic prompt)
    - Scoped tool list (only tools needed for that gate)
    - Guardrail definitions (what the agent must/must not do)
    - Transition edges (where to go next, with conditions)
"""

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class NodeType(enum.StrEnum):
    """ElevenLabs workflow node type."""

    SUBAGENT = "subagent"
    TOOL = "tool"
    CONDITION = "condition"
    TRANSFER = "transfer"
    END_CALL = "end_call"


class TransitionCondition(enum.StrEnum):
    """Condition that triggers a workflow edge transition."""

    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ON_CONSENT_GRANTED = "on_consent_granted"
    ON_CONSENT_DENIED = "on_consent_denied"
    ON_IDENTITY_VERIFIED = "on_identity_verified"
    ON_IDENTITY_FAILED = "on_identity_failed"
    ON_ELIGIBLE = "on_eligible"
    ON_INELIGIBLE = "on_ineligible"
    ON_SAFETY_TRIGGER = "on_safety_trigger"
    ON_STOP_KEYWORD = "on_stop_keyword"
    ON_BOOKING_CONFIRMED = "on_booking_confirmed"
    ON_TRANSPORT_ACCEPTED = "on_transport_accepted"
    ON_TRANSPORT_DECLINED = "on_transport_declined"
    ON_COMPLETE = "on_complete"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Guardrail:
    """Safety boundary enforced at a workflow node.

    Attributes:
        rule_id: Unique identifier for the guardrail.
        description: Human-readable description of the rule.
        enforcement: How the rule is enforced (block, warn, log).
        pattern: Optional regex or keyword pattern to match.
    """

    rule_id: str
    description: str
    enforcement: str = "block"
    pattern: str | None = None


@dataclass(frozen=True)
class TransitionEdge:
    """Directed edge between workflow nodes.

    Attributes:
        target_node_id: ID of the destination node.
        condition: Condition that triggers this transition.
        description: Human-readable description of this edge.
    """

    target_node_id: str
    condition: TransitionCondition
    description: str = ""


@dataclass(frozen=True)
class WorkflowSubagentNode:
    """A subagent node in the ElevenLabs workflow graph.

    Each node represents one pipeline gate with a scoped system
    prompt, limited tool set, and defined guardrails.

    Attributes:
        node_id: Unique identifier for this node.
        name: Human-readable node name.
        node_type: Type of workflow node.
        system_prompt: Focused system prompt for this gate.
        tools: List of tool names available to this subagent.
        guardrails: Safety rules enforced at this node.
        transitions: Outbound edges to other nodes.
        description: Human-readable description of this node.
    """

    node_id: str
    name: str
    node_type: NodeType = NodeType.SUBAGENT
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    guardrails: list[Guardrail] = field(default_factory=list)
    transitions: list[TransitionEdge] = field(default_factory=list)
    description: str = ""


@dataclass
class WorkflowDefinition:
    """Complete workflow graph definition.

    Attributes:
        workflow_id: Unique identifier for this workflow.
        name: Human-readable workflow name.
        entry_node_id: ID of the first node in the graph.
        nodes: All nodes in the workflow.
        version: Workflow version string.
    """

    workflow_id: str
    name: str
    entry_node_id: str
    nodes: list[WorkflowSubagentNode] = field(default_factory=list)
    version: str = "0.1.0"

    def get_node(self, node_id: str) -> WorkflowSubagentNode | None:
        """Look up a node by its ID.

        Args:
            node_id: The node identifier to search for.

        Returns:
            The matching node, or None if not found.
        """
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def validate_transitions(self) -> list[str]:
        """Check that all transition targets reference existing nodes.

        Returns:
            List of error messages for invalid transitions.
        """
        node_ids = {node.node_id for node in self.nodes}
        errors: list[str] = []
        for node in self.nodes:
            for edge in node.transitions:
                if edge.target_node_id not in node_ids:
                    errors.append(
                        f"Node '{node.node_id}' references "
                        f"unknown target '{edge.target_node_id}'"
                    )
        return errors


# ---------------------------------------------------------------------------
# Global guardrails (applied to ALL nodes)
# ---------------------------------------------------------------------------

GLOBAL_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="no_medical_advice",
        description="Never give medical advice, diagnoses, or treatment suggestions.",
        enforcement="block",
        pattern=r"(?i)(you should take|i recommend|my medical advice|"
        r"increase your dose|stop taking|prescribe)",
    ),
    Guardrail(
        rule_id="no_phi_before_identity",
        description="Never share trial details or PHI before identity verification.",
        enforcement="block",
    ),
    Guardrail(
        rule_id="stop_keyword",
        description="If participant says STOP, end the call immediately.",
        enforcement="block",
        pattern=r"(?i)\bstop\b",
    ),
    Guardrail(
        rule_id="emergency_transfer",
        description=(
            "On chest pain, difficulty breathing, suicidal thoughts, "
            "or life-threatening symptoms, transfer immediately."
        ),
        enforcement="block",
        pattern=r"(?i)(chest pain|difficulty breathing|shortness of breath|"
        r"suicidal|self-harm|seizure|severe bleeding|loss of consciousness)",
    ),
    Guardrail(
        rule_id="no_assumptions",
        description="Never assume the participant said something they did not say.",
        enforcement="block",
    ),
]


# ---------------------------------------------------------------------------
# Per-node system prompts
# ---------------------------------------------------------------------------

DISCLOSURE_PROMPT = (
    "You are Mary, an AI assistant making an outreach call about a clinical trial.\n\n"
    "YOUR SOLE TASK: Deliver the mandatory disclosure.\n\n"
    "Say the following clearly and naturally:\n"
    "1. You are an automated AI assistant (not a human).\n"
    "2. This call may be recorded.\n"
    "3. Ask: 'Is it okay to continue?'\n\n"
    "RULES:\n"
    "- Do NOT skip or abbreviate the disclosure.\n"
    "- Do NOT share any trial details yet.\n"
    "- Do NOT discuss the purpose of the call beyond 'a clinical study.'\n"
    "- After asking 'Is it okay to continue?', WAIT for their response.\n"
    "- Do NOT proceed until you hear a clear verbal response.\n"
    "- If they say STOP, end the call immediately.\n"
)

CONSENT_PROMPT = (
    "You are Mary. The participant has just heard the disclosure.\n\n"
    "YOUR SOLE TASK: Capture verbal consent to continue the call.\n\n"
    "Listen for the participant's response to 'Is it okay to continue?'\n"
    "- If they say yes, okay, sure, or similar agreement: call capture_consent "
    "with consent_to_continue=true.\n"
    "- If they say no, not interested, or decline: call capture_consent "
    "with consent_to_continue=false.\n"
    "- If unclear, ask once more: 'Just to confirm, is it okay for us to continue?'\n\n"
    "RULES:\n"
    "- Do NOT assume consent. You MUST hear a clear response.\n"
    "- Do NOT proceed to any other topic.\n"
    "- Do NOT call capture_consent until after the participant responds.\n"
    "- If consent is denied, say 'Thank you for your time. Have a good day.' "
    "and end the call.\n"
)

IDENTITY_PROMPT = (
    "You are Mary. The participant has consented to continue.\n\n"
    "YOUR SOLE TASK: Verify the participant's identity.\n\n"
    "STEPS:\n"
    "1. Ask for their year of birth (4 digits). Wait for their answer.\n"
    "2. Ask for their ZIP code (5 digits). Wait for their answer.\n"
    "3. Call verify_identity with both dob_year and zip_code.\n"
    "4. Wait for the tool result.\n\n"
    "IF verified=true: Say 'Thank you, I've confirmed your identity.'\n"
    "IF verified=false: Say 'I wasn't able to verify your identity. "
    "For your protection, I can't continue this call. Have a good day.' "
    "Then end the call.\n\n"
    "RULES:\n"
    "- Do NOT call verify_identity with empty values.\n"
    "- Do NOT share any trial details until identity is verified.\n"
    "- Do NOT skip this step.\n"
    "- Collect BOTH values before calling the tool.\n"
    "- If they cannot provide either value after 3 attempts, "
    "offer to connect with a coordinator.\n"
)

SCREENING_PROMPT_TEMPLATE = (
    "You are Mary. The participant's identity is verified.\n\n"
    "YOUR SOLE TASK: Ask screening questions ONE AT A TIME and record answers.\n\n"
    "SCREENING QUESTIONS — use these exact question_key values:\n"
    "{screening_questions}\n\n"
    "PROCEDURE:\n"
    "1. Ask ONE question. Wait for the answer.\n"
    "2. Call record_screening_answer with the exact question_key and their answer.\n"
    "3. Move to the next question. Repeat until all questions are asked.\n"
    "4. When ALL questions are answered, call check_eligibility.\n\n"
    "RULES:\n"
    "- NEVER ask multiple questions in a single turn.\n"
    "- NEVER combine or batch questions.\n"
    "- NEVER skip a question.\n"
    "- If an answer is unclear, ask the participant to clarify. Do NOT guess.\n"
    "- If they cannot answer after 3 attempts, offer to connect with a coordinator.\n"
    "- Health conditions mentioned during screening are normal. Record the answer "
    "and continue. Do NOT transfer for this reason.\n"
)

ELIGIBILITY_PROMPT = (
    "You are Mary. Screening is complete.\n\n"
    "YOUR SOLE TASK: Communicate the eligibility result to the participant.\n\n"
    "The check_eligibility tool has returned a result.\n"
    "- If eligible=true: Congratulate the participant warmly and naturally. "
    "Say something like 'Great news — based on your answers, you qualify for "
    "this study!' Then proceed to scheduling.\n"
    "- If eligible=false: Thank them sincerely for their time. Let them know "
    "they don't qualify for this particular study. Express empathy. "
    "End the call politely.\n\n"
    "RULES:\n"
    "- YOU determine eligibility based on the tool result. Do NOT second-guess it.\n"
    "- Do NOT transfer to a coordinator for eligibility decisions.\n"
    "- Do NOT apologize excessively if ineligible.\n"
    "- Do NOT share specific criteria that caused ineligibility.\n"
)

SCHEDULING_PROMPT = (
    "You are Mary. The participant is eligible for the study.\n\n"
    "YOUR SOLE TASK: Schedule the participant's first appointment.\n\n"
    "STEPS:\n"
    "1. Call check_availability to find open appointment slots.\n"
    "2. Present the available dates and times to the participant naturally.\n"
    "3. When they choose a slot, call book_appointment with that slot.\n"
    "4. Confirm the date, time, and location back to them.\n\n"
    "RULES:\n"
    "- Only offer slots returned by check_availability.\n"
    "- If no slots are available, apologize and offer to have a coordinator "
    "follow up when slots open.\n"
    "- Do NOT invent or fabricate appointment times.\n"
    "- Confirm all details back to the participant before finalizing.\n"
)

TRANSPORT_PROMPT = (
    "You are Mary. The appointment is booked.\n\n"
    "YOUR SOLE TASK: Offer complimentary transportation.\n\n"
    "STEPS:\n"
    "1. Tell the participant: 'We offer a complimentary ride to and from "
    "your appointment. Would you like us to arrange that?'\n"
    "2. If yes: Confirm their pickup address. Call book_transport.\n"
    "3. If no: Say 'No problem at all' and move to wrap-up.\n\n"
    "RULES:\n"
    "- Do NOT pressure the participant to accept transportation.\n"
    "- Verify the pickup address before booking.\n"
    "- If they want transport but cannot provide an address now, note it "
    "for coordinator follow-up.\n"
)

WRAP_UP_PROMPT = (
    "You are Mary. Everything is scheduled.\n\n"
    "YOUR SOLE TASK: Summarize and close the call warmly.\n\n"
    "STEPS:\n"
    "1. Thank the participant for their time.\n"
    "2. Summarize what was scheduled (appointment date/time, transport if booked).\n"
    "3. Let them know a confirmation will be sent.\n"
    "4. Say goodbye warmly and naturally.\n\n"
    "RULES:\n"
    "- Keep it concise but warm.\n"
    "- Do NOT introduce new topics.\n"
    "- Do NOT ask additional questions.\n"
)


# ---------------------------------------------------------------------------
# Per-node guardrails (supplementing globals)
# ---------------------------------------------------------------------------

DISCLOSURE_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="must_disclose_ai",
        description="Must identify as an automated AI assistant.",
    ),
    Guardrail(
        rule_id="must_disclose_recording",
        description="Must mention the call may be recorded.",
    ),
    Guardrail(
        rule_id="no_trial_details_before_consent",
        description="Do not share trial name, disease, or details before consent.",
    ),
]

CONSENT_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="no_assumed_consent",
        description="Do not assume consent; wait for explicit verbal agreement.",
    ),
    Guardrail(
        rule_id="must_call_capture_consent",
        description="Must call capture_consent tool, not handle conversationally.",
    ),
]

IDENTITY_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="no_empty_verification",
        description="Do not call verify_identity with empty dob_year or zip_code.",
    ),
    Guardrail(
        rule_id="no_phi_before_verified",
        description="Do not share any trial or health details until verified=true.",
    ),
    Guardrail(
        rule_id="max_three_attempts",
        description="After 3 failed attempts, offer coordinator transfer.",
        enforcement="warn",
    ),
]

SCREENING_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="one_question_at_a_time",
        description="Ask exactly one screening question per turn.",
    ),
    Guardrail(
        rule_id="must_use_tool",
        description="Must call record_screening_answer after each answer.",
    ),
    Guardrail(
        rule_id="no_eligibility_hints",
        description="Do not hint at eligibility before check_eligibility is called.",
    ),
]

ELIGIBILITY_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="trust_tool_result",
        description="Accept the check_eligibility result; do not second-guess.",
    ),
    Guardrail(
        rule_id="no_transfer_for_eligibility",
        description="Do not transfer to coordinator for eligibility decisions.",
    ),
]

SCHEDULING_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="only_real_slots",
        description="Only offer slots returned by check_availability.",
    ),
    Guardrail(
        rule_id="must_confirm_details",
        description="Confirm date, time, and location before finalizing.",
    ),
]

TRANSPORT_GUARDRAILS: list[Guardrail] = [
    Guardrail(
        rule_id="no_pressure",
        description="Do not pressure participant to accept transport.",
        enforcement="warn",
    ),
    Guardrail(
        rule_id="verify_address",
        description="Verify pickup address before calling book_transport.",
    ),
]


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_screening_node_prompt(
    inclusion_criteria: dict[str, str],
    exclusion_criteria: dict[str, str],
) -> str:
    """Build the screening subagent prompt with trial-specific questions.

    Args:
        inclusion_criteria: Trial inclusion criteria key-value pairs.
        exclusion_criteria: Trial exclusion criteria key-value pairs.

    Returns:
        Formatted screening system prompt with question keys.
    """
    from src.services.elevenlabs_client import _build_screening_questions

    questions_text = _build_screening_questions(
        inclusion_criteria,
        exclusion_criteria,
    )
    return SCREENING_PROMPT_TEMPLATE.format(
        screening_questions=questions_text,
    )


def build_pipeline_workflow(
    *,
    trial_name: str,
    site_name: str,
    coordinator_phone: str,
    inclusion_criteria: dict[str, str] | None = None,
    exclusion_criteria: dict[str, str] | None = None,
) -> WorkflowDefinition:
    """Build the complete Ask Mary pipeline workflow.

    Creates a WorkflowDefinition with all pipeline gate nodes,
    their system prompts, tools, guardrails, and transitions.

    Args:
        trial_name: Display name of the trial.
        site_name: Display name of the site.
        coordinator_phone: Coordinator phone for transfers.
        inclusion_criteria: Trial inclusion criteria.
        exclusion_criteria: Trial exclusion criteria.

    Returns:
        Complete WorkflowDefinition ready for API submission.
    """
    inclusion = inclusion_criteria or {}
    exclusion = exclusion_criteria or {}

    screening_prompt = build_screening_node_prompt(inclusion, exclusion)

    safety_transfer_node = WorkflowSubagentNode(
        node_id="safety_transfer",
        name="Emergency Transfer",
        node_type=NodeType.TRANSFER,
        system_prompt=(
            "I'm connecting you with our coordinator right now. "
            "Please stay on the line."
        ),
        description=(
            f"Warm transfer to coordinator at {coordinator_phone} "
            f"for Tier 1 medical emergencies."
        ),
    )

    end_call_node = WorkflowSubagentNode(
        node_id="end_call",
        name="End Call",
        node_type=NodeType.END_CALL,
        description="Graceful call termination.",
    )

    coordinator_node = WorkflowSubagentNode(
        node_id="coordinator_handoff",
        name="Coordinator Handoff",
        node_type=NodeType.TRANSFER,
        system_prompt=(
            "Let me connect you with a coordinator who can help. "
            "Please stay on the line."
        ),
        description=(
            f"Warm transfer to coordinator at {coordinator_phone} "
            f"for Tier 2 stuck participant."
        ),
    )

    disclosure_node = WorkflowSubagentNode(
        node_id="disclosure",
        name="Disclosure",
        system_prompt=DISCLOSURE_PROMPT,
        tools=[],
        guardrails=GLOBAL_GUARDRAILS + DISCLOSURE_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="consent",
                condition=TransitionCondition.ON_SUCCESS,
                description="Disclosure delivered, move to consent.",
            ),
            TransitionEdge(
                target_node_id="end_call",
                condition=TransitionCondition.ON_STOP_KEYWORD,
                description="Participant said STOP.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during disclosure.",
            ),
        ],
        description="Mandatory AI disclosure and recording notice.",
    )

    consent_node = WorkflowSubagentNode(
        node_id="consent",
        name="Consent Capture",
        system_prompt=CONSENT_PROMPT,
        tools=["capture_consent"],
        guardrails=GLOBAL_GUARDRAILS + CONSENT_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="identity",
                condition=TransitionCondition.ON_CONSENT_GRANTED,
                description="Consent granted, proceed to identity.",
            ),
            TransitionEdge(
                target_node_id="end_call",
                condition=TransitionCondition.ON_CONSENT_DENIED,
                description="Consent denied, end call politely.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during consent.",
            ),
        ],
        description="Captures verbal consent to continue the call.",
    )

    identity_node = WorkflowSubagentNode(
        node_id="identity",
        name="Identity Verification",
        system_prompt=IDENTITY_PROMPT,
        tools=["verify_identity"],
        guardrails=GLOBAL_GUARDRAILS + IDENTITY_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="screening",
                condition=TransitionCondition.ON_IDENTITY_VERIFIED,
                description="Identity verified, proceed to screening.",
            ),
            TransitionEdge(
                target_node_id="end_call",
                condition=TransitionCondition.ON_IDENTITY_FAILED,
                description="Identity verification failed, end call.",
            ),
            TransitionEdge(
                target_node_id="coordinator_handoff",
                condition=TransitionCondition.ON_FAILURE,
                description="Participant stuck after 3 attempts.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during identity.",
            ),
        ],
        description="DOB year + ZIP code identity verification gate.",
    )

    screening_node = WorkflowSubagentNode(
        node_id="screening",
        name="Screening Questions",
        system_prompt=screening_prompt,
        tools=["record_screening_answer", "check_eligibility"],
        guardrails=GLOBAL_GUARDRAILS + SCREENING_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="eligibility",
                condition=TransitionCondition.ON_SUCCESS,
                description="All questions answered, eligibility checked.",
            ),
            TransitionEdge(
                target_node_id="coordinator_handoff",
                condition=TransitionCondition.ON_FAILURE,
                description="Participant stuck after repeated attempts.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during screening.",
            ),
        ],
        description=f"Trial-specific screening for {trial_name}.",
    )

    eligibility_node = WorkflowSubagentNode(
        node_id="eligibility",
        name="Eligibility Result",
        system_prompt=ELIGIBILITY_PROMPT,
        tools=[],
        guardrails=GLOBAL_GUARDRAILS + ELIGIBILITY_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="scheduling",
                condition=TransitionCondition.ON_ELIGIBLE,
                description="Participant eligible, proceed to scheduling.",
            ),
            TransitionEdge(
                target_node_id="end_call",
                condition=TransitionCondition.ON_INELIGIBLE,
                description="Participant ineligible, end call.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during eligibility.",
            ),
        ],
        description="Communicates eligibility result to participant.",
    )

    scheduling_node = WorkflowSubagentNode(
        node_id="scheduling",
        name="Appointment Scheduling",
        system_prompt=SCHEDULING_PROMPT,
        tools=["check_availability", "book_appointment"],
        guardrails=GLOBAL_GUARDRAILS + SCHEDULING_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="transport",
                condition=TransitionCondition.ON_BOOKING_CONFIRMED,
                description="Appointment booked, offer transport.",
            ),
            TransitionEdge(
                target_node_id="coordinator_handoff",
                condition=TransitionCondition.ON_FAILURE,
                description="No slots or booking failed.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during scheduling.",
            ),
        ],
        description=f"Schedule first appointment at {site_name}.",
    )

    transport_node = WorkflowSubagentNode(
        node_id="transport",
        name="Transport Offer",
        system_prompt=TRANSPORT_PROMPT,
        tools=["book_transport"],
        guardrails=GLOBAL_GUARDRAILS + TRANSPORT_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="wrap_up",
                condition=TransitionCondition.ON_TRANSPORT_ACCEPTED,
                description="Transport booked, proceed to wrap-up.",
            ),
            TransitionEdge(
                target_node_id="wrap_up",
                condition=TransitionCondition.ON_TRANSPORT_DECLINED,
                description="Transport declined, proceed to wrap-up.",
            ),
            TransitionEdge(
                target_node_id="safety_transfer",
                condition=TransitionCondition.ON_SAFETY_TRIGGER,
                description="Emergency detected during transport.",
            ),
        ],
        description="Offers complimentary Uber ride to appointment.",
    )

    wrap_up_node = WorkflowSubagentNode(
        node_id="wrap_up",
        name="Wrap-Up",
        system_prompt=WRAP_UP_PROMPT,
        tools=[],
        guardrails=GLOBAL_GUARDRAILS,
        transitions=[
            TransitionEdge(
                target_node_id="end_call",
                condition=TransitionCondition.ON_COMPLETE,
                description="Call complete, terminate gracefully.",
            ),
        ],
        description="Summarizes, thanks participant, and ends call.",
    )

    return WorkflowDefinition(
        workflow_id=f"ask-mary-pipeline-{trial_name.lower().replace(' ', '-')}",
        name=f"Ask Mary Pipeline — {trial_name}",
        entry_node_id="disclosure",
        nodes=[
            disclosure_node,
            consent_node,
            identity_node,
            screening_node,
            eligibility_node,
            scheduling_node,
            transport_node,
            wrap_up_node,
            safety_transfer_node,
            coordinator_node,
            end_call_node,
        ],
        version="0.1.0",
    )


def _serialize_guardrails(
    guardrails: list[Guardrail],
) -> list[dict[str, str]]:
    """Serialize guardrails to API-compatible dicts.

    Args:
        guardrails: List of Guardrail objects to serialize.

    Returns:
        List of dicts with rule_id, description, and enforcement.
    """
    return [
        {
            "rule_id": g.rule_id,
            "description": g.description,
            "enforcement": g.enforcement,
        }
        for g in guardrails
    ]


def _serialize_edges(
    transitions: list[TransitionEdge],
) -> list[dict[str, str]]:
    """Serialize transition edges to API-compatible dicts.

    Args:
        transitions: List of TransitionEdge objects to serialize.

    Returns:
        List of dicts with target, condition, and description.
    """
    return [
        {
            "target": t.target_node_id,
            "condition": t.condition,
            "description": t.description,
        }
        for t in transitions
    ]


def _serialize_subagent_node(
    node: WorkflowSubagentNode,
) -> dict[str, Any]:
    """Serialize a SUBAGENT or CONDITION node as override_agent.

    Args:
        node: The workflow node to serialize.

    Returns:
        Dict in ElevenLabs override_agent format.
    """
    return {
        "type": "override_agent",
        "label": node.name,
        "conversation_config": {
            "agent": {"prompt": {"prompt": node.system_prompt}},
        },
        "additional_tool_ids": node.tools,
        "edge_order": [e.target_node_id for e in node.transitions],
        "guardrails": _serialize_guardrails(node.guardrails),
        "edges": _serialize_edges(node.transitions),
    }


def _serialize_transfer_node(
    node: WorkflowSubagentNode,
) -> dict[str, Any]:
    """Serialize a TRANSFER node as standalone_agent.

    Args:
        node: The workflow node to serialize.

    Returns:
        Dict in ElevenLabs standalone_agent format.
    """
    return {
        "type": "standalone_agent",
        "label": node.name,
        "transfer_message": node.system_prompt,
        "enable_transferred_agent_first_message": True,
    }


def _serialize_end_call_node(
    node: WorkflowSubagentNode,
) -> dict[str, Any]:
    """Serialize an END_CALL node.

    Args:
        node: The workflow node to serialize.

    Returns:
        Dict with type end_call and label.
    """
    return {
        "type": "end_call",
        "label": node.name,
    }


def _serialize_node(node: WorkflowSubagentNode) -> dict[str, Any]:
    """Route a node to its type-specific serializer.

    Args:
        node: The workflow node to serialize.

    Returns:
        Dict in the appropriate ElevenLabs API node format.

    Raises:
        ValueError: If node_type is not recognized.
    """
    serializers = {
        NodeType.SUBAGENT: _serialize_subagent_node,
        NodeType.CONDITION: _serialize_subagent_node,
        NodeType.TRANSFER: _serialize_transfer_node,
        NodeType.END_CALL: _serialize_end_call_node,
    }
    serializer = serializers.get(node.node_type)
    if serializer is None:
        msg = f"Unknown node type: {node.node_type}"
        raise ValueError(msg)
    return serializer(node)


def workflow_to_api_payload(
    workflow: WorkflowDefinition,
) -> dict[str, Any]:
    """Serialize a WorkflowDefinition to ElevenLabs API format.

    Args:
        workflow: The workflow definition to serialize.

    Returns:
        Dict matching the ElevenLabs workflow API schema.
    """
    return {
        "name": workflow.name,
        "nodes": {
            node.node_id: _serialize_node(node)
            for node in workflow.nodes
        },
        "entry_node_id": workflow.entry_node_id,
        "metadata": {"version": workflow.version},
    }


async def create_workflow_agent(
    workflow: WorkflowDefinition,
) -> dict[str, Any]:
    """Create an ElevenLabs agent from a workflow definition.

    Builds the API payload and logs it. Actual HTTP call is
    not yet implemented.

    Args:
        workflow: Workflow definition with nodes and edges.

    Returns:
        Dict with status and workflow_id.
    """
    # TODO: Add real HTTP client call to POST /v1/agents
    payload = workflow_to_api_payload(workflow)
    logger.info(
        "create_workflow_agent_payload",
        extra={"payload_keys": list(payload.keys())},
    )
    return {"status": "created", "workflow_id": workflow.workflow_id}


async def update_workflow_agent(
    agent_id: str,
    workflow: WorkflowDefinition,
) -> dict[str, Any]:
    """Update an existing ElevenLabs agent with a new workflow.

    Builds the API payload and logs it. Actual HTTP call is
    not yet implemented.

    Args:
        agent_id: Existing ElevenLabs agent ID.
        workflow: Updated workflow definition.

    Returns:
        Dict with status, agent_id, and workflow_id.
    """
    # TODO: Add real HTTP client call to PATCH /v1/agents/{agent_id}
    payload = workflow_to_api_payload(workflow)
    logger.info(
        "update_workflow_agent_payload",
        extra={
            "agent_id": agent_id,
            "payload_keys": list(payload.keys()),
        },
    )
    return {
        "status": "updated",
        "agent_id": agent_id,
        "workflow_id": workflow.workflow_id,
    }
