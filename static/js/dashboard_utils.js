// ╔══════════════════════════════════════════════════════════════╗
// ║  TREVLIX – Dashboard Utility Helpers                         ║
// ║  Pure helpers shared across the dashboard surface.           ║
// ║                                                              ║
// ║  Loaded before static/js/dashboard.js so all definitions are ║
// ║  in scope. No top-level `const`/`let` (those are            ║
// ║  script-scoped and would not be visible across <script> tags ║
// ║  – use `var` or window.* assignments only).                  ║
// ╚══════════════════════════════════════════════════════════════╝

// ── HTML-Escaping für sichere innerHTML-Nutzung ──────────────────────
function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
// JS-safe escaping for use in onclick="fn('${escJS(val)}')" attributes
function escJS(s){if(!s)return'';return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/</g,'\\x3c').replace(/>/g,'\\x3e');}

// ── Safe localStorage wrapper (handles private browsing) ─────────────
var _storage = {
  get(k){try{return localStorage.getItem(k);}catch(e){return null;}},
  set(k,v){try{localStorage.setItem(k,v);}catch(e){}},
  del(k){try{localStorage.removeItem(k);}catch(e){}}
};

// ── Format ───────────────────────────────────────────────────────────
var fmt=(n,d=2)=>Number(n||0).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});
var fmtPct=n=>(n>=0?'+':'')+fmt(n)+'%';
var fmtS=(n,d=2)=>(n>=0?'+':'')+fmt(n,d);
var clr=n=>n>=0?'var(--green)':'var(--red)';

// ── Toast ────────────────────────────────────────────────────────────
function toast(msg, type='info'){
  const c=document.getElementById('toasts');
  if(!c) return;
  /* Max 5 Toasts gleichzeitig anzeigen */
  while(c.children.length >= 5){ c.removeChild(c.firstChild); }
  const t=document.createElement('div');
  t.className='toast '+type; t.textContent=msg;
  t.setAttribute('role','alert');
  c.appendChild(t); setTimeout(()=>t.remove(),3700);
}
