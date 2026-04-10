// ── HTML-Escaping für sichere innerHTML-Nutzung ──────────────────────
function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
// JS-safe escaping for use in onclick="fn('${escJS(val)}')" attributes
function escJS(s){if(!s)return'';return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/</g,'\\x3c').replace(/>/g,'\\x3e');}

// ── Safe localStorage wrapper (handles private browsing) ─────────────
const _storage = {
  get(k){try{return localStorage.getItem(k);}catch(e){return null;}},
  set(k,v){try{localStorage.setItem(k,v);}catch(e){}},
  del(k){try{localStorage.removeItem(k);}catch(e){}}
};

// ── JWT Token (aus Cookie oder Session) ──────────────────────────────
let _jwtToken = (document.cookie.match(/(?:^|;\s*)token=([^;]*)/)||[])[1] || '';
const _csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

// [Socket.io Fix] Initiale State-Abfrage per HTTP, bevor WS verbunden ist
(async function _initState(){
  try {
    const r = await fetch('/api/v1/state', {credentials:'include'});
    if(r.ok){
      const d=await r.json();
      if(d&&d.running!==undefined) updateUI(d);
      if(d&&d.user_role) applyStateToRole(d);
    }
    refreshTradingInsights(true);
  } catch(e){ console.warn('Initial state fetch failed:', e); }
})();

const socket = TrevlixSocket.init({
  reconnectionAttempts: Infinity,
  reconnectionDelay: 2000,
  reconnectionDelayMax: 30000,
  timeout: 20000,
});
let portChart=null, hourChart=null, pnlChart=null, btChartInst=null;
let lastData=null, allTrades=[], tradeFilter='all';
let logEntries=[], logPaused=false, currentHmSort='change';
let wizStep=0, wizEx='cryptocom';

// ── Nav ──────────────────────────────────────────────────────────────
const _navHooks=[];
function onNav(fn){_navHooks.push(fn);}
function nav(id,el){
  if(id==='admin' && !document.body.classList.contains('is-admin')){
    toast('⛔ Admin-Bereich nur für Admins verfügbar.','warning');
    return;
  }
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('active'));
  const sec=document.getElementById('sec-'+id); if(sec) sec.classList.add('active');
  if(el) el.classList.add('active');
  if(id==='pos' && lastData) updateStats(lastData);
  if(id==='admin' && lastData?.ai) updateAI(lastData.ai);
  _navHooks.forEach(fn=>{try{fn(id);}catch(e){}});
  closeMobileNav();
  window.scrollTo({top:0,behavior:'smooth'});
}

// ── Mobile Nav Drawer ────────────────────────────────────────────────
function toggleMobileNav(){
  const overlay=document.getElementById('mobNavOverlay');
  const drawer=document.getElementById('mobNavDrawer');
  if(!overlay||!drawer) return;
  const isOpen=drawer.classList.contains('open');
  if(isOpen){closeMobileNav();return;}
  // Build drawer items from secondary nav buttons
  const items=document.querySelectorAll('.nb.nb-secondary');
  let html='<div class="drawer-handle"></div>';
  items.forEach(nb=>{
    if(nb.classList.contains('admin-only') && !document.body.classList.contains('is-admin')) return;
    const icon=nb.querySelector('.nb-icon')?.textContent||'';
    const label=nb.querySelector('[data-i18n]')?.textContent||'';
    const kbd=nb.querySelector('.nav-kbd')?.textContent||'';
    const isActive=nb.classList.contains('active');
    const oc=nb.getAttribute('onclick')||'';
    html+=`<div class="drawer-item${isActive?' active':''}" onclick="${oc}">
      <span class="di-icon">${icon}</span><span>${label}</span>
      ${kbd?'<span class="di-kbd">'+kbd+'</span>':''}
    </div>`;
  });
  drawer.innerHTML=html;
  overlay.classList.add('open');
  drawer.classList.add('open');
}
function closeMobileNav(){
  const overlay=document.getElementById('mobNavOverlay');
  const drawer=document.getElementById('mobNavDrawer');
  if(overlay) overlay.classList.remove('open');
  if(drawer) drawer.classList.remove('open');
}

// ── Format ───────────────────────────────────────────────────────────
const fmt=(n,d=2)=>Number(n||0).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct=n=>(n>=0?'+':'')+fmt(n)+'%';
const fmtS=(n,d=2)=>(n>=0?'+':'')+fmt(n,d);
const clr=n=>n>=0?'var(--green)':'var(--red)';

// ── Toast ────────────────────────────────────────────────────────────
function toast(msg, type='info'){
  const c=document.getElementById('toasts');
  if(!c) return;
  /* [Verbesserung #39] Max 5 Toasts gleichzeitig anzeigen */
  while(c.children.length >= 5){ c.removeChild(c.firstChild); }
  const t=document.createElement('div');
  t.className='toast '+type; t.textContent=msg;
  t.setAttribute('role','alert');
  c.appendChild(t); setTimeout(()=>t.remove(),3700);
}

// ── Log ──────────────────────────────────────────────────────────────
function addLog(msg, type='info', cat='system'){
  if(logPaused) return;
  logEntries.unshift({time:new Date().toTimeString().slice(0,8),msg,type,cat});
  logEntries=logEntries.slice(0,500);
  renderLog();
}
function renderLog(){
  const categories={All:logEntries,Trades:logEntries.filter(e=>e.cat==='trade'),
    Signals:logEntries.filter(e=>e.cat==='signal'),System:logEntries.filter(e=>e.cat==='system'),
    Ai:logEntries.filter(e=>e.cat==='ai'),Arb:logEntries.filter(e=>e.cat==='arb')};
  const icons={trade:'💰',signal:'📡',system:'⚙️',ai:'🧠',arb:'💹'};
  for(const[k,entries] of Object.entries(categories)){
    const el=document.getElementById('log'+k); if(!el) continue;
    const validTypes = new Set(['info','success','error','warning']);
    el.innerHTML=entries.slice(0,120).map(e=>`<div class="log-row ${validTypes.has(e.type)?e.type:'info'}">
      <span class="log-time">${esc(e.time)}</span>
      <span style="flex-shrink:0;width:14px;text-align:center">${icons[e.cat]||'·'}</span>
      <span class="log-msg">${esc(e.msg)}</span></div>`).join('')||'<div class="empty" style="padding:12px">'+QI18n.t('empty_log')+'</div>';
  }
}
function switchLog(tab,el){
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.log-panel').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  const p=document.getElementById('log'+tab); if(p) p.classList.add('active');
}
function clearLog(){ logEntries=[]; renderLog(); }
function pauseLog(){
  logPaused=!logPaused;
  const lpb=document.getElementById('logPauseBtn'); if(lpb) lpb.textContent=logPaused?'▶':'⏸';
}

