/* ═══════════════════════════════════════════════════════════
   TREVLIX v1.5.3 – Static Page i18n
   Languages: de | en | es | ru | pt
   Features:
     - localStorage language persistence
     - Browser language auto-detection
     - data-i18n / data-i18n-html attribute system
     - Language switcher injected into nav
     - Cross-page language sync via storage event
   ═══════════════════════════════════════════════════════════ */

const PAGE_LANGS = ['de','en','es','ru','pt'];
const PAGE_LANG_NAMES = {de:'Deutsch',en:'English',es:'Español',ru:'Русский',pt:'Português'};
const PAGE_LANG_FLAGS = {de:'🇩🇪',en:'🇺🇸',es:'🇪🇸',ru:'🇷🇺',pt:'🇧🇷'};

const PT = {
  /* ── SHARED NAV / GLOBAL ── */
  skip_to_content:     {de:'Zum Inhalt springen',en:'Skip to content',es:'Saltar al contenido',ru:'К содержимому',pt:'Ir para o conteúdo'},
  nav_home:            {de:'Home',en:'Home',es:'Inicio',ru:'Главная',pt:'Início'},
  nav_features:        {de:'Features',en:'Features',es:'Funciones',ru:'Функции',pt:'Funcionalidades'},
  nav_strategies:      {de:'Strategien',en:'Strategies',es:'Estrategias',ru:'Стратегии',pt:'Estratégias'},
  nav_api:             {de:'API',en:'API',es:'API',ru:'API',pt:'API'},
  nav_installation:    {de:'Installation',en:'Installation',es:'Instalación',ru:'Установка',pt:'Instalação'},
  nav_faq:             {de:'FAQ',en:'FAQ',es:'FAQ',ru:'FAQ',pt:'FAQ'},
  nav_dashboard:       {de:'Dashboard',en:'Dashboard',es:'Dashboard',ru:'Дашборд',pt:'Dashboard'},
  nav_download:        {de:'Download',en:'Download',es:'Descargar',ru:'Скачать',pt:'Baixar'},
  nav_changelog:       {de:'Changelog',en:'Changelog',es:'Changelog',ru:'История изменений',pt:'Changelog'},
  nav_roadmap:         {de:'Roadmap',en:'Roadmap',es:'Hoja de Ruta',ru:'Дорожная карта',pt:'Roteiro'},
  nav_about:           {de:'Über uns',en:'About',es:'Acerca de',ru:'О нас',pt:'Sobre'},

  /* ── SHARED FOOTER ── */
  footer_product:      {de:'Produkt',en:'Product',es:'Producto',ru:'Продукт',pt:'Produto'},
  footer_resources:    {de:'Ressourcen',en:'Resources',es:'Recursos',ru:'Ресурсы',pt:'Recursos'},
  footer_security:     {de:'Sicherheit',en:'Security',es:'Seguridad',ru:'Безопасность',pt:'Segurança'},
  footer_copyright:    {de:'Open Source, MIT Lizenz',en:'Open Source, MIT License',es:'Código Abierto, Licencia MIT',ru:'Открытый код, MIT Лицензия',pt:'Código Aberto, Licença MIT'},
  footer_paper:        {de:'Paper Trading empfohlen',en:'Paper Trading recommended',es:'Paper Trading recomendado',ru:'Бумажная торговля рекомендуется',pt:'Paper Trading recomendado'},
  footer_gh_star:      {de:'Star auf GitHub',en:'Star on GitHub',es:'Destacar en GitHub',ru:'Поставить звезду на GitHub',pt:'Marcar com estrela no GitHub'},

  /* ══════════════════════════════════════════════════════════
     ABOUT PAGE
  ══════════════════════════════════════════════════════════ */
  about_h1:            {de:'Über TREVLIX',en:'About TREVLIX',es:'Sobre TREVLIX',ru:'О TREVLIX',pt:'Sobre o TREVLIX'},
  about_subtitle:      {de:'Open Source Algorithmic Trading Intelligence — von der Community, für die Community',en:'Open Source Algorithmic Trading Intelligence — by the community, for the community',es:'Inteligencia de Trading Algorítmico Open Source — de la comunidad, para la comunidad',ru:'Алгоритмический торговый интеллект с открытым кодом — от сообщества, для сообщества',pt:'Inteligência de Trading Algorítmico Open Source — pela comunidade, para a comunidade'},
  about_mission:       {de:'Mission',en:'Mission',es:'Misión',ru:'Миссия',pt:'Missão'},
  about_mission_txt:   {de:'TREVLIX wurde entwickelt, um professionelle Krypto-Trading-Technologie für jeden zugänglich zu machen. Während kommerzielle Bots hunderte Euro pro Monat kosten, ist TREVLIX vollständig Open Source und kostenlos. Unser Ziel: Die beste selbst-gehostete Trading-KI, die ständig dazulernt.',en:'TREVLIX was developed to make professional crypto trading technology accessible to everyone. While commercial bots cost hundreds of euros per month, TREVLIX is completely open source and free. Our goal: the best self-hosted trading AI that continuously learns.',es:'TREVLIX fue desarrollado para hacer accesible la tecnología profesional de trading de criptomonedas para todos. Mientras los bots comerciales cuestan cientos de euros al mes, TREVLIX es completamente open source y gratuito. Nuestro objetivo: la mejor IA de trading autoalojada que aprende continuamente.',ru:'TREVLIX разработан для того, чтобы сделать профессиональные технологии криптотрейдинга доступными для всех. Тогда как коммерческие боты стоят сотни евро в месяц, TREVLIX полностью с открытым кодом и бесплатен. Наша цель: лучший самостоятельно размещённый торговый ИИ, который постоянно обучается.',pt:'O TREVLIX foi desenvolvido para tornar a tecnologia profissional de trading de criptomoedas acessível a todos. Enquanto bots comerciais custam centenas de euros por mês, o TREVLIX é completamente open source e gratuito. Nosso objetivo: a melhor IA de trading auto-hospedada que aprende continuamente.'},
  about_tech_stack:    {de:'Technologie-Stack',en:'Technology Stack',es:'Stack Tecnológico',ru:'Технологический стек',pt:'Stack Tecnológico'},
  about_tech_desc:     {de:'TREVLIX nutzt moderne, bewährte Technologien für maximale Performance und Zuverlässigkeit.',en:'TREVLIX uses modern, proven technologies for maximum performance and reliability.',es:'TREVLIX usa tecnologías modernas y probadas para máximo rendimiento y fiabilidad.',ru:'TREVLIX использует современные, проверенные технологии для максимальной производительности и надёжности.',pt:'O TREVLIX usa tecnologias modernas e comprovadas para máximo desempenho e confiabilidade.'},
  about_backend:       {de:'Backend',en:'Backend',es:'Backend',ru:'Бэкенд',pt:'Backend'},
  about_ai_ml:         {de:'KI / Machine Learning',en:'AI / Machine Learning',es:'IA / Machine Learning',ru:'ИИ / Машинное обучение',pt:'IA / Machine Learning'},
  about_infra:         {de:'Infrastructure',en:'Infrastructure',es:'Infraestructura',ru:'Инфраструктура',pt:'Infraestrutura'},
  about_contribute:    {de:'Mitmachen (Contributing)',en:'Contributing',es:'Contribuir',ru:'Участие в разработке',pt:'Contribuir'},
  about_contribute_txt:{de:'TREVLIX lebt von der Community. Jeder Beitrag — ob Code, Dokumentation, Bugfixes oder Feature-Requests — ist willkommen!',en:'TREVLIX thrives on community contributions. Every contribution — whether code, documentation, bug fixes, or feature requests — is welcome!',es:'TREVLIX vive de la comunidad. ¡Toda contribución — ya sea código, documentación, correcciones o solicitudes de funciones — es bienvenida!',ru:'TREVLIX живёт благодаря сообществу. Каждый вклад — код, документация, исправления или запросы — приветствуется!',pt:'O TREVLIX vive da comunidade. Toda contribuição — seja código, documentação, correções ou solicitações — é bem-vinda!'},
  about_how_contribute:{de:'So kannst du beitragen:',en:'How to contribute:',es:'Cómo contribuir:',ru:'Как внести вклад:',pt:'Como contribuir:'},
  about_step1:         {de:'Forke das Repository auf GitHub',en:'Fork the repository on GitHub',es:'Haz un fork del repositorio en GitHub',ru:'Сделайте форк репозитория на GitHub',pt:'Faça um fork do repositório no GitHub'},
  about_step2:         {de:'Erstelle einen Feature-Branch: <code>git checkout -b feat/mein-feature</code>',en:'Create a feature branch: <code>git checkout -b feat/my-feature</code>',es:'Crea una rama: <code>git checkout -b feat/mi-funcion</code>',ru:'Создайте ветку: <code>git checkout -b feat/моя-функция</code>',pt:'Crie um branch: <code>git checkout -b feat/minha-funcao</code>'},
  about_step3:         {de:'Schreibe Tests für deine Änderungen',en:'Write tests for your changes',es:'Escribe pruebas para tus cambios',ru:'Напишите тесты для ваших изменений',pt:'Escreva testes para suas alterações'},
  about_step4:         {de:'Stelle sicher, dass <code>make test</code> und <code>make lint</code> bestehen',en:'Make sure <code>make test</code> and <code>make lint</code> pass',es:'Asegúrate de que <code>make test</code> y <code>make lint</code> pasen',ru:'Убедитесь, что <code>make test</code> и <code>make lint</code> проходят',pt:'Certifique-se de que <code>make test</code> e <code>make lint</code> passem'},
  about_step5:         {de:'Erstelle einen Pull Request mit ausführlicher Beschreibung',en:'Create a Pull Request with a detailed description',es:'Crea un Pull Request con una descripción detallada',ru:'Создайте Pull Request с подробным описанием',pt:'Crie um Pull Request com descrição detalhada'},
  about_license:       {de:'Lizenz',en:'License',es:'Licencia',ru:'Лицензия',pt:'Licença'},
  about_license_txt:   {de:'TREVLIX ist lizenziert unter der <strong>MIT License</strong>. Du darfst die Software frei nutzen, kopieren, modifizieren, zusammenfügen, veröffentlichen, verteilen, unterlizenzieren und/oder verkaufen &mdash; unter Beibehaltung des Copyright-Hinweises.',en:'TREVLIX is licensed under the <strong>MIT License</strong>. You may freely use, copy, modify, merge, publish, distribute, sublicense, and/or sell the software &mdash; while retaining the copyright notice.',es:'TREVLIX está licenciado bajo la <strong>Licencia MIT</strong>. Puedes usar, copiar, modificar, fusionar, publicar, distribuir, sublicenciar y/o vender el software libremente &mdash; manteniendo el aviso de copyright.',ru:'TREVLIX распространяется под <strong>MIT License</strong>. Вы можете свободно использовать, копировать, изменять, объединять, публиковать, распространять, сублицензировать и/или продавать программное обеспечение &mdash; при сохранении уведомления об авторских правах.',pt:'O TREVLIX está licenciado sob a <strong>MIT License</strong>. Você pode usar, copiar, modificar, mesclar, publicar, distribuir, sublicenciar e/ou vender o software livremente &mdash; mantendo o aviso de direitos autorais.'},
  about_links:         {de:'Links',en:'Links',es:'Enlases',ru:'Ссылки',pt:'Links'},
  stat_modules:        {de:'Module',en:'Modules',es:'Módulos',ru:'Модулей',pt:'Módulos'},
  stat_strategies:     {de:'Strategien',en:'Strategies',es:'Estrategias',ru:'Стратегий',pt:'Estratégias'},
  stat_exchanges:      {de:'Exchanges',en:'Exchanges',es:'Exchanges',ru:'Бирж',pt:'Exchanges'},
  stat_ai_features:    {de:'KI-Features',en:'AI Features',es:'Funciones IA',ru:'ИИ-функций',pt:'Funções IA'},
  stat_languages:      {de:'Sprachen',en:'Languages',es:'Idiomas',ru:'Языков',pt:'Idiomas'},
  stat_open_source:    {de:'Open Source',en:'Open Source',es:'Código Abierto',ru:'Открытый код',pt:'Código Aberto'},
  about_comment_clone: {de:'# Repository klonen und einrichten',en:'# Clone and set up repository',es:'# Clonar y configurar el repositorio',ru:'# Клонирование и настройка репозитория',pt:'# Clonar e configurar o repositório'},

  /* ══════════════════════════════════════════════════════════
     FAQ PAGE
  ══════════════════════════════════════════════════════════ */
  faq_h1:           {de:'Häufig gestellte Fragen',en:'Frequently Asked Questions',es:'Preguntas Frecuentes',ru:'Часто задаваемые вопросы',pt:'Perguntas Frequentes'},
  faq_subtitle:     {de:'Antworten auf die wichtigsten Fragen rund um TREVLIX',en:'Answers to the most important questions about TREVLIX',es:'Respuestas a las preguntas más importantes sobre TREVLIX',ru:'Ответы на самые важные вопросы о TREVLIX',pt:'Respostas para as perguntas mais importantes sobre o TREVLIX'},
  faq_count:        {de:'18 Fragen &middot; Klicke auf eine Frage zum Aufklappen',en:'18 Questions &middot; Click a question to expand',es:'18 Preguntas &middot; Haz clic en una pregunta para expandir',ru:'18 Вопросов &middot; Нажмите на вопрос для раскрытия',pt:'18 Perguntas &middot; Clique numa pergunta para expandir'},
  faq_cat_general:  {de:'Allgemein',en:'General',es:'General',ru:'Общее',pt:'Geral'},
  faq_cat_trading:  {de:'Trading & Strategie',en:'Trading & Strategy',es:'Trading y Estrategia',ru:'Трейдинг и стратегия',pt:'Trading & Estratégia'},
  faq_cat_ai:       {de:'KI & Machine Learning',en:'AI & Machine Learning',es:'IA y Machine Learning',ru:'ИИ и машинное обучение',pt:'IA & Machine Learning'},
  faq_cat_install:  {de:'Installation & Betrieb',en:'Installation & Operations',es:'Instalación y Operación',ru:'Установка и эксплуатация',pt:'Instalação & Operação'},
  faq_cat_security: {de:'Sicherheit & Risiko',en:'Security & Risk',es:'Seguridad y Riesgo',ru:'Безопасность и риски',pt:'Segurança & Risco'},
  faq_q1:  {de:'Was ist TREVLIX?',en:'What is TREVLIX?',es:'¿Qué es TREVLIX?',ru:'Что такое TREVLIX?',pt:'O que é o TREVLIX?'},
  faq_a1:  {de:'TREVLIX ist ein Open-Source Algorithmic Trading Bot für Kryptowährungen. Er nutzt ein 4-Modell KI-Ensemble mit 9 Voting-Strategien, um automatisch Kauf- und Verkaufsentscheidungen zu treffen.',en:'TREVLIX is an open-source algorithmic trading bot for cryptocurrencies. It uses a 4-model AI ensemble with 9 voting strategies to automatically make buy and sell decisions.',es:'TREVLIX es un bot de trading algorítmico open source para criptomonedas. Utiliza un ensemble de 4 modelos de IA con 9 estrategias de votación para tomar decisiones automáticas de compra y venta.',ru:'TREVLIX — торговый бот с открытым кодом для криптовалют. Он использует ансамбль из 4 моделей ИИ с 9 стратегиями голосования для автоматического принятия торговых решений.',pt:'O TREVLIX é um bot de trading algorítmico open source para criptomoedas. Usa um ensemble de 4 modelos de IA com 9 estratégias de votação para tomar decisões automáticas de compra e venda.'},
  faq_q2:  {de:'Ist TREVLIX kostenlos?',en:'Is TREVLIX free?',es:'¿Es TREVLIX gratuito?',ru:'TREVLIX бесплатный?',pt:'O TREVLIX é gratuito?'},
  faq_a2:  {de:'Ja, TREVLIX ist vollständig Open Source unter der MIT-Lizenz. Du kannst es kostenlos nutzen, modifizieren und weiterverbreiten. Es gibt keine versteckten Kosten oder Premium-Versionen.',en:'Yes, TREVLIX is fully open source under the MIT license. You can use, modify, and redistribute it for free. There are no hidden costs or premium versions.',es:'Sí, TREVLIX es completamente open source bajo la licencia MIT. Puedes usarlo, modificarlo y redistribuirlo de forma gratuita. No hay costos ocultos ni versiones premium.',ru:'Да, TREVLIX полностью с открытым кодом под лицензией MIT. Вы можете использовать, изменять и распространять его бесплатно. Нет скрытых затрат или премиум-версий.',pt:'Sim, o TREVLIX é completamente open source sob a licença MIT. Você pode usá-lo, modificá-lo e redistribuí-lo gratuitamente. Não há custos ocultos ou versões premium.'},
  faq_q3:  {de:'Welche Exchanges werden unterstützt?',en:'Which exchanges are supported?',es:'¿Qué exchanges son compatibles?',ru:'Какие биржи поддерживаются?',pt:'Quais exchanges são suportadas?'},
  faq_a3:  {de:'Aktuell werden 8 Exchanges unterstützt: <strong>Crypto.com</strong>, <strong>Binance</strong>, <strong>Bybit</strong>, <strong>OKX</strong>, <strong>KuCoin</strong>, <strong>Kraken</strong>, <strong>Huobi</strong> und <strong>Coinbase</strong>. Die Integration erfolgt über die CCXT-Bibliothek, sodass weitere Exchanges leicht hinzugefügt werden können.',en:'Currently 8 exchanges are supported: <strong>Crypto.com</strong>, <strong>Binance</strong>, <strong>Bybit</strong>, <strong>OKX</strong>, <strong>KuCoin</strong>, <strong>Kraken</strong>, <strong>Huobi</strong> and <strong>Coinbase</strong>. Integration is via the CCXT library, so additional exchanges can easily be added.',es:'Actualmente se admiten 8 exchanges: <strong>Crypto.com</strong>, <strong>Binance</strong>, <strong>Bybit</strong>, <strong>OKX</strong>, <strong>KuCoin</strong>, <strong>Kraken</strong>, <strong>Huobi</strong> y <strong>Coinbase</strong>. La integración es a través de la biblioteca CCXT, por lo que se pueden agregar más exchanges fácilmente.',ru:'Поддерживается 8 бирж: <strong>Crypto.com</strong>, <strong>Binance</strong>, <strong>Bybit</strong>, <strong>OKX</strong>, <strong>KuCoin</strong>, <strong>Kraken</strong>, <strong>Huobi</strong> и <strong>Coinbase</strong>. Интеграция через библиотеку CCXT, дополнительные биржи добавляются легко.',pt:'São suportadas 8 exchanges: <strong>Crypto.com</strong>, <strong>Binance</strong>, <strong>Bybit</strong>, <strong>OKX</strong>, <strong>KuCoin</strong>, <strong>Kraken</strong>, <strong>Huobi</strong> e <strong>Coinbase</strong>. A integração é via biblioteca CCXT, então outras exchanges podem ser adicionadas facilmente.'},
  faq_q4:  {de:'Kann ich TREVLIX auf einem Raspberry Pi betreiben?',en:'Can I run TREVLIX on a Raspberry Pi?',es:'¿Puedo ejecutar TREVLIX en una Raspberry Pi?',ru:'Можно ли запустить TREVLIX на Raspberry Pi?',pt:'Posso executar o TREVLIX num Raspberry Pi?'},
  faq_a4:  {de:'Ja! TREVLIX läuft auf Raspberry Pi 4 (4GB+ RAM empfohlen). Die LSTM/TensorFlow-Komponente ist optional und kann bei begrenztem RAM deaktiviert werden. Das 3-Modell-Ensemble (ohne LSTM) läuft problemlos auf dem Pi.',en:'Yes! TREVLIX runs on Raspberry Pi 4 (4GB+ RAM recommended). The LSTM/TensorFlow component is optional and can be disabled on limited RAM. The 3-model ensemble (without LSTM) runs fine on the Pi.',es:'¡Sí! TREVLIX funciona en Raspberry Pi 4 (se recomiendan 4GB+ de RAM). El componente LSTM/TensorFlow es opcional y se puede desactivar con RAM limitada. El ensemble de 3 modelos (sin LSTM) funciona bien en la Pi.',ru:'Да! TREVLIX работает на Raspberry Pi 4 (рекомендуется 4 ГБ+ ОЗУ). Компонент LSTM/TensorFlow опционален и может быть отключён. Ансамбль из 3 моделей (без LSTM) работает на Pi.',pt:'Sim! O TREVLIX funciona no Raspberry Pi 4 (4GB+ RAM recomendados). O LSTM/TensorFlow é opcional e pode ser desativado. O ensemble de 3 modelos (sem LSTM) funciona bem no Pi.'},
  faq_q5:  {de:'Wie funktioniert das Voting-System?',en:'How does the voting system work?',es:'¿Cómo funciona el sistema de votación?',ru:'Как работает система голосования?',pt:'Como funciona o sistema de votação?'},
  faq_a5:  {de:'9 technische Strategien (EMA, RSI, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP) stimmen gleichzeitig ab. Jede gibt BUY, SELL oder HOLD. Überwiegt ein Signal den konfigurierbaren Schwellenwert (Standard: 5/9), wird ein Trade ausgeführt. Die KI gewichtet die Stimmen dynamisch basierend auf historischer Performance.',en:'9 technical strategies (EMA, RSI, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP) vote simultaneously. Each gives BUY, SELL or HOLD. If a signal exceeds the configurable threshold (default: 5/9), a trade is executed. The AI dynamically weights votes based on historical performance.',es:'9 estrategias técnicas (EMA, RSI, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP) votan simultáneamente. Cada una da BUY, SELL o HOLD. Si una señal supera el umbral configurable (predeterminado: 5/9), se ejecuta un trade. La IA pondera los votos dinámicamente según el rendimiento histórico.',ru:'9 технических стратегий (EMA, RSI, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP) голосуют одновременно. Каждая даёт BUY, SELL или HOLD. Если сигнал превышает порог (по умолчанию: 5/9), совершается сделка. ИИ динамически взвешивает голоса на основе исторической производительности.',pt:'9 estratégias técnicas (EMA, RSI, MACD, Bollinger, Volume, OBV, ROC, Ichimoku, VWAP) votam simultaneamente. Cada uma dá BUY, SELL ou HOLD. Se um sinal excede o limite (padrão: 5/9), um trade é executado. A IA pondera os votos dinamicamente com base no desempenho histórico.'},
  faq_q6:  {de:'Was ist Paper Trading?',en:'What is Paper Trading?',es:'¿Qué es el Paper Trading?',ru:'Что такое бумажная торговля?',pt:'O que é Paper Trading?'},
  faq_a6:  {de:'Paper Trading ist ein Simulationsmodus, der echten Handel nachahmt, aber kein echtes Geld einsetzt. Es ist <strong>dringend empfohlen</strong>, mindestens 30 Tage im Paper Trading Modus zu testen, bevor man mit echtem Geld handelt. Setze <code>PAPER_TRADING=true</code> in der <code>.env</code>-Datei.',en:'Paper Trading is a simulation mode that mimics real trading without using real money. It is <strong>strongly recommended</strong> to test for at least 30 days in Paper Trading mode before trading with real money. Set <code>PAPER_TRADING=true</code> in the <code>.env</code> file.',es:'El Paper Trading es un modo de simulación que imita el trading real sin usar dinero real. Se <strong>recomienda encarecidamente</strong> probar al menos 30 días en modo Paper Trading. Establece <code>PAPER_TRADING=true</code> en el archivo <code>.env</code>.',ru:'Бумажная торговля — режим симуляции без реальных денег. <strong>Настоятельно рекомендуется</strong> тестировать не менее 30 дней перед торговлей реальными деньгами. Установите <code>PAPER_TRADING=true</code> в файле <code>.env</code>.',pt:'Paper Trading é um modo de simulação sem dinheiro real. É <strong>fortemente recomendado</strong> testar pelo menos 30 dias antes de negociar com dinheiro real. Defina <code>PAPER_TRADING=true</code> no arquivo <code>.env</code>.'},
  faq_q7:  {de:'Kann TREVLIX auch Short-Selling?',en:'Can TREVLIX do short selling?',es:'¿Puede TREVLIX hacer short selling?',ru:'Поддерживает ли TREVLIX короткие продажи?',pt:'O TREVLIX suporta short selling?'},
  faq_a7:  {de:'Ja, auf Exchanges die Futures/Margin unterstützen (Binance Futures, Bybit). Der Bear-Regime KI-Modell ist speziell für Short-Positionen optimiert. Short-Selling wird nur aktiviert, wenn der Markt in einem Abwärtstrend ist und die KI eine hohe Konfidenz hat.',en:'Yes, on exchanges that support futures/margin (Binance Futures, Bybit). The Bear-Regime AI model is specifically optimized for short positions. Short selling is only activated when the market is in a downtrend and the AI has high confidence.',es:'Sí, en exchanges que admiten futuros/margen (Binance Futures, Bybit). El modelo IA de régimen bajista está optimizado para posiciones cortas. El short selling solo se activa en tendencia bajista con alta confianza de la IA.',ru:'Да, на биржах с фьючерсами/маржой (Binance Futures, Bybit). Модель ИИ медвежьего режима оптимизирована для коротких позиций. Шорт активируется только при нисходящем тренде и высокой уверенности ИИ.',pt:'Sim, em exchanges com futuros/margem (Binance Futures, Bybit). O modelo IA de regime bear é otimizado para posições curtas. O short selling é ativado apenas em tendência de baixa com alta confiança da IA.'},
  faq_q8:  {de:'Wie hoch ist die erwartete Rendite?',en:'What is the expected return?',es:'¿Cuál es el rendimiento esperado?',ru:'Какова ожидаемая доходность?',pt:'Qual é o retorno esperado?'},
  faq_a8:  {de:'Renditen hängen stark von Marktbedingungen, Konfiguration und Exchange ab. TREVLIX gibt keine Renditeversprechen. In Backtests zeigen die Strategien typischerweise Win-Rates von 55–65%. <strong>Vergangene Performance garantiert keine zukünftigen Ergebnisse.</strong> Starte immer mit Paper Trading!',en:'Returns depend heavily on market conditions, configuration, and exchange. TREVLIX makes no return guarantees. In backtests, strategies typically show win rates of 55–65%. <strong>Past performance does not guarantee future results.</strong> Always start with Paper Trading!',es:'Los rendimientos dependen de las condiciones del mercado, configuración y exchange. TREVLIX no promete rendimientos. Los backtests muestran win rates del 55–65%. <strong>El rendimiento pasado no garantiza resultados futuros.</strong> ¡Siempre empieza con Paper Trading!',ru:'Доходность зависит от рыночных условий, конфигурации и биржи. TREVLIX не гарантирует доходность. Бэктесты показывают win-rate 55–65%. <strong>Прошлые результаты не гарантируют будущих.</strong> Всегда начинайте с бумажной торговли!',pt:'Os retornos dependem das condições de mercado, configuração e exchange. O TREVLIX não garante retornos. Em backtests, win rates tipicamente 55–65%. <strong>Desempenho passado não garante resultados futuros.</strong> Sempre comece com Paper Trading!'},
  faq_q9:  {de:'Was ist der Circuit Breaker?',en:'What is the Circuit Breaker?',es:'¿Qué es el Circuit Breaker?',ru:'Что такое автовыключатель?',pt:'O que é o Circuit Breaker?'},
  faq_a9:  {de:'Der Circuit Breaker ist ein Sicherheitsmechanismus, der den Handel automatisch pausiert, wenn zu viele aufeinanderfolgende Verluste auftreten oder das tägliche Verlustlimit erreicht wird. Er schützt vor unkontrollierten Verlusten in volatilen Märkten und kann in den Einstellungen konfiguriert werden.',en:'The Circuit Breaker is a safety mechanism that automatically pauses trading when too many consecutive losses occur or the daily loss limit is reached. It protects against uncontrolled losses in volatile markets and can be configured in the settings.',es:'El Circuit Breaker es un mecanismo de seguridad que pausa automáticamente el trading cuando hay demasiadas pérdidas consecutivas o se alcanza el límite de pérdidas diarias. Protege contra pérdidas descontroladas en mercados volátiles.',ru:'Автовыключатель — механизм безопасности, который автоматически приостанавливает торговлю при слишком большом числе последовательных убытков или достижении дневного лимита. Защищает от неконтролируемых потерь.',pt:'O Circuit Breaker é um mecanismo de segurança que pausa automaticamente o trading quando há muitas perdas consecutivas ou o limite de perda diária é atingido. Protege contra perdas descontroladas em mercados voláteis.'},
  faq_q10: {de:'Wie lernt die KI?',en:'How does the AI learn?',es:'¿Cómo aprende la IA?',ru:'Как обучается ИИ?',pt:'Como a IA aprende?'},
  faq_a10: {de:'Die KI lernt aus vergangenen Trades. Nach 30+ Trades beginnt das Training, danach wird nach jedem 5. Trade neu trainiert. Das System nutzt Walk-Forward Validation, um Overfitting zu vermeiden. Vier Modelle (Global, Bull-Regime, Bear-Regime, LSTM) bilden ein Ensemble für robustere Vorhersagen.',en:'The AI learns from past trades. After 30+ trades training begins, then retrains after every 5th trade. The system uses Walk-Forward Validation to avoid overfitting. Four models (Global, Bull-Regime, Bear-Regime, LSTM) form an ensemble for robust predictions.',es:'La IA aprende de los trades pasados. Después de 30+ trades comienza el entrenamiento, luego se reentrena cada 5 trades. El sistema usa Walk-Forward Validation para evitar sobreajuste. Cuatro modelos forman un ensemble.',ru:'ИИ учится на прошлых сделках. После 30+ сделок начинается обучение, потом переобучение каждые 5 сделок. Система использует Walk-Forward Validation. Четыре модели образуют ансамбль.',pt:'A IA aprende com trades passados. Após 30+ trades o treinamento começa, depois retreina a cada 5º trade. O sistema usa Walk-Forward Validation. Quatro modelos formam um ensemble.'},
  faq_q11: {de:'Brauche ich eine GPU für die KI?',en:'Do I need a GPU for the AI?',es:'¿Necesito una GPU para la IA?',ru:'Нужна ли GPU для ИИ?',pt:'Preciso de uma GPU para a IA?'},
  faq_a11: {de:'Nein, die Modelle (Random Forest, XGBoost, LightGBM, CatBoost) laufen effizient auf CPU. Das optionale LSTM-Modell profitiert von einer GPU, ist aber auch ohne GPU nutzbar. Für die meisten Nutzer reicht ein Standard-Server oder Raspberry Pi 4.',en:'No, the models (Random Forest, XGBoost, LightGBM, CatBoost) run efficiently on CPU. The optional LSTM model benefits from a GPU but is usable without one. A standard server or Raspberry Pi 4 is sufficient for most users.',es:'No, los modelos (Random Forest, XGBoost, LightGBM, CatBoost) funcionan eficientemente en CPU. El modelo LSTM opcional se beneficia de una GPU pero también funciona sin ella.',ru:'Нет, модели (Random Forest, XGBoost, LightGBM, CatBoost) работают на CPU. Опциональная LSTM выигрывает от GPU, но работает и без неё.',pt:'Não, os modelos (Random Forest, XGBoost, LightGBM, CatBoost) funcionam na CPU. O LSTM opcional beneficia de GPU mas funciona sem ela.'},
  faq_q12: {de:'Was sind die 31 Features des ML-Modells?',en:'What are the 31 ML model features?',es:'¿Cuáles son los 31 features del modelo ML?',ru:'Каковы 31 признак модели ML?',pt:'Quais são os 31 features do modelo ML?'},
  faq_a12: {de:'Die Features umfassen: 7 Strategie-Votes, RSI normalisiert, Stochastic RSI, Bollinger %B und Width, MACD-Histogramm (Vorzeichen + Steigung), Volume Ratio, ATR%, EMA-Alignment, Preis vs. EMA21, ROC-10, Bull/Bear-Flag, Stunde (Sinus/Cosinus-codiert), Vote-Konsensus und die jüngste Win-Rate der letzten 10 Trades.',en:'Features include: 7 strategy votes, normalized RSI, Stochastic RSI, Bollinger %B and Width, MACD histogram (sign + slope), Volume Ratio, ATR%, EMA alignment, Price vs. EMA21, ROC-10, Bull/Bear flag, Hour (sine/cosine encoded), vote consensus, and recent win rate of the last 10 trades.',es:'Los features incluyen: 7 votos de estrategia, RSI normalizado, Stochastic RSI, Bollinger %B y Width, histograma MACD, Volume Ratio, ATR%, alineación EMA, Price vs. EMA21, ROC-10, flag Bull/Bear, hora codificada y tasa de éxito reciente.',ru:'Признаки: 7 голосов стратегий, RSI, Stochastic RSI, Bollinger %B и Width, гистограмма MACD, Volume Ratio, ATR%, выравнивание EMA, цена vs. EMA21, ROC-10, Bull/Bear флаг, час (sin/cos), консенсус и win-rate.',pt:'Features: 7 votos de estratégia, RSI normalizado, Stochastic RSI, Bollinger %B e Width, histograma MACD, Volume Ratio, ATR%, alinhamento EMA, Preço vs. EMA21, ROC-10, flag Bull/Bear, hora codificada e win rate recente.'},
  faq_q13: {de:'Welche Systemvoraussetzungen hat TREVLIX?',en:'What are the system requirements?',es:'¿Cuáles son los requisitos del sistema?',ru:'Каковы системные требования?',pt:'Quais são os requisitos de sistema?'},
  faq_a13: {de:'Python 3.9+ (empfohlen 3.11), MySQL 8.0+, 2 GB RAM (4 GB mit LSTM), Ubuntu 20.04+/Debian 11+/macOS/Windows (WSL). Docker wird für die einfachste Installation empfohlen.',en:'Python 3.9+ (3.11 recommended), MySQL 8.0+, 2 GB RAM (4 GB with LSTM), Ubuntu 20.04+/Debian 11+/macOS/Windows (WSL). Docker is recommended for the easiest installation.',es:'Python 3.9+ (se recomienda 3.11), MySQL 8.0+, 2 GB RAM (4 GB con LSTM), Ubuntu 20.04+/Debian 11+/macOS/Windows (WSL). Docker es recomendado.',ru:'Python 3.9+ (рекомендуется 3.11), MySQL 8.0+, 2 ГБ ОЗУ (4 ГБ с LSTM), Ubuntu 20.04+/Debian 11+/macOS/Windows (WSL). Docker рекомендуется.',pt:'Python 3.9+ (3.11 recomendado), MySQL 8.0+, 2 GB RAM (4 GB com LSTM), Ubuntu 20.04+/Debian 11+/macOS/Windows (WSL). Docker recomendado.'},
  faq_q14: {de:'Wie update ich TREVLIX?',en:'How do I update TREVLIX?',es:'¿Cómo actualizo TREVLIX?',ru:'Как обновить TREVLIX?',pt:'Como atualizo o TREVLIX?'},
  faq_a14: {de:'TREVLIX hat ein eingebautes GitHub Auto-Update System. Im Dashboard kann ein Update mit einem Klick gestartet werden. Alternativ: <code>cd trevlix &amp;&amp; git pull origin main</code>. Bei Docker: <code>docker compose pull &amp;&amp; docker compose up -d</code>.',en:'TREVLIX has a built-in GitHub auto-update system. In the dashboard, an update can be started with one click. Alternatively: <code>cd trevlix &amp;&amp; git pull origin main</code>. For Docker: <code>docker compose pull &amp;&amp; docker compose up -d</code>.',es:'TREVLIX tiene un sistema de actualización automática de GitHub integrado. En el dashboard se puede actualizar con un clic. Alternativa: <code>cd trevlix &amp;&amp; git pull origin main</code>. Docker: <code>docker compose pull &amp;&amp; docker compose up -d</code>.',ru:'TREVLIX имеет встроенную систему автообновления с GitHub. В дашборде обновление запускается одним кликом. Или: <code>cd trevlix &amp;&amp; git pull origin main</code>. Docker: <code>docker compose pull &amp;&amp; docker compose up -d</code>.',pt:'O TREVLIX tem sistema de atualização automática do GitHub. No dashboard atualiza com um clique. Ou: <code>cd trevlix &amp;&amp; git pull origin main</code>. Docker: <code>docker compose pull &amp;&amp; docker compose up -d</code>.'},
  faq_q15: {de:'Wie sichere ich meine API-Keys?',en:'How do I secure my API keys?',es:'¿Cómo protejo mis claves API?',ru:'Как защитить API-ключи?',pt:'Como protejo minhas chaves API?'},
  faq_a15: {de:'API-Keys werden automatisch mit Fernet-Verschlüsselung in der Datenbank gespeichert. Setze <code>ENCRYPTION_KEY</code> in der <code>.env</code>-Datei (wird beim Setup generiert). Nutze IP-Whitelisting bei deiner Exchange und beschränke die API-Berechtigungen auf das Minimum (nur Trading, kein Withdrawal).',en:'API keys are stored with Fernet encryption in the database. Set <code>ENCRYPTION_KEY</code> in the <code>.env</code> file (generated during setup). Use IP whitelisting on your exchange and restrict API permissions to the minimum (trading only, no withdrawal).',es:'Las claves API se almacenan con cifrado Fernet. Establece <code>ENCRYPTION_KEY</code> en el <code>.env</code>. Usa lista blanca de IP en tu exchange y restringe permisos al mínimo (solo trading, sin retiro).',ru:'API-ключи хранятся с Fernet-шифрованием. Установите <code>ENCRYPTION_KEY</code> в <code>.env</code>. Используйте IP-вайтлистинг на бирже и ограничьте права API (только торговля, без вывода).',pt:'As chaves API são armazenadas com criptografia Fernet. Defina <code>ENCRYPTION_KEY</code> no <code>.env</code>. Use IP whitelisting na exchange e restrinja permissões ao mínimo (apenas trading).'},
  faq_q16: {de:'Ist TREVLIX sicher?',en:'Is TREVLIX secure?',es:'¿Es TREVLIX seguro?',ru:'Безопасен ли TREVLIX?',pt:'O TREVLIX é seguro?'},
  faq_a16: {de:'TREVLIX implementiert umfangreiche Sicherheitsmaßnahmen: JWT-Authentifizierung, 2FA/TOTP, bcrypt-Passwort-Hashing, Fernet-API-Key-Verschlüsselung, Rate-Limiting, CORS-Schutz und IP-Whitelisting. Alle Aktionen werden im Audit-Log protokolliert. Für maximale Sicherheit nutze HTTPS via Nginx.',en:'TREVLIX implements extensive security measures: JWT authentication, 2FA/TOTP, bcrypt password hashing, Fernet API key encryption, rate limiting, CORS protection, and IP whitelisting. All actions are logged in the audit log. For maximum security, use HTTPS via Nginx.',es:'TREVLIX implementa amplias medidas de seguridad: autenticación JWT, 2FA/TOTP, hashing bcrypt, cifrado Fernet, rate limiting, protección CORS e IP whitelisting. Todo se registra en el audit log.',ru:'TREVLIX реализует: JWT-аутентификацию, 2FA/TOTP, bcrypt, Fernet-шифрование, rate limiting, CORS, IP-вайтлистинг. Все действия в журнале аудита. Используйте HTTPS через Nginx.',pt:'O TREVLIX implementa: autenticação JWT, 2FA/TOTP, bcrypt, criptografia Fernet, rate limiting, CORS, IP whitelisting. Tudo logado no audit log. Use HTTPS via Nginx para máxima segurança.'},
  faq_q17: {de:'Kann ich Geld verlieren?',en:'Can I lose money?',es:'¿Puedo perder dinero?',ru:'Могу ли я потерять деньги?',pt:'Posso perder dinheiro?'},
  faq_a17: {de:'<strong>Ja.</strong> Krypto-Trading birgt immer Verlustrisiken. TREVLIX minimiert Risiken durch Circuit Breaker, Stop-Loss, und tägliche Verlustlimits — aber kein System kann Verluste vollständig verhindern. Investiere nur, was du dir leisten kannst zu verlieren. Starte immer mit Paper Trading!',en:'<strong>Yes.</strong> Crypto trading always carries the risk of loss. TREVLIX minimizes risks through circuit breakers, stop-losses, and daily loss limits — but no system can completely prevent losses. Only invest what you can afford to lose. Always start with Paper Trading!',es:'<strong>Sí.</strong> El trading de criptomonedas siempre conlleva riesgos. TREVLIX minimiza riesgos con circuit breakers, stop-loss y límites diarios, pero ningún sistema puede prevenir todas las pérdidas. ¡Invierte solo lo que puedas perder!',ru:'<strong>Да.</strong> Криптотрейдинг всегда несёт риски потерь. TREVLIX минимизирует их через автовыключатели, стоп-лоссы и дневные лимиты — но ни одна система не гарантирует отсутствие потерь. Инвестируйте только то, что можете позволить потерять.',pt:'<strong>Sim.</strong> O trading de criptomoedas sempre carrega risco de perda. O TREVLIX minimiza riscos com circuit breakers, stop-losses e limites diários — mas nenhum sistema elimina perdas. Invista apenas o que pode perder.'},
  faq_q18: {de:'Wo bekomme ich Hilfe?',en:'Where can I get help?',es:'¿Dónde puedo obtener ayuda?',ru:'Где получить помощь?',pt:'Onde posso obter ajuda?'},
  faq_a18: {de:'Bei Problemen oder Fragen: (1) Prüfe die <a href="INSTALLATION.html">Installationsanleitung</a>, (2) Erstelle ein <a href="https://github.com/itsamemedev/Trevlix/issues" target="_blank" rel="noopener">GitHub Issue</a>, (3) Tritt dem Discord-Server bei. Für Sicherheitsprobleme nutze die verantwortungsvolle Offenlegung über GitHub Security Advisories.',en:'For issues or questions: (1) Check the <a href="INSTALLATION.html">installation guide</a>, (2) Create a <a href="https://github.com/itsamemedev/Trevlix/issues" target="_blank" rel="noopener">GitHub Issue</a>, (3) Join the Discord server. For security issues, use responsible disclosure via GitHub Security Advisories.',es:'Para problemas: (1) Revisa la <a href="INSTALLATION.html">guía de instalación</a>, (2) Crea un <a href="https://github.com/itsamemedev/Trevlix/issues" target="_blank" rel="noopener">GitHub Issue</a>, (3) Únete a Discord. Para problemas de seguridad, usa GitHub Security Advisories.',ru:'При проблемах: (1) <a href="INSTALLATION.html">Руководство по установке</a>, (2) <a href="https://github.com/itsamemedev/Trevlix/issues" target="_blank" rel="noopener">GitHub Issue</a>, (3) Discord-сервер. Для проблем безопасности — GitHub Security Advisories.',pt:'Para problemas: (1) <a href="INSTALLATION.html">Guia de instalação</a>, (2) <a href="https://github.com/itsamemedev/Trevlix/issues" target="_blank" rel="noopener">GitHub Issue</a>, (3) Discord. Para segurança, use GitHub Security Advisories.'},

  /* ══════════════════════════════════════════════════════════
     STRATEGIES PAGE
  ══════════════════════════════════════════════════════════ */
  strat_h1:           {de:'Trading-Strategien',en:'Trading Strategies',es:'Estrategias de Trading',ru:'Торговые стратегии',pt:'Estratégias de Trading'},
  strat_subtitle:     {de:'TREVLIX nutzt 9 Voting-Strategien, die gemeinsam über Trades abstimmen. Jede Strategie gibt ein Signal: <strong style="color:var(--jade)">BUY</strong>, <strong style="color:var(--red)">SELL</strong> oder <strong style="color:var(--sub)">HOLD</strong>.',en:'TREVLIX uses 9 voting strategies that collectively vote on trades. Each strategy gives a signal: <strong style="color:var(--jade)">BUY</strong>, <strong style="color:var(--red)">SELL</strong> or <strong style="color:var(--sub)">HOLD</strong>.',es:'TREVLIX utiliza 9 estrategias de votación que votan colectivamente sobre los trades. Cada estrategia da: <strong style="color:var(--jade)">BUY</strong>, <strong style="color:var(--red)">SELL</strong> o <strong style="color:var(--sub)">HOLD</strong>.',ru:'TREVLIX использует 9 стратегий голосования. Каждая даёт: <strong style="color:var(--jade)">BUY</strong>, <strong style="color:var(--red)">SELL</strong> или <strong style="color:var(--sub)">HOLD</strong>.',pt:'O TREVLIX usa 9 estratégias de votação. Cada uma dá: <strong style="color:var(--jade)">BUY</strong>, <strong style="color:var(--red)">SELL</strong> ou <strong style="color:var(--sub)">HOLD</strong>.'},
  strat_breadcrumb:   {de:'Trading-Strategien',en:'Trading Strategies',es:'Estrategias de Trading',ru:'Торговые стратегии',pt:'Estratégias de Trading'},
  strat_ensemble_h:   {de:'Voting-Ensemble System',en:'Voting Ensemble System',es:'Sistema de Votación Ensemble',ru:'Система голосования Ensemble',pt:'Sistema de Votação Ensemble'},
  strat_ensemble_p1:  {de:'Alle 9 Strategien stimmen gleichzeitig ab. Überwiegen die BUY-Stimmen den konfigurierbaren Schwellenwert (Standard: 5 von 9), wird ein Kauf-Signal erzeugt. Die KI gewichtet die Stimmen dynamisch basierend auf der historischen Trefferquote jeder Strategie.',en:'All 9 strategies vote simultaneously. If BUY votes exceed the configurable threshold (default: 5 of 9), a buy signal is generated. The AI dynamically weights votes based on each strategy\'s historical accuracy.',es:'Las 9 estrategias votan simultáneamente. Si los votos BUY superan el umbral configurable (predeterminado: 5 de 9), se genera una señal de compra. La IA pondera los votos dinámicamente según el historial de cada estrategia.',ru:'Все 9 стратегий голосуют одновременно. Если голоса BUY превышают настраиваемый порог (по умолчанию: 5 из 9), генерируется сигнал покупки. ИИ динамически взвешивает голоса на основе исторической точности каждой стратегии.',pt:'As 9 estratégias votam simultaneamente. Se os votos BUY excedem o limiar configurável (padrão: 5 de 9), um sinal de compra é gerado. A IA pondera os votos com base na precisão histórica de cada estratégia.'},
  strat_ensemble_p2:  {de:'Beispiel: Wenn 6 Strategien <strong style="color:var(--jade)">BUY</strong> signalisieren und 3 <strong style="color:var(--sub)">HOLD</strong> &mdash; wird ein Trade ausgeführt.',en:'Example: When 6 strategies signal <strong style="color:var(--jade)">BUY</strong> and 3 signal <strong style="color:var(--sub)">HOLD</strong> &mdash; a trade is executed.',es:'Ejemplo: Cuando 6 estrategias señalan <strong style="color:var(--jade)">BUY</strong> y 3 señalan <strong style="color:var(--sub)">HOLD</strong> &mdash; se ejecuta un trade.',ru:'Пример: если 6 стратегий сигнализируют <strong style="color:var(--jade)">BUY</strong>, а 3 — <strong style="color:var(--sub)">HOLD</strong> &mdash; сделка выполняется.',pt:'Exemplo: quando 6 estratégias sinalizam <strong style="color:var(--jade)">BUY</strong> e 3 sinalizam <strong style="color:var(--sub)">HOLD</strong> &mdash; um trade é executado.'},
  strat_weight_label: {de:'Gewichtung:',en:'Weight:',es:'Peso:',ru:'Вес:',pt:'Peso:'},
  strat_in_ensemble:  {de:'im KI-Ensemble',en:'in AI Ensemble',es:'en el Ensemble IA',ru:'в ансамбле ИИ',pt:'no Ensemble IA'},

  /* ══════════════════════════════════════════════════════════
     API DOCS PAGE
  ══════════════════════════════════════════════════════════ */
  api_h1:              {de:'API Dokumentation',en:'API Documentation',es:'Documentación API',ru:'Документация API',pt:'Documentação API'},
  api_subtitle:        {de:'Vollständige REST API Referenz für TREVLIX v1.0.4. Alle Endpunkte erfordern JWT-Authentifizierung.',en:'Complete REST API reference for TREVLIX v1.0.4. All endpoints require JWT authentication.',es:'Referencia completa de la API REST para TREVLIX v1.0.4. Todos los endpoints requieren autenticación JWT.',ru:'Полная справочная информация по REST API для TREVLIX v1.0.4. Все эндпоинты требуют JWT-аутентификации.',pt:'Referência completa da API REST para TREVLIX v1.0.4. Todos os endpoints requerem autenticação JWT.'},
  api_auth_h:          {de:'Authentifizierung',en:'Authentication',es:'Autenticación',ru:'Аутентификация',pt:'Autenticação'},
  api_endpoints_h:     {de:'Endpunkte',en:'Endpoints',es:'Endpoints',ru:'Эндпоинты',pt:'Endpoints'},
  api_method:          {de:'Methode',en:'Method',es:'Método',ru:'Метод',pt:'Método'},
  api_endpoint:        {de:'Endpunkt',en:'Endpoint',es:'Endpoint',ru:'Эндпоинт',pt:'Endpoint'},
  api_description:     {de:'Beschreibung',en:'Description',es:'Descripción',ru:'Описание',pt:'Descrição'},

  /* ══════════════════════════════════════════════════════════
     CHANGELOG PAGE
  ══════════════════════════════════════════════════════════ */
  changelog_h1:        {de:'Changelog',en:'Changelog',es:'Registro de Cambios',ru:'История изменений',pt:'Registo de Alterações'},
  changelog_subtitle:  {de:'Alle Versionen, neuen Features und Bugfixes auf einen Blick.',en:'All versions, new features, and bug fixes at a glance.',es:'Todas las versiones, nuevas funciones y correcciones de errores de un vistazo.',ru:'Все версии, новые функции и исправления ошибок одним взглядом.',pt:'Todas as versões, novos recursos e correções de bugs em resumo.'},
  changelog_tag_latest:{de:'Aktuell',en:'Latest',es:'Actual',ru:'Текущая',pt:'Atual'},
  changelog_tag_stable:{de:'Stabil',en:'Stable',es:'Estable',ru:'Стабильная',pt:'Estável'},
  changelog_added:     {de:'Hinzugefügt',en:'Added',es:'Añadido',ru:'Добавлено',pt:'Adicionado'},
  changelog_fixed:     {de:'Behoben',en:'Fixed',es:'Corregido',ru:'Исправлено',pt:'Corrigido'},
  changelog_changed:   {de:'Geändert',en:'Changed',es:'Cambiado',ru:'Изменено',pt:'Alterado'},
  changelog_removed:   {de:'Entfernt',en:'Removed',es:'Eliminado',ru:'Удалено',pt:'Removido'},

  /* ══════════════════════════════════════════════════════════
     ROADMAP PAGE
  ══════════════════════════════════════════════════════════ */
  roadmap_h1:          {de:'Roadmap',en:'Roadmap',es:'Hoja de Ruta',ru:'Дорожная карта',pt:'Roteiro'},
  roadmap_subtitle:    {de:'Geplante Features und die Zukunft des TREVLIX Trading Bots.',en:'Planned features and the future of the TREVLIX Trading Bot.',es:'Funciones planificadas y el futuro del bot de trading TREVLIX.',ru:'Запланированные функции и будущее торгового бота TREVLIX.',pt:'Recursos planejados e o futuro do bot de trading TREVLIX.'},
  roadmap_done:        {de:'✅ Fertig',en:'✅ Done',es:'✅ Completado',ru:'✅ Готово',pt:'✅ Concluído'},
  roadmap_active:      {de:'🔄 In Arbeit',en:'🔄 In Progress',es:'🔄 En Progreso',ru:'🔄 В разработке',pt:'🔄 Em Progresso'},
  roadmap_planned:     {de:'📋 Geplant',en:'📋 Planned',es:'📋 Planificado',ru:'📋 Запланировано',pt:'📋 Planejado'},
  roadmap_future:      {de:'🔮 Zukunft',en:'🔮 Future',es:'🔮 Futuro',ru:'🔮 Будущее',pt:'🔮 Futuro'},

  /* ══════════════════════════════════════════════════════════
     SECURITY PAGE
  ══════════════════════════════════════════════════════════ */
  security_h1:         {de:'Sicherheitsleitfaden',en:'Security Guide',es:'Guía de Seguridad',ru:'Руководство по безопасности',pt:'Guia de Segurança'},
  security_subtitle:   {de:'Best Practices für die sichere Konfiguration und den Betrieb von TREVLIX.',en:'Best practices for the secure configuration and operation of TREVLIX.',es:'Mejores prácticas para la configuración segura y operación de TREVLIX.',ru:'Лучшие практики безопасной настройки и эксплуатации TREVLIX.',pt:'Melhores práticas para a configuração segura e operação do TREVLIX.'},
  security_critical:   {de:'KRITISCH',en:'CRITICAL',es:'CRÍTICO',ru:'КРИТИЧНО',pt:'CRÍTICO'},
  security_warn:       {de:'WARNUNG',en:'WARNING',es:'ADVERTENCIA',ru:'ПРЕДУПРЕЖДЕНИЕ',pt:'AVISO'},
  security_ok:         {de:'OK',en:'OK',es:'OK',ru:'OK',pt:'OK'},

  /* ══════════════════════════════════════════════════════════
     404 PAGE
  ══════════════════════════════════════════════════════════ */
  err404_title:        {de:'Seite nicht gefunden',en:'Page not found',es:'Página no encontrada',ru:'Страница не найдена',pt:'Página não encontrada'},
  err404_desc:         {de:'Die angeforderte Seite existiert nicht oder wurde verschoben. Kein Grund zur Panik &mdash; dein Portfolio ist sicher!',en:'The requested page does not exist or has been moved. No need to panic &mdash; your portfolio is safe!',es:'La página solicitada no existe o fue movida. ¡No hay razón para entrar en pánico &mdash; tu cartera está segura!',ru:'Запрошенная страница не существует или была перемещена. Нет причин паниковать &mdash; ваш портфель в безопасности!',pt:'A página solicitada não existe ou foi movida. Sem pânico &mdash; seu portfólio está seguro!'},
  err404_home:         {de:'Zur Startseite',en:'Go to Homepage',es:'Ir a Inicio',ru:'На главную',pt:'Ir para Início'},
  err404_dashboard:    {de:'Zum Dashboard',en:'Go to Dashboard',es:'Ir al Dashboard',ru:'К дашборду',pt:'Ir para Dashboard'},

  /* ══════════════════════════════════════════════════════════
     LOGIN PAGE
  ══════════════════════════════════════════════════════════ */
  login_h1:            {de:'Anmelden',en:'Login',es:'Iniciar sesión',ru:'Вход',pt:'Entrar'},
  login_subtitle:      {de:'Melde dich an, um auf das Dashboard zuzugreifen.',en:'Log in to access the dashboard.',es:'Inicia sesión para acceder al panel.',ru:'Войдите для доступа к панели управления.',pt:'Faça login para acessar o painel.'},
  login_username:      {de:'Benutzername',en:'Username',es:'Usuario',ru:'Имя пользователя',pt:'Nome de usuário'},
  login_password:      {de:'Passwort',en:'Password',es:'Contraseña',ru:'Пароль',pt:'Senha'},
  login_submit:        {de:'Anmelden →',en:'Login →',es:'Iniciar sesión →',ru:'Войти →',pt:'Entrar →'},
  login_register_link: {de:'Kein Konto? Registrieren',en:'No account? Register',es:'¿Sin cuenta? Registrarse',ru:'Нет аккаунта? Регистрация',pt:'Sem conta? Registrar'},
  login_2fa_label:     {de:'2FA-Code',en:'2FA Code',es:'Código 2FA',ru:'Код 2FA',pt:'Código 2FA'},
  login_2fa_placeholder:{de:'6-stelliger Code',en:'6-digit code',es:'Código de 6 dígitos',ru:'6-значный код',pt:'Código de 6 dígitos'},
  login_remember:      {de:'Angemeldet bleiben',en:'Remember me',es:'Recordarme',ru:'Запомнить меня',pt:'Lembrar-me'},
  login_forgot:        {de:'Passwort vergessen?',en:'Forgot password?',es:'¿Olvidaste la contraseña?',ru:'Забыли пароль?',pt:'Esqueceu a senha?'},

  /* ── AUTH MESSAGES (Static pages) ── */
  auth_login_success:       {de:'Erfolgreich angemeldet',en:'Successfully logged in',es:'Inicio de sesión exitoso',ru:'Успешный вход',pt:'Login realizado com sucesso'},
  auth_login_failed:        {de:'Anmeldung fehlgeschlagen',en:'Login failed',es:'Error de inicio de sesión',ru:'Ошибка входа',pt:'Falha no login'},
  auth_login_blocked:       {de:'Zu viele Anmeldeversuche. Bitte warte.',en:'Too many login attempts. Please wait.',es:'Demasiados intentos. Por favor, espera.',ru:'Слишком много попыток. Подождите.',pt:'Muitas tentativas. Por favor, aguarde.'},
  auth_session_expired:     {de:'Deine Sitzung ist abgelaufen. Bitte erneut anmelden.',en:'Your session has expired. Please log in again.',es:'Tu sesión ha expirado. Inicia sesión de nuevo.',ru:'Сессия истекла. Войдите снова.',pt:'Sua sessão expirou. Faça login novamente.'},
  auth_register_disabled:   {de:'Registrierung ist derzeit deaktiviert.',en:'Registration is currently disabled.',es:'El registro está desactivado actualmente.',ru:'Регистрация в настоящее время отключена.',pt:'O registro está desativado no momento.'},
  auth_logout:              {de:'Abmelden',en:'Logout',es:'Cerrar sesión',ru:'Выйти',pt:'Sair'},

  /* ── SHARED NAV (additional) ── */
  nav_login:           {de:'Anmelden',en:'Login',es:'Iniciar sesión',ru:'Войти',pt:'Entrar'},
  nav_register:        {de:'Registrieren',en:'Register',es:'Registrarse',ru:'Регистрация',pt:'Registrar'},
  nav_logout:          {de:'Abmelden',en:'Logout',es:'Cerrar sesión',ru:'Выйти',pt:'Sair'},
  nav_profile:         {de:'Profil',en:'Profile',es:'Perfil',ru:'Профиль',pt:'Perfil'},

  /* ── SHARED FOOTER (additional) ── */
  footer_legal:        {de:'Rechtliches',en:'Legal',es:'Legal',ru:'Правовая информация',pt:'Legal'},
  footer_privacy:      {de:'Datenschutz',en:'Privacy',es:'Privacidad',ru:'Конфиденциальность',pt:'Privacidade'},
  footer_terms:        {de:'Nutzungsbedingungen',en:'Terms of Use',es:'Términos de Uso',ru:'Условия использования',pt:'Termos de Uso'},
  footer_contact:      {de:'Kontakt',en:'Contact',es:'Contacto',ru:'Контакт',pt:'Contato'},
};

