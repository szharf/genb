import asyncio
from collections import deque
from dataclasses import dataclass
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse

from .telemetry import MetricsRegistry


@dataclass(frozen=True)
class HttpProtectionSettings:
    max_body_bytes: int = 262_144
    requests_per_window: int = 600
    window_seconds: int = 60
    max_concurrent_requests: int = 64
    acquire_timeout_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not 1 <= self.max_body_bytes <= 8_388_608:
            raise ValueError("max_body_bytes is outside the safe range")
        if not 1 <= self.requests_per_window <= 100_000:
            raise ValueError("requests_per_window is outside the safe range")
        if not 1 <= self.window_seconds <= 3600:
            raise ValueError("window_seconds is outside the safe range")
        if not 1 <= self.max_concurrent_requests <= 10_000:
            raise ValueError("max_concurrent_requests is outside the safe range")
        if not 0.001 <= self.acquire_timeout_seconds <= 30:
            raise ValueError("acquire_timeout_seconds is outside the safe range")


class HttpProtection:
    def __init__(
        self, settings: HttpProtectionSettings, metrics: MetricsRegistry
    ) -> None:
        self.settings = settings
        self._metrics = metrics
        self._window: deque[float] = deque()
        self._window_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._inflight = 0
        for reason in ("body_size", "rate_limit", "concurrency"):
            metrics.ensure("control_protection_rejections_total", {"reason": reason})
        metrics.ensure("control_inflight_requests")

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/v1/control-system/"):
            return await call_next(request)
        request_id = request.headers.get("X-Request-Id", "unknown")[:128]
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.settings.max_body_bytes
            except ValueError:
                too_large = True
            if too_large:
                return self._reject(
                    reason="body_size",
                    status=413,
                    code="CONTROL_REQUEST_TOO_LARGE",
                    title="Control request is too large",
                    detail="The request body exceeds the configured byte budget.",
                    request_id=request_id,
                )
        if not await self._within_rate():
            return self._reject(
                reason="rate_limit",
                status=429,
                code="CONTROL_RATE_LIMITED",
                title="Control request rate was exceeded",
                detail="The service exceeded its configured request rate.",
                request_id=request_id,
                retryable=True,
                headers={"Retry-After": str(self.settings.window_seconds)},
            )
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.settings.acquire_timeout_seconds,
            )
        except TimeoutError:
            return self._reject(
                reason="concurrency",
                status=503,
                code="CONTROL_CAPACITY_EXHAUSTED",
                title="Control capacity is exhausted",
                detail="The service reached its configured concurrency limit.",
                request_id=request_id,
                retryable=True,
            )
        self._inflight += 1
        self._metrics.set("control_inflight_requests", self._inflight)
        try:
            return await call_next(request)
        finally:
            self._inflight -= 1
            self._metrics.set("control_inflight_requests", self._inflight)
            self._semaphore.release()

    async def _within_rate(self) -> bool:
        now = monotonic()
        threshold = now - self.settings.window_seconds
        async with self._window_lock:
            while self._window and self._window[0] <= threshold:
                self._window.popleft()
            if len(self._window) >= self.settings.requests_per_window:
                return False
            self._window.append(now)
            return True

    def _reject(
        self,
        *,
        reason: str,
        status: int,
        code: str,
        title: str,
        detail: str,
        request_id: str,
        retryable: bool = False,
        headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        self._metrics.increment(
            "control_protection_rejections_total", {"reason": reason}
        )
        return JSONResponse(
            status_code=status,
            headers=headers,
            media_type="application/problem+json",
            content={
                "type": f"https://errors.genb.local/{code.lower().replace('_', '-')}",
                "title": title,
                "status": status,
                "detail": detail,
                "code": code,
                "requestId": request_id,
                "retryable": retryable,
            },
        )

