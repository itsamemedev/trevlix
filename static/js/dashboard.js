// [Socket.io Fix] Initiale State-Abfrage per HTTP, bevor WS verbunden ist
(async function _initState(){
  try {
    const r = await fetch('/api/v1/state', {credentials:'include'});
    if(r.ok){ const d=await r.json(); if(d&&d.running!==undefined) updateUI(d); }
  } catch(e){}
})();

const socket = io({
  transports:['websocket','polling'],
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 2000,
  reconnectionDelayMax: 10000,
  timeout: 20000,
});
let portChart=null, hourChart=null, pnlChart=null, btChartInst=null;
let lastData=null, allTrades=[], tradeFilter='all';
let logEntries=[], logPaused=false, currentHmSort='change';
let wizStep=0, wizEx='cryptocom';

// ── Nav ──────────────────────────────────────────────────────────────
function nav(id,el){
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('active'));
  document.getElementById('sec-'+id).classList.add('active');
  el.classList.add('active');
  if(id==='stats' && lastData) updateStats(lastData);
  if(id==='ai' && lastData?.ai) updateAI(lastData.ai);
}

// ── Format ───────────────────────────────────────────────────────────
const fmt=(n,d=2)=>Number(n||0).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct=n=>(n>=0?'+':'')+fmt(n)+'%';
const fmtS=(n,d=2)=>(n>=0?'+':'')+fmt(n,d);
const clr=n=>n>=0?'var(--green)':'var(--red)';

// ── Toast ────────────────────────────────────────────────────────────
function toast(msg, type='info'){
  const c=document.getElementById('toasts');
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
    el.innerHTML=entries.slice(0,120).map(e=>`<div class="log-row ${e.type}">
      <span class="log-time">${e.time}</span>
      <span style="flex-shrink:0;width:14px;text-align:center">${icons[e.cat]||'·'}</span>
      <span class="log-msg">${e.msg}</span></div>`).join('')||'<div class="empty" style="padding:12px">Leer</div>';
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
  document.getElementById('logPauseBtn').textContent=logPaused?'▶':'⏸';
}

// ── Charts init ──────────────────────────────────────────────────────
const cBase={responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(5,8,16,.95)',borderColor:'rgba(0,255,136,.2)',borderWidth:1,bodyColor:'#00ff88',bodyFont:{family:"'JetBrains Mono'"}}},
  scales:{x:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#2e3d5a',font:{family:"'JetBrains Mono'",size:8},maxTicksLimit:6}},
          y:{grid:{color:'rgba(255,255,255,0.03)'},ticks:{color:'#2e3d5a',font:{family:"'JetBrains Mono'",size:8}}}}};
function initCharts(){
  portChart=new Chart(document.getElementById('portChart'),{type:'line',
    data:{labels:[],datasets:[{data:[],borderColor:'#00ff88',backgroundColor:'rgba(0,255,136,0.06)',borderWidth:2,fill:true,tension:.4,pointRadius:0}]},options:cBase});
  hourChart=new Chart(document.getElementById('hourChart'),{type:'bar',
    data:{labels:Array.from({length:24},(_,i)=>i+'h'),datasets:[{data:Array(24).fill(0),backgroundColor:'rgba(0,255,136,.35)',borderRadius:3}]},options:cBase});
  pnlChart=new Chart(document.getElementById('pnlChart'),{type:'bar',
    data:{labels:[],datasets:[{data:[],backgroundColor:[],borderRadius:3}]},options:cBase});
}

// ── Main UI Update ───────────────────────────────────────────────────
function updateUI(d){
  lastData=d; allTrades=d.closed_trades||[];
  // Header
  document.getElementById('hSub').textContent=(d.exchange||'TREVLIX').toUpperCase()+' · '+(d.paper_trading?'PAPER':'LIVE')+' · v'+(d.bot_version||'1.0.0');
  // Hero
  document.getElementById('hVal').innerHTML=fmt(d.portfolio_value)+' <span style="font-size:18px;opacity:.4">USDT</span>';
  const r=d.return_pct||0, re=document.getElementById('hReturn');
  re.textContent=(r>=0?'▲ +':'▼ ')+fmt(Math.abs(r))+'%'; re.className='pill '+(r>=0?'up':'dn');
  document.getElementById('hPnl').textContent=fmtS(d.total_pnl)+' USDT Gesamt';
  // Status
  const b=document.getElementById('statusBadge'),t=document.getElementById('statusTxt');
  if(d.paused){b.className='h-badge pause';t.textContent=QI18n.t('status_paused');}
  else if(d.running){b.className='h-badge run';t.textContent=QI18n.t('status_running');}
  else{b.className='h-badge stop';t.textContent=QI18n.t('status_stopped');}
  document.getElementById('btnStart').disabled=d.running;
  document.getElementById('btnStop').disabled=!d.running;
  document.getElementById('btnPause').disabled=!d.running;
  document.getElementById('btnPause').innerHTML=d.paused?QI18n.t('btn_resume'):QI18n.t('btn_pause');
  document.getElementById('iterBadge').textContent=d.last_scan||'—';
  document.getElementById('lastScan').textContent='⏰ '+(d.last_scan||'—');
  document.getElementById('nextScan').textContent='→ '+(d.next_scan||'—');
  // Stats
  document.getElementById('sBal').textContent=fmt(d.balance,0);
  document.getElementById('sWin').textContent=d.total_trades>0?fmt(d.win_rate,1)+'%':'—';
  document.getElementById('sDd').textContent=fmt(d.max_drawdown,1)+'%';
  document.getElementById('sOpen').textContent=d.open_trades+'/'+(d.max_trades||5);
  document.getElementById('sTrades').textContent=d.total_trades;
  document.getElementById('sSharpe').textContent=d.sharpe>0?fmt(d.sharpe,2):'—';
  // Bottom row
  const dp=document.getElementById('sDailyPnl'); dp.textContent=fmtS(d.daily_pnl||0); dp.style.color=clr(d.daily_pnl||0);
  document.getElementById('sPF').textContent=d.profit_factor>0?fmt(d.profit_factor,2):'—';
  // Regime
  const bull=(d.market_regime||'').includes('Bullish');
  document.getElementById('regimeBadge').textContent=bull?'🐂 Bullish':'🐻 Bearish';
  document.getElementById('regimeBadge').className=bull?'badge-pill badge-bull':'badge-pill badge-bear';
  document.getElementById('btcBadge').textContent='BTC '+(d.btc_price?fmt(d.btc_price,0):'—');
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
  if(d.rl) document.getElementById('rlEpisodes').textContent=d.rl.episodes||0;
  // Positions + trades
  updatePositions(d.positions||[]);
  renderTrades(allTrades, tradeFilter);
  document.getElementById('tradeCount').textContent=d.total_trades;
  document.getElementById('posCount').textContent=d.open_trades;
  const pb=document.getElementById('posBadge'); pb.textContent=d.open_trades; pb.classList.toggle('show',d.open_trades>0);
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
    document.getElementById('chartPosBtns').innerHTML=d.positions.map(p=>
      `<button onclick="openChart('${p.symbol}')" class="filter-btn">${p.symbol.replace('/USDT','')} ${p.trade_type==='short'?'📉':'📈'} ${fmtPct(p.pnl_pct||0)}</button>`).join('');
  }
  // ARB stat
  document.getElementById('sArb').textContent=(d.arb_log||[]).length;
}

function updateFG(fg){
  const v=fg.value||50, c=v<25?'var(--green)':v<45?'var(--teal)':v<55?'var(--yellow)':v<75?'var(--orange)':'var(--red)';
  document.getElementById('fgVal').textContent=v; document.getElementById('fgVal').style.color=c;
  document.getElementById('fgLabel').textContent=fg.label||'Neutral';
  document.getElementById('fgUpdated').textContent=fg.last_update||'—';
  const pct=v/100;
  document.getElementById('fgRing').style.background=`conic-gradient(${c} ${pct}turn,var(--bg3) ${pct}turn)`;
  document.getElementById('fgBar').style.cssText=`width:${v}%;background:${c}`;
  document.getElementById('fgSub').textContent=fg.ok_to_buy?'✅ '+QI18n.t('buy_allowed_label'):'🚫 '+QI18n.t('buy_blocked_label');
  document.getElementById('fgSub').style.color=fg.ok_to_buy?'var(--green)':'var(--red)';
}
function updateCB(cb){
  document.getElementById('cbBanner').style.display=cb.active?'block':'none';
  if(cb.active) document.getElementById('cbSub').textContent=`${cb.losses} Verluste · Pause noch ${cb.remaining_min} Min · bis ${cb.until||'—'}`;
}
function updateGoal(g){
  const sec=document.getElementById('goalSection');
  if(!g||!g.target||g.target<=0){sec.style.display='none';return;}
  sec.style.display='block';
  document.getElementById('goalCurrent').textContent=fmt(g.current)+' USDT';
  document.getElementById('goalTarget').textContent='Ziel: '+fmt(g.target)+' USDT';
  document.getElementById('goalBar').style.width=g.pct+'%';
  document.getElementById('goalPct').textContent=g.pct+'%';
  document.getElementById('goalETA').textContent='ETA: '+g.eta;
  document.getElementById('goalBadge').textContent=g.pct+'% erreicht';
}
function updateDom(dom){
  document.getElementById('domCard').style.display='block';
  document.getElementById('domBTC').textContent=dom.btc_dom+'%';
  document.getElementById('domUSDT').textContent=dom.usdt_dom+'%';
  document.getElementById('domUpdated').textContent=dom.last_update||'—';
  const s=document.getElementById('domStatus');
  if(!dom.ok_usdt){s.textContent='🚨';s.style.color='var(--red)';}
  else if(!dom.ok_btc){s.textContent='⚠️';s.style.color='var(--yellow)';}
  else{s.textContent='✅';s.style.color='var(--green)';}
  document.getElementById('cDom').textContent='BTC '+dom.btc_dom+'%';
  document.getElementById('cDom').style.color=dom.ok_btc?'var(--green)':'var(--red)';
}
function updateAnomaly(anom){
  document.getElementById('anomalyBanner').style.display=anom.is_anomaly?'block':'none';
  if(anom.is_anomaly) document.getElementById('anomalyTxt').textContent=`Symbol: ${anom.anomaly_symbol||'?'} · Score: ${anom.last_score?.toFixed(3)||0}`;
  document.getElementById('anomSamples').textContent=anom.samples||0;
}
function updateGenetic(gen){
  document.getElementById('genFitness').textContent=gen.best_fitness>0?gen.best_fitness.toFixed(3):'—';
  document.getElementById('genGenCount').textContent='Gen.'+gen.generation;
  const el=document.getElementById('genHistory');
  if(gen.history?.length) el.innerHTML=gen.history.slice(0,8).map(h=>
    `<div class="log-row info"><span class="log-time">Gen.${h.gen}</span>
     <span class="log-msg">Fitness:${h.fitness} · SL:${(h.genome?.sl*100).toFixed(1)}% · TP:${(h.genome?.tp*100).toFixed(1)}%</span></div>`).join('');
  else el.innerHTML='<div class="empty" style="padding:8px">—</div>';
}