/* ──────────────────────────────────────────────────────────
   LANGUAGE PREFERENCE (localStorage + browser detection)
────────────────────────────────────────────────────────── */
function plGetLang() {
  try { return localStorage.getItem('trevlix_lang') || plDetectBrowserLang(); }
  catch(e) { return 'de'; }
}

function plDetectBrowserLang() {
  const code = (navigator.language || navigator.userLanguage || 'de').split('-')[0].toLowerCase();
  return PAGE_LANGS.includes(code) ? code : 'de';
}

function plSetLang(lang) {
  if (!PAGE_LANGS.includes(lang)) return;
  try { localStorage.setItem('trevlix_lang', lang); } catch(e){}
  plApplyLang(lang);
  document.documentElement.lang = lang;
  plUpdateSwitcher(lang);
  window.dispatchEvent(new CustomEvent('trevlix:langchange', {detail:{lang}}));
}

/* ──────────────────────────────────────────────────────────
   TRANSLATION LOOKUP
────────────────────────────────────────────────────────── */
function plT(key, lang) {
  const entry = PT[key];
  if (!entry) return null;
  return entry[lang] || entry['de'] || null;
}

/* ──────────────────────────────────────────────────────────
   APPLY TRANSLATIONS TO DOM
────────────────────────────────────────────────────────── */
function plApplyLang(lang) {
  // text content
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const val = plT(el.dataset.i18n, lang);
    if (val !== null) el.textContent = val;
  });
  // inner HTML (rich content with links / markup)
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const val = plT(el.dataset.i18nHtml, lang);
    if (val !== null) el.innerHTML = val;
  });
  // title attribute
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const val = plT(el.dataset.i18nTitle, lang);
    if (val !== null) el.title = val;
  });
  // aria-label
  document.querySelectorAll('[data-i18n-aria]').forEach(el => {
    const val = plT(el.dataset.i18nAria, lang);
    if (val !== null) el.setAttribute('aria-label', val);
  });
}

