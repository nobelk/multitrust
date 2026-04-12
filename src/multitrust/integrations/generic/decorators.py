"""Generic decorators for trust-aware function execution."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from multitrust.core.errors import TrustThresholdError
from multitrust.core.evidence import Evidence


def trust_aware(
    manager: Any,
    agent_id: str,
    threshold: float = 0.5,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that gates function execution on agent trust score.

    Raises TrustThresholdError if the agent's trust score is below threshold.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            trust = await manager.get_trust(agent_id)
            if trust < threshold:
                raise TrustThresholdError(
                    f"Agent {agent_id} trust {trust:.2f} below threshold {threshold}"
                )
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def collect_evidence(
    manager: Any,
    agent_id: str,
    authority_id: str = "system",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that auto-collects evidence from function success/failure.

    On success: submits positive=1.0 evidence.
    On exception: submits negative=1.0 evidence, then re-raises.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = await fn(*args, **kwargs)
                await manager.submit_evidence(
                    Evidence(
                        agent_id=agent_id, authority_id=authority_id, positive=1.0, negative=0.0
                    )
                )
                return result
            except Exception:
                await manager.submit_evidence(
                    Evidence(
                        agent_id=agent_id, authority_id=authority_id, positive=0.0, negative=1.0
                    )
                )
                raise

        return wrapper

    return decorator
