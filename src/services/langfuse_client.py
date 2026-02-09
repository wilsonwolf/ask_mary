"""Langfuse observability client — traces agent interactions.

MVP stub: logs trace events locally. Production: replace with
real Langfuse SDK calls (langfuse-python package).
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """A single span within a Langfuse trace.

    Attributes:
        span_id: Unique span identifier.
        name: Span name (agent name, tool name, etc.).
        started_at: When the span started.
        ended_at: When the span ended.
        metadata: Additional span metadata.
    """

    span_id: str = ""
    name: str = ""
    started_at: str = ""
    ended_at: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Trace:
    """A Langfuse trace representing an agent interaction.

    Attributes:
        trace_id: Unique trace identifier.
        session_id: Session/conversation identifier.
        user_id: Participant identifier.
        spans: List of spans in this trace.
    """

    trace_id: str = ""
    session_id: str = ""
    user_id: str = ""
    spans: list[TraceSpan] = field(default_factory=list)


def create_trace(
    session_id: str,
    user_id: str,
) -> Trace:
    """Create a new Langfuse trace.

    Args:
        session_id: Conversation or session identifier.
        user_id: Participant identifier.

    Returns:
        New Trace instance.
    """
    trace_id = f"trace-{uuid.uuid4()}"
    logger.info(
        "langfuse_trace_created_stub",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "user_id": user_id,
        },
    )
    return Trace(
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
    )


def add_span(
    trace: Trace,
    name: str,
    metadata: dict | None = None,
) -> TraceSpan:
    """Add a span to a trace.

    Args:
        trace: Parent trace.
        name: Span name.
        metadata: Optional span metadata.

    Returns:
        Created TraceSpan.
    """
    span = TraceSpan(
        span_id=f"span-{uuid.uuid4()}",
        name=name,
        started_at=datetime.now(UTC).isoformat(),
        metadata=metadata or {},
    )
    trace.spans.append(span)
    logger.info(
        "langfuse_span_added_stub",
        extra={
            "trace_id": trace.trace_id,
            "span_id": span.span_id,
            "name": name,
        },
    )
    return span


def end_span(span: TraceSpan) -> None:
    """Mark a span as ended.

    Args:
        span: Span to end.
    """
    span.ended_at = datetime.now(UTC).isoformat()


def flush() -> None:
    """Flush pending traces to Langfuse.

    MVP stub: no-op (traces are logged inline).
    Production: calls langfuse.flush().
    """
    logger.debug("langfuse_flush_stub")