/* ──────────────────────────────────────────────────────────
   LANGUAGE SWITCHER (injected into .site-nav-right)
────────────────────────────────────────────────────────── */
function plInjectSwitcher() {
  const navRight = document.querySelector('.site-nav-right');
  if (!navRight || document.getElementById('plLangSwitcher')) return;

  const css = `
#plLangSwitcher{position:relative;display:flex;align-items:center;margin-right:4px}
#plLangBtn{background:none;border:1px solid rgba(255,255,255,.12);border-radius:6px;color:rgba(255,255,255,.5);font-family:var(--fm);font-size:11px;padding:5px 10px;cursor:pointer;display:flex;align-items:center;gap:5px;transition:.2s;white-space:nowrap;line-height:1}
#plLangBtn:hover{border-color:var(--jade);color:var(--jade)}
#plLangDropdown{display:none;position:absolute;top:calc(100% + 8px);right:0;background:#0a1210;border:1px solid rgba(255,255,255,.1);border-radius:10px;overflow:hidden;z-index:2000;min-width:140px;box-shadow:0 8px 32px rgba(0,0,0,.6)}
#plLangDropdown.open{display:block}
.pl-lang-item{display:flex;align-items:center;gap:10px;width:100%;padding:10px 14px;background:none;border:none;color:rgba(255,255,255,.55);font-family:var(--fm);font-size:12px;cursor:pointer;transition:.15s;text-align:left}
.pl-lang-item:hover{background:rgba(255,255,255,.04);color:#fff}
.pl-lang-item.active{color:var(--jade);background:rgba(0,255,136,.06)}
.pl-lang-flag{font-size:15px;line-height:1}
.pl-lang-caret{opacity:.4;font-size:9px}
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const wrapper = document.createElement('div');
  wrapper.id = 'plLangSwitcher';

  const btn = document.createElement('button');
  btn.id = 'plLangBtn';
  btn.setAttribute('aria-haspopup', 'listbox');
  btn.setAttribute('aria-expanded', 'false');
  btn.onclick = e => { e.stopPropagation(); plToggleDropdown(); };

  const dropdown = document.createElement('div');
  dropdown.id = 'plLangDropdown';
  dropdown.setAttribute('role', 'listbox');

  PAGE_LANGS.forEach(l => {
    const item = document.createElement('button');
    item.className = 'pl-lang-item';
    item.dataset.lang = l;
    item.setAttribute('role', 'option');
    item.innerHTML = `<span class="pl-lang-flag">${PAGE_LANG_FLAGS[l]}</span><span>${PAGE_LANG_NAMES[l]}</span>`;
    item.onclick = e => { e.stopPropagation(); plSetLang(l); plToggleDropdown(false); };
    dropdown.appendChild(item);
  });

  wrapper.appendChild(btn);
  wrapper.appendChild(dropdown);

  const mobileBtn = navRight.querySelector('.site-nav-mobile-btn');
  if (mobileBtn) navRight.insertBefore(wrapper, mobileBtn);
  else navRight.appendChild(wrapper);

  document.addEventListener('click', () => plToggleDropdown(false));
}

function plToggleDropdown(force) {
  const d = document.getElementById('plLangDropdown');
  const btn = document.getElementById('plLangBtn');
  if (!d) return;
  const open = force !== undefined ? force : !d.classList.contains('open');
  d.classList.toggle('open', open);
  if (btn) btn.setAttribute('aria-expanded', open);
}

function plUpdateSwitcher(lang) {
  const btn = document.getElementById('plLangBtn');
  if (btn) btn.innerHTML = `<span class="pl-lang-flag">${PAGE_LANG_FLAGS[lang]}</span> <span>${PAGE_LANG_NAMES[lang]}</span> <span class="pl-lang-caret">▼</span>`;
  document.querySelectorAll('.pl-lang-item').forEach(el => {
    el.classList.toggle('active', el.dataset.lang === lang);
  });
}

/* ──────────────────────────────────────────────────────────
   CROSS-PAGE LANGUAGE SYNC (storage event)
────────────────────────────────────────────────────────── */
window.addEventListener('storage', e => {
  if (e.key === 'trevlix_lang' && e.newValue && PAGE_LANGS.includes(e.newValue)) {
    plApplyLang(e.newValue);
    document.documentElement.lang = e.newValue;
    plUpdateSwitcher(e.newValue);
  }
});

/* ──────────────────────────────────────────────────────────
   INIT
────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  plInjectSwitcher();
  const lang = plGetLang();
  plApplyLang(lang);
  document.documentElement.lang = lang;
  plUpdateSwitcher(lang);
});
