"""TREVLIX – Multi-LLM-Provider mit Failover.

Integriert mehrere kostenlose LLM-APIs für KI-gestützte Trading-Analysen.
Automatisches Failover: Wenn ein Provider ausfällt, wird der nächste versucht.

Unterstützte Provider:
    - Groq (Llama 3.3 70B) – Schnellste Inferenz
    - OpenRouter (Llama 3.3 70B Free) – Viele kostenlose Modelle
    - Cerebras (Llama 3.3 70B) – Schnelle Inferenz
    - HuggingFace (DeepSeek V3) – Kostenlose Tier

Verwendung:
    from services.llm_providers import MultiLLMProvider
    provider = MultiLLMProvider()
    answer = provider.chat("Analysiere BTC/USDT", system="Du bist ein Analyst")
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("trevlix.llm_providers")

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_PROVIDER_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "groq",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "env_key": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "supports_tools": True,
        "max_tokens": 800,
    },
    {
        "name": "cerebras",
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "env_key": "CEREBRAS_API_KEY",
        "model": "llama-3.3-70b",
        "supports_tools": False,
        "max_tokens": 800,
    },
    {
        "name": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "supports_tools": True,
        "max_tokens": 800,
    },
    {
        "name": "huggingface",
        "endpoint": "https://router.huggingface.co/v1/chat/completions",
        "env_key": "HF_API_KEY",
        "model": "deepseek-ai/DeepSeek-V3-0324:novita",
        "supports_tools": False,
        "max_tokens": 800,
    },
]

_REQUEST_TIMEOUT = 30  # Sekunden
_CACHE_TTL = 300  # 5 Minuten
_CACHE_MAX_SIZE = 200
_DEFAULT_TEMPERATURE = 0.3
_RATE_LIMIT_COOLDOWN_SECONDS = 120
_CLIENT_ERROR_COOLDOWN_SECONDS = 600


class MultiLLMProvider:
    """Multi-LLM-Provider mit automatischem Failover.

    Versucht nacheinander konfigurierte LLM-APIs bis eine antwortet.
    Cacht Antworten um API-Aufrufe zu minimieren.

    Attributes:
        available_providers: Liste der konfigurierten Provider-Namen.
    """

    def __init__(self) -> None:
        """Initialisiert den Provider und erkennt verfuegbare API-Keys."""
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._cache_ts: dict[str, float] = {}
        self._providers: list[dict[str, Any]] = []
        self._health: dict[str, dict[str, Any]] = {}

        if not _HTTPX_AVAILABLE:
            log.warning("httpx nicht installiert – Multi-LLM deaktiviert")
            return

        for cfg in _PROVIDER_CONFIGS:
            api_key = os.environ.get(cfg["env_key"], "").strip()
            if api_key:
                self._providers.append({**cfg, "api_key": api_key})
                self._health[cfg["name"]] = {
                    "available": True,
                    "last_success": 0.0,
                    "last_error": "",
                    "cooldown_until": 0.0,
                    "requests": 0,
                    "errors": 0,
                }
                log.debug("LLM-Provider '%s' konfiguriert", cfg["name"])

        if not self._providers:
            log.info(
                "Keine Multi-LLM API-Keys konfiguriert. "
                "Setze GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY "
                "oder HF_API_KEY in .env"
            )

    @property
    def available_providers(self) -> list[str]:
        """Liste der konfigurierten Provider-Namen."""
        return [p["name"] for p in self._providers]

    def chat(
        self,
        prompt: str,
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int = 800,
    ) -> str | None:
        """Sendet eine Chat-Anfrage mit automatischem Failover.

        Args:
            prompt: Die Benutzer-Nachricht.
            system: Optionale System-Nachricht fuer Kontext.
            tools: Optionale Tool-Definitionen (nur fuer Provider mit Tool-Support).
            temperature: Kreativitaet der Antwort (0.0-1.0).
            max_tokens: Maximale Antwortlaenge in Tokens.

        Returns:
            LLM-Antwort als String oder None wenn alle Provider fehlschlagen.
        """
        if not self._providers:
            return None

        # Cache pruefen
        cache_key = self._make_cache_key(prompt, system)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Provider der Reihe nach versuchen
        for provider in self._providers:
            if self._is_in_cooldown(provider["name"]):
                continue
            try:
                result = self._call_provider(
                    provider, prompt, system, tools, temperature, max_tokens
                )
                if result:
                    self._set_cached(cache_key, result)
                    log.info("LLM-Antwort via %s (%d Zeichen)", provider["name"], len(result))
                    return result
            except Exception as exc:
                self._record_error(provider["name"], str(exc))
                log.debug("LLM-Provider '%s' fehlgeschlagen: %s", provider["name"], exc)
                continue

        log.warning("Alle LLM-Provider fehlgeschlagen")
        return None

    def chat_all(
        self,
        prompt: str,
        system: str = "",
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int = 500,
    ) -> list[dict[str, Any]]:
        """Fragt alle konfigurierten Provider ab (ohne Failover-Abbruch).

        Returns:
            Liste mit Antwort/Fehler je Provider.
        """
        result: list[dict[str, Any]] = []
        for provider in self._providers:
            try:
                answer = self._call_provider(
                    provider=provider,
                    prompt=prompt,
                    system=system,
                    tools=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if answer:
                    result.append(
                        {
                            "provider": provider["name"],
                            "model": provider.get("model", ""),
                            "ok": True,
                            "answer": answer,
                        }
                    )
                else:
                    result.append(
                        {
                            "provider": provider["name"],
                            "model": provider.get("model", ""),
                            "ok": False,
                            "error": "empty_response",
                        }
                    )
            except Exception as exc:
                self._record_error(provider["name"], str(exc))
                result.append(
                    {
                        "provider": provider["name"],
                        "model": provider.get("model", ""),
                        "ok": False,
                        "error": str(exc),
                    }
                )
        return result

    def status(self) -> list[dict[str, Any]]:
        """Gibt den Gesundheitsstatus aller Provider zurueck.

        Returns:
            Liste mit Status-Dicts pro Provider.
        """
        result = []
        with self._lock:
            for provider in self._providers:
                name = provider["name"]
                health = self._health.get(name, {})
                result.append(
                    {
                        "name": name,
                        "model": provider["model"],
                        "available": health.get("available", False),
                        "supports_tools": provider["supports_tools"],
                        "requests": health.get("requests", 0),
                        "errors": health.get("errors", 0),
                        "cooldown_until": health.get("cooldown_until", 0.0),
                        "last_error": health.get("last_error", ""),
                    }
                )
        return result

    def _call_provider(
        self,
        provider: dict[str, Any],
        prompt: str,
        system: str,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        """Ruft einen einzelnen LLM-Provider auf.

        Args:
            provider: Provider-Konfiguration.
            prompt: Benutzer-Nachricht.
            system: System-Nachricht.
            tools: Tool-Definitionen.
            temperature: Temperatur-Parameter.
            max_tokens: Max Tokens.

        Returns:
            Antwort-String oder None.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(max_tokens, provider["max_tokens"]),
            "stream": False,
        }

        # Tools nur bei unterstuetzten Providern hinzufuegen
        if tools and provider["supports_tools"]:
            payload["tools"] = tools

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
        }

        # OpenRouter erwartet zusaetzliche Header
        if provider["name"] == "openrouter":
            headers["HTTP-Referer"] = "https://trevlix.dev"
            headers["X-Title"] = "Trevlix Trading Bot"

        with self._lock:
            self._health[provider["name"]]["requests"] += 1

        resp = httpx.post(
            provider["endpoint"],
            json=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            self._record_error(provider["name"], error_msg)
            self._apply_cooldown(provider["name"], resp.status_code)
            return None

        data = resp.json()
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            self._record_error(provider["name"], "Keine choices in Antwort")
            return None

        answer = choices[0].get("message", {}).get("content", "")
        if answer:
            with self._lock:
                self._health[provider["name"]]["last_success"] = time.time()
                self._health[provider["name"]]["available"] = True
                self._health[provider["name"]]["cooldown_until"] = 0.0
            return answer

        return None

    def _record_error(self, name: str, error: str) -> None:
        """Zeichnet einen Provider-Fehler auf."""
        with self._lock:
            if name in self._health:
                self._health[name]["errors"] += 1
                self._health[name]["last_error"] = error
                self._health[name]["available"] = False

    def _apply_cooldown(self, name: str, status_code: int) -> None:
        """Setzt einen Cooldown fuer Provider bei erwartbaren API-Fehlern."""
        cooldown = 0
        if status_code == 429:
            cooldown = _RATE_LIMIT_COOLDOWN_SECONDS
        elif status_code in {400, 401, 403, 404, 422}:
            cooldown = _CLIENT_ERROR_COOLDOWN_SECONDS

        if not cooldown:
            return

        until = time.time() + cooldown
        with self._lock:
            if name in self._health:
                self._health[name]["cooldown_until"] = until

    def _is_in_cooldown(self, name: str) -> bool:
        """Prueft, ob ein Provider temporaer uebersprungen werden soll."""
        with self._lock:
            health = self._health.get(name)
            if not health:
                return False
            cooldown_until = health.get("cooldown_until", 0.0)
            if cooldown_until > time.time():
                return True
            if cooldown_until:
                health["cooldown_until"] = 0.0
                health["available"] = True
        return False

    @staticmethod
    def _make_cache_key(prompt: str, system: str) -> str:
        """Erzeugt einen Cache-Key aus Prompt und System-Nachricht."""
        raw = f"{system}||{prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_cached(self, key: str) -> str | None:
        """Gibt gecachte Antwort zurueck oder None."""
        with self._lock:
            if key in self._cache:
                ts = self._cache_ts.get(key, 0.0)
                if time.time() - ts < _CACHE_TTL:
                    return self._cache[key]
                # Abgelaufen
                self._cache.pop(key, None)
                self._cache_ts.pop(key, None)
        return None

    def _set_cached(self, key: str, value: str) -> None:
        """Speichert eine Antwort im Cache."""
        with self._lock:
            self._cache[key] = value
            self._cache_ts[key] = time.time()
            # Eviction wenn zu gross
            if len(self._cache) > _CACHE_MAX_SIZE:
                sorted_keys = sorted(self._cache_ts.keys(), key=lambda k: self._cache_ts[k])
                for k in sorted_keys[: len(self._cache) - _CACHE_MAX_SIZE]:
                    self._cache.pop(k, None)
                    self._cache_ts.pop(k, None)
