"""[#10] Pydantic-basierte Konfigurationsklasse für TREVLIX.

Ersetzt das globale CONFIG-Dict durch eine typsichere, validierte
Konfigurationsklasse mit Umgebungsvariablen-Support.

Verwendung:
    from services.config import TrevlixConfig, load_config
    cfg = load_config()
    print(cfg.exchange)
    print(cfg.fee_rate)
"""

from __future__ import annotations

import os
import secrets
from typing import Any

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    try:
        from pydantic import BaseModel, Field, validator
        from pydantic import BaseSettings
        PYDANTIC_AVAILABLE = True
    except ImportError:
        PYDANTIC_AVAILABLE = False


if PYDANTIC_AVAILABLE:

    class TrevlixConfig(BaseSettings):
        """Typsichere Konfiguration für TREVLIX Trading Bot.

        Alle Werte können über Umgebungsvariablen überschrieben werden.
        Beispiel: EXCHANGE=binance überschreibt exchange='cryptocom'.

        Args:
            exchange: Name der primären Exchange (cryptocom, binance, bybit, ...).
            api_key: API-Key der Exchange (wird verschlüsselt gespeichert).
            secret: API-Secret der Exchange.
            fee_rate: Standard-Fee-Rate (Dezimal, z.B. 0.001 = 0.1%).
            risk_per_trade: Risiko pro Trade als Anteil des Kapitals.
            stop_loss_pct: Stop-Loss als Prozent unter Einstieg.
            take_profit_pct: Take-Profit als Prozent über Einstieg.
            max_open_trades: Maximale gleichzeitige Positionen.
            paper_trading: True = Paper-Trading ohne echte Orders.
            paper_balance: Startkapital für Paper-Trading.
            max_corr: Maximale Korrelation zwischen offenen Positionen.
            mysql_host: MySQL-Server-Host.
            mysql_port: MySQL-Server-Port.
            mysql_user: MySQL-Benutzername.
            mysql_pass: MySQL-Passwort.
            mysql_db: MySQL-Datenbankname.
            jwt_secret: Geheimnis für JWT-Token-Signierung.
            admin_password: Passwort für den Admin-Account.
        """

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        ) if hasattr(BaseSettings, 'model_config') else {}

        # Exchange
        exchange: str = Field(default="cryptocom", description="Name der primären Exchange")
        api_key: str = Field(default="", description="Exchange API-Key")
        secret: str = Field(default="", description="Exchange API-Secret")
        quote_currency: str = Field(default="USDT")
        min_volume_usdt: float = Field(default=1_000_000.0, gt=0)

        # Trading-Parameter
        timeframe: str = Field(default="1h")
        candle_limit: int = Field(default=250, ge=50, le=1000)
        risk_per_trade: float = Field(default=0.015, ge=0.001, le=0.1)
        stop_loss_pct: float = Field(default=0.025, ge=0.005, le=0.5)
        take_profit_pct: float = Field(default=0.060, ge=0.01, le=1.0)
        max_open_trades: int = Field(default=5, ge=1, le=50)
        max_position_pct: float = Field(default=0.20, ge=0.01, le=1.0)
        fee_rate: float = Field(default=0.0004, ge=0.0, le=0.05)
        paper_trading: bool = Field(default=True)
        paper_balance: float = Field(default=10000.0, gt=0)
        scan_interval: int = Field(default=60, ge=5)

        # Risiko
        max_spread_pct: float = Field(default=0.5, ge=0.0)
        max_corr: float = Field(default=0.75, ge=0.0, le=1.0)
        circuit_breaker_losses: int = Field(default=3, ge=1)
        circuit_breaker_min: int = Field(default=120, ge=0)
        max_drawdown_pct: float = Field(default=0.10, ge=0.01, le=1.0)
        max_daily_loss_pct: float = Field(default=0.05, ge=0.001, le=1.0)
        slippage_pct: float = Field(default=0.001, ge=0.0, le=0.1)
        min_order_usdt: float = Field(default=10.0, ge=1.0)

        # KI
        ai_enabled: bool = Field(default=True)
        ai_min_samples: int = Field(default=20, ge=5)
        ai_min_confidence: float = Field(default=0.55, ge=0.5, le=1.0)
        ai_use_kelly: bool = Field(default=True)

        # MySQL
        mysql_host: str = Field(default="localhost")
        mysql_port: int = Field(default=3306, ge=1, le=65535)
        mysql_user: str = Field(default="root")
        mysql_pass: str = Field(default="")
        mysql_db: str = Field(default="nexus")

        # Auth
        admin_password: str = Field(default="nexus")
        jwt_secret: str = Field(default_factory=lambda: secrets.token_hex(32))
        jwt_expiry_hours: int = Field(default=24, ge=1)

        # CryptoPanic
        cryptopanic_token: str = Field(default="")

        # Telegram
        telegram_token: str = Field(default="")
        telegram_chat_id: str = Field(default="")

        # Discord
        discord_webhook: str = Field(default="")

        @field_validator("timeframe")
        @classmethod
        def validate_timeframe(cls, v: str) -> str:
            """Prüft ob der Timeframe ein gültiger CCXT-Wert ist."""
            valid = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
            if v not in valid:
                raise ValueError(f"Ungültiger Timeframe '{v}'. Erlaubt: {valid}")
            return v

        @field_validator("exchange")
        @classmethod
        def validate_exchange(cls, v: str) -> str:
            """Prüft ob der Exchange-Name unterstützt wird."""
            supported = {"cryptocom", "binance", "bybit", "okx", "kucoin", "kraken", "huobi", "coinbase"}
            if v not in supported:
                raise ValueError(f"Nicht unterstützte Exchange '{v}'. Erlaubt: {supported}")
            return v

        def to_dict(self) -> dict[str, Any]:
            """Konvertiert die Config in ein Dict (kompatibel mit CONFIG).

            Returns:
                Dict mit allen Konfigurationswerten.
            """
            return self.model_dump() if hasattr(self, "model_dump") else self.dict()

        @classmethod
        def from_env(cls) -> "TrevlixConfig":
            """Erstellt eine Config-Instanz aus Umgebungsvariablen.

            Returns:
                Validierte TrevlixConfig-Instanz.
            """
            return cls(
                exchange=os.getenv("EXCHANGE", "cryptocom"),
                api_key=os.getenv("API_KEY", ""),
                secret=os.getenv("API_SECRET", ""),
                mysql_host=os.getenv("MYSQL_HOST", "localhost"),
                mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
                mysql_user=os.getenv("MYSQL_USER", "root"),
                mysql_pass=os.getenv("MYSQL_PASS", ""),
                mysql_db=os.getenv("MYSQL_DB", "nexus"),
                admin_password=os.getenv("ADMIN_PASSWORD", "nexus"),
                jwt_secret=os.getenv("JWT_SECRET", secrets.token_hex(32)),
                cryptopanic_token=os.getenv("CRYPTOPANIC_TOKEN", ""),
                telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
                telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
                discord_webhook=os.getenv("DISCORD_WEBHOOK", ""),
            )

        def validate_security(self) -> list[str]:
            """Prüft sicherheitsrelevante Konfigurationswerte.

            Returns:
                Liste mit Warnmeldungen. Leer = alles OK.
            """
            warnings = []
            if len(self.admin_password) < 12:
                warnings.append("ADMIN_PASSWORD sollte mind. 12 Zeichen haben")
            if len(self.jwt_secret) < 32:
                warnings.append("JWT_SECRET sollte mind. 32 Zeichen haben")
            if not self.mysql_pass:
                warnings.append("MYSQL_PASS ist leer - unsicher für Produktion!")
            if self.paper_trading is False and not self.api_key:
                warnings.append("Live-Trading ohne API-Key konfiguriert!")
            return warnings

