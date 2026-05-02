"""Trade repository extracted from MySQLManager.

Holds the per-row CRUD for the ``trades``, ``trade_orders``,
``trade_decisions``, and ``trade_positions`` tables, plus the
performance-breakdown / load-trades / CSV-export read paths.

Late-binds to ``app.core.db_manager`` to read CONFIG and ``log`` so
init order during startup stays unaffected.
"""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    from app.core import db_manager as _m

    return _m


def _serialize_dates(row: dict, fields: tuple[str, ...]) -> dict:
    for f in fields:
        if f in row and hasattr(row[f], "isoformat"):
            row[f] = row[f].isoformat()
    return row


class TradeRepository:
    """Trades, orders, decisions, positions + reporting helpers."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    # ── Writes ──────────────────────────────────────────────────────────────
    def save_trade(self, trade: dict, user_id: int = 1):
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trades
                        (user_id,symbol,entry,exit_price,qty,pnl,pnl_pct,reason,
                         confidence,ai_score,win_prob,invested,opened,closed,exchange,
                         regime,trade_type,partial_sold,dca_level,news_score,onchain_score,
                         trade_mode,fees,order_ref)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                               %s,%s,%s,%s)""",
                        (
                            user_id,
                            trade.get("symbol"),
                            trade.get("entry"),
                            trade.get("exit"),
                            trade.get("qty"),
                            trade.get("pnl"),
                            trade.get("pnl_pct"),
                            trade.get("reason"),
                            trade.get("confidence"),
                            trade.get("ai_score"),
                            trade.get("win_prob"),
                            trade.get("invested"),
                            trade.get("opened"),
                            trade.get("closed"),
                            trade.get("exchange", m.CONFIG.get("exchange", "cryptocom")),
                            trade.get("regime", "bull"),
                            trade.get("trade_type", "long"),
                            trade.get("partial_sold", 0),
                            trade.get("dca_level", 0),
                            trade.get("news_score", 0),
                            trade.get("onchain_score", 0),
                            trade.get("trade_mode", "paper"),
                            trade.get("fees", 0),
                            trade.get("order_ref", ""),
                        ),
                    )
        except Exception as e:
            log.error(f"save_trade: {e}")

    def save_order(self, order: dict, user_id: int = 1) -> None:
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_orders
                        (user_id,symbol,side,order_type,status,price,qty,cost,fees,
                         trade_mode,exchange,exchange_order_id,reason,meta_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            user_id,
                            order.get("symbol"),
                            order.get("side", "buy"),
                            order.get("order_type", "market"),
                            order.get("status", "filled"),
                            order.get("price", 0),
                            order.get("qty", 0),
                            order.get("cost", 0),
                            order.get("fees", 0),
                            order.get("trade_mode", "paper"),
                            order.get("exchange", m.CONFIG.get("exchange", "cryptocom")),
                            str(order.get("exchange_order_id", "")),
                            order.get("reason", ""),
                            json.dumps(order.get("meta", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"save_order: {e}")

    def save_trade_decision(self, decision: dict, user_id: int = 1) -> None:
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_decisions
                        (user_id,symbol,decision,reason,confidence,ai_score,win_prob,
                         trade_mode,exchange,payload_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            user_id,
                            decision.get("symbol", ""),
                            decision.get("decision", "hold"),
                            decision.get("reason", ""),
                            decision.get("confidence", 0),
                            decision.get("ai_score", 0),
                            decision.get("win_prob", 0),
                            decision.get("trade_mode", "paper"),
                            decision.get("exchange", m.CONFIG.get("exchange", "cryptocom")),
                            json.dumps(decision.get("payload", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"save_trade_decision: {e}")

    def upsert_trade_position(self, position: dict, user_id: int = 1) -> None:
        m = _module()
        log = m.log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO trade_positions
                        (user_id,symbol,side,qty,entry_price,invested,stop_loss,
                         take_profit,trade_mode,exchange,status,opened_at,meta_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'open',%s,%s)
                        ON DUPLICATE KEY UPDATE
                        qty=VALUES(qty), entry_price=VALUES(entry_price),
                        invested=VALUES(invested),
                        stop_loss=VALUES(stop_loss), take_profit=VALUES(take_profit),
                        exchange=VALUES(exchange), meta_json=VALUES(meta_json)""",
                        (
                            user_id,
                            position.get("symbol"),
                            position.get("side", "long"),
                            position.get("qty", 0),
                            position.get("entry_price", 0),
                            position.get("invested", 0),
                            position.get("stop_loss", 0),
                            position.get("take_profit", 0),
                            position.get("trade_mode", "paper"),
                            position.get("exchange", m.CONFIG.get("exchange", "cryptocom")),
                            position.get("opened_at"),
                            json.dumps(position.get("meta", {})),
                        ),
                    )
        except Exception as e:
            log.error(f"upsert_trade_position: {e}")

    def close_trade_position(
        self, symbol: str, trade_mode: str = "paper", user_id: int = 1
    ) -> None:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """UPDATE trade_positions
                        SET status='closed', closed_at=NOW()
                        WHERE user_id=%s AND symbol=%s AND trade_mode=%s AND status='open'""",
                        (user_id, symbol, trade_mode),
                    )
        except Exception as e:
            log.error(f"close_trade_position: {e}")

    # ── Reads ───────────────────────────────────────────────────────────────
    def load_open_positions(
        self, user_id: int | None = None, trade_mode: str | None = None
    ) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_positions WHERE status='open'"
                    p: list = []
                    if user_id:
                        q += " AND user_id=%s"
                        p.append(user_id)
                    if trade_mode:
                        q += " AND trade_mode=%s"
                        p.append(trade_mode)
                    q += " ORDER BY opened_at DESC"
                    c.execute(q, p)
                    rows = c.fetchall()
            return [
                _serialize_dates(dict(r), ("opened_at", "closed_at", "updated_at"))
                for r in rows
            ]
        except Exception as e:
            log.error(f"load_open_positions: {e}")
            return []

    def load_orders(
        self,
        limit: int = 200,
        user_id: int | None = None,
        trade_mode: str | None = None,
    ) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_orders"
                    w: list = []
                    p: list = []
                    if user_id:
                        w.append("user_id=%s")
                        p.append(user_id)
                    if trade_mode:
                        w.append("trade_mode=%s")
                        p.append(trade_mode)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY created_at DESC LIMIT %s"
                    p.append(limit)
                    c.execute(q, p)
                    rows = c.fetchall()
            return [_serialize_dates(dict(r), ("created_at",)) for r in rows]
        except Exception as e:
            log.error(f"load_orders: {e}")
            return []

    def load_trade_decisions(
        self,
        limit: int = 200,
        user_id: int | None = None,
        trade_mode: str | None = None,
    ) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT * FROM trade_decisions"
                    w: list = []
                    p: list = []
                    if user_id:
                        w.append("user_id=%s")
                        p.append(user_id)
                    if trade_mode:
                        w.append("trade_mode=%s")
                        p.append(trade_mode)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY created_at DESC LIMIT %s"
                    p.append(limit)
                    c.execute(q, p)
                    rows = c.fetchall()
            return [_serialize_dates(dict(r), ("created_at",)) for r in rows]
        except Exception as e:
            log.error(f"load_trade_decisions: {e}")
            return []

    def performance_breakdown(self, user_id: int | None = None) -> dict:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    p: list = []
                    wu = ""
                    if user_id:
                        wu = "WHERE user_id=%s"
                        p.append(user_id)
                    c.execute(
                        f"""SELECT trade_mode, COUNT(*) AS n, SUM(pnl) AS pnl,
                                   SUM(fees) AS fees
                            FROM trades {wu}
                            GROUP BY trade_mode""",
                        p,
                    )
                    by_mode = c.fetchall()
                    c.execute(
                        f"""SELECT exchange, COUNT(*) AS n, SUM(pnl) AS pnl
                            FROM trades {wu}
                            GROUP BY exchange ORDER BY pnl DESC""",
                        p,
                    )
                    by_exchange = c.fetchall()
                    c.execute(
                        f"""SELECT reason, COUNT(*) AS n, SUM(pnl) AS pnl
                            FROM trades {wu}
                            GROUP BY reason ORDER BY pnl DESC LIMIT 50""",
                        p,
                    )
                    by_strategy = c.fetchall()
                    c.execute(
                        f"""SELECT
                                COALESCE(SUM(CASE WHEN trade_mode='paper' THEN pnl END),0)
                                    AS paper_pnl,
                                COALESCE(SUM(CASE WHEN trade_mode='live' THEN pnl END),0)
                                    AS live_pnl,
                                COALESCE(SUM(CASE WHEN trade_mode='paper' THEN fees END),0)
                                    AS paper_fees,
                                COALESCE(SUM(CASE WHEN trade_mode='live' THEN fees END),0)
                                    AS live_fees,
                                COALESCE(COUNT(CASE WHEN trade_mode='paper' THEN 1 END),0)
                                    AS paper_trades,
                                COALESCE(COUNT(CASE WHEN trade_mode='live' THEN 1 END),0)
                                    AS live_trades
                            FROM trades {wu}""",
                        p,
                    )
                    compare = dict(c.fetchone() or {})
            return {
                "by_mode": [dict(r) for r in by_mode],
                "by_exchange": [dict(r) for r in by_exchange],
                "by_strategy": [dict(r) for r in by_strategy],
                "paper_vs_live": compare,
            }
        except Exception as e:
            log.error(f"performance_breakdown: {e}")
            return {"by_mode": [], "by_exchange": [], "by_strategy": [], "paper_vs_live": {}}

    def load_trades(
        self,
        limit: int = 500,
        symbol: str | None = None,
        year: int | None = None,
        user_id: int | None = None,
    ) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    q = "SELECT *, exit_price as `exit` FROM trades"
                    params: list = []
                    w: list = []
                    if user_id:
                        w.append("user_id=%s")
                        params.append(user_id)
                    if symbol:
                        w.append("symbol=%s")
                        params.append(symbol)
                    if year:
                        w.append("YEAR(closed)=%s")
                        params.append(year)
                    if w:
                        q += " WHERE " + " AND ".join(w)
                    q += " ORDER BY closed DESC LIMIT %s"
                    params.append(limit)
                    c.execute(q, params)
                    rows = c.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for k in ("opened", "closed"):
                    if k in d and hasattr(d[k], "isoformat"):
                        d[k] = d[k].isoformat()
                result.append(d)
            return result
        except Exception as e:
            log.error(f"load_trades: {e}")
            return []

    # ── Export ──────────────────────────────────────────────────────────────
    def export_csv(self, user_id: int | None = None, limit: int = 10000) -> str:
        trades = self.load_trades(limit=limit, user_id=user_id)
        buf = io.StringIO()
        fields = [
            "id",
            "symbol",
            "entry",
            "exit",
            "qty",
            "pnl",
            "pnl_pct",
            "reason",
            "confidence",
            "ai_score",
            "win_prob",
            "invested",
            "opened",
            "closed",
            "exchange",
            "regime",
            "trade_type",
            "dca_level",
            "news_score",
            "onchain_score",
        ]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        if trades:
            w.writerows(trades)
        return buf.getvalue()