// ── Charts init ──────────────────────────────────────────────────────
const cBase={responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(5,8,16,.95)',borderColor:'rgba(0,255,136,.2)',borderWidth:1,bodyColor:'#00ff88',bodyFont:{family:"'JetBrains Mono'"}}},
  scales:{x:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#2e3d5a',font:{family:"'JetBrains Mono'",size:8},maxTicksLimit:6}},
          y:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#2e3d5a',font:{family:"'JetBrains Mono'",size:8}}}}};
function initCharts(){
  // Destroy existing chart instances to prevent memory leak
  if(portChart){try{portChart.destroy();}catch(e){}} portChart=null;
  if(hourChart){try{hourChart.destroy();}catch(e){}} hourChart=null;
  if(pnlChart){try{pnlChart.destroy();}catch(e){}} pnlChart=null;

  const portEl=document.getElementById('portChart');
  const hourEl=document.getElementById('hourChart');
  const pnlEl=document.getElementById('pnlChart');
  if(portEl) portChart=new Chart(portEl,{type:'line',
    data:{labels:[],datasets:[{data:[],borderColor:'#00ff88',backgroundColor:'rgba(0,255,136,0.06)',borderWidth:2,fill:true,tension:.4,pointRadius:0}]},options:cBase});
  if(hourEl) hourChart=new Chart(hourEl,{type:'bar',
    data:{labels:Array.from({length:24},(_,i)=>i+'h'),datasets:[{data:Array(24).fill(0),backgroundColor:'rgba(0,255,136,.35)',borderRadius:3}]},options:cBase});
  if(pnlEl) pnlChart=new Chart(pnlEl,{type:'bar',
    data:{labels:[],datasets:[{data:[],backgroundColor:[],borderRadius:3}]},options:cBase});
}

// ── Main UI Update ───────────────────────────────────────────────────
// Header-Status-Chips: Exchange, API-Keys, LLM, Paper-Trading
const _SUPPORTED_EXCHANGES = ['binance','bybit','okx','kucoin','cryptocom'];
let _installedKeysCount = null;
async function _refreshInstalledKeys(){
  try{
    const res = await fetch('/api/v1/user/exchanges', {credentials:'same-origin'});
    if(!res.ok) return;
    const data = await res.json();
    const list = Array.isArray(data) ? data : (data.exchanges||data.items||[]);
    _installedKeysCount = list.filter(x => (x && (x.api_key || x.enabled))).length;
  }catch(_e){}
}
function _setChip(id, cls, value){
  const el = document.getElementById(id);
  if(!el) return;
  el.className = 'chip '+cls;
  const v = document.getElementById(id+'Val');
  if(v && value !== undefined) v.textContent = value;
}
function renderHeaderStatus(d){
  // Exchange + Verbindung
  const exName = (d.exchange||'—').toUpperCase();
  const connectedFlag = d.api && typeof d.api.connected === 'string'
    ? d.api.connected
    : (d.running ? '✅' : '⏸️');
  let exCls = 'chip--muted';
  if(connectedFlag.indexOf('✅')>=0) exCls='chip--ok';
  else if(connectedFlag.indexOf('⚠')>=0||connectedFlag.indexOf('❌')>=0) exCls='chip--err';
  _setChip('chipExchange', exCls, exName);
  const dot = document.getElementById('chipExchangeDot');
  if(dot) dot.setAttribute('data-state', exCls.replace('chip--',''));
  // LLM
  const llm = d.llm || {};
  const provider = llm.provider && llm.provider !== '—' ? llm.provider : null;
  let llmCls = 'chip--muted', llmVal = 'nicht konfiguriert';
  if(provider){
    llmVal = provider;
    const st = String(llm.status||'');
    if(st.indexOf('✅')>=0) llmCls='chip--ok';
    else if(st.indexOf('❌')>=0) llmCls='chip--err';
    else llmCls='chip--warn';
  }
  _setChip('chipLlm', llmCls, llmVal);
  // API-Keys installiert
  if(_installedKeysCount === null){
    _setChip('chipKeys', 'chip--muted', '…');
  }else{
    const n = _installedKeysCount, m = _SUPPORTED_EXCHANGES.length;
    const cls = n>0 ? 'chip--ok' : 'chip--warn';
    _setChip('chipKeys', cls, n+'/'+m);
  }
  // Paper-Trading-Badge
  const paper = d.paper_trading !== false;
  _setChip('chipPaper', paper?'chip--warn':'chip--err', paper?'Paper Trading':'LIVE Trading');
  // Trading-Algorithmen Status
  const tAlgo = d.trading_algorithms || {};
  if(tAlgo.configured){
    const aBuy = tAlgo.buy_win_rate||0;
    const aTotal = tAlgo.total_trades||0;
    const aLbl = aTotal>0 ? 'Aktiv ('+aBuy.toFixed(0)+'% WR)' : 'Konfiguriert';
    _setChip('chipAlgo', aTotal>0?'chip--ok':'chip--warn', aLbl);
  }else{
    _setChip('chipAlgo', 'chip--muted', 'nicht konfiguriert');
  }
}
// Initial beim Laden holen, dann alle 60s aktualisieren
_refreshInstalledKeys();
setInterval(_refreshInstalledKeys, 60000);

function updateUI(d){
  if(!d || typeof d !== 'object') return;
  try {
  lastData=d; allTrades=d.closed_trades||[];
  const _s = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
  // Header
  _s('hSub', (d.exchange||'TREVLIX').toUpperCase()+' · '+(d.paper_trading?'PAPER':'LIVE')+' · v'+(d.bot_version||'1.0.0'));
  try { renderHeaderStatus(d); } catch(_e){}
  // Hero
  const hValEl=document.getElementById('hVal');
  if(hValEl){hValEl.textContent=fmt(d.portfolio_value)+' USDT';}
  const r=d.return_pct||0, re=document.getElementById('hReturn');
  if(re){re.textContent=(r>=0?'▲ +':'▼ ')+fmt(Math.abs(r))+'%'; re.className='pill '+(r>=0?'up':'dn');}
  _s('hPnl', fmtS(d.total_pnl)+' USDT '+(QI18n.t('total_label')||'Gesamt'));
  // Status
  const b=document.getElementById('statusBadge'),t=document.getElementById('statusTxt');
  if(b&&t){
    if(d.paused){b.className='h-badge pause';t.textContent=QI18n.t('status_paused');}
    else if(d.running){b.className='h-badge run';t.textContent=QI18n.t('status_running');}
    else{b.className='h-badge stop';t.textContent=QI18n.t('status_stopped');}
  }
  const btnStart=document.getElementById('btnStart'); if(btnStart) btnStart.disabled=d.running;
  const btnStop=document.getElementById('btnStop'); if(btnStop) btnStop.disabled=!d.running;
  const btnPause=document.getElementById('btnPause');
  if(btnPause){btnPause.disabled=!d.running; btnPause.textContent=d.paused?QI18n.t('btn_resume'):QI18n.t('btn_pause');}
  _s('iterBadge', d.last_scan||'—');
  _s('lastScan', '⏰ '+(d.last_scan||'—'));
  _s('nextScan', '→ '+(d.next_scan||'—'));
  // Stats
  _s('sBal', fmt(d.balance,0));
  _s('sWin', d.total_trades>0?fmt(d.win_rate,1)+'%':'—');
  _s('sDd', fmt(d.max_drawdown,1)+'%');
  _s('sOpen', d.open_trades+'/'+(d.max_trades||5));
  _s('sTrades', d.total_trades);
  _s('sSharpe', d.sharpe>0?fmt(d.sharpe,2):'—');
  // Bottom row
  const dp=document.getElementById('sDailyPnl');
  if(dp){dp.textContent=fmtS(d.daily_pnl||0); dp.style.color=clr(d.daily_pnl||0);}
  _s('sPF', d.profit_factor>0?fmt(d.profit_factor,2):'—');
  // Regime
  const bull=(d.market_regime||'').includes('bullish');
  const rb=document.getElementById('regimeBadge');
  if(rb){rb.textContent=bull?'🐂 '+QI18n.t('label_bullish'):'🐻 '+QI18n.t('label_bearish'); rb.className=bull?'badge-pill badge-bull':'badge-pill badge-bear';}
  _s('btcBadge', 'BTC '+(d.btc_price?fmt(d.btc_price,0):'—'));
  // Portfolio chart
  if(portChart && d.portfolio_history?.length){
    const vals=d.portfolio_history.map(h=>h.value);
    const cc=vals[vals.length-1]>=(vals[0]||0)?'#00ff88':'#ef4444';
    portChart.data.labels=d.portfolio_history.map(h=>h.time);
    portChart.data.datasets[0].data=vals;
    portChart.data.datasets[0].borderColor=cc;
    portChart.data.datasets[0].backgroundColor=cc==='#00ff88'?'rgba(0,255,136,0.06)':'rgba(255,61,113,0.06)';
    portChart.update('none');
  }
  // Sub-components
  if(d.fear_greed) updateFG(d.fear_greed);
  if(d.circuit_breaker) updateCB(d.circuit_breaker);
  if(d.goal) updateGoal(d.goal);
  if(d.dominance) updateDom(d.dominance);
  if(d.anomaly) updateAnomaly(d.anomaly);
  if(d.genetic) updateGenetic(d.genetic);
  if(d.rl){ const rlEl=document.getElementById('rlEpisodes'); if(rlEl) rlEl.textContent=d.rl.episodes||0; }
  // Positions + trades
  updatePositions(d.positions||[]);
  renderTrades(allTrades, tradeFilter);
  _s('tradeCount', d.total_trades);
  _s('posCount', d.open_trades);
  const pb=document.getElementById('posBadge'); if(pb){pb.textContent=d.open_trades; pb.classList.toggle('show',d.open_trades>0);}
  // Signals + activity
  updateSignals(d.signal_log||[]);
  updateActivity(d.activity_log||[]);
  if(d.price_alerts) renderAlerts(d.price_alerts);
  if(d.arb_log) renderArbLog(d.arb_log);
  if(d.ai) updateAI(d.ai);
  // Update badge in header
  if(d.update_status?.update_available){
    const ub = document.getElementById('statusBadge');
    if(!document.getElementById('updateHeaderBadge')){
      const b = document.createElement('div');
      b.id='updateHeaderBadge';
      b.style.cssText='font-size:9px;background:rgba(0,230,118,.15);border:1px solid rgba(0,230,118,.3);color:var(--green);border-radius:5px;padding:2px 7px;font-family:var(--mono);font-weight:700;cursor:pointer;';
      b.textContent='🎉 Update';
      b.onclick=()=>{nav('settings',document.getElementById('nb-settings'));};
      ub.parentNode.insertBefore(b, ub);
    }
    renderUpdateStatus(d.update_status);
  }

  // Chart pos buttons
  if((d.positions||[]).length){
    const cpb=document.getElementById('chartPosBtns');
    if(cpb) cpb.innerHTML=d.positions.map(p=>
      `<button onclick="openChart('${escJS(p.symbol)}')" class="filter-btn">${esc(p.symbol.replace('/USDT',''))} ${p.trade_type==='short'?'📉':'📈'} ${fmtPct(p.pnl_pct||0)}</button>`).join('');
  }
  // ARB stat
  _s('sArb', (d.arb_log||[]).length);
  refreshTradingInsights();
  } catch(e){ console.warn('updateUI error:', e); }
}

function updateFG(fg){
  if(!fg) return;
  const v=fg.value||50, c=v<25?'var(--green)':v<45?'var(--teal)':v<55?'var(--yellow)':v<75?'var(--orange)':'var(--red)';
  const fgv=document.getElementById('fgVal'); if(fgv){fgv.textContent=v; fgv.style.color=c;}
  const fgl=document.getElementById('fgLabel'); if(fgl) fgl.textContent=fg.label||'Neutral';
  const fgu=document.getElementById('fgUpdated'); if(fgu) fgu.textContent=fg.last_update||'—';
  const pct=v/100;
  const fgr=document.getElementById('fgRing'); if(fgr) fgr.style.background=`conic-gradient(${c} ${pct}turn,var(--bg3) ${pct}turn)`;
  const fgb=document.getElementById('fgBar'); if(fgb) fgb.style.cssText=`width:${v}%;background:${c}`;
  const fgs=document.getElementById('fgSub');
  if(fgs){fgs.textContent=fg.ok_to_buy?'✅ '+QI18n.t('buy_allowed_label'):'🚫 '+QI18n.t('buy_blocked_label'); fgs.style.color=fg.ok_to_buy?'var(--green)':'var(--red)';}
}
function updateCB(cb){
  const banner=document.getElementById('cbBanner'); if(banner) banner.style.display=cb.active?'block':'none';
  if(cb.active){const sub=document.getElementById('cbSub'); if(sub) sub.textContent=`${cb.losses} ${QI18n.t('cb_losses')} · ${QI18n.t('cb_pause_remaining')} ${cb.remaining_min} Min · ${QI18n.t('cb_until')} ${cb.until||'—'}`;}
}
function updateGoal(g){
  const sec=document.getElementById('goalSection');
  if(!sec) return;
  if(!g||!g.target||g.target<=0){sec.style.display='none';return;}
  sec.style.display='block';
  const gc=document.getElementById('goalCurrent'); if(gc) gc.textContent=fmt(g.current)+' USDT';
  const gt=document.getElementById('goalTarget'); if(gt) gt.textContent=QI18n.t('portfolio_goal')+': '+fmt(g.target)+' USDT';
  const gb=document.getElementById('goalBar'); if(gb) gb.style.width=g.pct+'%';
  const gp=document.getElementById('goalPct'); if(gp) gp.textContent=g.pct+'%';
  const ge=document.getElementById('goalETA'); if(ge) ge.textContent=QI18n.t('eta_label')+': '+g.eta;
  const gba=document.getElementById('goalBadge'); if(gba) gba.textContent=g.pct+'% '+QI18n.t('achieved');
}
function updateDom(dom){
  const dc=document.getElementById('domCard'); if(dc) dc.style.display='block';
  const _s = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
  _s('domBTC', dom.btc_dom+'%');
  _s('domUSDT', dom.usdt_dom+'%');
  _s('domUpdated', dom.last_update||'—');
  const s=document.getElementById('domStatus');
  if(s){
    if(!dom.ok_usdt){s.textContent='🚨';s.style.color='var(--red)';}
    else if(!dom.ok_btc){s.textContent='⚠️';s.style.color='var(--yellow)';}
    else{s.textContent='✅';s.style.color='var(--green)';}
  }
  const cd=document.getElementById('cDom');
  if(cd){cd.textContent='BTC '+dom.btc_dom+'%'; cd.style.color=dom.ok_btc?'var(--green)':'var(--red)';}
}
function updateAnomaly(anom){
  if(!anom) return;
  const ab=document.getElementById('anomalyBanner'); if(ab) ab.style.display=anom.is_anomaly?'block':'none';
  if(anom.is_anomaly){const at=document.getElementById('anomalyTxt'); if(at) at.textContent=`Symbol: ${anom.anomaly_symbol||'?'} · Score: ${anom.last_score?.toFixed(3)||0}`;}
  const as=document.getElementById('anomSamples'); if(as) as.textContent=anom.samples||0;
}
function updateGenetic(gen){
  if(!gen) return;
  const gf=document.getElementById('genFitness'); if(gf) gf.textContent=gen.best_fitness>0?gen.best_fitness.toFixed(3):'—';
  const gc=document.getElementById('genGenCount'); if(gc) gc.textContent='Gen.'+gen.generation;
  const el=document.getElementById('genHistory');
  if(!el) return;
  if(gen.history?.length) el.innerHTML=gen.history.slice(0,8).map(h=>
    `<div class="log-row info"><span class="log-time">Gen.${esc(String(h.gen||''))}</span>
     <span class="log-msg">Fitness:${esc(String(h.fitness||''))} · SL:${((h.genome?.sl??0)*100).toFixed(1)}% · TP:${((h.genome?.tp??0)*100).toFixed(1)}%</span></div>`).join('');
  else el.innerHTML='<div class="empty" style="padding:8px">—</div>';
}

function updatePositions(positions){
  const el=document.getElementById('posList');
  if(!el) return;
  if(!positions.length){el.innerHTML='<div class="empty"><div class="empty-ico">📭</div>'+QI18n.t('no_open_positions')+'</div>';return;}
  el.innerHTML=positions.map(p=>{
    const pos=p.pnl>=0,c=clr(p.pnl),isShort=p.trade_type==='short';
    const dcaBadge=p.dca_level>0?`<span class="badge-pill badge-dca">DCA lv${p.dca_level}</span>`:'';
    const newsBadge=Math.abs(p.news_score||0)>0.2?`<span class="badge-pill badge-news">📰${(p.news_score>=0?'+':'')}${(p.news_score||0).toFixed(2)}</span>`:'';
    const shortBadge=isShort?`<span class="badge-pill badge-short">SHORT</span>`:'';
    return `<div class="pos-card">
      <div class="pos-top">
        <div style="width:32px;height:32px;border-radius:8px;background:${pos?'rgba(0,255,136,.1)':'rgba(255,61,113,.1)'};display:flex;align-items:center;justify-content:center;font-size:16px">${isShort?'📉':(pos?'📈':'📊')}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:700;display:flex;align-items:center;gap:5px;flex-wrap:wrap">${esc(String(p.symbol||''))} ${dcaBadge}${newsBadge}${shortBadge}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono);margin-top:2px">${(p.entry||0).toFixed(4)} → ${(p.current||0).toFixed(4)}</div>
          <div style="font-size:10px;margin-top:2px;color:var(--sub)">KI: <span style="color:var(--cyan)">${p.ai_score||'—'}%</span> · Win: <span style="color:var(--cyan)">${p.win_prob||'—'}%</span></div>
        </div>
        <div style="text-align:right">
          <div style="font-size:14px;font-weight:700;font-family:var(--mono);color:${c}">${pos?'+':''}${fmt(p.pnl)}</div>
          <div style="font-size:11px;font-family:var(--mono);color:${c}">${fmtPct(p.pnl_pct||0)}</div>
          <button onclick="closePos('${escJS(p.symbol)}')" style="font-size:11px;padding:7px 10px">✕ ${QI18n.t('close_label')}</button>
              <button class="btn btn-info" style="font-size:11px;padding:7px 10px" onclick="adjustSL('${escJS(p.symbol)}',${p.entry})">🎯 SL</button>
        </div>
      </div>
      <div class="pos-bot"><span>SL: ${(p.sl||0).toFixed(4)}</span><span>TP: ${(p.tp||0).toFixed(4)}</span><span>${fmt(p.invested||0,0)} USDT</span></div>
    </div>`;
  }).join('');
}

function filterTrades(f,el){
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active'); tradeFilter=f; renderTrades(allTrades,f);
}
function renderTrades(trades,filter){
  let fl=trades;
  if(filter==='win')   fl=trades.filter(t=>(t.pnl||0)>0);
  if(filter==='loss')  fl=trades.filter(t=>(t.pnl||0)<=0);
  if(filter==='long')  fl=trades.filter(t=>t.trade_type!=='short');
  if(filter==='short') fl=trades.filter(t=>t.trade_type==='short');
  if(filter==='dca')   fl=trades.filter(t=>t.dca_level>0);
  const el=document.getElementById('tradeLog');
  if(!el) return;
  if(!fl.length){el.innerHTML='<div class="empty"><div class="empty-ico">📋</div>'+QI18n.t('no_trades_yet')+'</div>';return;}
  el.innerHTML=fl.slice(0,80).map(t=>{
    const won=(t.pnl||0)>0,c=clr(t.pnl||0),isShort=t.trade_type==='short';
    const ns=t.news_score!==0?` 📰${(t.news_score||0)>=0?'+':''}${(t.news_score||0).toFixed(2)}`:'';
    const dca=t.dca_level>0?` DCA${t.dca_level}`:'';
    return `<div class="trade-row">
      <div style="font-size:18px">${isShort?'📉':(won?'✅':'❌')}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:13px;font-weight:700">${esc(String(t.symbol||''))}${isShort?' SHORT':''}${dca}</div>
        <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${(t.entry||0).toFixed(4)} → ${(t.exit||0).toFixed(4)} · ${esc(String(t.reason||'—'))}${ns}</div>
        <div style="font-size:10px;color:var(--muted)">${esc(String((t.closed||'—').slice(0,10)))}</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:${c}">${fmtS(t.pnl||0)}</div>
        <div style="font-size:11px;font-family:var(--mono);color:${c}">${fmtPct(t.pnl_pct||0)}</div>
      </div>
    </div>`;
  }).join('');
}

function updateStats(d){
  if(!d) return;
  try {
    const _s = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
    const _sc = (id, v, color) => { const el=document.getElementById(id); if(el){el.textContent=v; if(color) el.style.color=color;} };
    _s('pStart', fmt(d.initial_balance)+' USDT');
    _s('pCurrent', fmt(d.portfolio_value)+' USDT');
    _sc('pPnl', fmtS(d.total_pnl)+' USDT', clr(d.total_pnl));
    _sc('pReturn', fmtPct(d.return_pct), clr(d.return_pct));
    _s('pDd', fmt(d.max_drawdown,1)+'%');
    _s('pSharpe', d.sharpe>0?fmt(d.sharpe,2):'—');
    _s('pTotal', d.total_trades);
    _s('pWR', d.total_trades>0?fmt(d.win_rate,1)+'%':'—');
    _s('pAvgW', fmt(d.avg_win)+' USDT');
    _s('pAvgL', fmt(d.avg_loss)+' USDT');
    _s('pPF', d.profit_factor>0?fmt(d.profit_factor,2):'—');
    _s('pDCA', allTrades.filter(t=>t.dca_level>0).length);
    _s('pShorts', allTrades.filter(t=>t.trade_type==='short').length);
    _s('pArbCount', (d.arb_log||[]).length);
    // Top coins
    const coinPnl={};
    allTrades.forEach(t=>{coinPnl[t.symbol]=(coinPnl[t.symbol]||0)+(t.pnl||0);});
    const topEl=document.getElementById('topCoins');
    if(topEl) topEl.innerHTML=Object.entries(coinPnl).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([sym,pnl])=>
      `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);font-size:12px">
         <span style="font-weight:600">${esc(String(sym))}</span>
         <span style="font-family:var(--mono);font-weight:700;color:${clr(pnl)}">${fmtS(pnl)}</span></div>`).join('')||'<div class="empty" style="padding:8px">—</div>';
    // Hour chart
    if(hourChart && allTrades.length){
      const hd=Array(24).fill(0);
      allTrades.forEach(t=>{if(t.closed){try{const h=new Date(t.closed).getUTCHours();if(h>=0&&h<24) hd[h]+=(t.pnl||0);}catch(e){}}});
      hourChart.data.datasets[0].data=hd;
      hourChart.data.datasets[0].backgroundColor=hd.map(v=>v>=0?'rgba(0,255,136,.4)':'rgba(255,61,113,.4)');
      hourChart.update('none');
    }
    // PnL chart
    if(pnlChart && allTrades.length){
      const rec=allTrades.slice(0,30).reverse();
      pnlChart.data.labels=rec.map((_,i)=>'#'+(i+1));
      pnlChart.data.datasets[0].data=rec.map(t=>t.pnl||0);
      pnlChart.data.datasets[0].backgroundColor=rec.map(t=>(t.pnl||0)>=0?'rgba(0,255,136,.5)':'rgba(255,61,113,.5)');
      pnlChart.update('none');
    }
  } catch(e){ console.warn('updateStats error:', e); }
}

function updateAI(ai){
  if(!ai) return;
  const _s = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
  const _sc = (id, v, color) => { const el=document.getElementById(id); if(el){el.textContent=v; if(color) el.style.color=color;} };
  _s('aiVer', ai.is_trained?'v'+ai.training_ver:'Training...');
  const assistantLabel = ai.assistant_name ? `${ai.assistant_name} ${ai.assistant_version||''}`.trim() : '—';
  _s('aiAssistant', assistantLabel);
  _sc('aiStatusMsg', ai.status_msg||'—', ai.is_trained?'var(--green)':'var(--sub)');
  _s('aiProgPct', (ai.progress_pct||0)+'%');
  const progBar=document.getElementById('aiProgBar');
  if(progBar){progBar.style.width=(ai.progress_pct||0)+'%'; progBar.style.background=(ai.progress_pct||0)>=100?'var(--green)':'var(--cyan)';}
  _s('aiWF', ai.wf_accuracy>0?ai.wf_accuracy+'%':'—');
  _s('aiBullAcc', ai.bull_accuracy>0?ai.bull_accuracy+'%':'—');
  _s('aiBearAcc', ai.bear_accuracy>0?ai.bear_accuracy+'%':'—');
  _s('aiSamples', ai.samples||0);
  _s('aiBullS', ai.bull_samples||0);
  _s('aiBearS', ai.bear_samples||0);
  _s('aiAllowed', ai.allowed_count||0);
  _s('aiBlocked', ai.blocked_count||0);
  _s('aiNews', (ai.status_msg?.includes('News'))||false?'✅':'—');
  _s('aiOnchain', '✅');
  _s('aiDecCount', ai.ai_log?.length||0);
  // Weights
  const wl=document.getElementById('weightList');
  if(wl && ai.weights?.length) wl.innerHTML=ai.weights.map(w=>{
    const pct=Math.min(100,Math.round(w.weight/3.5*100));
    const c=w.weight>1.2?'var(--green)':w.weight<0.5?'var(--red)':'var(--cyan)';
    return `<div class="weight-row"><span class="weight-name">${esc(String(w.name||''))}</span>
      <div class="weight-bar-wrap"><div class="weight-bar" style="width:${pct}%;background:${c}"></div></div>
      <span class="weight-val" style="color:${c}">${esc(String(w.weight||0))}×</span>
      <span style="font-size:9px;color:var(--sub);width:32px;flex-shrink:0;text-align:right">${esc(String(w.win_rate||0))}%</span></div>`;
  }).join('');
  // AI log
  const dl=document.getElementById('aiDecLog');
  if(dl && ai.ai_log?.length) dl.innerHTML=ai.ai_log.map(e=>
    `<div class="log-row ${e.allowed?'success':'error'}">
      <span class="log-time">${esc(String(e.time||''))}</span>
      <span class="log-msg">${esc(String(e.reason||'—'))} (${esc(String(e.prob||0))}%)</span></div>`).join('');
  updateAI3DFromAI(ai);
}

const _ai3dState = {
  ready:false, angle:0, wobble:0,
  wf:0, bull:0, bear:0, samples:0, preds:0, allowed:0, blocked:0,
  agentCount:0, lastAgent:'—', agentNames:[]
};
const _virginieChat = {loaded:false,messages:[],sending:false,pendingMessage:'',socketTimer:null};
let _virginieEdgeTimer = null;
const _virginieForecastFeed = [];

function _renderVirginieChat(){
  const log=document.getElementById('ai3dChatLog');
  if(!log) return;
  if(!_virginieChat.messages.length){
    log.innerHTML='<div style="font-size:10px;color:var(--sub)">Noch kein Chatverlauf. Schreibe VIRGINIE eine erste Nachricht.</div>';
    return;
  }
  const rows=_virginieChat.messages.slice(-40).map(m=>{
    const isUser=String(m.role||'')==='user';
    const bg=isUser?'rgba(110,231,255,.12)':'rgba(212,175,55,.12)';
    const border=isUser?'rgba(110,231,255,.28)':'rgba(212,175,55,.28)';
    const who=isUser?'Du':'VIRGINIE';
    return `<div style="border:1px solid ${border};background:${bg};border-radius:7px;padding:7px 8px">
      <div style="font-size:9px;color:var(--sub);font-family:var(--mono);margin-bottom:3px">${who}</div>
      <div style="font-size:11px;line-height:1.45;color:#f5efe1;white-space:pre-wrap">${esc(String(m.content||''))}</div>
    </div>`;
  });
  log.innerHTML=rows.join('');
  log.scrollTop=log.scrollHeight;
}

function _appendVirginieChatMessage(msg){
  if(!msg || !msg.content) return;
  const nextMsg = {
    role:String(msg.role||'assistant'),
    content:String(msg.content||''),
    time:String(msg.time||new Date().toISOString())
  };
  const last = _virginieChat.messages[_virginieChat.messages.length - 1];
  if(last && last.role===nextMsg.role && last.content===nextMsg.content) return;
  _virginieChat.messages.push(nextMsg);
  _renderVirginieChat();
}

async function loadVirginieChatHistory(){
  if(_virginieChat.loaded) return;
  try{
    const r = await fetch('/api/v1/virginie/chat', {credentials:'include'});
    if(!r.ok) return;
    const d = await r.json();
    _virginieChat.messages = Array.isArray(d.messages) ? d.messages : [];
    _virginieChat.loaded = true;
    _renderVirginieChat();
  }catch(_e){}
}

async function refreshVirginieChatHistory(force=false){
  if(force){ _virginieChat.loaded=false; }
  await loadVirginieChatHistory();
}

async function clearVirginieChatHistory(){
  try{
    const r=await fetch('/api/v1/virginie/chat/clear',{method:'POST',credentials:'include'});
    const d=await r.json();
    if(!r.ok || d.error){ toast('⚠️ '+(d.error||'Chat konnte nicht gelöscht werden'),'warning'); return; }
    _virginieChat.messages=[];
    _renderVirginieChat();
    toast('🧹 VIRGINIE Chat gelöscht','success');
  }catch(_e){
    toast('⚠️ VIRGINIE Chat aktuell nicht erreichbar','warning');
  }
}

function sendVirginieChat(){
  const input=document.getElementById('ai3dChatInput');
  if(!input || _virginieChat.sending) return;
  const message=String(input.value||'').trim();
  if(!message) return;
  _virginieChat.sending=true;
  _virginieChat.pendingMessage=message;
  if(_virginieChat.socketTimer){clearTimeout(_virginieChat.socketTimer);_virginieChat.socketTimer=null;}
  input.value='';
  if(socket && socket.connected){
    socket.emit('virginie_chat',{message});
    _virginieChat.socketTimer = setTimeout(()=>{
      if(!_virginieChat.sending) return;
      fetch('/api/v1/virginie/chat',{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message:_virginieChat.pendingMessage})
      }).then(r=>r.json()).then(d=>{
        if(d && d.user) _appendVirginieChatMessage(d.user);
        if(d && d.assistant) _appendVirginieChatMessage(d.assistant);
        if(d && d.error) toast('⚠️ '+d.error,'warning');
      }).catch(()=>toast('⚠️ VIRGINIE Chat aktuell nicht erreichbar','warning'))
        .finally(()=>{
          _virginieChat.sending=false;
          _virginieChat.pendingMessage='';
          if(_virginieChat.socketTimer){clearTimeout(_virginieChat.socketTimer);_virginieChat.socketTimer=null;}
        });
    }, 8000);
    return;
  }
  fetch('/api/v1/virginie/chat',{
    method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message})
  }).then(r=>r.json()).then(d=>{
    if(d && d.user) _appendVirginieChatMessage(d.user);
    if(d && d.assistant) _appendVirginieChatMessage(d.assistant);
    if(d && d.error) toast('⚠️ '+d.error,'warning');
  }).catch(()=>toast('⚠️ VIRGINIE Chat aktuell nicht erreichbar','warning'))
    .finally(()=>{
      _virginieChat.sending=false;
      _virginieChat.pendingMessage='';
    });
}

function sendVirginiePlanRequest(){
  const input=document.getElementById('ai3dChatInput');
  if(!input || _virginieChat.sending) return;
  input.value='/plan';
  sendVirginieChat();
}

function initVirginieChat(){
  const btn=document.getElementById('ai3dChatSendBtn');
  const input=document.getElementById('ai3dChatInput');
  const planBtn=document.getElementById('ai3dChatPlanBtn');
  const refreshBtn=document.getElementById('ai3dChatRefreshBtn');
  const clearBtn=document.getElementById('ai3dChatClearBtn');
  if(btn) btn.addEventListener('click', sendVirginieChat);
  if(input) input.addEventListener('keydown', (ev)=>{ if(ev.key==='Enter'){ ev.preventDefault(); sendVirginieChat(); }});
  if(planBtn) planBtn.addEventListener('click', sendVirginiePlanRequest);
  if(refreshBtn) refreshBtn.addEventListener('click', ()=>refreshVirginieChatHistory(true));
  if(clearBtn) clearBtn.addEventListener('click', clearVirginieChatHistory);
  loadVirginieChatHistory();
  loadVirginieEdgeProfile();
  if(!_virginieEdgeTimer){
    _virginieEdgeTimer = setInterval(loadVirginieEdgeProfile, 30000);
  }
}

async function loadVirginieEdgeProfile(){
  try{
    const r = await fetch('/api/v1/virginie/edge-profile', {credentials:'include'});
    if(!r.ok) return;
    const d = await r.json();
    _s('vEdgeScore', `${Number(d.edge_score||0).toFixed(1)} / 100`);
    _s('vEdgeTier', String(d.tier||'—'));
    _s('vEdgeUrgency', String(d.urgency||'—'));
    _s('vEdgeSignature', String(d.signature||'—'));
    const tierEl=document.getElementById('vEdgeTier');
    if(tierEl){
      const tier=String(d.tier||'');
      tierEl.style.color = tier==='S' ? 'var(--green)' : tier==='A' ? 'var(--jade)' : tier==='B' ? 'var(--yellow)' : 'var(--red)';
    }
  }catch(_e){}
  loadVirginieForecastFeed();
}

function _renderVirginieForecastFeed(){
  const el = document.getElementById('vEdgeFeed');
  if(!el) return;
  if(!_virginieForecastFeed.length){
    el.innerHTML = '<div class="row" style="color:var(--sub)">Noch keine Forecast-Events.</div>';
    return;
  }
  el.innerHTML = _virginieForecastFeed.slice(0,8).map(item=>{
    const clr = item.allowed ? 'var(--green)' : 'var(--red)';
    return `<div class="row">
      <div style="display:flex;justify-content:space-between;gap:6px">
        <span style="color:${clr};font-weight:700">${esc(item.symbol||'—')} · ${esc(item.recommended_action||'—')}</span>
        <span style="font-family:var(--mono);color:var(--sub)">${esc(item.time||'')}</span>
      </div>
      <div style="margin-top:2px;color:var(--sub)">Tier ${esc(item.tier||'—')} · ${esc(item.bias||'—')} · ${esc(String(item.score_pct||0))}%</div>
    </div>`;
  }).join('');
}

function _renderVirginieForecastStats(stats){
  const kpiEl = document.getElementById('vEdgeKpi');
  const tiersEl = document.getElementById('vEdgeTierStats');
  if(kpiEl){
    const total = Number(stats?.total||0);
    const allowRate = Number(stats?.allow_rate||0).toFixed(1);
    kpiEl.textContent = `Forecast KPI: ${total} Events · Allow-Rate ${allowRate}%`;
  }
  if(tiersEl){
    const by = stats?.by_tier || {};
    const items = ['S','A','B','C'].map(t=>{
      const d = by[t] || {};
      return `<span class="pill">${t}: ${Number(d.allow_rate||0).toFixed(1)}% (${Number(d.count||0)})</span>`;
    });
    tiersEl.innerHTML = items.join('');
  }
}

function _renderVirginieForecastQuality(q){
  const el = document.getElementById('vEdgeQuality');
  if(!el) return;
  const matched = Number(q?.matched_total||0);
  const wr = Number(q?.win_rate||0).toFixed(1);
  el.textContent = `Forecast Quality: ${wr}% Win-Rate · ${matched} matched`;
}

async function loadVirginieForecastFeed(){
  try{
    const r = await fetch('/api/v1/virginie/forecast-feed?limit=12', {credentials:'include'});
    if(!r.ok) return;
    const d = await r.json();
    const items = Array.isArray(d.items) ? d.items : [];
    _virginieForecastFeed.splice(0, _virginieForecastFeed.length, ...items);
    _renderVirginieForecastFeed();
    _renderVirginieForecastStats(d.stats || {});
  }catch(_e){}
  try{
    const rQ = await fetch('/api/v1/virginie/forecast-quality', {credentials:'include'});
    if(!rQ.ok) return;
    const q = await rQ.json();
    _renderVirginieForecastQuality(q);
  }catch(_e){}
}

