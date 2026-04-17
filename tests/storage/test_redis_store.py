"""Tests for RedisTrustStore.

We prefer ``fakeredis`` for hermetic testing because it executes Lua
scripts in-process, giving the same semantics as a real server for our
CAS operations without requiring Redis to be running.
"""

from __future__ import annotations

import pytest

pytest.importorskip("redis")
fakeredis = pytest.importorskip("fakeredis.aioredis")

from multitrust.core.errors import ConcurrencyError, StoreError  # noqa: E402
from multitrust.core.opinion import Opinion  # noqa: E402
from multitrust.core.trust_record import TrustRecord  # noqa: E402
from multitrust.storage.base import TrustStore, VersionedTrustStore  # noqa: E402
from multitrust.storage.redis_store import RedisTrustStore  # noqa: E402


def make_record(agent_id: str, belief: float = 0.5) -> TrustRecord:
    disbelief = 0.1
    uncertainty = max(0.0, 1.0 - belief - disbelief)
    # Snap to sum=1 exactly to avoid float drift in Opinion validation.
    belief = 1.0 - disbelief - uncertainty
    opinion = Opinion(belief=belief, disbelief=disbelief, uncertainty=uncertainty)
    return TrustRecord(agent_id=agent_id, opinion=opinion)


@pytest.fixture
async def store():
    client = fakeredis.FakeRedis(decode_responses=True)
    s = RedisTrustStore(client=client, namespace="test")
    yield s
    # Store does not own the client (owns_client=False), so flush + close manually.
    await client.flushall()
    await client.aclose()


async def test_protocol_conformance(store):
    assert isinstance(store, TrustStore)
    assert isinstance(store, VersionedTrustStore)


async def test_put_and_get(store):
    await store.put(make_record("agent-1"))
    retrieved = await store.get("agent-1")
    assert retrieved is not None
    assert retrieved.agent_id == "agent-1"


async def test_get_nonexistent_returns_none(store):
    assert await store.get("nope") is None
    assert await store.get_versioned("nope") is None


async def test_put_bumps_version(store):
    await store.put(make_record("agent-v"))
    _, v1 = await store.get_versioned("agent-v")
    assert v1 == 1
    await store.put(make_record("agent-v", belief=0.8))
    record, v2 = await store.get_versioned("agent-v")
    assert v2 == 2
    assert record.opinion.belief == pytest.approx(0.8)


async def test_put_if_version_insert_requires_zero(store):
    version = await store.put_if_version(make_record("agent-cas"), expected_version=0)
    assert version == 1


async def test_put_if_version_rejects_stale(store):
    await store.put_if_version(make_record("agent-cas"), expected_version=0)
    # Second CAS with expected_version=0 must fail — key exists with version 1.
    with pytest.raises(ConcurrencyError) as excinfo:
        await store.put_if_version(make_record("agent-cas"), expected_version=0)
    err = excinfo.value
    assert err.agent_id == "agent-cas"
    assert err.expected_version == 0
    assert err.actual_version == 1


async def test_put_if_version_concurrent_writers(store):
    # Simulate classic lost-update scenario.
    await store.put(make_record("agent-race", belief=0.5))
    _, version = await store.get_versioned("agent-race")

    # Writer A reads version, writer B reads version, A wins.
    await store.put_if_version(make_record("agent-race", belief=0.6), expected_version=version)

    with pytest.raises(ConcurrencyError) as excinfo:
        await store.put_if_version(make_record("agent-race", belief=0.9), expected_version=version)
    assert excinfo.value.actual_version == version + 1

    final = await store.get("agent-race")
    assert final.opinion.belief == pytest.approx(0.6)


async def test_put_if_version_cas_loop_pattern(store):
    await store.put(make_record("agent-loop", belief=0.3))

    for _ in range(5):
        current = await store.get_versioned("agent-loop")
        assert current is not None
        record, version = current
        updated = make_record("agent-loop", belief=min(record.opinion.belief + 0.1, 0.8))
        try:
            await store.put_if_version(updated, expected_version=version)
            break
        except ConcurrencyError:
            continue

    final = await store.get("agent-loop")
    assert final.opinion.belief == pytest.approx(0.4)


async def test_delete(store):
    await store.put(make_record("agent-d"))
    assert await store.delete("agent-d") is True
    assert await store.get("agent-d") is None
    assert await store.delete("agent-d") is False


async def test_delete_if_version(store):
    await store.put(make_record("agent-dv"))
    _, version = await store.get_versioned("agent-dv")

    with pytest.raises(ConcurrencyError):
        await store.delete_if_version("agent-dv", expected_version=version + 7)

    assert await store.delete_if_version("agent-dv", expected_version=version) is True
    assert await store.exists("agent-dv") is False


async def test_delete_if_version_missing_returns_false(store):
    assert await store.delete_if_version("ghost", expected_version=1) is False


async def test_delete_if_version_rejects_version_zero(store):
    with pytest.raises(ValueError):
        await store.delete_if_version("x", expected_version=0)


async def test_put_if_version_rejects_negative(store):
    with pytest.raises(ValueError):
        await store.put_if_version(make_record("x"), expected_version=-1)


async def test_list_agents(store):
    for i in range(3):
        await store.put(make_record(f"a{i}"))
    agents = await store.list_agents()
    assert set(agents) == {"a0", "a1", "a2"}


async def test_list_agents_respects_namespace(store):
    # Write a key outside our namespace directly on the backing client.
    client = store._client
    await client.hset("other:trust:foreign", mapping={"data": "{}", "version": 1})
    await store.put(make_record("ours"))
    agents = await store.list_agents()
    assert agents == ["ours"]


async def test_exists(store):
    await store.put(make_record("here"))
    assert await store.exists("here") is True
    assert await store.exists("not-here") is False


async def test_init_requires_url_or_client():
    with pytest.raises(ValueError):
        RedisTrustStore()


async def test_init_rejects_both_url_and_client():
    client = fakeredis.FakeRedis()
    with pytest.raises(ValueError):
        RedisTrustStore(url="redis://localhost:6379/0", client=client)
    await client.aclose()


async def test_close_is_noop_when_client_borrowed():
    client = fakeredis.FakeRedis(decode_responses=True)
    s = RedisTrustStore(client=client, namespace="test")
    await s.put(make_record("x"))
    await s.close()
    # Client should still be usable since store does not own it.
    assert await client.exists("test:trust:x") == 1
    await client.aclose()


async def test_store_error_wraps_transport_failure():
    # Point at a port nothing is listening on to force a connection error.
    unreachable = RedisTrustStore(url="redis://127.0.0.1:1/0", namespace="x")
    try:
        with pytest.raises(StoreError):
            await unreachable.get("anything")
    finally:
        await unreachable.close()
