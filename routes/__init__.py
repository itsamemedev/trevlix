"""
TREVLIX Routes Package
======================
Flask-Blueprint-Struktur für modulare API-Routen.

Dieses Package ist für die zukünftige Aufteilung von server.py vorbereitet.
Routen können hier als Blueprints registriert werden und in server.py
über app.register_blueprint() eingebunden werden.

Beispiel für zukünftige Erweiterung:
    from routes.trading import trading_bp
    from routes.admin import admin_bp
    app.register_blueprint(trading_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
"""

# Blueprints werden hier registriert, sobald routes/ aufgeteilt wird
__all__: list = []