function updateAI3DFromAI(ai){
  if(!ai) return;
  _ai3dState.wf = Number(ai.wf_accuracy||0);
  _ai3dState.bull = Number(ai.bull_accuracy||0);
  _ai3dState.bear = Number(ai.bear_accuracy||0);
  _ai3dState.samples = Number(ai.samples||0);
  _ai3dState.preds = Number(ai.allowed_count||0) + Number(ai.blocked_count||0);
  _ai3dState.allowed = Number(ai.allowed_count||0);
  _ai3dState.blocked = Number(ai.blocked_count||0);
  _ai3dState.agentCount = Number((ai.assistant_agents||{}).registered_agents||0);
  _ai3dState.lastAgent = String((ai.assistant_agents||{}).last_agent||'—');
  _ai3dState.agentNames = Array.isArray((ai.assistant_agents||{}).agent_names) ? (ai.assistant_agents||{}).agent_names : [];
  const m=document.getElementById('ai3dMeta');
  const assistantAgents = ai.assistant_agents || {};
  if(m) m.textContent = assistantAgents.registered_agents
    ? `VIRGINIE Agents: ${assistantAgents.registered_agents} · Coverage: ${assistantAgents.coverage_pct||0}%`
    : `WF: ${_ai3dState.wf.toFixed(1)}% · Pred: ${_ai3dState.preds}`;
  const collabEl = document.getElementById('ai3dCollab');
  if(collabEl){
    const providers = Number(ai.llm_providers_used||0);
    const answers = Number(ai.llm_responses_used||0);
    const runs = Number(ai.idle_learning_runs||0);
    const ag = ai.assistant_agents || {};
    const primary = Boolean(ai.assistant_primary_control);
    const autonomyW = Number(ai.assistant_autonomy_weight||0);
    const active = providers > 0 || answers > 0 || Number(ag.history_size||0) > 0;
    collabEl.textContent = active
      ? `🤖 VIRGINIE aktiv · ${primary?'Primary':'Hybrid'} · w=${autonomyW.toFixed(2)} · Agents ${ag.registered_agents||0} · Coverage ${ag.coverage_pct||0}% · Last ${ag.last_agent||'—'}`
      : `🤖 VIRGINIE wartet · ${primary?'Primary':'Hybrid'} · w=${autonomyW.toFixed(2)} · Agents ${ag.registered_agents||0} · Coverage ${ag.coverage_pct||0}%`;
  }
  const agentsEl = document.getElementById('ai3dAgents');
  if(agentsEl){
    const names = _ai3dState.agentNames.slice(0, 9);
    agentsEl.innerHTML = names.length
      ? names.map(n => `<span style="font-size:10px;padding:3px 7px;border:1px solid rgba(212,175,55,.25);border-radius:999px;background:rgba(212,175,55,.08);color:#e9d3a1">${esc(n)}</span>`).join('')
      : '<span style="font-size:10px;color:var(--sub)">Keine Agenten registriert</span>';
  }
  if(!_ai3dState.ready){
    _ai3dState.ready=true;
    requestAnimationFrame(_renderAI3D);
  }
}
function _renderAI3D(){
  const c=document.getElementById('ai3dCanvas');
  if(!c){ _ai3dState.ready=false; return; }
  const ctx=c.getContext('2d');
  const w=c.width,h=c.height;
  ctx.clearRect(0,0,w,h);
  // Background stars
  for(let i=0;i<26;i++){
    const x=(i*97 + _ai3dState.angle*13)%w;
    const y=(i*53 + _ai3dState.angle*7)%h;
    ctx.fillStyle='rgba(255,210,130,0.08)';
    ctx.fillRect(x,y,2,2);
  }
  const cx=w*0.34, cy=h*0.55;
  _ai3dState.angle += 0.015;
  _ai3dState.wobble = Math.sin(_ai3dState.angle*1.4)*6;
  // Orbital ring
  ctx.save();
  ctx.translate(cx,cy);
  ctx.rotate(_ai3dState.angle);
  ctx.strokeStyle='rgba(255,190,80,0.35)';
  ctx.lineWidth=2;
  ctx.beginPath(); ctx.ellipse(0,0,90,28,0,0,Math.PI*2); ctx.stroke();
  ctx.rotate(-_ai3dState.angle*1.8);
  ctx.strokeStyle='rgba(0,255,180,0.22)';
  ctx.beginPath(); ctx.ellipse(0,0,74,22,0,0,Math.PI*2); ctx.stroke();
  ctx.restore();
  // Agenten-Orbits (VIRGINIE)
  const agentN = Math.max(0, Math.min(12, _ai3dState.agentCount||0));
  for(let i=0;i<agentN;i++){
    const a = _ai3dState.angle + (i*(Math.PI*2/Math.max(agentN,1)));
    const rx = 70 + (i%3)*12;
    const ry = 30 + (i%2)*10;
    const x = cx + Math.cos(a)*rx;
    const y = cy + Math.sin(a)*ry;
    ctx.beginPath();
    ctx.arc(x,y,3.2,0,Math.PI*2);
    ctx.fillStyle = i===0 ? 'rgba(0,255,136,.9)' : 'rgba(255,196,90,.8)';
    ctx.fill();
  }
  ctx.fillStyle='rgba(220,200,150,.85)';
  ctx.font='10px Fira Code, monospace';
  ctx.fillText(`Agents: ${_ai3dState.agentCount} | Last: ${_ai3dState.lastAgent}`, 12, h-10);
  // Core sphere
  const grd=ctx.createRadialGradient(cx-10,cy-16,8,cx,cy,60);
  grd.addColorStop(0,'rgba(255,236,180,.95)');
  grd.addColorStop(.5,'rgba(255,180,70,.45)');
  grd.addColorStop(1,'rgba(255,120,40,.08)');
  ctx.fillStyle=grd;
  ctx.beginPath(); ctx.arc(cx,cy+_ai3dState.wobble,52,0,Math.PI*2); ctx.fill();
  // 3D bars (live metrics)
  const bars=[
    {k:'WF',v:_ai3dState.wf,c:'#00ffaa'},
    {k:'Bull',v:_ai3dState.bull,c:'#6ee7ff'},
    {k:'Bear',v:_ai3dState.bear,c:'#ff8ca1'},
    {k:'Allow',v:Math.min(100,_ai3dState.allowed),c:'#c7ff6e'},
    {k:'Block',v:Math.min(100,_ai3dState.blocked),c:'#ffb36e'}
  ];
  const bx=w*0.62, by=h*0.78, bw=28, gap=14, maxH=120;
  bars.forEach((b,i)=>{
    const x=bx+i*(bw+gap), bh=Math.max(4, Math.min(maxH,(b.v/100)*maxH));
    // Front
    ctx.globalAlpha=0.78;
    ctx.fillStyle=b.c;
    ctx.fillRect(x,by-bh,bw,bh);
    ctx.globalAlpha=1;
    // Side
    ctx.fillStyle='rgba(255,255,255,.08)';
    ctx.beginPath();
    ctx.moveTo(x+bw,by-bh); ctx.lineTo(x+bw+7,by-bh-5); ctx.lineTo(x+bw+7,by-5); ctx.lineTo(x+bw,by);
    ctx.closePath(); ctx.fill();
    // Top
    ctx.fillStyle='rgba(255,255,255,.16)';
    ctx.beginPath();
    ctx.moveTo(x,by-bh); ctx.lineTo(x+7,by-bh-5); ctx.lineTo(x+bw+7,by-bh-5); ctx.lineTo(x+bw,by-bh);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle='rgba(220,225,245,.9)';
    ctx.font='11px Barlow, sans-serif';
    ctx.fillText(b.k,x,by+14);
  });
  // Labels
  ctx.fillStyle='rgba(235,220,180,.85)';
  ctx.font='12px Fira Code, monospace';
  ctx.fillText(`samples:${_ai3dState.samples}`, 18, 22);
  ctx.fillText(`pred:${_ai3dState.preds}`, 18, 40);
  if(_ai3dState.ready) requestAnimationFrame(_renderAI3D);
}

function updateSignals(sigs){
  const el=document.getElementById('sigList');
  if(!el) return;
  const sc=document.getElementById('sigCount'); if(sc) sc.textContent=sigs.length||0;
  if(!sigs.length){
    el.innerHTML='<div class="empty"><div class="empty-ico">📡</div>'+QI18n.t('waiting_for_signals')+'</div>';
    _syncLivePanels(null);
    return;
  }
  el.innerHTML=sigs.slice(0,25).map(s=>{
    const signalTxt=String(s.signal||'').toUpperCase();
    const isSell=signalTxt.includes('VERKAUF') || signalTxt.includes('SELL');
    const signalColor=isSell?'var(--red)':'var(--green)';
    const signalLabel=signalTxt || 'SIGNAL';
    const nc=s.news_score>0.2?'var(--green)':s.news_score<-0.2?'var(--red)':'var(--sub)';
    return `<div style="background:var(--bg2);border-left:3px solid ${signalColor};border-radius:9px;padding:9px 11px;margin-bottom:5px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:13px;font-weight:700">${esc(String(s.symbol||''))}</span>
        <span style="font-size:10px;font-family:var(--mono);color:var(--sub)">${esc(String(s.time||'—'))}</span>
      </div>
      <div style="font-size:10px;color:${signalColor};margin-top:3px;font-family:var(--mono);font-weight:700">${esc(signalLabel)}</div>
      <div style="font-size:10px;color:var(--sub);margin-top:3px;font-family:var(--mono)">RSI:${esc(String(s.rsi||'—'))} · Conf:${s.confidence?Math.round(s.confidence*100):0}% · ${esc(String(s.mtf_desc||''))}</div>
      ${s.news_headline?`<div style="font-size:10px;color:${nc};margin-top:3px;font-style:italic">${esc(s.news_headline.slice(0,80))}</div>`:''}
    </div>`;
  }).join('');
  _syncLivePanels(sigs[0]||null);
}

function _syncLivePanels(sig){
  const _set=(id,val,color)=>{
    const el=document.getElementById(id);
    if(!el) return;
    el.textContent=val;
    if(color) el.style.color=color;
  };
  if(!sig){
    _set('cRSI','—');
    _set('cVol','—');
    _set('cMTF','—');
    const nf=document.getElementById('newsFeed');
    if(nf){
      nf.innerHTML='<div class="empty"><div class="empty-ico">📰</div>'+QI18n.t('waiting_for_signals')+'</div>';
    }
    return;
  }
  const rsi = sig.rsi===0 ? '0' : (sig.rsi || '—');
  const conf = sig.confidence || sig.confidence===0 ? Math.round(sig.confidence*100)+'%' : '—';
  _set('cRSI', String(rsi));
  _set('cVol', conf);
  _set('cMTF', String(sig.mtf_desc||'—'));

  const newsFeed=document.getElementById('newsFeed');
  const hasHeadline=typeof sig.news_headline==='string' && sig.news_headline.trim();
  if(!newsFeed) return;
  if(!hasHeadline){
    newsFeed.innerHTML='<div class="empty"><div class="empty-ico">📰</div>'+QI18n.t('waiting_for_signals')+'</div>';
    return;
  }
  const score=Number(sig.news_score||0);
  const nc=score>=0?'var(--green)':'var(--red)';
  newsFeed.innerHTML=`<div class="news-item">
    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
      <span style="font-size:11px;font-weight:700;color:${nc}">${score>=0?'+':''}${score.toFixed(2)} Score</span>
      <span style="font-size:10px;color:var(--sub)">${esc(String(sig.symbol||''))}</span>
    </div>
    <div style="font-size:11px;line-height:1.6">${esc(String(sig.news_headline||''))}</div>
  </div>`;
}

function updateActivity(acts){
  const el=document.getElementById('actList');
  if(!el) return;
  if(!acts.length){el.innerHTML='<div class="empty"><div class="empty-ico">⚡</div>'+QI18n.t('empty_start_bot')+'</div>';return;}
  el.innerHTML=acts.slice(0,12).map(a=>{
    const c={success:'var(--green)',error:'var(--red)',warning:'var(--yellow)',info:'var(--cyan)'}[a.type]||'var(--sub)';
    return `<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)">
      <div style="font-size:18px;flex-shrink:0">${esc(a.icon)}</div>
      <div style="flex:1"><div style="font-size:12px;font-weight:700;color:${c}">${esc(a.title)}</div>
        <div style="font-size:10px;color:var(--sub);margin-top:1px">${esc(a.detail)}</div></div>
      <div style="font-size:10px;color:var(--muted);font-family:var(--mono);flex-shrink:0">${esc(String(a.time||''))}</div>
    </div>`;
  }).join('');
}

function renderAlerts(alerts){
  const ac=document.getElementById('alertCount'); if(ac) ac.textContent=alerts.filter(a=>!a.triggered).length;
  const el=document.getElementById('alertList');
  if(!el) return;
  if(!alerts.length){el.innerHTML='<div class="empty" style="padding:8px">'+QI18n.t('empty_no_alerts')+'</div>';return;}
  el.innerHTML=alerts.map(a=>`<div class="alert-item" style="${a.triggered?'opacity:.4':''}">
    <div style="font-size:16px">${a.triggered?'✅':'🔔'}</div>
    <div style="flex:1"><div style="font-size:12px;font-weight:700">${esc(String(a.symbol||''))}</div>
      <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${a.direction==='above'?QI18n.t('dir_above'):QI18n.t('dir_below')} ${esc(String(a.target_price||''))}</div></div>
    ${!a.triggered?`<button onclick="deleteAlert(${parseInt(a.id,10)||0})" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:16px;padding:4px">🗑</button>`:''}`).join('');
}

function renderArbLog(arb){
  const cnt=(arb||[]).length;
  const acb=document.getElementById('arbCountBadge'); if(acb) acb.textContent=cnt;
  const ac2=document.getElementById('arbCount2'); if(ac2) ac2.textContent=cnt;
  const acd=document.getElementById('arbCard'); if(acd) acd.style.display=cnt>0?'block':'none';
  const html=arb.slice(0,5).map(a=>`<div class="arb-item">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:13px;font-weight:700">${esc(String(a.symbol||''))}</span>
      <span style="font-family:var(--mono);font-weight:900;font-size:13px;color:var(--yellow)">+${esc(String(a.spread||0))}%</span>
    </div>
    <div style="font-size:10px;color:var(--sub);margin-top:3px;font-family:var(--mono)">Kauf: ${esc(String(a.buy||''))} → Verkauf: ${esc(String(a.sell||''))} · ${esc(String(a.time||'—'))}</div>
  </div>`).join('');
  const alh=document.getElementById('arbLogHome'); if(alh) alh.innerHTML=html||'<div class="empty" style="padding:8px">—</div>';
  const al2=document.getElementById('arbList2'); if(al2) al2.innerHTML=html||'<div class="empty" style="padding:8px">'+QI18n.t('empty_no_scans')+'</div>';
}

let _tradingInsightTs = 0;
let _tradingInsightBusy = false;
let _tradingInsightWarnTs = 0;
async function _fetchJsonWithTimeout(path, opts={}, timeoutMs=6500){
  const ctrl = new AbortController();
  const timer = setTimeout(()=>ctrl.abort(), timeoutMs);
  const requestOpts = {...opts};
  const headers = {...(requestOpts.headers||{})};
  if(_jwtToken && !headers.Authorization) headers.Authorization = 'Bearer '+_jwtToken;
  requestOpts.headers = headers;
  try{
    const r = await fetch(path, {...requestOpts, credentials:'include', signal:ctrl.signal});
    let data = {};
    try{ data = await r.json(); }catch(_e){}
    if(!r.ok) throw new Error((data&&data.error)||(`${path} -> ${r.status}`));
    return data;
  } finally {
    clearTimeout(timer);
  }
}
async function _fetchTradingEndpoint(path){
  return _fetchJsonWithTimeout(path, {}, 6500);
}
async function _postTradingEndpoint(path, payload){
  const body = {...(payload||{})};
  if(_csrfToken && !body._csrf) body._csrf = _csrfToken;
  return _fetchJsonWithTimeout(
    path,
    {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)},
    8000
  );
}
function _warnTradingTimeoutOnce(msg){
  const now = Date.now();
  if(now - _tradingInsightWarnTs < 15000) return;
  _tradingInsightWarnTs = now;
  toast(msg,'warning');
}

function _renderSimpleRows(elId, rows, mapFn, emptyTxt){
  const el=document.getElementById(elId);
  if(!el) return;
  if(!rows || !rows.length){
    el.innerHTML = `<div class="empty"><div class="empty-ico">📭</div><span>${esc(emptyTxt||'—')}</span></div>`;
    return;
  }
  el.innerHTML = rows.map(mapFn).join('');
}

async function refreshTradingInsights(force=false){
  if(_tradingInsightBusy) return;
  const now = Date.now();
  if(!force && (now - _tradingInsightTs) < 7000) return;
  _tradingInsightBusy = true;
  _tradingInsightTs = now;
  try{
    const [modeData, orderData, decisionData, perfData] = await Promise.all([
      _fetchTradingEndpoint('/api/v1/trading/mode'),
      _fetchTradingEndpoint('/api/v1/trading/order-history?limit=30'),
      _fetchTradingEndpoint('/api/v1/trading/decision-history?limit=30'),
      _fetchTradingEndpoint('/api/v1/trading/performance')
    ]);
    const mb=document.getElementById('tradeModeBadge');
    if(mb){
      const isPaper = modeData.paper_trading !== false;
      mb.textContent = isPaper ? 'PAPER' : 'LIVE';
      mb.style.color = isPaper ? 'var(--yellow)' : 'var(--red)';
    }
    const oc=document.getElementById('orderCountBadge'); if(oc) oc.textContent = (orderData.orders||[]).length;
    const dc=document.getElementById('decisionCountBadge'); if(dc) dc.textContent = (decisionData.decisions||[]).length;

    _renderSimpleRows(
      'orderHistoryList',
      (orderData.orders||[]).slice(0,20),
      o => `<div style="display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:11px">
        <div><div style="font-weight:700">${esc(String(o.symbol||''))} · ${esc(String((o.side||'').toUpperCase()))}</div>
        <div style="font-size:10px;color:var(--sub)">${esc(String((o.trade_mode||'').toUpperCase()))} · ${esc(String(o.reason||''))}</div></div>
        <div style="text-align:right"><div>${fmt(o.cost||0,2)} USDT</div><div style="font-size:10px;color:var(--sub)">${esc(String((o.created_at||'').slice(0,16)))}</div></div>
      </div>`,
      'Noch keine Orders.'
    );

    _renderSimpleRows(
      'decisionHistoryList',
      (decisionData.decisions||[]).slice(0,20),
      d => `<div style="display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:11px">
        <div><div style="font-weight:700">${esc(String(d.symbol||''))} · ${esc(String((d.decision||'').toUpperCase()))}</div>
        <div style="font-size:10px;color:var(--sub)">${esc(String(d.reason||''))}</div></div>
        <div style="text-align:right"><div>${esc(String((d.trade_mode||'').toUpperCase()))}</div><div style="font-size:10px;color:var(--sub)">${esc(String((d.created_at||'').slice(0,16)))}</div></div>
      </div>`,
      'Noch keine Decisions.'
    );

    const byMode = perfData.by_mode||[];
    const byStrategy = perfData.by_strategy||[];
    const byExchange = perfData.by_exchange||[];
    const pvsl = perfData.paper_vs_live||{};
    _renderSimpleRows(
      'comparePnlList',
      [pvsl],
      c => `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;padding-bottom:4px">
        <div style="border:1px solid var(--line);border-radius:8px;padding:8px">
          <div style="color:var(--sub);font-size:10px">Paper (${esc(String(c.paper_trades||0))} Trades)</div>
          <div style="font-weight:700;color:${(c.paper_pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(c.paper_pnl||0,2)} USDT</div>
          <div style="color:var(--sub);font-size:10px">Fees: ${fmt(c.paper_fees||0,2)}</div>
        </div>
        <div style="border:1px solid var(--line);border-radius:8px;padding:8px">
          <div style="color:var(--sub);font-size:10px">Live (${esc(String(c.live_trades||0))} Trades)</div>
          <div style="font-weight:700;color:${(c.live_pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(c.live_pnl||0,2)} USDT</div>
          <div style="color:var(--sub);font-size:10px">Fees: ${fmt(c.live_fees||0,2)}</div>
        </div>
      </div>`,
      'Keine Vergleichsdaten.'
    );
    _renderSimpleRows(
      'modePerfList',
      byMode,
      m => `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--muted);font-size:11px">
        <span>${esc(String((m.trade_mode||'').toUpperCase()))} · ${esc(String(m.n||0))} Trades</span>
        <span style="color:${(m.pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(m.pnl||0,2)} USDT</span>
      </div>`,
      'Keine Performance-Daten.'
    );
    _renderSimpleRows(
      'strategyPerfList',
      byStrategy.slice(0,8),
      s => `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--muted);font-size:11px">
        <span>${esc(String(s.reason||'unknown'))}</span>
        <span style="color:${(s.pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(s.pnl||0,2)}</span>
      </div>`,
      'Keine Strategie-Auswertung.'
    );
    _renderSimpleRows(
      'exchangePerfList',
      byExchange,
      e => `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--muted);font-size:11px">
        <span>${esc(String((e.exchange||'').toUpperCase()))}</span>
        <span style="color:${(e.pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(e.pnl||0,2)}</span>
      </div>`,
      'Keine Exchange-Auswertung.'
    );
  }catch(err){
    if(String(err).toLowerCase().includes('abort')){
      _warnTradingTimeoutOnce('⚠️ Trading-API Timeout – erneuter Versuch läuft');
    }else{
      console.warn('refreshTradingInsights failed:', err);
    }
  } finally {
    _tradingInsightBusy = false;
  }
}

async function switchTradingMode(mode){
  try{
    const data = await _postTradingEndpoint('/api/v1/trading/mode',{mode});
    toast(`🧭 Trading Mode: ${(data.mode||mode).toUpperCase()}`,'success');
    refreshTradingInsights(true);
    if(socket && socket.connected) socket.emit('request_state');
  }catch(e){ toast('❌ Mode-Wechsel fehlgeschlagen: '+e,'error'); }
}

async function executeTradingControl(action, opts={}){
  const preferSocket = Boolean(opts.preferSocket);
  if(preferSocket){
    const event = action==='start' ? 'start_bot' : action==='stop' ? 'stop_bot' : null;
    if(event && _emitSafe(event, undefined, {silent:true})){
      if(socket && socket.connected) socket.emit('request_state');
      refreshTradingInsights(true);
      return true;
    }
  }
  return _botControlFallback(action);
}

async function apiTradingControl(action){
  const ok = await executeTradingControl(action, {preferSocket:false});
  if(!ok) return;
  toast(action==='start'?'▶ Trading gestartet':'■ Trading gestoppt','success');
}

