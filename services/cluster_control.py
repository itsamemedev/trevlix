"""
TREVLIX – Multi-Server Control Agent
======================================
Manages a cluster of remote TREVLIX nodes: health-checking, command
execution, metric aggregation, and coordinated deployments.

Usage:
    from services.cluster_control import ClusterController

    ctrl = ClusterController(
        config={"health_interval": 30},
        notifier=my_callback,
    )
    ctrl.add_node("us-east", "10.0.1.5", 5000, "tok_abc123")
    ctrl.start_bot("us-east")
    metrics = ctrl.get_cluster_metrics()
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import requests

log = logging.getLogger("trevlix.cluster")

_DEFAULT_TIMEOUT = 5  # seconds
_DEFAULT_HEALTH_INTERVAL = 30  # seconds

# Private/reserved IP ranges that must not be used as cluster node hosts
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _validate_host(host: str) -> None:
    """Validate that a host is not a private/reserved IP (SSRF prevention).

    Args:
        host: Hostname or IP address string.

    Raises:
        ValueError: If the host resolves to a blocked IP range.
    """
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # It's a hostname – resolve it first
        try:
            resolved = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            addrs = {ipaddress.ip_address(r[4][0]) for r in resolved}
        except socket.gaierror as e:
            raise ValueError(f"Cannot resolve hostname: {host}") from e
        for addr in addrs:
            for net in _BLOCKED_NETWORKS:
                if addr in net:
                    raise ValueError(f"Host '{host}' resolves to blocked IP range {net}") from None
        return

    for net in _BLOCKED_NETWORKS:
        if addr in net:
            raise ValueError(f"Host '{host}' is in blocked IP range {net}")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class NodeStatus(StrEnum):
    """Possible states for a remote node."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


@dataclass
class NodeInfo:
    """Registry entry for a single remote TREVLIX node."""

    name: str
    host: str
    port: int
    api_token: str
    status: NodeStatus = NodeStatus.OFFLINE
    last_check: datetime | None = None
    last_error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL for this node."""
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict[str, Any]:
        """Serialise node info for API / dashboard consumption."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "status": self.status.value,
            "last_check": (self.last_check.isoformat() if self.last_check else None),
            "last_error": self.last_error,
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# Cluster controller
# ---------------------------------------------------------------------------


