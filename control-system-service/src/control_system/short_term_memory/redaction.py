import re

_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)\s*([:=])\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


def redact_sensitive_content(content: str) -> str:
    redacted = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        content,
    )
    return _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
