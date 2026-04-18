"""Tests für services.metrics_collector."""

from __future__ import annotations

import threading

import pytest

from services.metrics_collector import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    _sanitize_name,
    get_registry,
)


class TestSanitizeName:
    def test_alphanumeric_preserved(self):
        assert _sanitize_name("trevlix_api_calls") == "trevlix_api_calls"

    def test_invalid_chars_replaced(self):
        assert _sanitize_name("a.b-c/d") == "a_b_c_d"

    def test_empty_fallback(self):
        assert _sanitize_name("") == "unnamed"
        assert _sanitize_name("---") == "unnamed"


class TestCounter:
    def test_inc_basic(self):
        c = Counter("c")
        c.inc()
        c.inc(2)
        assert c.value() == 3.0

    def test_negative_ignored(self):
        c = Counter("c")
        c.inc(-5)
        assert c.value() == 0.0

    def test_labels_separate_streams(self):
        c = Counter("c")
        c.inc(labels={"endpoint": "a"})
        c.inc(labels={"endpoint": "b"})
        c.inc(labels={"endpoint": "a"})
        assert c.value({"endpoint": "a"}) == 2.0
        assert c.value({"endpoint": "b"}) == 1.0

    def test_thread_safety(self):
        c = Counter("c")

        def worker():
            for _ in range(1000):
                c.inc()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert c.value() == 8000.0


class TestGauge:
    def test_set_and_get(self):
        g = Gauge("g")
        g.set(42.5)
        assert g.value() == 42.5

    def test_inc_dec(self):
        g = Gauge("g")
        g.inc(5)
        g.inc(3)
        g.dec(2)
        assert g.value() == 6.0

    def test_labels(self):
        g = Gauge("g")
        g.set(10, labels={"host": "a"})
        g.set(20, labels={"host": "b"})
        assert g.value({"host": "a"}) == 10.0
        assert g.value({"host": "b"}) == 20.0


class TestHistogram:
    def test_observe_buckets(self):
        h = Histogram("h", buckets=(0.1, 1.0, 10.0))
        h.observe(0.05)
        h.observe(0.5)
        h.observe(5.0)
        snap = h.snapshot()
        assert len(snap) == 1
        buckets = dict(snap[0]["buckets"])
        # 0.05 lands in all three buckets, 0.5 in (1.0, 10.0), 5.0 only in 10.0
        assert buckets[0.1] == 1
        assert buckets[1.0] == 2
        assert buckets[10.0] == 3
        assert snap[0]["count"] == 3

    def test_non_finite_ignored(self):
        h = Histogram("h")
        h.observe(float("nan"))
        h.observe(float("inf"))
        assert h.snapshot() == []

    def test_time_context_manager(self):
        h = Histogram("h")
        with h.time():
            pass
        snap = h.snapshot()
        assert snap[0]["count"] == 1
        assert snap[0]["sum"] >= 0.0

    def test_invalid_buckets_fallback(self):
        h = Histogram("h", buckets=(-1.0, 0.0))
        # falsy buckets removed → default kicks in
        assert len(h.buckets) > 0
        assert all(b > 0 for b in h.buckets)


class TestRegistry:
    def test_idempotent_registration(self):
        reg = MetricsRegistry()
        c1 = reg.counter("trades")
        c2 = reg.counter("trades")
        assert c1 is c2

    def test_global_singleton(self):
        assert get_registry() is get_registry()

    def test_render_prometheus(self):
        reg = MetricsRegistry()
        reg.counter("api_calls", "calls to /api").inc(3, labels={"route": "health"})
        reg.gauge("queue_depth", "pending jobs").set(7)
        reg.histogram("lat", "latency", buckets=(0.1, 1.0)).observe(0.5)
        lines = reg.render_prometheus()
        text = "\n".join(lines)
        assert "# TYPE api_calls counter" in text
        assert 'api_calls{route="health"} 3' in text
        assert "# TYPE queue_depth gauge" in text
        assert "queue_depth 7" in text
        assert "# TYPE lat histogram" in text
        assert 'lat_bucket{le="0.1"} 0' in text
        assert 'lat_bucket{le="1"} 1' in text
        assert 'lat_bucket{le="+Inf"} 1' in text
        assert "lat_count 1" in text

    def test_reset(self):
        reg = MetricsRegistry()
        reg.counter("x").inc()
        reg.reset()
        assert reg.render_prometheus() == []

    def test_label_escaping(self):
        reg = MetricsRegistry()
        reg.counter("c").inc(labels={"msg": 'with "quote" and \\ back'})
        rendered = "\n".join(reg.render_prometheus())
        assert r"\"quote\"" in rendered
        assert r"\\" in rendered


@pytest.fixture(autouse=True)
def _reset_global_registry():
    yield
    get_registry().reset()
