/* ═══════════════════════════════════════════════════════════
   TREVLIX v1.0.0 – Translations
   Languages: de | en | es | ru | pt
   ═══════════════════════════════════════════════════════════ */
const QLANG_NAMES = {de:'Deutsch',en:'English',es:'Español',ru:'Русский',pt:'Português'};
const QLANG_FLAGS = {de:'🇩🇪',en:'🇺🇸',es:'🇪🇸',ru:'🇷🇺',pt:'🇧🇷'};

const QT = {
  /* ── GLOBAL STATUS ── */
  status_running:   {de:'Aktiv',en:'Running',es:'Activo',ru:'Работает',pt:'Ativo'},
  status_stopped:   {de:'Gestoppt',en:'Stopped',es:'Detenido',ru:'Остановлен',pt:'Parado'},
  status_paused:    {de:'Pausiert',en:'Paused',es:'Pausado',ru:'Пауза',pt:'Pausado'},
  paper_mode:       {de:'Paper',en:'Paper',es:'Simulación',ru:'Бумажный',pt:'Simulação'},
  live_mode:        {de:'Live',en:'Live',es:'En Vivo',ru:'Живой',pt:'Ao Vivo'},

  /* ── BOTTOM NAV ── */
  nav_home:     {de:'Home',en:'Home',es:'Inicio',ru:'Главная',pt:'Início'},
  nav_trades:   {de:'Trades',en:'Trades',es:'Trades',ru:'Сделки',pt:'Trades'},
  nav_stats:    {de:'Stats',en:'Stats',es:'Stats',ru:'Статистика',pt:'Stats'},
  nav_ai:       {de:'KI',en:'AI',es:'IA',ru:'ИИ',pt:'IA'},
  nav_market:   {de:'Markt',en:'Market',es:'Mercado',ru:'Рынок',pt:'Mercado'},
  nav_chart:    {de:'Chart',en:'Chart',es:'Gráfico',ru:'График',pt:'Gráfico'},
  nav_backtest: {de:'Backtest',en:'Backtest',es:'Backtest',ru:'Бэктест',pt:'Backtest'},
  nav_tax:      {de:'Steuer',en:'Tax',es:'Impuesto',ru:'Налоги',pt:'Imposto'},
  nav_log:      {de:'Log',en:'Log',es:'Registro',ru:'Журнал',pt:'Log'},
  nav_settings: {de:'Settings',en:'Settings',es:'Ajustes',ru:'Настройки',pt:'Config'},

  /* ── HOME ── */
  portfolio_value:   {de:'Portfolio-Wert',en:'Portfolio Value',es:'Valor de Cartera',ru:'Стоимость портфеля',pt:'Valor do Portfólio'},
  total_return:      {de:'Gesamtrendite',en:'Total Return',es:'Rendimiento Total',ru:'Общая доходность',pt:'Retorno Total'},
  portfolio_goal:    {de:'Portfolio-Ziel',en:'Portfolio Goal',es:'Meta de Cartera',ru:'Цель портфеля',pt:'Meta do Portfólio'},
  achieved:          {de:'erreicht',en:'achieved',es:'alcanzado',ru:'достигнуто',pt:'alcançado'},
  eta_label:         {de:'ETA',en:'ETA',es:'ETA',ru:'Срок',pt:'ETA'},
  fear_greed:        {de:'Fear & Greed Index',en:'Fear & Greed Index',es:'Índice de Miedo y Codicia',ru:'Индекс страха и жадности',pt:'Índice de Medo e Ganância'},
  fear_label:        {de:'Extreme Angst',en:'Extreme Fear',es:'Miedo Extremo',ru:'Крайний страх',pt:'Medo Extremo'},
  fear2_label:       {de:'Angst',en:'Fear',es:'Miedo',ru:'Страх',pt:'Medo'},
  neutral_label:     {de:'Neutral',en:'Neutral',es:'Neutral',ru:'Нейтрально',pt:'Neutro'},
  greed_label:       {de:'Gier',en:'Greed',es:'Codicia',ru:'Жадность',pt:'Ganância'},
  greed2_label:      {de:'Extreme Gier',en:'Extreme Greed',es:'Codicia Extrema',ru:'Крайняя жадность',pt:'Ganância Extrema'},
  buy_allowed:       {de:'✅ Kaufen erlaubt',en:'✅ Buying allowed',es:'✅ Compra permitida',ru:'✅ Покупка разрешена',pt:'✅ Compra permitida'},
  buy_blocked:       {de:'🚫 Kauf blockiert',en:'🚫 Buying blocked',es:'🚫 Compra bloqueada',ru:'🚫 Покупка заблокирована',pt:'🚫 Compra bloqueada'},
  dominance:         {de:'Markt-Dominanz',en:'Market Dominance',es:'Dominancia del Mercado',ru:'Рыночная доминация',pt:'Dominância do Mercado'},
  btc_dom:           {de:'BTC Dominanz',en:'BTC Dominance',es:'Dominancia BTC',ru:'Доминация BTC',pt:'Dominância BTC'},
  usdt_dom:          {de:'USDT Dominanz',en:'USDT Dominance',es:'Dominancia USDT',ru:'Доминация USDT',pt:'Dominância USDT'},
  market_status:     {de:'Markt-Status',en:'Market Status',es:'Estado del Mercado',ru:'Статус рынка',pt:'Status do Mercado'},
  bot_control:       {de:'Bot Steuerung',en:'Bot Control',es:'Control del Bot',ru:'Управление ботом',pt:'Controle do Bot'},
  btn_start:         {de:'▶ Start',en:'▶ Start',es:'▶ Iniciar',ru:'▶ Старт',pt:'▶ Iniciar'},
  btn_stop:          {de:'■ Stop',en:'■ Stop',es:'■ Detener',ru:'■ Стоп',pt:'■ Parar'},
  btn_pause:         {de:'⏸ Pause',en:'⏸ Pause',es:'⏸ Pausar',ru:'⏸ Пауза',pt:'⏸ Pausar'},
  btn_resume:        {de:'▶ Weiter',en:'▶ Resume',es:'▶ Reanudar',ru:'▶ Продолжить',pt:'▶ Retomar'},
  btn_report:        {de:'📊 Report',en:'📊 Report',es:'📊 Informe',ru:'📊 Отчёт',pt:'📊 Relatório'},
  btn_arbitrage:     {de:'💹 Arbitrage',en:'💹 Arbitrage',es:'💹 Arbitraje',ru:'💹 Арбитраж',pt:'💹 Arbitragem'},
  btn_genetic:       {de:'🧬 Genetik',en:'🧬 Genetic',es:'🧬 Genético',ru:'🧬 Генетик',pt:'🧬 Genético'},
  btn_backup:        {de:'💾 Backup',en:'💾 Backup',es:'💾 Copia',ru:'💾 Бэкап',pt:'💾 Backup'},
  portfolio_chart:   {de:'Portfolio-Verlauf',en:'Portfolio History',es:'Historial de Cartera',ru:'История портфеля',pt:'Histórico do Portfólio'},
  activity_feed:     {de:'Bot-Aktivität',en:'Bot Activity',es:'Actividad del Bot',ru:'Активность бота',pt:'Atividade do Bot'},
  arb_opps:          {de:'Arbitrage-Chancen',en:'Arbitrage Opportunities',es:'Oportunidades de Arbitraje',ru:'Арбитражные возможности',pt:'Oportunidades de Arbitragem'},
  circuit_breaker:   {de:'Circuit Breaker aktiv!',en:'Circuit Breaker active!',es:'¡Disyuntor activo!',ru:'Автовыключатель активен!',pt:'Disjuntor ativo!'},
  anomaly_detected:  {de:'Anomalie erkannt — Trading pausiert',en:'Anomaly detected — Trading paused',es:'Anomalía detectada — Trading pausado',ru:'Аномалия — торговля приостановлена',pt:'Anomalia detectada — Trading pausado'},

  /* ── STAT LABELS ── */
  stat_balance:  {de:'💵 Kapital',en:'💵 Balance',es:'💵 Saldo',ru:'💵 Баланс',pt:'💵 Saldo'},
  stat_winrate:  {de:'🎯 Win-Rate',en:'🎯 Win Rate',es:'🎯 Éxito',ru:'🎯 Побед',pt:'🎯 Acerto'},
  stat_drawdown: {de:'📉 Drawdown',en:'📉 Drawdown',es:'📉 Retroceso',ru:'📉 Просадка',pt:'📉 Drawdown'},
  stat_pos:      {de:'📂 Positionen',en:'📂 Positions',es:'📂 Posiciones',ru:'📂 Позиции',pt:'📂 Posições'},
  stat_trades:   {de:'🔄 Trades',en:'🔄 Trades',es:'🔄 Operaciones',ru:'🔄 Сделки',pt:'🔄 Negociações'},
  stat_sharpe:   {de:'📊 Sharpe',en:'📊 Sharpe',es:'📊 Sharpe',ru:'📊 Шарп',pt:'📊 Sharpe'},
  daily_pnl:     {de:'Tages-PnL',en:'Daily PnL',es:'PnL Diario',ru:'Дневной PnL',pt:'PnL Diário'},
  profit_factor: {de:'Profit Faktor',en:'Profit Factor',es:'Factor de Ganancia',ru:'Фактор прибыли',pt:'Fator de Lucro'},
  regime_badge:  {de:'Regime',en:'Regime',es:'Régimen',ru:'Режим',pt:'Regime'},

  /* ── POSITIONS / TRADES ── */
  open_positions:  {de:'Offene Positionen',en:'Open Positions',es:'Posiciones Abiertas',ru:'Открытые позиции',pt:'Posições Abertas'},
  trade_history:   {de:'Trade-Verlauf',en:'Trade History',es:'Historial de Trades',ru:'История сделок',pt:'Histórico de Trades'},
  no_positions:    {de:'Keine offenen Positionen',en:'No open positions',es:'Sin posiciones abiertas',ru:'Нет открытых позиций',pt:'Sem posições abertas'},
  no_trades:       {de:'Noch keine Trades',en:'No trades yet',es:'Sin operaciones aún',ru:'Пока нет сделок',pt:'Ainda sem trades'},
  filter_all:      {de:'Alle',en:'All',es:'Todos',ru:'Все',pt:'Todos'},
  filter_wins:     {de:'✅ Gewinne',en:'✅ Wins',es:'✅ Ganancias',ru:'✅ Прибыль',pt:'✅ Ganhos'},
  filter_losses:   {de:'❌ Verluste',en:'❌ Losses',es:'❌ Pérdidas',ru:'❌ Убытки',pt:'❌ Perdas'},
  filter_long:     {de:'📈 Long',en:'📈 Long',es:'📈 Largo',ru:'📈 Лонг',pt:'📈 Long'},
  filter_short:    {de:'📉 Short',en:'📉 Short',es:'📉 Corto',ru:'📉 Шорт',pt:'📉 Short'},
  filter_dca:      {de:'📉 DCA',en:'📉 DCA',es:'📉 DCA',ru:'📉 DCA',pt:'📉 DCA'},
  btn_close:       {de:'✕ Schließen',en:'✕ Close',es:'✕ Cerrar',ru:'✕ Закрыть',pt:'✕ Fechar'},

  /* ── STATS ── */
  perf_capital:    {de:'💰 Kapital & Rendite',en:'💰 Capital & Return',es:'💰 Capital y Rendimiento',ru:'💰 Капитал и доходность',pt:'💰 Capital e Retorno'},
  start_capital:   {de:'Startkapital',en:'Start Capital',es:'Capital Inicial',ru:'Начальный капитал',pt:'Capital Inicial'},
  current_val:     {de:'Aktuell',en:'Current',es:'Actual',ru:'Текущий',pt:'Atual'},
  total_pnl:       {de:'Gesamt-PnL',en:'Total PnL',es:'PnL Total',ru:'Общий PnL',pt:'PnL Total'},
  returns:         {de:'Rendite',en:'Return',es:'Rendimiento',ru:'Доходность',pt:'Retorno'},
  max_drawdown:    {de:'Max Drawdown',en:'Max Drawdown',es:'Retroceso Máx.',ru:'Макс. просадка',pt:'Drawdown Máx.'},
  trades_label:    {de:'🎯 Trades',en:'🎯 Trades',es:'🎯 Operaciones',ru:'🎯 Сделки',pt:'🎯 Trades'},
  total_label:     {de:'Gesamt',en:'Total',es:'Total',ru:'Всего',pt:'Total'},
  avg_win:         {de:'Ø Gewinn',en:'Avg Win',es:'Ganancia Prom.',ru:'Ср. прибыль',pt:'Ganho Médio'},
  avg_loss:        {de:'Ø Verlust',en:'Avg Loss',es:'Pérdida Prom.',ru:'Ср. убыток',pt:'Perda Média'},
  dca_trades:      {de:'DCA-Trades',en:'DCA Trades',es:'Trades DCA',ru:'DCA-сделки',pt:'Trades DCA'},
  short_trades:    {de:'Short-Trades',en:'Short Trades',es:'Trades Cortos',ru:'Шорт-сделки',pt:'Trades Short'},
  arb_count:       {de:'Arb-Chancen',en:'Arb Opportunities',es:'Oportunidades Arb',ru:'Арб. возможности',pt:'Oportunidades Arb'},
  top_coins:       {de:'🏆 Top Coins (PnL)',en:'🏆 Top Coins (PnL)',es:'🏆 Mejores Monedas',ru:'🏆 Лучшие монеты',pt:'🏆 Melhores Moedas'},
  pnl_by_hour:     {de:'📊 PnL nach Uhrzeit',en:'📊 PnL by Hour',es:'📊 PnL por Hora',ru:'📊 PnL по часам',pt:'📊 PnL por Hora'},
  last_30_trades:  {de:'📈 Letzte 30 Trades',en:'📈 Last 30 Trades',es:'📈 Últimas 30 Operaciones',ru:'📈 Последние 30 сделок',pt:'📈 Últimas 30 Trades'},

  /* ── AI ── */
  ai_engine:       {de:'TREVLIX AI Engine',en:'TREVLIX AI Engine',es:'Motor IA TREVLIX',ru:'ИИ-движок TREVLIX',pt:'Motor IA TREVLIX'},
  ai_training:     {de:'KI-Training',en:'AI Training',es:'Entrenamiento IA',ru:'Обучение ИИ',pt:'Treino IA'},
  walk_forward:    {de:'Walk-Forward',en:'Walk-Forward',es:'Walk-Forward',ru:'Скользящий тест',pt:'Walk-Forward'},
  bull_model:      {de:'🐂 Bull-Modell',en:'🐂 Bull Model',es:'🐂 Modelo Alcista',ru:'🐂 Бычья модель',pt:'🐂 Modelo Bull'},
  bear_model:      {de:'🐻 Bear-Modell',en:'🐻 Bear Model',es:'🐻 Modelo Bajista',ru:'🐻 Медвежья модель',pt:'🐻 Modelo Bear'},
  rl_agent:        {de:'🤖 RL-Agent',en:'🤖 RL Agent',es:'🤖 Agente AR',ru:'🤖 RL-агент',pt:'🤖 Agente RL'},
  genetic:         {de:'🧬 Genetik',en:'🧬 Genetic',es:'🧬 Genético',ru:'🧬 Генетик',pt:'🧬 Genético'},
  anomaly:         {de:'🔍 Anomalie',en:'🔍 Anomaly',es:'🔍 Anomalía',ru:'🔍 Аномалия',pt:'🔍 Anomalia'},
  samples_label:   {de:'Samples (Global)',en:'Samples (Global)',es:'Muestras (Global)',ru:'Сэмплов (всего)',pt:'Amostras (Global)'},
  bull_bear:       {de:'Bull / Bear',en:'Bull / Bear',es:'Alcista / Bajista',ru:'Бык / Медведь',pt:'Bull / Bear'},
  allowed_label:   {de:'Erlaubt',en:'Allowed',es:'Permitido',ru:'Разрешено',pt:'Permitido'},
  blocked_label:   {de:'Blockiert',en:'Blocked',es:'Bloqueado',ru:'Заблокировано',pt:'Bloqueado'},
  news_active:     {de:'News aktiv',en:'News active',es:'Noticias activas',ru:'Новости активны',pt:'Notícias ativas'},
  onchain_label:   {de:'On-Chain',en:'On-Chain',es:'On-Chain',ru:'Ончейн',pt:'On-Chain'},
  strat_weights:   {de:'Strategie-Gewichte (9 Strats)',en:'Strategy Weights (9 Strats)',es:'Pesos de Estrategia',ru:'Веса стратегий',pt:'Pesos de Estratégia'},
  ai_decisions:    {de:'KI-Entscheidungen',en:'AI Decisions',es:'Decisiones IA',ru:'Решения ИИ',pt:'Decisões IA'},
  gen_history:     {de:'Genetik-History',en:'Genetic History',es:'Historial Genético',ru:'История генетика',pt:'Histórico Genético'},
  btn_train:       {de:'🧠 Train',en:'🧠 Train',es:'🧠 Entrenar',ru:'🧠 Обучить',pt:'🧠 Treinar'},
  btn_optimize:    {de:'🔬 Optim',en:'🔬 Optim',es:'🔬 Optimizar',ru:'🔬 Оптим',pt:'🔬 Otimizar'},
  btn_reset_ai:    {de:'🔄 Reset',en:'🔄 Reset',es:'🔄 Restablecer',ru:'🔄 Сброс',pt:'🔄 Reset'},

  /* ── MARKET / HEATMAP ── */
  heatmap_title:   {de:'Markt-Heatmap',en:'Market Heatmap',es:'Mapa de Calor',ru:'Тепловая карта',pt:'Mapa de Calor'},
  sort_change:     {de:'% Change',en:'% Change',es:'% Cambio',ru:'% Изменение',pt:'% Variação'},
  sort_volume:     {de:'Volumen',en:'Volume',es:'Volumen',ru:'Объём',pt:'Volume'},
  sort_news:       {de:'📰 News',en:'📰 News',es:'📰 Noticias',ru:'📰 Новости',pt:'📰 Notícias'},
  hm_long_pos:     {de:'🔷 Long-Pos.',en:'🔷 Long Pos.',es:'🔷 Pos. Larga',ru:'🔷 Лонг',pt:'🔷 Pos. Long'},
  hm_short_pos:    {de:'🔺 Short-Pos.',en:'🔺 Short Pos.',es:'🔺 Pos. Corta',ru:'🔺 Шорт',pt:'🔺 Pos. Short'},
  arb_scanner:     {de:'Arbitrage-Scanner',en:'Arbitrage Scanner',es:'Escáner de Arbitraje',ru:'Сканер арбитража',pt:'Scanner de Arbitragem'},
  arb_info:        {de:'Net-Spread nach Fees (~0.16%). Binance ↔ Bybit.',en:'Net spread after fees (~0.16%). Binance ↔ Bybit.',es:'Spread neto tras comisiones (~0.16%). Binance ↔ Bybit.',ru:'Чистый спред после комиссий (~0.16%). Binance ↔ Bybit.',pt:'Spread líquido após taxas (~0.16%). Binance ↔ Bybit.'},
  btn_scan_now:    {de:'🔍 Jetzt scannen',en:'🔍 Scan now',es:'🔍 Escanear ahora',ru:'🔍 Сканировать',pt:'🔍 Escanear agora'},
  no_scan:         {de:'Noch kein Scan',en:'No scan yet',es:'Sin escaneo aún',ru:'Сканирование не выполнялось',pt:'Sem escaneamento ainda'},
  price_alerts:    {de:'Preis-Alerts',en:'Price Alerts',es:'Alertas de Precio',ru:'Ценовые алерты',pt:'Alertas de Preço'},
  symbol_label:    {de:'Symbol',en:'Symbol',es:'Símbolo',ru:'Символ',pt:'Símbolo'},
  target_price:    {de:'Zielpreis',en:'Target Price',es:'Precio Objetivo',ru:'Целевая цена',pt:'Preço Alvo'},
  direction_label: {de:'Richtung',en:'Direction',es:'Dirección',ru:'Направление',pt:'Direção'},
  dir_above:       {de:'↑ Über',en:'↑ Above',es:'↑ Por Encima',ru:'↑ Выше',pt:'↑ Acima'},
  dir_below:       {de:'↓ Unter',en:'↓ Below',es:'↓ Por Debajo',ru:'↓ Ниже',pt:'↓ Abaixo'},
  no_alerts:       {de:'Keine Alerts',en:'No alerts',es:'Sin alertas',ru:'Нет алертов',pt:'Sem alertas'},

  /* ── CHART ── */
  chart_load:      {de:'← Symbol eingeben & Laden',en:'← Enter symbol & Load',es:'← Ingresar símbolo y Cargar',ru:'← Введите символ и загрузите',pt:'← Digite símbolo e Carregar'},
  live_indicators: {de:'Live-Indikatoren',en:'Live Indicators',es:'Indicadores en Vivo',ru:'Живые индикаторы',pt:'Indicadores ao Vivo'},
  rsi_label:       {de:'RSI',en:'RSI',es:'RSI',ru:'RSI',pt:'RSI'},
  bb_pos:          {de:'BB-Position',en:'BB Position',es:'Posición BB',ru:'Позиция BB',pt:'Posição BB'},
  vol_ratio:       {de:'Vol-Ratio',en:'Vol Ratio',es:'Ratio Vol.',ru:'Объём-ратио',pt:'Razão Vol.'},
  ob_ratio:        {de:'OB-Ratio',en:'OB Ratio',es:'Ratio OB',ru:'ОБ-ратио',pt:'Razão OB'},
  mtf_label:       {de:'4h MTF',en:'4h MTF',es:'4h MTF',ru:'4ч МТФ',pt:'4h MTF'},
  sentiment_label: {de:'Sentiment',en:'Sentiment',es:'Sentimiento',ru:'Настроение',pt:'Sentimento'},
  news_score:      {de:'News Score',en:'News Score',es:'Puntuación News',ru:'Оценка новостей',pt:'Pontuação News'},
  news_feed:       {de:'News-Feed',en:'News Feed',es:'Feed de Noticias',ru:'Лента новостей',pt:'Feed de Notícias'},
  chart_hint:      {de:'Lade Chart um News zu sehen',en:'Load chart to see news',es:'Carga el gráfico para ver noticias',ru:'Загрузите график для новостей',pt:'Carregue o gráfico para ver notícias'},

  /* ── BACKTEST ── */
  backtest_engine: {de:'Backtest Engine',en:'Backtest Engine',es:'Motor de Backtest',ru:'Движок бэктеста',pt:'Motor de Backtest'},
  timeframe_label: {de:'Zeitrahmen',en:'Timeframe',es:'Marco Temporal',ru:'Таймфрейм',pt:'Período'},
  candles_label:   {de:'Kerzen',en:'Candles',es:'Velas',ru:'Свечи',pt:'Velas'},
  sl_label:        {de:'Stop-Loss %',en:'Stop-Loss %',es:'Stop-Loss %',ru:'Стоп-лосс %',pt:'Stop-Loss %'},
  tp_label:        {de:'Take-Profit %',en:'Take-Profit %',es:'Take-Profit %',ru:'Тейк-профит %',pt:'Take-Profit %'},
  vote_threshold:  {de:'Vote-Threshold %',en:'Vote Threshold %',es:'Umbral de Voto %',ru:'Порог голосования %',pt:'Limiar de Voto %'},
  btn_run_bt:      {de:'🔬 Backtest starten',en:'🔬 Run Backtest',es:'🔬 Iniciar Backtest',ru:'🔬 Запустить бэктест',pt:'🔬 Iniciar Backtest'},
  bt_result:       {de:'Backtest-Ergebnis',en:'Backtest Result',es:'Resultado del Backtest',ru:'Результат бэктеста',pt:'Resultado do Backtest'},
  bt_history_lbl:  {de:'Backtest-Verlauf',en:'Backtest History',es:'Historial de Backtest',ru:'История бэктестов',pt:'Histórico de Backtest'},
  win_rate:        {de:'Win-Rate',en:'Win Rate',es:'Tasa de Éxito',ru:'Процент побед',pt:'Taxa de Acerto'},
  max_dd:          {de:'Max DD',en:'Max DD',es:'DD Máx.',ru:'Макс. ДД',pt:'DD Máx.'},
  running_bt:      {de:'⏳ Backtest läuft...',en:'⏳ Backtest running...',es:'⏳ Backtest en curso...',ru:'⏳ Бэктест выполняется...',pt:'⏳ Backtest a decorrer...'},

  /* ── TAX ── */
  tax_report:      {de:'Steuer-Report',en:'Tax Report',es:'Informe Fiscal',ru:'Налоговый отчёт',pt:'Relatório Fiscal'},
  tax_disclaimer:  {de:'Kein Ersatz für Steuerberater. Vereinfachte Berechnung.',en:'Not a substitute for tax advice. Simplified calculation.',es:'No sustituye al asesor fiscal. Cálculo simplificado.',ru:'Не заменяет налогового консультанта. Упрощённый расчёт.',pt:'Não substitui consultor fiscal. Cálculo simplificado.'},
  tax_year:        {de:'Steuerjahr',en:'Tax Year',es:'Año Fiscal',ru:'Налоговый год',pt:'Ano Fiscal'},
  method_label:    {de:'Methode',en:'Method',es:'Método',ru:'Метод',pt:'Método'},
  btn_calculate:   {de:'🧮 Berechnen',en:'🧮 Calculate',es:'🧮 Calcular',ru:'🧮 Рассчитать',pt:'🧮 Calcular'},
  btn_csv_export:  {de:'📥 CSV Export',en:'📥 CSV Export',es:'📥 Exportar CSV',ru:'📥 CSV Экспорт',pt:'📥 Exportar CSV'},
  gains_label:     {de:'Gewinne',en:'Gains',es:'Ganancias',ru:'Прибыль',pt:'Ganhos'},
  losses_label:    {de:'Verluste',en:'Losses',es:'Pérdidas',ru:'Убытки',pt:'Perdas'},
  net_pnl:         {de:'Netto PnL',en:'Net PnL',es:'PnL Neto',ru:'Чистый PnL',pt:'PnL Líquido'},
  taxable_label:   {de:'Steuerpflichtig',en:'Taxable',es:'Imponible',ru:'Налогооблагаемый',pt:'Tributável'},
  fees_label:      {de:'Gebühren',en:'Fees',es:'Comisiones',ru:'Комиссии',pt:'Taxas'},
  tax_warning:     {de:'Steuerpflichtige Gewinne > 600 USDT — Steuerberater empfohlen!',en:'Taxable gains > 600 USDT — Tax advisor recommended!',es:'Ganancias imponibles > 600 USDT — ¡Se recomienda asesor fiscal!',ru:'Налогооблагаемая прибыль > 600 USDT — рекомендуется консультант!',pt:'Ganhos tributáveis > 600 USDT — Consultor fiscal recomendado!'},
  top_gains:       {de:'Top Gewinne',en:'Top Gains',es:'Principales Ganancias',ru:'Лучшие сделки',pt:'Principais Ganhos'},

  /* ── LOG ── */
  system_log:      {de:'System-Log',en:'System Log',es:'Registro del Sistema',ru:'Системный журнал',pt:'Log do Sistema'},
  log_all:         {de:'Alle',en:'All',es:'Todos',ru:'Все',pt:'Todos'},
  log_trades:      {de:'💰 Trades',en:'💰 Trades',es:'💰 Trades',ru:'💰 Сделки',pt:'💰 Trades'},
  log_signals:     {de:'📡 Signale',en:'📡 Signals',es:'📡 Señales',ru:'📡 Сигналы',pt:'📡 Sinais'},
  log_system:      {de:'⚙️ System',en:'⚙️ System',es:'⚙️ Sistema',ru:'⚙️ Система',pt:'⚙️ Sistema'},
  log_ai:          {de:'🧠 KI',en:'🧠 AI',es:'🧠 IA',ru:'🧠 ИИ',pt:'🧠 IA'},
  log_arb:         {de:'💹 Arb',en:'💹 Arb',es:'💹 Arb',ru:'💹 Арб',pt:'💹 Arb'},
  btn_clear:       {de:'Leer',en:'Clear',es:'Limpiar',ru:'Очистить',pt:'Limpar'},
  signal_feed:     {de:'Signal-Feed',en:'Signal Feed',es:'Feed de Señales',ru:'Лента сигналов',pt:'Feed de Sinais'},
  waiting_signals: {de:'Warte auf Signale...',en:'Waiting for signals...',es:'Esperando señales...',ru:'Ожидание сигналов...',pt:'Aguardando sinais...'},

  /* ── SETTINGS ── */
  settings_title:       {de:'Alle Einstellungen speichern',en:'Save all settings',es:'Guardar todos los ajustes',ru:'Сохранить все настройки',pt:'Salvar todas as configurações'},
  sec_goal:             {de:'🎯 Portfolio-Ziel',en:'🎯 Portfolio Goal',es:'🎯 Meta de Cartera',ru:'🎯 Цель портфеля',pt:'🎯 Meta do Portfólio'},
  goal_help:            {de:'ETA + Fortschrittsbalken auf Startseite',en:'ETA + progress bar on home screen',es:'ETA + barra de progreso en inicio',ru:'ETA + прогресс-бар на главной',pt:'ETA + barra de progresso na tela inicial'},
  sec_exchange:         {de:'🌐 Exchange & Keys',en:'🌐 Exchange & Keys',es:'🌐 Exchange & Claves',ru:'🌐 Биржа & Ключи',pt:'🌐 Exchange & Chaves'},
  sec_presets:          {de:'🎛️ Risiko-Presets',en:'🎛️ Risk Presets',es:'🎛️ Presets de Riesgo',ru:'🎛️ Пресеты риска',pt:'🎛️ Predefinições de Risco'},
  preset_conservative:  {de:'🛡️ Konservativ – Wenig Risiko',en:'🛡️ Conservative – Low Risk',es:'🛡️ Conservador – Bajo Riesgo',ru:'🛡️ Консервативный – Низкий риск',pt:'🛡️ Conservador – Baixo Risco'},
  preset_balanced:      {de:'⚖️ Ausgewogen – Empfohlen',en:'⚖️ Balanced – Recommended',es:'⚖️ Equilibrado – Recomendado',ru:'⚖️ Сбалансированный – Рекомендуется',pt:'⚖️ Equilibrado – Recomendado'},
  preset_aggressive:    {de:'🚀 Aggressiv – Hohes Risiko',en:'🚀 Aggressive – High Risk',es:'🚀 Agresivo – Alto Riesgo',ru:'🚀 Агрессивный – Высокий риск',pt:'🚀 Agressivo – Alto Risco'},
  sec_trading:          {de:'📈 Handel',en:'📈 Trading',es:'📈 Trading',ru:'📈 Торговля',pt:'📈 Negociação'},
  scan_interval:        {de:'Scan-Intervall (s)',en:'Scan Interval (s)',es:'Intervalo de Escaneo (s)',ru:'Интервал сканирования (с)',pt:'Intervalo de Scan (s)'},
  max_positions:        {de:'Max. Positionen',en:'Max. Positions',es:'Máx. Posiciones',ru:'Макс. позиций',pt:'Máx. Posições'},
  paper_trading:        {de:'Paper Trading',en:'Paper Trading',es:'Trading Simulado',ru:'Бумажная торговля',pt:'Paper Trading'},
  paper_help:           {de:'Simulation – kein echtes Geld',en:'Simulation – no real money',es:'Simulación – sin dinero real',ru:'Симуляция – без реальных денег',pt:'Simulação – sem dinheiro real'},
  sec_risk:             {de:'🛡️ Risiko & Stop',en:'🛡️ Risk & Stop',es:'🛡️ Riesgo & Stop',ru:'🛡️ Риск & Стоп',pt:'🛡️ Risco & Stop'},
  trailing_stop:        {de:'Trailing Stop',en:'Trailing Stop',es:'Stop Móvil',ru:'Скользящий стоп',pt:'Stop Móvel'},
  max_spread:           {de:'Max. Spread %',en:'Max. Spread %',es:'Spread Máx. %',ru:'Макс. спред %',pt:'Spread Máx. %'},
  sec_dca:              {de:'📉 DCA & Partial TP',en:'📉 DCA & Partial TP',es:'📉 DCA & TP Parcial',ru:'📉 DCA & Частичный TP',pt:'📉 DCA & TP Parcial'},
  dca_enable:           {de:'DCA aktivieren',en:'Enable DCA',es:'Activar DCA',ru:'Включить DCA',pt:'Ativar DCA'},
  dca_help:             {de:'Nachkaufen bei Kursrückgang',en:'Buy more on price dip',es:'Comprar más en caída',ru:'Докупать при снижении цены',pt:'Comprar mais em queda'},
  dca_levels:           {de:'DCA-Levels max.',en:'DCA Levels max.',es:'Niveles DCA máx.',ru:'Макс. уровней DCA',pt:'Níveis DCA máx.'},
  partial_tp:           {de:'Partial TP aktivieren',en:'Enable Partial TP',es:'Activar TP Parcial',ru:'Включить частичный TP',pt:'Ativar TP Parcial'},
  sec_shorts:           {de:'📉 Short-Selling',en:'📉 Short Selling',es:'📉 Venta en Corto',ru:'📉 Короткие продажи',pt:'📉 Venda a Descoberto'},
  shorts_enable:        {de:'Short aktivieren',en:'Enable Short',es:'Activar Short',ru:'Включить шорт',pt:'Ativar Short'},
  shorts_help:          {de:'Futures auf Bybit/Binance nötig',en:'Futures on Bybit/Binance required',es:'Requiere futuros en Bybit/Binance',ru:'Требуются фьючерсы на Bybit/Binance',pt:'Requer futuros na Bybit/Binance'},
  sec_arb:              {de:'💹 Arbitrage',en:'💹 Arbitrage',es:'💹 Arbitraje',ru:'💹 Арбитраж',pt:'💹 Arbitragem'},
  arb_enable:           {de:'Arbitrage-Scanner',en:'Arbitrage Scanner',es:'Escáner de Arbitraje',ru:'Сканер арбитража',pt:'Scanner de Arbitragem'},
  min_spread:           {de:'Min. Spread %',en:'Min. Spread %',es:'Spread Mín. %',ru:'Мин. спред %',pt:'Spread Mín. %'},
  sec_circuit:          {de:'⚡ Circuit Breaker',en:'⚡ Circuit Breaker',es:'⚡ Disyuntor',ru:'⚡ Автовыключатель',pt:'⚡ Disjuntor'},
  losses_to_pause:      {de:'Verluste bis Pause',en:'Losses until pause',es:'Pérdidas hasta pausa',ru:'Убытков до паузы',pt:'Perdas até pausa'},
  pause_duration:       {de:'Pause-Dauer (Min)',en:'Pause Duration (min)',es:'Duración de Pausa (min)',ru:'Длительность паузы (мин)',pt:'Duração da Pausa (min)'},
  sec_ai:               {de:'🧠 KI & Analyse',en:'🧠 AI & Analysis',es:'🧠 IA & Análisis',ru:'🧠 ИИ & Анализ',pt:'🧠 IA & Análise'},
  ai_confidence:        {de:'Min. KI-Konfidenz %',en:'Min. AI Confidence %',es:'Confianza IA mín. %',ru:'Мин. уверенность ИИ %',pt:'Confiança IA mín. %'},
  mtf_label2:           {de:'Multi-Timeframe (4h)',en:'Multi-Timeframe (4h)',es:'Multi-Marco Temporal (4h)',ru:'Мульти-таймфрейм (4ч)',pt:'Multi-Período (4h)'},
  news_sentiment:       {de:'News-Sentiment',en:'News Sentiment',es:'Sentimiento de Noticias',ru:'Настроение новостей',pt:'Sentimento de Notícias'},
  news_api_help:        {de:'CryptoPanic API',en:'CryptoPanic API',es:'CryptoPanic API',ru:'CryptoPanic API',pt:'CryptoPanic API'},
  onchain_data:         {de:'On-Chain Daten',en:'On-Chain Data',es:'Datos On-Chain',ru:'Ончейн-данные',pt:'Dados On-Chain'},
  dom_filter:           {de:'Dominanz-Filter',en:'Dominance Filter',es:'Filtro de Dominancia',ru:'Фильтр доминирования',pt:'Filtro de Dominância'},
  anomaly_detect:       {de:'Anomalie-Erkennung',en:'Anomaly Detection',es:'Detección de Anomalías',ru:'Обнаружение аномалий',pt:'Detecção de Anomalias'},
  gen_optimizer:        {de:'Genetischer Optimizer',en:'Genetic Optimizer',es:'Optimizador Genético',ru:'Генетический оптимизатор',pt:'Otimizador Genético'},
  rl_agent_s:           {de:'RL-Agent',en:'RL Agent',es:'Agente AR',ru:'RL-агент',pt:'Agente RL'},
  fear_greed_s:         {de:'Fear & Greed',en:'Fear & Greed',es:'Miedo y Codicia',ru:'Страх & Жадность',pt:'Medo e Ganância'},
  kelly_sizing:         {de:'Kelly-Sizing',en:'Kelly Sizing',es:'Dimensionamiento Kelly',ru:'Размер позиции Келли',pt:'Kelly Sizing'},
  news_block_score:     {de:'News Block-Score',en:'News Block Score',es:'Puntuación de Bloqueo',ru:'Порог блокировки новостей',pt:'Pontuação de Bloqueio'},
  news_block_help:      {de:'Kauf blockiert unter diesem Wert',en:'Buy blocked below this value',es:'Compra bloqueada por debajo de este valor',ru:'Покупка заблокирована ниже этого значения',pt:'Compra bloqueada abaixo deste valor'},
  sec_discord:          {de:'💬 Discord',en:'💬 Discord',es:'💬 Discord',ru:'💬 Discord',pt:'💬 Discord'},
  report_hour:          {de:'Report-Uhrzeit',en:'Report Hour',es:'Hora del Informe',ru:'Час отчёта',pt:'Hora do Relatório'},
  btn_save_discord:     {de:'💬 Speichern & Test',en:'💬 Save & Test',es:'💬 Guardar y Probar',ru:'💬 Сохранить и тест',pt:'💬 Salvar e Testar'},
  sec_api:              {de:'🔑 REST-API (JWT)',en:'🔑 REST API (JWT)',es:'🔑 API REST (JWT)',ru:'🔑 REST-API (JWT)',pt:'🔑 REST API (JWT)'},
  api_info:             {de:'Docs: /api/v1/docs | TradingView Webhook: /api/v1/signal',en:'Docs: /api/v1/docs | TradingView Webhook: /api/v1/signal',es:'Docs: /api/v1/docs | Webhook TradingView: /api/v1/signal',ru:'Docs: /api/v1/docs | Вебхук TradingView: /api/v1/signal',pt:'Docs: /api/v1/docs | Webhook TradingView: /api/v1/signal'},
  btn_create_token:     {de:'🔑 Neuen API-Token erstellen',en:'🔑 Create new API token',es:'🔑 Crear nuevo token API',ru:'🔑 Создать новый API-токен',pt:'🔑 Criar novo token API'},
  btn_api_docs:         {de:'📚 API-Dokumentation',en:'📚 API Documentation',es:'📚 Documentación API',ru:'📚 Документация API',pt:'📚 Documentação API'},
  sec_backup:           {de:'💾 Backup',en:'💾 Backup',es:'💾 Copia de Seguridad',ru:'💾 Резервная копия',pt:'💾 Backup'},
  auto_backup:          {de:'Auto-Backup tägl. 03:00',en:'Auto-Backup daily 03:00',es:'Copia automática diaria 03:00',ru:'Авто-бэкап ежедневно 03:00',pt:'Backup automático diário 03:00'},
  btn_manual_backup:    {de:'💾 Jetzt Backup erstellen',en:'💾 Create backup now',es:'💾 Crear copia ahora',ru:'💾 Создать бэкап сейчас',pt:'💾 Criar backup agora'},
  btn_wizard:           {de:'🧙 Einrichtungs-Assistent',en:'🧙 Setup Wizard',es:'🧙 Asistente de Configuración',ru:'🧙 Мастер настройки',pt:'🧙 Assistente de Configuração'},
  btn_save_keys:        {de:'🔑 Keys speichern',en:'🔑 Save keys',es:'🔑 Guardar claves',ru:'🔑 Сохранить ключи',pt:'🔑 Salvar chaves'},
  language_label:       {de:'🌐 Sprache',en:'🌐 Language',es:'🌐 Idioma',ru:'🌐 Язык',pt:'🌐 Idioma'},

  /* ── WIZARD ── */
  wiz_welcome_title:  {de:'Willkommen bei',en:'Welcome to',es:'Bienvenido a',ru:'Добро пожаловать в',pt:'Bem-vindo ao'},
  wiz_welcome_sub:    {de:'Assistent richtet deinen Bot in 5 Schritten ein.',en:'Wizard sets up your bot in 5 steps.',es:'El asistente configura tu bot en 5 pasos.',ru:'Мастер настроит бота за 5 шагов.',pt:'O assistente configura o bot em 5 etapas.'},
  wiz_lets_go:        {de:'→ Los geht\'s!',en:'→ Let\'s go!',es:'→ ¡Empecemos!',ru:'→ Поехали!',pt:'→ Vamos lá!'},
  wiz_exchange:       {de:'Exchange wählen',en:'Choose Exchange',es:'Elegir Exchange',ru:'Выбрать биржу',pt:'Escolher Exchange'},
  wiz_api_keys:       {de:'API-Keys',en:'API Keys',es:'Claves API',ru:'API-ключи',pt:'Chaves API'},
  wiz_paper_note:     {de:'Paper-Mode ist Standard — kein echtes Geld nötig.',en:'Paper mode is default — no real money needed.',es:'Modo simulación por defecto — sin dinero real.',ru:'По умолчанию — бумажный режим, без реальных денег.',pt:'Modo simulação por padrão — sem dinheiro real.'},
  wiz_risk_profile:   {de:'Risiko-Profil',en:'Risk Profile',es:'Perfil de Riesgo',ru:'Профиль риска',pt:'Perfil de Risco'},
  wiz_complete_title: {de:'Alles bereit!',en:'All set!',es:'¡Todo listo!',ru:'Всё готово!',pt:'Tudo pronto!'},
  wiz_complete_sub:   {de:'Klicke Start für Paper-Trading. Echten Handel in Settings aktivieren.',en:'Click Start for paper trading. Enable live trading in Settings.',es:'Clic en Iniciar para trading simulado. Activa en Ajustes.',ru:'Нажмите Старт для бумажной торговли. Включите реальную в Настройках.',pt:'Clique em Iniciar para paper trading. Ative o live em Configurações.'},
  wiz_open_dashboard: {de:'✅ Dashboard öffnen',en:'✅ Open Dashboard',es:'✅ Abrir Panel',ru:'✅ Открыть панель',pt:'✅ Abrir Painel'},
  wiz_next:           {de:'→ Weiter',en:'→ Next',es:'→ Siguiente',ru:'→ Далее',pt:'→ Próximo'},
  wiz_save_next:      {de:'→ Speichern & Weiter',en:'→ Save & Next',es:'→ Guardar y Siguiente',ru:'→ Сохранить и далее',pt:'→ Salvar e Próximo'},

  /* ── WEBSITE ── */
  web_nav_features:    {de:'Features',en:'Features',es:'Características',ru:'Возможности',pt:'Recursos'},
  web_nav_ai:          {de:'KI Engine',en:'AI Engine',es:'Motor IA',ru:'ИИ-движок',pt:'Motor IA'},
  web_nav_strategies:  {de:'Strategien',en:'Strategies',es:'Estrategias',ru:'Стратегии',pt:'Estratégias'},
  web_nav_install:     {de:'Installation',en:'Installation',es:'Instalación',ru:'Установка',pt:'Instalação'},
  web_nav_specs:       {de:'Spezifikationen',en:'Specifications',es:'Especificaciones',ru:'Технические характеристики',pt:'Especificações'},
  web_nav_download:    {de:'Download',en:'Download',es:'Descargar',ru:'Скачать',pt:'Download'},
  web_hero_eyebrow:    {de:'v1.0.0 · trevlix.com · Open Source',en:'v1.0.0 · trevlix.com · Open Source',es:'v1.0.0 · trevlix.com · Código Abierto',ru:'v1.0.0 · trevlix.com · Открытый код',pt:'v1.0.0 · trevlix.com · Código Aberto'},
  web_hero_sub:        {de:'Der fortschrittlichste Crypto Trading Bot. KI-gesteuert, selbstlernend, mit 14 Echtzeit-Features — von Anomalie-Detektion bis Arbitrage.',en:'The most advanced Crypto Trading Bot. AI-powered, self-learning, with 14 real-time features — from anomaly detection to arbitrage.',es:'El bot de trading cripto más avanzado. Impulsado por IA, autoaprendizaje, con 14 características en tiempo real.',ru:'Самый продвинутый крипто-торговый бот. ИИ-управление, самообучение, 14 функций в реальном времени.',pt:'O bot de trading cripto mais avançado. Alimentado por IA, autoaprendizagem, com 14 recursos em tempo real.'},
  web_btn_start:       {de:'⚡ Jetzt starten',en:'⚡ Get started',es:'⚡ Comenzar ahora',ru:'⚡ Начать сейчас',pt:'⚡ Começar agora'},
  web_btn_discover:    {de:'Features entdecken',en:'Explore Features',es:'Explorar Características',ru:'Изучить возможности',pt:'Explorar Recursos'},
  web_stat_strategies: {de:'KI-Strategien',en:'AI Strategies',es:'Estrategias IA',ru:'ИИ-стратегий',pt:'Estratégias IA'},
  web_stat_features:   {de:'Features',en:'Features',es:'Características',ru:'Функций',pt:'Recursos'},
  web_stat_loc:        {de:'Lines of Code',en:'Lines of Code',es:'Líneas de Código',ru:'Строк кода',pt:'Linhas de Código'},
  web_stat_exchanges:  {de:'Exchanges',en:'Exchanges',es:'Exchanges',ru:'Бирж',pt:'Exchanges'},
  web_feat_eyebrow:    {de:'Features',en:'Features',es:'Características',ru:'Возможности',pt:'Recursos'},
  web_feat_title1:     {de:'Alles was du',en:'Everything you',es:'Todo lo que',ru:'Всё что тебе',pt:'Tudo o que'},
  web_feat_title2:     {de:'brauchst',en:'need',es:'necesitas',ru:'нужно',pt:'precisas'},
  web_feat_sub:        {de:'14 voll integrierte Module — von der KI bis zur Steuerauswertung.',en:'14 fully integrated modules — from AI to tax reporting.',es:'14 módulos totalmente integrados — de la IA a la declaración fiscal.',ru:'14 полностью интегрированных модулей — от ИИ до налоговой отчётности.',pt:'14 módulos totalmente integrados — da IA ao relatório fiscal.'},
  web_ai_eyebrow:      {de:'KI Engine',en:'AI Engine',es:'Motor IA',ru:'ИИ-движок',pt:'Motor IA'},
  web_ai_title1:       {de:'4 Modelle.',en:'4 Models.',es:'4 Modelos.',ru:'4 Модели.',pt:'4 Modelos.'},
  web_ai_title2:       {de:'Ein Ziel.',en:'One Goal.',es:'Un Objetivo.',ru:'Одна цель.',pt:'Um Objetivo.'},
  web_ai_sub:          {de:'TREVLIX kombiniert vier KI-Systeme zu einem hochpräzisen Ensemble.',en:'TREVLIX combines four AI systems into a high-precision ensemble.',es:'TREVLIX combina cuatro sistemas de IA en un conjunto de alta precisión.',ru:'TREVLIX объединяет четыре ИИ-системы в высокоточный ансамбль.',pt:'TREVLIX combina quatro sistemas de IA num conjunto de alta precisão.'},
  web_strat_eyebrow:   {de:'9 Strategien',en:'9 Strategies',es:'9 Estrategias',ru:'9 Стратегий',pt:'9 Estratégias'},
  web_strat_title1:    {de:'Mehrheitsentscheid',en:'Majority vote',es:'Voto mayoritario',ru:'Голосование большинства',pt:'Voto maioritário'},
  web_strat_title2:    {de:'durch Abstimmung',en:'by consensus',es:'por consenso',ru:'по консенсусу',pt:'por consenso'},
  web_strat_sub:       {de:'Jede Strategie gibt eine Stimme ab. Die KI gewichtet und bündelt alle Signale.',en:'Each strategy casts a vote. The AI weights and combines all signals.',es:'Cada estrategia emite un voto. La IA pondera y combina todas las señales.',ru:'Каждая стратегия голосует. ИИ взвешивает и объединяет все сигналы.',pt:'Cada estratégia vota. A IA pondera e combina todos os sinais.'},
  web_how_eyebrow:     {de:'Installation',en:'Installation',es:'Instalación',ru:'Установка',pt:'Instalação'},
  web_how_title1:      {de:'In 5 Minuten',en:'In 5 minutes',es:'En 5 minutos',ru:'За 5 минут',pt:'Em 5 minutos'},
  web_how_title2:      {de:'live',en:'live',es:'en vivo',ru:'в работе',pt:'ao vivo'},
  web_how_sub:         {de:'TREVLIX läuft auf jedem Server oder lokal. MySQL + Python — fertig.',en:'TREVLIX runs on any server or locally. MySQL + Python — done.',es:'TREVLIX funciona en cualquier servidor o localmente. MySQL + Python — listo.',ru:'TREVLIX работает на любом сервере или локально. MySQL + Python — готово.',pt:'TREVLIX funciona em qualquer servidor ou localmente. MySQL + Python — pronto.'},
  web_oss_eyebrow:     {de:'Open Source',en:'Open Source',es:'Código Abierto',ru:'Открытый код',pt:'Código Aberto'},
  web_oss_title:       {de:'100% kostenlos.\n100% dein Code.',en:'100% free.\n100% your code.',es:'100% gratis.\n100% tu código.',ru:'100% бесплатно.\n100% твой код.',pt:'100% grátis.\n100% o teu código.'},
  web_oss_desc:        {de:'TREVLIX ist vollständig Open Source. Kein Abo, keine versteckten Kosten, kein Cloud-Zwang.',en:'TREVLIX is fully open source. No subscription, no hidden costs, no cloud required.',es:'TREVLIX es completamente de código abierto. Sin suscripción, sin costos ocultos.',ru:'TREVLIX полностью открытый. Без подписки, скрытых расходов, без облака.',pt:'TREVLIX é totalmente open source. Sem subscrição, sem custos ocultos.'},
  web_specs_eyebrow:   {de:'Technische Spezifikationen',en:'Technical Specifications',es:'Especificaciones Técnicas',ru:'Технические характеристики',pt:'Especificações Técnicas'},
  web_specs_title1:    {de:'Gebaut für',en:'Built for',es:'Construido para',ru:'Создан для',pt:'Construído para'},
  web_specs_title2:    {de:'Performance',en:'Performance',es:'Rendimiento',ru:'Производительности',pt:'Desempenho'},
  web_cta_title1:      {de:'Bereit für',en:'Ready for',es:'¿Listo para',ru:'Готов к',pt:'Pronto para'},
  web_cta_title2:      {de:'Quantum Trading?',en:'Quantum Trading?',es:'Quantum Trading?',ru:'Quantum Trading?',pt:'Quantum Trading?'},
  web_cta_sub:         {de:'Starte mit Paper-Trading — kein echtes Geld, kein Risiko.',en:'Start with Paper Trading — no real money, no risk.',es:'Comienza con Trading Simulado — sin dinero real, sin riesgo.',ru:'Начните с бумажной торговли — без реальных денег, без риска.',pt:'Comece com Paper Trading — sem dinheiro real, sem risco.'},
  web_btn_dl:          {de:'⬇ server.py (181KB)',en:'⬇ server.py (181KB)',es:'⬇ server.py (181KB)',ru:'⬇ server.py (181KB)',pt:'⬇ server.py (181KB)'},
  web_btn_install:     {de:'📖 Installations-Guide',en:'📖 Installation Guide',es:'📖 Guía de Instalación',ru:'📖 Руководство',pt:'📖 Guia de Instalação'},
};

