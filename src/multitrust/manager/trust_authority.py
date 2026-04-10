from __future__ import annotations

from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.operators.discount import discount_opinion


class TrustAuthority:
    """An authority that can observe agent behaviour and submit evidence."""

    def __init__(self, authority_id: str, manager: object) -> None:
        self.authority_id = authority_id
        self._manager = manager

    async def observe(
        self,
        agent_id: str,
        positive: float = 0.0,
        negative: float = 0.0,
        **kwargs: object,
    ) -> TrustRecord:
        evidence = Evidence(
            agent_id=agent_id,
            authority_id=self.authority_id,
            positive=positive,
            negative=negative,
            metadata={k: v for k, v in kwargs.items()},
        )
        return await self._manager.submit_evidence(evidence)  # type: ignore[union-attr]

    async def get_opinion(self, agent_id: str) -> Opinion | None:
        record = await self._manager.get_agent(agent_id)  # type: ignore[union-attr]
        if record is None:
            return None
        return record.opinion


class DistributedAuthority(TrustAuthority):
    """Authority whose opinions are discounted by its own trustworthiness."""

    async def observe(
        self,
        agent_id: str,
        positive: float = 0.0,
        negative: float = 0.0,
        **kwargs: object,
    ) -> TrustRecord:
        # Get this authority's own trust record to use as discounting factor
        authority_record = await self._manager.get_agent(self.authority_id)  # type: ignore[union-attr]
        if authority_record is not None:
            authority_opinion = authority_record.opinion
            # Build raw opinion from evidence
            from multitrust.operators.mapping import evidence_to_opinion

            raw_opinion = evidence_to_opinion(positive, negative)
            # Discount by authority's trustworthiness
            discounted = discount_opinion(authority_opinion, raw_opinion)
            # Submit as pre-computed evidence equivalent: use discounted belief/disbelief
            # We submit as a direct opinion merge instead of raw evidence
            import time

            record = await self._manager.get_agent(agent_id)  # type: ignore[union-attr]
            if record is None:
                record = await self._manager.register_agent(agent_id)
            from multitrust.operators.fusion import cumulative_fusion

            new_opinion = cumulative_fusion(record.opinion, discounted)
            record.opinion = new_opinion
            record.updated_at = time.time()
            await self._manager._store.put(record)  # type: ignore[union-attr]
            return record
        # Fallback: behave like a normal authority
        return await super().observe(agent_id, positive=positive, negative=negative, **kwargs)
