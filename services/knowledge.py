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
import time
from datetime import datetime
from typing import Any

log = logging.getLogger("NEXUS")

# Optionale LLM-Anbindung
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class KnowledgeBase:
    """Zentrales KI-Gemeinschaftswissen für alle User.

    Speichert Erkenntnisse aus Trading, KI-Modellen und Marktdaten
    in der DB und stellt sie allen Usern zur Verfügung.
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

    def __init__(self, db_manager, llm_endpoint: str = "", llm_api_key: str = ""):
        """Initialisiert die KnowledgeBase.

        Args:
            db_manager: MySQLManager-Instanz für DB-Zugriff.
            llm_endpoint: URL einer lokalen LLM-API (z.B. Ollama, LM Studio).
            llm_api_key: API-Key für die LLM-API (falls nötig).
        """
        self._db = db_manager
        self._llm_endpoint = llm_endpoint
        self._llm_api_key = llm_api_key
        self._cache: dict[str, dict] = {}
        self._cache_ts: dict[str, float] = {}
        self._cache_ttl = 300  # 5 Minuten Cache

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
            result = {
                "value": json.loads(row["value_json"]) if row.get("value_json") else None,
                "confidence": row.get("confidence", 0.5),
                "source": row.get("source", "unknown"),
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
            }
            self._cache[cache_key] = result
            self._cache_ts[cache_key] = now
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
                d = {
                    "key": r["key_name"],
                    "value": json.loads(r["value_json"]) if r["value_json"] else None,
                    "confidence": r["confidence"],
                    "source": r["source"],
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
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
            data["last_trade"] = datetime.now().isoformat()
            wr = data["wins"] / data["total_trades"] if data["total_trades"] > 0 else 0
        else:
            data = {
                "total_trades": 1,
                "total_pnl": pnl,
                "wins": 1 if pnl > 0 else 0,
                "last_regime": regime,
                "last_trade": datetime.now().isoformat(),
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

    def query_llm(self, prompt: str, context: str = "") -> str | None:
        """Fragt eine lokale LLM-Instanz nach Analyse/Empfehlung.

        Unterstützt Ollama, LM Studio, oder jede OpenAI-kompatible API.

        Args:
            prompt: Die Frage/Aufgabe für die LLM.
            context: Zusätzlicher Kontext (z.B. aktuelle Marktdaten).

        Returns:
            LLM-Antwort als String oder None bei Fehler.
        """
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

            resp = httpx.post(
                self._llm_endpoint,
                json={"messages": messages, "temperature": 0.3, "max_tokens": 500},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                # OpenAI-kompatibles Format
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not answer:
                    # Ollama-Format
                    answer = data.get("response", "")
                return answer
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
            v = s.get("value", {})
            if v.get("total_trades", 0) >= 3:
                wr = v.get("wins", 0) / v["total_trades"]
                top_symbols.append(
                    {
                        "symbol": s["key"],
                        "win_rate": round(wr, 2),
                        "trades": v["total_trades"],
                        "pnl": round(v.get("total_pnl", 0), 2),
                    }
                )
        top_symbols.sort(key=lambda x: x["win_rate"], reverse=True)

        # Strategie-Ranking
        strat_ranking = []
        for s in strategies:
            v = s.get("value", {})
            if v.get("trades", 0) >= 2:
                wr = v.get("wins", 0) / v["trades"]
                strat_ranking.append(
                    {
                        "strategy": s["key"],
                        "win_rate": round(wr, 2),
                        "trades": v["trades"],
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
