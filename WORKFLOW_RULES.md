# WORKFLOW_RULES

Diese Regeln gelten dauerhaft für Änderungen im Repository.

1. **Versionspflege bei jeder relevanten Änderung**
   - Version prüfen/erhöhen (`VERSION.md`, `pyproject.toml`, `services/utils.py`, README/Dokumentation falls angezeigt).
2. **Dokumentation immer mitziehen**
   - `CHANGELOG.md` ergänzen.
   - `LAST_WORK.md` aktualisieren.
   - Bei Strukturänderungen zusätzlich `README.md` und `PROJECT_STRUCTURE.md` aktualisieren.
3. **`server.py` schlank halten**
   - Keine neue große Fachlogik direkt in `server.py`.
   - Neue Logik in passende Module (`routes/`, `services/`, `app/core/`, `utils/`) auslagern.
4. **Konsistenz bei Verschiebungen/Löschungen**
   - Imports, Verweise, Doku und ggf. Tests anpassen.
5. **Code-Sauberkeit**
   - Ungenutzte Imports und offensichtlichen Dead Code entfernen (sofern sicher).
   - Kleine, klar benannte Funktionen bevorzugen.
   - Duplikate vermeiden.
