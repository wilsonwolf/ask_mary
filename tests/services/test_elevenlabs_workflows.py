"""Tests for ElevenLabs Workflows API serialization."""

import pytest

from src.services.elevenlabs_workflows import (
    Guardrail,
    NodeType,
    TransitionCondition,
    TransitionEdge,
    WorkflowDefinition,
    WorkflowSubagentNode,
    _serialize_edges,
    _serialize_end_call_node,
    _serialize_guardrails,
    _serialize_node,
    _serialize_subagent_node,
    _serialize_transfer_node,
    build_pipeline_workflow,
    create_workflow_agent,
    update_workflow_agent,
    workflow_to_api_payload,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_guardrail() -> Guardrail:
    """A single guardrail for testing."""
    return Guardrail(
        rule_id="no_medical_advice",
        description="Never give medical advice.",
        enforcement="block",
    )


@pytest.fixture()
def simple_transition() -> TransitionEdge:
    """A single transition edge for testing."""
    return TransitionEdge(
        target_node_id="node_b",
        condition=TransitionCondition.ON_SUCCESS,
        description="Proceed to node B.",
    )


@pytest.fixture()
def subagent_node(
    simple_guardrail: Guardrail,
    simple_transition: TransitionEdge,
) -> WorkflowSubagentNode:
    """A SUBAGENT node with one guardrail and one transition."""
    return WorkflowSubagentNode(
        node_id="node_a",
        name="Disclosure Gate",
        node_type=NodeType.SUBAGENT,
        system_prompt="You are Mary.",
        tools=["capture_consent"],
        guardrails=[simple_guardrail],
        transitions=[simple_transition],
    )


@pytest.fixture()
def transfer_node() -> WorkflowSubagentNode:
    """A TRANSFER node for testing."""
    return WorkflowSubagentNode(
        node_id="transfer_node",
        name="Emergency Transfer",
        node_type=NodeType.TRANSFER,
        system_prompt="Connecting you now.",
    )


@pytest.fixture()
def end_call_node() -> WorkflowSubagentNode:
    """An END_CALL node for testing."""
    return WorkflowSubagentNode(
        node_id="end_call",
        name="End Call",
        node_type=NodeType.END_CALL,
    )


@pytest.fixture()
def two_node_workflow(
    subagent_node: WorkflowSubagentNode,
    end_call_node: WorkflowSubagentNode,
) -> WorkflowDefinition:
    """A minimal workflow with subagent -> end_call."""
    return WorkflowDefinition(
        workflow_id="test-workflow",
        name="Test Workflow",
        entry_node_id="node_a",
        nodes=[subagent_node, end_call_node],
        version="1.0.0",
    )


# ---------------------------------------------------------------------------
# _serialize_guardrails
# ---------------------------------------------------------------------------


class TestSerializeGuardrails:
    """Tests for _serialize_guardrails helper."""

    def test_returns_list_of_dicts(
        self,
        simple_guardrail: Guardrail,
    ) -> None:
        """Each guardrail becomes a dict with required keys."""
        result = _serialize_guardrails([simple_guardrail])
        assert len(result) == 1
        assert result[0]["rule_id"] == "no_medical_advice"
        assert result[0]["description"] == "Never give medical advice."
        assert result[0]["enforcement"] == "block"

    def test_empty_guardrails(self) -> None:
        """Empty input produces empty output."""
        assert _serialize_guardrails([]) == []

    def test_multiple_guardrails(self) -> None:
        """Multiple guardrails serialize correctly."""
        guardrails = [
            Guardrail(rule_id="r1", description="Rule 1"),
            Guardrail(
                rule_id="r2",
                description="Rule 2",
                enforcement="warn",
            ),
        ]
        result = _serialize_guardrails(guardrails)
        assert len(result) == 2
        assert result[1]["enforcement"] == "warn"


# ---------------------------------------------------------------------------
# _serialize_edges
# ---------------------------------------------------------------------------


class TestSerializeEdges:
    """Tests for _serialize_edges helper."""

    def test_returns_list_of_dicts(
        self,
        simple_transition: TransitionEdge,
    ) -> None:
        """Each edge becomes a dict with target, condition, description."""
        result = _serialize_edges([simple_transition])
        assert len(result) == 1
        assert result[0]["target"] == "node_b"
        assert result[0]["condition"] == TransitionCondition.ON_SUCCESS
        assert result[0]["description"] == "Proceed to node B."

    def test_empty_transitions(self) -> None:
        """Empty input produces empty output."""
        assert _serialize_edges([]) == []


# ---------------------------------------------------------------------------
# _serialize_node (routing)
# ---------------------------------------------------------------------------


class TestSerializeSubagentNode:
    """Tests for subagent / condition node serialization."""

    def test_type_is_override_agent(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """SUBAGENT nodes serialize as override_agent type."""
        result = _serialize_subagent_node(subagent_node)
        assert result["type"] == "override_agent"

    def test_label_matches_name(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """Label field matches the node name."""
        result = _serialize_subagent_node(subagent_node)
        assert result["label"] == "Disclosure Gate"

    def test_prompt_in_conversation_config(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """System prompt is nested under conversation_config."""
        result = _serialize_subagent_node(subagent_node)
        prompt = result["conversation_config"]["agent"]["prompt"]["prompt"]
        assert prompt == "You are Mary."

    def test_tools_in_additional_tool_ids(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """Tools list maps to additional_tool_ids."""
        result = _serialize_subagent_node(subagent_node)
        assert result["additional_tool_ids"] == ["capture_consent"]

    def test_edge_order_matches_transitions(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """edge_order contains target node IDs from transitions."""
        result = _serialize_subagent_node(subagent_node)
        assert result["edge_order"] == ["node_b"]

    def test_guardrails_included(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """Guardrails are serialized and included."""
        result = _serialize_subagent_node(subagent_node)
        assert len(result["guardrails"]) == 1
        assert result["guardrails"][0]["rule_id"] == "no_medical_advice"

    def test_condition_node_uses_override_agent(self) -> None:
        """CONDITION nodes also serialize as override_agent."""
        node = WorkflowSubagentNode(
            node_id="cond",
            name="Condition Check",
            node_type=NodeType.CONDITION,
            system_prompt="Check condition.",
        )
        result = _serialize_node(node)
        assert result["type"] == "override_agent"


# ---------------------------------------------------------------------------
# _serialize_transfer_node
# ---------------------------------------------------------------------------


class TestSerializeTransferNode:
    """Tests for TRANSFER node serialization."""

    def test_type_is_standalone_agent(
        self,
        transfer_node: WorkflowSubagentNode,
    ) -> None:
        """TRANSFER nodes serialize as standalone_agent type."""
        result = _serialize_transfer_node(transfer_node)
        assert result["type"] == "standalone_agent"

    def test_transfer_message_from_prompt(
        self,
        transfer_node: WorkflowSubagentNode,
    ) -> None:
        """transfer_message comes from system_prompt."""
        result = _serialize_transfer_node(transfer_node)
        assert result["transfer_message"] == "Connecting you now."

    def test_first_message_enabled(
        self,
        transfer_node: WorkflowSubagentNode,
    ) -> None:
        """enable_transferred_agent_first_message is True."""
        result = _serialize_transfer_node(transfer_node)
        assert result["enable_transferred_agent_first_message"] is True

    def test_label_matches_name(
        self,
        transfer_node: WorkflowSubagentNode,
    ) -> None:
        """Label field matches the node name."""
        result = _serialize_transfer_node(transfer_node)
        assert result["label"] == "Emergency Transfer"


# ---------------------------------------------------------------------------
# _serialize_end_call_node
# ---------------------------------------------------------------------------


class TestSerializeEndCallNode:
    """Tests for END_CALL node serialization."""

    def test_type_is_end_call(
        self,
        end_call_node: WorkflowSubagentNode,
    ) -> None:
        """END_CALL nodes serialize with type end_call."""
        result = _serialize_end_call_node(end_call_node)
        assert result["type"] == "end_call"

    def test_label_matches_name(
        self,
        end_call_node: WorkflowSubagentNode,
    ) -> None:
        """Label field matches the node name."""
        result = _serialize_end_call_node(end_call_node)
        assert result["label"] == "End Call"


# ---------------------------------------------------------------------------
# _serialize_node (dispatch)
# ---------------------------------------------------------------------------


class TestSerializeNodeDispatch:
    """Tests for _serialize_node routing to correct serializer."""

    def test_subagent_routes_correctly(
        self,
        subagent_node: WorkflowSubagentNode,
    ) -> None:
        """SUBAGENT type routes to override_agent serializer."""
        result = _serialize_node(subagent_node)
        assert result["type"] == "override_agent"

    def test_transfer_routes_correctly(
        self,
        transfer_node: WorkflowSubagentNode,
    ) -> None:
        """TRANSFER type routes to standalone_agent serializer."""
        result = _serialize_node(transfer_node)
        assert result["type"] == "standalone_agent"

    def test_end_call_routes_correctly(
        self,
        end_call_node: WorkflowSubagentNode,
    ) -> None:
        """END_CALL type routes to end_call serializer."""
        result = _serialize_node(end_call_node)
        assert result["type"] == "end_call"

    def test_unknown_type_raises_value_error(self) -> None:
        """Unknown node type raises ValueError."""
        node = WorkflowSubagentNode(
            node_id="bad",
            name="Bad Node",
            node_type=NodeType.TOOL,
            system_prompt="",
        )
        with pytest.raises(ValueError, match="Unknown node type"):
            _serialize_node(node)


# ---------------------------------------------------------------------------
# workflow_to_api_payload
# ---------------------------------------------------------------------------


class TestWorkflowToApiPayload:
    """Tests for the top-level workflow serialization."""

    def test_top_level_keys(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Payload contains name, nodes, entry_node_id, metadata."""
        payload = workflow_to_api_payload(two_node_workflow)
        assert payload["name"] == "Test Workflow"
        assert payload["entry_node_id"] == "node_a"
        assert payload["metadata"]["version"] == "1.0.0"

    def test_nodes_keyed_by_id(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Nodes dict is keyed by node_id."""
        payload = workflow_to_api_payload(two_node_workflow)
        assert "node_a" in payload["nodes"]
        assert "end_call" in payload["nodes"]

    def test_node_count_matches(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Number of serialized nodes matches definition."""
        payload = workflow_to_api_payload(two_node_workflow)
        assert len(payload["nodes"]) == 2

    def test_subagent_node_type_in_payload(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Subagent node serializes as override_agent in payload."""
        payload = workflow_to_api_payload(two_node_workflow)
        assert payload["nodes"]["node_a"]["type"] == "override_agent"

    def test_end_call_node_type_in_payload(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """End call node serializes as end_call in payload."""
        payload = workflow_to_api_payload(two_node_workflow)
        assert payload["nodes"]["end_call"]["type"] == "end_call"

    def test_edge_order_in_subagent_payload(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """edge_order in subagent node matches transition targets."""
        payload = workflow_to_api_payload(two_node_workflow)
        node_a = payload["nodes"]["node_a"]
        assert node_a["edge_order"] == ["node_b"]

    def test_guardrails_in_subagent_payload(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Guardrails are present in serialized subagent node."""
        payload = workflow_to_api_payload(two_node_workflow)
        node_a = payload["nodes"]["node_a"]
        assert len(node_a["guardrails"]) == 1


# ---------------------------------------------------------------------------
# build_pipeline_workflow
# ---------------------------------------------------------------------------


class TestBuildPipelineWorkflow:
    """Tests for the full pipeline workflow builder."""

    def test_produces_expected_node_count(self) -> None:
        """Pipeline workflow has 11 nodes (8 gates + 3 terminal)."""
        workflow = build_pipeline_workflow(
            trial_name="Test Trial",
            site_name="Test Site",
            coordinator_phone="+15035551234",
        )
        assert len(workflow.nodes) == 11

    def test_entry_node_is_disclosure(self) -> None:
        """Pipeline starts at the disclosure node."""
        workflow = build_pipeline_workflow(
            trial_name="Test Trial",
            site_name="Test Site",
            coordinator_phone="+15035551234",
        )
        assert workflow.entry_node_id == "disclosure"

    def test_validate_transitions_returns_no_errors(self) -> None:
        """All transitions reference valid node IDs."""
        workflow = build_pipeline_workflow(
            trial_name="Test Trial",
            site_name="Test Site",
            coordinator_phone="+15035551234",
        )
        errors = workflow.validate_transitions()
        assert errors == []

    def test_workflow_serializes_without_error(self) -> None:
        """Pipeline workflow serializes to API payload cleanly."""
        workflow = build_pipeline_workflow(
            trial_name="Test Trial",
            site_name="Test Site",
            coordinator_phone="+15035551234",
        )
        payload = workflow_to_api_payload(workflow)
        assert payload["name"] == "Ask Mary Pipeline — Test Trial"
        assert len(payload["nodes"]) == 11

    def test_all_node_types_present(self) -> None:
        """Pipeline contains subagent, transfer, and end_call nodes."""
        workflow = build_pipeline_workflow(
            trial_name="Test Trial",
            site_name="Test Site",
            coordinator_phone="+15035551234",
        )
        payload = workflow_to_api_payload(workflow)
        node_types = {n["type"] for n in payload["nodes"].values()}
        assert "override_agent" in node_types
        assert "standalone_agent" in node_types
        assert "end_call" in node_types


# ---------------------------------------------------------------------------
# create_workflow_agent / update_workflow_agent stubs
# ---------------------------------------------------------------------------


class TestCreateWorkflowAgent:
    """Tests for the create_workflow_agent stub."""

    @pytest.mark.asyncio()
    async def test_returns_created_status(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Stub returns status=created and workflow_id."""
        result = await create_workflow_agent(two_node_workflow)
        assert result["status"] == "created"
        assert result["workflow_id"] == "test-workflow"


class TestUpdateWorkflowAgent:
    """Tests for the update_workflow_agent stub."""

    @pytest.mark.asyncio()
    async def test_returns_updated_status(
        self,
        two_node_workflow: WorkflowDefinition,
    ) -> None:
        """Stub returns status=updated with agent_id."""
        result = await update_workflow_agent(
            "agent-xyz",
            two_node_workflow,
        )
        assert result["status"] == "updated"
        assert result["agent_id"] == "agent-xyz"
        assert result["workflow_id"] == "test-workflow"
