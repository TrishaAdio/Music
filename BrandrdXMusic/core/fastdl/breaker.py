"""
Per-provider health tracking.

The point of this module is that a dead provider must cost ~0ms, not a timeout.
When a provider fails repeatedly it gets benched for a cooldown window, then
gets a single probationary request. One success clears the record.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .config import fastdl_config


@dataclass
class ProviderHealth:
    name: str
    failures: int = 0
    successes: int = 0
    consecutive_failures: int = 0
    benched_until: float = 0.0
    last_error: str = ""
    latencies: List[float] = field(default_factory=list)

    @property
    def avg_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)


class CircuitBreaker:
    def __init__(self) -> None:
        self._health: Dict[str, ProviderHealth] = {}

    def _get(self, name: str) -> ProviderHealth:
        if name not in self._health:
            self._health[name] = ProviderHealth(name=name)
        return self._health[name]

    def available(self, name: str) -> bool:
        health = self._get(name)
        if health.benched_until and time.monotonic() >= health.benched_until:
            # Cooldown elapsed: let exactly one request through to re-test.
            health.benched_until = 0.0
            health.consecutive_failures = fastdl_config.breaker_threshold - 1
        return health.benched_until == 0.0

    def record_success(self, name: str, latency: float) -> None:
        health = self._get(name)
        health.successes += 1
        health.consecutive_failures = 0
        health.benched_until = 0.0
        health.last_error = ""
        health.latencies.append(latency)
        if len(health.latencies) > 25:
            health.latencies.pop(0)

    def record_failure(self, name: str, error: str) -> None:
        health = self._get(name)
        health.failures += 1
        health.consecutive_failures += 1
        health.last_error = error[:200]
        if health.consecutive_failures >= fastdl_config.breaker_threshold:
            health.benched_until = time.monotonic() + fastdl_config.breaker_cooldown

    def order(self, names: List[str]) -> List[str]:
        """
        Configured order first, but push benched providers to the back instead of
        dropping them, so a total outage still degrades to "try everything".
        """
        live = [n for n in names if self.available(n)]
        benched = [n for n in names if not self.available(n)]
        return live + benched

    def snapshot(self) -> List[Tuple[str, ProviderHealth]]:
        return sorted(self._health.items(), key=lambda kv: kv[0])

    def report(self) -> str:
        if not self._health:
            return "no provider activity yet"
        lines = []
        now = time.monotonic()
        for name, h in self.snapshot():
            state = "ok"
            if h.benched_until > now:
                state = f"benched {int(h.benched_until - now)}s"
            total = h.successes + h.failures
            rate = (h.successes / total * 100) if total else 0.0
            lines.append(
                f"{name}: {state} | {h.successes}/{total} ok ({rate:.0f}%) "
                f"| avg {h.avg_latency:.2f}s"
                + (f" | last error: {h.last_error}" if h.last_error else "")
            )
        return "\n".join(lines)


breaker = CircuitBreaker()