// ── Heatmap ──────────────────────────────────────────────────────────
async function loadHeatmap(sortBy){
  currentHmSort=sortBy;
  document.querySelectorAll('[id^="hmBtn"]').forEach(b=>b.classList.remove('active'));
  const btn=document.getElementById('hmBtn'+sortBy); if(btn) btn.classList.add('active');
  document.getElementById('heatmapGrid').innerHTML='<div class="empty" style="grid-column:span 5;padding:16px">⏳ Lade...</div>';
  try{
    const data=await(await fetch('/api/heatmap')).json();
    if(data.error){document.getElementById('heatmapGrid').innerHTML=`<div class="empty" style="grid-column:span 5">${esc(data.error)}</div>`;return;}
    const sorted=[...data].sort((a,b)=>sortBy==='volume'?b.volume-a.volume:sortBy==='news'?b.news_score-a.news_score:b.change-a.change);
    document.getElementById('heatmapGrid').innerHTML=sorted.slice(0,40).map(coin=>{
      const pct=coin.change, int=Math.min(1,Math.abs(pct)/10);
      const bg=pct>=0?`rgba(0,${Math.round(100+130*int)},${Math.round(80*int)},${0.18+0.5*int})`:`rgba(${Math.round(180+75*int)},${Math.round(30*int)},${Math.round(60*int)},${0.18+0.5*int})`;
      const sym=coin.symbol.replace('/USDT','');
      const nc=coin.news_score>0.3?'🟢':coin.news_score<-0.3?'🔴':'⬜';
      const cls=(coin.in_pos?' inpos':'')+(coin.short?' inshort':'');
      return `<div class="hm-cell${cls}" style="background:${bg}" onclick="openChart('${escJS(coin.symbol)}')">
        <div class="hm-symbol">${sym}</div>
        <div class="hm-pct">${pct>=0?'+':''}${pct.toFixed(1)}%</div>
        <div class="hm-news">${nc}</div>
      </div>`;
    }).join('');
  }catch(e){document.getElementById('heatmapGrid').innerHTML='<div class="empty" style="grid-column:span 5">'+QI18n.t('err_generic')+': '+esc(String(e))+'</div>';}
}

// ── Chart ────────────────────────────────────────────────────────────
async function loadChart(){
  const sym=document.getElementById('chartSym').value.trim().replace('-','/').toUpperCase();
  const tf=document.getElementById('chartTf').value;
  document.getElementById('chartBadge').textContent=sym+' '+tf;
  const chartEl=document.getElementById('tvChart');
  chartEl.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--sub);font-size:12px">⏳ Lade Chart...</div>';
  try{
    const data=await(await fetch(`/api/ohlcv/${encodeURIComponent(sym.replace('/','-'))}?tf=${encodeURIComponent(tf)}&limit=200`)).json();
    if(data.error){chartEl.innerHTML=`<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:12px">${esc(data.error)}</div>`;return;}
    renderTVChart(data, chartEl);
    // News
    try{
      const ndata=await(await fetch(`/api/v1/news/${encodeURIComponent(sym.replace('/USDT',''))}`)).json();
      const nScore=typeof ndata.score==='number'?ndata.score:0;
      const nCount=typeof ndata.count==='number'?ndata.count:0;
      if(ndata.headline&&ndata.headline!=='—'){
        const nc=nScore>=0?'var(--green)':'var(--red)';
        document.getElementById('newsFeed').innerHTML=`<div class="news-item">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:11px;font-weight:700;color:${nc}">${nScore>=0?'+':''}${nScore.toFixed(2)} Score</span>
            <span style="font-size:10px;color:var(--sub)">${nCount} Artikel</span>
          </div>
          <div style="font-size:11px;line-height:1.6">${esc(String(ndata.headline||''))}</div>
        </div>`;
        document.getElementById('cNews').textContent=(nScore>=0?'+':'')+nScore.toFixed(2);
        document.getElementById('cNews').style.color=nc;
      }
    }catch(e){}
    // On-chain
    try{
      const oc=await(await fetch(`/api/v1/onchain/${encodeURIComponent(sym.replace('/USDT',''))}`)).json();
      const ocScore=typeof oc.score==='number'?oc.score:0;
      document.getElementById('cOnchain').textContent=(ocScore>=0?'+':'')+ocScore.toFixed(2);
      document.getElementById('cOnchain').style.color=ocScore>=0?'var(--green)':'var(--red)';
    }catch(e){}
    const sig=lastData?.signal_log?.find(s=>s.symbol===sym);
    if(sig){
      document.getElementById('cRSI').textContent=sig.rsi||'—';
      document.getElementById('cMTF').textContent=sig.mtf_desc||'—';
      document.getElementById('cVol').textContent=sig.confidence?Math.round(sig.confidence*100)+'%':'—';
    }
  }catch(e){chartEl.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:12px">'+QI18n.t('err_generic')+': '+esc(String(e))+'</div>';}
}
function openChart(sym){document.getElementById('chartSym').value=sym;nav('chart',document.getElementById('nb-chart'));loadChart();}
let _tvChartInst = null; // Track LightweightCharts instance for cleanup
function renderTVChart(data, el){
  // Cleanup previous chart instance to prevent memory leak
  if(_tvChartInst){try{_tvChartInst.remove();}catch(e){}_tvChartInst=null;}
  el.innerHTML='';
  if(!data.ohlcv?.length) return;
  try {
    const chart=LightweightCharts.createChart(el,{
      layout:{background:{color:'#020408'},textColor:'#2e3d5a'},
      grid:{vertLines:{color:'rgba(255,255,255,.025)'},horzLines:{color:'rgba(255,255,255,.025)'}},
      rightPriceScale:{borderColor:'rgba(255,255,255,.04)'},
      timeScale:{borderColor:'rgba(255,255,255,.04)',timeVisible:true},
      handleScroll:true,handleScale:true,
    });
    _tvChartInst = chart;
    // LightweightCharts v4 compatibility: use addSeries if addCandlestickSeries doesn't exist
    let cs, vs;
    if(typeof chart.addCandlestickSeries === 'function'){
      cs=chart.addCandlestickSeries({upColor:'#00ff88',downColor:'#ef4444',borderUpColor:'#00ff88',borderDownColor:'#ef4444',wickUpColor:'#00ff88',wickDownColor:'#ef4444'});
    } else {
      cs=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#00ff88',downColor:'#ef4444',borderUpColor:'#00ff88',borderDownColor:'#ef4444',wickUpColor:'#00ff88',wickDownColor:'#ef4444'});
    }
    if(typeof chart.addHistogramSeries === 'function'){
      vs=chart.addHistogramSeries({color:'rgba(0,255,136,.2)',priceFormat:{type:'volume'},priceScaleId:'vol'});
    } else {
      vs=chart.addSeries(LightweightCharts.HistogramSeries,{color:'rgba(0,255,136,.2)',priceFormat:{type:'volume'},priceScaleId:'vol'});
    }
    chart.priceScale('vol').applyOptions({scaleMargins:{top:0.85,bottom:0}});
    cs.setData(data.ohlcv.map(r=>({time:Math.floor(r[0]/1000),open:r[1],high:r[2],low:r[3],close:r[4]})));
    vs.setData(data.ohlcv.map(r=>({time:Math.floor(r[0]/1000),value:r[5],color:r[4]>=r[1]?'rgba(0,255,136,.25)':'rgba(255,61,113,.25)'})));
    if(data.trades?.length){
      const mk=[]; data.trades.forEach(t=>{
        if(t.opened) mk.push({time:Math.floor(new Date(t.opened).getTime()/1000),position:'belowBar',color:'#00ff88',shape:'arrowUp',text:'K'});
        if(t.closed) mk.push({time:Math.floor(new Date(t.closed).getTime()/1000),position:'aboveBar',color:(t.pnl||0)>=0?'#00ff88':'#ef4444',shape:'arrowDown',text:fmtS(t.pnl||0,0)});
      });
      mk.sort((a,b)=>a.time-b.time); cs.setMarkers(mk);
    }
    chart.timeScale().fitContent();
  } catch(e) {
    console.error('Chart render error:', e);
    el.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:12px">'+QI18n.t('err_generic')+': '+esc(String(e.message||e))+'</div>';
  }
}

// ── Backtest ─────────────────────────────────────────────────────────
function runBacktest(){
  const candles=parseInt(document.getElementById('btCandles')?.value, 10);
  const sl=parseFloat(document.getElementById('btSL')?.value);
  const tp=parseFloat(document.getElementById('btTP')?.value);
  const vote=parseFloat(document.getElementById('btVote')?.value);
  if(isNaN(candles)||isNaN(sl)||isNaN(tp)||isNaN(vote)){toast(QI18n.t('err_generic'),'warning');return;}
  if(!socket.connected){toast('⚠️ '+QI18n.t('conn_disconnected'),'warning');return;}
  const bts=document.getElementById('btStatus'); if(bts) bts.textContent=QI18n.t('running_bt');
  const btb=document.getElementById('btBtn'); if(btb) btb.disabled=true;
  const btr=document.getElementById('btResultSection'); if(btr) btr.style.display='none';
  socket.emit('run_backtest',{
    symbol:(document.getElementById('btSym')?.value||'').trim(),
    timeframe:document.getElementById('btTf')?.value||'1h',
    candles:candles,
    sl:sl/100,
    tp:tp/100,
    vote:vote/100,
  });
}
async function loadBtHistory(){
  try{
    const data=await(await fetch('/api/backtest/history',{headers:{'Authorization':'Bearer '+(_jwtToken||'')}})).json();
    if(!data||!data.length){
      const el1=document.getElementById('btHistory'); if(el1) el1.innerHTML='<div class="empty" style="padding:8px">—</div>';
      const el2=document.getElementById('btHistoryList'); if(el2) el2.innerHTML='<div class="empty"><div class="empty-ico">📊</div>'+QI18n.t('empty_no_backtests')+'</div>';
      return;
    }
    // Compact view (home/backtest tab inline)
    const el1=document.getElementById('btHistory');
    if(el1) el1.innerHTML=data.map(r=>`<div style="background:var(--bg2);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:12px;font-weight:700">${esc(String(r.symbol||''))} ${esc(String(r.timeframe||''))}</div>
        <div style="font-size:10px;color:var(--sub)">${esc(String(r.candles||''))} ${QI18n.t('candles_label')} · ${esc(String(r.total_trades||''))} Trades</div></div>
      <div style="text-align:right">
        <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:${(r.win_rate||0)>50?'var(--green)':'var(--red)'}">${(r.win_rate||0).toFixed(1)}%</div>
        <div style="font-size:10px;font-family:var(--mono);color:${(r.total_pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(r.total_pnl||0)} USDT</div>
      </div></div>`).join('');
    // Detailed view (backtest history list)
    const el2=document.getElementById('btHistoryList');
    if(el2) el2.innerHTML=data.slice(0,10).map(b=>`
      <div style="padding:8px 0;border-bottom:1px solid var(--muted);display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center">
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--txt)">${esc(String(b.symbol||''))} · ${esc(String(b.timeframe||''))}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${esc(String(b.total_trades||''))} Trades · ${esc(String(b.candles||''))} ${QI18n.t('candles_label')} · ${esc(String(b.run_date?.slice(0,10)||''))}</div>
        </div>
        <div style="text-align:right">
          <div style="font-family:var(--mono);font-size:13px;color:${b.return_pct>0?'var(--jade)':'var(--red)'}">${b.return_pct}%</div>
          <div style="font-size:10px;color:var(--sub)">WR: ${b.win_rate}%</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:10px;color:var(--dim)">Sharpe</div>
          <div style="font-family:var(--mono);font-size:12px;color:var(--blue)">${b.sharpe_ratio||'—'}</div>
        </div>
      </div>`).join('');
  }catch(e){ console.warn('Backtest history load failed:', e); }
}

// ── Tax ──────────────────────────────────────────────────────────────
async function loadTax(){
  const taxYearEl=document.getElementById('taxYear');
  const taxMethodEl=document.getElementById('taxMethod');
  if(!taxYearEl || !taxMethodEl){
    toast('⚠️ Tax-Ansicht ist aktuell nicht verfügbar.','warning');
    return;
  }
  const year=taxYearEl.value||new Date().getFullYear();
  const method=taxMethodEl.value;
  try{
    const data=await(await fetch(`/api/tax_report?year=${encodeURIComponent(year)}&method=${encodeURIComponent(method)}`)).json();
    if(data.error){toast(data.error,'error');return;}
    const s=data.summary;
    const taxResultEl=document.getElementById('taxResult');
    const taxGainsEl=document.getElementById('taxGains');
    const taxLossesEl=document.getElementById('taxLosses');
    const taxNetEl=document.getElementById('taxNet');
    const taxTaxableEl=document.getElementById('taxTaxable');
    const taxFeesEl=document.getElementById('taxFees');
    const taxCountEl=document.getElementById('taxCount');
    const taxWarnBarEl=document.getElementById('taxWarnBar');
    const taxWarnTxtEl=document.getElementById('taxWarnTxt');
    const taxTableEl=document.getElementById('taxTable');
    if(!taxResultEl||!taxGainsEl||!taxLossesEl||!taxNetEl||!taxTaxableEl||!taxFeesEl||!taxCountEl||!taxWarnBarEl||!taxTableEl){
      toast('⚠️ Tax-UI-Elemente fehlen im Dashboard.','warning');
      return;
    }
    taxResultEl.style.display='block';
    taxGainsEl.textContent=fmtS(s.total_gains)+' USDT';
    taxLossesEl.textContent=fmtS(s.total_losses)+' USDT';
    taxNetEl.textContent=fmtS(s.net_pnl)+' USDT'; taxNetEl.style.color=clr(s.net_pnl);
    taxTaxableEl.textContent=fmt(s.taxable_gains)+' USDT';
    taxFeesEl.textContent=fmt(s.total_fees)+' USDT';
    taxCountEl.textContent=s.trade_count+'T ('+s.win_count+'G / '+s.loss_count+'V)';
    if(s.taxable_gains>600){taxWarnBarEl.style.display='flex'; if(taxWarnTxtEl) taxWarnTxtEl.textContent=QI18n.t('msg_tax_warn');}
    else taxWarnBarEl.style.display='none';
    taxTableEl.innerHTML=data.gains.slice(0,30).map(g=>
      `<div style="display:grid;grid-template-columns:80px 1fr 1fr;gap:6px;padding:6px 0;border-bottom:1px solid var(--line);font-size:10px;font-family:var(--mono)">
        <span style="color:var(--sub)">${esc(String(g.date||''))}</span><span>${esc(String(g.symbol||''))}</span>
        <span style="color:var(--green);text-align:right">${fmtS(g.net_pnl)}</span></div>`).join('')||'<div class="empty" style="padding:8px">—</div>';
  }catch(e){toast(QI18n.t('err_generic')+': '+e,'error');}
}
function exportTaxCSV(){const y=document.getElementById('taxYear')?.value||new Date().getFullYear();window.open(`/api/tax_report?year=${encodeURIComponent(y)}&format=csv`);}
function exportCSV(){window.open('/api/export/csv');}
function exportJSON(){window.open('/api/export/json');}

// ── Bot controls ─────────────────────────────────────────────────────
function _emitSafe(event, data, opts){
  const silent = Boolean(opts && opts.silent);
  if(!socket || !socket.connected){
    if(!silent) toast('⚠️ '+QI18n.t('conn_disconnected')+' – '+QI18n.t('msg_socket_reconnect'),'warning');
    return false;
  }
  if(data!==undefined) socket.emit(event,data); else socket.emit(event);
  return true;
}
async function _botControlFallback(action){
  try{
    await _postTradingEndpoint('/api/v1/trading/control',{action});
    if(action==='start') toast('▶ Bot gestartet (HTTP-Fallback)','success');
    if(action==='stop') toast('■ Bot gestoppt (HTTP-Fallback)','success');
    if(socket && socket.connected) socket.emit('request_state');
    refreshTradingInsights(true);
    return true;
  }catch(e){
    toast('❌ Bot-Control fehlgeschlagen: '+e,'error');
    return false;
  }
}
function startBot(){
  executeTradingControl('start', {preferSocket:true});
}
function stopBot(){
  executeTradingControl('stop', {preferSocket:true});
}
function pauseBot(){_emitSafe('pause_bot');}

// ── Exchange Selector ─────────────────────────────────────────────────
let _selectedExchange = '';

function selectExchange(ex, el) {
  if (!ex) return;
  _selectedExchange = ex;
  // Highlight active button
  document.querySelectorAll('.ex-btn').forEach(b => b.classList.remove('active'));
  if (!el) el = document.getElementById('ex-btn-' + ex);
  if (el) el.classList.add('active');
  // Sync settings dropdown
  const sEl = document.getElementById('sExchange');
  if (sEl) sEl.value = ex;
  // Update badge + button label
  const badge = document.getElementById('activeExBadge');
  if (badge) badge.textContent = ex.toUpperCase();
  const lbl = document.getElementById('exStartLabel');
  const running = document.getElementById('statusBadge')?.classList.contains('run');
  if (lbl) lbl.textContent = running ? 'Exchange wechseln & neu starten' : 'Bot mit ' + ex.toUpperCase() + ' starten';
}

function startBotWithExchange() {
  const ex = _selectedExchange || document.getElementById('sExchange')?.value;
  if (!ex) { toast('⚠️ Bitte zuerst eine Exchange wählen', 'warning'); return; }
  // Emit dedicated select_exchange event (available to all auth users), then start bot
  _emitSafe('select_exchange', { exchange: ex });
  setTimeout(() => { _emitSafe('start_bot'); }, 400);
  toast('🚀 Starte Bot auf ' + ex.toUpperCase() + '…', 'info');
}

function _initExchangeSelector(activeEx, keyStates) {
  // keyStates: {cryptocom: true, binance: false, ...}
  const exchanges = ['cryptocom','binance','bybit','okx','kucoin','kraken','huobi','coinbase'];
  exchanges.forEach(ex => {
    const btn = document.getElementById('ex-btn-' + ex);
    if (!btn) return;
    if (keyStates && keyStates[ex]) btn.classList.add('has-keys');
    else btn.classList.remove('has-keys');
  });
  if (activeEx) selectExchange(activeEx, document.getElementById('ex-btn-' + activeEx));
}
const _closeHistory = [];
let _undoTimeout = null;

function closePos(sym){
  if(!confirm(QI18n.t('confirm_close_pos').replace('{sym}',sym))) return;
  if(!_emitSafe('close_position',{symbol:sym})){
    _postTradingEndpoint('/api/v1/trading/close-position',{symbol:sym})
      .then(()=>{toast(`✅ ${sym} geschlossen`,'success'); refreshTradingInsights(true);})
      .catch((e)=>toast('❌ Position schließen fehlgeschlagen: '+e,'error'));
  }
  _closeHistory.push(sym);
  showUndoBar(sym);
}

function showUndoBar(sym){
  const bar = document.getElementById('undoBar');
  const msg = document.getElementById('undoMsg');
  if(msg) msg.textContent = sym + ' closed';
  if(bar) bar.style.display = 'flex';
  clearTimeout(_undoTimeout);
  _undoTimeout = setTimeout(()=>{ bar.style.display='none'; }, 8000);
}

function undoClose(){
  if(!_closeHistory.length) return;
  const sym = _closeHistory.pop();
  _emitSafe('undo_close', {symbol: sym});
  const undoBar = document.getElementById('undoBar');
  if(undoBar) undoBar.style.display = 'none';
  clearTimeout(_undoTimeout);
  toast('↩ '+QI18n.t('msg_undo_close')+' '+sym,'info');
}
function forceTrain(){if(_emitSafe('force_train')) toast('🧠 '+QI18n.t('ai_training')+'...','info');}
function forceOptimize(){if(_emitSafe('force_optimize')) toast('🔬 '+QI18n.t('toast_optimize'),'info');}
function forceGenetic(){if(_emitSafe('force_genetic')) toast('🧬 '+QI18n.t('toast_genetic'),'info');}
function resetAI(){if(confirm(QI18n.t('confirm_reset_ai'))) _emitSafe('reset_ai');}
function manualBackup(){_emitSafe('manual_backup');}
function sendReport(){_emitSafe('send_daily_report');}
function resetCB(){_emitSafe('reset_circuit_breaker');}
function refreshDom(){if(_emitSafe('update_dominance')) toast(QI18n.t('dominance')+'...','info');}
function scanArb(){if(_emitSafe('scan_arbitrage')) toast(QI18n.t('btn_arbitrage')+'...','info');}
function addAlert(){
  const sym=document.getElementById('alertSym').value.trim().toUpperCase();
  const target=parseFloat(document.getElementById('alertTarget').value);
  const dir=document.getElementById('alertDir').value;
  if(!sym||isNaN(target)||target<=0){toast(QI18n.t('err_symbol_price'),'error');return;}
  _emitSafe('add_price_alert',{symbol:sym,target,direction:dir});
  document.getElementById('alertTarget').value='';
}
function deleteAlert(id){_emitSafe('delete_price_alert',{id});}

// ── Settings ─────────────────────────────────────────────────────────

