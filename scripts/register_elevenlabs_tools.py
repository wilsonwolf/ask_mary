#!/usr/bin/env python3
"""Register server tools on the ElevenLabs agent.

Two-step process:
1. Create each tool via POST /v1/convai/tools
2. Attach tool IDs to the agent via PATCH /v1/convai/agents/{agent_id}

Reads ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, and PUBLIC_BASE_URL
from environment variables.

Usage:
    export ELEVENLABS_API_KEY=...
    export ELEVENLABS_AGENT_ID=...
    export PUBLIC_BASE_URL=https://your-cloud-run-url.run.app
    python scripts/register_elevenlabs_tools.py
"""

import json
import os
import sys

import httpx

TOOLS_URL = "https://api.elevenlabs.io/v1/convai/tools"
AGENTS_URL = "https://api.elevenlabs.io/v1/convai/agents"
WEBHOOK_PATH = "/webhooks/elevenlabs/server-tool"


def _build_tool_config(
    name: str,
    description: str,
    properties: dict,
    required: list[str],
    base_url: str,
) -> dict:
    """Build a tool_config payload for POST /v1/convai/tools.

    Args:
        name: Tool name.
        description: Tool description.
        properties: Request body schema properties.
        required: Required property names.
        base_url: Public base URL for the webhook.

    Returns:
        tool_config dict for the create tool API.
    """
    return {
        "type": "webhook",
        "name": name,
        "description": description,
        "api_schema": {
            "url": f"{base_url}{WEBHOOK_PATH}",
            "method": "POST",
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "constant_value": name,
                    },
                    **properties,
                },
                "required": ["tool_name", *required],
            },
        },
    }


