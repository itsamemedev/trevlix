"""
TREVLIX Tests – Alert Escalation Manager
==========================================

Tests for the AlertEscalationManager service that provides tiered
alert escalation with automatic severity progression.

Run with:  pytest tests/test_alert_escalation.py -v
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.core.time_compat import UTC

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.alert_escalation import (
    Alert,
    AlertEscalationManager,
    AlertLevel,
)


def _make_manager(
    threshold: int = 3,
    window: int = 300,
    auto_resolve_minutes: int = 60,
    notifier=None,
) -> AlertEscalationManager:
    """Create an AlertEscalationManager with no DB."""
    config = {
        "escalation_threshold": threshold,
        "escalation_window": window,
        "auto_resolve_minutes": auto_resolve_minutes,
    }
    return AlertEscalationManager(
        db=None,
        config=config,
        notifier=notifier,
    )


class TestRaiseAlert:
    """Tests for raising alerts."""

    def test_raise_alert_creates_new(self) -> None:
        """Raise an alert, verify it appears in active alerts."""
        mgr = _make_manager()
        alert = mgr.raise_alert(
            "test_alert",
            "Something broke",
            source="unit_test",
        )

        assert isinstance(alert, Alert)
        assert alert.alert_id == "test_alert"
        assert alert.occurrence_count == 1

        active = mgr.get_active_alerts()
        assert len(active) == 1
        assert active[0]["alert_id"] == "test_alert"

    def test_raise_alert_increments_count(self) -> None:
        """Raise same alert twice, verify count=2."""
        mgr = _make_manager()
        mgr.raise_alert("dup", "first")
        alert = mgr.raise_alert("dup", "first")

        assert alert.occurrence_count == 2


class TestEscalation:
    """Tests for automatic escalation."""

    def test_auto_escalation(self) -> None:
        """Raise alert N times (threshold), verify level increases."""
        mgr = _make_manager(threshold=3, window=600)

        for _ in range(3):
            alert = mgr.raise_alert(
                "esc_test",
                "repeated failure",
                level=AlertLevel.WARNING,
            )

        # After 3 occurrences it should escalate from WARNING
        assert alert.level >= AlertLevel.CRITICAL

    def test_max_escalation_level(self) -> None:
        """Verify can't escalate beyond EMERGENCY."""
        mgr = _make_manager(threshold=2, window=600)

        # Start at CRITICAL so one escalation reaches EMERGENCY
        mgr.raise_alert(
            "max_test",
            "critical issue",
            level=AlertLevel.CRITICAL,
        )
        # 2nd occurrence triggers escalation to EMERGENCY
        mgr.raise_alert("max_test", "critical issue")
        # 3rd + 4th should not go beyond EMERGENCY
        mgr.raise_alert("max_test", "critical issue")
        alert = mgr.raise_alert("max_test", "critical issue")

        assert alert.level == AlertLevel.EMERGENCY


class TestAcknowledge:
    """Tests for alert acknowledgement."""

    def test_acknowledge_alert(self) -> None:
        """Acknowledge an alert, verify no more escalation."""
        mgr = _make_manager(threshold=3, window=600)

        mgr.raise_alert("ack_test", "issue")
        result = mgr.acknowledge("ack_test")
        assert result is True

        active = mgr.get_active_alerts()
        assert active[0]["acknowledged"] is True

        # Further raises should not escalate
        for _ in range(5):
            alert = mgr.raise_alert("ack_test", "issue")
        assert alert.level == AlertLevel.WARNING  # unchanged


class TestResolve:
    """Tests for alert resolution."""

    def test_resolve_alert(self) -> None:
        """Resolve an alert, verify moved to history."""
        mgr = _make_manager()
        mgr.raise_alert("resolve_me", "transient issue")

        result = mgr.resolve("resolve_me")
        assert result is True
        assert len(mgr.get_active_alerts()) == 0

        history = mgr.get_history()
        assert len(history) == 1
        assert history[0]["alert_id"] == "resolve_me"

    def test_resolve_nonexistent_returns_false(self) -> None:
        """Resolving a non-existent alert returns False."""
        mgr = _make_manager()
        assert mgr.resolve("ghost") is False


class TestAutoResolve:
    """Tests for automatic stale alert resolution."""

    def test_auto_resolve_stale(self) -> None:
        """Create old alert, run auto_resolve, verify resolved."""
        mgr = _make_manager(auto_resolve_minutes=60)
        alert = mgr.raise_alert("stale_alert", "old issue")

        # Manually backdate the last_occurrence
        alert.last_occurrence = datetime.now(UTC) - timedelta(
            minutes=120,
        )

        resolved_ids = mgr.auto_resolve_stale()
        assert "stale_alert" in resolved_ids
        assert len(mgr.get_active_alerts()) == 0

    def test_auto_resolve_keeps_fresh(self) -> None:
        """Fresh alerts should not be auto-resolved."""
        mgr = _make_manager(auto_resolve_minutes=60)
        mgr.raise_alert("fresh_alert", "just happened")

        resolved_ids = mgr.auto_resolve_stale()
        assert len(resolved_ids) == 0
        assert len(mgr.get_active_alerts()) == 1


class TestSorting:
    """Tests for alert ordering."""

    def test_get_active_alerts_sorted(self) -> None:
        """Multiple alerts, verify sorted by level desc."""
        mgr = _make_manager()
        mgr.raise_alert(
            "low",
            "info issue",
            level=AlertLevel.WARNING,
        )
        mgr.raise_alert(
            "high",
            "critical issue",
            level=AlertLevel.CRITICAL,
        )
        mgr.raise_alert(
            "mid",
            "warning issue",
            level=AlertLevel.WARNING,
        )

        active = mgr.get_active_alerts()
        levels = [a["level_value"] for a in active]
        assert levels == sorted(levels, reverse=True)
        assert active[0]["alert_id"] == "high"


class TestSnapshot:
    """Tests for the snapshot() method."""

    def test_snapshot_structure(self) -> None:
        """Verify snapshot dict keys."""
        mgr = _make_manager()
        mgr.raise_alert("snap_test", "test")

        snap = mgr.snapshot()
        expected_keys = {
            "active_count",
            "active_alerts",
            "highest_level",
            "emergency_active",
            "recent_history",
        }
        assert expected_keys.issubset(snap.keys())
        assert snap["active_count"] == 1
        assert snap["emergency_active"] is False


class TestNotifier:
    """Tests for notifier callback integration."""

    def test_notifier_called_on_escalation(self) -> None:
        """Verify notifier callback is called on escalation."""
        notifier = Mock()
        mgr = _make_manager(
            threshold=3,
            window=600,
            notifier=notifier,
        )

        for _ in range(3):
            mgr.raise_alert(
                "notify_test",
                "repeated failure",
                level=AlertLevel.WARNING,
            )

        # Notifier called on initial raise + escalation (not every occurrence)
        assert notifier.call_count >= 2

    def test_notifier_not_called_for_info(self) -> None:
        """INFO level alerts should not trigger notifier."""
        notifier = Mock()
        mgr = _make_manager(notifier=notifier)

        mgr.raise_alert(
            "info_test",
            "informational",
            level=AlertLevel.INFO,
        )

        notifier.assert_not_called()
