"""Market intelligence repository: sentiment + news + on-chain + arbitrage.

Per-row CRUD for the cache tables ``sentiment_cache``, ``news_cache``,
``onchain_cache``, plus the ``arb_opportunities`` write path and the
``daily_reports`` read/write helpers.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    from app.core import db_manager as _m

    return _m


class IntelRepository:
    """Per-row CRUD for sentiment / news / onchain caches + reports + arb."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    # ── Daily reports ───────────────────────────────────────────────────────
    def save_daily_report(self, date_str: str, report: dict):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO daily_reports (report_date,report_json)
                        VALUES(%s,%s) ON DUPLICATE KEY UPDATE
                        report_json=%s,sent_at=NOW()""",
                        (date_str, json.dumps(report), json.dumps(report)),
                    )
        except Exception as e:
            log.error(f"save_daily_report: {e}")

    def report_sent_today(self) -> bool:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT id FROM daily_reports WHERE report_date=CURDATE()")
                    row = c.fetchone()
            return row is not None
        except Exception as e:
            log.error(f"report_sent_today: {e}")
            return False

    # ── Sentiment ───────────────────────────────────────────────────────────
    def save_sentiment(self, symbol: str, score: float, source: str):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO sentiment_cache (symbol,score,source,updated_at)
                        VALUES(%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE score=%s,source=%s,updated_at=NOW()""",
                        (symbol, score, source, score, source),
                    )
        except Exception as e:
            log.error(f"save_sentiment({symbol!r}): {e}")

    def get_sentiment(self, symbol: str) -> float | None:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT score FROM sentiment_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 2 HOUR""",
                        (symbol,),
                    )
                    row = c.fetchone()
            if row and row.get("score") is not None:
                return float(row["score"])
            return None
        except Exception as e:
            log.error(f"get_sentiment({symbol!r}): {e}")
            return None

    # ── News ────────────────────────────────────────────────────────────────
    def save_news(self, symbol: str, score: float, headline: str, count: int):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO news_cache
                        (symbol,score,headline,article_count,updated_at)
                        VALUES(%s,%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE score=%s,headline=%s,article_count=%s,updated_at=NOW()""",
                        (symbol, score, headline[:500], count, score, headline[:500], count),
                    )
        except Exception as e:
            log.error(f"save_news({symbol!r}): {e}")

    def get_news(self, symbol: str) -> dict | None:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT score,headline,article_count FROM news_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 30 MINUTE""",
                        (symbol,),
                    )
                    row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            log.error(f"get_news({symbol!r}): {e}")
            return None

    # ── On-chain ────────────────────────────────────────────────────────────
    def save_onchain(self, symbol: str, whale_score: float, flow_score: float, detail: str):
        log = _module().log
        whale_score = whale_score if whale_score is not None else 0.0
        flow_score = flow_score if flow_score is not None else 0.0
        net = (whale_score + flow_score) / 2
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO onchain_cache
                        (symbol,whale_score,flow_score,net_score,detail,updated_at)
                        VALUES(%s,%s,%s,%s,%s,NOW()) ON DUPLICATE KEY
                        UPDATE whale_score=%s,flow_score=%s,net_score=%s,detail=%s,
                               updated_at=NOW()""",
                        (
                            symbol,
                            whale_score,
                            flow_score,
                            net,
                            detail[:500],
                            whale_score,
                            flow_score,
                            net,
                            detail[:500],
                        ),
                    )
        except Exception as e:
            log.error(f"save_onchain({symbol!r}): {e}")

    def get_onchain(self, symbol: str) -> dict | None:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """SELECT whale_score,flow_score,net_score,detail FROM onchain_cache
                        WHERE symbol=%s AND updated_at > NOW() - INTERVAL 1 HOUR""",
                        (symbol,),
                    )
                    row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            log.error(f"get_onchain({symbol!r}): {e}")
            return None

    # ── Arbitrage ───────────────────────────────────────────────────────────
    def save_arb(self, arb: dict):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO arb_opportunities
                        (symbol,exchange_buy,price_buy,exchange_sell,price_sell,
                         spread_pct,executed,profit)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            arb.get("symbol", "UNKNOWN"),
                            arb.get("exchange_buy", ""),
                            arb.get("price_buy", 0),
                            arb.get("exchange_sell", ""),
                            arb.get("price_sell", 0),
                            arb.get("spread_pct", 0),
                            arb.get("executed", 0),
                            arb.get("profit", 0),
                        ),
                    )
        except Exception as e:
            log.error(f"save_arb({arb.get('symbol', '?')}): {e}")
