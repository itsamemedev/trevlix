"""TREVLIX – Auto-Healing Agent Service.

Monitors system health and performs automatic recovery when issues
are detected. Checks the bot trading loop heartbeat, database pool,
exchange API connectivity, and notification services.

Usage:
    from services.auto_healing import AutoHealingAgent

    healer = AutoHealingAgent(db=db_manager, config=CONFIG)
    healer.start()

    # From the trading loop, call periodically:
    healer.heartbeat()

    # Dashboard snapshot:
    status = healer.health_snapshot()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from trevlix_i18n import t

log = logging.getLogger("trevlix.healing")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CHECK_INTERVAL: int = 30  # seconds
_HEARTBEAT_TIMEOUT: int = 120  # seconds without heartbeat → stalled
_MEMORY_THRESHOLD: float = 90.0  # percent
_ESCALATION_WINDOW: int = 600  # 10 minutes in seconds
_ESCALATION_LIMIT: int = 3  # failures within window before escalation


class ServiceName(str, Enum):
    """Identifiers for each monitored subsystem."""

    BOT_LOOP = "bot_loop"
    DATABASE = "database"
    EXCHANGE = "exchange"
    NOTIFICATIONS = "notifications"
    MEMORY = "memory"


class Severity(str, Enum):
    """Incident severity levels."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Incident:
    """A single recorded health incident."""

    timestamp: datetime
    service: ServiceName
    severity: Severity
    message: str
    recovered: bool = False


@dataclass
class _ServiceTracker:
    """Internal tracker for per-service failure history."""

    failures: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    recovery_attempts: int = 0
    last_status_ok: bool = True
    escalated: bool = False


