from __future__ import annotations

import pytest

from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.manager.sync import SyncTrustManager


def test_register_and_get_agent():
    mgr = SyncTrustManager()
    try:
        record = mgr.register_agent("agent-1")
        assert record.agent_id == "agent-1"
        fetched = mgr.get_agent("agent-1")
        assert fetched is not None
        assert fetched.agent_id == "agent-1"
    finally:
        mgr.close()


def test_submit_evidence():
    mgr = SyncTrustManager()
    try:
        mgr.register_agent("agent-1")
        initial = mgr.get_trust("agent-1")
        ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=10.0, negative=0.0)
        record = mgr.submit_evidence(ev)
        assert record.trustworthiness > initial
        assert record.evidence_count == 1
    finally:
        mgr.close()


def test_submit_batch():
    mgr = SyncTrustManager()
    try:
        mgr.register_agent("agent-1")
        evidences = [
            Evidence(agent_id="agent-1", authority_id="auth-1", positive=5.0),
            Evidence(agent_id="agent-1", authority_id="auth-1", positive=3.0),
        ]
        records = mgr.submit_batch(evidences)
        assert len(records) == 2
        assert records[-1].evidence_count == 2
    finally:
        mgr.close()


def test_is_trusted():
    mgr = SyncTrustManager()
    try:
        high_trust = Opinion(0.9, 0.05, 0.05, 0.5)
        mgr.register_agent("trusted", initial_opinion=high_trust)
        assert mgr.is_trusted("trusted", threshold=0.5) is True
        mgr.register_agent("vacuous")
        assert mgr.is_trusted("vacuous", threshold=0.9) is False
    finally:
        mgr.close()


def test_rank_agents():
    mgr = SyncTrustManager()
    try:
        mgr.register_agent("low", initial_opinion=Opinion(0.1, 0.8, 0.1, 0.5))
        mgr.register_agent("high", initial_opinion=Opinion(0.8, 0.1, 0.1, 0.5))
        ranking = mgr.rank_agents()
        assert ranking[0][0] == "high"
    finally:
        mgr.close()


def test_deregister_agent():
    mgr = SyncTrustManager()
    try:
        mgr.register_agent("agent-del")
        assert mgr.deregister_agent("agent-del") is True
        assert mgr.get_agent("agent-del") is None
    finally:
        mgr.close()


def test_apply_decay():
    mgr = SyncTrustManager()
    try:
        import time
        high_trust = Opinion(0.8, 0.1, 0.1, 0.5)
        mgr.register_agent("agent-decay", initial_opinion=high_trust)
        record = mgr.get_agent("agent-decay")
        record.updated_at = time.time() - 86400
        mgr._run(mgr._manager._store.put(record))
        trust_before = mgr.get_trust("agent-decay")
        count = mgr.apply_decay(half_life_seconds=86400.0)
        assert count == 1
        trust_after = mgr.get_trust("agent-decay")
        assert trust_after < trust_before
    finally:
        mgr.close()


def test_merge_authority_opinions():
    mgr = SyncTrustManager()
    try:
        mgr.register_agent("target")
        auth_op = Opinion(0.7, 0.1, 0.2, 0.5)
        agent_op = Opinion(0.8, 0.1, 0.1, 0.5)
        record = mgr.merge_authority_opinions("target", [(auth_op, agent_op)])
        assert record.trustworthiness > Opinion.vacuous().trustworthiness
    finally:
        mgr.close()


def test_context_manager():
    with SyncTrustManager() as mgr:
        mgr.register_agent("ctx-agent")
        assert mgr.get_agent("ctx-agent") is not None


def test_get_trust_unregistered_raises():
    from multitrust.core.errors import AgentNotFoundError
    mgr = SyncTrustManager()
    try:
        with pytest.raises(AgentNotFoundError):
            mgr.get_trust("nonexistent")
    finally:
        mgr.close()
