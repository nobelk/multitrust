"""Tests for the admin / bulk-operations API on TrustManager."""

from __future__ import annotations

import json

import pytest

from multitrust.core.errors import AgentNotFoundError, AuthorityNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.core.opinion import Opinion
from multitrust.manager.admin import (
    ADMIN_AGENT_ID,
    SNAPSHOT_SCHEMA_VERSION,
    AdminAction,
    TrustSnapshot,
)
from multitrust.manager.trust_manager import AUTHORITY_METADATA_FLAG, TrustManager
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger


def _make_manager(with_ledger: bool = True) -> TrustManager:
    ledger = InMemoryEvidenceLedger() if with_ledger else None
    return TrustManager(evidence_ledger=ledger)


# ---------------------------------------------------------------------------
# Authority listing / management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_authority_marks_metadata_flag() -> None:
    manager = _make_manager()
    record = await manager.register_authority("auth-1", is_trusted=True)
    assert record.metadata.get(AUTHORITY_METADATA_FLAG) is True


@pytest.mark.asyncio
async def test_list_authorities_excludes_plain_agents() -> None:
    manager = _make_manager()
    await manager.register_agent("plain-agent")
    await manager.register_authority("auth-1")
    await manager.register_authority("auth-2", is_trusted=True)

    authorities = await manager.list_authorities()
    assert sorted(authorities) == ["auth-1", "auth-2"]


@pytest.mark.asyncio
async def test_get_authority_raises_for_plain_agent() -> None:
    manager = _make_manager()
    await manager.register_agent("not-an-authority")
    with pytest.raises(AuthorityNotFoundError):
        await manager.get_authority("not-an-authority")
    with pytest.raises(AuthorityNotFoundError):
        await manager.get_authority("nonexistent")


@pytest.mark.asyncio
async def test_set_authority_trust_with_explicit_opinion() -> None:
    manager = _make_manager()
    await manager.register_authority("auth-1", is_trusted=True)
    new_opinion = Opinion(0.3, 0.3, 0.4, 0.5)

    record = await manager.set_authority_trust("auth-1", opinion=new_opinion, actor_id="ops")
    assert record.opinion == new_opinion


@pytest.mark.asyncio
async def test_set_authority_trust_with_is_trusted_flag() -> None:
    manager = _make_manager()
    await manager.register_authority("auth-1", is_trusted=True)

    updated = await manager.set_authority_trust("auth-1", is_trusted=False, actor_id="ops")
    assert updated.trustworthiness == pytest.approx(0.5)  # vacuous, default base_rate


@pytest.mark.asyncio
async def test_set_authority_trust_requires_one_input() -> None:
    manager = _make_manager()
    await manager.register_authority("auth-1")
    with pytest.raises(ValueError):
        await manager.set_authority_trust("auth-1")


@pytest.mark.asyncio
async def test_deregister_authority_removes_and_rejects_plain_agents() -> None:
    manager = _make_manager()
    await manager.register_authority("auth-1", is_trusted=True)
    await manager.register_agent("plain")

    assert await manager.deregister_authority("auth-1", actor_id="ops") is True
    assert await manager.get_agent("auth-1") is None

    with pytest.raises(AuthorityNotFoundError):
        await manager.deregister_authority("plain")


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_snapshot_captures_records_and_authorities() -> None:
    manager = _make_manager()
    await manager.register_agent("a1", initial_opinion=Opinion(0.7, 0.1, 0.2, 0.5))
    await manager.register_agent("a2")
    await manager.register_authority("auth-1", is_trusted=True)

    snapshot = await manager.export_snapshot()
    assert snapshot.schema_version == SNAPSHOT_SCHEMA_VERSION
    assert sorted(r["agent_id"] for r in snapshot.records) == ["a1", "a2", "auth-1"]
    assert snapshot.authorities == ["auth-1"]


@pytest.mark.asyncio
async def test_export_snapshot_is_json_serializable() -> None:
    manager = _make_manager()
    await manager.register_agent("a1")
    snapshot = await manager.export_snapshot()
    blob = json.dumps(snapshot.to_dict())
    reloaded = TrustSnapshot.from_dict(json.loads(blob))
    assert reloaded.schema_version == snapshot.schema_version
    assert reloaded.records[0]["agent_id"] == "a1"


