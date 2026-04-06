# LAST_WORK

## Zuletzt erledigt (2026-04-06)

1. Kritischen Bot-Loop-Heartbeat-Stall behoben: Heartbeats werden jetzt auch während langer Scan-Phasen regelmäßig gesendet.
2. Long-/Short-Scan gegen Hänger abgesichert: Batch-Timeouts + Abbruch nicht-fertiger Futures eingebaut.
3. Updater-Version korrigiert: harter Fallback `1.5.2` entfernt, stattdessen dynamisch über `BOT_VERSION`.
4. Version und Doku auf `1.6.4` synchronisiert.

## Nächste sinnvolle Schritte

1. Weitere API- und Socket-Handler aus `server.py` schrittweise in `routes/` auslagern.
2. Trading- und Portfolio-Funktionen in dedizierte `services/`-Submodule aufteilen.
3. Bestehende Endpunkte mit gezielten Integrationstests absichern.
4. `server.py` weiter auf reinen Entry-Point + Wiring reduzieren.