function changeLang(lang){
  QI18n.setLang(lang);
  _emitSafe('update_config',{language:lang});
  toast(QLANG_FLAGS[lang]+' '+QLANG_NAMES[lang],'info');
}
function applyPreset(name){
  const p={conservative:{sl:1.5,tp:4,maxTrades:3,interval:120,conf:60},
           balanced:{sl:2.5,tp:6,maxTrades:5,interval:60,conf:55},
           aggressive:{sl:4,tp:10,maxTrades:8,interval:30,conf:50}}[name];
  if(!p) return;
  document.getElementById('sSL').value=p.sl;
  document.getElementById('sTP').value=p.tp;
  document.getElementById('sMaxTrades').value=p.maxTrades;
  document.getElementById('sInterval').value=p.interval;
  document.getElementById('sAiConf').value=p.conf;
  toast('✅ '+QI18n.t('msg_preset_loaded')+': "'+name+'"','success');
}
function saveSettings(){
  const _pf=v=>{const n=parseFloat(v);return isNaN(n)?0:n;};
  const _pi=v=>{const n=parseInt(v,10);return isNaN(n)?0:n;};
  const sl=_pf(document.getElementById('sSL').value);
  const tp=_pf(document.getElementById('sTP').value);
  if(sl<=0||tp<=0||sl>=tp){toast(QI18n.t('err_sltp_invalid'),'error');return;}
  _emitSafe('update_config',{
    stop_loss_pct:sl/100,
    take_profit_pct:tp/100,
    max_open_trades:_pi(document.getElementById('sMaxTrades').value),
    scan_interval:_pi(document.getElementById('sInterval').value),
    paper_trading:document.getElementById('sPaper').checked,
    trailing_stop:document.getElementById('sTrailing').checked,
    ai_min_confidence:_pf(document.getElementById('sAiConf').value)/100,
    circuit_breaker_losses:_pi(document.getElementById('sCBLosses').value),
    circuit_breaker_min:_pi(document.getElementById('sCBMin').value),
    max_spread_pct:_pf(document.getElementById('sSpread').value),
    use_fear_greed:document.getElementById('sFG').checked,
    ai_use_kelly:document.getElementById('sKelly').checked,
    mtf_enabled:document.getElementById('sMTF').checked,
    use_news:document.getElementById('sNews').checked,
    use_onchain:document.getElementById('sOnchain').checked,
    use_dominance:document.getElementById('sDom').checked,
    use_anomaly:document.getElementById('sAnomaly').checked,
    use_dca:document.getElementById('sDCA').checked,
    dca_max_levels:_pi(document.getElementById('sDCALvl').value),
    use_partial_tp:document.getElementById('sPartialTP').checked,
    use_shorts:document.getElementById('sShorts').checked,
    use_arbitrage:document.getElementById('sArb').checked,
    arb_min_spread_pct:_pf(document.getElementById('sArbSpread').value),
    genetic_enabled:document.getElementById('sGenetic').checked,
    rl_enabled:document.getElementById('sRL').checked,
    backup_enabled:document.getElementById('sBackup').checked,
    portfolio_goal:_pf(document.getElementById('sGoal').value)||0,
    news_block_score:_pf(document.getElementById('sNewsBlock').value),
    virginie_enabled:document.getElementById('sVirginieEnabled').checked,
    virginie_primary_control:document.getElementById('sVirginiePrimary').checked,
    virginie_autonomy_weight:_pf(document.getElementById('sVirginieAutonomy').value),
    virginie_min_score:_pf(document.getElementById('sVirginieMinScore').value),
    virginie_max_risk_penalty:_pf(document.getElementById('sVirginieMaxRisk').value),
    exchange:document.getElementById('sExchange')?.value||undefined,
  });
}
function saveKeys(){
  // Legacy-Alias: API-Key-Verwaltung ist jetzt unter Exchanges (#sec-exchanges).
  const nbEx=document.getElementById('nb-ex');
  if(typeof nav==='function'&&nbEx){nav('exchanges',nbEx);}
}
function saveDiscord(){
  _emitSafe('update_discord',{webhook:document.getElementById('sDiscord').value,
    report_hour:parseInt(document.getElementById('sReportHour').value, 10)});
}
async function createToken(){
  try{
    const res=await fetch('/api/v1/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:'dashboard'})});
    const data=await res.json();
    const box=document.getElementById('apiTokenBox');
    box.style.display='block'; box.textContent=data.token||'—';
    toast('🔑 '+QI18n.t('msg_token_created')+' ('+data.expires_hours+QI18n.t('msg_valid_hours')+')','success');
  }catch(e){toast(QI18n.t('err_generic')+': '+e,'error');}
}

// ── Wizard ───────────────────────────────────────────────────────────
function showWizard(){document.getElementById('wizardOverlay').style.display='flex';wizStep=0;updateWizDots();}
function wizNext(){
  if(wizStep<4){document.getElementById('wz'+wizStep).classList.remove('active');wizStep++;document.getElementById('wz'+wizStep).classList.add('active');updateWizDots();}
}
function updateWizDots(){for(let i=0;i<5;i++) document.getElementById('wd'+i).className='wd'+(i<=wizStep?' done':'');}
function wizSelEx(ex,el){document.querySelectorAll('#wz1 .btn').forEach(b=>{b.style.borderColor='rgba(212,175,55,.15)';b.style.background='';});el.style.borderColor='var(--jade)';el.style.background='rgba(212,175,55,.08)';wizEx=ex;document.getElementById('sExchange').value=ex;selectExchange(ex,document.getElementById('ex-btn-'+ex));}
function wizSaveKeys(){_emitSafe('save_api_keys',{api_key:document.getElementById('wzKey').value,secret:document.getElementById('wzSecret').value,exchange:wizEx});wizNext();}
function wizPreset(name,el){document.querySelectorAll('#wz3 .btn').forEach(b=>b.style.opacity='.5');el.style.opacity='1';applyPreset(name);}
function wizFinish(){document.getElementById('wizardOverlay').style.display='none';saveSettings();_storage.set('trevlix_wiz','1');toast(QI18n.t('wiz_ready'),'success');}

// ── Socket events (with listener cleanup to prevent duplicates on reconnect) ──
// Remove all previous listeners before registering to prevent accumulation
const _socketEvents = ['connect','connect_error','disconnect','auth_error',
  'update','ai_update','genetic_update','status','trade','price_alert','backtest_result',
  'update_status','update_result','system_analytics','healing_update','revenue_update',
  'cluster_update','ai_model_updated','exchange_update','virginie_chat_message','virginie_chat_error','virginie_forecast'];
_socketEvents.forEach(ev => socket.off(ev));

function _setConnStatus(state){
  const el=document.getElementById('connStatus');
  if(!el)return;
  el.className='conn-status '+state;
  el.title=state==='connected'?QI18n.t('conn_connected'):state==='reconnecting'?QI18n.t('conn_reconnecting'):QI18n.t('conn_disconnected');
}
const LIVE_STATE_PULL_MS = 4000;
let _liveStatePullTimer = null;
function _startLiveStatePull(){
  if(_liveStatePullTimer) return;
  _liveStatePullTimer = setInterval(()=>{
    if(document.hidden) return;
    if(socket && socket.connected) socket.emit('request_state');
  }, LIVE_STATE_PULL_MS);
}
function _stopLiveStatePull(){
  if(!_liveStatePullTimer) return;
  clearInterval(_liveStatePullTimer);
  _liveStatePullTimer = null;
}

socket.on('connect',()=>{
  _setConnStatus('connected');
  addLog(QI18n.t('dashboard_connected'),'success','system');
  toast('📡 '+QI18n.t('msg_dashboard_conn'),'success');
  // Nach Verbindung sofort State anfragen (bei Reconnect)
  socket.emit('request_state');
  _startLiveStatePull();
});
socket.on('connect_error',(err)=>{
  _setConnStatus('reconnecting');
  addLog(QI18n.t('msg_socket_reconnect')+': '+(err&&err.message||'Unknown'),'error','system');
  toast('⚠️ '+QI18n.t('msg_socket_reconnect'),'warning');
});
socket.on('disconnect',(reason)=>{
  _setConnStatus('disconnected');
  addLog(QI18n.t('dashboard_disconnected')+' ('+reason+')','error','system');
  toast('⚠️ '+QI18n.t('dashboard_disconnected'),'warning');
  _stopLiveStatePull();
});
socket.on('auth_error',(d)=>{
  addLog(QI18n.t('msg_auth_error')+': '+(d&&d.msg||QI18n.t('msg_not_authenticated')),'error','system');
  setTimeout(()=>location.href='/login',2000);
});
socket.on('update', d=>{
  if(d){
    updateUI(d);
    if(d.user_role) applyStateToRole(d);
    // Initialize exchange selector from server state
    if(d.exchange && !_selectedExchange) {
      _initExchangeSelector(d.exchange, d.exchange_key_states || {});
    } else if(d.exchange) {
      // Always keep has-keys markers in sync
      _initExchangeSelector(_selectedExchange || d.exchange, d.exchange_key_states || {});
    }
    // Auto-refresh stats if stats tab is active
    const statsTab=document.getElementById('sec-stats');
    if(statsTab && statsTab.classList.contains('active')) updateStats(d);
  }
});
document.addEventListener('visibilitychange', ()=>{
  if(document.hidden) return;
  if(socket && socket.connected) socket.emit('request_state');
  refreshTradingInsights(true);
});
setInterval(()=>{ if(!document.hidden) refreshTradingInsights(); }, 10000);
socket.on('ai_update', ai=>{if(ai) updateAI(ai);});
socket.on('genetic_update', g=>{
  if(!g) return;
  const gf=document.getElementById('genFitness');
  const gc=document.getElementById('genGenCount');
  if(gf) gf.textContent=(g.fitness||0).toFixed(3);
  if(gc) gc.textContent='Gen.'+(g.gen||0)+'/'+(g.total||0);
});
socket.on('status', d=>{
  if(!d||!d.msg) return;
  const msg = d.key ? QI18n.t(d.key) : d.msg;
  toast(msg, d.type||'info');
  addLog(msg, d.type||'info', 'system');
});
socket.on('trade', d=>{
  if(!d) return;
  const won=(d.pnl||0)>=0;
  const msg=d.type==='buy'?`🟢 ${QI18n.t('trade_buy')} ${d.symbol} @ ${d.price}`:
    `${won?'✅':'❌'} ${QI18n.t('trade_sell')} ${d.symbol} | ${fmtS(d.pnl||0)} USDT`;
  addLog(msg, d.type==='buy'?'success':(won?'success':'error'), 'trade');
  toast(msg, d.type==='buy'?'success':(won?'success':'warning'));
  _checkPush(d);
});
socket.on('price_alert', d=>{
  if(!d) return;
  toast(`🔔 Alert: ${d.symbol} @ ${d.price}`,'warning');
  addLog(`🔔 ${QI18n.t('alert_triggered')}: ${d.symbol}`,'warning','system');
});
socket.on('backtest_result', d=>{
  const btBtnEl=document.getElementById('btBtn');
  const btStatusEl=document.getElementById('btStatus');
  const btResultSectionEl=document.getElementById('btResultSection');
  const btBadgeEl=document.getElementById('btBadge');
  if(btBtnEl) btBtnEl.disabled=false;
  if(!d) return;
  if(d.error){if(btStatusEl) btStatusEl.textContent='❌ '+d.error;toast(d.error,'error');return;}
  if(btStatusEl) btStatusEl.textContent='';
  if(btResultSectionEl) btResultSectionEl.style.display='block';
  if(btBadgeEl) btBadgeEl.textContent=d.symbol+' '+d.timeframe;
  const btEl=document.getElementById('btWR'); if(btEl){btEl.textContent=d.win_rate+'%';btEl.style.color=d.win_rate>50?'var(--green)':'var(--red)';}
  const btPnl=document.getElementById('btPnl'); if(btPnl){btPnl.textContent=fmtS(d.total_pnl);btPnl.style.color=clr(d.total_pnl);}
  const btPF=document.getElementById('btPF'); if(btPF){btPF.textContent=d.profit_factor;btPF.style.color=d.profit_factor>1.2?'var(--green)':'var(--red)';}
  const btDDEl=document.getElementById('btDD'); if(btDDEl) btDDEl.textContent=d.max_drawdown+'%';
  if(btChartInst){try{btChartInst.destroy();}catch(e){} btChartInst=null;}
  if(d.equity_curve?.length){
    const cc=d.return_pct>=0?'#00ff88':'#ef4444';
    const btChartEl=document.getElementById('btChart');
    if(btChartEl) btChartInst=new Chart(btChartEl,{type:'line',
      data:{labels:d.equity_curve.map(e=>e.time?.slice(5,16)||''),
        datasets:[{data:d.equity_curve.map(e=>e.value),borderColor:cc,backgroundColor:cc==='#00ff88'?'rgba(0,255,136,.06)':'rgba(255,61,113,.06)',borderWidth:2,fill:true,tension:.4,pointRadius:0}]},
      options:cBase});
  }
  toast(`✅ Backtest: ${QI18n.t('stat_winrate')} ${d.win_rate}% | PnL ${fmtS(d.total_pnl)} USDT`,'success');
  addLog(`Backtest ${d.symbol}: ${QI18n.t('stat_winrate')} ${d.win_rate}% PnL ${fmtS(d.total_pnl)}`,'success','system');
});
socket.on('virginie_chat_message', d=>{
  _appendVirginieChatMessage(d);
  _virginieChat.sending=false;
  _virginieChat.pendingMessage='';
  if(_virginieChat.socketTimer){clearTimeout(_virginieChat.socketTimer);_virginieChat.socketTimer=null;}
});
socket.on('virginie_chat_error', d=>{
  _virginieChat.sending=false;
  _virginieChat.pendingMessage='';
  if(_virginieChat.socketTimer){clearTimeout(_virginieChat.socketTimer);_virginieChat.socketTimer=null;}
  toast('⚠️ '+(d&&d.error?d.error:'Chat-Fehler'),'warning');
});
socket.on('virginie_forecast', d=>{
  if(!d) return;
  _virginieForecastFeed.unshift(d);
  if(_virginieForecastFeed.length > 25) _virginieForecastFeed.length = 25;
  _renderVirginieForecastFeed();
});


// ── GitHub Updater ───────────────────────────────────────────────────
function checkUpdate(){
  if(_emitSafe('check_update')) toast('🔍 '+QI18n.t('checking_github'),'info');
}
function applyUpdate(){
  if(!confirm(QI18n.t('confirm_install_update'))) return;
  if(_emitSafe('apply_update')) toast('⬆ '+QI18n.t('installing_update'),'info');
}
function rollbackUpdate(){
  if(!confirm(QI18n.t('confirm_rollback'))) return;
  _emitSafe('rollback_update');
}
function renderUpdateStatus(d){
  document.getElementById('updateCurrent').textContent = d.current || d.current_version || '—';
  document.getElementById('updateLatest').textContent  = d.latest  || d.latest_version  || '—';
  document.getElementById('updateRepo').textContent    = d.repo   || 'DEIN_USER/trevlix';
  document.getElementById('updateBranch').textContent  = d.branch || 'main';
  document.getElementById('updateLastCheck').textContent = d.last_check || '—';
  const avail = d.update_available;
  document.getElementById('updateAvailableBanner').style.display = avail ? 'block' : 'none';
  document.getElementById('updateUpToDate').style.display        = (!avail && d.latest_version && d.latest_version!=='—') ? 'flex' : 'none';
  document.getElementById('btnApplyUpdate').disabled = !avail;
  if(d.changelog){
    const el = document.getElementById('updateChangelog');
    if(el){el.style.display='block'; el.textContent=d.changelog;}
    const elShort = document.getElementById('updateChangelogShort');
    if(elShort && d.changelog) elShort.textContent = d.changelog.split('\n')[0].slice(0,60);
  }
}
socket.on('update_status', d => { if(!d) return; renderUpdateStatus(d); toast(d.update_available ? '🎉 '+QI18n.t('msg_update_avail')+' v'+d.latest : '✅ '+QI18n.t('msg_up_to_date'), d.update_available?'success':'info'); });
socket.on('update_result', d => { if(!d) return; toast(d.status==='success'?'✅ '+QI18n.t('msg_update_installed'):'⚠ '+QI18n.t('msg_update_partial'), d.status==='success'?'success':'warning'); if(d.status==='success') setTimeout(()=>location.reload(),3000); });


// ── Theme Toggle ─────────────────────────────────────────────────────────
function toggleTheme(){
  const root = document.documentElement;
  const isLight = root.getAttribute('data-theme') === 'light';
  root.setAttribute('data-theme', isLight ? 'dark' : 'light');
  const themeBtn = document.getElementById('themeBtn');
  if(themeBtn) themeBtn.textContent = isLight ? '🌙' : '☀️';
  _storage.set('trevlix_theme', isLight ? 'dark' : 'light');
}
// Restore theme
(function(){
  const saved = _storage.get('trevlix_theme');
  if(saved === 'light'){
    document.documentElement.setAttribute('data-theme','light');
    setTimeout(()=>{const b=document.getElementById('themeBtn');if(b)b.textContent='☀️';},100);
  }
})();

// ── Copy-Trading ──────────────────────────────────────────────────────────
async function registerFollower(){
  const name  = document.getElementById('ctName').value.trim();
  const url   = document.getElementById('ctUrl').value.trim();
  const scale = parseFloat(document.getElementById('ctScale').value) || 1.0;
  if(!name || !url){ toast(QI18n.t('err_name_url'),'warning'); return; }
  const r = await fetch('/api/v1/copy-trading/register', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({name, webhook_url:url, scale})
  });
  const d = await r.json();
  if(d.token){
    toast('✅ '+QI18n.t('msg_follower_reg')+' '+d.token.slice(0,12)+'…','success');
    loadFollowers();
  } else { toast(QI18n.t('err_generic')+': '+JSON.stringify(d),'error'); }
}

