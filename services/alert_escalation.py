"""TREVLIX – Alert Escalation Manager.

Provides tiered alert escalation with automatic severity progression.
Integrates with Auto-Healing, Revenue Tracking, and Cluster Control agents
to ensure critical issues receive appropriate attention.

Usage:
    from services.alert_escalation import AlertEscalationManager

    escalation = AlertEscalationManager(config=CONFIG, notifier=notify_fn)
    escalation.raise_alert(
        "exchange_down", "Binance API unreachable", source="auto_healing"
    )
    escalation.get_active_alerts()
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

log = logging.getLogger("trevlix.escalation")


class AlertLevel(IntEnum):
    """Alert severity levels with automatic escalation."""

    INFO = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3


@dataclass
class Alert:
    """A single alert record with escalation tracking."""

    alert_id: str
    message: str
    source: str
    level: AlertLevel
    created_at: datetime
    escalated_at: datetime | None = None
    acknowledged: bool = False
    occurrence_count: int = 1
    last_occurrence: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialise the alert to a plain dict."""
        return {
            "alert_id": self.alert_id,
            "message": self.message,
            "source": self.source,
            "level": self.level.name,
            "level_value": int(self.level),
            "created_at": self.created_at.isoformat(),
            "escalated_at": (self.escalated_at.isoformat() if self.escalated_at else None),
            "acknowledged": self.acknowledged,
            "occurrence_count": self.occurrence_count,
            "last_occurrence": self.last_occurrence.isoformat(),
        }


