"""AI training samples + backtest results repository.

Per-row CRUD for ``ai_training``, ``backtest_results``, and
``genetic_results`` tables.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from app.core.db_manager import MySQLManager


def _module():
    from app.core import db_manager as _m

    return _m


class AIRepository:
    """Per-row CRUD for ai_training + backtest_results + genetic_results."""

    def __init__(self, manager: MySQLManager) -> None:
        self._m = manager

    def save_ai_sample(self, features: np.ndarray, label: int, regime: str = "bull"):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO ai_training (features,label,regime) VALUES(%s,%s,%s)",
                        (json.dumps(features.tolist()), label, regime),
                    )
        except Exception as e:
            log.error(f"save_ai_sample: {e}")

    def load_ai_samples(self) -> tuple[list, list, list]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT features,label,regime FROM ai_training")
                    rows = c.fetchall()
            X: list = []
            y: list = []
            regimes: list = []
            for r in rows:
                try:
                    feats = json.loads(r.get("features", "[]"))
                    if not isinstance(feats, list):
                        continue
                    X.append(np.array(feats, dtype=np.float32))
                    y.append(r.get("label", 0))
                    regimes.append(r.get("regime", "range"))
                except (json.JSONDecodeError, ValueError, TypeError):
                    log.warning("load_ai_samples: skipping row with invalid features")
                    continue
            return X, y, regimes
        except Exception as e:
            log.error(f"load_ai_samples: {e}")
            return [], [], []

    def save_ai_samples_batch(self, samples: list[tuple[np.ndarray, int, str]]):
        """Batch-Insert für mehrere AI-Samples."""
        log = _module().log
        if not samples:
            return
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.executemany(
                        "INSERT INTO ai_training (features,label,regime) VALUES(%s,%s,%s)",
                        [
                            (json.dumps(feat.tolist()), label, regime)
                            for feat, label, regime in samples
                        ],
                    )
        except Exception as e:
            log.error(f"save_ai_samples_batch: {e}")

    def save_backtest(self, result: dict):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        """INSERT INTO backtest_results
                        (symbol,timeframe,candles,total_trades,win_rate,total_pnl,
                         profit_factor,max_drawdown,result_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            result.get("symbol"),
                            result.get("timeframe"),
                            result.get("candles"),
                            result.get("total_trades"),
                            result.get("win_rate"),
                            result.get("total_pnl"),
                            result.get("profit_factor"),
                            result.get("max_drawdown"),
                            json.dumps(result)[:65000],
                        ),
                    )
        except Exception as e:
            log.error(f"save_backtest: {e}")

    def get_recent_backtests(self, limit: int = 10) -> list[dict]:
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = c.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"get_recent_backtests: {e}")
            return []

    def save_genetic(self, generation: int, fitness: float, genome: dict):
        log = _module().log
        try:
            with self._m._get_conn() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "INSERT INTO genetic_results (generation,fitness,genome_json) "
                        "VALUES(%s,%s,%s)",
                        (generation, fitness, json.dumps(genome)),
                    )
        except Exception as e:
            log.error(f"save_genetic(gen={generation}, fitness={fitness:.4f}): {e}")