async function loadFollowers(){
  try {
    const r = await fetch('/api/v1/copy-trading/followers',{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const el = document.getElementById('followersList');
    if(!el) return;
    if(!d.followers || !d.followers.length){ el.innerHTML='<div style="font-size:11px;color:var(--sub)">'+QI18n.t('empty_no_followers')+'</div>'; return; }
    el.innerHTML = d.followers.map(f=>`
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--muted);font-size:12px">
        <span style="color:var(--txt)">${esc(String(f.name||''))}</span>
        <span style="color:var(--sub)">×${esc(String(f.scale||''))} · ${esc(String(f.signals||''))} Signale</span>
        <span style="color:${f.active?'var(--jade)':'var(--red)'}">${f.active?QI18n.t('label_active'):QI18n.t('label_inactive')}</span>
      </div>`).join('');
  } catch(e){}
}

async function testCopySignal(){
  try {
    const r = await fetch('/api/v1/copy-trading/test',{method:'POST',headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    if(r.ok) toast('📡 '+QI18n.t('msg_test_signal'),'info');
    else toast(QI18n.t('err_generic'),'error');
  } catch(e){ toast(QI18n.t('err_network')+': '+e.message,'error'); }
}

// ── Pine Script ──────────────────────────────────────────────────────────
async function downloadPineScript(){
  const sym = encodeURIComponent((document.getElementById('pineSymbol')?.value || 'BTCUSDT').replace('/',''));
  try {
    const r = await fetch(`/api/v1/pine-script?symbol=${sym}`,{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    if(!r.ok){ toast(QI18n.t('err_generic'),'error'); return; }
    const txt = await r.text();
    const blob = new Blob([txt], {type:'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href=url; a.download=`trevlix_${sym.toLowerCase()}.pine`; a.click();
    URL.revokeObjectURL(url);
    toast('⬇ '+QI18n.t('msg_pine_download'),'success');
  } catch(e){ toast(QI18n.t('err_network')+': '+e.message,'error'); }
}

// ── Gas Tracker ─────────────────────────────────────────────────────────
async function updateGasFees(){
  try {
    const r = await fetch('/api/v1/gas');
    if(!r.ok) return;
    const d = await r.json();
    if(!d) return;
    const el = document.getElementById('gasGwei');
    if(el && typeof d.gwei === 'number') el.textContent = d.gwei.toFixed(1) + ' Gwei';
    const sig = document.getElementById('gasSig');
    if(sig) sig.textContent = d.signal===1?'⬆ '+QI18n.t('gas_high'):d.signal===-1?'⬇ '+QI18n.t('gas_low'):'→ '+QI18n.t('gas_normal');
  } catch(e){ console.warn('Gas fees fetch failed:', e); }
}
let _gasInterval = setInterval(updateGasFees, 120000);
// Cleanup on page unload to prevent memory leak
window.addEventListener('beforeunload', () => {
  clearInterval(_gasInterval);
  _gasInterval = null;
  if(_virginieEdgeTimer){ clearInterval(_virginieEdgeTimer); _virginieEdgeTimer = null; }
});



// ── Role-Based UI ─────────────────────────────────────────────────────────────
let _currentRole = 'user';

function applyRoleUI(role) {
  _currentRole = role || 'user';
  const body = document.body;
  const badge = document.getElementById('roleBadge');

  if (role === 'admin') {
    body.classList.add('is-admin');
    body.classList.remove('is-user');
    if (badge) { badge.textContent = 'admin'; badge.className = 'role-badge admin'; }
  } else {
    body.classList.remove('is-admin');
    body.classList.add('is-user');
    if (badge) { badge.textContent = 'user'; badge.className = 'role-badge user'; }
  }

  // Update admin-only element visibility (nav buttons + sections)
  document.querySelectorAll('.admin-only').forEach(el => {
    if (role === 'admin') {
      el.style.display = el.classList.contains('nb') ? 'flex' : '';
    } else {
      el.style.display = 'none';
    }
  });
}

function applyStateToRole(data) {
  const role = data.user_role || 'user';
  applyRoleUI(role);
  // Fill admin stats if visible
  if (role === 'admin') {
    const ic = document.getElementById('adminIterCount');
    const mc = document.getElementById('adminMarketCount');
    if (ic) ic.textContent = data.iteration || 0;
    if (mc) mc.textContent = (data.markets || []).length || 0;
  }
}

// ── Admin: System Analytics ───────────────────────────────────────────────────
async function loadSystemAnalytics() {
  if(socket.connected){
    socket.emit('request_system_analytics');
  } else {
    // HTTP fallback when socket is disconnected
    try{
      const r=await fetch('/api/v1/system-analytics',{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
      if(r.ok){ const d=await r.json(); socket.listeners('system_analytics').forEach(fn=>fn(d)); }
      else { toast('⚠️ Analytics: '+r.status,'warning'); }
    }catch(e){ toast('⚠️ '+QI18n.t('conn_disconnected'),'warning'); }
  }
  loadAdminBlockerInsights();
}

function _parsePercent(v){
  if(v===null||v===undefined) return 0;
  const n = parseFloat(String(v).replace('%','').trim());
  return Number.isFinite(n) ? n : 0;
}

function _formatDecisionReason(reason){
  const raw = String(reason||'').trim();
  if(!raw) return {label:'unbekannt', detail:'kein Grund übermittelt'};
  if(raw.startsWith('ai_filter:')) return {label:'AI/VIRGINIE Filter', detail:raw.slice(10).trim()||'AI/VIRGINIE blockiert'};
  if(raw === 'circuit_breaker') return {label:'Circuit Breaker', detail:'Risikostopp aktiv'};
  if(raw === 'daily_loss_limit') return {label:'Daily Loss Limit', detail:'Tagesverlust-Limit erreicht'};
  if(raw === 'max_open_trades') return {label:'Max Open Trades', detail:'Positionslimit erreicht'};
  if(raw === 'already_open') return {label:'Position bereits offen', detail:'Symbol ist bereits im Portfolio'};
  if(raw === 'invest_too_small') return {label:'Invest zu klein', detail:'Ordergröße unter Minimum'};
  if(raw === 'qty_invalid') return {label:'Ungültige Menge', detail:'Berechnete Menge <= 0'};
  if(raw.includes('Cooldown')) return {label:'Cooldown aktiv', detail:raw};
  if(raw.includes('Unzureichendes Guthaben')) return {label:'Guthaben zu niedrig', detail:raw};
  if(raw.startsWith('live_buy_failed:')) return {label:'Live-Orderfehler', detail:raw.slice(16).trim()||raw};
  if(raw.startsWith('live_sell_failed:')) return {label:'Live-Orderfehler', detail:raw.slice(17).trim()||raw};
  if(raw.startsWith('executed:')) return {label:'Ausgeführt', detail:raw.slice(9).trim()||'Order ausgeführt'};
  return {label:raw.split(':')[0] || raw, detail:raw};
}

async function loadAdminBlockerInsights(){
  const summaryTotal=document.getElementById('adminBlockerTotal');
  const summaryErrors=document.getElementById('adminBlockerErrors');
  const summaryTop=document.getElementById('adminBlockerTop');
  const summaryUpdated=document.getElementById('adminBlockerUpdated');
  const listEl=document.getElementById('adminBlockerList');
  const latestEl=document.getElementById('adminBlockerLatest');
  if(!summaryTotal || !summaryErrors || !summaryTop || !summaryUpdated || !listEl || !latestEl) return;

  try{
    const data = await _fetchTradingEndpoint('/api/v1/trading/decision-history?limit=200');
    const rows = Array.isArray(data.decisions) ? data.decisions : [];
    const blocked = rows.filter(r => String(r.decision||'').toLowerCase()==='blocked');
    const errors = rows.filter(r => String(r.decision||'').toLowerCase()==='error');
    const grouped = new Map();
    blocked.forEach(row=>{
      const parsed = _formatDecisionReason(row.reason);
      const key = parsed.label;
      const prev = grouped.get(key) || {count:0, detail:parsed.detail};
      prev.count += 1;
      if(parsed.detail) prev.detail = parsed.detail;
      grouped.set(key, prev);
    });
    const top = Array.from(grouped.entries())
      .sort((a,b)=>b[1].count-a[1].count)
      .slice(0,6);

    summaryTotal.textContent = String(blocked.length);
    summaryErrors.textContent = String(errors.length);
    summaryTop.textContent = top.length ? `${top[0][0]} (${top[0][1].count}x)` : '—';
    summaryUpdated.textContent = new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit',second:'2-digit'});

    if(!top.length){
      listEl.innerHTML = '<div class="empty"><div class="empty-ico">✅</div>Keine Blocker in den letzten 200 Decisions.</div>';
    } else {
      listEl.innerHTML = top.map(([label,meta]) => `
        <div style="display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid var(--muted);font-size:11px">
          <div style="min-width:0">
            <div style="font-weight:700;color:var(--txt)">${esc(label)}</div>
            <div style="color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(meta.detail||'')}</div>
          </div>
          <div style="font-family:var(--mono);color:var(--yellow);font-weight:700">${meta.count}x</div>
        </div>
      `).join('');
    }

    const latest = rows
      .filter(r=>['blocked','error'].includes(String(r.decision||'').toLowerCase()))
      .slice(0,5);
    if(!latest.length){
      latestEl.innerHTML = '<div class="empty"><div class="empty-ico">📭</div>Keine aktuellen Block-/Error-Events.</div>';
      return;
    }
    latestEl.innerHTML = latest.map(r=>{
      const parsed = _formatDecisionReason(r.reason);
      const confidence = Number(r.confidence||0);
      const aiScore = Number(r.ai_score||0);
      const winProb = Number(r.win_prob||0);
      return `<div style="padding:7px 0;border-bottom:1px solid var(--line);font-size:11px">
        <div style="display:flex;justify-content:space-between;gap:6px;margin-bottom:2px">
          <span style="font-weight:700;color:var(--txt)">${esc(String(r.symbol||''))} · ${esc(String((r.decision||'').toUpperCase()))}</span>
          <span style="font-family:var(--mono);color:var(--sub)">${esc(String((r.created_at||'').slice(0,19)).replace('T',' '))}</span>
        </div>
        <div style="color:var(--yellow);font-weight:600">${esc(parsed.label)}</div>
        <div style="color:var(--sub);margin-top:1px">${esc(parsed.detail)}</div>
        <div style="display:flex;gap:10px;margin-top:3px;font-family:var(--mono);color:var(--sub)">
          <span>conf: ${Number.isFinite(confidence)?confidence.toFixed(3):'—'}</span>
          <span>ai: ${Number.isFinite(aiScore)?aiScore.toFixed(3):'—'}</span>
          <span>win: ${Number.isFinite(winProb)?winProb.toFixed(1):'—'}%</span>
        </div>
      </div>`;
    }).join('');
  }catch(e){
    listEl.innerHTML = '<div class="empty"><div class="empty-ico">⚠️</div>Blocker-Analyse konnte nicht geladen werden.</div>';
    latestEl.innerHTML = '';
  }
}

function renderAIDiagnosePanel(diag){
  const _s=(id,v)=>{ const el=document.getElementById(id); if(el) el.textContent=v; };
  const reasoningEl = document.getElementById('aiDiagReasoning');
  const actionsEl = document.getElementById('aiDiagActions');
  if(!reasoningEl || !actionsEl) return;

  const acc = _parsePercent(diag.accuracy);
  const cv = _parsePercent(diag.cv_accuracy);
  const agree = Math.max(0, 100 - Math.abs(acc - cv));
  const pred = Number(diag.predictions||0);
  const corr = Number(diag.correct||0);
  const decisionQ = pred > 0 ? (corr/pred)*100 : 0;
  const trained = !!diag.trained;
  const assistantAgents = diag.assistant_agents || {};
  const agentCount = Number(assistantAgents.registered_agents||0);
  const coveragePct = Number(assistantAgents.coverage_pct||0);
  const latencyMs = Number(diag.llm_latency_ms||0);
  const riskLosses = Number(diag.circuit_losses||0);
  const riskLimit = Number(diag.circuit_limit||0);
  const riskPressure = riskLimit>0 ? (riskLosses/riskLimit)*100 : 0;
  const healthScore = Math.max(
    0,
    Math.min(
      100,
      (trained ? 20 : 0) +
      (acc * 0.35) +
      (decisionQ * 0.25) +
      (agree * 0.15) +
      (latencyMs > 0 ? Math.max(0, 20 - Math.min(20, latencyMs / 50)) : 10) -
      (riskPressure * 0.15)
    )
  );

  const healthTxt = healthScore >= 75 ? `🟢 ${healthScore.toFixed(1)}%` : healthScore >= 50 ? `🟡 ${healthScore.toFixed(1)}%` : `🔴 ${healthScore.toFixed(1)}%`;
  const driftTxt = agree >= 85 ? '🟢 niedrig' : agree >= 65 ? '🟡 mittel' : '🔴 hoch';
  const qualityTxt = decisionQ >= 70 ? `🟢 ${decisionQ.toFixed(1)}%` : decisionQ >= 55 ? `🟡 ${decisionQ.toFixed(1)}%` : `🔴 ${decisionQ.toFixed(1)}%`;
  const latencyTxt = latencyMs > 0 ? `${latencyMs} ms` : '—';
  const collabProviders = Number(diag.llm_providers_used||0);
  const collabResponses = Number(diag.llm_responses_used||0);
  const collabRuns = Number(diag.idle_learning_runs||0);
  const collabActive = !!diag.llm_collaboration_active || collabProviders>0 || collabResponses>0;
  const collabTxt = collabActive
    ? `🟢 Agents ${agentCount} / Coverage ${coveragePct.toFixed(1)}% / Provider ${collabProviders}`
    : `🟡 standby (Agents ${agentCount}, Coverage ${coveragePct.toFixed(1)}%)`;

  _s('aiDiagHealth', healthTxt);
  _s('aiDiagQuality', qualityTxt);
  _s('aiDiagDrift', driftTxt);
  _s('aiDiagLatency', latencyTxt);
  _s('aiDiagCollab', collabTxt);
  _s('aiDiagIdleRuns', String(collabRuns));

  const reasons = [];
  if(!trained) reasons.push('Modell ist aktuell nicht trainiert.');
  if(acc < 55) reasons.push('Model-Accuracy ist niedrig.');
  if(decisionQ < 55 && pred >= 20) reasons.push('Trefferquote der Vorhersagen ist niedrig.');
  if(agree < 70) reasons.push('Abweichung zwischen Accuracy und CV-Accuracy deutet auf Drift/Overfitting hin.');
  if(latencyMs > 1500) reasons.push('LLM-Latenz ist erhöht – mögliche API/Provider-Bremse.');
  if(agentCount <= 0) reasons.push('VIRGINIE-Agenten sind nicht registriert.');
  if(Array.isArray(assistantAgents.missing_domains) && assistantAgents.missing_domains.length){
    reasons.push(`Fehlende Agent-Domains: ${assistantAgents.missing_domains.join(', ')}`);
  }
  if(!collabActive) reasons.push('LLM/VIRGINIE-Kollaboration im Idle-Modus ist aktuell noch nicht aktiv.');
  if(diag.assistant_review?.summary) reasons.push(`Review: ${diag.assistant_review.summary}`);
  if(diag.idle_learning_error) reasons.push(`Idle-Learning Fehler: ${diag.idle_learning_error}`);
  if(riskPressure >= 80) reasons.push('Circuit-Breaker steht kurz vor dem Limit.');
  if(diag.idle_learning_summary) reasons.push(`Letzter Idle-Impuls: ${diag.idle_learning_summary}`);
  reasoningEl.textContent = reasons.length ? reasons.join(' ') : 'AI-System arbeitet stabil. Keine kritischen Auffälligkeiten erkannt.';

  const actions = [];
  if(!trained || acc < 60) actions.push({txt:'🧠 Train starten', fn:'forceTrain()'});
  if(agree < 75) actions.push({txt:'🔧 Optimierung', fn:'forceOptimize()'});
  if(riskPressure >= 80) actions.push({txt:'🛑 Trading pausieren', fn:"apiTradingControl('stop')"});
  if(latencyMs > 1500) actions.push({txt:'🌐 LLM Provider prüfen', fn:'loadLlmProviderStatus()'});
  if(agentCount <= 0) actions.push({txt:'🤖 Agenten initialisieren', fn:'loadSystemAnalytics()'});
  if(Array.isArray(assistantAgents.missing_domains) && assistantAgents.missing_domains.length){
    actions.push({txt:'🧩 Agent-Lücken prüfen', fn:'loadSystemAnalytics()'});
  }
  if(!actions.length) actions.push({txt:'✅ Kein Eingriff nötig', fn:''});

  actionsEl.innerHTML = actions.map(a => a.fn
    ? `<button class="btn btn-info" style="padding:7px 10px;font-size:11px" onclick="${a.fn}">${esc(a.txt)}</button>`
    : `<span style="font-size:11px;color:var(--green);font-weight:700">${esc(a.txt)}</span>`
  ).join('');
}

socket.on('system_analytics', d => {
  if (!d) return;
  const _el = id => document.getElementById(id);
  const _set = (id, v) => { const e = _el(id); if (e) e.textContent = v || '—'; };
  // System info
  if (d.system) {
    const s = d.system;
    _set('sysPython', s.python); _set('sysPlatform', s.platform);
    _set('sysCpu', s.cpu); _set('sysMemory', s.memory);
    _set('sysDisk', s.disk); _set('sysUptime', s.uptime);
  }
  // API status
  if (d.api) {
    const a = d.api;
    _set('apiExchange', a.exchange); _set('apiConnected', a.connected);
    _set('apiLatency', a.latency); _set('apiCalls24h', a.calls_24h);
    _set('apiDiscord', a.discord); _set('apiTelegram', a.telegram);
  }
  // LLM status
  if (d.llm) {
    const l = d.llm;
    _set('llmProvider', l.provider || '—');
    _set('llmEndpoint', l.endpoint); _set('llmModel', l.model);
    _set('llmStatus', l.status); _set('llmLatency', l.latency);
    _set('llmQueries24h', l.queries_24h); _set('llmTokens24h', l.tokens_24h);
  }
  // DB status
  if (d.db) {
    const b = d.db;
    _set('dbPoolSize', b.pool_size); _set('dbActiveConn', b.active_conn);
    _set('dbUtilization', b.utilization); _set('dbTables', b.tables); _set('dbSize', b.size);
  }
  // AI Engine
  if (d.ai) {
    const a = d.ai;
    _set('aiTrained', a.trained ? '✅' : '❌');
    _set('aiAccuracy', a.accuracy); _set('aiCvAccuracy', a.cv_accuracy);
    _set('aiPredictions', a.predictions); _set('aiCorrect', a.correct);
    _set('aiVersion', 'v' + (a.version || 0)); _set('aiLastTrained', a.last_trained);
    _set('aiAssistant', (a.assistant_name || '—') + (a.assistant_version ? ' ' + a.assistant_version : ''));
    _set('aiTradesSinceRetrain', a.trades_since_retrain);
    updateAI3DFromAI({
      wf_accuracy: parseFloat(String(a.accuracy||'0').replace('%','')) || 0,
      bull_accuracy: parseFloat(String(a.cv_accuracy||'0').replace('%','')) || 0,
      bear_accuracy: parseFloat(String(a.cv_accuracy||'0').replace('%','')) || 0,
      samples: a.predictions || 0,
      allowed_count: a.correct || 0,
      blocked_count: Math.max(0,(a.predictions||0)-(a.correct||0)),
      llm_providers_used: a.llm_providers_used || 0,
      llm_responses_used: a.llm_responses_used || 0,
      idle_learning_runs: a.idle_learning_runs || 0,
    });
    renderAIDiagnosePanel({
      ...a,
      llm_latency_ms: _parsePercent((d.llm||{}).latency),
      circuit_losses: (d.risk||{}).circuit_losses || 0,
      circuit_limit: (d.risk||{}).circuit_limit || 0,
    });
  }
  // Risk
  if (d.risk) {
    const r = d.risk;
    _set('riskCircuitActive', r.circuit_active ? '🔴 '+QI18n.t('label_active') : '🟢 '+QI18n.t('label_inactive'));
    _set('riskCircuitLosses', r.circuit_losses + '/' + r.circuit_limit);
    _set('riskMaxDrawdown', r.max_drawdown);
  }
  // Revenue
  if (d.revenue) {
    const v = d.revenue;
    _set('revGrossPnl', v.gross_pnl + ' USDT'); _set('revNetPnl', v.net_pnl + ' USDT');
    _set('revFees', v.total_fees + ' USDT'); _set('revTrades', v.total_trades);
    _set('revRoi', v.roi_pct); _set('revDrawdown', v.max_drawdown);
    _set('revPF', v.profit_factor); _set('revWinRate', v.win_rate);
    // Color net PnL
    const ne = _el('revNetPnl');
    if (ne) ne.style.color = v.net_pnl >= 0 ? 'var(--green)' : 'var(--red)';
  }
  // Performance attribution
  if (d.attribution) {
    const p = d.attribution;
    _set('attrTrades', p.total_trades); _set('attrPF', p.profit_factor);
    _set('attrExpectancy', p.expectancy + ' USDT'); _set('attrSharpe', p.sharpe);
  }
  // Strategy weights
  if (d.strategies) {
    const st = d.strategies;
    _set('stratTotal', st.total); _set('stratAdapted', st.adapted);
    _set('stratVotes', st.total_votes);
    const el = _el('stratTopList');
    if (el && st.top && st.top.length) {
      el.innerHTML = st.top.map(s =>
        '<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line);font-size:12px">' +
        '<span style="color:var(--txt);font-weight:600">' + esc(s.name) + '</span>' +
        '<span style="font-family:var(--mono);color:var(--cyan)">' + s.weight + 'x</span>' +
        '<span style="color:var(--sub)">' + s.win_rate + ' · ' + s.trades + ' trades</span></div>'
      ).join('');
    }
  }
  // Cache stats
  if (d.cache) {
    const c = d.cache;
    _set('cacheTotal', c.total_entries); _set('cacheFresh', c.fresh_entries);
    _set('cacheStale', c.stale_entries); _set('cacheTTL', (c.ttl_seconds || 0) + 's');
  }
  // Healing
  if (d.healing && d.healing.services) {
    const el = _el('healingList');
    if (el) {
      const svcs = Object.entries(d.healing.services);
      el.innerHTML = svcs.map(([name, s]) =>
        '<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line);font-size:12px">' +
        '<span style="color:var(--txt)">' + esc(name) + '</span>' +
        '<span style="color:' + (s.healthy ? 'var(--green)' : 'var(--red)') + '">' + (s.healthy ? '✅' : '❌') + '</span>' +
        '<span style="font-family:var(--mono);color:var(--sub)">' + (s.restarts || 0) + ' restarts</span></div>'
      ).join('');
    }
  }
});

// ── Missing WebSocket Event Handlers ─────────────────────────────────────────
socket.on('healing_update', d => {
  if (!d) return;
  addLog('🏥 ' + QI18n.t('admin_healing') + ': ' + (d.status || 'update'), 'info', 'system');
});
socket.on('revenue_update', d => {
  if (!d) return;
  addLog('💰 ' + QI18n.t('admin_revenue') + ': ' + QI18n.t('admin_net_pnl') + ' ' + (d.net_pnl || 0) + ' USDT', 'info', 'system');
});
socket.on('cluster_update', d => {
  if (!d) return;
  addLog('🔗 Cluster: ' + (d.status || 'update'), 'info', 'system');
});

// ── Admin: KPI Stat Cards ─────────────────────────────────────────────────────
function updateAdminKPIs(d) {
  if (!d || typeof d !== 'object') return;
  const _s = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  // Revenue = total PnL
  const pnl = d.total_pnl || 0;
  _s('adminRevTotal', (pnl >= 0 ? '+' : '') + fmt(pnl) + ' USDT');
  const revEl = document.getElementById('adminRevTotal');
  if (revEl) revEl.style.color = pnl >= 0 ? '#00e676' : '#ef4444';
  _s('adminRevChange', (d.daily_pnl >= 0 ? '+' : '') + fmt(d.daily_pnl || 0) + ' today');
  // Total trades
  _s('adminTradesTotal', d.total_trades || 0);
  _s('adminTradesChange', (d.open_trades || 0) + ' open');
  // Active users (from connected clients count)
  _s('adminUsersTotal', d.connected_clients || 1);
  _s('adminUsersOnline', (d.connected_clients || 1) + ' online');
  // Win rate
  const wr = d.win_rate || 0;
  _s('adminWinRate', fmt(wr, 1) + '%');
  const wrEl = document.getElementById('adminWinRate');
  if (wrEl) wrEl.style.color = wr >= 50 ? '#00e676' : wr > 0 ? '#ffb400' : '#8a8a8a';
  _s('adminIterCount2', (d.iteration_count || 0) + ' Iterationen');
  // Bot controls mini-stats
  _s('adminIterCount', d.iteration_count || 0);
  _s('adminClientCount', d.connected_clients || 0);
  _s('adminMarketCount', (d.symbols || []).length || 1);
}
// Hook into existing update flow
socket.on('update', d => { if (d) updateAdminKPIs(d); });

// ── Admin: LLM Provider Status ────────────────────────────────────────────────
async function loadLlmProviderStatus() {
  const el = document.getElementById('adminLlmProviders');
  if (!el) return;
  try {
    const r = await fetch('/api/v1/llm-status', {headers: {'Authorization': 'Bearer ' + (_jwtToken || '')}});
    if (!r.ok) { el.innerHTML = '<div style="color:#8a6a3a;font-size:12px">Status nicht verfuegbar</div>'; return; }
    const d = await r.json();
    const providers = d.multi_llm_providers || d.providers || [];
    if (!providers.length) {
      el.innerHTML = '<div style="color:#8a6a3a;font-size:12px">Keine LLM-Provider konfiguriert</div>';
      return;
    }
    el.innerHTML = providers.map(p =>
      '<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,180,0,.08);font-size:12px">' +
      '<div><span style="color:#e8f0ff;font-weight:600">' + esc(p.name) + '</span>' +
      '<span style="color:#6a5a3a;margin-left:8px;font-family:var(--mono);font-size:10px">' + esc(p.model || '') + '</span></div>' +
      '<div style="display:flex;gap:8px;align-items:center">' +
      (p.supports_tools ? '<span style="font-size:9px;background:rgba(255,180,0,.1);border:1px solid rgba(255,180,0,.2);color:#ffb400;border-radius:3px;padding:1px 5px">Tools</span>' : '') +
      '<span style="color:' + (p.available ? '#00e676' : '#ef4444') + ';font-weight:600">' + (p.available ? 'Online' : 'Offline') + '</span>' +
      '<span style="font-family:var(--mono);color:#6a5a3a;font-size:10px">' + (p.requests || 0) + ' req / ' + (p.errors || 0) + ' err</span>' +
      '</div></div>'
    ).join('');
  } catch (e) {
    el.innerHTML = '<div style="color:#8a6a3a;font-size:12px">Fehler: ' + esc(e.message) + '</div>';
  }
}
// Auto-load LLM status when admin section becomes visible
(function(){
  const obs = new MutationObserver(() => {
    const sec = document.getElementById('sec-admin');
    if (sec && sec.classList.contains('active')) { loadLlmProviderStatus(); obs.disconnect(); }
  });
  obs.observe(document.body, {subtree: true, attributes: true, attributeFilter: ['class']});
})();

// ── Admin: Load Users ──────────────────────────────────────────────────────────
async function loadUsers() {
  const el = document.getElementById('userList');
  try {
    const r = await fetch('/api/v1/admin/users', {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const users = d.users || d || [];
    if (!users.length) { if(el) el.innerHTML='<div class="empty">'+QI18n.t('empty_no_users')+'</div>'; return; }
    if (el) el.innerHTML = users.map(u => `
      <div style="display:flex;align-items:center;justify-content:space-between;
        padding:8px 0;border-bottom:1px solid var(--muted);gap:8px">
        <div>
          <div style="font-size:13px;font-weight:600;color:var(--txt)">${esc(String(u.username||''))}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">
            ${esc(String(u.created_at?.slice?.(0,10)||''))} · ${esc(String(u.role||'user'))}
          </div>
        </div>
        <span class="role-badge ${esc(String(u.role||'user'))}">${esc(String(u.role||'user'))}</span>
        <div style="font-family:var(--mono);font-size:12px;color:var(--jade)">
          ${(u.balance||0).toFixed(0)} USDT
        </div>
      </div>`).join('');
  } catch(e){ if(el) el.innerHTML='<div class="empty">'+QI18n.t('empty_load_error')+'</div>'; }
}

async function createUser() {
  const username = document.getElementById('newUsername')?.value?.trim();
  const password = document.getElementById('newPassword')?.value;
  const role     = document.getElementById('newRole')?.value || 'user';
  if (!username || !password) { toast(QI18n.t('err_user_pass'),'warning'); return; }
  if(!_emitSafe('admin_create_user', {username, password, role})) return;
  document.getElementById('newUsername').value = '';
  document.getElementById('newPassword').value = '';
  setTimeout(loadUsers, 800);
}

async function toggleRegistration(enabled) {
  if(_emitSafe('update_config', {allow_registration: enabled}))
    toast(enabled ? '✅ '+QI18n.t('msg_reg_enabled') : '🔒 '+QI18n.t('msg_reg_disabled'), 'info');
}


// ── Shared AI Model broadcast ──────────────────────────────────────────────
socket.on('ai_model_updated', data => {
  if(!data) return;
  toast(`🧠 ${QI18n.t('msg_ai_model_new')} v${data.version||'?'} (WF: ${data.wf_accuracy||0}%)`, 'success');
  loadSharedAIStatus();
  // Animate version badge
  const badge = document.getElementById('sharedAIVersionBadge');
  if (badge) {
    badge.textContent = 'v' + data.version;
    badge.style.animation = 'none';
    setTimeout(() => badge.style.animation = '', 10);
  }
});

// ════════════════════════════════════════════════════════════════
// SHARED AI JS
// ════════════════════════════════════════════════════════════════

async function loadSharedAIStatus() {
  try {
    const r = await fetch('/api/v1/ai/shared/status',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.error) return;

    // Version badge
    const badge = document.getElementById('sharedAIVersionBadge');
    if (badge) badge.textContent = 'v' + (d.shared_version || '—');

    // Status
    const st = document.getElementById('sharedAIStatus');
    if (st) st.textContent = d.status_msg || '—';

    // Accuracies
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = val + '%';
      el.style.color = val >= 65 ? 'var(--jade)' : val >= 55 ? 'var(--amber)' : 'var(--red)';
    };
    set('sharedWF',   d.wf_accuracy   || 0);
    set('sharedBull', d.bull_accuracy || 0);
    set('sharedBear', d.bear_accuracy || 0);
    set('sharedLSTM', d.lstm_accuracy || 0);

    // Samples
    const sv = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = (val||0).toLocaleString('de-DE'); };
    sv('sharedSamples',     d.n_samples);
    sv('sharedSamplesBull', d.n_samples_bull);
    sv('sharedSamplesBear', d.n_samples_bear);

    // Sync status
    const dot  = document.getElementById('sharedSyncDot');
    const text = document.getElementById('sharedSyncText');
    if (d.is_up_to_date) {
      if (dot)  dot.style.background  = '#00ff88';
      if (text) text.textContent = `✅ Aktuell (v${d.shared_version}) · Letzte Aktualisierung: ${d.last_trained || '—'}`;
    } else {
      if (dot)  dot.style.background  = '#f59e0b';
      if (text) text.textContent = `⚠ Update verfügbar: v${d.shared_version} (aktuell: v${d.local_version})`;
    }

    // Model history
    const hist = document.getElementById('modelHistoryList');
    if (hist && d.models?.length) {
      hist.innerHTML = d.models.map(m => `
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--muted)">
          <span style="font-family:var(--mono);font-size:10px;color:var(--jade);min-width:30px">v${esc(String(m.version||''))}</span>
          <span style="font-size:9px;background:rgba(255,255,255,.05);padding:1px 6px;border-radius:4px;color:var(--sub)">${esc(String(m.type||''))}</span>
          <div style="flex:1">
            <div style="font-size:11px;color:var(--txt)">${esc(String(m.accuracy||''))}% WF · ${(m.samples||0).toLocaleString('de-DE')} Samples</div>
            <div style="font-size:9px;color:var(--sub)">${esc(String(m.date||''))} · von ${esc(String(m.trained_by||''))}</div>
          </div>
          <div style="width:50px;height:4px;background:var(--bg3);border-radius:2px">
            <div style="width:${Math.min(100,m.accuracy)}%;height:100%;border-radius:2px;
              background:${m.accuracy>=65?'var(--jade)':m.accuracy>=55?'#f59e0b':'var(--red)'}"></div>
          </div>
        </div>`).join('');
    }

    // Contributors
    const contribs = document.getElementById('contributorsList');
    if (contribs && d.contributors?.length) {
      contribs.innerHTML = d.contributors.map((c,i) => `
        <div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--muted)">
          <span style="font-family:var(--mono);font-size:13px;min-width:24px;color:${i===0?'#f59e0b':i===1?'#94a3b8':i===2?'#b45309':'var(--sub)'}">${['🥇','🥈','🥉'][i]||'·'}</span>
          <div style="flex:1">
            <div style="font-size:12px;font-weight:600;color:var(--txt)">${esc(String(c.username||''))}</div>
            <div style="font-size:10px;color:var(--sub)">${esc(String(c.last?.slice(0,16)||''))}</div>
          </div>
          <div style="text-align:right">
            <div style="font-family:var(--mono);font-size:12px;color:var(--jade)">${(c.samples||0).toLocaleString('de-DE')} Samples</div>
            <div style="font-size:10px;color:${c.pnl>=0?'var(--jade)':'var(--red)'};font-family:var(--mono)">${c.pnl>=0?'+':''}${(c.pnl||0).toFixed(2)} USDT PnL</div>
          </div>
        </div>`).join('');
    } else if (contribs && !d.contributors?.length) {
      contribs.innerHTML = '<div class="empty"><div class="empty-ico">🏆</div>'+QI18n.t('empty_no_contributions')+'</div>';
    }
  } catch(e) { console.warn('loadSharedAIStatus:', e); }
}

async function syncSharedModel(event) {
  const btn = event?.target || document.activeElement;
  btn.textContent = '⏳';
  try {
    const r = await fetch('/api/v1/ai/shared/force-sync', {
      method:'POST', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.updated) {
      toast(`✅ ${QI18n.t('msg_model_synced')} v${d.version} (${d.accuracy}% WF)`, 'success');
      loadSharedAIStatus();
    } else {
      toast(QI18n.t('msg_no_new_model'), 'info');
    }
  } catch(e) { toast(QI18n.t('msg_sync_error'), 'error'); }
  btn.textContent = '↻ Sync';
}

async function adminTrainGlobal() {
  if (!confirm(QI18n.t('confirm_global_train'))) return;
  try {
    const r = await fetch('/api/v1/ai/shared/train', {
      method:'POST', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.started) {
      toast(`🧠 ${QI18n.t('msg_training_started')}: ${d.samples_total} Samples (${d.new_samples})`, 'success');
    } else {
      toast(d.error || QI18n.t('toast_error'), 'error');
    }
  } catch(e) { toast(QI18n.t('msg_training_error'), 'error'); }
}

async function loadModelHistory() { await loadSharedAIStatus(); }
async function loadContributors()  { await loadSharedAIStatus(); }

// Load on AI tab
const _origOnTabSwitch = typeof onTabSwitch === 'function' ? onTabSwitch : null;
function onTabSwitch(section) {
  if (_origOnTabSwitch) _origOnTabSwitch(section);
  if (section === 'ai') {
    setTimeout(loadSharedAIStatus, 200);
    setTimeout(loadFeatureImportance, 500);
  }
  if (section === 'backtest') setTimeout(loadBtHistory, 300);
}

// Initial load
setTimeout(loadSharedAIStatus, 2000);


// ════════════════════════════════════════════════════════════════
// MONTE CARLO
// ════════════════════════════════════════════════════════════════
async function runMonteCarlo() {
  const n    = document.getElementById('mcSims')?.value || 10000;
  const days = document.getElementById('mcDays')?.value || 30;
  document.getElementById('mcLoading')?.style && (document.getElementById('mcLoading').style.display='block');
  document.getElementById('mcResults')?.style  && (document.getElementById('mcResults').style.display='none');
  document.getElementById('mcEmpty')?.style    && (document.getElementById('mcEmpty').style.display='none');
  try {
    const r = await fetch(`/api/v1/risk/monte-carlo?n=${encodeURIComponent(n)}&days=${encodeURIComponent(days)}`,
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    if(!r.ok){ toast(QI18n.t('err_generic'),'error'); return; }
    const d = await r.json();
    if (d.error) { toast(d.error,'warning'); return; }
    const _s = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
    const _sh = (id, show) => { const el=document.getElementById(id); if(el) el.style.display=show?'block':'none'; };
    _sh('mcLoading', false);
    _sh('mcResults', true);
    _s('mcP50', fmt(d.percentile_50) + ' USDT');
    _s('mcP5', fmt(d.percentile_5) + ' USDT');
    _s('mcP95', fmt(d.percentile_95) + ' USDT');
    _s('mcProbProfit', d.prob_profit_pct + '%');
    _s('mcVaR95', fmt(d.var_95_usdt) + ' USDT');
    _s('mcBarMin', fmt(d.percentile_5));
    _s('mcBarMax', fmt(d.percentile_95));
    _s('mcBarExpected', fmt(d.percentile_50) + ' USDT');
    const range = d.percentile_95 - d.percentile_5;
    const pos   = range > 0 ? (d.percentile_50 - d.percentile_5) / range * 100 : 50;
    const mcBar=document.getElementById('mcBar'); if(mcBar) mcBar.style.width = Math.max(10, Math.min(90, pos)) + '%';
  } catch(e) {
    const mcl=document.getElementById('mcLoading'); if(mcl) mcl.style.display='none';
    const mce=document.getElementById('mcEmpty'); if(mce) mce.style.display='block';
    toast(QI18n.t('msg_monte_error'),'error');
  }
}

// ════════════════════════════════════════════════════════════════
// FUNDING RATES
// ════════════════════════════════════════════════════════════════
async function loadFundingRates() {
  const el = document.getElementById('fundingList');
  if(!el) return;
  try {
    const r = await fetch('/api/v1/funding-rates?n=15',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    if(!r.ok){ el.innerHTML='<div class="empty">'+QI18n.t('empty_error')+'</div>'; return; }
    const d = await r.json();
    const rates = d.top_rates || [];
    if (!rates.length) { el.innerHTML='<div class="empty">'+QI18n.t('empty_no_data')+'</div>'; return; }
    el.innerHTML = rates.map(f => {
      const pct = parseFloat(f.rate) || 0;
      const col = pct > 0.05 ? 'var(--red)' : pct < -0.05 ? 'var(--jade)' : 'var(--sub)';
      return `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:12px;font-weight:600;color:var(--txt);flex:1">${esc(String(f.symbol||''))}</span>
        <span style="font-family:var(--mono);font-size:12px;color:${col}">${pct > 0 ? '+' : ''}${pct.toFixed(4)}%</span>
        ${pct > 0.08 ? '<span style="font-size:9px;background:rgba(239,68,68,.1);color:#ef4444;padding:1px 5px;border-radius:4px">'+QI18n.t('label_high')+'</span>' : ''}
      </div>`;
    }).join('');
  } catch(e) { if(el) el.innerHTML='<div class="empty">'+QI18n.t('empty_error')+'</div>'; }
}
async function saveFundingConfig() {
  const enabled = document.getElementById('fundingEnabled')?.checked;
  const maxRate = parseFloat(document.getElementById('fundingMaxRate')?.value || '0.1') / 100;
  try {
    const r = await fetch('/api/v1/funding-rates/config', {
      method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
      body: JSON.stringify({enabled, max_rate: maxRate})
    });
    if(r.ok) toast(QI18n.t('msg_funding_saved'),'success');
    else toast(QI18n.t('err_generic'),'error');
  } catch(e){ toast(QI18n.t('err_network')+': '+e.message,'error'); }
}

// ════════════════════════════════════════════════════════════════
// COOLDOWNS
// ════════════════════════════════════════════════════════════════
async function loadCooldowns() {
  const el = document.getElementById('cooldownList');
  try {
    const r = await fetch('/api/v1/cooldowns',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const cds = d.cooldowns || {};
    if (!Object.keys(cds).length) {
      el.innerHTML = '<div class="empty"><div class="empty-ico">✅</div>'+QI18n.t('empty_no_locks')+'</div>';
      return;
    }
    el.innerHTML = Object.entries(cds).map(([sym, info]) => `
      <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:13px;font-weight:600;color:#ef4444;flex:1">${esc(String(sym))}</span>
        <span style="font-size:11px;color:var(--sub)">bis ${info.until} (${info.remaining_min} Min.)</span>
        <button onclick="clearCooldown('${escJS(sym)}')" style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:10px;padding:2px 8px">✕</button>
      </div>`).join('');
  } catch(e) { el.innerHTML = '<div class="empty">'+QI18n.t('empty_error')+'</div>'; }
}
async function clearCooldown(symbol) {
  try {
    await fetch('/api/v1/cooldowns/'+encodeURIComponent(symbol), {
      method:'DELETE', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    loadCooldowns();
    toast(`${symbol} ${QI18n.t('msg_cooldown_cleared')}`, 'info');
  } catch(e){ toast(QI18n.t('err_network'),'error'); }
}

// ════════════════════════════════════════════════════════════════
// GRID TRADING
// ════════════════════════════════════════════════════════════════
async function createGrid() {
  const symbol = document.getElementById('gridSymbol')?.value?.trim().toUpperCase();
  const lower  = parseFloat(document.getElementById('gridLower')?.value);
  const upper  = parseFloat(document.getElementById('gridUpper')?.value);
  const levels = parseInt(document.getElementById('gridLevels')?.value || 10, 10);
  const invest = parseFloat(document.getElementById('gridInvest')?.value || 100);
  if (!symbol || isNaN(lower) || isNaN(upper) || isNaN(levels) || isNaN(invest) || lower >= upper) {
    toast(QI18n.t('err_grid_params'), 'warning'); return;
  }
  if(!_emitSafe('create_grid', {symbol, lower, upper, levels, invest_per_level: invest})) return;
  setTimeout(loadGrids, 600);
}
async function loadGrids() {
  const el = document.getElementById('gridList');
  if (!el) return;
  try {
    const r = await fetch('/api/v1/grid', {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const grids = d.grids || [];
    if (!grids.length) { el.innerHTML = '<div style="font-size:12px;color:var(--sub)">'+QI18n.t('empty_no_grids')+'</div>'; return; }
    el.innerHTML = grids.map(g => `
      <div style="background:#091017;border-radius:8px;padding:10px;margin-top:8px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="font-weight:700;color:#e8f4ff">${esc(String(g.symbol||''))}</span>
          <span style="font-size:9px;padding:2px 6px;border-radius:4px;${g.active?'background:rgba(0,255,136,.08);color:var(--jade)':'background:rgba(255,255,255,.05);color:var(--sub)'}">${g.active?QI18n.t('label_grid_active'):QI18n.t('label_grid_inactive')}</span>
          <button onclick="deleteGrid('${escJS(g.symbol)}')" style="margin-left:auto;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:10px;padding:2px 8px">✕</button>
        </div>
        <div style="font-size:11px;color:var(--sub)">${g.levels} Stufen · ${g.lower}–${g.upper} USDT · Schritt: ${g.step?.toFixed(4) || '—'}</div>
        <div style="font-size:11px;color:var(--sub)">Offene Käufe: ${g.open_buys || 0} · Trades: ${g.total_trades || 0} · PnL: <span style="color:${(g.total_pnl||0)>=0?'var(--jade)':'var(--red)'}">${(g.total_pnl||0)>=0?'+':''}${(g.total_pnl||0).toFixed(4)} USDT</span></div>
      </div>`).join('');
  } catch(e) { if(el) el.innerHTML = '<div style="font-size:12px;color:var(--red)">'+QI18n.t('empty_error')+'</div>'; }
}
async function deleteGrid(symbol) {
  if (!confirm(QI18n.t('confirm_delete_grid').replace('{sym}',symbol))) return;
  try {
    const r = await fetch('/api/v1/grid/'+encodeURIComponent(symbol), {
      method:'DELETE', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    if(!r.ok){ const d=await r.json().catch(()=>({})); toast(d.error||QI18n.t('err_delete'),'error'); return; }
    loadGrids(); toast(`Grid ${symbol} ${QI18n.t('msg_grid_deleted')}`, 'info');
  } catch(e){ toast(QI18n.t('err_network')+': '+e.message,'error'); }
}

// ════════════════════════════════════════════════════════════════
// TELEGRAM
// ════════════════════════════════════════════════════════════════
async function saveTelegram() {
  const token   = document.getElementById('tgToken')?.value?.trim();
  const chat_id = document.getElementById('tgChatId')?.value?.trim();
  if (!token || !chat_id) { toast(QI18n.t('err_token_chatid'),'warning'); return; }
  const r = await fetch('/api/v1/telegram/configure', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({token, chat_id})
  });
  const d = await r.json();
  toast(d.success ? '✅ '+QI18n.t('msg_tg_connected') : '❌ '+QI18n.t('msg_tg_failed'), d.success?'success':'error');
}

// ════════════════════════════════════════════════════════════════
// IP WHITELIST
// ════════════════════════════════════════════════════════════════
async function saveIpWhitelist() {
  const raw = document.getElementById('ipWhitelist')?.value || '';
  const ips = raw.split('\n').map(l=>l.trim()).filter(Boolean);
  if (!confirm(QI18n.t('confirm_set_ips').replace('{n}',ips.length))) return;
  const r = await fetch('/api/v1/admin/ip-whitelist', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({ips})
  });
  const d = await r.json();
  toast(`✅ ${d.whitelist.length} ${QI18n.t('msg_ips_set')}`, 'success');
}
async function loadIpWhitelist() {
  try {
    const r = await fetch('/api/v1/admin/ip-whitelist',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const el = document.getElementById('ipWhitelist');
    if (el && d.whitelist) el.value = d.whitelist.join('\n');
  } catch(e){}
}

// ════════════════════════════════════════════════════════════════
// NEWS FILTER
// ════════════════════════════════════════════════════════════════
async function saveNewsFilter() {
  const minScore       = parseFloat(document.getElementById('newsMinScore')?.value || '-0.2');
  const blockScore     = parseFloat(document.getElementById('newsBlockScore')?.value || '-0.4');
  const requirePositive= document.getElementById('newsRequirePositive')?.checked || false;
  const r = await fetch('/api/v1/config/news-filter', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({min_score: minScore, block_score: blockScore, require_positive: requirePositive})
  });
  const d = await r.json();
  toast(d.success ? '✅ '+QI18n.t('toast_news_saved') : QI18n.t('toast_error'), d.success?'success':'error');
}
async function loadNewsFilter() {
  try {
    const r = await fetch('/api/v1/config/news-filter',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (document.getElementById('newsMinScore'))    document.getElementById('newsMinScore').value = d.news_sentiment_min;
    if (document.getElementById('newsBlockScore'))  document.getElementById('newsBlockScore').value = d.news_block_score;
    if (document.getElementById('newsRequirePositive')) document.getElementById('newsRequirePositive').checked = d.news_require_positive;
  } catch(e){}
}

// ════════════════════════════════════════════════════════════════
// BREAK-EVEN SAVE
// ════════════════════════════════════════════════════════════════
function saveBreakEven() {
  const trigger = parseFloat(document.getElementById('beeTrigger')?.value || '1.5') / 100;
  const buffer  = parseFloat(document.getElementById('beeBuffer')?.value  || '0.1') / 100;
  const enabled = document.getElementById('beeEnabled')?.checked;
  if(_emitSafe('update_config', {
    break_even_enabled: enabled,
    break_even_trigger: trigger,
    break_even_buffer:  buffer,
  })) toast('✅ '+QI18n.t('msg_breakeven_saved'), 'success');
}

// ════════════════════════════════════════════════════════════════
// AUDIT LOG
// ════════════════════════════════════════════════════════════════
async function loadAuditLog() {
  const el = document.getElementById('auditLogList');
  try {
    const r = await fetch('/api/v1/admin/audit-log',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const logs = d.logs || [];
    if (!logs.length) { el.innerHTML='<div class="empty">'+QI18n.t('empty_no_entries')+'</div>'; return; }
    const icons = {login:'🔑',trade:'💹',config:'⚙️',admin:'👑','2fa':'🔐',default:'📋'};
    el.innerHTML = logs.map(l => {
      const ico = Object.entries(icons).find(([k])=>l.action?.includes(k))?.[1] || icons.default;
      return `<div style="display:flex;gap:8px;padding:5px 0;border-bottom:1px solid var(--muted);font-size:11px">
        <span style="flex-shrink:0">${ico}</span>
        <div style="flex:1;min-width:0">
          <div style="color:var(--txt);font-weight:600">${esc(String(l.action||''))}</div>
          <div style="color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(String(l.detail||''))}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;color:var(--sub)">
          <div>${esc(String(l.username||'system'))}</div>
          <div style="font-family:var(--mono)">${(l.created_at||'').slice(11,16)}</div>
        </div>
      </div>`;
    }).join('');
  } catch(e) { el.innerHTML='<div class="empty">'+QI18n.t('empty_error')+'</div>'; }
}

// Load data when switching to risk/admin tabs
onNav(id => {
  if (id === 'risk') { loadFundingRates(); loadCooldowns(); }
  if (id === 'admin') { loadAuditLog(); loadGrids(); loadIpWhitelist(); loadAdminBlockerInsights(); }
  if (id === 'settings') { loadNewsFilter(); }
});
// Initial data load
setTimeout(() => { loadFundingRates(); }, 3000);

// ── Keyboard Shortcuts ─────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT') return;
  if(e.ctrlKey||e.metaKey||e.altKey) return;
  switch(e.key.toLowerCase()){
    case ' ':  e.preventDefault(); if(lastData?.running) stopBot(); else startBot(); break;
    case 't':  { const nb=document.getElementById('nb-trading'); if(nb) nav('trading',nb); } break;
    case 'p':  { const nb=document.getElementById('nb-pos'); if(nb) nav('pos',nb); } break;
    case 's':  { const nb=document.getElementById('nb-settings'); if(nb) nav('settings',nb); } break;
    case 'd':  { const nb=document.getElementById('nb-home'); if(nb) nav('home',nb); } break;
    case 'c':  { const nb=document.getElementById('nb-chart'); if(nb) nav('chart',nb); } break;
    case 'a':  { const nb=document.getElementById('nb-admin'); if(nb) nav('admin',nb); } break;
    case 'l':  toggleTheme(); break;
    case '?':
      const h = document.getElementById('shortcutHelp');
      h.classList.toggle('show'); break;
  }
});
document.addEventListener('click', e => {
  const h = document.getElementById('shortcutHelp');
  if(h && !h.contains(e.target) && e.target.id!=='shortcutHelp')
    h.classList.remove('show');
});

// ── Feature Importance ─────────────────────────────────────────────────────
async function loadFeatureImportance(){
  try {
    const r = await fetch('/api/v1/ai/feature-importance',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if(d.error){ toast(d.error,'warning'); return; }
    const fiCard = document.getElementById('featureImportanceCard');
    if(fiCard) fiCard.style.display='';
    const acc = document.getElementById('fi-accuracy');
    if(acc) acc.textContent = `WF: ${d.wf_accuracy}%`;
    const list = document.getElementById('fiList');
    if(!list) return;
    const names = d.feature_names || [];
    const imps  = d.importances   || [];
    const max   = imps.length > 0 ? Math.max(...imps, 0.001) : 1;
    list.innerHTML = names.map((n,i)=>{
      const v = imps[i]||0;
      const w = Math.round(v/max*100);
      return `<div style="margin-bottom:5px">
        <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px">
          <span style="color:var(--txt)">${esc(n)}</span>
          <span style="font-family:var(--mono);color:var(--jade)">${(v*100).toFixed(2)}%</span>
        </div>
        <div style="height:4px;background:var(--bg3);border-radius:2px">
          <div style="width:${w}%;height:100%;border-radius:2px;
            background:linear-gradient(90deg,var(--jade),var(--blue))"></div>
        </div></div>`;
    }).join('');
    // Strategy weights
    const ws = d.strategy_weights || [];
    if(ws.length){
      list.innerHTML += '<div style="margin-top:14px;font-family:var(--mono);font-size:9px;color:var(--sub);letter-spacing:2px;margin-bottom:6px">STRATEGIE-GEWICHTE</div>' +
        ws.map(w=>`<div style="display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-bottom:1px solid var(--muted)">
          <span>${esc(String(w.name||''))}</span>
          <span style="color:var(--jade)">${esc(String(w.weight||''))}× &nbsp; WR: ${esc(String(w.win_rate||''))}%</span>
        </div>`).join('');
    }
  } catch(e){ toast(QI18n.t('msg_fi_error'),'error'); }
}

function showReliabilityDiagram(){
  toast(QI18n.t('msg_calibration'),'info');
}

// ── Markowitz Optimization ─────────────────────────────────────────────────
async function runMarkowitz(){
  const syms = document.getElementById('markowitzSymbols')?.value?.split(',').map(s=>s.trim()).filter(Boolean);
  if(!syms||syms.length<2){ toast(QI18n.t('err_min2_symbols'),'warning'); return; }
  const el = document.getElementById('markowitzResults');
  if(el) el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--sub)">⏳ '+QI18n.t('msg_markowitz_calc')+'</div>';
  try {
    const r = await fetch('/api/v1/portfolio/optimize',{
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
      body: JSON.stringify({symbols:syms})
    });
    const d = await r.json();
    if(d.error){ toast(d.error,'error'); return; }
    if(el) el.innerHTML = `
      <div style="padding:10px;background:rgba(0,255,136,.05);border:1px solid rgba(0,255,136,.15);border-radius:8px;margin-bottom:8px">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center">
          <div><div style="font-family:var(--mono);font-size:14px;color:var(--jade)">${d.exp_return}%</div><div style="font-size:9px;color:var(--sub)">Erw. Rendite</div></div>
          <div><div style="font-family:var(--mono);font-size:14px;color:var(--amber)">${d.exp_volatility}%</div><div style="font-size:9px;color:var(--sub)">Volatilität</div></div>
          <div><div style="font-family:var(--mono);font-size:14px;color:var(--blue)">${d.sharpe_ratio}</div><div style="font-size:9px;color:var(--sub)">Sharpe</div></div>
        </div>
      </div>
      ${d.symbols.map((s,i)=>`
        <div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--muted)">
          <span style="font-size:12px;flex:1">${esc(String(s))}</span>
          <div style="flex:2;height:6px;background:var(--bg3);border-radius:3px">
            <div style="width:${((d.weights[i]??0)*100).toFixed(1)}%;height:100%;border-radius:3px;background:var(--jade)"></div>
          </div>
          <span style="font-family:var(--mono);font-size:12px;color:var(--jade);min-width:45px;text-align:right">${d.allocations[s]??0}%</span>
        </div>`).join('')}`;
  } catch(e){ toast(QI18n.t('msg_markowitz_error')+': '+e.message,'error'); }
}

// ── Backtest Compare ────────────────────────────────────────────────────────
async function runCompareBacktest(){
  const syms = document.getElementById('compareSymbols')?.value?.split(',').map(s=>s.trim()).filter(Boolean);
  const tf   = document.getElementById('compareTf')?.value || '1h';
  const can  = parseInt(document.getElementById('compareCandles')?.value, 10) || 500;
  const el   = document.getElementById('compareResults');
  if(!syms||syms.length<1){ toast(QI18n.t('err_min1_symbol'),'warning'); return; }
  if(el) el.innerHTML='<div style="text-align:center;padding:20px;color:var(--sub)">⏳ '+QI18n.t('msg_bt_running')+'</div>';
  try {
    const r = await fetch('/api/v1/backtest/compare',{
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
      body: JSON.stringify({symbols:syms,timeframe:tf,candles:can})
    });
    const d = await r.json();
    if(d.error){ toast(d.error,'error'); return; }
    const results = d.results||{};
    const cols = ['return_pct','win_rate','sharpe_ratio','max_drawdown','total_trades'];
    const labels= ['Return%','Win-Rate','Sharpe','MaxDD%','Trades'];
    if(el) el.innerHTML = `<div style="overflow-x:auto"><table style="width:100%;font-size:11px;border-collapse:collapse">
      <tr>${['Symbol',...labels].map(h=>`<th style="padding:6px 8px;text-align:${h==='Symbol'?'left':'right'};color:var(--sub);font-family:var(--mono);letter-spacing:1px;font-size:9px;text-transform:uppercase">${h}</th>`).join('')}</tr>
      ${syms.map(s=>{
        const res = results[s]||{};
        const color = (res.return_pct||0)>0?'var(--jade)':'var(--red)';
        return `<tr style="border-top:1px solid var(--muted)">
          <td style="padding:6px 8px;font-weight:600;color:var(--txt)">${s}</td>
          ${cols.map(c=>`<td style="padding:6px 8px;text-align:right;font-family:var(--mono);
            color:${c==='return_pct'?color:c==='max_drawdown'?'var(--red)':'var(--dim)'}">${res[c]!=null?res[c]:'—'}</td>`).join('')}
        </tr>`;
      }).join('')}
      </table></div>`;
  } catch(e){ toast(QI18n.t('msg_compare_error'),'error'); }
}

// ── Backtest History ────────────────────────────────────────────────────────
// NOTE: loadBtHistory is defined above (merged version that populates both #btHistory and #btHistoryList)

// ── Manual SL/TP Adjustment ─────────────────────────────────────────────────
async function adjustSL(symbol, entryPrice){
  const raw = prompt(`SL für ${symbol} (% vom Entry ${entryPrice.toFixed(4)})\nz.B. 2.5 für -2.5%:`);
  if(!raw) return;
  const pct = parseFloat(raw);
  if(isNaN(pct) || pct <= 0 || pct > 50){
    toast(QI18n.t('err_sl_invalid'),'error');
    return;
  }
  try {
    const r = await fetch('/api/v1/positions/'+encodeURIComponent(symbol)+'/sl',{
      method:'PATCH',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
      body: JSON.stringify({sl_pct: pct})
    });
    const d = await r.json();
    if(d.new_sl) toast(`✅ SL ${symbol}: ${d.new_sl.toFixed(4)}`,'success');
    else toast(d.error||QI18n.t('err_generic'),'error');
  } catch(e) {
    toast(QI18n.t('err_network')+': '+e.message,'error');
  }
}

// ── Web Push Notifications ──────────────────────────────────────────────────
let _pushSub = null;
async function requestPushPermission(){
  if(!('Notification' in window) || typeof Notification.requestPermission !== 'function'){
    toast(QI18n.t('toast_push_unsupported'),'warning'); return;
  }
  const perm = await Notification.requestPermission();
  if(perm === 'granted'){
    toast('🔔 '+QI18n.t('msg_push_enabled'),'success');
    document.getElementById('pushBtn').style.color='var(--jade)';
    document.getElementById('pushBtn').style.borderColor='var(--jade)';
    _storage.set('trevlix_push','1');
    // Register service worker
    if('serviceWorker' in navigator){
      try {
        await navigator.serviceWorker.register('/sw.js');
      } catch(e){}
    }
  } else {
    toast(QI18n.t('msg_push_denied'),'warning');
  }
}

// Auto-push on trade events via socket
function _checkPush(data){
  if(!('Notification' in window)||Notification.permission!=='granted') return;
  if(_storage.get('trevlix_push')!=='1') return;
  // Trade event from socket (has symbol, pnl, price, type)
  if(data.symbol){
    const key = data.type+'_'+data.symbol+'_'+(data.price||0);
    if(key !== window._lastPushKey){
      window._lastPushKey = key;
      const won = (data.pnl||0) >= 0;
      const body = data.type==='buy'
        ? `${QI18n.t('trade_buy')} ${data.symbol} @ ${data.price}`
        : `${QI18n.t('trade_sell')} ${data.symbol} | ${fmtS(data.pnl||0)} USDT`;
      new Notification('⚡ TREVLIX', {
        body: body,
        icon: '/static/icon-192.png',
        badge: '/static/icon-96.png',
        tag: 'trade',
      });
    }
    return;
  }
  // Legacy: update event with last_action
  if(data.last_action && data.last_action !== window._lastAction){
    window._lastAction = data.last_action;
    new Notification('⚡ TREVLIX', {
      body: data.last_action,
      icon: '/static/icon-192.png',
      badge: '/static/icon-96.png',
      tag: 'trade',
    });
  }
}

// NOTE: onTabSwitch is already defined above (line ~1113) with loadSharedAIStatus + loadFeatureImportance + loadBtHistory.
// Do NOT redefine it here — the earlier definition already covers all tab switch logic.

// Restore push pref
if(_storage.get('trevlix_push')==='1' && 'Notification' in window && Notification.permission==='granted'){
  const _pb=document.getElementById('pushBtn'); if(_pb) _pb.style.color='var(--jade)';
}


// ════════════════════════════════════════════════════════════════
// MULTI-EXCHANGE UI
// ════════════════════════════════════════════════════════════════

const MEX_NAMES = {
  cryptocom: 'Crypto.com', binance: 'Binance',
  bybit: 'Bybit', okx: 'OKX', kucoin: 'KuCoin'
};
const MEX_LOGOS = {
  cryptocom:'🔵', binance:'🟡', bybit:'⚫', okx:'⬛', kucoin:'🟢'
};

// Socket-Handler für Exchange-Updates
socket.on('exchange_update', mexUpdate);

function mexUpdate(data) {
  if (!data) return;
  // Legacy WS payload ({exchange, status}) -> Snapshot reload
  if (data.exchange && data.status && !data.exchanges) {
    mexReloadSnapshot();
    return;
  }
  // Fallback for old HTTP shape: list of exchanges
  if (Array.isArray(data)) {
    const mapped = {};
    data.forEach(ex => {
      const name = String(ex.exchange || '').toLowerCase();
      if (!name) return;
      mapped[name] = {
        enabled: !!ex.enabled,
        running: false,
        portfolio_value: 0,
        return_pct: 0,
        trade_count: 0,
        open_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        markets_count: 0,
        last_scan: '—',
        positions: [],
        error: ex.enabled ? 'Konfiguriert' : 'Nicht aktiviert',
      };
    });
    data = { exchanges: mapped, combined_pv: 0, combined_pnl: 0, total_pv: 0, total_pnl: 0 };
  }
  const exs = data.exchanges || {};
  const active = Object.values(exs).filter(e => e.running).length;

  // Gesamt-Header
  const pv = data.combined_pv || data.total_pv || 0;
  const pnl = data.combined_pnl || data.total_pnl || 0;
  const pvEl = document.getElementById('mex-total-pv');
  if (pvEl) pvEl.innerHTML = fmt(pv) + ' <span style="font-size:16px;opacity:.4">USDT</span>';
  const pnlEl = document.getElementById('mex-total-pnl');
  if (pnlEl) {
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl) + ' USDT ' + QI18n.t('total_pnl');
    pnlEl.className = 'pill ' + (pnl >= 0 ? 'up' : 'dn');
  }
  const acEl = document.getElementById('mex-active-count');
  if (acEl) acEl.textContent = active + ' Exchange' + (active !== 1 ? 's' : '') + ' ' + QI18n.t('label_active').toLowerCase();

  // Badge in Nav
  const badge = document.getElementById('exBadge');
  if (badge) {
    badge.textContent = active;
    badge.style.background = active > 0 ? 'var(--jade)' : '#f59e0b';
  }

  // Exchange-Karten
  const container = document.getElementById('mex-cards');
  if (!container) return;
  container.innerHTML = Object.entries(MEX_NAMES).map(([id, label]) => {
    const ex = exs[id] || {};
    const running = ex.running || false;
    const enabled = ex.enabled || false;
    const pv = ex.portfolio_value || 0;
    const ret = ex.return_pct || 0;
    const trades = ex.trade_count || 0;
    const open = ex.open_trades || 0;
    const wr = ex.win_rate || 0;
    const pnl = ex.total_pnl || 0;
    const err = ex.error || '';
    const marketCount = Number(ex.markets_count ?? ex.symbol_count ?? 0);
    const statusDetail = String(ex.status_detail || '');
    const positions = ex.positions || [];

    const statusDot = running
      ? '<span style="width:8px;height:8px;border-radius:50%;background:#00ff88;display:inline-block;box-shadow:0 0 6px #00ff88"></span>'
      : (enabled
          ? '<span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;display:inline-block"></span>'
          : '<span style="width:8px;height:8px;border-radius:50%;background:#374151;display:inline-block"></span>');

    const posHtml = positions.length ? positions.map(p => `
      <div style="display:flex;justify-content:space-between;padding:4px 0;border-top:1px solid var(--muted);font-size:11px">
        <span style="color:var(--txt);font-weight:600">${esc(String(p.symbol||''))}</span>
        <span style="font-family:var(--mono);color:var(--sub)">@ ${p.entry}</span>
        <span style="font-family:var(--mono);color:${p.pnl>=0?'var(--jade)':'var(--red)'}">${p.pnl>=0?'+':''}${p.pnl?.toFixed(2)} USDT</span>
        <button onclick="mexClosePos('${escJS(id)}','${escJS(p.symbol)}')" style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:9px;padding:2px 6px">✕</button>
      </div>`).join('') : '';

    return `
    <div class="card" style="border-color:${running?'rgba(0,255,136,.15)':enabled?'rgba(245,158,11,.1)':'rgba(255,255,255,.05)'}">
      <div class="card-hd" style="padding-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:20px">${MEX_LOGOS[id]}</span>
          <div>
            <div style="font-weight:800;font-size:14px;color:#e8f4ff">${label}</div>
            <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${marketCount} Märkte · ${ex.last_scan||'—'}${statusDetail ? ` · ${esc(statusDetail)}` : ''}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          ${statusDot}
          <span style="font-size:10px;font-family:var(--mono);color:${running?'var(--jade)':enabled?'#f59e0b':'var(--muted)'}">${running?QI18n.t('mex_active_label'):enabled?QI18n.t('mex_configured'):QI18n.t('mex_inactive')}</span>
        </div>
      </div>

      ${err ? `<div style="padding:6px 16px;background:rgba(239,68,68,.08);border-left:3px solid #ef4444;font-size:11px;color:#ef4444;margin-bottom:8px">${esc(String(err))}</div>` : ''}

      <div class="card-body" style="padding-top:0">
        <div class="sg" style="grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
          <div class="sc">
            <div class="sv" style="font-size:14px;color:${ret>=0?'var(--jade)':'var(--red)'}">${ret>=0?'+':''}${(ret??0).toFixed(2)}%</div>
            <div class="sl">Return</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px;color:${pnl>=0?'var(--jade)':'var(--red)'}">${pnl>=0?'+':''}${(pnl??0).toFixed(2)}</div>
            <div class="sl">PnL (USDT)</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px">${(wr??0).toFixed(1)}%</div>
            <div class="sl">Win-Rate</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px">${trades}</div>
            <div class="sl">Trades</div>
          </div>
        </div>

        ${positions.length ? `
        <div style="font-size:9px;font-family:var(--mono);color:var(--sub);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">${open} ${QI18n.t('open_positions').toUpperCase()}</div>
        ${posHtml}` : ''}

        <div style="display:flex;gap:8px;margin-top:12px">
          ${!enabled
            ? `<button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${escJS(id)}')">${esc(QI18n.t('mex_setup_keys'))}</button>`
            : running
              ? `<button class="btn btn-red"  style="flex:1;padding:8px;font-size:12px" onclick="mexStop('${escJS(id)}')">⏹ ${QI18n.t('btn_stop')}</button>
                 <button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${escJS(id)}')">🔑 Keys</button>`
              : `<button class="btn btn-jade" style="flex:1;padding:8px;font-size:12px" onclick="mexStart('${escJS(id)}')">▶ ${QI18n.t('btn_start')}</button>
                 <button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${escJS(id)}')">🔑 Keys</button>`
          }
        </div>
      </div>
    </div>`;
  }).join('');
}

async function mexReloadSnapshot() {
  try{
    const r = await fetch('/api/v1/exchanges', {
      headers:{'Authorization':'Bearer '+(_jwtToken||'')}
    });
    if(!r.ok) return;
    const payload = await r.json();
    mexUpdate(payload);
  }catch(e){
    console.warn('Exchange-Status laden fehlgeschlagen:', e);
  }
}

function mexStart(name)  { _emitSafe('start_exchange',  {exchange: name}); }
function mexStop(name)   { _emitSafe('stop_exchange',   {exchange: name}); }

function mexSetupKeys(name) {
  document.getElementById('mex-key-exchange').value = name;
  mexOnExchangeSelect(name);
  // Scroll to key form
  document.querySelector('#mex-key-exchange')?.scrollIntoView({behavior:'smooth', block:'center'});
}

function mexOnExchangeSelect(name) {
  // Only OKX and KuCoin require a passphrase – Crypto.com does NOT
  const needsPP = ['okx','kucoin'].includes(name);
  document.getElementById('mex-passphrase-wrap').style.display = needsPP ? '' : 'none';
}

function mexSaveKeys() {
  const exchange   = document.getElementById('mex-key-exchange').value;
  const api_key    = document.getElementById('mex-key-apikey').value.trim();
  const secret     = document.getElementById('mex-key-secret').value.trim();
  const passphrase = document.getElementById('mex-key-passphrase')?.value?.trim() || '';
  if (!api_key || !secret) { toast(QI18n.t('err_apikey_secret'), 'warning'); return; }
  if(!_emitSafe('save_exchange_keys', {exchange, api_key, secret, passphrase})) return;
  document.getElementById('mex-key-apikey').value = '';
  document.getElementById('mex-key-secret').value = '';
}

function mexClosePos(exchange, symbol) {
  if (!confirm(QI18n.t('confirm_close_exchange_pos').replace('{sym}',symbol).replace('{exc}',exchange.toUpperCase()))) return;
  _emitSafe('close_exchange_position', {exchange, symbol});
}

async function mexLoadTrades() {
  const el = document.getElementById('mex-trades-list');
  try {
    const r = await fetch('/api/v1/exchanges/combined/trades',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const trades = d.trades || [];
    if (!trades.length) {
      el.innerHTML = '<div class="empty"><div class="empty-ico">📋</div>'+QI18n.t('empty_no_trades')+'</div>';
      return;
    }
    el.innerHTML = trades.slice(0,50).map(t => {
      const won = (t.pnl||0) >= 0;
      return `
      <div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:11px;background:rgba(255,255,255,.05);border-radius:4px;padding:2px 6px;color:var(--sub);font-family:var(--mono)">${esc(String((t.exchange||'').toUpperCase()))}</span>
        <div style="flex:1">
          <div style="font-size:12px;font-weight:600;color:var(--txt)">${esc(String(t.symbol||''))}</div>
          <div style="font-size:10px;color:var(--sub)">${esc(String(t.reason||''))} · ${esc(String((t.closed||'').slice(0,16)))}</div>
        </div>
        <div style="font-family:var(--mono);font-size:13px;color:${won?'var(--jade)':'var(--red)'}">
          ${won?'+':''}${(t.pnl||0).toFixed(2)} USDT
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty">'+QI18n.t('empty_load_error')+'</div>';
  }
}

// Beim Wechsel auf Exchanges-Tab: Trades laden
onNav(id => { if (id === 'exchanges') mexLoadTrades(); });

// Beim Start: Exchange-Status laden
mexReloadSnapshot();

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{
  // [#40] Loading Skeleton ausblenden nach DOM-Ready
  const overlay = document.getElementById('pageLoadOverlay');
  if(overlay){ overlay.classList.add('ready'); setTimeout(()=>overlay.remove(), 500); }

  // [#38] Responsive Tables: Schatten-Indikator bei Scroll
  document.querySelectorAll('.table-responsive').forEach(wrap=>{
    const checkOverflow=()=>{
      wrap.classList.toggle('has-overflow', wrap.scrollLeft < wrap.scrollWidth - wrap.clientWidth - 1);
    };
    wrap.addEventListener('scroll', checkOverflow, {passive:true});
    checkOverflow();
  });

  initCharts();
  initVirginieChat();
  const taxYearEl=document.getElementById('taxYear');
  if(taxYearEl) taxYearEl.value=new Date().getFullYear();
  QI18n.init('langSwitcher');
  loadFollowers();
  updateGasFees();
  const sLang=document.getElementById('sLang');if(sLang)sLang.value=QI18n.lang;
  if(!_storage.get('trevlix_wiz')) setTimeout(showWizard,800);
});
