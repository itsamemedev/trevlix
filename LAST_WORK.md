# LAST_WORK

## Zuletzt erledigt (2026-04-06)

1. Exchange-Wechsel im Dashboard stabilisiert: Wechsel wird jetzt zusätzlich als Primär-Exchange gepinnt (falls vorhanden), damit kein unerwarteter Rückfall auf `cryptocom` passiert.
2. `create_exchange()` so erweitert, dass die gewünschte Exchange aus `CONFIG` priorisiert wird.
3. Automatische Exchange-Recovery beim Start ergänzt: bei Verbindungsfehlern wird auf andere aktivierte Exchanges gefailovert.
4. Version und Doku auf `1.6.3` synchronisiert (`CHANGELOG.md`, `VERSION.md`, README, technische Docs).

## Nächste sinnvolle Schritte

1. Weitere API- und Socket-Handler aus `server.py` schrittweise in `routes/` auslagern.
2. Trading- und Portfolio-Funktionen in dedizierte `services/`-Submodule aufteilen.
3. Bestehende Endpunkte mit gezielten Integrationstests absichern.
4. `server.py` weiter auf reinen Entry-Point + Wiring reduzieren.
