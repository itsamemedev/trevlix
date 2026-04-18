"""In-process metric registry for Trevlix.

Provides thread-safe ``Counter``, ``Gauge`` and ``Histogram`` primitives plus a
global :class:`MetricsRegistry` singleton. Designed as a zero-dependency
complement to the hardcoded state-based Prometheus lines in
``app/core/prometheus_metrics.py``: code paths that need to instrument a
latency or count an event can register a metric once and the registry snapshot
is emitted alongside the existing lines.

Thread-safety follows Lessons 15/19/24/49 – every internal dict/list is
guarded by its own lock and all read-check-write patterns run under the lock.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager

# Histogram buckets in seconds; tuned for HTTP / exchange call latencies.
DEFAULT_BUCKETS_S: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


def _sanitize_name(name: str) -> str:
    """Return a Prometheus-safe metric name (``[a-zA-Z0-9_]``)."""
    out = []
    for ch in str(name):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    cleaned = "".join(out).strip("_")
    return cleaned or "unnamed"


def _format_labels(labels: dict[str, str] | None) -> str:
    """Format label dict for Prometheus text exposition."""
    if not labels:
        return ""
    parts = []
    for k in sorted(labels):
        v = str(labels[k]).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        parts.append(f'{_sanitize_name(k)}="{v}"')
    return "{" + ",".join(parts) + "}"


class Counter:
    """Monotonically increasing counter. Never decreases."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = _sanitize_name(name)
        self.description = description
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the counter. Negative values are ignored."""
        if value < 0:
            return
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] += float(value)

    def value(self, labels: dict[str, str] | None = None) -> float:
        """Return current counter value for the given label combination."""
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def snapshot(self) -> list[tuple[dict[str, str], float]]:
        """Return a snapshot list of (labels, value) pairs."""
        with self._lock:
            return [(dict(k), v) for k, v in self._values.items()]


class Gauge:
    """Point-in-time value (e.g. queue depth, active connections)."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = _sanitize_name(name)
        self.description = description
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge to the given value."""
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = float(value)

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge (may be negative)."""
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(value)

    def dec(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge."""
        self.inc(-value, labels)

    def value(self, labels: dict[str, str] | None = None) -> float:
        """Return current gauge value."""
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def snapshot(self) -> list[tuple[dict[str, str], float]]:
        """Return a snapshot list of (labels, value) pairs."""
        with self._lock:
            return [(dict(k), v) for k, v in self._values.items()]


class Histogram:
    """Bucketed latency/distribution tracker."""

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] = DEFAULT_BUCKETS_S,
    ) -> None:
        self.name = _sanitize_name(name)
        self.description = description
        # Ensure buckets are sorted and unique; strip non-positive values.
        cleaned = tuple(sorted({b for b in buckets if b > 0}))
        self.buckets = cleaned or DEFAULT_BUCKETS_S
        self._counts: dict[tuple[tuple[str, str], ...], list[int]] = {}
        self._sums: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._totals: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a single observation."""
        if not math.isfinite(value):
            return
        key = tuple(sorted((labels or {}).items()))
        with self._lock:
            counts = self._counts.get(key)
            if counts is None:
                counts = [0] * len(self.buckets)
                self._counts[key] = counts
            for i, upper in enumerate(self.buckets):
                if value <= upper:
                    counts[i] += 1
            self._sums[key] += float(value)
            self._totals[key] += 1

    @contextmanager
    def time(self, labels: dict[str, str] | None = None) -> Iterator[None]:
        """Context manager that records elapsed wall-clock seconds on exit."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(time.perf_counter() - start, labels)

    def snapshot(self) -> list[dict[str, object]]:
        """Return list of per-label snapshots with buckets/sum/count."""
        with self._lock:
            out: list[dict[str, object]] = []
            for key, counts in self._counts.items():
                out.append(
                    {
                        "labels": dict(key),
                        "buckets": list(zip(self.buckets, counts, strict=True)),
                        "sum": self._sums.get(key, 0.0),
                        "count": self._totals.get(key, 0),
                    }
                )
            return out


class MetricsRegistry:
    """Central registry for all metrics."""

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str = "") -> Counter:
        """Return (or create) a named counter."""
        safe = _sanitize_name(name)
        with self._lock:
            existing = self._counters.get(safe)
            if existing is not None:
                return existing
            c = Counter(safe, description)
            self._counters[safe] = c
            return c

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Return (or create) a named gauge."""
        safe = _sanitize_name(name)
        with self._lock:
            existing = self._gauges.get(safe)
            if existing is not None:
                return existing
            g = Gauge(safe, description)
            self._gauges[safe] = g
            return g

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] = DEFAULT_BUCKETS_S,
    ) -> Histogram:
        """Return (or create) a named histogram."""
        safe = _sanitize_name(name)
        with self._lock:
            existing = self._histograms.get(safe)
            if existing is not None:
                return existing
            h = Histogram(safe, description, buckets)
            self._histograms[safe] = h
            return h

    def reset(self) -> None:
        """Drop all registered metrics. Intended for tests only."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def render_prometheus(self) -> list[str]:
        """Render all metrics in Prometheus text-exposition format."""
        with self._lock:
            counters = list(self._counters.values())
            gauges = list(self._gauges.values())
            histograms = list(self._histograms.values())

        lines: list[str] = []
        for c in counters:
            if c.description:
                lines.append(f"# HELP {c.name} {c.description}")
            lines.append(f"# TYPE {c.name} counter")
            for labels, val in c.snapshot():
                lines.append(f"{c.name}{_format_labels(labels)} {val:g}")

        for g in gauges:
            if g.description:
                lines.append(f"# HELP {g.name} {g.description}")
            lines.append(f"# TYPE {g.name} gauge")
            for labels, val in g.snapshot():
                lines.append(f"{g.name}{_format_labels(labels)} {val:g}")

        for h in histograms:
            if h.description:
                lines.append(f"# HELP {h.name} {h.description}")
            lines.append(f"# TYPE {h.name} histogram")
            for entry in h.snapshot():
                labels_d = dict(entry["labels"])  # type: ignore[arg-type]
                for upper, count in entry["buckets"]:  # type: ignore[union-attr]
                    bucket_labels = dict(labels_d)
                    bucket_labels["le"] = f"{upper:g}"
                    lines.append(f"{h.name}_bucket{_format_labels(bucket_labels)} {count:g}")
                inf_labels = dict(labels_d)
                inf_labels["le"] = "+Inf"
                lines.append(f"{h.name}_bucket{_format_labels(inf_labels)} {entry['count']:g}")
                lines.append(f"{h.name}_sum{_format_labels(labels_d)} {entry['sum']:g}")
                lines.append(f"{h.name}_count{_format_labels(labels_d)} {entry['count']:g}")

        return lines


_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Return the process-wide metrics registry singleton."""
    return _registry
