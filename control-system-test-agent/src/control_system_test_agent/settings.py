from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    agent_id: str
    genb_base_url: str
    control_system_base_url: str
    service_credential: str
    user_token: str
    http_timeout_seconds: float = 5.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "Settings":
        required = (
            "AGENT_ID",
            "GENB_BASE_URL",
            "CONTROL_SYSTEM_BASE_URL",
            "SERVICE_CREDENTIAL",
            "USER_TOKEN",
        )
        missing = [key for key in required if not values.get(key)]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")
        for key in ("GENB_BASE_URL", "CONTROL_SYSTEM_BASE_URL"):
            parsed = urlparse(values[key])
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{key} must be an HTTP(S) URL")
        for key in ("SERVICE_CREDENTIAL", "USER_TOKEN"):
            if values[key].startswith("${"):
                raise ValueError(f"{key} contains an unresolved placeholder")
        timeout = float(values.get("HTTP_TIMEOUT_SECONDS", "5"))
        if timeout <= 0 or timeout > 30:
            raise ValueError("HTTP_TIMEOUT_SECONDS must be greater than 0 and at most 30")
        return cls(
            agent_id=values["AGENT_ID"],
            genb_base_url=values["GENB_BASE_URL"],
            control_system_base_url=values["CONTROL_SYSTEM_BASE_URL"],
            service_credential=values["SERVICE_CREDENTIAL"],
            user_token=values["USER_TOKEN"],
            http_timeout_seconds=timeout,
        )
