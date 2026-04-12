"""Tests für die LLM → Agenten Bridge via MCP-Tools."""

from __future__ import annotations

from typing import Any

import pytest

from services.mcp_tools import MCPToolRegistry
from services.virginie import (
    AgentResult,
    AgentTask,
    VirginieAgent,
    VirginieOrchestrator,
    build_default_project_agents,
)


class _StubKB:
    """Minimale KnowledgeBase-Nachbildung für den Registry-Konstruktor."""

    CATEGORIES = ("market_insight", "strategy_perf")

    def get(self, *_a, **_k):  # pragma: no cover - nur für Tool-Schema nötig
        return None

    def get_category(self, *_a, **_k):  # pragma: no cover
        return []


class _StubState:
    balance = 0.0
    positions: dict[str, Any] = {}
    running = False
    paused = False
    iteration = 0


class _StubHealer:
    def __init__(self) -> None:
        self._running = True

    def health_snapshot(self) -> dict[str, Any]:
        return {"status": "ok", "recoveries": 0}

    def is_running(self) -> bool:
        return self._running


class _StubAlertEscalation:
    def snapshot(self) -> dict[str, Any]:
        return {"total": 0, "active": 0}

    def get_active_alerts(self) -> list[dict[str, Any]]:
        return []


class _StubCluster:
    def snapshot(self) -> dict[str, Any]:
        return {"nodes": []}


@pytest.fixture()
def registry() -> MCPToolRegistry:
    reg = MCPToolRegistry(
        db_manager=None,
        state=_StubState(),
        knowledge_base=_StubKB(),
        config={},
    )
    return reg


def test_agent_control_tools_are_registered(registry: MCPToolRegistry) -> None:
    names = {t["function"]["name"] for t in registry.get_tools_schema()}
    assert {
        "list_agents",
        "execute_agent_task",
        "healing_status",
        "alert_status",
        "cluster_status",
    }.issubset(names)


def test_tools_return_error_without_agent_refs(registry: MCPToolRegistry) -> None:
    for tool in ("list_agents", "healing_status", "alert_status", "cluster_status"):
        result = registry.execute(tool, {})
        assert "error" in result, f"{tool} sollte ohne Refs 'error' zurückgeben"


def test_list_agents_returns_status_when_wired(registry: MCPToolRegistry) -> None:
    orch = VirginieOrchestrator()
    for agent in build_default_project_agents():
        orch.register_agent(agent)
    orch.set_required_domains(["trading", "operations"])
    registry.set_agent_refs(virginie_orchestrator=orch)

    result = registry.execute("list_agents", {})
    assert "error" not in result
    assert result["registered_agents"] >= 2
    assert "coverage_pct" in result
    assert isinstance(result["missing_domains"], list)


def test_execute_agent_task_dispatches_via_orchestrator(
    registry: MCPToolRegistry,
) -> None:
    calls: list[AgentTask] = []

    def _handler(task: AgentTask) -> AgentResult:
        calls.append(task)
        return AgentResult(
            agent_name="unit-agent",
            task_id=task.task_id,
            success=True,
            summary="done",
            data={"echo": task.objective},
        )

    orch = VirginieOrchestrator()
    orch.register_agent(VirginieAgent(name="unit-agent", domains=("trading",), handler=_handler))
    registry.set_agent_refs(virginie_orchestrator=orch)

    # Cache mit leeren Args vermeiden: explizite Payload macht Key eindeutig.
    result = registry.execute(
        "execute_agent_task",
        {"domain": "trading", "objective": "pause bot", "payload": {"reason": "drawdown"}},
    )
    assert "error" not in result
    assert result["success"] is True
    assert result["agent"] == "unit-agent"
    assert result["data"]["echo"] == "pause bot"
    assert len(calls) == 1
    assert calls[0].domain == "trading"
    assert calls[0].payload == {"reason": "drawdown"}


def test_execute_agent_task_validates_required_fields(registry: MCPToolRegistry) -> None:
    registry.set_agent_refs(virginie_orchestrator=VirginieOrchestrator())
    missing_domain = registry.execute("execute_agent_task", {"objective": "x"})
    assert "error" in missing_domain and "domain" in missing_domain["error"]
    missing_obj = registry.execute("execute_agent_task", {"domain": "trading"})
    assert "error" in missing_obj and "objective" in missing_obj["error"]


def test_execute_agent_task_rejects_non_object_payload(
    registry: MCPToolRegistry,
) -> None:
    registry.set_agent_refs(virginie_orchestrator=VirginieOrchestrator())
    bad = registry.execute(
        "execute_agent_task",
        {"domain": "trading", "objective": "x", "payload": "not-a-dict"},
    )
    assert "error" in bad


def test_healing_alert_cluster_status_report_when_wired(
    registry: MCPToolRegistry,
) -> None:
    registry.set_agent_refs(
        healer=_StubHealer(),
        alert_escalation=_StubAlertEscalation(),
        cluster_ctrl=_StubCluster(),
    )
    heal = registry.execute("healing_status", {})
    assert heal["running"] is True
    assert heal["snapshot"]["status"] == "ok"

    alerts = registry.execute("alert_status", {})
    assert alerts["active_alerts"] == []
    assert alerts["snapshot"]["total"] == 0

    cluster = registry.execute("cluster_status", {})
    assert cluster["snapshot"]["nodes"] == []


def test_set_agent_refs_is_additive(registry: MCPToolRegistry) -> None:
    """Folgende set_agent_refs-Calls dürfen nicht-angegebene Refs nicht löschen."""
    orch = VirginieOrchestrator()
    registry.set_agent_refs(virginie_orchestrator=orch)
    registry.set_agent_refs(healer=_StubHealer())
    # list_agents sollte immer noch funktionieren, weil orch beibehalten wurde
    result = registry.execute("list_agents", {})
    assert "error" not in result
