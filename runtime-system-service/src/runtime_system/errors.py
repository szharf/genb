from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProblem(Exception):
    status: int
    code: str
    title: str
    detail: str
    request_id: str
    retryable: bool = False
