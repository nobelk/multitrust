from __future__ import annotations

from multitrust.core.evidence import EvidenceResult


class TaskCompletionRule:
    """Evaluates task completion from context['success'] (bool)."""

    name: str = "task_completion"

    def evaluate(self, context: dict) -> EvidenceResult | None:
        success = context.get("success")
        if success is None:
            return None
        if success:
            return EvidenceResult(positive=1.0, negative=0.0, metadata={"rule": self.name})
        else:
            return EvidenceResult(positive=0.0, negative=1.0, metadata={"rule": self.name})
