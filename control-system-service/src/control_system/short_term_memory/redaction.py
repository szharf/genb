import re

_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)\s*([:=])\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_CHINESE_SECRET_PATTERN = re.compile(
    r"(?i)(密码|验证码|动态口令|密钥)\s*(是|为|[:：=])\s*([^\s,;，；。]+)"
)
_OTP_PATTERN = re.compile(r"(?i)\b(otp|verification[_ -]?code)\s*([:=])\s*([^\s,;]+)")
_PROVIDER_KEY_PATTERN = re.compile(r"(?i)\bsk-[a-z0-9_-]{16,}\b")
_JWT_PATTERN = re.compile(
    r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b"
)
_DATABASE_URI_PATTERN = re.compile(
    r"(?i)\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s:/@]+:)([^\s@]+)(@[^\s]+)"
)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.DOTALL,
)


def redact_sensitive_content(content: str) -> str:
    redacted = _PRIVATE_KEY_PATTERN.sub("[REDACTED PRIVATE KEY]", content)
    redacted = _DATABASE_URI_PATTERN.sub(
        lambda match: f"{match.group(1)}[REDACTED]{match.group(3)}", redacted
    )
    redacted = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        redacted,
    )
    redacted = _CHINESE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted
    )
    redacted = _OTP_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted
    )
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
    redacted = _PROVIDER_KEY_PATTERN.sub("[REDACTED]", redacted)
    return _JWT_PATTERN.sub("[REDACTED]", redacted)


def contains_sensitive_content(content: str) -> bool:
    return redact_sensitive_content(content) != content
