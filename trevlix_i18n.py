"""
TREVLIX v1.4.0 — i18n Translation Module
Sprachen: DE | EN | ES | RU | PT
"""

SUPPORTED_LANGS = ["de", "en", "es", "ru", "pt"]

TRANSLATIONS = {
    # ── BOT STATUS ──────────────────────────────────────────────────────
    "bot_started": {
        "de": "🚀 TREVLIX gestartet",
        "en": "🚀 TREVLIX started",
        "es": "🚀 TREVLIX iniciado",
        "ru": "🚀 TREVLIX запущен",
        "pt": "🚀 TREVLIX iniciado",
    },
    "bot_stopped": {
        "de": "⏹ Bot gestoppt",
        "en": "⏹ Bot stopped",
        "es": "⏹ Bot detenido",
        "ru": "⏹ Бот остановлен",
        "pt": "⏹ Bot parado",
    },
    "bot_paused": {
        "de": "⏸ Bot pausiert",
        "en": "⏸ Bot paused",
        "es": "⏸ Bot pausado",
        "ru": "⏸ Бот приостановлен",
        "pt": "⏸ Bot pausado",
    },
    "bot_resumed": {
        "de": "▶ Bot fortgesetzt",
        "en": "▶ Bot resumed",
        "es": "▶ Bot reanudado",
        "ru": "▶ Бот возобновлён",
        "pt": "▶ Bot retomado",
    },
    # ── TRADING ─────────────────────────────────────────────────────────
    "buy_signal": {
        "de": "🟢 Kaufsignal",
        "en": "🟢 Buy Signal",
        "es": "🟢 Señal de Compra",
        "ru": "🟢 Сигнал покупки",
        "pt": "🟢 Sinal de Compra",
    },
    "sell_signal": {
        "de": "🔴 Verkaufssignal",
        "en": "🔴 Sell Signal",
        "es": "🔴 Señal de Venta",
        "ru": "🔴 Сигнал продажи",
        "pt": "🔴 Sinal de Venda",
    },
    "position_opened": {
        "de": "📈 Position eröffnet",
        "en": "📈 Position opened",
        "es": "📈 Posición abierta",
        "ru": "📈 Позиция открыта",
        "pt": "📈 Posição aberta",
    },
    "position_closed": {
        "de": "📊 Position geschlossen",
        "en": "📊 Position closed",
        "es": "📊 Posición cerrada",
        "ru": "📊 Позиция закрыта",
        "pt": "📊 Posição fechada",
    },
    "short_opened": {
        "de": "📉 Short-Position eröffnet",
        "en": "📉 Short position opened",
        "es": "📉 Posición corta abierta",
        "ru": "📉 Открыта короткая позиция",
        "pt": "📉 Posição short aberta",
    },
    "short_closed": {
        "de": "📉 Short-Position geschlossen",
        "en": "📉 Short position closed",
        "es": "📉 Posición corta cerrada",
        "ru": "📉 Закрыта короткая позиция",
        "pt": "📉 Posição short fechada",
    },
    "sl_hit": {
        "de": "🛑 Stop-Loss getroffen",
        "en": "🛑 Stop-Loss hit",
        "es": "🛑 Stop-Loss alcanzado",
        "ru": "🛑 Стоп-лосс сработал",
        "pt": "🛑 Stop-Loss atingido",
    },
    "tp_hit": {
        "de": "🎯 Take-Profit getroffen",
        "en": "🎯 Take-Profit hit",
        "es": "🎯 Take-Profit alcanzado",
        "ru": "🎯 Тейк-профит сработал",
        "pt": "🎯 Take-Profit atingido",
    },
    "trailing_updated": {
        "de": "🔄 Trailing Stop aktualisiert",
        "en": "🔄 Trailing stop updated",
        "es": "🔄 Stop móvil actualizado",
        "ru": "🔄 Скользящий стоп обновлён",
        "pt": "🔄 Stop móvel atualizado",
    },
    "dca_triggered": {
        "de": "📉 DCA ausgelöst",
        "en": "📉 DCA triggered",
        "es": "📉 DCA activado",
        "ru": "📉 DCA активирован",
        "pt": "📉 DCA acionado",
    },
    "partial_tp": {
        "de": "🎯 Partial Take-Profit",
        "en": "🎯 Partial Take-Profit",
        "es": "🎯 Toma de ganancias parcial",
        "ru": "🎯 Частичный тейк-профит",
        "pt": "🎯 Take-Profit parcial",
    },
    "manual_close": {
        "de": "🖐 Manuell geschlossen",
        "en": "🖐 Manually closed",
        "es": "🖐 Cerrado manualmente",
        "ru": "🖐 Закрыто вручную",
        "pt": "🖐 Fechado manualmente",
    },
    # ── DISCORD MESSAGES ────────────────────────────────────────────────
    "discord_buy_title": {
        "de": "🟢 Kauf ausgeführt",
        "en": "🟢 Buy executed",
        "es": "🟢 Compra ejecutada",
        "ru": "🟢 Покупка исполнена",
        "pt": "🟢 Compra executada",
    },
    "discord_sell_title": {
        "de": "📊 Verkauf ausgeführt",
        "en": "📊 Sell executed",
        "es": "📊 Venta ejecutada",
        "ru": "📊 Продажа исполнена",
        "pt": "📊 Venda executada",
    },
    "discord_daily_title": {
        "de": "📊 TREVLIX Tagesbericht",
        "en": "📊 TREVLIX Daily Report",
        "es": "📊 Informe Diario TREVLIX",
        "ru": "📊 Ежедневный отчёт TREVLIX",
        "pt": "📊 Relatório Diário TREVLIX",
    },
    "discord_backup_done": {
        "de": "💾 Backup abgeschlossen",
        "en": "💾 Backup completed",
        "es": "💾 Copia de seguridad completada",
        "ru": "💾 Резервная копия создана",
        "pt": "💾 Backup concluído",
    },
    "discord_price_alert": {
        "de": "🔔 Preis-Alert ausgelöst!",
        "en": "🔔 Price alert triggered!",
        "es": "🔔 ¡Alerta de precio activada!",
        "ru": "🔔 Ценовой алерт сработал!",
        "pt": "🔔 Alerta de preço acionado!",
    },
    "discord_arb_found": {
        "de": "💹 Arbitrage-Chance gefunden",
        "en": "💹 Arbitrage opportunity found",
        "es": "💹 Oportunidad de arbitraje encontrada",
        "ru": "💹 Найдена арбитражная возможность",
        "pt": "💹 Oportunidade de arbitragem encontrada",
    },
    "discord_error": {
        "de": "❌ Bot-Fehler",
        "en": "❌ Bot Error",
        "es": "❌ Error del Bot",
        "ru": "❌ Ошибка бота",
        "pt": "❌ Erro do Bot",
    },
    "discord_circuit_breaker": {
        "de": "⚡ Circuit Breaker ausgelöst",
        "en": "⚡ Circuit breaker triggered",
        "es": "⚡ Interruptor de circuito activado",
        "ru": "⚡ Автоматический выключатель сработал",
        "pt": "⚡ Disjuntor acionado",
    },
    "discord_anomaly": {
        "de": "🚨 Anomalie erkannt — Trading pausiert",
        "en": "🚨 Anomaly detected — Trading paused",
        "es": "🚨 Anomalía detectada — Trading pausado",
        "ru": "🚨 Аномалия обнаружена — торговля приостановлена",
        "pt": "🚨 Anomalia detectada — Trading pausado",
    },
    # ── AI MESSAGES ──────────────────────────────────────────────────────
    "ai_training_start": {
        "de": "🧠 KI-Training gestartet...",
        "en": "🧠 AI training started...",
        "es": "🧠 Entrenamiento de IA iniciado...",
        "ru": "🧠 Обучение ИИ начато...",
        "pt": "🧠 Treinamento de IA iniciado...",
    },
    "ai_training_done": {
        "de": "✅ KI trainiert",
        "en": "✅ AI trained",
        "es": "✅ IA entrenada",
        "ru": "✅ ИИ обучен",
        "pt": "✅ IA treinada",
    },
    "ai_not_trained": {
        "de": "⏳ KI noch nicht trainiert — sammle Daten...",
        "en": "⏳ AI not yet trained — collecting data...",
        "es": "⏳ IA aún no entrenada — recopilando datos...",
        "ru": "⏳ ИИ ещё не обучен — сбор данных...",
        "pt": "⏳ IA ainda não treinada — coletando dados...",
    },
    "ai_blocked": {
        "de": "KI blockiert",
        "en": "AI blocked",
        "es": "IA bloqueada",
        "ru": "ИИ заблокировал",
        "pt": "IA bloqueada",
    },
    "ai_allowed": {
        "de": "KI erlaubt",
        "en": "AI allowed",
        "es": "IA permitida",
        "ru": "ИИ разрешил",
        "pt": "IA permitida",
    },
    # ── RISK / FILTERS ───────────────────────────────────────────────────
    "circuit_breaker_active": {
        "de": "⚡ Circuit Breaker aktiv",
        "en": "⚡ Circuit breaker active",
        "es": "⚡ Interruptor activo",
        "ru": "⚡ Автовыключатель активен",
        "pt": "⚡ Disjuntor ativo",
    },
    "daily_loss_exceeded": {
        "de": "📉 Tagesverlust-Limit erreicht",
        "en": "📉 Daily loss limit reached",
        "es": "📉 Límite de pérdida diaria alcanzado",
        "ru": "📉 Достигнут дневной лимит убытков",
        "pt": "📉 Limite de perda diária atingido",
    },
    "max_trades_reached": {
        "de": "⚠️ Maximale Positionsanzahl erreicht",
        "en": "⚠️ Maximum positions reached",
        "es": "⚠️ Máximo de posiciones alcanzado",
        "ru": "⚠️ Достигнуто максимальное число позиций",
        "pt": "⚠️ Máximo de posições atingido",
    },
    "spread_too_high": {
        "de": "⚠️ Spread zu hoch",
        "en": "⚠️ Spread too high",
        "es": "⚠️ Spread demasiado alto",
        "ru": "⚠️ Спред слишком высокий",
        "pt": "⚠️ Spread muito alto",
    },
    "news_blocked": {
        "de": "📰 Kauf durch negatives News-Sentiment blockiert",
        "en": "📰 Buy blocked by negative news sentiment",
        "es": "📰 Compra bloqueada por sentimiento negativo",
        "ru": "📰 Покупка заблокирована негативными новостями",
        "pt": "📰 Compra bloqueada por sentimento negativo",
    },
    "dominance_blocked": {
        "de": "🌐 Kauf durch Dominanz-Filter blockiert",
        "en": "🌐 Buy blocked by dominance filter",
        "es": "🌐 Compra bloqueada por filtro de dominancia",
        "ru": "🌐 Покупка заблокирована фильтром доминирования",
        "pt": "🌐 Compra bloqueada pelo filtro de dominância",
    },
    "paper_trading_note": {
        "de": "📝 Paper Trading — kein echtes Geld",
        "en": "📝 Paper Trading — no real money",
        "es": "📝 Operación simulada — sin dinero real",
        "ru": "📝 Бумажная торговля — без реальных денег",
        "pt": "📝 Paper Trading — sem dinheiro real",
    },
    # ── GENERAL ──────────────────────────────────────────────────────────
    "settings_saved": {
        "de": "✅ Einstellungen gespeichert",
        "en": "✅ Settings saved",
        "es": "✅ Configuración guardada",
        "ru": "✅ Настройки сохранены",
        "pt": "✅ Configurações salvas",
    },
    "keys_saved": {
        "de": "🔑 API-Keys gespeichert",
        "en": "🔑 API keys saved",
        "es": "🔑 Claves API guardadas",
        "ru": "🔑 API-ключи сохранены",
        "pt": "🔑 Chaves API salvas",
    },
    "backup_started": {
        "de": "💾 Backup wird erstellt...",
        "en": "💾 Creating backup...",
        "es": "💾 Creando copia de seguridad...",
        "ru": "💾 Создание резервной копии...",
        "pt": "💾 Criando backup...",
    },
    "report_sent": {
        "de": "📊 Tagesbericht gesendet",
        "en": "📊 Daily report sent",
        "es": "📊 Informe diario enviado",
        "ru": "📊 Ежедневный отчёт отправлен",
        "pt": "📊 Relatório diário enviado",
    },
    "error_generic": {
        "de": "❌ Fehler aufgetreten",
        "en": "❌ An error occurred",
        "es": "❌ Ocurrió un error",
        "ru": "❌ Произошла ошибка",
        "pt": "❌ Ocorreu um erro",
    },
    # ── DAILY REPORT FIELDS ──────────────────────────────────────────────
    "dr_balance": {
        "de": "💰 Kapital",
        "en": "💰 Balance",
        "es": "💰 Saldo",
        "ru": "💰 Баланс",
        "pt": "💰 Saldo",
    },
    "dr_daily_pnl": {
        "de": "📈 Tages-PnL",
        "en": "📈 Daily PnL",
        "es": "📈 PnL Diario",
        "ru": "📈 Дневной PnL",
        "pt": "📈 PnL Diário",
    },
    "dr_trades": {
        "de": "🔄 Trades heute",
        "en": "🔄 Trades today",
        "es": "🔄 Operaciones hoy",
        "ru": "🔄 Сделок сегодня",
        "pt": "🔄 Negociações hoje",
    },
    "dr_win_rate": {
        "de": "🎯 Win-Rate",
        "en": "🎯 Win Rate",
        "es": "🎯 Tasa de Éxito",
        "ru": "🎯 Процент побед",
        "pt": "🎯 Taxa de Acerto",
    },
    "dr_portfolio": {
        "de": "💼 Portfolio-Wert",
        "en": "💼 Portfolio Value",
        "es": "💼 Valor de Cartera",
        "ru": "💼 Стоимость портфеля",
        "pt": "💼 Valor do Portfólio",
    },
    "dr_best_coin": {
        "de": "🏆 Bestes Coin",
        "en": "🏆 Best Coin",
        "es": "🏆 Mejor Moneda",
        "ru": "🏆 Лучший актив",
        "pt": "🏆 Melhor Moeda",
    },
    "dr_worst_coin": {
        "de": "💀 Schlechtestes Coin",
        "en": "💀 Worst Coin",
        "es": "💀 Peor Moneda",
        "ru": "💀 Худший актив",
        "pt": "💀 Pior Moeda",
    },
    "dr_ai_accuracy": {
        "de": "🧠 KI-Genauigkeit",
        "en": "🧠 AI Accuracy",
        "es": "🧠 Precisión IA",
        "ru": "🧠 Точность ИИ",
        "pt": "🧠 Precisão IA",
    },
    # ── AUTH / LOGIN ────────────────────────────────────────────────
    "login_success": {
        "de": "✅ Erfolgreich angemeldet",
        "en": "✅ Successfully logged in",
        "es": "✅ Inicio de sesión exitoso",
        "ru": "✅ Успешный вход",
        "pt": "✅ Login realizado com sucesso",
    },
    "login_failed": {
        "de": "❌ Anmeldung fehlgeschlagen",
        "en": "❌ Login failed",
        "es": "❌ Error de inicio de sesión",
        "ru": "❌ Ошибка входа",
        "pt": "❌ Falha no login",
    },
    "login_blocked": {
        "de": "🚫 Zu viele Anmeldeversuche",
        "en": "🚫 Too many login attempts",
        "es": "🚫 Demasiados intentos de inicio de sesión",
        "ru": "🚫 Слишком много попыток входа",
        "pt": "🚫 Muitas tentativas de login",
    },
    "register_success": {
        "de": "✅ Konto erstellt",
        "en": "✅ Account created",
        "es": "✅ Cuenta creada",
        "ru": "✅ Аккаунт создан",
        "pt": "✅ Conta criada",
    },
    "register_disabled": {
        "de": "🚫 Registrierung deaktiviert",
        "en": "🚫 Registration disabled",
        "es": "🚫 Registro desactivado",
        "ru": "🚫 Регистрация отключена",
        "pt": "🚫 Registro desativado",
    },
    "session_expired": {
        "de": "⏰ Sitzung abgelaufen",
        "en": "⏰ Session expired",
        "es": "⏰ Sesión expirada",
        "ru": "⏰ Сессия истекла",
        "pt": "⏰ Sessão expirada",
    },
    # ── CONFIG / EXCHANGE ──────────────────────────────────────────
    "config_updated": {
        "de": "✅ Konfiguration aktualisiert",
        "en": "✅ Configuration updated",
        "es": "✅ Configuración actualizada",
        "ru": "✅ Конфигурация обновлена",
        "pt": "✅ Configuração atualizada",
    },
    "exchange_connected": {
        "de": "🌐 Exchange verbunden",
        "en": "🌐 Exchange connected",
        "es": "🌐 Exchange conectado",
        "ru": "🌐 Биржа подключена",
        "pt": "🌐 Exchange conectada",
    },
    "exchange_error": {
        "de": "❌ Exchange-Fehler",
        "en": "❌ Exchange error",
        "es": "❌ Error del exchange",
        "ru": "❌ Ошибка биржи",
        "pt": "❌ Erro da exchange",
    },
    "insufficient_balance": {
        "de": "⚠️ Unzureichendes Guthaben",
        "en": "⚠️ Insufficient balance",
        "es": "⚠️ Saldo insuficiente",
        "ru": "⚠️ Недостаточный баланс",
        "pt": "⚠️ Saldo insuficiente",
    },
    # ── ORDERS ─────────────────────────────────────────────────────
    "order_placed": {
        "de": "📋 Order platziert",
        "en": "📋 Order placed",
        "es": "📋 Orden colocada",
        "ru": "📋 Ордер размещён",
        "pt": "📋 Ordem colocada",
    },
    "order_failed": {
        "de": "❌ Order fehlgeschlagen",
        "en": "❌ Order failed",
        "es": "❌ Orden fallida",
        "ru": "❌ Ордер не выполнен",
        "pt": "❌ Ordem falhou",
    },
    # ── GRID TRADING ───────────────────────────────────────────────
    "grid_started": {
        "de": "📊 Grid Trading gestartet",
        "en": "📊 Grid trading started",
        "es": "📊 Trading en cuadrícula iniciado",
        "ru": "📊 Сеточная торговля запущена",
        "pt": "📊 Grid trading iniciado",
    },
    "grid_stopped": {
        "de": "⏹ Grid Trading gestoppt",
        "en": "⏹ Grid trading stopped",
        "es": "⏹ Trading en cuadrícula detenido",
        "ru": "⏹ Сеточная торговля остановлена",
        "pt": "⏹ Grid trading parado",
    },
    # ── COPY-TRADE ─────────────────────────────────────────────────
    "copy_trade_signal": {
        "de": "📡 Copy-Trade Signal empfangen",
        "en": "📡 Copy-trade signal received",
        "es": "📡 Señal de copy-trade recibida",
        "ru": "📡 Сигнал копитрейдинга получен",
        "pt": "📡 Sinal de copy-trade recebido",
    },
    # ── UPDATES ────────────────────────────────────────────────────
    "update_available": {
        "de": "🔄 Update verfügbar",
        "en": "🔄 Update available",
        "es": "🔄 Actualización disponible",
        "ru": "🔄 Доступно обновление",
        "pt": "🔄 Atualização disponível",
    },
    "update_installed": {
        "de": "✅ Update installiert",
        "en": "✅ Update installed",
        "es": "✅ Actualización instalada",
        "ru": "✅ Обновление установлено",
        "pt": "✅ Atualização instalada",
    },
    "maintenance_mode": {
        "de": "🔧 Wartungsmodus aktiv",
        "en": "🔧 Maintenance mode active",
        "es": "🔧 Modo de mantenimiento activo",
        "ru": "🔧 Режим обслуживания активен",
        "pt": "🔧 Modo de manutenção ativo",
    },
    # ── API / WEBHOOKS ─────────────────────────────────────────────
    "api_rate_limited": {
        "de": "⚠️ API Rate-Limit erreicht",
        "en": "⚠️ API rate limit reached",
        "es": "⚠️ Límite de tasa API alcanzado",
        "ru": "⚠️ Достигнут лимит запросов API",
        "pt": "⚠️ Limite de requisições da API atingido",
    },
    "webhook_received": {
        "de": "📥 Webhook empfangen",
        "en": "📥 Webhook received",
        "es": "📥 Webhook recibido",
        "ru": "📥 Вебхук получен",
        "pt": "📥 Webhook recebido",
    },
    # ── ADVANCED FEATURES ──────────────────────────────────────────
    "smart_exit_triggered": {
        "de": "🎯 Smart Exit ausgelöst",
        "en": "🎯 Smart exit triggered",
        "es": "🎯 Salida inteligente activada",
        "ru": "🎯 Умный выход сработал",
        "pt": "🎯 Smart exit acionado",
    },
    "dna_pattern_found": {
        "de": "🧬 DNA-Muster erkannt",
        "en": "🧬 DNA pattern found",
        "es": "🧬 Patrón DNA encontrado",
        "ru": "🧬 Обнаружен DNA-паттерн",
        "pt": "🧬 Padrão DNA encontrado",
    },
    "adaptive_weights_updated": {
        "de": "⚖️ Adaptive Gewichte aktualisiert",
        "en": "⚖️ Adaptive weights updated",
        "es": "⚖️ Pesos adaptativos actualizados",
        "ru": "⚖️ Адаптивные веса обновлены",
        "pt": "⚖️ Pesos adaptativos atualizados",
    },
    "attribution_report_ready": {
        "de": "📊 Performance-Report bereit",
        "en": "📊 Performance report ready",
        "es": "📊 Informe de rendimiento listo",
        "ru": "📊 Отчёт о производительности готов",
        "pt": "📊 Relatório de desempenho pronto",
    },
}


def t(key: str, lang: str = "de", **kwargs) -> str:
    """Translate a key to the given language, with optional format kwargs."""
    lang = lang if lang in SUPPORTED_LANGS else "de"
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get("de") or key
    try:
        return text.format(**kwargs) if kwargs else text
    except (KeyError, IndexError, ValueError):
        return text


def get_lang_name(lang: str) -> str:
    names = {"de": "Deutsch", "en": "English", "es": "Español", "ru": "Русский", "pt": "Português"}
    return names.get(lang, lang)
