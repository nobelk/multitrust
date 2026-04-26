"""Redis-backed trust store with optimistic concurrency.

Durability and consistency
--------------------------

Durability is delegated to the Redis server configuration. A write that
returns successfully has been accepted by the Redis master; whether it
survives a crash depends on the server's persistence settings:

- **RDB only (Redis default)** — acknowledged writes may be lost on crash.
  Suitable for caching, not recommended as a system of record.
- **AOF with ``appendfsync everysec``** — at most ~1 second of writes lost
  on crash. A reasonable trade-off for most workloads.
- **AOF with ``appendfsync always``** — every write is fsynced before ack.
  Highest durability; lower throughput.
- **Replication / Redis Enterprise / managed services** — additional
  durability via replicas; configure according to your RPO.

``RedisTrustStore`` does not attempt to hide these trade-offs. Callers who
need strict durability must configure Redis accordingly.

Consistency guarantees (single-node or cluster):

- Every method touches exactly one key, so all operations are
  linearizable with respect to that key.
- ``put_if_version`` and ``delete_if_version`` use a server-side Lua
  script, so the version check and the mutation are atomic — no
  interleaving with concurrent writers is possible.
- ``list_agents`` uses ``SCAN`` and is *not* a consistent snapshot: keys
  added or removed during iteration may be seen zero or two times.
  Callers requiring a point-in-time listing must serialize externally.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, cast

from multitrust.core.errors import ConcurrencyError, StoreError
from multitrust.core.trust_record import TrustRecord
from multitrust.storage._errors import store_op

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.commands.core import AsyncScript


# KEYS[1] = hash key
# ARGV[1] = expected_version (int, 0 means "must not exist")
# ARGV[2] = new data (JSON string)
# Returns: new version on success, or {-1, actual_version} on mismatch.
_CAS_PUT_SCRIPT = """
local current = redis.call('HGET', KEYS[1], 'version')
local expected = tonumber(ARGV[1])
if current == false then
    if expected ~= 0 then
        return {-1, 0}
    end
    redis.call('HSET', KEYS[1], 'data', ARGV[2], 'version', 1)
    return {1}
end
current = tonumber(current)
if current ~= expected then
    return {-1, current}
end
local next_version = current + 1
redis.call('HSET', KEYS[1], 'data', ARGV[2], 'version', next_version)
return {next_version}
"""

# KEYS[1] = hash key
# ARGV[1] = expected_version
# Returns: 1 on successful delete, 0 if absent, {-1, actual_version} on mismatch.
_CAS_DELETE_SCRIPT = """
local current = redis.call('HGET', KEYS[1], 'version')
if current == false then
    return 0
end
current = tonumber(current)
local expected = tonumber(ARGV[1])
if current ~= expected then
    return {-1, current}
