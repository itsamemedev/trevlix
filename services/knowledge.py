"""TREVLIX – KI-Gemeinschaftswissen Service.

Speichert und teilt KI-Erkenntnisse zwischen allen Usern.
Das Wissen wird in der DB gespeichert und kann von einer lokalen
LLM-Instanz oder über externe APIs angereichert werden.

Kategorien:
    - market_insight: Marktanalysen und Trends
    - strategy_perf: Strategie-Performance-Daten
    - symbol_info: Symbol-spezifische Erkenntnisse
    - risk_pattern: Erkannte Risikomuster
    - model_config: Optimierte Modell-Parameter

Verwendung:
    from services.knowledge import KnowledgeBase
    kb = KnowledgeBase(db)
    kb.store("market_insight", "btc_trend", {"direction": "bull", "confidence": 0.85})
    insight = kb.get("market_insight", "btc_trend")
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("trevlix.knowledge")

# Optionale LLM-Anbindung
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from services.llm_providers import MultiLLMProvider

    _MULTI_LLM_AVAILABLE = True
except ImportError:
    _MULTI_LLM_AVAILABLE = False


class KnowledgeBase:
    """Zentrales KI-Gemeinschaftswissen für alle User.

    Speichert Erkenntnisse aus Trading, KI-Modellen und Marktdaten
    in der DB und stellt sie allen Usern zur Verfügung.
    Unterstützt MCP-Tool-Integration für LLM-gestützte Analysen.
    """

    # Gültige Kategorien
    CATEGORIES = frozenset(
        {
            "market_insight",
            "strategy_perf",
            "symbol_info",
            "risk_pattern",
            "model_config",
            "trade_pattern",
            "anomaly_log",
        }
    )

    def __init__(
        self,
        db_manager,
        llm_endpoint: str = "",
        llm_api_key: str = "",
        llm_model: str = "",
    ):
        """Initialisiert die KnowledgeBase.

        Args:
            db_manager: MySQLManager-Instanz für DB-Zugriff.
            llm_endpoint: URL einer lokalen LLM-API (z.B. Ollama, LM Studio).
            llm_api_key: API-Key für die LLM-API (falls nötig).
            llm_model: Modellname (z.B. llama3, mistral). Pflicht für Ollama.
        """
        self._db = db_manager
        self._llm_endpoint = llm_endpoint
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        self._cache_ts: dict[str, float] = {}
        self._cache_ttl = 300  # 5 Minuten Cache
        self._cache_max_size = 500  # Max Einträge
        self._llm_cache: dict[str, str] = {}
        self._llm_cache_ts: dict[str, float] = {}
        self._llm_cache_ttl = 900  # 15 Minuten LLM-Response Cache
        self._llm_cache_max_size = 100  # Max LLM-Einträge
        self._cached_market_analysis: str = ""
        self._cached_market_analysis_ts: float = 0.0
        self._idle_learning = {
            "runs": 0,
            "last_run_ts": 0.0,
            "last_run_at": None,
            "last_summary": "",
            "last_error": "",
            "providers_used": 0,
            "responses_used": 0,
        }
        self._mcp_registry: Any = None  # MCPToolRegistry (lazy init)
        self._multi_llm: MultiLLMProvider | None = None
        if _MULTI_LLM_AVAILABLE:
            try:
                self._multi_llm = MultiLLMProvider()
                if self._multi_llm.available_providers:
                    log.info(
                        "Multi-LLM Provider aktiv: %s",
                        ", ".join(self._multi_llm.available_providers),
                    )
            except Exception as e:
                log.debug("Multi-LLM Init: %s", e)

    @staticmethod
    def _evict_cache(cache: dict, ts_dict: dict, max_size: int) -> None:
        """Entfernt die ältesten Einträge wenn Cache max_size überschreitet."""
        if len(cache) <= max_size:
            return
        sorted_keys = sorted(cache.keys(), key=lambda k: ts_dict.get(k, 0))  # type: ignore[arg-type]
        to_remove = len(cache) - max_size
        for k in sorted_keys[:to_remove]:
            cache.pop(k, None)
            ts_dict.pop(k, None)

    def store(
        self, category: str, key: str, value: Any, confidence: float = 0.5, source: str = "ai"
    ) -> bool:
        """Speichert eine Erkenntnis in der DB.

        Args:
            category: Kategorie der Erkenntnis.
            key: Eindeutiger Schlüssel innerhalb der Kategorie.
            value: Wert als Dict/List/String (wird als JSON gespeichert).
            confidence: Konfidenzwert (0.0-1.0).
            source: Quelle der Erkenntnis (ai, user, market, llm).

        Returns:
            True bei Erfolg.
        """
        if category not in self.CATEGORIES:
            log.warning(f"KnowledgeBase: Unbekannte Kategorie '{category}'")
            return False
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO shared_knowledge "
                        "(category, key_name, value_json, confidence, source) "
                        "VALUES(%s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE value_json=%s, confidence=%s, "
                        "source=%s, updated_at=NOW()",
                        (
                            category,
                            key,
                            json.dumps(value, ensure_ascii=False),
                            confidence,
                            source,
                            json.dumps(value, ensure_ascii=False),
                            confidence,
                            source,
                        ),
                    )
            # Cache invalidieren
            cache_key = f"{category}:{key}"
            self._cache.pop(cache_key, None)
            return True
        except Exception as e:
            log.error(f"KnowledgeBase.store: {e}")
            return False

    def get(self, category: str, key: str) -> dict | None:
        """Lädt eine Erkenntnis aus der DB (mit Cache).

        Args:
            category: Kategorie der Erkenntnis.
            key: Schlüssel innerhalb der Kategorie.

        Returns:
            Dict mit value, confidence, source, updated_at oder None.
        """
        cache_key = f"{category}:{key}"
        now = time.time()
        if cache_key in self._cache and now - self._cache_ts.get(cache_key, 0) < self._cache_ttl:
            return self._cache[cache_key]
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT value_json, confidence, source, updated_at "
                        "FROM shared_knowledge WHERE category=%s AND key_name=%s",
                        (category, key),
                    )
                    row = c.fetchone()
            if not row:
                return None
            try:
                parsed_value = json.loads(row["value_json"]) if row.get("value_json") else None
            except (json.JSONDecodeError, TypeError):
                log.warning(f"Korruptes JSON in knowledge '{category}/{key}', verwende None")
                parsed_value = None
            result = {
                "value": parsed_value,
                "confidence": row.get("confidence", 0.5),
                "source": row.get("source", "unknown"),
                "updated_at": (
                    row["updated_at"].isoformat() if row.get("updated_at") is not None else None
                ),
            }
            self._cache[cache_key] = result
            self._cache_ts[cache_key] = now
            self._evict_cache(self._cache, self._cache_ts, self._cache_max_size)
            return result
        except Exception as e:
            log.error(f"KnowledgeBase.get: {e}")
            return None

    def get_category(self, category: str, limit: int = 50) -> list[dict]:
        """Lädt alle Erkenntnisse einer Kategorie.

        Args:
            category: Kategorie.
            limit: Maximale Anzahl Ergebnisse.

        Returns:
            Liste von Dicts mit key, value, confidence, source, updated_at.
        """
        try:
            with self._db._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT key_name, value_json, confidence, source, updated_at "
                        "FROM shared_knowledge WHERE category=%s "
                        "ORDER BY updated_at DESC LIMIT %s",
                        (category, limit),
                    )
                    rows = c.fetchall()
            result = []
            for r in rows:
                try:
                    val = json.loads(r.get("value_json", "null")) if r.get("value_json") else None
                except (json.JSONDecodeError, TypeError):
                    val = None
                d = {
                    "key": r.get("key_name", ""),
                    "value": val,
                    "confidence": r.get("confidence", 0.5),
                    "source": r.get("source", "unknown"),
                    "updated_at": r.get("updated_at").isoformat() if r.get("updated_at") else None,
                }
                result.append(d)
            return result
        except Exception as e:
            log.error(f"KnowledgeBase.get_category: {e}")
            return []

    def learn_from_trade(self, trade: dict) -> None:
        """Extrahiert Erkenntnisse aus einem abgeschlossenen Trade.

        Speichert Strategie-Performance und Symbol-Informationen
        als Gemeinschaftswissen.

        Args:
            trade: Trade-Dict mit symbol, pnl, reason, confidence, etc.
        """
        symbol = trade.get("symbol", "")
        reason = trade.get("reason", "")
        pnl = trade.get("pnl", 0)
        regime = trade.get("regime", "bull")

        # Symbol-Info aktualisieren
        sym_info = self.get("symbol_info", symbol)
        if sym_info and sym_info.get("value"):
            data = sym_info["value"]
            data["total_trades"] = data.get("total_trades", 0) + 1
            data["total_pnl"] = data.get("total_pnl", 0) + pnl
            data["wins"] = data.get("wins", 0) + (1 if pnl > 0 else 0)
            data["last_regime"] = regime
            data["last_trade"] = datetime.now(UTC).isoformat()
            wr = data["wins"] / data["total_trades"] if data["total_trades"] > 0 else 0
        else:
            data = {
                "total_trades": 1,
                "total_pnl": pnl,
                "wins": 1 if pnl > 0 else 0,
                "last_regime": regime,
                "last_trade": datetime.now(UTC).isoformat(),
            }
            wr = 1.0 if pnl > 0 else 0.0
        self.store("symbol_info", symbol, data, confidence=min(wr, 0.95), source="trade")

        # Strategie-Performance aktualisieren
        if reason:
            strat_key = f"{reason}_{regime}"
            strat_info = self.get("strategy_perf", strat_key)
            if strat_info and strat_info.get("value"):
                sd = strat_info["value"]
                sd["trades"] = sd.get("trades", 0) + 1
                sd["pnl"] = sd.get("pnl", 0) + pnl
                sd["wins"] = sd.get("wins", 0) + (1 if pnl > 0 else 0)
            else:
                sd = {"trades": 1, "pnl": pnl, "wins": 1 if pnl > 0 else 0}
            swr = sd["wins"] / sd["trades"] if sd["trades"] > 0 else 0
            self.store("strategy_perf", strat_key, sd, confidence=swr, source="trade")

    @property
    def _is_ollama(self) -> bool:
        """Erkennt ob der Endpunkt eine Ollama-Instanz ist."""
        return "11434" in self._llm_endpoint or "/api/chat" in self._llm_endpoint

    def query_llm(self, prompt: str, context: str = "") -> str | None:
        """Fragt eine lokale LLM-Instanz nach Analyse/Empfehlung.

        Unterstützt Ollama, LM Studio, oder jede OpenAI-kompatible API.

        Args:
            prompt: Die Frage/Aufgabe für die LLM.
            context: Zusätzlicher Kontext (z.B. aktuelle Marktdaten).

        Returns:
            LLM-Antwort als String oder None bei Fehler.
        """
        # Multi-LLM Fallback wenn kein lokaler Endpunkt konfiguriert
        if not self._llm_endpoint and self._multi_llm:
            return self._multi_llm.chat(prompt, system=context)
        if not self._llm_endpoint or not HTTPX_AVAILABLE:
            return None
        try:
            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": prompt})

            headers = {"Content-Type": "application/json"}
            if self._llm_api_key:
                headers["Authorization"] = f"Bearer {self._llm_api_key}"

            # Ollama erwartet zwingend "model" und "stream": false
            if self._is_ollama:
                model = self._llm_model or "llama3"
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 500},
                }
            else:
                # OpenAI-kompatibles Format (LM Studio, vLLM, etc.)
                payload = {
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 500,
                }
                if self._llm_model:
                    payload["model"] = self._llm_model

            resp = httpx.post(
                self._llm_endpoint,
                json=payload,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Ollama /api/chat Format: {"message": {"content": "..."}}
                if self._is_ollama:
                    answer = data.get("message", {}).get("content", "")
                    if not answer:
                        answer = data.get("response", "")
                    return answer or None
                # OpenAI-kompatibles Format
                choices = data.get("choices") or []
                answer = (
                    choices[0].get("message", {}).get("content", "")
                    if choices and isinstance(choices[0], dict)
                    else ""
                )
                return answer or None
            log.warning(f"LLM Query fehlgeschlagen: HTTP {resp.status_code}")
            return None
        except Exception as e:
            log.debug(f"LLM Query: {e}")
            return None

    def get_market_summary(self) -> dict:
        """Erstellt eine Zusammenfassung des aktuellen Marktwissens.

        Returns:
            Dict mit Marktinsights, Top-Symbolen und Strategie-Rankings.
        """
        insights = self.get_category("market_insight", limit=10)
        symbols = self.get_category("symbol_info", limit=20)
        strategies = self.get_category("strategy_perf", limit=20)

        # Top-Symbole nach Win-Rate
        top_symbols = []
        for s in symbols:
            v = s.get("value") or {}
            total_trades = v.get("total_trades", 0)
            if total_trades >= 3:
                wr = v.get("wins", 0) / max(total_trades, 1)
                top_symbols.append(
                    {
                        "symbol": s.get("key", "?"),
                        "win_rate": round(wr, 2),
                        "trades": total_trades,
                        "pnl": round(v.get("total_pnl", 0), 2),
                    }
                )
        top_symbols.sort(key=lambda x: x["win_rate"], reverse=True)

        # Strategie-Ranking
        strat_ranking = []
        for s in strategies:
            v = s.get("value") or {}
            num_trades = v.get("trades", 0)
            if num_trades >= 2:
                wr = v.get("wins", 0) / max(num_trades, 1)
                strat_ranking.append(
                    {
                        "strategy": s.get("key", "?"),
                        "win_rate": round(wr, 2),
                        "trades": num_trades,
                        "pnl": round(v.get("pnl", 0), 2),
                    }
                )
        strat_ranking.sort(key=lambda x: x["win_rate"], reverse=True)

        return {
            "insights": insights[:5],
            "top_symbols": top_symbols[:10],
            "strategy_ranking": strat_ranking[:10],
            "total_knowledge_entries": len(insights) + len(symbols) + len(strategies),
        }

    def set_mcp_registry(self, registry: Any) -> None:
        """Setzt die MCP-Tool-Registry für Tool-Use-Unterstützung.

        Args:
            registry: MCPToolRegistry-Instanz.
        """
        self._mcp_registry = registry
        log.info("MCP-Tool-Registry verbunden (%d Tools)", len(registry.get_tools_schema()))

    def query_llm_with_tools(
        self, prompt: str, context: str = "", max_rounds: int = 3
    ) -> str | None:
        """LLM-Abfrage mit automatischem MCP-Tool-Use.

        Sendet den Prompt an die LLM mit Tool-Definitionen.
        Falls die LLM Tool-Calls zurückgibt, werden diese ausgeführt
        und die Ergebnisse in einer Folgenachricht zurückgegeben.

        Args:
            prompt: Die Frage/Aufgabe für die LLM.
            context: System-Kontext.
            max_rounds: Maximale Tool-Use-Runden.

        Returns:
            Finale LLM-Antwort als String oder None bei Fehler.
        """
        if not self._llm_endpoint or not HTTPX_AVAILABLE:
            return None
        if not self._mcp_registry:
            return self.query_llm(prompt, context)

        try:
            messages: list[dict[str, Any]] = []
            tools_desc = self._mcp_registry.get_tool_descriptions()
            system_ctx = (
                (
                    f"{context}\n\n{tools_desc}\n\n"
                    "Du kannst diese Tools nutzen um aktuelle Daten abzurufen. "
                    "Rufe Tools auf indem du JSON im Format "
                    '{"tool": "name", "args": {...}} zurückgibst. '
                    "Antworte nach Tool-Ergebnissen mit deiner finalen Analyse."
                )
                if context
                else (f"{tools_desc}\n\nDu kannst diese Tools nutzen um aktuelle Daten abzurufen.")
            )
            messages.append({"role": "system", "content": system_ctx})
            messages.append({"role": "user", "content": prompt})

            headers = {"Content-Type": "application/json"}
            if self._llm_api_key:
                headers["Authorization"] = f"Bearer {self._llm_api_key}"

            tools_schema = self._mcp_registry.get_tools_schema()

            for _round in range(max_rounds):
                if self._is_ollama:
                    payload: dict[str, Any] = {
                        "model": self._llm_model or "llama3",
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 800},
                    }
                else:
                    payload = {
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 800,
                        "tools": tools_schema,
                    }
                    if self._llm_model:
                        payload["model"] = self._llm_model

                resp = httpx.post(
                    self._llm_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=45,
                )
                if resp.status_code != 200:
                    log.warning("LLM Tool-Query HTTP %d", resp.status_code)
                    return None

                data = resp.json()

                # Prüfe auf Tool-Calls in der Antwort
                if self._is_ollama:
                    answer = data.get("message", {}).get("content", "")
                    # Ollama: Prüfe ob Antwort einen Tool-Call enthält
                    tool_call = self._parse_tool_call_from_text(answer)
                    if tool_call and _round < max_rounds - 1:
                        result = self._mcp_registry.execute(
                            tool_call["tool"], tool_call.get("args", {})
                        )
                        messages.append({"role": "assistant", "content": answer})
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Tool-Ergebnis für {tool_call['tool']}: "
                                f"{json.dumps(result, ensure_ascii=False, default=str)}\n\n"
                                "Bitte gib jetzt deine finale Analyse basierend auf diesen Daten.",
                            }
                        )
                        continue
                    return answer or None

                # OpenAI-kompatibles Format: Prüfe auf tool_calls
                choices = data.get("choices") or []
                if not choices:
                    return None
                message = choices[0].get("message", {})
                tool_calls = message.get("tool_calls")

                if tool_calls and _round < max_rounds - 1:
                    # Tool-Calls ausführen
                    messages.append(message)
                    results = self._mcp_registry.process_tool_calls(tool_calls)
                    for r in results:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": r["tool_call_id"],
                                "content": r["result"],
                            }
                        )
                    continue

                # Finale Antwort
                return message.get("content") or None

            return None
        except Exception as e:
            log.debug("LLM Tool-Query: %s", e)
            return None

    @staticmethod
    def _parse_tool_call_from_text(text: str) -> dict[str, Any] | None:
        """Versucht einen Tool-Call aus Freitext zu extrahieren.

        Unterstützt Ollama-Modelle die kein natives tool_use haben.

        Args:
            text: LLM-Antwort als Freitext.

        Returns:
            Dict mit 'tool' und 'args' oder None.
        """
        try:
            # Suche nach JSON-Block im Text
            start = text.find('{"tool"')
            if start == -1:
                return None
            # Finde das Ende des JSON-Blocks
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > start:
                parsed = json.loads(text[start:end])
                if "tool" in parsed:
                    return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @property
    def llm_enabled(self) -> bool:
        """Prüft ob LLM-Endpunkt konfiguriert und verfügbar ist."""
        local_ready = bool(self._llm_endpoint) and HTTPX_AVAILABLE
        multi_ready = bool(self._multi_llm and self._multi_llm.available_providers)
        return local_ready or multi_ready

    @property
    def cached_market_analysis(self) -> str:
        """Letztes gecachtes Markt-Analyse-Ergebnis der LLM."""
        return self._cached_market_analysis

    def idle_learning_status(self) -> dict[str, Any]:
        """Status des Leerlauf-Lernzyklus für Diagnose/UI."""
        with self._lock:
            return dict(self._idle_learning)

    def idle_learn_async(
        self,
        *,
        regime_is_bull: bool,
        fg_value: int,
        open_positions: int,
        iteration: int,
        min_interval_sec: int = 600,
    ) -> None:
        """Startet einen Leerlauf-Lernzyklus mit Multi-LLM-Kollaboration."""
        if not self.llm_enabled:
            return
        now = time.time()
        with self._lock:
            last_run = float(self._idle_learning.get("last_run_ts", 0) or 0)
            if now - last_run < max(min_interval_sec, 30):
                return
            self._idle_learning["last_run_ts"] = now
        threading.Thread(
            target=self._idle_learn_cycle,
            args=(regime_is_bull, fg_value, open_positions, iteration),
            daemon=True,
        ).start()

    def _idle_learn_cycle(
        self,
        regime_is_bull: bool,
        fg_value: int,
        open_positions: int,
        iteration: int,
    ) -> None:
        """Interner Leerlauf-Lernzyklus: mehrere LLMs + Synthese."""
        try:
            summary = self.get_market_summary()
            top_syms = json.dumps(summary.get("top_symbols", [])[:5], ensure_ascii=False)
            top_strats = json.dumps(summary.get("strategy_ranking", [])[:5], ensure_ascii=False)
            context = (
                "Du bist Teil eines Trading-AI-Kollektivs. "
                "Bewerte Risiko, Chancen und Lernfokus für das Modelltraining. "
                "Antworte kurz auf Deutsch."
            )
            prompt = (
                f"Leerlauf-Lernzyklus:\n"
                f"Regime: {'bull' if regime_is_bull else 'bear'}\n"
                f"Fear&Greed: {fg_value}\n"
                f"Offene Positionen: {open_positions}\n"
                f"Iteration: {iteration}\n"
                f"Top Symbole: {top_syms}\n"
                f"Top Strategien: {top_strats}\n"
                "Was soll das selbstlernende Modell als Nächstes priorisieren?"
            )
            provider_count = 0
            responses: list[dict[str, Any]] = []
            if self._multi_llm and hasattr(self._multi_llm, "chat_all"):
                responses = self._multi_llm.chat_all(prompt=prompt, system=context, max_tokens=300)
                provider_count = len(getattr(self._multi_llm, "available_providers", []))

            usable = [r for r in responses if r.get("ok") and r.get("answer")]
            if usable:
                stitched = "\n".join(
                    [
                        f"{r.get('provider', 'llm')}: {str(r.get('answer', ''))[:220]}"
                        for r in usable[:4]
                    ]
                )
                synth_prompt = (
                    "Fasse diese LLM-Meinungen zu einer kurzen, umsetzbaren Lernanweisung "
                    "für ein selbstlernendes Trading-Modell zusammen:\n"
                    f"{stitched}"
                )
                final_answer = self.query_llm(synth_prompt, context) or stitched
            else:
                final_answer = self.query_llm(prompt, context)

            if not final_answer:
                return

            insight_key = f"idle_collab_{int(time.time())}"
            self.store(
                "model_config",
                insight_key,
                {
                    "type": "idle_learning",
                    "iteration": iteration,
                    "regime": "bull" if regime_is_bull else "bear",
                    "fg_value": fg_value,
                    "providers_used": provider_count,
                    "responses_used": len(usable),
                    "summary": final_answer[:600],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                confidence=0.62 if usable else 0.55,
                source="llm",
            )

            with self._lock:
                self._idle_learning["runs"] = int(self._idle_learning.get("runs", 0) or 0) + 1
                self._idle_learning["last_run_at"] = datetime.now(UTC).isoformat()
                self._idle_learning["last_summary"] = final_answer[:220]
                self._idle_learning["last_error"] = ""
                self._idle_learning["providers_used"] = provider_count
                self._idle_learning["responses_used"] = len(usable)
        except Exception as e:
            with self._lock:
                self._idle_learning["last_error"] = str(e)[:180]
            log.debug("Idle-Learning-Zyklus: %s", e)

    def _query_llm_cached(self, cache_key: str, prompt: str, context: str = "") -> str | None:
        """LLM-Abfrage mit Cache um redundante Anfragen zu vermeiden.

        Args:
            cache_key: Eindeutiger Schlüssel für den Cache.
            prompt: Die Frage/Aufgabe für die LLM.
            context: Zusätzlicher Kontext.

        Returns:
            LLM-Antwort als String oder None bei Fehler/Cache-Miss.
        """
        now = time.time()
        with self._lock:
            if cache_key in self._llm_cache:
                if now - self._llm_cache_ts.get(cache_key, 0) < self._llm_cache_ttl:
                    return self._llm_cache[cache_key]
        answer = self.query_llm(prompt, context)
        if answer:
            with self._lock:
                self._llm_cache[cache_key] = answer
                self._llm_cache_ts[cache_key] = now
                self._evict_cache(self._llm_cache, self._llm_cache_ts, self._llm_cache_max_size)
        return answer

    def analyze_trade_async(self, trade: dict, features: dict | None = None) -> None:
        """Analysiert einen abgeschlossenen Trade asynchron per LLM.

        Sendet Trade-Daten an die LLM und speichert die Erkenntnisse
        als Gemeinschaftswissen. Läuft in einem eigenen Thread.

        Args:
            trade: Trade-Dict mit symbol, pnl, pnl_pct, reason, etc.
            features: Optionale Feature-Daten des Trades.
        """
        if not self.llm_enabled:
            return
        threading.Thread(
            target=self._analyze_trade,
            args=(trade, features),
            daemon=True,
        ).start()

    def _analyze_trade(self, trade: dict, features: dict | None = None) -> None:
        """Interne Trade-Analyse per LLM (synchron, für Thread-Ausführung).

        Args:
            trade: Trade-Dict.
            features: Optionale Feature-Daten.
        """
        try:
            symbol = str(trade.get("symbol", "?"))[:20]
            pnl = trade.get("pnl", 0)
            pnl_pct = trade.get("pnl_pct", 0)
            reason = str(trade.get("reason", ""))[:100]
            regime = str(trade.get("regime", "unknown"))[:30]
            won = pnl > 0

            context = (
                "Du bist ein Krypto-Trading-Analyst. Analysiere diesen Trade "
                "und gib kurze, umsetzbare Erkenntnisse. Antworte auf Deutsch. "
                "Maximal 3 Sätze."
            )
            prompt = (
                f"Trade: {symbol} | {'Gewinn' if won else 'Verlust'} "
                f"{pnl:+.2f} USDT ({pnl_pct:+.2f}%) | "
                f"Strategie: {reason} | Regime: {regime}"
            )
            if features:
                prompt += f" | RSI: {features.get('rsi', '?')}"
                prompt += f" | News-Score: {features.get('news_score', '?')}"

            prompt += (
                "\nWarum war dieser Trade "
                f"{'erfolgreich' if won else 'ein Verlust'}? "
                "Was kann optimiert werden?"
            )

            answer = self.query_llm(prompt, context)
            if not answer:
                return

            # Erkenntnis speichern
            insight_key = f"trade_analysis_{symbol}_{int(time.time())}"
            self.store(
                "trade_pattern",
                insight_key,
                {
                    "symbol": symbol,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "won": won,
                    "reason": reason,
                    "regime": regime,
                    "llm_analysis": answer[:500],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                confidence=0.7 if won else 0.5,
                source="llm",
            )
            log.info(f"🤖 LLM Trade-Analyse {symbol}: {answer[:100]}...")

        except Exception as e:
            log.debug(f"LLM Trade-Analyse: {e}")

    def generate_market_context_async(
        self,
        regime_is_bull: bool,
        fg_value: int,
        open_positions: int,
        iteration: int,
    ) -> None:
        """Generiert periodisch eine LLM-Marktanalyse (async).

        Wird im Bot-Loop alle ~60 Iterationen aufgerufen.
        Ergebnis wird gecacht und für spätere Entscheidungen genutzt.

        Args:
            regime_is_bull: Aktuelles Markt-Regime.
            fg_value: Fear & Greed Index Wert.
            open_positions: Anzahl offener Positionen.
            iteration: Aktuelle Bot-Iteration.
        """
        if not self.llm_enabled:
            return
        # Nur alle 15 Minuten neu generieren
        now = time.time()
        if now - self._cached_market_analysis_ts < 900:
            return
        threading.Thread(
            target=self._generate_market_context,
            args=(regime_is_bull, fg_value, open_positions, iteration),
            daemon=True,
        ).start()

    def _generate_market_context(
        self,
        regime_is_bull: bool,
        fg_value: int,
        open_positions: int,
        iteration: int,
    ) -> None:
        """Interne Markt-Kontext-Generierung per LLM (synchron).

        Args:
            regime_is_bull: Aktuelles Markt-Regime.
            fg_value: Fear & Greed Index Wert.
            open_positions: Anzahl offener Positionen.
            iteration: Aktuelle Bot-Iteration.
        """
        try:
            summary = self.get_market_summary()
            top_syms = json.dumps(summary.get("top_symbols", [])[:5], ensure_ascii=False)
            strat_rank = json.dumps(summary.get("strategy_ranking", [])[:5], ensure_ascii=False)

            context = (
                "Du bist ein Krypto-Trading-Analyst. Erstelle eine kurze "
                "Marktanalyse und Handlungsempfehlung. Antworte auf Deutsch. "
                "Maximal 5 Sätze."
            )
            prompt = (
                f"Marktregime: {'Bullenmarkt' if regime_is_bull else 'Bärenmarkt'}\n"
                f"Fear & Greed Index: {fg_value}/100\n"
                f"Offene Positionen: {open_positions}\n"
                f"Top Symbole: {top_syms}\n"
                f"Strategie-Performance: {strat_rank}\n"
                f"Wissenseinträge: {summary.get('total_knowledge_entries', 0)}\n\n"
                "Bewertung: Wie ist die aktuelle Marktstimmung? "
                "Sollte aggressiver oder defensiver gehandelt werden?"
            )

            # MCP-Tool-gestützte Analyse bevorzugen
            if self._mcp_registry:
                answer = self.query_llm_with_tools(prompt, context, max_rounds=2)
            else:
                answer = self._query_llm_cached("market_context", prompt, context)
            if not answer:
                return

            self._cached_market_analysis = answer
            self._cached_market_analysis_ts = time.time()

            # Als Market Insight speichern
            self.store(
                "market_insight",
                "llm_market_context",
                {
                    "analysis": answer[:500],
                    "regime": "bull" if regime_is_bull else "bear",
                    "fg_value": fg_value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                confidence=0.65,
                source="llm",
            )
            log.info(f"🤖 LLM Marktanalyse: {answer[:80]}...")

        except Exception as e:
            log.debug(f"LLM Marktanalyse: {e}")

    def analyze_training_async(
        self,
        training_ver: int,
        wf_accuracy: float,
        bull_accuracy: float,
        bear_accuracy: float,
        feature_weights: dict[str, float],
        threshold: float,
    ) -> None:
        """Analysiert KI-Training-Ergebnisse per LLM (async).

        Wird nach jedem 3. Training aufgerufen um Modell-Verhalten
        zu interpretieren.

        Args:
            training_ver: Aktuelle Trainingsversion.
            wf_accuracy: Walk-Forward Genauigkeit.
            bull_accuracy: Bull-Regime Genauigkeit.
            bear_accuracy: Bear-Regime Genauigkeit.
            feature_weights: Strategie-Gewichte aus Feature-Importance.
            threshold: Optimierter Entscheidungsschwellwert.
        """
        if not self.llm_enabled:
            return
        # Nur alle 3 Trainings
        if training_ver % 3 != 0:
            return
        threading.Thread(
            target=self._analyze_training,
            args=(
                training_ver,
                wf_accuracy,
                bull_accuracy,
                bear_accuracy,
                feature_weights,
                threshold,
            ),
            daemon=True,
        ).start()

    def _analyze_training(
        self,
        training_ver: int,
        wf_accuracy: float,
        bull_accuracy: float,
        bear_accuracy: float,
        feature_weights: dict[str, float],
        threshold: float,
    ) -> None:
        """Interne Training-Analyse per LLM (synchron).

        Args:
            training_ver: Aktuelle Trainingsversion.
            wf_accuracy: Walk-Forward Genauigkeit.
            bull_accuracy: Bull-Regime Genauigkeit.
            bear_accuracy: Bear-Regime Genauigkeit.
            feature_weights: Strategie-Gewichte.
            threshold: Entscheidungsschwellwert.
        """
        try:
            weights_str = ", ".join(
                f"{k}: {v:.2f}"
                for k, v in sorted(feature_weights.items(), key=lambda x: x[1], reverse=True)
            )

            context = (
                "Du bist ein ML-Experte für Trading-Modelle. "
                "Analysiere die Trainingsergebnisse und gib "
                "Optimierungsvorschläge. Antworte auf Deutsch. "
                "Maximal 4 Sätze."
            )
            prompt = (
                f"KI-Modell v{training_ver}:\n"
                f"Walk-Forward Accuracy: {wf_accuracy * 100:.1f}%\n"
                f"Bull-Accuracy: {bull_accuracy * 100:.1f}%\n"
                f"Bear-Accuracy: {bear_accuracy * 100:.1f}%\n"
                f"Schwellwert: {threshold:.3f}\n"
                f"Strategie-Gewichte: {weights_str}\n\n"
                "Interpretation: Welche Strategien dominieren? "
                "Gibt es Anzeichen für Overfitting? "
                "Welche Anpassungen wären sinnvoll?"
            )

            answer = self.query_llm(prompt, context)
            if not answer:
                return

            self.store(
                "model_config",
                f"training_analysis_v{training_ver}",
                {
                    "version": training_ver,
                    "wf_accuracy": round(wf_accuracy * 100, 1),
                    "bull_accuracy": round(bull_accuracy * 100, 1),
                    "bear_accuracy": round(bear_accuracy * 100, 1),
                    "threshold": round(threshold, 3),
                    "llm_analysis": answer[:500],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                confidence=0.6,
                source="llm",
            )
            log.info(f"🤖 LLM Training-Analyse v{training_ver}: {answer[:80]}...")

        except Exception as e:
            log.debug(f"LLM Training-Analyse: {e}")

    def analyze_optimization_async(
        self,
        best_sl: float,
        best_tp: float,
        prev_sl: float,
        prev_tp: float,
        trade_count: int,
    ) -> None:
        """Analysiert SL/TP-Optimierungsergebnisse per LLM (async).

        Args:
            best_sl: Optimierter Stop-Loss in Prozent.
            best_tp: Optimierter Take-Profit in Prozent.
            prev_sl: Vorheriger Stop-Loss.
            prev_tp: Vorheriger Take-Profit.
            trade_count: Anzahl Trades in der Optimierung.
        """
        if not self.llm_enabled:
            return
        threading.Thread(
            target=self._analyze_optimization,
            args=(best_sl, best_tp, prev_sl, prev_tp, trade_count),
            daemon=True,
        ).start()

    def _analyze_optimization(
        self,
        best_sl: float,
        best_tp: float,
        prev_sl: float,
        prev_tp: float,
        trade_count: int,
    ) -> None:
        """Interne Optimierungs-Analyse per LLM (synchron).

        Args:
            best_sl: Optimierter Stop-Loss.
            best_tp: Optimierter Take-Profit.
            prev_sl: Vorheriger Stop-Loss.
            prev_tp: Vorheriger Take-Profit.
            trade_count: Anzahl Trades.
        """
        try:
            sl_change = (best_sl - prev_sl) * 100
            tp_change = (best_tp - prev_tp) * 100
            ratio = best_tp / best_sl if best_sl > 0 else 0

            context = (
                "Du bist ein Risk-Management-Experte. "
                "Bewerte die SL/TP-Optimierung. Antworte auf Deutsch. "
                "Maximal 3 Sätze."
            )
            prompt = (
                f"SL/TP Optimierung (basierend auf {trade_count} Trades):\n"
                f"Stop-Loss: {prev_sl * 100:.1f}% → {best_sl * 100:.1f}% "
                f"({sl_change:+.1f}pp)\n"
                f"Take-Profit: {prev_tp * 100:.1f}% → {best_tp * 100:.1f}% "
                f"({tp_change:+.1f}pp)\n"
                f"Risk/Reward Ratio: 1:{ratio:.1f}\n\n"
                "Ist diese Anpassung sinnvoll? Gibt es Risiken?"
            )

            answer = self.query_llm(prompt, context)
            if not answer:
                return

            self.store(
                "risk_pattern",
                f"sltp_optimization_{int(time.time())}",
                {
                    "best_sl": round(best_sl * 100, 1),
                    "best_tp": round(best_tp * 100, 1),
                    "prev_sl": round(prev_sl * 100, 1),
                    "prev_tp": round(prev_tp * 100, 1),
                    "ratio": round(ratio, 1),
                    "trade_count": trade_count,
                    "llm_analysis": answer[:500],
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                confidence=0.6,
                source="llm",
            )
            log.info(f"🤖 LLM SL/TP-Analyse: {answer[:80]}...")

        except Exception as e:
            log.debug(f"LLM Optimierungs-Analyse: {e}")
