"""
TREVLIX Tests – Auto-Healing Agent
====================================

Tests for the AutoHealingAgent service that monitors system health
and performs automatic recovery.

Run with:  pytest tests/test_auto_healing.py -v
"""

import os
import sys
import time
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auto_healing import (
    _ESCALATION_LIMIT,
    AutoHealingAgent,
    Incident,
    ServiceName,
    Severity,
)


class TestAutoHealingAgent:
    """Tests for the AutoHealingAgent."""

    def _make_agent(
        self,
        notifier: Mock | None = None,
        check_interval: int = 30,
        heartbeat_timeout: int = 120,
    ) -> AutoHealingAgent:
        """Create an AutoHealingAgent with mocked dependencies."""
        db = MagicMock()
        db.db_available = True
        config: dict = {"language": "en"}
        return AutoHealingAgent(
            db=db,
            config=config,
            notifier=notifier,
            check_interval=check_interval,
            heartbeat_timeout=heartbeat_timeout,
        )

    def test_init_defaults(self) -> None:
        """Verify default config values after initialisation."""
        agent = self._make_agent()
        assert agent._check_interval == 30
        assert agent._heartbeat_timeout == 120
        assert agent._running is False
        assert agent._thread is None
        assert len(agent._trackers) == len(ServiceName)
        assert len(agent._incidents) == 0

    def test_heartbeat_updates_timestamp(self) -> None:
        """Calling heartbeat() updates _last_heartbeat."""
        agent = self._make_agent()
        before = agent._last_heartbeat
        time.sleep(0.01)
        agent.heartbeat()
        assert agent._last_heartbeat > before

    def test_health_snapshot_structure(self) -> None:
        """Snapshot returns the expected top-level keys."""
        agent = self._make_agent()
        snap = agent.health_snapshot()
        expected_keys = {
            "healthy",
            "services",
            "recent_incidents",
            "check_interval",
            "heartbeat_timeout",
        }
        assert set(snap.keys()) == expected_keys
        assert isinstance(snap["services"], dict)
        assert isinstance(snap["recent_incidents"], list)
        assert snap["healthy"] is True

    def test_start_stop_lifecycle(self) -> None:
        """Start sets is_running, stop clears it."""
        agent = self._make_agent(check_interval=600)
        assert agent.is_running is False
        agent.start()
        assert agent.is_running is True
        assert agent._thread is not None
        agent.stop()
        assert agent.is_running is False
        assert agent._thread is None

    def test_memory_check_reads_proc(self) -> None:
        """Mock /proc files to verify memory percentage calculation."""
        proc_status = "VmRSS:\t500000 kB\n"
        proc_meminfo = "MemTotal:\t1000000 kB\n"

        def mock_open_files(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            from io import StringIO

            if path == "/proc/self/status":
                return StringIO(proc_status)
            if path == "/proc/meminfo":
                return StringIO(proc_meminfo)
            raise FileNotFoundError(path)

        with (
            patch("builtins.open", side_effect=mock_open_files),
            patch("os.path.exists", return_value=True),
        ):
            result = AutoHealingAgent._read_memory_percent()
        assert result is not None
        assert abs(result - 50.0) < 0.01

    def test_escalation_on_repeated_failures(self) -> None:
        """Simulate 3+ failures within window to trigger escalation."""
        notifier = Mock()
        agent = self._make_agent(notifier=notifier)

        for _ in range(_ESCALATION_LIMIT):
            agent._record_failure(
                ServiceName.DATABASE,
                Severity.ERROR,
                "db connection failed",
            )

        tracker = agent._trackers[ServiceName.DATABASE]
        assert tracker.escalated is True
        # The final call should produce an ESCALATION message
        escalation_calls = [c for c in notifier.call_args_list if "ESCALATION" in str(c)]
        assert len(escalation_calls) >= 1

    def test_record_failure_creates_incident(self) -> None:
        """Recording a failure creates and stores an Incident."""
        agent = self._make_agent()
        agent._record_failure(
            ServiceName.EXCHANGE,
            Severity.WARNING,
            "exchange timeout",
        )
        assert len(agent._incidents) == 1
        inc = agent._incidents[0]
        assert isinstance(inc, Incident)
        assert inc.service == ServiceName.EXCHANGE
        assert inc.severity == Severity.WARNING
        assert inc.message == "exchange timeout"
        assert inc.recovered is False

    def test_mark_healthy_resets_tracker(self) -> None:
        """Marking a service healthy resets escalated and last_status_ok."""
        agent = self._make_agent()
        tracker = agent._trackers[ServiceName.DATABASE]
        tracker.last_status_ok = False
        tracker.escalated = True

        agent._mark_healthy(ServiceName.DATABASE)

        assert tracker.last_status_ok is True
        assert tracker.escalated is False

    def test_db_recovery_attempt(self) -> None:
        """Verify database recovery is attempted when DB check fails."""
        agent = self._make_agent()
        agent._db.db_available = False
        agent._db.reconnect = Mock()

        agent._check_database()

        agent._db.reconnect.assert_called_once()

    def test_notifier_callback_called(self) -> None:
        """Verify the notifier callback is invoked on incidents."""
        notifier = Mock()
        agent = self._make_agent(notifier=notifier)

        agent._record_failure(
            ServiceName.MEMORY,
            Severity.WARNING,
            "high memory usage",
        )

        notifier.assert_called_once()
        call_arg = notifier.call_args[0][0]
        assert "high memory usage" in call_arg