class AlertEscalationManager:
    """Manages alert lifecycle and automatic escalation.

    Features:
        - Tiered escalation: INFO -> WARNING -> CRITICAL -> EMERGENCY
        - Auto-escalate on repeated occurrences within time window
        - Deduplication of identical alerts
        - Notification on each escalation level change
        - Alert acknowledgement to suppress further notifications
        - History tracking (last 200 alerts)
        - Persist alerts to database
    """

    _HISTORY_MAXLEN = 200

    def __init__(
        self,
        db: Any = None,
        config: dict[str, Any] | None = None,
        notifier: Callable[..., Any] | None = None,
    ) -> None:
        """Initialise the escalation manager.

        Args:
            db: Database pool instance with ``_get_conn()``
                context manager.  Optional.
            config: Configuration dict.  Recognised keys:
                - ``escalation_window`` (int): Seconds within which
                  repeated occurrences trigger escalation.
                  Defaults to 300 (5 min).
                - ``escalation_threshold`` (int): Number of
                  occurrences before escalation.  Defaults to 3.
                - ``auto_resolve_minutes`` (int): Minutes of silence
                  before auto-resolving an alert.  Defaults to 60.
            notifier: Callable invoked on alert state changes.
                Receives ``(message: str)`` as single argument.
        """
        self._db = db
        self._config = config or {}
        self._notifier = notifier
        self._active: dict[str, Alert] = {}
        self._history: deque[Alert] = deque(maxlen=self._HISTORY_MAXLEN)
        self._lock = threading.Lock()

        self._escalation_window: int = int(self._config.get("escalation_window", 300))
        self._escalation_threshold: int = int(self._config.get("escalation_threshold", 3))
        self._auto_resolve_minutes: int = int(self._config.get("auto_resolve_minutes", 60))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def raise_alert(
        self,
        alert_id: str,
        message: str,
        source: str = "system",
        level: AlertLevel = AlertLevel.WARNING,
    ) -> Alert:
        """Raise or escalate an alert.

        If *alert_id* already exists and is active, increment the
        occurrence count and potentially auto-escalate.  Otherwise
        create a new alert.

        Args:
            alert_id: Unique identifier for this alert type.
            message: Human-readable description.
            source: Originating agent (e.g. ``auto_healing``).
            level: Initial severity level for new alerts.

        Returns:
            The current :class:`Alert` state.
        """
        now = datetime.now(UTC)
        with self._lock:
            existing = self._active.get(alert_id)

            if existing is not None:
                existing.occurrence_count += 1
                existing.last_occurrence = now

                if not existing.acknowledged:
                    within_window = (
                        now - existing.created_at
                    ).total_seconds() <= self._escalation_window or (
                        existing.escalated_at
                        and (now - existing.escalated_at).total_seconds() <= self._escalation_window
                    )
                    threshold_met = existing.occurrence_count % self._escalation_threshold == 0
                    if within_window and threshold_met and existing.level < AlertLevel.EMERGENCY:
                        existing.level = AlertLevel(existing.level + 1)
                        existing.escalated_at = now
                        self._notify(existing, action="escalated")

                self._persist(existing)
                return existing

            alert = Alert(
                alert_id=alert_id,
                message=message,
                source=source,
                level=level,
                created_at=now,
                last_occurrence=now,
            )
            self._active[alert_id] = alert
            self._notify(alert, action="raised")
            self._persist(alert)
            return alert

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert to suppress further notifications.

        Args:
            alert_id: The alert to acknowledge.

        Returns:
            ``True`` if the alert was found and acknowledged.
        """
        with self._lock:
            alert = self._active.get(alert_id)
            if alert is None:
                return False
            alert.acknowledged = True
            self._persist(alert)
            log.info("Alert acknowledged: %s", alert_id)
            return True

    def resolve(self, alert_id: str) -> bool:
        """Resolve and archive an alert.

        Moves the alert from the active set into the history ring
        buffer.

        Args:
            alert_id: The alert to resolve.

        Returns:
            ``True`` if the alert was found and resolved.
        """
        with self._lock:
            alert = self._active.pop(alert_id, None)
            if alert is None:
                return False
            self._history.append(alert)
            self._persist_resolved(alert)
            log.info("Alert resolved: %s", alert_id)
            return True

    def auto_resolve_stale(self) -> list[str]:
        """Resolve alerts that haven't recurred recently.

        Any active alert whose ``last_occurrence`` is older than
        ``auto_resolve_minutes`` will be automatically resolved.

        Returns:
            List of resolved alert IDs.
        """
        now = datetime.now(UTC)
        threshold_seconds = self._auto_resolve_minutes * 60
        resolved: list[str] = []

        with self._lock:
            stale_ids = [
                aid
                for aid, alert in self._active.items()
                if (now - alert.last_occurrence).total_seconds() >= threshold_seconds
            ]
            for aid in stale_ids:
                alert = self._active.pop(aid)
                self._history.append(alert)
                self._persist_resolved(alert)
                resolved.append(aid)

        if resolved:
            log.info(
                "Auto-resolved %d stale alert(s): %s",
                len(resolved),
                ", ".join(resolved),
            )
        return resolved

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Return all active alerts sorted by level (highest first).

        Returns:
            List of alert dicts.
        """
        with self._lock:
            alerts = sorted(
                self._active.values(),
                key=lambda a: a.level,
                reverse=True,
            )
            return [a.to_dict() for a in alerts]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent alert history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of alert dicts, most recent first.
        """
        with self._lock:
            items = list(self._history)[-limit:]
            items.reverse()
            return [a.to_dict() for a in items]

    def snapshot(self) -> dict[str, Any]:
        """Return a dashboard-ready snapshot of escalation state.

        Returns:
            Dict with ``active_count``, ``active_alerts``,
            ``highest_level``, ``emergency_active``, and
            ``recent_history`` (last 10).
        """
        with self._lock:
            active = sorted(
                self._active.values(),
                key=lambda a: a.level,
                reverse=True,
            )
            active_dicts = [a.to_dict() for a in active]

            highest = max(a.level for a in active) if active else None
            emergency = any(a.level == AlertLevel.EMERGENCY for a in active)

            history_items = list(self._history)[-10:]
            history_items.reverse()

            return {
                "active_count": len(active_dicts),
                "active_alerts": active_dicts,
                "highest_level": (highest.name if highest is not None else None),
                "emergency_active": emergency,
                "recent_history": [a.to_dict() for a in history_items],
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _notify(self, alert: Alert, action: str = "raised") -> None:
        """Send notification for an alert state change.

        Notification behaviour varies by level:
            - INFO: log only, no external notification.
            - WARNING: single notification.
            - CRITICAL: notification with emphasis.
            - EMERGENCY: notification prefixed with alarm emoji.

        Args:
            alert: The alert to notify about.
            action: Description of the state change
                (e.g. ``raised``, ``escalated``).
        """
        level_prefix = {
            AlertLevel.INFO: "[INFO]",
            AlertLevel.WARNING: "[WARNING]",
            AlertLevel.CRITICAL: "[CRITICAL]",
            AlertLevel.EMERGENCY: "\U0001f6a8 [EMERGENCY]",
        }
        prefix = level_prefix.get(alert.level, "[ALERT]")
        text = (
            f"{prefix} Alert {action}: {alert.alert_id} "
            f"– {alert.message} "
            f"(source={alert.source}, "
            f"occurrences={alert.occurrence_count})"
        )

        log.log(
            logging.CRITICAL
            if alert.level >= AlertLevel.CRITICAL
            else logging.WARNING
            if alert.level == AlertLevel.WARNING
            else logging.INFO,
            text,
        )

        if alert.level == AlertLevel.INFO:
            return

        if self._notifier is not None:
            try:
                self._notifier(text)
            except Exception:
                log.exception(
                    "Failed to send notification for alert %s",
                    alert.alert_id,
                )

    def _persist(self, alert: Alert) -> None:
        """Persist alert to the ``alert_escalations`` table.

        Silently logs errors to avoid disrupting calling code.

        Args:
            alert: The alert to persist.
        """
        if self._db is None:
            return
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO alert_escalations
                            (alert_id, message, source, level,
                             occurrence_count, created_at,
                             escalated_at, acknowledged,
                             resolved_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                                NULL)
                        ON DUPLICATE KEY UPDATE
                            level = VALUES(level),
                            occurrence_count =
                                VALUES(occurrence_count),
                            escalated_at = VALUES(escalated_at),
                            acknowledged = VALUES(acknowledged)
                        """,
                        (
                            alert.alert_id,
                            alert.message,
                            alert.source,
                            int(alert.level),
                            alert.occurrence_count,
                            alert.created_at,
                            alert.escalated_at,
                            alert.acknowledged,
                        ),
                    )
                conn.commit()
        except Exception:
            log.exception("Failed to persist alert %s", alert.alert_id)

    def _persist_resolved(self, alert: Alert) -> None:
        """Mark an alert as resolved in the database.

        Args:
            alert: The alert that was resolved.
        """
        if self._db is None:
            return
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """UPDATE alert_escalations
                        SET resolved_at = %s
                        WHERE alert_id = %s
                        """,
                        (datetime.now(UTC), alert.alert_id),
                    )
                conn.commit()
        except Exception:
            log.exception(
                "Failed to persist resolved state for alert %s",
                alert.alert_id,
            )