else:
    # Fallback wenn Pydantic nicht verfügbar
    class TrevlixConfig:  # type: ignore[no-redef]
        """Fallback-Config ohne Pydantic-Validierung."""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def from_env(cls) -> "TrevlixConfig":
            """Erstellt eine Config-Instanz aus Umgebungsvariablen."""
            return cls(
                exchange=os.getenv("EXCHANGE", "cryptocom"),
                mysql_host=os.getenv("MYSQL_HOST", "localhost"),
            )

        def to_dict(self) -> dict[str, Any]:
            """Konvertiert die Config in ein Dict."""
            return vars(self)

        def validate_security(self) -> list[str]:
            """Sicherheitsvalidierung (Fallback ohne Pydantic)."""
            return []


def load_config() -> TrevlixConfig:
    """Lädt und validiert die Konfiguration aus Umgebungsvariablen.

    Returns:
        Validierte TrevlixConfig-Instanz.

    Raises:
        SystemExit: Wenn kritische Konfigurationswerte fehlen.
    """
    try:
        cfg = TrevlixConfig.from_env()
        warnings = cfg.validate_security()
        if warnings:
            import logging
            log = logging.getLogger(__name__)
            for w in warnings:
                log.warning(f"[Config] {w}")
        return cfg
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Konfigurationsfehler: {e}")
        raise