end
redis.call('DEL', KEYS[1])
return 1
"""


class RedisTrustStore:
    """Persistent trust record store backed by Redis.

    Implements both :class:`TrustStore` and :class:`VersionedTrustStore`.

    Parameters
    ----------
    url:
        Redis connection URL (e.g. ``redis://localhost:6379/0``).
        Mutually exclusive with ``client``.
    client:
        A pre-constructed ``redis.asyncio.Redis`` instance. Takes
        precedence when provided; caller retains ownership and is
        responsible for closing it (``close()`` on the store is a no-op
        in that case).
    namespace:
        Key prefix. All keys are stored as ``{namespace}:trust:{agent_id}``.
        Defaults to ``"multitrust"``.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        client: Redis | None = None,
        namespace: str = "multitrust",
    ) -> None:
        try:
            import redis.asyncio as _redis_async  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "redis is required to use RedisTrustStore. "
                "Install it with: pip install 'multitrust[redis]' or pip install redis"
            ) from exc

        if client is None and url is None:
            raise ValueError("RedisTrustStore requires either `url` or `client`")
        if client is not None and url is not None:
            raise ValueError("Pass either `url` or `client`, not both")

        self._url = url
        self._client: Redis | None = client
        self._owns_client = client is None
        self._namespace = namespace
        self._put_script: AsyncScript | None = None
        self._delete_script: AsyncScript | None = None

    def _key(self, agent_id: str) -> str:
        return f"{self._namespace}:trust:{agent_id}"

    async def _ensure_client(self) -> Redis:
        if self._client is None:
            from redis.asyncio import Redis as _Redis

            assert self._url is not None  # guarded in __init__
            self._client = _Redis.from_url(self._url, decode_responses=True)
        assert self._client is not None
        client: Redis = self._client
        if self._put_script is None:
            self._put_script = client.register_script(_CAS_PUT_SCRIPT)
            self._delete_script = client.register_script(_CAS_DELETE_SCRIPT)
        return client

    async def get(self, agent_id: str) -> TrustRecord | None:
        result = await self.get_versioned(agent_id)
        return None if result is None else result[0]

    @store_op("Failed to get trust record")
    async def get_versioned(self, agent_id: str) -> tuple[TrustRecord, int] | None:
        client = await self._ensure_client()
        # redis-py 7.x types hmget as returning Awaitable | sync, so cast.
        coro = cast(
            "Awaitable[list[Any]]",
            client.hmget(self._key(agent_id), ["data", "version"]),
        )
        raw = await coro
        data, version = raw[0], raw[1]
        if data is None or version is None:
            return None
        record = TrustRecord.from_dict(json.loads(data))
        return record, int(version)

    @store_op("Failed to put trust record")
    async def put(self, record: TrustRecord) -> None:
        """Unconditional write (last-write-wins).

        Bumps the stored version by 1; creates it at 1 if absent. Use
        :meth:`put_if_version` when you need to detect concurrent writes.
        """
        client = await self._ensure_client()
        data = json.dumps(record.to_dict())
        # Simple HSET + HINCRBY in a pipeline — atomic per-key.
        async with client.pipeline(transaction=True) as pipe:
            pipe.hset(self._key(record.agent_id), "data", data)
            pipe.hincrby(self._key(record.agent_id), "version", 1)
            await pipe.execute()

    async def put_if_version(self, record: TrustRecord, expected_version: int) -> int:
        """Conditional write. Returns the new version on success.

        ``expected_version=0`` requires the key to be absent (insert).
        Otherwise the stored version must match exactly. Raises
        :class:`ConcurrencyError` on mismatch.
        """
        if expected_version < 0:
            raise ValueError("expected_version must be >= 0")
        try:
            await self._ensure_client()
            assert self._put_script is not None
            data = json.dumps(record.to_dict())
            result = cast(
                list[int],
                await self._put_script(
                    keys=[self._key(record.agent_id)],
                    args=[expected_version, data],
                ),
            )
        except StoreError:
            raise
        except Exception as exc:
            raise StoreError(f"Failed to put record for {record.agent_id!r}") from exc

        if result[0] == -1:
            actual = int(result[1])
            raise ConcurrencyError(
                f"Version mismatch for {record.agent_id!r}: "
                f"expected {expected_version}, actual {actual}",
                agent_id=record.agent_id,
                expected_version=expected_version,
                actual_version=actual,
            )
        return int(result[0])

    @store_op("Failed to delete trust record")
    async def delete(self, agent_id: str) -> bool:
        client = await self._ensure_client()
        removed = await client.delete(self._key(agent_id))
        return bool(removed)

    async def delete_if_version(self, agent_id: str, expected_version: int) -> bool:
        """Conditional delete. Returns True if removed, False if absent.

        Raises :class:`ConcurrencyError` when the key exists but its
        version does not match ``expected_version``.
        """
        if expected_version < 1:
            raise ValueError("expected_version must be >= 1 for delete")
        try:
            await self._ensure_client()
            assert self._delete_script is not None
            result = await self._delete_script(
                keys=[self._key(agent_id)],
                args=[expected_version],
            )
        except ConcurrencyError:
            raise
        except Exception as exc:
            raise StoreError(f"Failed to delete record for {agent_id!r}") from exc

        if isinstance(result, list) and result and result[0] == -1:
            actual = int(result[1])
            raise ConcurrencyError(
                f"Version mismatch for {agent_id!r}: expected {expected_version}, actual {actual}",
                agent_id=agent_id,
                expected_version=expected_version,
                actual_version=actual,
            )
        return int(cast(int, result)) == 1

    @store_op("Failed to list agents")
    async def list_agents(self) -> list[str]:
        client = await self._ensure_client()
        prefix = f"{self._namespace}:trust:"
        match = f"{prefix}*"
        agents: list[str] = []
        async for key in client.scan_iter(match=match, count=500):
            key_str = key.decode() if isinstance(key, bytes) else key
            agents.append(cast(str, key_str)[len(prefix) :])
        return agents

    @store_op("Failed to check trust record existence")
    async def exists(self, agent_id: str) -> bool:
        client = await self._ensure_client()
        count = await client.exists(self._key(agent_id))
        return bool(count)

    async def close(self) -> None:
        if self._client is None or not self._owns_client:
            return
        try:
            await self._client.aclose()
        except AttributeError:
            close: Any = getattr(self._client, "close", None)
            if close is not None:
                await close()
        except Exception as exc:
            raise StoreError("Failed to close Redis client") from exc
        finally:
            self._client = None
            self._put_script = None
            self._delete_script = None
