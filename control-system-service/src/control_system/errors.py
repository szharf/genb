class ControlSystemProblem(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        request_id: str,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.request_id = request_id


class AuthenticationProblem(ControlSystemProblem):
    def __init__(self, detail: str, request_id: str) -> None:
        super().__init__(
            status=401,
            code="CONTROL_CALLER_UNAUTHENTICATED",
            title="Control System caller is unauthenticated",
            detail=detail,
            request_id=request_id,
        )


class AuthorizationProblem(ControlSystemProblem):
    def __init__(self, detail: str, request_id: str) -> None:
        super().__init__(
            status=403,
            code="CONTROL_SCOPE_DENIED",
            title="Control System scope is denied",
            detail=detail,
            request_id=request_id,
        )


class IdempotencyProblem(ControlSystemProblem):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            status=409,
            code="SHORT_TERM_IDEMPOTENCY_CONFLICT",
            title="Idempotency key conflicts with an earlier request",
            detail="The Idempotency-Key was already used for different content.",
            request_id=request_id,
        )


class DependencyProblem(ControlSystemProblem):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            status=503,
            code="SHORT_TERM_STORE_UNAVAILABLE",
            title="Short-term Memory store is unavailable",
            detail="Short-term Memory is temporarily unavailable.",
            request_id=request_id,
        )


class RuntimeConfigProblem(ControlSystemProblem):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            status=503,
            code="SHORT_TERM_CONFIG_UNAVAILABLE",
            title="Short-term Memory runtime config is unavailable",
            detail="A valid published Short-term Memory config is required.",
            request_id=request_id,
        )
