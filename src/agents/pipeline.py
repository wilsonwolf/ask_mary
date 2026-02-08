"""Agent pipeline assembly — wires orchestrator handoffs.

This is the assembly module that connects the orchestrator to all
specialized agents via the OpenAI Agents SDK handoff pattern.
It imports from agent files to configure the handoff chain.

This is NOT an agent-to-agent import — it's the wiring layer that
creates the multi-agent pipeline. No agent imports from another agent;
only this assembly module references all agents to build the pipeline.
"""

from src.agents.adversarial import adversarial_agent
from src.agents.comms import comms_agent
from src.agents.identity import identity_agent
from src.agents.orchestrator import orchestrator
from src.agents.outreach import outreach_agent
from src.agents.scheduling import scheduling_agent
from src.agents.screening import screening_agent
from src.agents.supervisor import supervisor_agent
from src.agents.transport import transport_agent


def build_pipeline():
    """Assemble the multi-agent pipeline with handoffs.

    Configures the orchestrator to hand off to all specialized agents.
    This must be called once at application startup.

    Returns:
        The configured orchestrator agent ready to run.
    """
    orchestrator.handoffs = [
        outreach_agent,
        identity_agent,
        screening_agent,
        scheduling_agent,
        transport_agent,
        comms_agent,
        supervisor_agent,
        adversarial_agent,
    ]
    return orchestrator