class AutoHealingAgent:
    """Background agent that monitors system health and self-heals.

    Runs a daemon thread that periodically checks critical subsystems.
    When a failure is detected the agent attempts a soft recovery,
    logs the incident, and optionally notifies via Discord / Telegram.
    If the same service fails more than *_ESCALATION_LIMIT* times
    within *_ESCALATION_WINDOW* seconds the issue is escalated.

    Args:
        db: MySQLManager instance (from server.py).
        config: Application configuration dictionary.
        notifier: Optional callback ``(message: str) -> None`` used
            to send alerts via Discord / Telegram.
        check_interval: Seconds between health checks (default 30).
        heartbeat_timeout: Seconds before a missing heartbeat is
            considered a stall (default 120).
    """

    def __init__(
        self,
        db: Any,
        config: dict[str, Any],
        notifier: Callable[[str], None] | None = None,
        check_interval: int = _DEFAULT_CHECK_INTERVAL,
        heartbeat_timeout: int = _HEARTBEAT_TIMEOUT,
    ) -> None:
        self._db = db
        self._config = config
        self._notifier = notifier
        self._check_interval = max(check_interval, 5)
        self._heartbeat_timeout = heartbeat_timeout

        # Thread safety
        self._lock = threading.Lock()

        # Heartbeat tracking
        self._last_heartbeat: float = time.monotonic()

        # Per-service trackers
        self._trackers: dict[ServiceName, _ServiceTracker] = {
            svc: _ServiceTracker() for svc in ServiceName
        }

        # Incident log (bounded to prevent unbounded growth)
        self._incidents: deque[Incident] = deque(maxlen=500)

        # Control flags
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._running:
                log.warning("AutoHealingAgent already running")
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="trevlix-auto-healer",
                daemon=True,
            )
            self._thread.start()
            log.info("AutoHealingAgent started (interval=%ds)", self._check_interval)

    def stop(self) -> None:
        """Signal the monitoring thread to stop."""
        with self._lock:
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._check_interval + 5)
            self._thread = None
        log.info("AutoHealingAgent stopped")

    def heartbeat(self) -> None:
        """Record a heartbeat from the trading loop.

        Call this method periodically from the main bot loop so the
        agent knows the loop is still alive.
        """
        with self._lock:
            self._last_heartbeat = time.monotonic()

    def health_snapshot(self) -> dict[str, Any]:
        """Return a point-in-time health status for the dashboard.

        Returns:
            Dictionary with per-service status, recent incidents,
            and overall system health.
        """
        with self._lock:
            services: dict[str, dict[str, Any]] = {}
            for svc, tracker in self._trackers.items():
                services[svc.value] = {
                    "healthy": tracker.last_status_ok,
                    "recovery_attempts": tracker.recovery_attempts,
                    "escalated": tracker.escalated,
                }

            recent = [
                {
                    "timestamp": inc.timestamp.isoformat(),
                    "service": inc.service.value,
                    "severity": inc.severity.value,
                    "message": inc.message,
                    "recovered": inc.recovered,
                }
                for inc in list(self._incidents)[-20:]
            ]

            all_ok = all(trk.last_status_ok for trk in self._trackers.values())

        return {
            "healthy": all_ok,
            "services": services,
            "recent_incidents": recent,
            "check_interval": self._check_interval,
            "heartbeat_timeout": self._heartbeat_timeout,
        }

    @property
    def is_running(self) -> bool:
        """Whether the monitoring thread is active."""
        return self._running

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main monitoring loop executed in the daemon thread."""
        log.debug("Healing loop entered")
        while self._running:
            try:
                self._check_all()
            except Exception as exc:
                log.exception("Unexpected error in healing loop: %s", exc)
            # Sleep in small increments so stop() is responsive
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_all(self) -> None:
        """Run every health check in sequence."""
        self._check_heartbeat()
        self._check_database()
        self._check_exchange()
        self._check_notifications()
        self._check_memory()

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_heartbeat(self) -> None:
        """Detect stalled bot trading loop via heartbeat age."""
        with self._lock:
            age = time.monotonic() - self._last_heartbeat

        if age > self._heartbeat_timeout:
            self._record_failure(
                ServiceName.BOT_LOOP,
                Severity.CRITICAL,
                f"Bot loop stalled – no heartbeat for {int(age)}s "
                f"(threshold {self._heartbeat_timeout}s)",
            )
        else:
            self._mark_healthy(ServiceName.BOT_LOOP)

    def _check_database(self) -> None:
        """Verify the database connection pool is responsive."""
        try:
            if not getattr(self._db, "db_available", False):
                raise ConnectionError("db_available flag is False")

            pool = getattr(self._db, "_pool", None)
            if pool is not None:
                conn = pool.acquire()
                try:
                    conn.ping(reconnect=True)
                finally:
                    pool.release(conn)
            self._mark_healthy(ServiceName.DATABASE)
        except Exception as exc:
            self._record_failure(
                ServiceName.DATABASE,
                Severity.ERROR,
                f"Database health check failed: {exc}",
            )
            self._attempt_db_recovery()

    def _check_exchange(self) -> None:
        """Verify the exchange API is reachable."""
        try:
            exchange_inst = self._config.get("_exchange_instance")
            if exchange_inst is None:
                # No exchange configured – skip
                self._mark_healthy(ServiceName.EXCHANGE)
                return

            # Use CCXT load_markets or fetch_time as a lightweight ping
            if hasattr(exchange_inst, "fetch_time"):
                exchange_inst.fetch_time()
            elif hasattr(exchange_inst, "load_markets"):
                exchange_inst.load_markets()
            self._mark_healthy(ServiceName.EXCHANGE)
        except Exception as exc:
            self._record_failure(
                ServiceName.EXCHANGE,
                Severity.ERROR,
                f"Exchange API unreachable: {exc}",
            )
            self._attempt_exchange_recovery()

    def _check_notifications(self) -> None:
        """Check if notification services appear configured."""
        discord_url = self._config.get("discord_webhook", "")
        telegram_token = self._config.get("telegram_token", "")
        if discord_url or telegram_token:
            self._mark_healthy(ServiceName.NOTIFICATIONS)
        # If neither is configured, skip check – not a failure, just unconfigured

    def _check_memory(self) -> None:
        """Check process memory usage via /proc/self/status."""
        usage_pct = self._read_memory_percent()
        if usage_pct is None:
            # Cannot determine – skip silently
            self._mark_healthy(ServiceName.MEMORY)
            return

        if usage_pct > _MEMORY_THRESHOLD:
            self._record_failure(
                ServiceName.MEMORY,
                Severity.WARNING,
                f"Memory usage at {usage_pct:.1f}% (threshold {_MEMORY_THRESHOLD}%)",
            )
        else:
            self._mark_healthy(ServiceName.MEMORY)

    # ------------------------------------------------------------------
    # Recovery actions
    # ------------------------------------------------------------------

    def _attempt_db_recovery(self) -> None:
        """Try to re-establish the database connection pool.

        Uses public methods where available to avoid breaking encapsulation.
        Falls back to connection test via ping as verification.
        """
        log.info("Attempting database recovery...")
        try:
            # Prefer public reconnect/init methods
            if hasattr(self._db, "reconnect"):
                self._db.reconnect()
            elif hasattr(self._db, "_init_db"):
                self._db._init_db()
            else:
                # Last resort: test with a simple query to trigger reconnection
                self._db.execute_query("SELECT 1")

            if getattr(self._db, "db_available", False):
                log.info("Database recovery successful")
                self._mark_healthy(ServiceName.DATABASE)
                return
            log.warning("Database recovery: db_available still False")
        except Exception as exc:
            log.error("Database recovery failed: %s", exc)

    def _attempt_exchange_recovery(self) -> None:
        """Try to reinitialise the exchange connection."""
        log.info("Attempting exchange recovery...")
        try:
            exchange_inst = self._config.get("_exchange_instance")
            if exchange_inst is None:
                return
            # CCXT exchanges can be re-loaded by calling load_markets
            if hasattr(exchange_inst, "load_markets"):
                exchange_inst.load_markets(reload=True)
                log.info("Exchange recovery successful")
                self._mark_healthy(ServiceName.EXCHANGE)
        except Exception as exc:
            log.error("Exchange recovery failed: %s", exc)

    # ------------------------------------------------------------------
    # Incident tracking & escalation
    # ------------------------------------------------------------------

    def _record_failure(
        self,
        service: ServiceName,
        severity: Severity,
        message: str,
    ) -> None:
        """Log a failure, update tracker, and escalate if needed."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc)

        incident = Incident(
            timestamp=now_utc,
            service=service,
            severity=severity,
            message=message,
        )

        with self._lock:
            tracker = self._trackers[service]
            tracker.last_status_ok = False
            tracker.recovery_attempts += 1
            tracker.failures.append(now_mono)
            self._incidents.append(incident)

            # Check escalation: >N failures within window
            cutoff = now_mono - _ESCALATION_WINDOW
            recent = sum(1 for ts in tracker.failures if ts > cutoff)
            should_escalate = recent >= _ESCALATION_LIMIT and not tracker.escalated
            if should_escalate:
                tracker.escalated = True

        log.warning(
            "[%s] %s – %s",
            severity.value.upper(),
            service.value,
            message,
        )

        if should_escalate:
            self._escalate(service, recent)
        else:
            self._notify(f"[{severity.value.upper()}] {service.value}: {message}")

    def _mark_healthy(self, service: ServiceName) -> None:
        """Mark a service as healthy, resetting escalation if needed."""
        with self._lock:
            tracker = self._trackers[service]
            was_down = not tracker.last_status_ok
            tracker.last_status_ok = True
            tracker.escalated = False

        if was_down:
            log.info("Service recovered: %s", service.value)
            self._notify(
                t(
                    "healing_recovered",
                    lang=self._config.get("language", "en"),
                )
                + f" {service.value}"
            )

    def _escalate(self, service: ServiceName, failure_count: int) -> None:
        """Handle repeated failures that exceed the escalation threshold."""
        msg = (
            f"ESCALATION: {service.value} failed {failure_count} times "
            f"in the last {_ESCALATION_WINDOW // 60} minutes. "
            "Manual intervention may be required."
        )
        log.critical(msg)
        self._notify(msg)

    def _notify(self, message: str) -> None:
        """Send an alert through the configured notifier callback."""
        if self._notifier is None:
            return
        try:
            self._notifier(message)
        except Exception as exc:
            log.error("Notification delivery failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_memory_percent() -> float | None:
        """Read process memory usage from /proc/self/status.

        Returns:
            Memory usage as a percentage of VmPeak, or None if
            the information is unavailable.
        """
        try:
            if not os.path.exists("/proc/self/status"):
                return None

            vm_rss: int | None = None
            mem_total: int | None = None

            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        vm_rss = int(line.split()[1])  # kB
                        break

            if vm_rss is None:
                return None

            # Read total system memory from /proc/meminfo
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_total = int(line.split()[1])  # kB
                            break

            if mem_total is None or mem_total == 0:
                return None

            return (vm_rss / mem_total) * 100.0
        except (OSError, ValueError, IndexError):
            return None