/* ════════════════════════════════════════════════════════════
   TREVLIX i18n Engine
   ════════════════════════════════════════════════════════════ */

  /* ── REGISTRATION ── */
  reg_title:        {de:'Account erstellen',en:'Create Account',es:'Crear cuenta',ru:'Создать аккаунт',pt:'Criar conta'},
  reg_username:     {de:'Benutzername',en:'Username',es:'Usuario',ru:'Имя пользователя',pt:'Nome de usuário'},
  reg_password:     {de:'Passwort',en:'Password',es:'Contraseña',ru:'Пароль',pt:'Senha'},
  reg_password2:    {de:'Passwort bestätigen',en:'Confirm Password',es:'Confirmar contraseña',ru:'Подтвердить пароль',pt:'Confirmar senha'},
  reg_submit:       {de:'Account erstellen →',en:'Create Account →',es:'Crear cuenta →',ru:'Создать аккаунт →',pt:'Criar conta →'},
  reg_login_link:   {de:'Bereits ein Konto? Anmelden',en:'Already have an account? Login',es:'¿Ya tienes cuenta? Iniciar sesión',ru:'Уже есть аккаунт? Войти',pt:'Já tem conta? Entrar'},
  reg_err_exists:   {de:'Benutzername bereits vergeben.',en:'Username already taken.',es:'Nombre de usuario ya existe.',ru:'Имя уже занято.',pt:'Nome de usuário já existe.'},
  reg_err_pw:       {de:'Passwort zu kurz (min. 8 Zeichen).',en:'Password too short (min. 8 chars).',es:'Contraseña muy corta (mín. 8).',ru:'Пароль слишком короткий.',pt:'Senha muito curta (mín. 8).'},
  reg_err_match:    {de:'Passwörter stimmen nicht überein.',en:'Passwords do not match.',es:'Las contraseñas no coinciden.',ru:'Пароли не совпадают.',pt:'As senhas não coincidem.'},

  /* ── ADMIN PANEL ── */
  admin_title:      {de:'Admin-Panel',en:'Admin Panel',es:'Panel de administración',ru:'Панель администратора',pt:'Painel Admin'},
  admin_users:      {de:'Nutzerverwaltung',en:'User Management',es:'Gestión de usuarios',ru:'Управление пользователями',pt:'Gestão de utilizadores'},
  admin_create_user:{de:'Nutzer erstellen',en:'Create User',es:'Crear usuario',ru:'Создать пользователя',pt:'Criar utilizador'},
  admin_bot_config: {de:'Bot-Konfiguration',en:'Bot Configuration',es:'Configuración del bot',ru:'Настройки бота',pt:'Configuração do bot'},
  admin_sys_status: {de:'System-Status',en:'System Status',es:'Estado del sistema',ru:'Статус системы',pt:'Estado do sistema'},
  admin_reg_enabled:{de:'Registrierung erlaubt',en:'Registration enabled',es:'Registro habilitado',ru:'Регистрация включена',pt:'Registro habilitado'},

  /* ── INSTALL / DONATION (Website) ── */
  web_donate_title: {de:'Die KI wird durch Spenden trainiert',en:'AI is trained through donations',es:'La IA se entrena con donaciones',ru:'ИИ обучается на пожертвования',pt:'IA treinada com doações'},
  web_donate_sub:   {de:'TREVLIX bleibt 100% kostenlos. Spenden helfen, bessere KI-Modelle zu trainieren.',en:'TREVLIX stays 100% free. Donations help train better AI models.',es:'TREVLIX sigue siendo 100% gratuito. Las donaciones ayudan a entrenar mejores modelos de IA.',ru:'TREVLIX остаётся 100% бесплатным. Пожертвования помогают обучать лучшие ИИ-модели.',pt:'TREVLIX permanece 100% gratuito. Doações ajudam a treinar modelos de IA melhores.'},
  web_donate_usdt:  {de:'USDT Spendenaddressen',en:'USDT Donation Addresses',es:'Direcciones de donación USDT',ru:'Адреса для пожертвований USDT',pt:'Endereços de doação USDT'},
  web_install_sh:   {de:'install.sh — Automatisch installieren',en:'install.sh — Auto Install',es:'install.sh — Instalación automática',ru:'install.sh — Автоустановка',pt:'install.sh — Instalar automaticamente'},
  web_install_one:  {de:'Ein-Zeilen-Install:',en:'One-line install:',es:'Instalación en una línea:',ru:'Установка в одну строку:',pt:'Instalação em uma linha:'},
  web_docs_link:    {de:'Dokumentation',en:'Documentation',es:'Documentación',ru:'Документация',pt:'Documentação'},
  web_donate_link:  {de:'Spenden',en:'Donate',es:'Donar',ru:'Пожертвовать',pt:'Doar'},

  /* ── ROLE LABELS ── */
  role_admin:       {de:'Admin',en:'Admin',es:'Admin',ru:'Админ',pt:'Admin'},
  role_user:        {de:'Nutzer',en:'User',es:'Usuario',ru:'Пользователь',pt:'Utilizador'},

  /* ── FEATURE IMPORTANCE ── */
  fi_title:         {de:'Feature Importance',en:'Feature Importance',es:'Importancia de características',ru:'Важность признаков',pt:'Importância das características'},
  fi_strat_weights: {de:'Strategie-Gewichte',en:'Strategy Weights',es:'Pesos de estrategia',ru:'Веса стратегий',pt:'Pesos das estratégias'},

  /* ── MARKOWITZ ── */
  markowitz_title:  {de:'Markowitz Optimierung',en:'Markowitz Optimization',es:'Optimización de Markowitz',ru:'Оптимизация Марковица',pt:'Otimização de Markowitz'},
  markowitz_run:    {de:'Optimieren',en:'Optimize',es:'Optimizar',ru:'Оптимизировать',pt:'Otimizar'},

  /* ── COPY-TRADING ── */
  copy_title:       {de:'Copy-Trading',en:'Copy Trading',es:'Copy Trading',ru:'Копитрейдинг',pt:'Copy Trading'},
  copy_register:    {de:'+ Follower hinzufügen',en:'+ Add Follower',es:'+ Añadir seguidor',ru:'+ Добавить подписчика',pt:'+ Adicionar seguidor'},
  copy_test:        {de:'Test-Signal',en:'Test Signal',es:'Señal de prueba',ru:'Тестовый сигнал',pt:'Sinal de teste'},

  /* ── PINE SCRIPT ── */
  pine_title:       {de:'Pine Script Export',en:'Pine Script Export',es:'Exportar Pine Script',ru:'Экспорт Pine Script',pt:'Exportar Pine Script'},
  pine_download:    {de:'⬇ Pine Script herunterladen',en:'⬇ Download Pine Script',es:'⬇ Descargar Pine Script',ru:'⬇ Скачать Pine Script',pt:'⬇ Baixar Pine Script'},

  /* ── KEYBOARD SHORTCUTS ── */
  shortcuts_title:  {de:'Tastenkürzel',en:'Keyboard Shortcuts',es:'Atajos de teclado',ru:'Горячие клавиши',pt:'Atalhos de teclado'},



  /* ── MULTI-EXCHANGE ── */
  nav_exchanges:      {de:'Exchanges',en:'Exchanges',es:'Exchanges',ru:'Биржи',pt:'Exchanges'},
  mex_total:          {de:'Gesamt-Portfolio',en:'Combined Portfolio',es:'Cartera combinada',ru:'Общий портфель',pt:'Portfólio combinado'},
  mex_active:         {de:'Exchanges aktiv',en:'Exchanges active',es:'Exchanges activas',ru:'Бирж активно',pt:'Exchanges ativas'},
  mex_setup_keys:     {de:'API-Keys einrichten',en:'Set up API Keys',es:'Configurar claves API',ru:'Настроить API-ключи',pt:'Configurar chaves API'},
  mex_save_keys:      {de:'Speichern & Aktivieren',en:'Save & Enable',es:'Guardar y activar',ru:'Сохранить и включить',pt:'Salvar e ativar'},
  mex_close_pos:      {de:'Position schließen',en:'Close Position',es:'Cerrar posición',ru:'Закрыть позицию',pt:'Fechar posição'},
  mex_all_trades:     {de:'Alle Trades (Exchange-übergreifend)',en:'All Trades (Cross-Exchange)',es:'Todos los trades (cross-exchange)',ru:'Все сделки (все биржи)',pt:'Todas as trades (multi-exchange)'},
  mex_inactive:       {de:'INAKTIV',en:'INACTIVE',es:'INACTIVO',ru:'НЕАКТИВНА',pt:'INATIVA'},
  mex_configured:     {de:'KONFIGURIERT',en:'CONFIGURED',es:'CONFIGURADA',ru:'НАСТРОЕНА',pt:'CONFIGURADA'},
  mex_active_label:   {de:'AKTIV',en:'ACTIVE',es:'ACTIVA',ru:'АКТИВНА',pt:'ATIVA'},


  /* ── SHARED AI ── */
  shared_ai_title:     {de:'Globales KI-Modell',en:'Global AI Model',es:'Modelo IA global',ru:'Глобальная модель ИИ',pt:'Modelo IA global'},
  shared_ai_version:   {de:'Version',en:'Version',es:'Versión',ru:'Версия',pt:'Versão'},
  shared_ai_sync:      {de:'Synchronisiert',en:'In sync',es:'Sincronizado',ru:'Синхронизировано',pt:'Sincronizado'},
  shared_ai_outdated:  {de:'Update verfügbar',en:'Update available',es:'Actualización disponible',ru:'Доступно обновление',pt:'Atualização disponível'},
  shared_ai_train:     {de:'Globales Training starten',en:'Start global training',es:'Iniciar entrenamiento global',ru:'Запустить глобальное обучение',pt:'Iniciar treinamento global'},
  shared_ai_contrib:   {de:'Training-Beiträge',en:'Training Contributions',es:'Contribuciones al entrenamiento',ru:'Вклад в обучение',pt:'Contribuições de treino'},
  shared_ai_samples:   {de:'Gesamt-Samples',en:'Total Samples',es:'Muestras totales',ru:'Всего образцов',pt:'Amostras totais'},
  shared_ai_model_hist:{de:'Modell-Versionen',en:'Model History',es:'Historial de modelos',ru:'История моделей',pt:'Histórico de modelos'},
  shared_ai_no_model:  {de:'Kein Modell verfügbar — Admin muss erst trainieren',en:'No model available — admin must train first',es:'Sin modelo — el administrador debe entrenar primero',ru:'Нет модели — администратор должен сначала обучить',pt:'Sem modelo — o administrador deve treinar primeiro'},
  shared_ai_by:        {de:'trainiert von',en:'trained by',es:'entrenado por',ru:'обучен',pt:'treinado por'},


  /* ── 10 NEW IMPROVEMENTS ── */
  nav_risk:           {de:'Risiko',en:'Risk',es:'Riesgo',ru:'Риск',pt:'Risco'},
  audit_title:        {de:'Audit-Log',en:'Audit Log',es:'Registro de auditoría',ru:'Журнал аудита',pt:'Log de auditoria'},
  grid_title:         {de:'Grid-Trading',en:'Grid Trading',es:'Trading en cuadrícula',ru:'Сеточная торговля',pt:'Grid Trading'},
  grid_create:        {de:'Grid erstellen',en:'Create Grid',es:'Crear cuadrícula',ru:'Создать сетку',pt:'Criar grade'},
  monte_title:        {de:'Monte-Carlo-Simulation',en:'Monte Carlo Simulation',es:'Simulación Monte Carlo',ru:'Симуляция Монте-Карло',pt:'Simulação Monte Carlo'},
  monte_run:          {de:'Simulation starten',en:'Run Simulation',es:'Iniciar simulación',ru:'Запустить симуляцию',pt:'Iniciar simulação'},
  tg_title:           {de:'Telegram-Benachrichtigungen',en:'Telegram Notifications',es:'Notificaciones Telegram',ru:'Уведомления Telegram',pt:'Notificações Telegram'},
  funding_title:      {de:'Funding Rates',en:'Funding Rates',es:'Tasas de financiación',ru:'Ставки финансирования',pt:'Taxas de financiamento'},
  cooldown_title:     {de:'Symbol-Sperren',en:'Symbol Cooldowns',es:'Bloqueos de símbolos',ru:'Блокировки символов',pt:'Bloqueios de símbolos'},
  break_even_title:   {de:'Break-Even Stop-Loss',en:'Break-Even Stop-Loss',es:'Stop-Loss Break-Even',ru:'Break-Even Стоп-Лосс',pt:'Stop-Loss Break-Even'},
  ip_whitelist_title: {de:'IP-Whitelist',en:'IP Whitelist',es:'Lista blanca de IPs',ru:'Белый список IP',pt:'Lista branca de IPs'},
  news_filter_title:  {de:'News-Sentiment-Filter',en:'News Sentiment Filter',es:'Filtro de sentimiento de noticias',ru:'Фильтр настроений новостей',pt:'Filtro de sentimento de notícias'},
  fa_2fa_title:       {de:'Zwei-Faktor-Auth',en:'Two-Factor Auth',es:'Autenticación de dos factores',ru:'Двухфакторная аутентификация',pt:'Autenticação de dois fatores'},
  auto_retrain_label: {de:'Auto-Retrain aktiv',en:'Auto-retrain active',es:'Auto-reentrenamiento activo',ru:'Авто-переобучение активно',pt:'Auto-retraining ativo'},
  monte_var:          {de:'Value at Risk (95%)',en:'Value at Risk (95%)',es:'Valor en riesgo (95%)',ru:'VaR (95%)',pt:'Valor em risco (95%)'},
  monte_prob_profit:  {de:'Profit-Wahrscheinlichkeit',en:'Profit Probability',es:'Probabilidad de ganancia',ru:'Вероятность прибыли',pt:'Probabilidade de lucro'},

const QI18n = {
  lang: localStorage.getItem('trevlix_lang') || 'de',

  t(key) {
    const entry = QT[key];
    if (!entry) return key;
    return entry[this.lang] || entry['de'] || key;
  },

  setLang(lang) {
    this.lang = lang;
    localStorage.setItem('trevlix_lang', lang);
    this.applyAll();
    document.documentElement.lang = lang;
  },

  applyAll() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const txt = this.t(key);
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = txt;
      } else {
        el.textContent = txt;
      }
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      el.innerHTML = this.t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = this.t(el.dataset.i18nTitle);
    });
    // Update switcher highlight
    document.querySelectorAll('.lang-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.lang === this.lang);
    });
  },

  renderSwitcher(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = Object.entries(QLANG_FLAGS).map(([code, flag]) =>
      `<button class="lang-btn${this.lang === code ? ' active' : ''}" data-lang="${code}"
         onclick="QI18n.setLang('${code}')" title="${QLANG_NAMES[code]}">${flag} <span>${code.toUpperCase()}</span></button>`
    ).join('');
  },

  init(switcherId) {
    this.renderSwitcher(switcherId || 'langSwitcher');
    this.applyAll();
  }
};
