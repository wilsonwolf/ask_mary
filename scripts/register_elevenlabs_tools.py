#!/usr/bin/env python3
"""Register server tools on the ElevenLabs agent.

Three-step process:
1. (Optional --clean) Delete all tools currently attached to the agent
2. Create each tool via POST /v1/convai/tools
3. Attach tool IDs to the agent via PATCH /v1/convai/agents/{agent_id}

Reads ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, and PUBLIC_BASE_URL
from environment variables.

Usage:
    export ELEVENLABS_API_KEY=...
    export ELEVENLABS_AGENT_ID=...
    export PUBLIC_BASE_URL=https://your-cloud-run-url.run.app

    # First time or incremental:
    python scripts/register_elevenlabs_tools.py

    # Full replacement (recommended):
    python scripts/register_elevenlabs_tools.py --clean
"""

import argparse
import json
import os
import sys

import httpx

TOOLS_URL = "https://api.elevenlabs.io/v1/convai/tools"
AGENTS_URL = "https://api.elevenlabs.io/v1/convai/agents"
WORKSPACE_WEBHOOKS_URL = "https://api.elevenlabs.io/v1/workspace/webhooks"
WEBHOOK_PATH = "/webhooks/elevenlabs/server-tool"
CALL_COMPLETE_PATH = "/webhooks/elevenlabs/call-complete"


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
    """Build all 14 tool configs.

    Args:
        base_url: Public base URL for webhooks.

    Returns:
        List of tool_config dicts.
    """
    return [
        _build_tool_config(
            name="verify_identity",
            description=("Verify participant identity using date of birth year and ZIP code"),
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
            name="capture_consent",
            description=("Record AI disclosure and participant consent to continue"),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
                "disclosed_automation": {
                    "type": "string",
                    "description": ("Whether AI disclosure was given (true/false)"),
                },
                "consent_to_continue": {
                    "type": "string",
                    "description": ("Whether participant consented (true/false)"),
                },
            },
            required=[
                "participant_id",
                "disclosed_automation",
                "consent_to_continue",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="record_screening_answer",
            description=("Record participant's answer to a screening question"),
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
                    "description": (
                        "EXACT screening question key from the system prompt "
                        "SCREENING QUESTIONS list, e.g. age, diagnosis, hba1c, "
                        "pregnant_or_nursing. Use the key EXACTLY as listed."
                    ),
                },
                "answer": {
                    "type": "string",
                    "description": "Participant's verbatim answer",
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
            description=("Determine if participant is eligible for the trial"),
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
            description=("Find available appointment slots for preferred dates"),
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
                    "description": ("Comma-separated ISO dates (YYYY-MM-DD)"),
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
            description=("Book an appointment with 12-hour confirmation window"),
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
                    "description": ("Visit type: screening, baseline, or follow_up"),
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
            description=("Book a ride for the participant to their appointment"),
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
            description=("MANDATORY — run safety gate on every response before sending"),
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
        _build_tool_config(
            name="check_geo_eligibility",
            description="Check if participant is within travel distance to trial site",
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
            name="verify_teach_back",
            description=(
                "Verify participant can repeat appointment date, time, and location"
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
                "date_response": {
                    "type": "string",
                    "description": "Participant's stated appointment date",
                },
                "time_response": {
                    "type": "string",
                    "description": "Participant's stated appointment time",
                },
                "location_response": {
                    "type": "string",
                    "description": "Participant's stated appointment location",
                },
            },
            required=[
                "participant_id",
                "appointment_id",
                "date_response",
                "time_response",
                "location_response",
            ],
            base_url=base_url,
        ),
        _build_tool_config(
            name="hold_slot",
            description="Temporarily hold an appointment slot before final booking",
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
                    "description": "ISO datetime for the slot to hold",
                },
            },
            required=["participant_id", "trial_id", "slot_datetime"],
            base_url=base_url,
        ),
        _build_tool_config(
            name="mark_wrong_person",
            description=(
                "Mark that you are speaking to the wrong person — "
                "suppresses further outreach"
            ),
            properties={
                "participant_id": {
                    "type": "string",
                    "dynamic_variable": "participant_id",
                },
            },
            required=["participant_id"],
            base_url=base_url,
        ),
        _build_tool_config(
            name="mark_call_outcome",
            description=(
                "Record call result before ending: completed, no_answer, "
                "voicemail, early_hangup, wrong_person, refused, consent_denied"
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
                "outcome": {
                    "type": "string",
                    "description": (
                        "Call outcome: completed, no_answer, voicemail, "
                        "early_hangup, wrong_person, refused, consent_denied"
                    ),
                },
            },
            required=["participant_id", "trial_id", "outcome"],
            base_url=base_url,
        ),
        _build_tool_config(
            name="get_verification_prompts",
            description=(
                "Get adversarial re-verification prompts for the current call"
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


def get_agent_tool_ids(agent_id: str, headers: dict) -> list[str]:
    """Fetch tool IDs currently attached to the agent.

    Args:
        agent_id: ElevenLabs agent ID.
        headers: API headers with xi-api-key.

    Returns:
        List of tool ID strings currently on the agent.
    """
    url = f"{AGENTS_URL}/{agent_id}"
    response = httpx.get(url, headers=headers, timeout=30.0)
    if response.status_code != 200:
        print(f"  WARNING: Could not fetch agent ({response.status_code})")
        return []
    agent_data = response.json()
    return (
        agent_data.get("conversation_config", {})
        .get("agent", {})
        .get("prompt", {})
        .get("tool_ids", [])
    )


def delete_tool(tool_id: str, headers: dict) -> bool:
    """Delete a single tool via DELETE /v1/convai/tools/{tool_id}.

    Args:
        tool_id: Tool ID to delete.
        headers: API headers with xi-api-key.

    Returns:
        True on success.
    """
    url = f"{TOOLS_URL}/{tool_id}"
    response = httpx.delete(url, headers=headers, timeout=30.0)
    if response.status_code in (200, 204):
        print(f"  Deleted: {tool_id}")
        return True
    print(f"  Delete failed: {tool_id} ({response.status_code})")
    print(f"    {response.text[:200]}")
    return False


def clean_agent_tools(agent_id: str, headers: dict) -> None:
    """Remove all tools currently attached to the agent.

    Fetches the agent to find attached tool_ids, detaches them,
    then deletes each tool definition.

    Args:
        agent_id: ElevenLabs agent ID.
        headers: API headers with xi-api-key.
    """
    existing_ids = get_agent_tool_ids(agent_id, headers)
    if not existing_ids:
        print("  No existing tools found on agent.\n")
        return

    print(f"  Found {len(existing_ids)} existing tools on agent.")

    # Detach all tools from agent first
    print("  Detaching tools from agent...")
    detach_payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": [],
                },
            },
        },
    }
    url = f"{AGENTS_URL}/{agent_id}"
    response = httpx.patch(
        url,
        json=detach_payload,
        headers=headers,
        timeout=30.0,
    )
    if response.status_code == 200:
        print("  Detached all tools from agent.")
    else:
        print(f"  WARNING: Detach returned {response.status_code}")

    # Delete each tool definition
    print("  Deleting tool definitions...")
    for tool_id in existing_ids:
        delete_tool(tool_id, headers)

    print()


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
        url,
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    if response.status_code == 200:
        return True
    print(f"  Attach failed: {response.status_code}")
    print(f"    {response.text[:300]}")
    return False


