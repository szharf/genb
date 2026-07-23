import re

_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)\s*([:=])\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_CHINESE_SECRET_PATTERN = re.compile(
    r"(?i)(密码|验证码|动态口令|密钥)\s*(是|为|[:：=])\s*([^\s,;，；。]+)"
)
_OTP_PATTERN = re.compile(r"(?i)\b(otp|verification[_ -]?code)\s*([:=])\s*([^\s,;]+)")


def redact_sensitive_content(content: str) -> str:
    redacted = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        content,
    )
    redacted = _CHINESE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted
    )
    redacted = _OTP_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted
    )
    return _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)


def contains_sensitive_content(content: str) -> bool:
    return redact_sensitive_content(content) != content
