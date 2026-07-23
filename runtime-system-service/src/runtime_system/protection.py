import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from .errors import RuntimeProblem
from .identity import CallerIdentity
from .telemetry import MetricsRegistry


@dataclass(frozen=True)
class RuntimeProtectionSettings:
    max_input_characters: int = 262_144
    requests_per_window: int = 120
    window_seconds: int = 60
    max_concurrent_requests: int = 32
    acquire_timeout_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not 1 <= self.max_input_characters <= 4_194_304:
            raise ValueError("max_input_characters is outside the safe range")
        if not 1 <= self.requests_per_window <= 100_000:
            raise ValueError("requests_per_window is outside the safe range")
        if not 1 <= self.window_seconds <= 3600:
            raise ValueError("window_seconds is outside the safe range")
        if not 1 <= self.max_concurrent_requests <= 10_000:
            raise ValueError("max_concurrent_requests is outside the safe range")
        if not 0.001 <= self.acquire_timeout_seconds <= 30:
            raise ValueError("acquire_timeout_seconds is outside the safe range")


class CapacityLease:
    def __init__(self, guard: "RuntimeCapacityGuard") -> None:
        self._guard = guard
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._guard.release()

    async def __aenter__(self) -> "CapacityLease":
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.release()


class RuntimeCapacityGuard:
    def __init__(
        self,
        settings: RuntimeProtectionSettings,
        metrics: MetricsRegistry,
    ) -> None:
        self.settings = settings
        self._metrics = metrics
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._window_lock = asyncio.Lock()
        self._inflight = 0
        for reason in ("input_limit", "rate_limit", "concurrency"):
            metrics.ensure("runtime_protection_rejections_total", {"reason": reason})
        metrics.ensure("runtime_inflight_requests")

    async def acquire(
        self,
        identity: CallerIdentity,
        *,
        input_characters: int,
        request_id: str,
    ) -> CapacityLease:
        if input_characters > self.settings.max_input_characters:
            self._reject("input_limit")
            raise RuntimeProblem(
                status=413,
                code="MODEL_INPUT_LIMIT_EXCEEDED",
                title="Model input limit was exceeded",
                detail="The model input exceeds the configured character budget.",
                request_id=request_id,
            )
        await self._check_rate(identity, request_id)
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.settings.acquire_timeout_seconds,
            )
        except TimeoutError as error:
            self._reject("concurrency")
            raise RuntimeProblem(
                status=503,
                code="MODEL_CAPACITY_EXHAUSTED",
                title="Model capacity is exhausted",
                detail="The inference service has reached its configured concurrency limit.",
                request_id=request_id,
                retryable=True,
            ) from error
        self._inflight += 1
        self._metrics.set("runtime_inflight_requests", self._inflight)
        return CapacityLease(self)

    def release(self) -> None:
        self._inflight -= 1
        self._metrics.set("runtime_inflight_requests", self._inflight)
        self._semaphore.release()

    async def _check_rate(
        self, identity: CallerIdentity, request_id: str
    ) -> None:
        caller_key = sha256(identity.token_id.encode("utf-8")).hexdigest()
        now = monotonic()
        threshold = now - self.settings.window_seconds
        async with self._window_lock:
            window = self._windows[caller_key]
            while window and window[0] <= threshold:
                window.popleft()
            if len(window) >= self.settings.requests_per_window:
                self._reject("rate_limit")
                raise RuntimeProblem(
                    status=429,
                    code="MODEL_RATE_LIMITED",
                    title="Model request rate was exceeded",
                    detail="The caller exceeded the configured inference request rate.",
                    request_id=request_id,
                    retryable=True,
                )
            window.append(now)

    def _reject(self, reason: str) -> None:
        self._metrics.increment(
            "runtime_protection_rejections_total", {"reason": reason}
        )

