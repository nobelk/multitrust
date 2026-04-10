from __future__ import annotations

from typing import TYPE_CHECKING

from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.operators.discount import discount_opinion
from multitrust.operators.mapping import evidence_to_opinion

if TYPE_CHECKING:
    from multitrust.manager.trust_manager import TrustManager


class TrustAuthority:
    """An authority that can observe agent behaviour and submit evidence."""

    def __init__(self, authority_id: str, manager: TrustManager) -> None:
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
        return await self._manager.submit_evidence(evidence)

    async def get_opinion(self, agent_id: str) -> Opinion | None:
        record = await self._manager.get_agent(agent_id)
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
        authority_record = await self._manager.get_agent(self.authority_id)
        if authority_record is not None:
            authority_opinion = authority_record.opinion
            # Build raw opinion from evidence using manager-configured prior_weight and base_rate
            raw_opinion = evidence_to_opinion(
                positive,
                negative,
                W=self._manager._config.default_prior_weight,
                base_rate=self._manager._config.default_base_rate,
            )
            # Discount by authority's trustworthiness
            discounted = discount_opinion(authority_opinion, raw_opinion)
            # Submit via manager API to ensure proper bookkeeping and callbacks
            return await self._manager.submit_discounted_opinion(
                agent_id, discounted, positive, negative
            )
        # Fallback: behave like a normal authority
        return await super().observe(agent_id, positive=positive, negative=negative, **kwargs)
