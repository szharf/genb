from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading


@dataclass(frozen=True)
class ActorTokenLease:
    token: str
    expires_at: datetime
    binding_version: int


class CachingActorTokenProvider:
    """Caches Actor Tokens only inside their signed subject, capability and binding version."""

    def __init__(self, issuer, clock, *, max_ttl: timedelta = timedelta(minutes=5),
                 safety_margin: timedelta = timedelta(seconds=5)) -> None:
        self.issuer, self.clock = issuer, clock
        self.max_ttl, self.safety_margin = max_ttl, safety_margin
        self._values: dict[tuple, tuple[str, datetime]] = {}
        self._lock = threading.RLock()

    def issue(self, session, capability_code: str, binding_version: int = 1) -> str:
        key = (session.tenant_id, session.user_id, session.agent_id, session.session_id,
               capability_code, binding_version)
        with self._lock:
            now = self.clock()
            existing = self._values.get(key)
            if existing is not None and now < existing[1]:
                return existing[0]
            self._values.pop(key, None)
            lease = self.issuer.issue_lease(session, capability_code)
            if (not isinstance(lease, ActorTokenLease) or lease.binding_version != binding_version
                    or lease.expires_at.tzinfo is None or not lease.token):
                received_version = lease.binding_version if isinstance(lease, ActorTokenLease) else None
                raise ConnectionError(
                    "actor token lease does not match the active binding "
                    f"(expected={binding_version}, received={received_version})"
                )
            usable_until = min(lease.expires_at - self.safety_margin, now + self.max_ttl)
            if usable_until <= now:
                raise ConnectionError("actor token lease is already expired")
            self._values[key] = (lease.token, usable_until)
            return lease.token

    def invalidate(self, *, agent_id: str | None = None, capability_code: str | None = None,
                   session_id: str | None = None) -> int:
        with self._lock:
            matching = [key for key in self._values if (
                (agent_id is None or key[2] == agent_id)
                and (session_id is None or key[3] == session_id)
                and (capability_code is None or key[4] == capability_code)
            )]
            for key in matching:
                self._values.pop(key, None)
            return len(matching)
