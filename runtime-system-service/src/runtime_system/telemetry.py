from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    """Small dependency-free Prometheus text registry with controlled labels."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = Lock()

    def ensure(self, name: str, labels: dict[str, str] | None = None) -> None:
        self.increment(name, labels, amount=0)

    def increment(
        self, name: str, labels: dict[str, str] | None = None, amount: float = 1
    ) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._values[key] += amount

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._values[key] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
    ) -> None:
        base_labels = labels or {}
        self.increment(f"{name}_sum", base_labels, value)
        self.increment(f"{name}_count", base_labels)
        for boundary in buckets:
            if value <= boundary:
                self.increment(
                    f"{name}_bucket", {**base_labels, "le": _number(boundary)}
                )
        self.increment(f"{name}_bucket", {**base_labels, "le": "+Inf"})

    def render(self) -> str:
        with self._lock:
            rows = sorted(self._values.items())
        lines: list[str] = []
        for (name, labels), value in rows:
            suffix = ""
            if labels:
                suffix = "{" + ",".join(
                    f'{key}="{_escape(label)}"' for key, label in labels
                ) + "}"
            number = _number(value)
            lines.append(f"{name}{suffix} {number}")
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(value)