function updatePositions(positions){
  const el=document.getElementById('posList');
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
          <div style="font-size:13px;font-weight:700;display:flex;align-items:center;gap:5px;flex-wrap:wrap">${p.symbol} ${dcaBadge}${newsBadge}${shortBadge}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono);margin-top:2px">${(p.entry||0).toFixed(4)} → ${(p.current||0).toFixed(4)}</div>
          <div style="font-size:10px;margin-top:2px;color:var(--sub)">KI: <span style="color:var(--cyan)">${p.ai_score||'—'}%</span> · Win: <span style="color:var(--cyan)">${p.win_prob||'—'}%</span></div>
        </div>
        <div style="text-align:right">
          <div style="font-size:14px;font-weight:700;font-family:var(--mono);color:${c}">${pos?'+':''}${fmt(p.pnl)}</div>
          <div style="font-size:11px;font-family:var(--mono);color:${c}">${fmtPct(p.pnl_pct||0)}</div>
          <button onclick="closePos('${p.symbol}')" style="font-size:11px;padding:7px 10px">✕ ${QI18n.t('close_label')}</button>
              <button class="btn btn-info" style="font-size:11px;padding:7px 10px" onclick="adjustSL('${p.symbol}',${p.entry})">🎯 SL</button>
              <button class="btn btn-teal" style="font-size:11px;padding:7px 10px;display:none"  style="margin-top:5px;padding:3px 9px;border-radius:5px;background:rgba(255,61,113,.15);border:1px solid rgba(255,61,113,.3);color:var(--red);font-size:10px;font-weight:700;cursor:pointer;font-family:var(--font)">✕ ${QI18n.t('close_label')}</button>
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
  if(!fl.length){el.innerHTML='<div class="empty"><div class="empty-ico">📋</div>'+QI18n.t('no_trades_yet')+'</div>';return;}
  el.innerHTML=fl.slice(0,80).map(t=>{
    const won=(t.pnl||0)>0,c=clr(t.pnl||0),isShort=t.trade_type==='short';
    const ns=t.news_score!==0?` 📰${(t.news_score||0)>=0?'+':''}${(t.news_score||0).toFixed(2)}`:'';
    const dca=t.dca_level>0?` DCA${t.dca_level}`:'';
    return `<div class="trade-row">
      <div style="font-size:18px">${isShort?'📉':(won?'✅':'❌')}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:13px;font-weight:700">${t.symbol}${isShort?' SHORT':''}${dca}</div>
        <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${(t.entry||0).toFixed(4)} → ${(t.exit||0).toFixed(4)} · ${t.reason||'—'}${ns}</div>
        <div style="font-size:10px;color:var(--muted)">${(t.closed||'—').slice(0,10)}</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:${c}">${fmtS(t.pnl||0)}</div>
        <div style="font-size:11px;font-family:var(--mono);color:${c}">${fmtPct(t.pnl_pct||0)}</div>
      </div>
    </div>`;
  }).join('');
}

function updateStats(d){
  document.getElementById('pStart').textContent=fmt(d.initial_balance)+' USDT';
  document.getElementById('pCurrent').textContent=fmt(d.portfolio_value)+' USDT';
  const pp=document.getElementById('pPnl'); pp.textContent=fmtS(d.total_pnl)+' USDT'; pp.style.color=clr(d.total_pnl);
  const pr=document.getElementById('pReturn'); pr.textContent=fmtPct(d.return_pct); pr.style.color=clr(d.return_pct);
  document.getElementById('pDd').textContent=fmt(d.max_drawdown,1)+'%';
  document.getElementById('pSharpe').textContent=d.sharpe>0?fmt(d.sharpe,2):'—';
  document.getElementById('pTotal').textContent=d.total_trades;
  document.getElementById('pWR').textContent=d.total_trades>0?fmt(d.win_rate,1)+'%':'—';
  document.getElementById('pAvgW').textContent=fmt(d.avg_win)+' USDT';
  document.getElementById('pAvgL').textContent=fmt(d.avg_loss)+' USDT';
  document.getElementById('pPF').textContent=d.profit_factor>0?fmt(d.profit_factor,2):'—';
  document.getElementById('pDCA').textContent=allTrades.filter(t=>t.dca_level>0).length;
  document.getElementById('pShorts').textContent=allTrades.filter(t=>t.trade_type==='short').length;
  document.getElementById('pArbCount').textContent=(d.arb_log||[]).length;
  // Top coins
  const coinPnl={};
  allTrades.forEach(t=>{coinPnl[t.symbol]=(coinPnl[t.symbol]||0)+(t.pnl||0);});
  document.getElementById('topCoins').innerHTML=Object.entries(coinPnl).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([sym,pnl])=>
    `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);font-size:12px">
       <span style="font-weight:600">${sym}</span>
       <span style="font-family:var(--mono);font-weight:700;color:${clr(pnl)}">${fmtS(pnl)}</span></div>`).join('')||'<div class="empty" style="padding:8px">—</div>';
  // Hour chart
  if(hourChart && allTrades.length){
    const hd=Array(24).fill(0);
    allTrades.forEach(t=>{if(t.closed) hd[new Date(t.closed).getHours()]+=(t.pnl||0);});
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
}

function updateAI(ai){
  document.getElementById('aiVer').textContent=ai.is_trained?'v'+ai.training_ver:'Training...';
  document.getElementById('aiStatusMsg').textContent=ai.status_msg||'—';
  document.getElementById('aiStatusMsg').style.color=ai.is_trained?'var(--green)':'var(--sub)';
  document.getElementById('aiProgPct').textContent=ai.progress_pct+'%';
  document.getElementById('aiProgBar').style.width=ai.progress_pct+'%';
  document.getElementById('aiProgBar').style.background=ai.progress_pct>=100?'var(--green)':'var(--cyan)';
  document.getElementById('aiWF').textContent=ai.wf_accuracy>0?ai.wf_accuracy+'%':'—';
  document.getElementById('aiBullAcc').textContent=ai.bull_accuracy>0?ai.bull_accuracy+'%':'—';
  document.getElementById('aiBearAcc').textContent=ai.bear_accuracy>0?ai.bear_accuracy+'%':'—';
  document.getElementById('aiSamples').textContent=ai.samples||0;
  document.getElementById('aiBullS').textContent=ai.bull_samples||0;
  document.getElementById('aiBearS').textContent=ai.bear_samples||0;
  document.getElementById('aiAllowed').textContent=ai.allowed_count||0;
  document.getElementById('aiBlocked').textContent=ai.blocked_count||0;
  document.getElementById('aiNews').textContent=ai.status_msg?.includes('News')||true?'✅':'—';
  document.getElementById('aiOnchain').textContent='✅';
  document.getElementById('aiDecCount').textContent=ai.ai_log?.length||0;
  // Weights
  const wl=document.getElementById('weightList');
  if(ai.weights?.length) wl.innerHTML=ai.weights.map(w=>{
    const pct=Math.min(100,Math.round(w.weight/3.5*100));
    const c=w.weight>1.2?'var(--green)':w.weight<0.5?'var(--red)':'var(--cyan)';
    return `<div class="weight-row"><span class="weight-name">${w.name}</span>
      <div class="weight-bar-wrap"><div class="weight-bar" style="width:${pct}%;background:${c}"></div></div>
      <span class="weight-val" style="color:${c}">${w.weight}×</span>
      <span style="font-size:9px;color:var(--sub);width:32px;flex-shrink:0;text-align:right">${w.win_rate}%</span></div>`;
  }).join('');
  // AI log
  const dl=document.getElementById('aiDecLog');
  if(ai.ai_log?.length) dl.innerHTML=ai.ai_log.map(e=>
    `<div class="log-row ${e.allowed?'success':'error'}">
      <span class="log-time">${e.time}</span>
      <span class="log-msg">${e.reason||'—'} (${e.prob||0}%)</span></div>`).join('');
}

