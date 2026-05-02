// ╔══════════════════════════════════════════════════════════════╗
// ║  TREVLIX – Dashboard misc helpers                            ║
// ║                                                              ║
// ║  Self-contained dashboard widgets that do not share state    ║
// ║  with the main dashboard.js: Theme Toggle, Pine-Script       ║
// ║  download, Copy-Trading register/list/test. Each function    ║
// ║  uses only globals already present in dashboard_utils.js     ║
// ║  (esc, _storage, toast) plus the page-level _jwtToken /      ║
// ║  QI18n that dashboard.js itself initialises – we are loaded  ║
// ║  AFTER dashboard.js, so those are in scope.                  ║
// ║                                                              ║
// ║  Loaded by templates/dashboard.html as a separate <script>.  ║
// ╚══════════════════════════════════════════════════════════════╝

// ── Theme Toggle ─────────────────────────────────────────────────────────
function toggleTheme(){
  const root = document.documentElement;
  const isLight = root.getAttribute('data-theme') === 'light';
  root.setAttribute('data-theme', isLight ? 'dark' : 'light');
  const themeBtn = document.getElementById('themeBtn');
  if(themeBtn) themeBtn.textContent = isLight ? '🌙' : '☀️';
  _storage.set('trevlix_theme', isLight ? 'dark' : 'light');
}
// Restore theme on load
(function(){
  const saved = _storage.get('trevlix_theme');
  if(saved === 'light'){
    document.documentElement.setAttribute('data-theme','light');
    setTimeout(()=>{const b=document.getElementById('themeBtn');if(b)b.textContent='☀️';},100);
  }
})();

// ── Pine Script download ─────────────────────────────────────────────────
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

// ── Copy-Trading ─────────────────────────────────────────────────────────
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
