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
        self._cache_max_size = 500  # Max Einträge
        self._llm_cache: dict[str, str] = {}
        self._llm_cache_ts: dict[str, float] = {}
        self._llm_cache_ttl = 900  # 15 Minuten LLM-Response Cache
        self._llm_cache_max_size = 100  # Max LLM-Einträge
        self._cached_market_analysis: str = ""
        self._cached_market_analysis_ts: float = 0.0

    @staticmethod
    def _evict_cache(cache: dict, ts_dict: dict, max_size: int) -> None:
        """Entfernt die ältesten Einträge wenn Cache max_size überschreitet."""
        if len(cache) <= max_size:
            return
        sorted_keys = sorted(ts_dict, key=ts_dict.get)  # type: ignore[arg-type]
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
            except json.JSONDecodeError:
                log.warning(f"Korruptes JSON in knowledge '{category}/{key}', verwende None")
                parsed_value = None
            result = {
                "value": parsed_value,
                "confidence": row.get("confidence", 0.5),
                "source": row.get("source", "unknown"),
                "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
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
                choices = data.get("choices") or []
                answer = choices[0].get("message", {}).get("content", "") if choices else ""
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
            v = s.get("value") or {}
            total_trades = v.get("total_trades", 0)
            if total_trades >= 3:
                wr = v.get("wins", 0) / total_trades
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
                wr = v.get("wins", 0) / num_trades
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

    @property
    def llm_enabled(self) -> bool:
        """Prüft ob LLM-Endpunkt konfiguriert und verfügbar ist."""
        return bool(self._llm_endpoint) and HTTPX_AVAILABLE

    @property
    def cached_market_analysis(self) -> str:
        """Letztes gecachtes Markt-Analyse-Ergebnis der LLM."""
        return self._cached_market_analysis

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
        if cache_key in self._llm_cache:
            if now - self._llm_cache_ts.get(cache_key, 0) < self._llm_cache_ttl:
                return self._llm_cache[cache_key]
        answer = self.query_llm(prompt, context)
        if answer:
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
            symbol = trade.get("symbol", "?")
            pnl = trade.get("pnl", 0)
            pnl_pct = trade.get("pnl_pct", 0)
            reason = trade.get("reason", "")
            regime = trade.get("regime", "unknown")
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
                    "timestamp": datetime.now().isoformat(),
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
                    "timestamp": datetime.now().isoformat(),
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
                    "timestamp": datetime.now().isoformat(),
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
                    "timestamp": datetime.now().isoformat(),
                },
                confidence=0.6,
                source="llm",
            )
            log.info(f"🤖 LLM SL/TP-Analyse: {answer[:80]}...")

        except Exception as e:
            log.debug(f"LLM Optimierungs-Analyse: {e}")