function updateSignals(sigs){
  const el=document.getElementById('sigList');
  if(!sigs.length){el.innerHTML='<div class="empty"><div class="empty-ico">📡</div>'+QI18n.t('waiting_for_signals')+'</div>';return;}
  document.getElementById('sigCount').textContent=sigs.length;
  el.innerHTML=sigs.slice(0,25).map(s=>{
    const nc=s.news_score>0.2?'var(--green)':s.news_score<-0.2?'var(--red)':'var(--sub)';
    return `<div style="background:var(--bg2);border-left:3px solid var(--green);border-radius:9px;padding:9px 11px;margin-bottom:5px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:13px;font-weight:700">${s.symbol}</span>
        <span style="font-size:10px;font-family:var(--mono);color:var(--sub)">${s.time||'—'}</span>
      </div>
      <div style="font-size:10px;color:var(--sub);margin-top:3px;font-family:var(--mono)">RSI:${s.rsi||'—'} · Conf:${s.confidence?Math.round(s.confidence*100):0}% · ${s.mtf_desc||''}</div>
      ${s.news_headline?`<div style="font-size:10px;color:${nc};margin-top:3px;font-style:italic">${s.news_headline.slice(0,80)}</div>`:''}
    </div>`;
  }).join('');
}

function updateActivity(acts){
  const el=document.getElementById('actList');
  if(!acts.length){el.innerHTML='<div class="empty"><div class="empty-ico">⚡</div>Starte TREVLIX</div>';return;}
  el.innerHTML=acts.slice(0,12).map(a=>{
    const c={success:'var(--green)',error:'var(--red)',warning:'var(--yellow)',info:'var(--cyan)'}[a.type]||'var(--sub)';
    return `<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)">
      <div style="font-size:18px;flex-shrink:0">${a.icon}</div>
      <div style="flex:1"><div style="font-size:12px;font-weight:700;color:${c}">${a.title}</div>
        <div style="font-size:10px;color:var(--sub);margin-top:1px">${a.detail}</div></div>
      <div style="font-size:10px;color:var(--muted);font-family:var(--mono);flex-shrink:0">${a.time}</div>
    </div>`;
  }).join('');
}