@pytest.mark.asyncio
async def test_export_snapshot_with_filter() -> None:
    manager = _make_manager()
    await manager.register_agent("a1")
    await manager.register_agent("a2")
    await manager.register_agent("a3")

    snapshot = await manager.export_snapshot(agent_ids=["a1", "a3", "missing"])
    assert sorted(r["agent_id"] for r in snapshot.records) == ["a1", "a3"]


@pytest.mark.asyncio
async def test_import_snapshot_merge_preserves_other_agents() -> None:
    src = _make_manager()
    await src.register_agent("a1", initial_opinion=Opinion(0.8, 0.1, 0.1, 0.5))
    snapshot = await src.export_snapshot()

    dest = _make_manager()
    await dest.register_agent("existing-only-in-dest")

    written = await dest.import_snapshot(snapshot, mode="merge")
    assert written == 1
    assert await dest.get_agent("a1") is not None
    assert await dest.get_agent("existing-only-in-dest") is not None


@pytest.mark.asyncio
async def test_import_snapshot_replace_wipes_store() -> None:
    src = _make_manager()
    await src.register_agent("a1")
    snapshot = await src.export_snapshot()

    dest = _make_manager()
    await dest.register_agent("will-be-deleted")
    await dest.import_snapshot(snapshot, mode="replace")

    assert await dest.get_agent("will-be-deleted") is None
    assert await dest.get_agent("a1") is not None


@pytest.mark.asyncio
async def test_import_snapshot_restores_authority_flag() -> None:
    src = _make_manager()
    await src.register_authority("auth-1", is_trusted=True)
    snapshot = await src.export_snapshot()

    dest = _make_manager()
    await dest.import_snapshot(snapshot.to_dict(), mode="replace")
    assert await dest.list_authorities() == ["auth-1"]


@pytest.mark.asyncio
async def test_import_snapshot_rejects_unknown_mode() -> None:
    manager = _make_manager()
    with pytest.raises(ValueError):
        await manager.import_snapshot(TrustSnapshot(), mode="nonsense")


@pytest.mark.asyncio
async def test_snapshot_version_mismatch_rejected() -> None:
    d = TrustSnapshot().to_dict()
    d["schema_version"] = 99
    with pytest.raises(ValueError):
        TrustSnapshot.from_dict(d)


# ---------------------------------------------------------------------------
# Reset / Reseed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_agent_clears_opinion_and_counters() -> None:
    manager = _make_manager()
    await manager.register_agent("a1", initial_opinion=Opinion(0.9, 0.05, 0.05, 0.5))
    await manager.submit_evidence(
        Evidence(agent_id="a1", authority_id="auth", positive=10.0, negative=0.0)
    )

    record = await manager.reset_agent("a1", actor_id="ops", reason="dispute")
    assert record.opinion == Opinion.vacuous()
    assert record.positive_total == 0.0
    assert record.negative_total == 0.0
    assert record.evidence_count == 0


@pytest.mark.asyncio
async def test_reset_agent_preserves_counters_when_requested() -> None:
    manager = _make_manager()
    await manager.register_agent("a1")
    await manager.submit_evidence(
        Evidence(agent_id="a1", authority_id="auth", positive=3.0, negative=1.0)
    )

    record = await manager.reset_agent("a1", clear_counters=False)
    assert record.opinion == Opinion.vacuous()
    assert record.positive_total == 3.0
    assert record.negative_total == 1.0


@pytest.mark.asyncio
async def test_reset_agent_missing_raises() -> None:
    manager = _make_manager()
    with pytest.raises(AgentNotFoundError):
        await manager.reset_agent("nonexistent")


