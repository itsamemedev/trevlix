"""TREVLIX – MCP Tool Integration für KI-gestütztes Trading.

Stellt MCP-kompatible Tools bereit, die von der LLM-Integration
genutzt werden können, um Echtzeit-Marktdaten, Nachrichten und
technische Analysen abzurufen.

Tools:
    - market_price: Aktueller Preis + 24h-Änderung für ein Symbol
    - market_news: Aktuelle Krypto-Nachrichten und Sentiment
    - technical_summary: Technische Indikatoren für ein Symbol
    - portfolio_status: Aktueller Portfolio-Stand und offene Positionen
    - risk_assessment: Risiko-Bewertung basierend auf aktuellen Daten
    - knowledge_query: Abfrage des Gemeinschaftswissens
    - list_agents: Registrierte VIRGINIE-Agenten + Coverage
    - execute_agent_task: VIRGINIE-Agent per Domain/Objective steuern
    - healing_status: Auto-Healing-Agent Snapshot
    - alert_status: Alert-Escalation Snapshot
    - cluster_status: Cluster-Controller Snapshot

Verwendung:
    from services.mcp_tools import MCPToolRegistry
    registry = MCPToolRegistry(db, state, knowledge_base)
    result = registry.execute("market_price", {"symbol": "BTC/USDT"})
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

log = logging.getLogger("trevlix.mcp_tools")


class MCPTool:
    """Definition eines einzelnen MCP-Tools.

    Attributes:
        name: Eindeutiger Tool-Name.
        description: Beschreibung für die LLM.
        parameters: JSON-Schema der Parameter.
        handler: Callable das das Tool ausführt.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Any,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_schema(self) -> dict[str, Any]:
        """Gibt das Tool-Schema im MCP/OpenAI-Format zurück."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class MCPToolRegistry:
    """Registry für alle verfügbaren MCP-Tools.

    Verwaltet die Tool-Definitionen und deren Ausführung.
    Tools werden bei der Initialisierung registriert und können
    von der LLM über tool_use aufgerufen werden.

    Args:
        db_manager: MySQLManager für DB-Zugriff.
        state: Bot-State-Objekt.
        knowledge_base: KnowledgeBase-Instanz.
        exchange_fn: Factory-Funktion für Exchange-Objekte.
        config: Globale Konfiguration.
    """

    def __init__(
        self,
        db_manager: Any,
        state: Any,
        knowledge_base: Any,
        exchange_fn: Any | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._db = db_manager
        self._state = state
        self._kb = knowledge_base
        self._exchange_fn = exchange_fn
        self._config = config or {}
        self._tools: dict[str, MCPTool] = {}
        self._call_cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 60  # 1 Minute Cache für Tool-Ergebnisse

        # Agent-Referenzen werden nachträglich via set_agent_refs() gesetzt,
        # da orchestrator/healer/alert/cluster erst nach der Registry entstehen.
        self._virginie_orchestrator: Any | None = None
        self._healer: Any | None = None
        self._alert_escalation: Any | None = None
        self._cluster_ctrl: Any | None = None

        self._register_builtin_tools()
        self._register_agent_control_tools()

    def set_agent_refs(
        self,
        *,
        virginie_orchestrator: Any | None = None,
        healer: Any | None = None,
        alert_escalation: Any | None = None,
        cluster_ctrl: Any | None = None,
    ) -> None:
        """Bind live agent references so the LLM can command them.

        Called from server.py after agents are constructed. Passing ``None``
        leaves the existing reference untouched (use a new registry to clear).
        """
        if virginie_orchestrator is not None:
            self._virginie_orchestrator = virginie_orchestrator
        if healer is not None:
            self._healer = healer
        if alert_escalation is not None:
            self._alert_escalation = alert_escalation
        if cluster_ctrl is not None:
            self._cluster_ctrl = cluster_ctrl

    def _register_builtin_tools(self) -> None:
        """Registriert alle eingebauten Trading-Tools."""
        self.register(
            MCPTool(
                name="market_price",
                description=(
                    "Ruft den aktuellen Preis und 24h-Änderung für ein "
                    "Kryptowährungs-Symbol ab. Nutze dies um aktuelle "
                    "Marktpreise zu prüfen."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading-Paar z.B. BTC/USDT",
                        },
                    },
                    "required": ["symbol"],
                },
                handler=self._tool_market_price,
            )
        )

        self.register(
            MCPTool(
                name="market_news",
                description=(
                    "Ruft aktuelle Krypto-Nachrichten und Sentiment-Scores "
                    "aus dem Cache ab. Nutze dies für Stimmungsanalysen."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol z.B. BTC oder ETH",
                        },
                    },
                    "required": ["symbol"],
                },
                handler=self._tool_market_news,
            )
        )

        self.register(
            MCPTool(
                name="technical_summary",
                description=(
                    "Gibt technische Indikatoren (RSI, MACD, Bollinger, "
                    "ATR) für ein Symbol zurück. Nutze dies für "
                    "technische Analyse."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading-Paar z.B. BTC/USDT",
                        },
                    },
                    "required": ["symbol"],
                },
                handler=self._tool_technical_summary,
            )
        )

        self.register(
            MCPTool(
                name="portfolio_status",
                description=(
                    "Zeigt den aktuellen Portfolio-Stand, offene Positionen und Bilanz an."
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self._tool_portfolio_status,
            )
        )

        self.register(
            MCPTool(
                name="risk_assessment",
                description=(
                    "Bewertet das aktuelle Risikoprofil basierend auf "
                    "offenen Positionen, Drawdown und Marktlage."
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self._tool_risk_assessment,
            )
        )

        self.register(
            MCPTool(
                name="knowledge_query",
                description=(
                    "Durchsucht das Gemeinschaftswissen nach Erkenntnissen "
                    "zu einem bestimmten Thema oder Symbol."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": list(self._kb.CATEGORIES),
                            "description": "Wissens-Kategorie",
                        },
                        "key": {
                            "type": "string",
                            "description": "Suchbegriff oder Symbol-Name",
                        },
                    },
                    "required": ["category"],
                },
                handler=self._tool_knowledge_query,
            )
        )

        self.register(
            MCPTool(
                name="trade_history",
                description=(
                    "Ruft die letzten Trades ab, optional gefiltert "
                    "nach Symbol. Nutze dies um aus vergangenen "
                    "Trades zu lernen."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Optional: Filter nach Symbol",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Anzahl Trades (max 50)",
                            "default": 10,
                        },
                    },
                },
                handler=self._tool_trade_history,
            )
        )

        self.register(
            MCPTool(
                name="strategy_performance",
                description=(
                    "Zeigt die Performance aller Trading-Strategien mit Win-Rate und PnL an."
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self._tool_strategy_performance,
            )
        )

    def _register_agent_control_tools(self) -> None:
        """Registriert Tools, mit denen die LLM laufende Agenten steuert."""
        self.register(
            MCPTool(
                name="list_agents",
                description=(
                    "Listet alle registrierten VIRGINIE-Agenten mit Domain, "
                    "Auslastung und Fehlerquote. Zusätzlich Coverage-Report "
                    "(welche Pflicht-Domains aktuell abgedeckt sind)."
                ),
                parameters={"type": "object", "properties": {}},
                handler=self._tool_list_agents,
            )
        )
        self.register(
            MCPTool(
                name="execute_agent_task",
                description=(
                    "Sendet eine Aufgabe an einen VIRGINIE-Projekt-Agenten. "
                    "Die Domain (z.B. 'trading', 'operations', 'risk', "
                    "'notifications', 'quality', 'learning', 'portfolio') "
                    "bestimmt das Routing. 'objective' beschreibt das Ziel "
                    "in Klartext, 'payload' liefert strukturierte Parameter."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": (
                                "Ziel-Domain (trading, operations, risk, "
                                "notifications, quality, learning, portfolio, "
                                "planning, compliance)"
                            ),
                        },
                        "objective": {
                            "type": "string",
                            "description": "Kurze Ziel-Beschreibung (max 240 Zeichen)",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Optionale strukturierte Parameter",
                        },
                    },
                    "required": ["domain", "objective"],
                },
                handler=self._tool_execute_agent_task,
            )
        )
        self.register(
            MCPTool(
                name="healing_status",
                description=(
                    "Gibt den aktuellen Health-Snapshot des Auto-Healing-"
                    "Agenten zurück (Heartbeat, Recovery-Zähler, aktive "
                    "Probleme)."
                ),
                parameters={"type": "object", "properties": {}},
                handler=self._tool_healing_status,
            )
        )
        self.register(
            MCPTool(
                name="alert_status",
                description=(
                    "Liefert aktive Alerts, History-Zusammenfassung und "
                    "Eskalations-Stufen aus dem AlertEscalationManager."
                ),
                parameters={"type": "object", "properties": {}},
                handler=self._tool_alert_status,
            )
        )
        self.register(
            MCPTool(
                name="cluster_status",
                description=(
                    "Zeigt den Zustand aller registrierten Cluster-Nodes "
                    "(Status, letzter Check, Bot-Health)."
                ),
                parameters={"type": "object", "properties": {}},
                handler=self._tool_cluster_status,
            )
        )

    def register(self, tool: MCPTool) -> None:
        """Registriert ein neues Tool."""
        self._tools[tool.name] = tool

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """Gibt alle Tool-Schemas im MCP/OpenAI-Format zurück."""
        return [tool.to_schema() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """Gibt eine formatierte Beschreibung aller Tools zurück.

        Wird als System-Prompt-Ergänzung für die LLM verwendet.
        """
        lines = ["Verfügbare Tools:"]
        for tool in self._tools.values():
            params = tool.parameters.get("properties", {})
            param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
            lines.append(f"- {tool.name}({param_str}): {tool.description}")
        return "\n".join(lines)

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Führt ein Tool aus und gibt das Ergebnis zurück.

        Args:
            tool_name: Name des Tools.
            arguments: Tool-Parameter als Dict.

        Returns:
            Dict mit 'result' oder 'error' Schlüssel.
        """
        if tool_name not in self._tools:
            return {"error": f"Unbekanntes Tool: {tool_name}"}

        arguments = arguments or {}

        # Cache-Check
        cache_key = f"{tool_name}:{json.dumps(arguments, sort_keys=True)}"
        now = time.time()
        if cache_key in self._call_cache:
            ts, cached_result = self._call_cache[cache_key]
            if now - ts < self._cache_ttl:
                return cached_result

        try:
            result = self._tools[tool_name].handler(arguments)
            # Cache speichern
            self._call_cache[cache_key] = (now, result)
            # Cache-Eviction (max 200 Einträge)
            if len(self._call_cache) > 200:
                oldest = sorted(
                    self._call_cache.items(),
                    key=lambda x: x[1][0],
                )
                for k, _ in oldest[: len(self._call_cache) - 200]:
                    self._call_cache.pop(k, None)
            return result
        except Exception as e:
            log.debug(f"MCP Tool {tool_name} Fehler: {e}")
            return {"error": str(e)}

    def process_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Verarbeitet mehrere Tool-Calls aus einer LLM-Antwort.

        Args:
            tool_calls: Liste von Tool-Call-Dicts mit 'name' und 'arguments'.

        Returns:
            Liste von Ergebnis-Dicts mit 'tool_name' und 'result'.
        """
        results = []
        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            result = self.execute(name, args)
            results.append(
                {
                    "tool_call_id": call.get("id", ""),
                    "tool_name": name,
                    "result": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        return results

    # ═════════════════════════════════════════════════════════════════════════
    # TOOL HANDLER IMPLEMENTIERUNGEN
    # ═════════════════════════════════════════════════════════════════════════

    def _tool_market_price(self, args: dict[str, Any]) -> dict[str, Any]:
        """Aktuellen Preis für ein Symbol abrufen."""
        symbol = args.get("symbol", "BTC/USDT")
        # Daten aus State-Objekt (letzte bekannte Werte)
        prices = getattr(self._state, "prices", {})
        if symbol in prices:
            price_data = prices[symbol]
            if isinstance(price_data, dict):
                return {
                    "symbol": symbol,
                    "price": price_data.get("last", 0),
                    "change_24h": price_data.get("change", 0),
                    "volume_24h": price_data.get("volume", 0),
                    "timestamp": datetime.now().isoformat(),
                }
            return {
                "symbol": symbol,
                "price": float(price_data),
                "timestamp": datetime.now().isoformat(),
            }

        # Fallback: Position-Daten
        positions = getattr(self._state, "positions", {})
        if symbol in positions:
            pos = positions[symbol]
            return {
                "symbol": symbol,
                "price": pos.get("current_price", pos.get("entry_price", 0)),
                "entry_price": pos.get("entry_price", 0),
                "pnl_pct": pos.get("pnl_pct", 0),
                "timestamp": datetime.now().isoformat(),
            }

        return {"symbol": symbol, "error": "Kein Preis verfügbar", "hint": "Bot muss laufen"}

    def _tool_market_news(self, args: dict[str, Any]) -> dict[str, Any]:
        """Nachrichten und Sentiment für ein Symbol."""
        symbol = args.get("symbol", "BTC")
        result: dict[str, Any] = {"symbol": symbol, "timestamp": datetime.now().isoformat()}

        # Sentiment aus DB
        try:
            sentiment = self._db.get_sentiment(symbol)
            result["sentiment_score"] = sentiment
        except Exception:
            result["sentiment_score"] = None

        # News aus DB
        try:
            news = self._db.get_news(symbol)
            if news:
                result["news_score"] = news.get("score", 0)
                result["headline"] = news.get("headline", "")
                result["article_count"] = news.get("count", 0)
        except Exception:
            pass

        # On-Chain-Daten
        try:
            onchain = self._db.get_onchain(symbol)
            if onchain:
                result["whale_score"] = onchain.get("whale_score", 0)
                result["flow_score"] = onchain.get("flow_score", 0)
        except Exception:
            pass

        return result

    def _tool_technical_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        """Technische Indikatoren für ein Symbol."""
        symbol = args.get("symbol", "BTC/USDT")
        # Indikatoren aus State/Cache
        indicators = getattr(self._state, "indicators", {})
        sym_data = indicators.get(symbol, {})

        if sym_data:
            return {
                "symbol": symbol,
                "rsi": sym_data.get("rsi"),
                "macd": sym_data.get("macd"),
                "macd_signal": sym_data.get("macd_signal"),
                "bb_upper": sym_data.get("bb_upper"),
                "bb_lower": sym_data.get("bb_lower"),
                "atr": sym_data.get("atr"),
                "ema_short": sym_data.get("ema_short"),
                "ema_long": sym_data.get("ema_long"),
                "volume_ratio": sym_data.get("volume_ratio"),
                "timestamp": datetime.now().isoformat(),
            }

        # Fallback: Letzte bekannte Daten aus Positionen
        positions = getattr(self._state, "positions", {})
        if symbol in positions:
            pos = positions[symbol]
            return {
                "symbol": symbol,
                "entry_price": pos.get("entry_price", 0),
                "current_price": pos.get("current_price", 0),
                "pnl_pct": pos.get("pnl_pct", 0),
                "note": "Nur Positionsdaten verfügbar",
                "timestamp": datetime.now().isoformat(),
            }

        return {"symbol": symbol, "error": "Keine technischen Daten verfügbar"}

    def _tool_portfolio_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Aktueller Portfolio-Stand."""
        positions = getattr(self._state, "positions", {})
        pos_list = []
        for sym, pos in positions.items():
            if isinstance(pos, dict):
                pos_list.append(
                    {
                        "symbol": sym,
                        "entry_price": pos.get("entry_price", 0),
                        "current_price": pos.get("current_price", 0),
                        "pnl_pct": round(pos.get("pnl_pct", 0), 2),
                        "size": pos.get("size", 0),
                    }
                )

        return {
            "balance": round(getattr(self._state, "balance", 0), 2),
            "portfolio_value": round(self._state.portfolio_value(), 2)
            if hasattr(self._state, "portfolio_value")
            else None,
            "open_positions": len(positions),
            "positions": pos_list,
            "running": getattr(self._state, "running", False),
            "paused": getattr(self._state, "paused", False),
            "iteration": getattr(self._state, "iteration", 0),
            "timestamp": datetime.now().isoformat(),
        }

    def _tool_risk_assessment(self, args: dict[str, Any]) -> dict[str, Any]:
        """Risiko-Bewertung des Portfolios."""
        positions = getattr(self._state, "positions", {})
        balance = getattr(self._state, "balance", 0)
        max_balance = getattr(self._state, "max_balance", balance)

        # Drawdown berechnen
        drawdown = 0.0
        if max_balance > 0:
            drawdown = round((1 - balance / max_balance) * 100, 2)

        # Position-Exposure
        total_exposure = 0.0
        losing_positions = 0
        for pos in positions.values():
            if isinstance(pos, dict):
                total_exposure += abs(pos.get("size", 0) * pos.get("current_price", 0))
                if pos.get("pnl_pct", 0) < 0:
                    losing_positions += 1

        exposure_pct = round(total_exposure / max(balance, 1) * 100, 2) if balance > 0 else 0

        # Risiko-Level bestimmen
        risk_level = "niedrig"
        if drawdown > 10 or exposure_pct > 80:
            risk_level = "hoch"
        elif drawdown > 5 or exposure_pct > 50:
            risk_level = "mittel"

        return {
            "risk_level": risk_level,
            "drawdown_pct": drawdown,
            "max_balance": round(max_balance, 2),
            "current_balance": round(balance, 2),
            "exposure_pct": exposure_pct,
            "open_positions": len(positions),
            "losing_positions": losing_positions,
            "timestamp": datetime.now().isoformat(),
        }

    def _tool_knowledge_query(self, args: dict[str, Any]) -> dict[str, Any]:
        """Gemeinschaftswissen abfragen."""
        category = args.get("category", "market_insight")
        key = args.get("key", "")

        if key:
            entry = self._kb.get(category, key)
            if entry:
                return {"found": True, "entry": entry}
            return {"found": False, "category": category, "key": key}

        entries = self._kb.get_category(category, limit=10)
        return {
            "category": category,
            "count": len(entries),
            "entries": entries[:10],
        }

    def _tool_trade_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """Letzte Trades abrufen."""
        symbol = args.get("symbol")
        limit = min(args.get("limit", 10), 50)

        try:
            trades = self._db.load_trades(limit=limit, symbol=symbol)
            simplified = []
            for t in trades:
                simplified.append(
                    {
                        "symbol": t.get("symbol", "?"),
                        "type": t.get("type", "?"),
                        "pnl": round(t.get("pnl", 0), 2),
                        "pnl_pct": round(t.get("pnl_pct", 0), 2),
                        "reason": t.get("reason", ""),
                        "closed_at": str(t.get("closed_at", "")),
                    }
                )
            return {"trades": simplified, "count": len(simplified)}
        except Exception as e:
            return {"error": f"Trade-Abfrage fehlgeschlagen: {e}"}

    def _tool_strategy_performance(self, args: dict[str, Any]) -> dict[str, Any]:
        """Strategie-Performance aus dem Gemeinschaftswissen."""
        strategies = self._kb.get_category("strategy_perf", limit=20)
        perf_list = []
        for s in strategies:
            v = s.get("value") or {}
            trades = v.get("trades", 0)
            if trades >= 1:
                wins = v.get("wins", 0)
                perf_list.append(
                    {
                        "strategy": s.get("key", "?"),
                        "trades": trades,
                        "wins": wins,
                        "win_rate": round(wins / max(trades, 1), 2),
                        "pnl": round(v.get("pnl", 0), 2),
                    }
                )
        perf_list.sort(key=lambda x: x["win_rate"], reverse=True)
        return {"strategies": perf_list, "count": len(perf_list)}

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT CONTROL HANDLERS – LLM steuert laufende VIRGINIE-Agenten
    # ═════════════════════════════════════════════════════════════════════════

    def _tool_list_agents(self, _args: dict[str, Any]) -> dict[str, Any]:
        """Registrierte VIRGINIE-Agenten und Coverage-Report."""
        orch = self._virginie_orchestrator
        if orch is None:
            return {"error": "VIRGINIE-Orchestrator ist nicht verbunden."}
        try:
            status = orch.status()
            coverage = orch.coverage_report()
            return {
                "agents": status.get("agents", []),
                "registered_agents": status.get("registered_agents", 0),
                "required_domains": coverage.get("required_domains", []),
                "missing_domains": coverage.get("missing_domains", []),
                "coverage_pct": coverage.get("coverage_pct", 0),
                "last_agent": status.get("last_agent"),
                "history_size": status.get("history_size", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            log.debug("list_agents Fehler: %s", exc)
            return {"error": f"list_agents fehlgeschlagen: {exc}"}

    def _tool_execute_agent_task(self, args: dict[str, Any]) -> dict[str, Any]:
        """LLM delegiert eine Aufgabe an einen VIRGINIE-Agenten."""
        orch = self._virginie_orchestrator
        if orch is None:
            return {"error": "VIRGINIE-Orchestrator ist nicht verbunden."}
        domain = str(args.get("domain", "")).strip()
        objective = str(args.get("objective", "")).strip()
        if not domain:
            return {"error": "Parameter 'domain' fehlt."}
        if not objective:
            return {"error": "Parameter 'objective' fehlt."}
        payload = args.get("payload") or {}
        if not isinstance(payload, dict):
            return {"error": "Parameter 'payload' muss ein Objekt sein."}
        # Defensive Cap gegen übergroße Payloads aus LLM-Antworten.
        if len(payload) > 32:
            return {"error": "Payload zu groß (>32 Felder) – LLM bitte verdichten."}
        try:
            from services.virginie import AgentTask  # lazy import, vermeidet Zyklus
        except Exception as exc:
            return {"error": f"AgentTask-Import fehlgeschlagen: {exc}"}
        task = AgentTask(
            task_id=f"llm-{uuid.uuid4().hex[:10]}",
            domain=domain,
            objective=objective[:240],
            payload=payload,
        )
        try:
            result = orch.execute(task)
        except Exception as exc:
            log.debug("execute_agent_task Fehler: %s", exc)
            return {"error": f"Agent-Ausführung fehlgeschlagen: {exc}"}
        return {
            "task_id": task.task_id,
            "agent": result.agent_name,
            "success": bool(result.success),
            "summary": result.summary,
            "data": result.data,
            "timestamp": datetime.now().isoformat(),
        }

    def _tool_healing_status(self, _args: dict[str, Any]) -> dict[str, Any]:
        """Auto-Healing-Agent Snapshot."""
        healer = self._healer
        if healer is None:
            return {"error": "Auto-Healing-Agent ist nicht verbunden."}
        try:
            snap = healer.health_snapshot()
            running = bool(getattr(healer, "is_running", lambda: False)())
            return {
                "running": running,
                "snapshot": snap,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            log.debug("healing_status Fehler: %s", exc)
            return {"error": f"healing_status fehlgeschlagen: {exc}"}

    def _tool_alert_status(self, _args: dict[str, Any]) -> dict[str, Any]:
        """Alert-Escalation Snapshot."""
        mgr = self._alert_escalation
        if mgr is None:
            return {"error": "AlertEscalationManager ist nicht verbunden."}
        try:
            snap = mgr.snapshot()
            active = mgr.get_active_alerts()
            return {
                "active_alerts": active,
                "snapshot": snap,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            log.debug("alert_status Fehler: %s", exc)
            return {"error": f"alert_status fehlgeschlagen: {exc}"}

    def _tool_cluster_status(self, _args: dict[str, Any]) -> dict[str, Any]:
        """Cluster-Controller Snapshot."""
        cluster = self._cluster_ctrl
        if cluster is None:
            return {"error": "ClusterController ist nicht verbunden."}
        try:
            snap = cluster.snapshot()
            return {
                "snapshot": snap,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            log.debug("cluster_status Fehler: %s", exc)
            return {"error": f"cluster_status fehlgeschlagen: {exc}"}