function renderAlerts(alerts){
  document.getElementById('alertCount').textContent=alerts.filter(a=>!a.triggered).length;
  const el=document.getElementById('alertList');
  if(!alerts.length){el.innerHTML='<div class="empty" style="padding:8px">Keine Alerts</div>';return;}
  el.innerHTML=alerts.map(a=>`<div class="alert-item" style="${a.triggered?'opacity:.4':''}">
    <div style="font-size:16px">${a.triggered?'✅':'🔔'}</div>
    <div style="flex:1"><div style="font-size:12px;font-weight:700">${a.symbol}</div>
      <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${a.direction==='above'?'↑ Über':'↓ Unter'} ${a.target_price}</div></div>
    ${!a.triggered?`<button onclick="deleteAlert(${a.id})" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:16px;padding:4px">🗑</button>`:''}`).join('');
}

function renderArbLog(arb){
  const cnt=(arb||[]).length;
  document.getElementById('arbCountBadge').textContent=cnt;
  document.getElementById('arbCount2').textContent=cnt;
  document.getElementById('arbCard').style.display=cnt>0?'block':'none';
  const html=arb.slice(0,5).map(a=>`<div class="arb-item">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:13px;font-weight:700">${a.symbol}</span>
      <span style="font-family:var(--mono);font-weight:900;font-size:13px;color:var(--yellow)">+${a.spread}%</span>
    </div>
    <div style="font-size:10px;color:var(--sub);margin-top:3px;font-family:var(--mono)">Kauf: ${a.buy} → Verkauf: ${a.sell} · ${a.time||'—'}</div>
  </div>`).join('');
  document.getElementById('arbLogHome').innerHTML=html||'<div class="empty" style="padding:8px">—</div>';
  document.getElementById('arbList2').innerHTML=html||'<div class="empty" style="padding:8px">Noch kein Scan</div>';
}

// ── Heatmap ──────────────────────────────────────────────────────────
async function loadHeatmap(sortBy){
  currentHmSort=sortBy;
  document.querySelectorAll('[id^="hmBtn"]').forEach(b=>b.classList.remove('active'));
  const btn=document.getElementById('hmBtn'+sortBy); if(btn) btn.classList.add('active');
  document.getElementById('heatmapGrid').innerHTML='<div class="empty" style="grid-column:span 5;padding:16px">⏳ Lade...</div>';
  try{
    const data=await(await fetch('/api/heatmap')).json();
    if(data.error){document.getElementById('heatmapGrid').innerHTML=`<div class="empty" style="grid-column:span 5">${data.error}</div>`;return;}
    const sorted=[...data].sort((a,b)=>sortBy==='volume'?b.volume-a.volume:sortBy==='news'?b.news_score-a.news_score:b.change-a.change);
    document.getElementById('heatmapGrid').innerHTML=sorted.slice(0,40).map(coin=>{
      const pct=coin.change, int=Math.min(1,Math.abs(pct)/10);
      const bg=pct>=0?`rgba(0,${Math.round(100+130*int)},${Math.round(80*int)},${0.18+0.5*int})`:`rgba(${Math.round(180+75*int)},${Math.round(30*int)},${Math.round(60*int)},${0.18+0.5*int})`;
      const sym=coin.symbol.replace('/USDT','');
      const nc=coin.news_score>0.3?'🟢':coin.news_score<-0.3?'🔴':'⬜';
      const cls=(coin.in_pos?' inpos':'')+(coin.short?' inshort':'');
      return `<div class="hm-cell${cls}" style="background:${bg}" onclick="openChart('${coin.symbol}')">
        <div class="hm-symbol">${sym}</div>
        <div class="hm-pct">${pct>=0?'+':''}${pct.toFixed(1)}%</div>
        <div class="hm-news">${nc}</div>
      </div>`;
    }).join('');
  }catch(e){document.getElementById('heatmapGrid').innerHTML='<div class="empty" style="grid-column:span 5">Fehler: '+e+'</div>';}
}

// ── Chart ────────────────────────────────────────────────────────────
async function loadChart(){
  const sym=document.getElementById('chartSym').value.trim().replace('-','/').toUpperCase();
  const tf=document.getElementById('chartTf').value;
  document.getElementById('chartBadge').textContent=sym+' '+tf;
  const chartEl=document.getElementById('tvChart');
  chartEl.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--sub);font-size:12px">⏳ Lade Chart...</div>';
  try{
    const data=await(await fetch(`/api/ohlcv/${sym.replace('/','-')}?tf=${tf}&limit=200`)).json();
    if(data.error){chartEl.innerHTML=`<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:12px">${data.error}</div>`;return;}
    renderTVChart(data, chartEl);
    // News
    try{
      const ndata=await(await fetch(`/api/v1/news/${sym.replace('/USDT','')}`)).json();
      if(ndata.headline&&ndata.headline!=='—'){
        const nc=ndata.score>=0?'var(--green)':'var(--red)';
        document.getElementById('newsFeed').innerHTML=`<div class="news-item">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:11px;font-weight:700;color:${nc}">${ndata.score>=0?'+':''}${(ndata.score).toFixed(2)} Score</span>
            <span style="font-size:10px;color:var(--sub)">${ndata.count} Artikel</span>
          </div>
          <div style="font-size:11px;line-height:1.6">${ndata.headline}</div>
        </div>`;
        document.getElementById('cNews').textContent=(ndata.score>=0?'+':'')+ndata.score.toFixed(2);
        document.getElementById('cNews').style.color=nc;
      }
    }catch(e){}
    // On-chain
    try{
      const oc=await(await fetch(`/api/v1/onchain/${sym.replace('/USDT','')}`)).json();
      document.getElementById('cOnchain').textContent=(oc.score>=0?'+':'')+oc.score.toFixed(2);
      document.getElementById('cOnchain').style.color=oc.score>=0?'var(--green)':'var(--red)';
    }catch(e){}
    const sig=lastData?.signal_log?.find(s=>s.symbol===sym);
    if(sig){
      document.getElementById('cRSI').textContent=sig.rsi||'—';
      document.getElementById('cMTF').textContent=sig.mtf_desc||'—';
      document.getElementById('cVol').textContent=sig.confidence?Math.round(sig.confidence*100)+'%':'—';
    }
  }catch(e){chartEl.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:12px">Fehler: '+e+'</div>';}
}
function openChart(sym){document.getElementById('chartSym').value=sym;nav('chart',document.getElementById('nb-chart'));loadChart();}
function renderTVChart(data, el){
  el.innerHTML='';
  if(!data.ohlcv?.length) return;
  const chart=LightweightCharts.createChart(el,{
    layout:{background:{color:'#020408'},textColor:'#2e3d5a'},
    grid:{vertLines:{color:'rgba(255,255,255,.025)'},horzLines:{color:'rgba(255,255,255,.025)'}},
    rightPriceScale:{borderColor:'rgba(255,255,255,.04)'},
    timeScale:{borderColor:'rgba(255,255,255,.04)',timeVisible:true},
    handleScroll:true,handleScale:true,
  });
  const cs=chart.addCandlestickSeries({upColor:'#00ff88',downColor:'#ef4444',borderUpColor:'#00ff88',borderDownColor:'#ef4444',wickUpColor:'#00ff88',wickDownColor:'#ef4444'});
  const vs=chart.addHistogramSeries({color:'rgba(0,255,136,.2)',priceFormat:{type:'volume'},priceScaleId:'vol'});
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
}

// ── Backtest ─────────────────────────────────────────────────────────
function runBacktest(){
  document.getElementById('btStatus').textContent='⏳ Backtest läuft...';
  document.getElementById('btBtn').disabled=true;
  document.getElementById('btResultSection').style.display='none';
  socket.emit('run_backtest',{
    symbol:document.getElementById('btSym').value.trim(),
    timeframe:document.getElementById('btTf').value,
    candles:parseInt(document.getElementById('btCandles').value),
    sl:parseFloat(document.getElementById('btSL').value)/100,
    tp:parseFloat(document.getElementById('btTP').value)/100,
    vote:parseFloat(document.getElementById('btVote').value)/100,
  });
}
async function loadBtHistory(){
  try{
    const data=await(await fetch('/api/backtest/history')).json();
    const el=document.getElementById('btHistory');
    if(!data.length){el.innerHTML='<div class="empty" style="padding:8px">—</div>';return;}
    el.innerHTML=data.map(r=>`<div style="background:var(--bg2);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:12px;font-weight:700">${r.symbol} ${r.timeframe}</div>
        <div style="font-size:10px;color:var(--sub)">${r.candles} Kerzen · ${r.total_trades} Trades</div></div>
      <div style="text-align:right">
        <div style="font-size:13px;font-weight:700;font-family:var(--mono);color:${(r.win_rate||0)>50?'var(--green)':'var(--red)'}">${(r.win_rate||0).toFixed(1)}%</div>
        <div style="font-size:10px;font-family:var(--mono);color:${(r.total_pnl||0)>=0?'var(--green)':'var(--red)'}">${fmtS(r.total_pnl||0)} USDT</div>
      </div></div>`).join('');
  }catch(e){}
}

// ── Tax ──────────────────────────────────────────────────────────────
async function loadTax(){
  const year=document.getElementById('taxYear').value||new Date().getFullYear();
  const method=document.getElementById('taxMethod').value;
  try{
    const data=await(await fetch(`/api/tax_report?year=${year}&method=${method}`)).json();
    if(data.error){toast(data.error,'error');return;}
    const s=data.summary;
    document.getElementById('taxResult').style.display='block';
    document.getElementById('taxGains').textContent=fmtS(s.total_gains)+' USDT';
    document.getElementById('taxLosses').textContent=fmtS(s.total_losses)+' USDT';
    const tn=document.getElementById('taxNet'); tn.textContent=fmtS(s.net_pnl)+' USDT'; tn.style.color=clr(s.net_pnl);
    document.getElementById('taxTaxable').textContent=fmt(s.taxable_gains)+' USDT';
    document.getElementById('taxFees').textContent=fmt(s.total_fees)+' USDT';
    document.getElementById('taxCount').textContent=s.trade_count+'T ('+s.win_count+'G / '+s.loss_count+'V)';
    const wb=document.getElementById('taxWarnBar');
    if(s.taxable_gains>600){wb.style.display='flex';document.getElementById('taxWarnTxt').textContent='Steuerpflichtige Gewinne > 600 USDT — Steuerberater empfohlen!';}
    else wb.style.display='none';
    document.getElementById('taxTable').innerHTML=data.gains.slice(0,30).map(g=>
      `<div style="display:grid;grid-template-columns:80px 1fr 1fr;gap:6px;padding:6px 0;border-bottom:1px solid var(--line);font-size:10px;font-family:var(--mono)">
        <span style="color:var(--sub)">${g.date}</span><span>${g.symbol}</span>
        <span style="color:var(--green);text-align:right">${fmtS(g.net_pnl)}</span></div>`).join('')||'<div class="empty" style="padding:8px">—</div>';
  }catch(e){toast('Fehler: '+e,'error');}
}
function exportTaxCSV(){const y=document.getElementById('taxYear').value||new Date().getFullYear();window.open(`/api/tax_report?year=${y}&format=csv`);}
function exportCSV(){window.open('/api/export/csv');}
function exportJSON(){window.open('/api/export/json');}

// ── Bot controls ─────────────────────────────────────────────────────
function startBot(){socket.emit('start_bot');}
function stopBot(){socket.emit('stop_bot');}
function pauseBot(){socket.emit('pause_bot');}
let _lastClosedSymbol = null;
let _undoTimeout = null;

function closePos(sym){
  if(!confirm(QI18n.t('confirm_close_pos').replace('{sym}',sym))) return;
  _lastClosedSymbol = sym;
  socket.emit('close_position',{symbol:sym});
  showUndoBar(sym);
}

function showUndoBar(sym){
  const bar = document.getElementById('undoBar');
  const msg = document.getElementById('undoMsg');
  msg.textContent = sym + ' closed';
  bar.style.display = 'flex';
  clearTimeout(_undoTimeout);
  _undoTimeout = setTimeout(()=>{ bar.style.display='none'; _lastClosedSymbol=null; }, 8000);
}

function undoClose(){
  if(!_lastClosedSymbol) return;
  socket.emit('undo_close', {symbol: _lastClosedSymbol});
  document.getElementById('undoBar').style.display = 'none';
  clearTimeout(_undoTimeout);
  _lastClosedSymbol = null;
  toast('↩ Undo close — attempting','info');
}
// old closePos replaced above
function _closePos_orig(sym){if(confirm(QI18n.t('confirm_close_pos').replace('{sym}',sym))) socket.emit('close_position',{symbol:sym});}
function forceTrain(){socket.emit('force_train');toast('🧠 '+QI18n.t('ai_training')+'...','info');}
function forceOptimize(){socket.emit('force_optimize');toast('🔬 '+QI18n.t('toast_optimize'),'info');}
function forceGenetic(){socket.emit('force_genetic');toast('🧬 '+QI18n.t('toast_genetic'),'info');}
function resetAI(){if(confirm(QI18n.t('confirm_reset_ai'))) socket.emit('reset_ai');}
function manualBackup(){socket.emit('manual_backup');}
function sendReport(){socket.emit('send_daily_report');}
function resetCB(){socket.emit('reset_circuit_breaker');}
function refreshDom(){socket.emit('update_dominance');toast(QI18n.t('dominance')+'...','info');}
function scanArb(){socket.emit('scan_arbitrage');toast(QI18n.t('btn_arbitrage')+'...','info');}
function addAlert(){
  const sym=document.getElementById('alertSym').value.trim().toUpperCase();
  const target=parseFloat(document.getElementById('alertTarget').value);
  const dir=document.getElementById('alertDir').value;
  if(!sym||!target){toast('Symbol und Preis eingeben!','error');return;}
  socket.emit('add_price_alert',{symbol:sym,target,direction:dir});
  document.getElementById('alertTarget').value='';
}
function deleteAlert(id){socket.emit('delete_price_alert',{id});}

// ── Settings ─────────────────────────────────────────────────────────

function changeLang(lang){
  QI18n.setLang(lang);
  socket.emit('update_config',{language:lang});
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
  toast('✅ Preset "'+name+'" geladen','success');
}
function saveSettings(){
  socket.emit('update_config',{
    stop_loss_pct:parseFloat(document.getElementById('sSL').value)/100,
    take_profit_pct:parseFloat(document.getElementById('sTP').value)/100,
    max_open_trades:parseInt(document.getElementById('sMaxTrades').value),
    scan_interval:parseInt(document.getElementById('sInterval').value),
    paper_trading:document.getElementById('sPaper').checked,
    trailing_stop:document.getElementById('sTrailing').checked,
    ai_min_confidence:parseFloat(document.getElementById('sAiConf').value)/100,
    circuit_breaker_losses:parseInt(document.getElementById('sCBLosses').value),
    circuit_breaker_min:parseInt(document.getElementById('sCBMin').value),
    max_spread_pct:parseFloat(document.getElementById('sSpread').value),
    use_fear_greed:document.getElementById('sFG').checked,
    ai_use_kelly:document.getElementById('sKelly').checked,
    mtf_enabled:document.getElementById('sMTF').checked,
    use_news:document.getElementById('sNews').checked,
    use_onchain:document.getElementById('sOnchain').checked,
    use_dominance:document.getElementById('sDom').checked,
    use_anomaly:document.getElementById('sAnomaly').checked,
    use_dca:document.getElementById('sDCA').checked,
    dca_max_levels:parseInt(document.getElementById('sDCALvl').value),
    use_partial_tp:document.getElementById('sPartialTP').checked,
    use_shorts:document.getElementById('sShorts').checked,
    use_arbitrage:document.getElementById('sArb').checked,
    arb_min_spread_pct:parseFloat(document.getElementById('sArbSpread').value),
    genetic_enabled:document.getElementById('sGenetic').checked,
    rl_enabled:document.getElementById('sRL').checked,
    backup_enabled:document.getElementById('sBackup').checked,
    portfolio_goal:parseFloat(document.getElementById('sGoal').value)||0,
    news_block_score:parseFloat(document.getElementById('sNewsBlock').value),
  });
}
function saveKeys(){
  socket.emit('save_api_keys',{api_key:document.getElementById('cfgKey').value,
    secret:document.getElementById('cfgSecret').value,exchange:document.getElementById('sExchange').value});
}
function saveDiscord(){
  socket.emit('update_discord',{webhook:document.getElementById('sDiscord').value,
    report_hour:parseInt(document.getElementById('sReportHour').value)});
}
async function createToken(){
  try{
    const res=await fetch('/api/v1/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:'dashboard'})});
    const data=await res.json();
    const box=document.getElementById('apiTokenBox');
    box.style.display='block'; box.textContent=data.token||'—';
    toast('🔑 Token erstellt ('+data.expires_hours+'h gültig)','success');
  }catch(e){toast('Fehler: '+e,'error');}
}

// ── Wizard ───────────────────────────────────────────────────────────
function showWizard(){document.getElementById('wizardOverlay').style.display='flex';wizStep=0;updateWizDots();}
function wizNext(){
  if(wizStep<4){document.getElementById('wz'+wizStep).classList.remove('active');wizStep++;document.getElementById('wz'+wizStep).classList.add('active');updateWizDots();}
}
function updateWizDots(){for(let i=0;i<5;i++) document.getElementById('wd'+i).className='wd'+(i<=wizStep?' done':'');}
function wizSelEx(ex,el){document.querySelectorAll('#wz1 .btn').forEach(b=>b.style.borderColor='rgba(0,255,136,.2)');el.style.borderColor='var(--cyan)';wizEx=ex;document.getElementById('sExchange').value=ex;}
function wizSaveKeys(){socket.emit('save_api_keys',{api_key:document.getElementById('wzKey').value,secret:document.getElementById('wzSecret').value,exchange:wizEx});wizNext();}
function wizPreset(name,el){document.querySelectorAll('#wz3 .btn').forEach(b=>b.style.opacity='.5');el.style.opacity='1';applyPreset(name);}
function wizFinish(){document.getElementById('wizardOverlay').style.display='none';saveSettings();toast(QI18n.t('wiz_ready'),'success');}

// ── Socket events ────────────────────────────────────────────────────
socket.on('connect',()=>{
  addLog(QI18n.t('dashboard_connected'),'success','system');
  toast('📡 Dashboard verbunden','success');
  // Nach Verbindung sofort State anfragen (bei Reconnect)
  socket.emit('request_state');
});
socket.on('connect_error',(err)=>{
  addLog('Socket-Verbindungsfehler: '+err.message,'error','system');
  toast('⚠️ Socket-Fehler – Verbindung wird wiederhergestellt...','warning');
});
socket.on('disconnect',(reason)=>{
  addLog(QI18n.t('dashboard_disconnected')+' ('+reason+')','error','system');
  toast('⚠️ '+QI18n.t('dashboard_disconnected'),'warning');
});
socket.on('auth_error',(d)=>{
  addLog('Auth-Fehler: '+(d&&d.msg||'Nicht authentifiziert'),'error','system');
  setTimeout(()=>location.href='/login',2000);
});
socket.on('update', d=>{updateUI(d);});
socket.on('ai_update', ai=>{updateAI(ai);});
socket.on('genetic_update', g=>{
  document.getElementById('genFitness').textContent=(g.fitness||0).toFixed(3);
  document.getElementById('genGenCount').textContent='Gen.'+g.gen+'/'+g.total;
});
socket.on('status', d=>{
  toast(d.msg, d.type||'info');
  addLog(d.msg, d.type||'info', 'system');
});
socket.on('trade', d=>{
  const won=(d.pnl||0)>=0;
  const msg=d.type==='buy'?`🟢 ${QI18n.t('trade_buy')} ${d.symbol} @ ${d.price}`:
    `${won?'✅':'❌'} ${QI18n.t('trade_sell')} ${d.symbol} | ${fmtS(d.pnl||0)} USDT`;
  addLog(msg, d.type==='buy'?'success':(won?'success':'error'), 'trade');
  toast(msg, d.type==='buy'?'success':(won?'success':'warning'));
});
socket.on('price_alert', d=>{
  toast(`🔔 Alert: ${d.symbol} @ ${d.price}`,'warning');
  addLog(`🔔 ${QI18n.t('alert_triggered')}: ${d.symbol}`,'warning','system');
});
socket.on('backtest_result', d=>{
  document.getElementById('btBtn').disabled=false;
  if(d.error){document.getElementById('btStatus').textContent='❌ '+d.error;toast(d.error,'error');return;}
  document.getElementById('btStatus').textContent='';
  document.getElementById('btResultSection').style.display='block';
  document.getElementById('btBadge').textContent=d.symbol+' '+d.timeframe;
  const btEl=document.getElementById('btWR'); btEl.textContent=d.win_rate+'%';btEl.style.color=d.win_rate>50?'var(--green)':'var(--red)';
  const btPnl=document.getElementById('btPnl'); btPnl.textContent=fmtS(d.total_pnl);btPnl.style.color=clr(d.total_pnl);
  const btPF=document.getElementById('btPF'); btPF.textContent=d.profit_factor;btPF.style.color=d.profit_factor>1.2?'var(--green)':'var(--red)';
  document.getElementById('btDD').textContent=d.max_drawdown+'%';
  if(btChartInst){btChartInst.destroy();btChartInst=null;}
  if(d.equity_curve?.length){
    const cc=d.return_pct>=0?'#00ff88':'#ef4444';
    btChartInst=new Chart(document.getElementById('btChart'),{type:'line',
      data:{labels:d.equity_curve.map(e=>e.time?.slice(5,16)||''),
        datasets:[{data:d.equity_curve.map(e=>e.value),borderColor:cc,backgroundColor:cc==='#00ff88'?'rgba(0,255,136,.06)':'rgba(255,61,113,.06)',borderWidth:2,fill:true,tension:.4,pointRadius:0}]},
      options:cBase});
  }
  toast(`✅ Backtest: WR ${d.win_rate}% | PnL ${fmtS(d.total_pnl)} USDT`,'success');
  addLog(`Backtest ${d.symbol}: WR ${d.win_rate}% PnL ${fmtS(d.total_pnl)}`,'success','system');
});


// ── GitHub Updater ───────────────────────────────────────────────────
function checkUpdate(){
  toast('🔍 '+QI18n.t('checking_github'),'info');
  socket.emit('check_update');
}
function applyUpdate(){
  if(!confirm(QI18n.t('confirm_install_update'))) return;
  toast('⬆ '+QI18n.t('installing_update'),'info');
  socket.emit('apply_update');
}
function rollbackUpdate(){
  if(!confirm(QI18n.t('confirm_rollback'))) return;
  socket.emit('rollback_update');
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
    el.style.display='block'; el.textContent=d.changelog;
    document.getElementById('updateChangelogShort').textContent = d.changelog.split('\n')[0].slice(0,60);
  }
}
socket.on('update_status', d => { renderUpdateStatus(d); toast(d.update_available ? '🎉 Update verfügbar! v'+d.latest : '✅ Aktuell', d.update_available?'success':'info'); });
socket.on('update_result', d => { toast(d.status==='success'?'✅ Update installiert – Neustart...':'⚠ Update teilweise', d.status==='success'?'success':'warning'); if(d.status==='success') setTimeout(()=>location.reload(),3000); });


// ── Theme Toggle ─────────────────────────────────────────────────────────
function toggleTheme(){
  const root = document.documentElement;
  const isLight = root.getAttribute('data-theme') === 'light';
  root.setAttribute('data-theme', isLight ? 'dark' : 'light');
  document.getElementById('themeBtn').textContent = isLight ? '🌙' : '☀️';
  localStorage.setItem('trevlix_theme', isLight ? 'dark' : 'light');
}
// Restore theme
(function(){
  const saved = localStorage.getItem('trevlix_theme');
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
  if(!name || !url){ toast('Name und URL erforderlich','warning'); return; }
  const r = await fetch('/api/v1/copy-trading/register', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({name, webhook_url:url, scale})
  });
  const d = await r.json();
  if(d.token){
    toast('✅ Follower registriert. Token: '+d.token.slice(0,12)+'…','success');
    loadFollowers();
  } else { toast('Fehler: '+JSON.stringify(d),'error'); }
}

async function loadFollowers(){
  try {
    const r = await fetch('/api/v1/copy-trading/followers',{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const el = document.getElementById('followersList');
    if(!el) return;
    if(!d.followers || !d.followers.length){ el.innerHTML='<div style="font-size:11px;color:var(--sub)">Keine Follower registriert</div>'; return; }
    el.innerHTML = d.followers.map(f=>`
      <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--muted);font-size:12px">
        <span style="color:var(--txt)">${f.name}</span>
        <span style="color:var(--sub)">×${f.scale} · ${f.signals} Signale</span>
        <span style="color:${f.active?'var(--jade)':'var(--red)'}">${f.active?'aktiv':'inaktiv'}</span>
      </div>`).join('');
  } catch(e){}
}

async function testCopySignal(){
  await fetch('/api/v1/copy-trading/test',{method:'POST',headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
  toast('📡 Test-Signal gesendet','info');
}

// ── Pine Script ──────────────────────────────────────────────────────────
async function downloadPineScript(){
  const sym = (document.getElementById('pineSymbol')?.value || 'BTCUSDT').replace('/','');
  const r = await fetch(`/api/v1/pine-script?symbol=${sym}`,{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
  const txt = await r.text();
  const blob = new Blob([txt], {type:'text/plain'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href=url; a.download=`trevlix_${sym.toLowerCase()}.pine`; a.click();
  URL.revokeObjectURL(url);
  toast('⬇ Pine Script heruntergeladen','success');
}

// ── Gas Tracker ─────────────────────────────────────────────────────────
async function updateGasFees(){
  try {
    const r = await fetch('/api/v1/gas');
    const d = await r.json();
    const el = document.getElementById('gasGwei');
    if(el) el.textContent = d.gwei.toFixed(1) + ' Gwei';
    const sig = document.getElementById('gasSig');
    if(sig) sig.textContent = d.signal===1?'⬆ Hohe Aktivität':d.signal===-1?'⬇ Niedrige Aktivität':'→ Normal';
  } catch(e){}
}
setInterval(updateGasFees, 120000);



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

  // Show admin nav item
  const adminNav = document.querySelector('[onclick*="sec-admin"], [onclick*="admin"]');

  // Update nav visibility
  document.querySelectorAll('.nb.admin-only').forEach(el => {
    el.style.display = role === 'admin' ? '' : 'none';
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

// ── Admin: Load Users ──────────────────────────────────────────────────────────
async function loadUsers() {
  const el = document.getElementById('userList');
  try {
    const r = await fetch('/api/v1/admin/users', {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const users = d.users || d || [];
    if (!users.length) { if(el) el.innerHTML='<div class="empty">Keine Nutzer</div>'; return; }
    if (el) el.innerHTML = users.map(u => `
      <div style="display:flex;align-items:center;justify-content:space-between;
        padding:8px 0;border-bottom:1px solid var(--muted);gap:8px">
        <div>
          <div style="font-size:13px;font-weight:600;color:var(--txt)">${u.username}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">
            ${u.created_at?.slice?.(0,10)||''} · ${u.role}
          </div>
        </div>
        <span class="role-badge ${u.role}">${u.role}</span>
        <div style="font-family:var(--mono);font-size:12px;color:var(--jade)">
          ${(u.balance||0).toFixed(0)} USDT
        </div>
      </div>`).join('');
  } catch(e){ if(el) el.innerHTML='<div class="empty">Fehler beim Laden</div>'; }
}

async function createUser() {
  const username = document.getElementById('newUsername')?.value?.trim();
  const password = document.getElementById('newPassword')?.value;
  const role     = document.getElementById('newRole')?.value || 'user';
  if (!username || !password) { toast('Username und Passwort erforderlich','warning'); return; }
  socket.emit('admin_create_user', {username, password, role});
  document.getElementById('newUsername').value = '';
  document.getElementById('newPassword').value = '';
  setTimeout(loadUsers, 800);
}

async function toggleRegistration(enabled) {
  socket.emit('update_config', {allow_registration: enabled});
  toast(enabled ? '✅ Registrierung aktiviert' : '🔒 Registrierung deaktiviert', 'info');
}


// ── Shared AI Model broadcast ──────────────────────────────────────────────
socket.on('ai_model_updated', data => {
  toast(`🧠 Neues KI-Modell v${data.version} von ${data.trained_by} (WF: ${data.wf_accuracy}%)`, 'success');
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
          <span style="font-family:var(--mono);font-size:10px;color:var(--jade);min-width:30px">v${m.version}</span>
          <span style="font-size:9px;background:rgba(255,255,255,.05);padding:1px 6px;border-radius:4px;color:var(--sub)">${m.type}</span>
          <div style="flex:1">
            <div style="font-size:11px;color:var(--txt)">${m.accuracy}% WF · ${(m.samples||0).toLocaleString('de-DE')} Samples</div>
            <div style="font-size:9px;color:var(--sub)">${m.date} · von ${m.trained_by}</div>
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
            <div style="font-size:12px;font-weight:600;color:var(--txt)">${c.username}</div>
            <div style="font-size:10px;color:var(--sub)">${c.last?.slice(0,16)||''}</div>
          </div>
          <div style="text-align:right">
            <div style="font-family:var(--mono);font-size:12px;color:var(--jade)">${(c.samples||0).toLocaleString('de-DE')} Samples</div>
            <div style="font-size:10px;color:${c.pnl>=0?'var(--jade)':'var(--red)'};font-family:var(--mono)">${c.pnl>=0?'+':''}${(c.pnl||0).toFixed(2)} USDT PnL</div>
          </div>
        </div>`).join('');
    } else if (contribs && !d.contributors?.length) {
      contribs.innerHTML = '<div class="empty"><div class="empty-ico">🏆</div>Noch keine Beiträge</div>';
    }
  } catch(e) { console.warn('loadSharedAIStatus:', e); }
}

async function syncSharedModel() {
  const btn = event.target;
  btn.textContent = '⏳';
  try {
    const r = await fetch('/api/v1/ai/shared/force-sync', {
      method:'POST', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.updated) {
      toast(`✅ Modell v${d.version} synchronisiert (${d.accuracy}% WF)`, 'success');
      loadSharedAIStatus();
    } else {
      toast('Kein neues Modell verfügbar', 'info');
    }
  } catch(e) { toast('Sync-Fehler', 'error'); }
  btn.textContent = '↻ Sync';
}

async function adminTrainGlobal() {
  if (!confirm(QI18n.t('confirm_global_train'))) return;
  try {
    const r = await fetch('/api/v1/ai/shared/train', {
      method:'POST', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.started) {
      toast(`🧠 Training gestartet: ${d.samples_total} Samples (${d.new_samples} neu)`, 'success');
    } else {
      toast(d.error || QI18n.t('toast_error'), 'error');
    }
  } catch(e) { toast('Training-Fehler', 'error'); }
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
    const r = await fetch(`/api/v1/risk/monte-carlo?n=${n}&days=${days}`,
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if (d.error) { toast(d.error,'warning'); return; }
    document.getElementById('mcLoading').style.display = 'none';
    document.getElementById('mcResults').style.display = 'block';
    document.getElementById('mcP50').textContent  = fmt(d.percentile_50)  + ' USDT';
    document.getElementById('mcP5').textContent   = fmt(d.percentile_5)   + ' USDT';
    document.getElementById('mcP95').textContent  = fmt(d.percentile_95)  + ' USDT';
    document.getElementById('mcProbProfit').textContent = d.prob_profit_pct + '%';
    document.getElementById('mcVaR95').textContent = fmt(d.var_95_usdt) + ' USDT';
    document.getElementById('mcBarMin').textContent = fmt(d.percentile_5);
    document.getElementById('mcBarMax').textContent = fmt(d.percentile_95);
    document.getElementById('mcBarExpected').textContent = fmt(d.percentile_50) + ' USDT';
    // Bar: show where median falls between p5 and p95
    const range = d.percentile_95 - d.percentile_5;
    const pos   = range > 0 ? (d.percentile_50 - d.percentile_5) / range * 100 : 50;
    document.getElementById('mcBar').style.width = Math.max(10, Math.min(90, pos)) + '%';
  } catch(e) {
    document.getElementById('mcLoading').style.display = 'none';
    document.getElementById('mcEmpty').style.display = 'block';
    toast('Monte-Carlo-Fehler','error');
  }
}

// ════════════════════════════════════════════════════════════════
// FUNDING RATES
// ════════════════════════════════════════════════════════════════
async function loadFundingRates() {
  const el = document.getElementById('fundingList');
  try {
    const r = await fetch('/api/v1/funding-rates?n=15',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const rates = d.top_rates || [];
    if (!rates.length) { el.innerHTML='<div class="empty">Keine Daten</div>'; return; }
    el.innerHTML = rates.map(f => {
      const pct = parseFloat(f.rate) || 0;
      const col = pct > 0.05 ? 'var(--red)' : pct < -0.05 ? 'var(--jade)' : 'var(--sub)';
      return `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:12px;font-weight:600;color:var(--txt);flex:1">${f.symbol}</span>
        <span style="font-family:var(--mono);font-size:12px;color:${col}">${pct > 0 ? '+' : ''}${pct.toFixed(4)}%</span>
        ${pct > 0.08 ? '<span style="font-size:9px;background:rgba(239,68,68,.1);color:#ef4444;padding:1px 5px;border-radius:4px">HOCH</span>' : ''}
      </div>`;
    }).join('');
  } catch(e) { el.innerHTML='<div class="empty">Fehler</div>'; }
}
async function saveFundingConfig() {
  const enabled = document.getElementById('fundingEnabled')?.checked;
  const maxRate = parseFloat(document.getElementById('fundingMaxRate')?.value || '0.1') / 100;
  await fetch('/api/v1/funding-rates/config', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({enabled, max_rate: maxRate})
  });
  toast('Funding-Filter gespeichert','success');
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
      el.innerHTML = '<div class="empty"><div class="empty-ico">✅</div>Keine Sperren aktiv</div>';
      return;
    }
    el.innerHTML = Object.entries(cds).map(([sym, info]) => `
      <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:13px;font-weight:600;color:#ef4444;flex:1">${sym}</span>
        <span style="font-size:11px;color:var(--sub)">bis ${info.until} (${info.remaining_min} Min.)</span>
        <button onclick="clearCooldown('${sym}')" style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:10px;padding:2px 8px">✕</button>
      </div>`).join('');
  } catch(e) { el.innerHTML = '<div class="empty">Fehler</div>'; }
}
async function clearCooldown(symbol) {
  await fetch('/api/v1/cooldowns/'+symbol, {
    method:'DELETE', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
  loadCooldowns();
  toast(`${symbol} Sperre aufgehoben`, 'info');
}

// ════════════════════════════════════════════════════════════════
// GRID TRADING
// ════════════════════════════════════════════════════════════════
async function createGrid() {
  const symbol = document.getElementById('gridSymbol')?.value?.trim().toUpperCase();
  const lower  = parseFloat(document.getElementById('gridLower')?.value);
  const upper  = parseFloat(document.getElementById('gridUpper')?.value);
  const levels = parseInt(document.getElementById('gridLevels')?.value || 10);
  const invest = parseFloat(document.getElementById('gridInvest')?.value || 100);
  if (!symbol || !lower || !upper || lower >= upper) {
    toast('Symbol, Unter- und Obergrenze erforderlich (untere < obere)', 'warning'); return;
  }
  socket.emit('create_grid', {symbol, lower, upper, levels, invest_per_level: invest});
  setTimeout(loadGrids, 600);
}
async function loadGrids() {
  const el = document.getElementById('gridList');
  if (!el) return;
  try {
    const r = await fetch('/api/v1/grid', {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const grids = d.grids || [];
    if (!grids.length) { el.innerHTML = '<div style="font-size:12px;color:var(--sub)">Keine aktiven Grids</div>'; return; }
    el.innerHTML = grids.map(g => `
      <div style="background:#091017;border-radius:8px;padding:10px;margin-top:8px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="font-weight:700;color:#e8f4ff">${g.symbol}</span>
          <span style="font-size:9px;padding:2px 6px;border-radius:4px;${g.active?'background:rgba(0,255,136,.08);color:var(--jade)':'background:rgba(255,255,255,.05);color:var(--sub)'}">${g.active?'AKTIV':'INAKTIV'}</span>
          <button onclick="deleteGrid('${g.symbol}')" style="margin-left:auto;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:10px;padding:2px 8px">✕</button>
        </div>
        <div style="font-size:11px;color:var(--sub)">${g.levels} Stufen · ${g.lower}–${g.upper} USDT · Schritt: ${g.step?.toFixed(4) || '—'}</div>
        <div style="font-size:11px;color:var(--sub)">Offene Käufe: ${g.open_buys || 0} · Trades: ${g.total_trades || 0} · PnL: <span style="color:${(g.total_pnl||0)>=0?'var(--jade)':'var(--red)'}">${(g.total_pnl||0)>=0?'+':''}${(g.total_pnl||0).toFixed(4)} USDT</span></div>
      </div>`).join('');
  } catch(e) { if(el) el.innerHTML = '<div style="font-size:12px;color:var(--red)">Fehler</div>'; }
}
async function deleteGrid(symbol) {
  if (!confirm(QI18n.t('confirm_delete_grid').replace('{sym}',symbol))) return;
  await fetch('/api/v1/grid/'+symbol, {
    method:'DELETE', headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
  loadGrids(); toast(`Grid ${symbol} gelöscht`, 'info');
}

// ════════════════════════════════════════════════════════════════
// TELEGRAM
// ════════════════════════════════════════════════════════════════
async function saveTelegram() {
  const token   = document.getElementById('tgToken')?.value?.trim();
  const chat_id = document.getElementById('tgChatId')?.value?.trim();
  if (!token || !chat_id) { toast('Token und Chat-ID erforderlich','warning'); return; }
  const r = await fetch('/api/v1/telegram/configure', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({token, chat_id})
  });
  const d = await r.json();
  toast(d.success ? '✅ Telegram verbunden!' : '❌ Verbindung fehlgeschlagen', d.success?'success':'error');
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
  toast(`✅ ${d.whitelist.length} IPs gesetzt`, 'success');
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
  socket.emit('update_config', {
    break_even_enabled: enabled,
    break_even_trigger: trigger,
    break_even_buffer:  buffer,
  });
  toast('✅ Break-Even Einstellungen gespeichert', 'success');
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
    if (!logs.length) { el.innerHTML='<div class="empty">Keine Einträge</div>'; return; }
    const icons = {login:'🔑',trade:'💹',config:'⚙️',admin:'👑','2fa':'🔐',default:'📋'};
    el.innerHTML = logs.map(l => {
      const ico = Object.entries(icons).find(([k])=>l.action?.includes(k))?.[1] || icons.default;
      return `<div style="display:flex;gap:8px;padding:5px 0;border-bottom:1px solid var(--muted);font-size:11px">
        <span style="flex-shrink:0">${ico}</span>
        <div style="flex:1;min-width:0">
          <div style="color:var(--txt);font-weight:600">${l.action}</div>
          <div style="color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${l.detail||''}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;color:var(--sub)">
          <div>${l.username||'system'}</div>
          <div style="font-family:var(--mono)">${(l.created_at||'').slice(11,16)}</div>
        </div>
      </div>`;
    }).join('');
  } catch(e) { el.innerHTML='<div class="empty">Fehler</div>'; }
}

// Load data when switching to risk/admin tabs
const _navBefore = nav;
function nav(id, el) {
  _navBefore(id, el);
  if (id === 'risk') {
    loadFundingRates();
    loadCooldowns();
  }
  if (id === 'admin') {
    loadAuditLog();
    loadGrids();
    loadIpWhitelist();
  }
  if (id === 'settings') {
    loadNewsFilter();
  }
}
// Initial data load
setTimeout(() => { loadFundingRates(); }, 3000);

// ── Keyboard Shortcuts ─────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT') return;
  if(e.ctrlKey||e.metaKey||e.altKey) return;
  switch(e.key.toLowerCase()){
    case ' ':  e.preventDefault(); toggleBot(); break;
    case 'b':  showSection('backtest'); break;
    case 's':  showSection('settings'); break;
    case 'd':  showSection('home'); break;
    case 'a':  showSection('ai'); break;
    case 't':  toggleTheme(); break;
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
    document.getElementById('featureImportanceCard').style.display='';
    const acc = document.getElementById('fi-accuracy');
    if(acc) acc.textContent = `WF: ${d.wf_accuracy}%`;
    const list = document.getElementById('fiList');
    if(!list) return;
    const names = d.feature_names || [];
    const imps  = d.importances   || [];
    const max   = Math.max(...imps, 0.001);
    list.innerHTML = names.map((n,i)=>{
      const v = imps[i]||0;
      const w = Math.round(v/max*100);
      return `<div style="margin-bottom:5px">
        <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px">
          <span style="color:var(--txt)">${n}</span>
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
          <span>${w.name}</span>
          <span style="color:var(--jade)">${w.weight}× &nbsp; WR: ${w.win_rate}%</span>
        </div>`).join('');
    }
  } catch(e){ toast('Feature Importance Fehler','error'); }
}

function showReliabilityDiagram(){
  toast('Kalibrierungs-Diagramm: In Kürze verfügbar','info');
}

// ── Markowitz Optimization ─────────────────────────────────────────────────
async function runMarkowitz(){
  const syms = document.getElementById('markowitzSymbols')?.value?.split(',').map(s=>s.trim()).filter(Boolean);
  if(!syms||syms.length<2){ toast('Mindestens 2 Symbole','warning'); return; }
  const el = document.getElementById('markowitzResults');
  if(el) el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--sub)">⏳ Berechne Markowitz...</div>';
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
          <span style="font-size:12px;flex:1">${s}</span>
          <div style="flex:2;height:6px;background:var(--bg3);border-radius:3px">
            <div style="width:${d.weights[i]*100}%;height:100%;border-radius:3px;background:var(--jade)"></div>
          </div>
          <span style="font-family:var(--mono);font-size:12px;color:var(--jade);min-width:45px;text-align:right">${d.allocations[s]}%</span>
        </div>`).join('')}`;
  } catch(e){ toast('Markowitz Fehler: '+e.message,'error'); }
}

// ── Backtest Compare ────────────────────────────────────────────────────────
async function runCompareBacktest(){
  const syms = document.getElementById('compareSymbols')?.value?.split(',').map(s=>s.trim()).filter(Boolean);
  const tf   = document.getElementById('compareTf')?.value || '1h';
  const can  = parseInt(document.getElementById('compareCandles')?.value) || 500;
  const el   = document.getElementById('compareResults');
  if(!syms||syms.length<1){ toast('Mindestens 1 Symbol','warning'); return; }
  if(el) el.innerHTML='<div style="text-align:center;padding:20px;color:var(--sub)">⏳ Backtest läuft...</div>';
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
  } catch(e){ toast('Vergleich Fehler','error'); }
}

// ── Backtest History ────────────────────────────────────────────────────────
async function loadBtHistory(){
  const el = document.getElementById('btHistoryList');
  try {
    const r = await fetch('/api/backtest/history',{headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    if(!d.length){ if(el) el.innerHTML='<div class="empty"><div class="empty-ico">📊</div>Keine Backtests</div>'; return; }
    if(el) el.innerHTML = d.slice(0,10).map(b=>`
      <div style="padding:8px 0;border-bottom:1px solid var(--muted);display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center">
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--txt)">${b.symbol} · ${b.timeframe}</div>
          <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${b.total_trades} Trades · ${b.candles} Kerzen · ${b.run_date?.slice(0,10)||''}</div>
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
  } catch(e){ if(el) el.innerHTML='<div class="empty">Laden fehlgeschlagen</div>'; }
}

// ── Manual SL/TP Adjustment ─────────────────────────────────────────────────
async function adjustSL(symbol, entryPrice){
  const pct = prompt(`SL für ${symbol} (% vom Entry ${entryPrice.toFixed(4)})\nz.B. 2.5 für -2.5%:`);
  if(!pct) return;
  const r = await fetch('/api/v1/positions/'+encodeURIComponent(symbol)+'/sl',{
    method:'PATCH',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+(_jwtToken||'')},
    body: JSON.stringify({sl_pct: parseFloat(pct)})
  });
  const d = await r.json();
  if(d.new_sl) toast(`✅ SL ${symbol}: ${d.new_sl.toFixed(4)}`,'success');
  else toast(d.error||'Fehler','error');
}

// ── Web Push Notifications ──────────────────────────────────────────────────
let _pushSub = null;
async function requestPushPermission(){
  if(!('Notification' in window)){ toast(QI18n.t('toast_push_unsupported'),'warning'); return; }
  const perm = await Notification.requestPermission();
  if(perm === 'granted'){
    toast('🔔 Browser-Benachrichtigungen aktiviert','success');
    document.getElementById('pushBtn').style.color='var(--jade)';
    document.getElementById('pushBtn').style.borderColor='var(--jade)';
    localStorage.setItem('trevlix_push','1');
    // Register service worker
    if('serviceWorker' in navigator){
      try {
        await navigator.serviceWorker.register('/sw.js');
      } catch(e){}
    }
  } else {
    toast('Benachrichtigungen verweigert','warning');
  }
}

// Auto-push on trade events via socket
function _checkPush(data){
  if(!('Notification' in window)||Notification.permission!=='granted') return;
  if(localStorage.getItem('trevlix_push')!=='1') return;
  // New trade
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

// ── Load Feature Importance on AI tab switch ─────────────────────────────────
function onTabSwitch(section){
  if(section === 'ai'){
    setTimeout(loadFeatureImportance, 500);
  }
  if(section === 'backtest'){
    setTimeout(loadBtHistory, 300);
  }
}

// Restore push pref
if(localStorage.getItem('trevlix_push')==='1' && 'Notification' in window && Notification.permission==='granted'){
  document.getElementById('pushBtn').style.color='var(--jade)';
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
  const exs = data.exchanges || {};
  const active = Object.values(exs).filter(e => e.running).length;

  // Gesamt-Header
  const pv = data.combined_pv || data.total_pv || 0;
  const pnl = data.combined_pnl || data.total_pnl || 0;
  const pvEl = document.getElementById('mex-total-pv');
  if (pvEl) pvEl.innerHTML = fmt(pv) + ' <span style="font-size:16px;opacity:.4">USDT</span>';
  const pnlEl = document.getElementById('mex-total-pnl');
  if (pnlEl) {
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl) + ' USDT Gesamt-PnL';
    pnlEl.className = 'pill ' + (pnl >= 0 ? 'up' : 'dn');
  }
  const acEl = document.getElementById('mex-active-count');
  if (acEl) acEl.textContent = active + ' Exchange' + (active !== 1 ? 's' : '') + ' aktiv';

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
    const positions = ex.positions || [];

    const statusDot = running
      ? '<span style="width:8px;height:8px;border-radius:50%;background:#00ff88;display:inline-block;box-shadow:0 0 6px #00ff88"></span>'
      : (enabled
          ? '<span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;display:inline-block"></span>'
          : '<span style="width:8px;height:8px;border-radius:50%;background:#374151;display:inline-block"></span>');

    const posHtml = positions.length ? positions.map(p => `
      <div style="display:flex;justify-content:space-between;padding:4px 0;border-top:1px solid var(--muted);font-size:11px">
        <span style="color:var(--txt);font-weight:600">${p.symbol}</span>
        <span style="font-family:var(--mono);color:var(--sub)">@ ${p.entry}</span>
        <span style="font-family:var(--mono);color:${p.pnl>=0?'var(--jade)':'var(--red)'}">${p.pnl>=0?'+':''}${p.pnl?.toFixed(2)} USDT</span>
        <button onclick="mexClosePos('${id}','${p.symbol}')" style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);border-radius:4px;color:#ef4444;cursor:pointer;font-size:9px;padding:2px 6px">✕</button>
      </div>`).join('') : '';

    return `
    <div class="card" style="border-color:${running?'rgba(0,255,136,.15)':enabled?'rgba(245,158,11,.1)':'rgba(255,255,255,.05)'}">
      <div class="card-hd" style="padding-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:20px">${MEX_LOGOS[id]}</span>
          <div>
            <div style="font-weight:800;font-size:14px;color:#e8f4ff">${label}</div>
            <div style="font-size:10px;color:var(--sub);font-family:var(--mono)">${ex.markets_count||0} Märkte · ${ex.last_scan||'—'}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          ${statusDot}
          <span style="font-size:10px;font-family:var(--mono);color:${running?'var(--jade)':enabled?'#f59e0b':'var(--muted)'}">${running?'AKTIV':enabled?'KONFIGURIERT':'INAKTIV'}</span>
        </div>
      </div>

      ${err ? `<div style="padding:6px 16px;background:rgba(239,68,68,.08);border-left:3px solid #ef4444;font-size:11px;color:#ef4444;margin-bottom:8px">${err}</div>` : ''}

      <div class="card-body" style="padding-top:0">
        <div class="sg" style="grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
          <div class="sc">
            <div class="sv" style="font-size:14px;color:${ret>=0?'var(--jade)':'var(--red)'}">${ret>=0?'+':''}${ret?.toFixed(2)}%</div>
            <div class="sl">Return</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px;color:${pnl>=0?'var(--jade)':'var(--red)'}">${pnl>=0?'+':''}${pnl?.toFixed(2)}</div>
            <div class="sl">PnL (USDT)</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px">${wr?.toFixed(1)}%</div>
            <div class="sl">Win-Rate</div>
          </div>
          <div class="sc">
            <div class="sv" style="font-size:14px">${trades}</div>
            <div class="sl">Trades</div>
          </div>
        </div>

        ${positions.length ? `
        <div style="font-size:9px;font-family:var(--mono);color:var(--sub);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">${open} OFFENE POSITIONEN</div>
        ${posHtml}` : ''}

        <div style="display:flex;gap:8px;margin-top:12px">
          ${!enabled
            ? `<button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${id}')">🔑 API-Keys einrichten</button>`
            : running
              ? `<button class="btn btn-red"  style="flex:1;padding:8px;font-size:12px" onclick="mexStop('${id}')">⏹ Stoppen</button>
                 <button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${id}')">🔑 Keys</button>`
              : `<button class="btn btn-jade" style="flex:1;padding:8px;font-size:12px" onclick="mexStart('${id}')">▶ Starten</button>
                 <button class="btn btn-info" style="flex:1;padding:8px;font-size:12px" onclick="mexSetupKeys('${id}')">🔑 Keys</button>`
          }
        </div>
      </div>
    </div>`;
  }).join('');
}

function mexStart(name)  { socket.emit('start_exchange',  {exchange: name}); }
function mexStop(name)   { socket.emit('stop_exchange',   {exchange: name}); }

function mexSetupKeys(name) {
  document.getElementById('mex-key-exchange').value = name;
  mexOnExchangeSelect(name);
  // Scroll to key form
  document.querySelector('#mex-key-exchange')?.scrollIntoView({behavior:'smooth', block:'center'});
}

function mexOnExchangeSelect(name) {
  const needsPP = ['okx','kucoin'].includes(name);
  document.getElementById('mex-passphrase-wrap').style.display = needsPP ? '' : 'none';
}

function mexSaveKeys() {
  const exchange   = document.getElementById('mex-key-exchange').value;
  const api_key    = document.getElementById('mex-key-apikey').value.trim();
  const secret     = document.getElementById('mex-key-secret').value.trim();
  const passphrase = document.getElementById('mex-key-passphrase')?.value?.trim() || '';
  if (!api_key || !secret) { toast('API-Key und Secret erforderlich', 'warning'); return; }
  socket.emit('save_exchange_keys', {exchange, api_key, secret, passphrase});
  document.getElementById('mex-key-apikey').value = '';
  document.getElementById('mex-key-secret').value = '';
}

function mexClosePos(exchange, symbol) {
  if (!confirm(QI18n.t('confirm_close_exchange_pos').replace('{sym}',symbol).replace('{exc}',exchange.toUpperCase()))) return;
  socket.emit('close_exchange_position', {exchange, symbol});
}

async function mexLoadTrades() {
  const el = document.getElementById('mex-trades-list');
  try {
    const r = await fetch('/api/v1/exchanges/combined/trades',
      {headers:{'Authorization':'Bearer '+(_jwtToken||'')}});
    const d = await r.json();
    const trades = d.trades || [];
    if (!trades.length) {
      el.innerHTML = '<div class="empty"><div class="empty-ico">📋</div>Keine Trades</div>';
      return;
    }
    el.innerHTML = trades.slice(0,50).map(t => {
      const won = (t.pnl||0) >= 0;
      return `
      <div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--muted)">
        <span style="font-size:11px;background:rgba(255,255,255,.05);border-radius:4px;padding:2px 6px;color:var(--sub);font-family:var(--mono)">${(t.exchange||'').toUpperCase()}</span>
        <div style="flex:1">
          <div style="font-size:12px;font-weight:600;color:var(--txt)">${t.symbol}</div>
          <div style="font-size:10px;color:var(--sub)">${t.reason||''} · ${(t.closed||'').slice(0,16)}</div>
        </div>
        <div style="font-family:var(--mono);font-size:13px;color:${won?'var(--jade)':'var(--red)'}">
          ${won?'+':''}${(t.pnl||0).toFixed(2)} USDT
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty">Fehler beim Laden</div>';
  }
}

// Beim Wechsel auf Exchanges-Tab: Trades laden
const _origNav = nav;
function nav(id, el) {
  _origNav(id, el);
  if (id === 'exchanges') mexLoadTrades();
}

// Beim Start: Exchange-Status laden
fetch('/api/v1/exchanges', {headers:{'Authorization':'Bearer '+(_jwtToken||'')}})
  .then(r => r.json()).then(mexUpdate).catch(()=>{});

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
  document.getElementById('taxYear').value=new Date().getFullYear();
  QI18n.init('langSwitcher');
  loadFollowers();
  updateGasFees();
  const sLang=document.getElementById('sLang');if(sLang)sLang.value=QI18n.lang;
  if(!localStorage.getItem('trevlix_wiz')) setTimeout(showWizard,800);
});
