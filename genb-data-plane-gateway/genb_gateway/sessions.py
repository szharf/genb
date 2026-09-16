from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import secrets
import socket
import threading
from typing import Callable


@dataclass(frozen=True)
class GatewaySession:
    session_id: str
    tenant_id: str
    user_id: str
    username: str
    agent_id: str
    session_grant: str
    expires_at: datetime
    created_at: datetime | None = None


class InMemorySessionStore:
    """Test adapter for the Gateway Session interface; stores only token hashes as keys."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._sessions: dict[str, GatewaySession] = {}

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, *, ttl: timedelta, **subject) -> str:
        token = secrets.token_urlsafe(32)
        now = self._clock()
        session = GatewaySession(expires_at=now + ttl, created_at=now, **subject)
        self._sessions[self._hash(token)] = session
        return token

    def resolve(self, token: str | None) -> GatewaySession | None:
        if not token:
            return None
        key = self._hash(token)
        session = self._sessions.get(key)
        if session is None:
            return None
        if session.expires_at <= self._clock():
            self._sessions.pop(key, None)
            return None
        return session

    def revoke(self, token: str | None) -> GatewaySession | None:
        if not token:
            return None
        return self._sessions.pop(self._hash(token), None)

    def is_active(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> bool:
        now = self._clock()
        return any(
            session.expires_at > now and session.session_id == session_id and session.tenant_id == tenant_id
            and session.user_id == user_id and session.agent_id == agent_id
            for session in self._sessions.values()
        )

    def resolve_subject(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> GatewaySession | None:
        now = self._clock()
        return next((session for session in self._sessions.values()
                     if session.expires_at > now and session.session_id == session_id and session.tenant_id == tenant_id
                     and session.user_id == user_id and session.agent_id == agent_id), None)

    def revoke_subject(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> int:
        matching = [key for key, session in self._sessions.items()
                    if session.session_id == session_id and session.tenant_id == tenant_id
                    and session.user_id == user_id and session.agent_id == agent_id]
        for key in matching: self._sessions.pop(key, None)
        return len(matching)

    def revoke_access(self, *, tenant_id: str, user_id: str, agent_id: str) -> int:
        matching = [key for key, session in self._sessions.items()
                    if session.tenant_id == tenant_id and session.user_id == user_id and session.agent_id == agent_id]
        for key in matching: self._sessions.pop(key, None)
        return len(matching)

    def revoke_agent(self, *, agent_id: str) -> int:
        matching = [key for key, session in self._sessions.items() if session.agent_id == agent_id]
        for key in matching: self._sessions.pop(key, None)
        return len(matching)


class L1SessionStore:
    """Five-second read-through cache; all writes still require the Redis adapter."""

    def __init__(self, backend, clock, *, ttl: timedelta = timedelta(seconds=5),
                 deny_ttl: timedelta = timedelta(hours=8)) -> None:
        self.backend, self.clock, self.ttl, self.deny_ttl = backend, clock, ttl, deny_ttl
        self._tokens: dict[str, tuple[GatewaySession, datetime]] = {}
        self._subjects: dict[tuple[str, str, str, str], tuple[GatewaySession, datetime]] = {}
        self._denied_tokens: dict[str, datetime] = {}
        self._denied_subjects: dict[tuple[str, str, str, str], datetime] = {}
        self._denied_access: dict[tuple[str, str, str], datetime] = {}
        self._denied_agents: dict[str, datetime] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _token_key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _subject_key(*, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> tuple[str, str, str, str]:
        return tenant_id, user_id, agent_id, session_id

    def create(self, **kwargs) -> str:
        return self.backend.create(**kwargs)

    def resolve(self, token: str | None) -> GatewaySession | None:
        if not token: return None
        key = self._token_key(token)
        with self._lock:
            hit = self._tokens.get(key)
            if hit and self.clock() < hit[1] and self.clock() < hit[0].expires_at:
                return None if self._is_denied(hit[0], token_key=key) else hit[0]
            self._tokens.pop(key, None)
        session = self.backend.resolve(token)
        if session is not None and self._is_denied(session, token_key=key): return None
        if session is not None: self._remember(key, session)
        return session

    def resolve_subject(self, **subject) -> GatewaySession | None:
        key = self._subject_key(**subject)
        with self._lock:
            hit = self._subjects.get(key)
            if hit and self.clock() < hit[1] and self.clock() < hit[0].expires_at:
                return None if self._is_denied(hit[0]) else hit[0]
            self._subjects.pop(key, None)
        session = self.backend.resolve_subject(**subject)
        if session is not None and self._is_denied(session): return None
        if session is not None: self._remember(None, session)
        return session

    def is_active(self, **subject) -> bool:
        return self.resolve_subject(**subject) is not None

    def revoke(self, token: str | None) -> GatewaySession | None:
        cached = None
        if token:
            with self._lock:
                key = self._token_key(token)
                entry = self._tokens.pop(key, None)
                cached = entry[0] if entry else None
                self._denied_tokens[key] = self.clock() + self.deny_ttl
                if cached is not None:
                    subject = (cached.tenant_id, cached.user_id, cached.agent_id, cached.session_id)
                    self._subjects.pop(subject, None)
                    self._denied_subjects[subject] = self.clock() + self.deny_ttl
        session = self.backend.revoke(token)
        if session is not None: self._forget(lambda item: item == session)
        return session

    def revoke_subject(self, **subject) -> int:
        self._forget(lambda item: self._matches(item, **subject))
        with self._lock:
            self._denied_subjects[self._subject_key(**subject)] = self.clock() + self.deny_ttl
        return self.backend.revoke_subject(**subject)

    def revoke_access(self, **subject) -> int:
        self._forget(lambda item: self._matches(item, **subject))
        with self._lock:
            key = (subject["tenant_id"], subject["user_id"], subject["agent_id"])
            self._denied_access[key] = self.clock() + self.deny_ttl
        return self.backend.revoke_access(**subject)

    def revoke_agent(self, *, agent_id: str) -> int:
        self._forget(lambda item: item.agent_id == agent_id)
        with self._lock: self._denied_agents[agent_id] = self.clock() + self.deny_ttl
        return self.backend.revoke_agent(agent_id=agent_id)

    def _is_denied(self, session: GatewaySession, *, token_key: str | None = None) -> bool:
        now = self.clock()
        subject = (session.tenant_id, session.user_id, session.agent_id, session.session_id)
        access = subject[:3]
        with self._lock:
            self._denied_tokens = {key: expiry for key, expiry in self._denied_tokens.items() if expiry > now}
            self._denied_subjects = {key: expiry for key, expiry in self._denied_subjects.items() if expiry > now}
            self._denied_access = {key: expiry for key, expiry in self._denied_access.items() if expiry > now}
            self._denied_agents = {key: expiry for key, expiry in self._denied_agents.items() if expiry > now}
            # Scope invalidation revokes sessions existing at that moment. A later
            # successful authorization may create a new session for the same user.
            # Legacy records without creation time stay conservatively revoked.
            def predates(expiry):
                return expiry is not None and (session.created_at is None
                                                or session.created_at <= expiry - self.deny_ttl)
            return ((token_key is not None and token_key in self._denied_tokens)
                    or subject in self._denied_subjects
                    or predates(self._denied_access.get(access))
                    or predates(self._denied_agents.get(session.agent_id)))

    def _remember(self, token_key: str | None, session: GatewaySession) -> None:
        expires = min(self.clock() + self.ttl, session.expires_at)
        subject = (session.tenant_id, session.user_id, session.agent_id, session.session_id)
        with self._lock:
            if token_key: self._tokens[token_key] = (session, expires)
            self._subjects[subject] = (session, expires)

    def _forget(self, predicate) -> None:
        with self._lock:
            self._tokens = {key:value for key,value in self._tokens.items() if not predicate(value[0])}
            self._subjects = {key:value for key,value in self._subjects.items() if not predicate(value[0])}

    @staticmethod
    def _matches(session: GatewaySession, **subject) -> bool:
        return all(getattr(session, name) == value for name, value in subject.items())


class RespRedisClient:
    def __init__(self, host: str, port: int, *, timeout: float = 1.0, password: str | None = None) -> None:
        self.host, self.port, self.timeout, self.password = host, port, timeout, password

    def command(self, *parts: str):
        def encode(command_parts):
            return f"*{len(command_parts)}\r\n".encode() + b"".join(
                f"${len(part.encode())}\r\n".encode() + part.encode() + b"\r\n" for part in command_parts
            )
        request = (encode(("AUTH", self.password)) if self.password else b"") + encode(parts)
        with socket.create_connection((self.host, self.port), self.timeout) as connection:
            connection.sendall(request)
            stream = connection.makefile("rb")
            if self.password and self._read(stream) != "OK":
                raise ConnectionError("Redis authentication failed")
            return self._read(stream)

    def _read(self, stream):
        marker = stream.read(1)
        if marker == b"+": return stream.readline()[:-2].decode()
        if marker == b"-": raise ConnectionError(stream.readline()[:-2].decode())
        if marker == b":": return int(stream.readline()[:-2])
        if marker == b"$":
            length = int(stream.readline()[:-2])
            if length < 0: return None
            value = stream.read(length); stream.read(2); return value.decode()
        if marker == b"*":
            count = int(stream.readline()[:-2]); return [self._read(stream) for _ in range(count)]
        raise ConnectionError("invalid Redis response")


class RedisSessionStore:
    CREATE_SCRIPT = (
        "if redis.call('EXISTS',KEYS[1]) == 1 then return 0; end; "
        "redis.call('SET',KEYS[1],ARGV[1],'EX',ARGV[2]); "
        "redis.call('SET',KEYS[2],ARGV[3],'EX',ARGV[2]); redis.call('SADD',KEYS[3],KEYS[2]); "
        "redis.call('SADD',KEYS[4],KEYS[2]); redis.call('EXPIRE',KEYS[3],ARGV[2]); "
        "redis.call('EXPIRE',KEYS[4],ARGV[2]); return 1"
    )
    REVOKE_SCRIPT = (
        "local v=redis.call('GET',KEYS[1]); if not v then return nil; end; "
        "local r=cjson.decode(v); local raw=r.tenant_id..'\\0'..r.user_id..'\\0'..r.agent_id..'\\0'..r.session_id; "
        "local sk=ARGV[1]..'subject:'..redis.sha1hex(raw); redis.call('DEL',KEYS[1]); "
        "local sv=redis.call('GET',sk); if sv then local sr=cjson.decode(sv); "
        "if sr.primary_key == KEYS[1] then redis.call('DEL',sk); end; end; "
        "local ak=ARGV[1]..'access:'..redis.sha1hex(r.tenant_id..'\\0'..r.user_id..'\\0'..r.agent_id); "
        "local gk=ARGV[1]..'agent:'..redis.sha1hex(r.agent_id); "
        "redis.call('SREM',ak,sk); redis.call('SREM',gk,sk); return v"
    )
    REVOKE_SUBJECT_SCRIPT = (
        "local v=redis.call('GET',KEYS[1]); if not v then return nil; end; local r=cjson.decode(v); "
        "if r.primary_key then redis.call('DEL',r.primary_key); redis.call('DEL',KEYS[1]); "
        "local s=r.session; local ak=ARGV[1]..'access:'..redis.sha1hex(s.tenant_id..'\\0'..s.user_id..'\\0'..s.agent_id); "
        "local gk=ARGV[1]..'agent:'..redis.sha1hex(s.agent_id); "
        "redis.call('SREM',ak,KEYS[1]); redis.call('SREM',gk,KEYS[1]); return cjson.encode(s); end; "
        "redis.call('DEL',KEYS[1]); return v"
    )
    REVOKE_ACCESS_SCRIPT = (
        "local members=redis.call('SMEMBERS',KEYS[1]); local count=0; for _,sk in ipairs(members) do "
        "local v=redis.call('GET',sk); if v then local r=cjson.decode(v); "
        "if r.primary_key then redis.call('DEL',r.primary_key); end; if r.session then "
        "local gk=ARGV[1]..'agent:'..redis.sha1hex(r.session.agent_id); redis.call('SREM',gk,sk); end; "
        "redis.call('DEL',sk); count=count+1; end; end; "
        "redis.call('DEL',KEYS[1]); return count"
    )
    REVOKE_AGENT_SCRIPT = (
        "local members=redis.call('SMEMBERS',KEYS[1]); local count=0; for _,sk in ipairs(members) do "
        "local v=redis.call('GET',sk); if v then local r=cjson.decode(v); "
        "if r.primary_key then redis.call('DEL',r.primary_key); end; if r.session then local s=r.session; "
        "local ak=ARGV[1]..'access:'..redis.sha1hex(s.tenant_id..'\\0'..s.user_id..'\\0'..s.agent_id); "
        "redis.call('SREM',ak,sk); end; redis.call('DEL',sk); count=count+1; end; end; "
        "redis.call('DEL',KEYS[1]); return count"
    )

    def __init__(self, redis: RespRedisClient, clock: Callable[[], datetime], *, namespace: str = "genb:gateway:session:") -> None:
        self.redis, self._clock, self.namespace = redis, clock, namespace

    def _key(self, token: str) -> str:
        return self.namespace + hashlib.sha256(token.encode()).hexdigest()

    def create(self, *, ttl: timedelta, **subject) -> str:
        for _ in range(4):
            token = secrets.token_urlsafe(32)
            now = self._clock()
            session = GatewaySession(expires_at=now + ttl, created_at=now, **subject)
            value = json.dumps({**session.__dict__, "expires_at": session.expires_at.isoformat(),
                                "created_at": now.isoformat()}, separators=(",", ":"))
            subject_value = json.dumps({"primary_key":self._key(token), "session":json.loads(value)}, separators=(",", ":"))
            seconds = str(max(1, int(ttl.total_seconds())))
            if self.redis.command("EVAL", self.CREATE_SCRIPT, "4", self._key(token),
                                  self._subject_key(session.session_id, session.tenant_id, session.user_id, session.agent_id),
                                  self._access_key(session.tenant_id, session.user_id, session.agent_id),
                                  self._agent_key(session.agent_id),
                                  value, seconds, subject_value) == 1:
                return token
        raise RuntimeError("failed to allocate unique gateway session")

    def resolve(self, token: str | None) -> GatewaySession | None:
        if not token: return None
        value = self.redis.command("GET", self._key(token))
        session = self._decode(value)
        if session and session.expires_at <= self._clock():
            self.revoke(token); return None
        return session

    def revoke(self, token: str | None) -> GatewaySession | None:
        if not token: return None
        value = self.redis.command("EVAL", self.REVOKE_SCRIPT, "1", self._key(token), self.namespace)
        return self._decode(value)

    def is_active(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> bool:
        return self.resolve_subject(session_id=session_id, tenant_id=tenant_id, user_id=user_id, agent_id=agent_id) is not None

    def resolve_subject(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> GatewaySession | None:
        value = self.redis.command("GET", self._subject_key(session_id, tenant_id, user_id, agent_id))
        if value is None: return None
        record = json.loads(value)
        return self._decode(json.dumps(record["session"])) if "session" in record else self._decode(value)

    def revoke_subject(self, *, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> int:
        key = self._subject_key(session_id, tenant_id, user_id, agent_id)
        value = self.redis.command("EVAL", self.REVOKE_SUBJECT_SCRIPT, "1", key, self.namespace)
        return 1 if value is not None else 0

    def revoke_access(self, *, tenant_id: str, user_id: str, agent_id: str) -> int:
        return int(self.redis.command("EVAL", self.REVOKE_ACCESS_SCRIPT, "1",
                                      self._access_key(tenant_id, user_id, agent_id), self.namespace))

    def revoke_agent(self, *, agent_id: str) -> int:
        return int(self.redis.command("EVAL", self.REVOKE_AGENT_SCRIPT, "1", self._agent_key(agent_id), self.namespace))

    def _subject_key(self, session_id: str, tenant_id: str, user_id: str, agent_id: str) -> str:
        return self.namespace + "subject:" + hashlib.sha1(
            f"{tenant_id}\0{user_id}\0{agent_id}\0{session_id}".encode()
        ).hexdigest()

    def _access_key(self, tenant_id: str, user_id: str, agent_id: str) -> str:
        return self.namespace + "access:" + hashlib.sha1(f"{tenant_id}\0{user_id}\0{agent_id}".encode()).hexdigest()

    def _agent_key(self, agent_id: str) -> str:
        return self.namespace + "agent:" + hashlib.sha1(agent_id.encode()).hexdigest()

    @staticmethod
    def _decode(value: str | None) -> GatewaySession | None:
        if value is None: return None
        record = json.loads(value); record["expires_at"] = datetime.fromisoformat(record["expires_at"])
        if record.get("created_at") is not None:
            record["created_at"] = datetime.fromisoformat(record["created_at"])
        return GatewaySession(**record)


@dataclass(frozen=True)
class LoginState:
    agent_id: str
    return_path: str
    expires_at: datetime


class LoginStateStore:
    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._states: dict[str, LoginState] = {}

    def create(self, agent_id: str, return_path: str) -> str:
        state = secrets.token_urlsafe(32)
        self._states[self._hash(state)] = LoginState(agent_id, return_path, self._clock() + timedelta(minutes=5))
        return state

    def consume(self, state: str) -> LoginState | None:
        record = self._states.pop(self._hash(state), None)
        return record if record and record.expires_at > self._clock() else None

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()
