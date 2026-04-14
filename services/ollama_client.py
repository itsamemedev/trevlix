"""TREVLIX – Ollama-Client für lokale LLM-Inferenz.

Dünner Wrapper um die Ollama REST-API (http://127.0.0.1:11434), der
Health-Checks, Modell-Listing und einfache Chat-Anfragen bereitstellt.
Wird vom Installer und vom Auto-Healing-Agent genutzt, um die lokale
Ollama-Instanz zu überwachen – und kann als Fallback-Provider für
``services.knowledge`` fungieren, wenn kein externer LLM-Endpoint
konfiguriert ist.

Voraussetzung: httpx (optional). Ohne httpx laufen alle Methoden im
No-Op-Modus und geben ``False`` / leere Ergebnisse zurück – genau wie
die übrigen Service-Module im Projekt.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("trevlix.ollama")

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _HTTPX_AVAILABLE = False


DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
DEFAULT_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))


class OllamaClient:
    """Leichtgewichtiger Client für eine lokale Ollama-Instanz."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialisiert den Client.

        Args:
            host: Basis-URL der Ollama-API (ohne Pfad).
            model: Standard-Modell für Chat-Anfragen.
            timeout: Timeout in Sekunden pro Request.
        """
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ── Health / Introspection ───────────────────────────────────────────
    def is_available(self) -> bool:
        """Prüft, ob der Ollama-Dienst erreichbar ist."""
        if not _HTTPX_AVAILABLE:
            return False
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=min(self.timeout, 5))
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Ollama nicht erreichbar ({self.host}): {exc}")
            return False

    def list_models(self) -> list[str]:
        """Gibt die Namen aller lokal geladenen Modelle zurück."""
        if not _HTTPX_AVAILABLE:
            return []
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=min(self.timeout, 5))
            if resp.status_code != 200:
                return []
            data = resp.json() or {}
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:  # noqa: BLE001
            log.debug(f"list_models failed: {exc}")
            return []

    def has_model(self, model: str | None = None) -> bool:
        """Prüft, ob ein bestimmtes Modell lokal verfügbar ist."""
        target = model or self.model
        if not target:
            return False
        models = self.list_models()
        # Ollama-Namen können ":latest" enthalten – locker vergleichen
        target_base = target.split(":")[0]
        return any(m == target or m.split(":")[0] == target_base for m in models)

    # ── Chat / Generate ──────────────────────────────────────────────────
    def chat(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        """Schickt eine Chat-Anfrage an Ollama und gibt die Antwort zurück.

        Args:
            prompt: User-Prompt.
            system: Optionale System-Rolle.
            model: Überschreibt das Standardmodell.
            temperature: Sampling-Temperatur.
            max_tokens: Maximale Token-Anzahl der Antwort.

        Returns:
            Antwort-Text oder leerer String bei Fehler.
        """
        if not _HTTPX_AVAILABLE:
            return ""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": float(temperature),
                "num_predict": int(max_tokens),
            },
        }
        try:
            resp = httpx.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                log.warning(f"Ollama chat HTTP {resp.status_code}: {resp.text[:200]}")
                return ""
            data = resp.json() or {}
            return (data.get("message") or {}).get("content", "") or ""
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Ollama chat failed: {exc}")
            return ""

    # ── Model Management ─────────────────────────────────────────────────
    def pull_model(self, model: str | None = None) -> bool:
        """Lädt ein Modell via Ollama-API nach (blockierend).

        Für größere Modelle bitte die CLI ``ollama pull`` nutzen – diese
        Methode ist vor allem für kleine Standardmodelle gedacht.
        """
        if not _HTTPX_AVAILABLE:
            return False
        target = model or self.model
        if not target:
            return False
        try:
            with httpx.stream(
                "POST",
                f"{self.host}/api/pull",
                json={"name": target, "stream": True},
                timeout=None,
            ) as resp:
                if resp.status_code != 200:
                    return False
                # Stream bis zum Ende konsumieren
                for _ in resp.iter_lines():
                    pass
            return self.has_model(target)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Ollama pull '{target}' failed: {exc}")
            return False


# ── Convenience-Funktionen ───────────────────────────────────────────────
_default_client: OllamaClient | None = None


def get_default_client() -> OllamaClient:
    """Gibt einen prozessweiten Standard-Client zurück."""
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client


def is_ollama_available() -> bool:
    """Kurzform für Health-Checks."""
    return get_default_client().is_available()


def ollama_status() -> dict[str, Any]:
    """Gibt einen Status-Dict für Dashboard / MOTD zurück."""
    client = get_default_client()
    available = client.is_available()
    models = client.list_models() if available else []
    return {
        "available": available,
        "host": client.host,
        "default_model": client.model,
        "models": models,
        "has_default_model": client.has_model() if available else False,
    }