def build_all_tool_configs(base_url: str) -> list[dict]:
    """Build all 7 tool configs.

    Args:
        base_url: Public base URL for webhooks.

    Returns:
        List of tool_config dicts.
    """
    return [
        _build_tool_config(
            name="verify_identity",
            description=(
                "Verify participant identity using date of birth "
                "year and ZIP code"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "dob_year": {
                    "type": "string",
                    "description": "Four-digit birth year",
                },
                "zip_code": {
                    "type": "string",
                    "description": "Five-digit ZIP code",
                },
            },
            required=["participant_id", "dob_year", "zip_code"],
            base_url=base_url,
        ),
        _build_tool_config(
            name="record_screening_answer",
            description=(
                "Record participant's answer to a screening question"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "trial_id": {
                    "type": "string",
                    "dynamic_variable": "trial_id",
                },
                "question_key": {
                    "type": "string",
                    "description": "Screening question identifier",
                },
                "answer": {
                    "type": "string",
                    "description": "Participant's answer",
                },
            },
            required=[
                "participant_id",
                "trial_id",
                "question_key",
                "answer",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="check_eligibility",
            description=(
                "Determine if participant is eligible for the trial"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "trial_id": {
                    "type": "string",
                    "dynamic_variable": "trial_id",
                },
            },
            required=["participant_id", "trial_id"],
            base_url=base_url,
        ),
        _build_tool_config(
            name="check_availability",
            description=(
                "Find available appointment slots for preferred dates"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "trial_id": {
                    "type": "string",
                    "dynamic_variable": "trial_id",
                },
                "preferred_dates": {
                    "type": "string",
                    "description": (
                        "Comma-separated ISO dates (YYYY-MM-DD)"
                    ),
                },
            },
            required=[
                "participant_id",
                "trial_id",
                "preferred_dates",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="book_appointment",
            description=(
                "Book an appointment with 12-hour confirmation window"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "trial_id": {
                    "type": "string",
                    "dynamic_variable": "trial_id",
                },
                "slot_datetime": {
                    "type": "string",
                    "description": "ISO datetime for the appointment slot",
                },
                "visit_type": {
                    "type": "string",
                    "description": (
                        "Visit type: screening, baseline, or follow_up"
                    ),
                },
            },
            required=[
                "participant_id",
                "trial_id",
                "slot_datetime",
                "visit_type",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="book_transport",
            description=(
                "Book a ride for the participant to their appointment"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "appointment_id": {
                    "type": "string",
                    "description": "Appointment UUID",
                },
                "pickup_address": {
                    "type": "string",
                    "description": "Full pickup street address",
                },
            },
            required=[
                "participant_id",
                "appointment_id",
                "pickup_address",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="safety_check",
            description=(
                "Run safety gate check on agent response before sending"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "response": {
                    "type": "string",
                    "description": "Agent response text to safety-check",
                },
                "trial_id": {
                    "type": "string",
                    "dynamic_variable": "trial_id",
                },
                "context": {
                    "type": "string",
                    "description": "Recent conversation context",
                },
            },
            required=["participant_id", "response"],
            base_url=base_url,
        ),
    ]


def _extract_tool_id(data: dict) -> str:
    """Extract tool id from possible ElevenLabs response shapes."""
    return (
        data.get("tool_id")
        or data.get("id")
        or data.get("tool", {}).get("tool_id")
        or data.get("tool", {}).get("id")
        or ""
    )


def create_tool(
    tool_config: dict,
    headers: dict,
) -> str | None:
    """Create a single tool via POST /v1/convai/tools.

    Args:
        tool_config: Tool configuration dict.
        headers: API headers with xi-api-key.

    Returns:
        Tool ID string, or None on failure.
    """
    payload = {"tool_config": tool_config}
    response = httpx.post(
        TOOLS_URL,
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    if response.status_code in (200, 201):
        data = response.json()
        tool_id = _extract_tool_id(data)
        if tool_id:
            print(f"  Created: {tool_config['name']} -> {tool_id}")
            return tool_id

        print(f"  Created: {tool_config['name']} -> (missing tool id)")
        print("    Response keys:", ", ".join(sorted(data.keys())))
        print(f"    Raw: {json.dumps(data)[:400]}")
        return None

    print(f"  FAILED: {tool_config['name']} ({response.status_code})")
    print(f"    {response.text[:300]}")
    return None


def attach_tools_to_agent(
    agent_id: str,
    tool_ids: list[str],
    headers: dict,
) -> bool:
    """Attach tool IDs to agent via PATCH.

    Args:
        agent_id: ElevenLabs agent ID.
        tool_ids: List of tool ID strings.
        headers: API headers with xi-api-key.

    Returns:
        True on success.
    """
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": tool_ids,
                },
            },
        },
    }
    url = f"{AGENTS_URL}/{agent_id}"
    response = httpx.patch(
        url, json=payload, headers=headers, timeout=30.0,
    )
    if response.status_code == 200:
        return True
    print(f"  Attach failed: {response.status_code}")
    print(f"    {response.text[:300]}")
    return False


def main() -> None:
    """Create tools and attach them to the agent."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID", "")
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

    if not api_key or not agent_id or not base_url:
        print(
            "ERROR: Set ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, "
            "and PUBLIC_BASE_URL environment variables.",
        )
        sys.exit(1)

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    configs = build_all_tool_configs(base_url)
    print(f"Creating {len(configs)} tools...")
    print(f"Webhook URL: {base_url}{WEBHOOK_PATH}\n")

    tool_ids: list[str] = []
    for config in configs:
        tool_id = create_tool(config, headers)
        if tool_id:
            tool_ids.append(tool_id)

    if not tool_ids:
        print("\nERROR: No tools created.")
        sys.exit(1)

    print(f"\nAttaching {len(tool_ids)} tools to agent {agent_id}...")
    if attach_tools_to_agent(agent_id, tool_ids, headers):
        print("Done! Tools attached successfully.")
    else:
        print("ERROR: Failed to attach tools to agent.")
        print(f"Tool IDs to attach manually: {json.dumps(tool_ids)}")
        sys.exit(1)

    # Verify
    verify = httpx.get(
        f"{AGENTS_URL}/{agent_id}",
        headers={"xi-api-key": api_key},
        timeout=30.0,
    )
    if verify.status_code == 200:
        agent_data = verify.json()
        ids = (
            agent_data.get("conversation_config", {})
            .get("agent", {})
            .get("prompt", {})
            .get("tool_ids", [])
        )
        print(f"\nVerified: agent has {len(ids)} tool_ids attached.")


if __name__ == "__main__":
    main()