def create_post_call_webhook(
    base_url: str,
    headers: dict,
) -> str | None:
    """Create a workspace webhook for post-call data.

    Args:
        base_url: Public base URL for the webhook endpoint.
        headers: API headers with xi-api-key.

    Returns:
        Webhook ID string, or None on failure.
    """
    payload = {
        "settings": {
            "auth_type": "hmac",
            "name": "ask-mary-call-complete",
            "webhook_url": f"{base_url}{CALL_COMPLETE_PATH}",
        },
    }
    response = httpx.post(
        WORKSPACE_WEBHOOKS_URL,
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    if response.status_code in (200, 201):
        data = response.json()
        webhook_id = data.get("webhook_id", "")
        secret = data.get("webhook_secret", "")
        if webhook_id:
            print(f"  Created post-call webhook: {webhook_id}")
            if secret:
                print(f"  Webhook secret: {secret}")
                print("  (Save this — needed for HMAC verification)")
            return webhook_id
    print(f"  FAILED to create webhook ({response.status_code})")
    print(f"    {response.text[:300]}")
    return None


def attach_post_call_webhook(
    agent_id: str,
    webhook_id: str,
    headers: dict,
) -> bool:
    """Attach post-call webhook to agent and enable audio.

    Args:
        agent_id: ElevenLabs agent ID.
        webhook_id: Workspace webhook ID.
        headers: API headers with xi-api-key.

    Returns:
        True on success.
    """
    payload = {
        "workspace_overrides": {
            "webhooks": {
                "post_call_webhook_id": webhook_id,
                "events": ["transcript"],
                "send_audio": True,
            },
        },
    }
    url = f"{AGENTS_URL}/{agent_id}"
    response = httpx.patch(
        url,
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    if response.status_code == 200:
        print("  Attached post-call webhook to agent.")
        return True
    print(f"  Attach webhook failed ({response.status_code})")
    print(f"    {response.text[:300]}")
    return False


def main() -> None:
    """Create tools and attach them to the agent."""
    parser = argparse.ArgumentParser(
        description="Register ElevenLabs server tools for Ask Mary agent.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "Delete all existing tools on the agent before creating "
            "new ones. Ensures a full replacement with no orphans."
        ),
    )
    parser.add_argument(
        "--setup-webhook",
        action="store_true",
        help=(
            "Create a post-call webhook and attach it to the agent. "
            "Enables transcript and audio delivery after each call."
        ),
    )
    args = parser.parse_args()

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

    if args.clean:
        print("Cleaning existing tools from agent...\n")
        clean_agent_tools(agent_id, headers)

    configs = build_all_tool_configs(base_url)
    expected_names = [c["name"] for c in configs]
    print(f"Creating {len(configs)} tools: {', '.join(expected_names)}")
    print(f"Webhook URL: {base_url}{WEBHOOK_PATH}\n")

    tool_ids: list[str] = []
    for config in configs:
        tool_id = create_tool(config, headers)
        if tool_id:
            tool_ids.append(tool_id)

    if not tool_ids:
        print("\nERROR: No tools created.")
        sys.exit(1)

    if len(tool_ids) < len(configs):
        print(
            f"\nWARNING: Only {len(tool_ids)}/{len(configs)} tools created. Some may have failed.",
        )

    print(f"\nAttaching {len(tool_ids)} tools to agent {agent_id}...")
    if attach_tools_to_agent(agent_id, tool_ids, headers):
        print("Done! Tools attached successfully.")
    else:
        print("ERROR: Failed to attach tools to agent.")
        print(f"Tool IDs to attach manually: {json.dumps(tool_ids)}")
        sys.exit(1)

    # Post-call webhook setup
    if args.setup_webhook:
        print("\nSetting up post-call webhook...")
        print(f"  Endpoint: {base_url}{CALL_COMPLETE_PATH}")
        webhook_id = create_post_call_webhook(base_url, headers)
        if webhook_id:
            attach_post_call_webhook(agent_id, webhook_id, headers)
        else:
            print("  WARNING: Could not create post-call webhook.")

    # Verify
    verified_ids = get_agent_tool_ids(agent_id, headers)
    print(f"\nVerified: agent has {len(verified_ids)} tool_ids attached.")
    if len(verified_ids) != len(configs):
        print(
            f"WARNING: Expected {len(configs)} tools but agent has {len(verified_ids)}.",
        )


if __name__ == "__main__":
    main()
