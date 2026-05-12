"""
Schema Validation Rule — Negative Evidence on Off-Schema Output
================================================================

You ship an agent that's supposed to return JSON like
``{"answer": "<string>", "confidence": <0..1>}``. Sometimes it
hallucinates a different shape. This example wires
``SchemaValidationRule`` into a ``RuleBasedCollector`` so every off-schema
response feeds *negative* evidence into the agent's trust record — no
custom evaluator code required.

Flow:

    1. Define the JSON shape the agent must return.
    2. Build a SchemaValidationRule + RuleBasedCollector.
    3. Feed three "responses" through the collector — one valid, two
       broken — and submit each as Evidence.
    4. Print the final trust score and the explain_trust() summary.

Run:

    uv run python examples/schema_validation_rule.py
"""

from __future__ import annotations

import asyncio

from multitrust import (
    InMemoryEvidenceLedger,
    RuleBasedCollector,
    SchemaValidationRule,
    TrustManager,
)

ANSWER_SCHEMA = {
    "type": "object",
    "required": ["answer", "confidence"],
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}

CANDIDATE_RESPONSES = [
    {"answer": "Paris is the capital of France.", "confidence": 0.92},  # valid
    {"answer": "", "confidence": 0.4},  # empty answer
    {"answer": "Geneva", "confidence": 1.7},  # confidence out of range
]


async def main() -> None:
    ledger = InMemoryEvidenceLedger()
    async with TrustManager(evidence_ledger=ledger) as manager:
        await manager.register_agent("answer-bot")
        collector = RuleBasedCollector(
            authority_id="schema-checker",
            rules=[SchemaValidationRule(schema=ANSWER_SCHEMA)],
        )

        for i, response in enumerate(CANDIDATE_RESPONSES, start=1):
            evidences = await collector.collect(
                agent_id="answer-bot",
                context={"output": response},
            )
            for evidence in evidences:
                await manager.submit_evidence(evidence)
            verdict = "valid" if evidences and evidences[0].positive > 0 else "off-schema"
            print(f"  response {i}: {verdict}")

        trust = await manager.get_trust("answer-bot")
        print(f"\nTrust after 3 responses (1 good, 2 off-schema): {trust:.3f}")

        explanation = await manager.explain_trust("answer-bot")
        print(explanation.summary())


if __name__ == "__main__":
    asyncio.run(main())
