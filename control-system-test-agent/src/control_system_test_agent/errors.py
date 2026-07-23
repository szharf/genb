class RemoteCallError(RuntimeError):
    """Sanitized upstream failure that never retains request or response bodies."""

    def __init__(
        self,
        *,
        operation: str,
        status_code: int | None,
        request_id: str | None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.request_id = request_id
        status = "network failure" if status_code is None else f"HTTP {status_code}"
        super().__init__(f"{operation} failed ({status}, requestId={request_id or 'unknown'})")
