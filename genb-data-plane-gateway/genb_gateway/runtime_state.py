from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import copy
import json
import threading

from .capabilities import PublishedCapability, PublishedCapabilityTable
from .routing import PublishedAgentRoute, PublishedRouteTable


class ConfigurationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredSnapshot:
    snapshot: dict
    fetched_at: datetime


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self._record: StoredSnapshot | None = None

    def save(self, snapshot: dict, fetched_at: datetime) -> None:
        self._record = StoredSnapshot(copy.deepcopy(snapshot), fetched_at)

    def load(self) -> StoredSnapshot | None:
        if self._record is None:
            return None
        return StoredSnapshot(copy.deepcopy(self._record.snapshot), self._record.fetched_at)


class RedisSnapshotStore:
    def __init__(self, redis, *, key: str = "genb:gateway:config:last-known-good") -> None:
        self.redis, self.key = redis, key

    def save(self, snapshot: dict, fetched_at: datetime) -> None:
        value = json.dumps({
            "schemaVersion":"1.0", "fetchedAt":fetched_at.isoformat(), "snapshot":snapshot,
        }, separators=(",", ":"), sort_keys=True)
        self.redis.command("SET", self.key, value)

    def load(self) -> StoredSnapshot | None:
        value = self.redis.command("GET", self.key)
        if value is None:
            return None
        try:
            record = json.loads(value)
            if set(record) != {"schemaVersion", "fetchedAt", "snapshot"} or record["schemaVersion"] != "1.0":
                raise ValueError("invalid stored snapshot")
            fetched_at = datetime.fromisoformat(record["fetchedAt"])
            if fetched_at.tzinfo is None:
                raise ValueError("stored snapshot timestamp must be timezone-aware")
            return StoredSnapshot(record["snapshot"], fetched_at)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ConfigurationUnavailable("stored snapshot is invalid") from error


@dataclass(frozen=True)
class RuntimeSnapshot:
    config_version: int
    published_at: str
    loaded_at: datetime
    raw: dict
    capabilities: PublishedCapabilityTable
    routes: PublishedRouteTable


class ControlSnapshotModule:
    """Owns validation, last-known-good persistence and atomic runtime publication."""

    def __init__(self, *, source, store, clock, poll_interval: timedelta = timedelta(seconds=2),
                 high_risk_ttl: timedelta = timedelta(seconds=5),
                 low_risk_grace: timedelta = timedelta(minutes=15),
                 allowed_upstreams: frozenset[tuple[str, int]] = frozenset()) -> None:
        self.source, self.store, self.clock = source, store, clock
        self.poll_interval = poll_interval
        self.high_risk_ttl = high_risk_ttl
        self.low_risk_grace = low_risk_grace
        self.allowed_upstreams = allowed_upstreams
        self._current: RuntimeSnapshot | None = None
        self._last_checked: datetime | None = None
        self._last_control_success: datetime | None = None
        self._lock = threading.RLock()

    def start(self) -> RuntimeSnapshot:
        try:
            return self.refresh(force=True)
        except ConfigurationUnavailable as control_error:
            try:
                record = self.store.load()
            except (ConnectionError, OSError) as store_error:
                raise ConfigurationUnavailable("control and snapshot store are unavailable") from store_error
            if record is None:
                raise control_error
            with self._lock:
                restored = self._compile(record.snapshot, record.fetched_at)
                self._current = restored
                self._last_control_success = record.fetched_at
                self._last_checked = self.clock()
                return self.current(risk="LOW")

    def invalidate(self) -> RuntimeSnapshot:
        with self._lock:
            self._last_checked = None
        return self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> RuntimeSnapshot:
        with self._lock:
            now = self.clock()
            if not force and self._last_checked is not None and now - self._last_checked < self.poll_interval:
                return self.current(risk="HIGH")
            self._last_checked = now
            try:
                version = self.source.get_version()
                if self._current is not None and version == self._current.config_version:
                    self._last_control_success = now
                    return self._current
                candidate = self.source.get_snapshot()
                if candidate.get("configVersion") != version:
                    raise ValueError("snapshot version does not match control version")
                compiled = self._compile(candidate, now)
            except (ConnectionError, OSError, ValueError, KeyError, TypeError) as error:
                raise ConfigurationUnavailable("complete control snapshot is unavailable") from error
            try:
                self.store.save(candidate, now)
            except (ConnectionError, OSError):
                pass
            self._current = compiled
            self._last_control_success = now
            return compiled

    def current(self, *, risk: str = "HIGH") -> RuntimeSnapshot:
        with self._lock:
            if self._current is None:
                raise ConfigurationUnavailable("no last-known-good snapshot")
            age = self.clock() - (self._last_control_success or self._current.loaded_at)
            limit = self.high_risk_ttl if risk == "HIGH" else self.low_risk_grace
            if risk not in {"HIGH", "LOW"} or age > limit:
                raise ConfigurationUnavailable("last-known-good snapshot is too old")
            return self._current

    def resolve(self, agent_id: str, capability_code: str | None = None):
        try:
            self.refresh()
        except ConfigurationUnavailable:
            pass
        state = self.current(risk="HIGH")
        if capability_code is None:
            return state.routes.resolve(agent_id)
        return state.capabilities.resolve(agent_id, capability_code)

    def _compile(self, snapshot: dict, loaded_at: datetime) -> RuntimeSnapshot:
        if set(snapshot) != {"schemaVersion", "configVersion", "publishedAt", "agents", "implementations", "bindings"}:
            raise ValueError("snapshot envelope is not closed")
        if snapshot["schemaVersion"] != "1.0" or not isinstance(snapshot["configVersion"], int):
            raise ValueError("unsupported snapshot")
        serialized = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
        immutable_raw = json.loads(serialized)
        capabilities = PublishedCapabilityTable.from_snapshot(immutable_raw)
        routes = PublishedRouteTable(
            routes=[PublishedAgentRoute(
                item["agentId"], item["upstreamRef"].rstrip("/"), item["identityMode"], frozenset({"*"}),
            ) for item in immutable_raw["agents"] if item["status"] == "PUBLISHED"],
            allowed_upstreams=self.allowed_upstreams,
        )
        return RuntimeSnapshot(snapshot["configVersion"], snapshot["publishedAt"], loaded_at,
                               immutable_raw, capabilities, routes)