@pytest.mark.asyncio
async def test_reset_agents_bulk_scope() -> None:
    manager = _make_manager()
    for aid in ("a1", "a2", "a3"):
        await manager.register_agent(aid, initial_opinion=Opinion(0.8, 0.1, 0.1, 0.5))

    count = await manager.reset_agents(["a1", "a2", "missing"])
    assert count == 2
    untouched = await manager.get_agent("a3")
    assert untouched is not None
    assert untouched.opinion.belief == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_reset_agents_all_when_none_passed() -> None:
    manager = _make_manager()
    for aid in ("a1", "a2"):
        await manager.register_agent(aid, initial_opinion=Opinion(0.8, 0.1, 0.1, 0.5))

    count = await manager.reset_agents()
    assert count == 2


@pytest.mark.asyncio
async def test_reseed_from_opinion_creates_record() -> None:
    manager = _make_manager()
    seed = Opinion(0.6, 0.2, 0.2, 0.5)
    record = await manager.reseed_agent("new-agent", opinion=seed, actor_id="migration")
    assert record.opinion == seed
    assert record.evidence_count == 0


@pytest.mark.asyncio
async def test_reseed_from_evidence_counts() -> None:
    manager = _make_manager()
    record = await manager.reseed_agent("a1", positive=10.0, negative=2.0)
    assert record.positive_total == 10.0
    assert record.negative_total == 2.0
    assert record.opinion.belief > record.opinion.disbelief


@pytest.mark.asyncio
async def test_reseed_requires_exactly_one_source() -> None:
    manager = _make_manager()
    with pytest.raises(ValueError):
        await manager.reseed_agent("a1")
    with pytest.raises(ValueError):
        await manager.reseed_agent("a1", opinion=Opinion.vacuous(), positive=1.0)


# ---------------------------------------------------------------------------
# Admin audit log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_audit_log_records_reset_and_reseed() -> None:
    manager = _make_manager()
    await manager.register_agent("a1")
    await manager.reset_agent("a1", actor_id="ops-alice", reason="bug")
    await manager.reseed_agent("a1", opinion=Opinion(0.5, 0.3, 0.2, 0.5), actor_id="ops-alice")

    entries = await manager.admin_audit_log(agent_id="a1")
    actions = [e.metadata["action"] for e in entries]
    assert "reset" in actions
    assert "reseed" in actions
    assert all(e.metadata["actor_id"] == "ops-alice" for e in entries)


@pytest.mark.asyncio
async def test_admin_audit_log_filters() -> None:
    manager = _make_manager()
    await manager.register_agent("a1")
    await manager.reset_agent("a1", actor_id="alice")
    await manager.reset_agent("a1", actor_id="bob")

    alice_entries = await manager.admin_audit_log(agent_id="a1", actor_id="alice")
    assert len(alice_entries) == 1
    assert alice_entries[0].metadata["actor_id"] == "alice"


@pytest.mark.asyncio
async def test_admin_audit_log_untargeted_action_uses_admin_agent_id() -> None:
    manager = _make_manager()
    # Export with no agents -> records an export action under ADMIN_AGENT_ID
    await manager.export_snapshot(actor_id="ops")

    entries = await manager.admin_audit_log(agent_id=ADMIN_AGENT_ID, action="export")
    assert len(entries) == 1
    assert entries[0].metadata["record_count"] == 0


@pytest.mark.asyncio
async def test_admin_audit_log_no_ledger_returns_empty() -> None:
    manager = _make_manager(with_ledger=False)
    await manager.register_agent("a1")
    await manager.reset_agent("a1")
    assert await manager.admin_audit_log() == []


@pytest.mark.asyncio
async def test_admin_action_to_dict_shape() -> None:
    action = AdminAction(action="reset", actor_id="ops", reason="r", target_ids=("a", "b"))
    d = action.to_dict()
    assert d["action"] == "reset"
    assert d["target_ids"] == ["a", "b"]
    assert d["actor_id"] == "ops"


@pytest.mark.asyncio
async def test_authority_deregistration_is_audited() -> None:
    manager = _make_manager()
    await manager.register_authority("auth-1")
    await manager.deregister_authority("auth-1", actor_id="ops", reason="rotation")

    entries = await manager.admin_audit_log(action="deregister_authority")
    assert len(entries) == 1
    assert entries[0].metadata["reason"] == "rotation"