class ClusterController:
    """Manage, monitor, and command a fleet of remote TREVLIX nodes.

    Parameters
    ----------
    config : dict
        Optional keys:
        - ``health_interval`` (int): seconds between automatic health
          checks.  Defaults to 30.
        - ``timeout`` (int): HTTP request timeout in seconds.
          Defaults to 5.
    notifier : callable, optional
        ``notifier(message: str)`` – called on significant cluster
        events (node down, deploy complete, etc.).
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        notifier: Callable[[str], None] | None = None,
    ) -> None:
        config = config or {}
        self._timeout: int = int(config.get("timeout", _DEFAULT_TIMEOUT))
        self._health_interval: int = int(config.get("health_interval", _DEFAULT_HEALTH_INTERVAL))
        self._notifier = notifier

        self._nodes: dict[str, NodeInfo] = {}
        self._lock = threading.Lock()

        # Background health-check daemon
        self._stop_event = threading.Event()
        self._health_thread = threading.Thread(
            target=self._health_loop,
            name="cluster-health",
            daemon=True,
        )
        self._health_thread.start()
        log.info(
            "ClusterController started (interval=%ds, timeout=%ds)",
            self._health_interval,
            self._timeout,
        )

    # ------------------------------------------------------------------
    # Node registry
    # ------------------------------------------------------------------

    def add_node(
        self,
        name: str,
        host: str,
        port: int,
        api_token: str,
    ) -> NodeInfo:
        """Register a remote TREVLIX node.

        Parameters
        ----------
        name : str
            Unique human-readable identifier for the node.
        host : str
            Hostname or IP address.
        port : int
            HTTP API port.
        api_token : str
            Bearer token for authenticating with the remote API.

        Returns
        -------
        NodeInfo
            The newly registered node.

        Raises
        ------
        ValueError
            If a node with the same *name* already exists.
        """
        _validate_host(host)
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}")
        with self._lock:
            if name in self._nodes:
                raise ValueError(f"Node '{name}' is already registered")
            node = NodeInfo(
                name=name,
                host=host,
                port=port,
                api_token=api_token,
            )
            self._nodes[name] = node
        log.info("Node registered: %s (%s:%d)", name, host, port)
        return node

    def remove_node(self, name: str) -> None:
        """Unregister a node by name.

        Raises
        ------
        KeyError
            If no node with *name* exists.
        """
        with self._lock:
            if name not in self._nodes:
                raise KeyError(f"Node '{name}' not found")
            del self._nodes[name]
        log.info("Node removed: %s", name)

    def get_nodes(self) -> list[dict[str, Any]]:
        """Return all registered nodes with their current status."""
        with self._lock:
            return [n.to_dict() for n in self._nodes.values()]

    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------

    def check_node(self, name: str) -> NodeStatus:
        """Run a health check against a single node.

        Tries ``/api/v1/health`` first; falls back to
        ``/api/v1/state`` if the first endpoint returns a non-200
        response.

        Returns
        -------
        NodeStatus
            The updated status of the node.

        Raises
        ------
        KeyError
            If no node with *name* exists.
        """
        node = self._get_node(name)
        status = self._probe_node(node)
        previous = node.status
        with self._lock:
            node.status = status
            node.last_check = datetime.now(UTC)
        if status != previous:
            self._notify(f"Node '{name}' status changed: {previous.value} -> {status.value}")
        return status

    def check_all(self) -> dict[str, str]:
        """Health-check every registered node.

        Returns
        -------
        dict[str, str]
            Mapping of node name to its status string.
        """
        with self._lock:
            names = list(self._nodes.keys())
        results: dict[str, str] = {}
        for name in names:
            try:
                results[name] = self.check_node(name).value
            except KeyError:
                # Node removed mid-iteration – skip it.
                continue
        return results

    # ------------------------------------------------------------------
    # Remote commands
    # ------------------------------------------------------------------

    def start_bot(self, name: str) -> dict[str, Any]:
        """Start the trading bot on a remote node.

        Raises
        ------
        KeyError
            If the node is not registered.
        ConnectionError
            If the remote call fails.
        """
        return self._post_command(name, "/api/v1/bot/start")

    def stop_bot(self, name: str) -> dict[str, Any]:
        """Stop the trading bot on a remote node.

        Raises
        ------
        KeyError
            If the node is not registered.
        ConnectionError
            If the remote call fails.
        """
        return self._post_command(name, "/api/v1/bot/stop")

    def restart_bot(self, name: str) -> dict[str, Any]:
        """Restart the trading bot on a remote node.

        Raises
        ------
        KeyError
            If the node is not registered.
        ConnectionError
            If the remote call fails.
        """
        return self._post_command(name, "/api/v1/bot/restart")

    def deploy_update(self, name: str) -> dict[str, Any]:
        """Trigger a git-pull + restart on a remote node.

        Raises
        ------
        KeyError
            If the node is not registered.
        ConnectionError
            If the remote call fails.
        """
        result = self._post_command(name, "/api/v1/deploy")
        self._notify(f"Deploy triggered on '{name}'")
        return result

    # ------------------------------------------------------------------
    # Metrics & aggregation
    # ------------------------------------------------------------------

    def get_cluster_metrics(self) -> dict[str, Any]:
        """Aggregate metrics across all online nodes.

        Fetches ``/api/v1/metrics`` from each reachable node and
        combines the results into a cluster-wide summary.

        Returns
        -------
        dict
            Keys: ``total_portfolio_value``, ``total_positions``,
            ``nodes_online``, ``nodes_total``, ``per_node``.
        """
        with self._lock:
            nodes = list(self._nodes.values())

        total_value = 0.0
        total_positions = 0
        nodes_online = 0
        per_node: list[dict[str, Any]] = []

        for node in nodes:
            entry: dict[str, Any] = {"name": node.name}
            try:
                data = self._get_json(node, "/api/v1/metrics")
                entry["portfolio_value"] = float(data.get("portfolio_value", 0))
                entry["positions"] = int(data.get("positions", 0))
                entry["pnl"] = float(data.get("pnl", 0))
                entry["uptime"] = data.get("uptime")
                entry["status"] = NodeStatus.ONLINE.value
                total_value += entry["portfolio_value"]
                total_positions += entry["positions"]
                nodes_online += 1
                # Cache latest metrics on the node object.
                with self._lock:
                    node.metrics = data
            except (requests.RequestException, ValueError) as exc:
                entry["status"] = NodeStatus.OFFLINE.value
                entry["error"] = str(exc)

            per_node.append(entry)

        return {
            "total_portfolio_value": total_value,
            "total_positions": total_positions,
            "nodes_online": nodes_online,
            "nodes_total": len(nodes),
            "per_node": per_node,
        }

    def snapshot(self) -> dict[str, Any]:
        """Return a dashboard-ready state dictionary.

        Combines the node list with cluster-level aggregate metrics
        for rendering on the admin dashboard.
        """
        nodes = self.get_nodes()
        online = sum(1 for n in nodes if n["status"] == NodeStatus.ONLINE.value)
        degraded = sum(1 for n in nodes if n["status"] == NodeStatus.DEGRADED.value)
        offline = sum(1 for n in nodes if n["status"] == NodeStatus.OFFLINE.value)
        return {
            "nodes": nodes,
            "cluster": {
                "total": len(nodes),
                "online": online,
                "degraded": degraded,
                "offline": offline,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Stop the background health-check thread gracefully."""
        self._stop_event.set()
        self._health_thread.join(timeout=self._health_interval + 2)
        log.info("ClusterController shut down")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_node(self, name: str) -> NodeInfo:
        """Retrieve a node by name (thread-safe)."""
        with self._lock:
            try:
                return self._nodes[name]
            except KeyError:
                raise KeyError(f"Node '{name}' not found") from None

    def _auth_headers(self, node: NodeInfo) -> dict[str, str]:
        """Build authorization headers for a remote request."""
        return {"Authorization": f"Bearer {node.api_token}"}

    def _probe_node(self, node: NodeInfo) -> NodeStatus:
        """Probe a node's health endpoints and return its status."""
        for endpoint in ("/api/v1/health", "/api/v1/state"):
            try:
                resp = requests.get(
                    f"{node.base_url}{endpoint}",
                    headers=self._auth_headers(node),
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("status") == "degraded":
                        with self._lock:
                            node.last_error = body.get("reason")
                        return NodeStatus.DEGRADED
                    with self._lock:
                        node.last_error = None
                    return NodeStatus.ONLINE
            except requests.RequestException:
                continue

        with self._lock:
            node.last_error = "All health endpoints unreachable"
        return NodeStatus.OFFLINE

    def _post_command(self, name: str, path: str) -> dict[str, Any]:
        """Send a POST command to a remote node and return the JSON body.

        Raises
        ------
        KeyError
            If the node does not exist.
        ConnectionError
            If the HTTP call fails or returns a non-2xx status.
        """
        node = self._get_node(name)
        url = f"{node.base_url}{path}"
        try:
            resp = requests.post(
                url,
                headers=self._auth_headers(node),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except requests.RequestException as exc:
            log.error("Command %s failed on node '%s': %s", path, name, exc)
            raise ConnectionError(f"Remote call {path} failed on '{name}': {exc}") from exc

    def _get_json(self, node: NodeInfo, path: str) -> dict[str, Any]:
        """GET JSON from a remote node."""
        url = f"{node.base_url}{path}"
        resp = requests.get(
            url,
            headers=self._auth_headers(node),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _notify(self, message: str) -> None:
        """Forward a message to the optional notifier callback."""
        log.info(message)
        if self._notifier is not None:
            try:
                self._notifier(message)
            except Exception:
                log.exception("Notifier callback failed")

    def _health_loop(self) -> None:
        """Background daemon loop that periodically checks all nodes."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._health_interval)
            if self._stop_event.is_set():
                break
            try:
                self.check_all()
            except Exception:
                log.exception("Unexpected error in health-check loop")
