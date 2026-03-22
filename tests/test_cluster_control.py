"""
TREVLIX Tests – Cluster Control Agent
=======================================

Tests for the ClusterController service that manages remote TREVLIX
nodes: health-checking, commands, and metric aggregation.

Run with:  pytest tests/test_cluster_control.py -v
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from services.cluster_control import (
    ClusterController,
    NodeInfo,
    NodeStatus,
)


@pytest.fixture
def ctrl() -> ClusterController:
    """Create a ClusterController with immediate shutdown of health thread."""
    c = ClusterController(
        config={"health_interval": 9999, "timeout": 1},
        notifier=None,
    )
    yield c
    c.shutdown()


class TestNodeRegistry:
    """Tests for node add/remove operations."""

    def test_add_node(self, ctrl: ClusterController) -> None:
        """Add a node, verify it appears in the nodes list."""
        node = ctrl.add_node("us-east", "10.0.1.5", 5000, "tok_abc")
        assert isinstance(node, NodeInfo)
        assert node.name == "us-east"

        nodes = ctrl.get_nodes()
        assert len(nodes) == 1
        assert nodes[0]["name"] == "us-east"

    def test_add_duplicate_node(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify ValueError on duplicate name."""
        ctrl.add_node("node1", "10.0.0.1", 5000, "tok1")
        with pytest.raises(ValueError, match="already registered"):
            ctrl.add_node("node1", "10.0.0.2", 5001, "tok2")

    def test_remove_node(self, ctrl: ClusterController) -> None:
        """Add then remove a node, verify removed."""
        ctrl.add_node("node1", "10.0.0.1", 5000, "tok1")
        ctrl.remove_node("node1")
        assert len(ctrl.get_nodes()) == 0

    def test_remove_nonexistent(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify KeyError when removing non-existent node."""
        with pytest.raises(KeyError, match="not found"):
            ctrl.remove_node("ghost")

    def test_get_nodes_empty(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify empty list initially."""
        assert ctrl.get_nodes() == []


class TestHealthChecks:
    """Tests for node health checking."""

    def test_check_node_offline(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Mock failed HTTP, verify OFFLINE status."""
        ctrl.add_node("node1", "10.0.0.1", 5000, "tok1")

        with patch("services.cluster_control.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("refused")
            status = ctrl.check_node("node1")

        assert status == NodeStatus.OFFLINE

    def test_check_all_nodes(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Add multiple nodes, check all, verify results."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "t1")
        ctrl.add_node("n2", "10.0.0.2", 5000, "t2")

        with patch("services.cluster_control.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("refused")
            results = ctrl.check_all()

        assert "n1" in results
        assert "n2" in results
        assert results["n1"] == NodeStatus.OFFLINE.value
        assert results["n2"] == NodeStatus.OFFLINE.value


class TestRemoteCommands:
    """Tests for bot start/stop/restart and deploy."""

    def test_start_bot_sends_post(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Mock requests.post, verify correct URL called."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "tok1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "started"}
        mock_resp.raise_for_status = Mock()

        with patch(
            "services.cluster_control.requests.post",
            return_value=mock_resp,
        ) as mock_post:
            result = ctrl.start_bot("n1")

        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "/api/v1/bot/start" in url
        assert result == {"status": "started"}

    def test_stop_bot_sends_post(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify stop sends POST to /api/v1/bot/stop."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "tok1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "stopped"}
        mock_resp.raise_for_status = Mock()

        with patch(
            "services.cluster_control.requests.post",
            return_value=mock_resp,
        ) as mock_post:
            result = ctrl.stop_bot("n1")

        url = mock_post.call_args[0][0]
        assert "/api/v1/bot/stop" in url
        assert result == {"status": "stopped"}

    def test_restart_bot(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify restart sends POST to /api/v1/bot/restart."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "tok1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "restarted"}
        mock_resp.raise_for_status = Mock()

        with patch(
            "services.cluster_control.requests.post",
            return_value=mock_resp,
        ) as mock_post:
            ctrl.restart_bot("n1")

        url = mock_post.call_args[0][0]
        assert "/api/v1/bot/restart" in url

    def test_deploy_update(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify POST to /api/v1/deploy."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "tok1")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"deployed": True}
        mock_resp.raise_for_status = Mock()

        with patch(
            "services.cluster_control.requests.post",
            return_value=mock_resp,
        ) as mock_post:
            result = ctrl.deploy_update("n1")

        url = mock_post.call_args[0][0]
        assert "/api/v1/deploy" in url
        assert result == {"deployed": True}


class TestSnapshot:
    """Tests for the snapshot() method."""

    def test_snapshot_structure(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Verify snapshot dict keys."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "tok1")
        snap = ctrl.snapshot()

        assert "nodes" in snap
        assert "cluster" in snap
        assert "generated_at" in snap
        assert "total" in snap["cluster"]
        assert "online" in snap["cluster"]
        assert "degraded" in snap["cluster"]
        assert "offline" in snap["cluster"]


class TestClusterMetrics:
    """Tests for metric aggregation."""

    def test_cluster_metrics_aggregation(
        self,
        ctrl: ClusterController,
    ) -> None:
        """Mock per-node metrics, verify aggregation."""
        ctrl.add_node("n1", "10.0.0.1", 5000, "t1")
        ctrl.add_node("n2", "10.0.0.2", 5000, "t2")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "portfolio_value": 5000.0,
            "positions": 3,
            "pnl": 150.0,
            "uptime": "2h",
        }
        mock_resp.raise_for_status = Mock()

        with patch(
            "services.cluster_control.requests.get",
            return_value=mock_resp,
        ):
            metrics = ctrl.get_cluster_metrics()

        assert metrics["total_portfolio_value"] == 10_000.0
        assert metrics["total_positions"] == 6
        assert metrics["nodes_online"] == 2
        assert metrics["nodes_total"] == 2
        assert len(metrics["per_node"]) == 2


class TestShutdown:
    """Tests for graceful shutdown."""

    def test_shutdown_stops_thread(self) -> None:
        """Verify shutdown stops health check thread."""
        ctrl = ClusterController(
            config={"health_interval": 9999},
        )
        assert ctrl._health_thread.is_alive()
        ctrl.shutdown()
        assert ctrl._stop_event.is_set()
        assert not ctrl._health_thread.is_alive()
