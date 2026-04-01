"""[#9] TREVLIX – Auth Blueprint (Login, Register, Logout).

Enthält alle Authentifizierungs-Routes als Flask Blueprint.
Wird von server.py über ``register_auth_blueprint()`` eingebunden.

Verwendung:
    from routes.auth import create_auth_blueprint
    bp = create_auth_blueprint(db, CONFIG, limiter, db_audit_fn, check_rate_fn, record_fn, audit_fn)
    app.register_blueprint(bp)
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from flask import Blueprint, make_response, redirect, request, send_file, session

log = logging.getLogger("trevlix.auth")

# Auth-Seite HTML-Template (Glassmorphism-Design mit i18n)
_AUTH_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TREVLIX %(page_title)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700;900&display=swap"
      rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
@keyframes gradMove{
  0%%{background-position:0%% 50%%}
  25%%{background-position:50%% 100%%}
  50%%{background-position:100%% 50%%}
  75%%{background-position:50%% 0%%}
  100%%{background-position:0%% 50%%}
}
@keyframes fadeUp{from{opacity:0;transform:translateY(24px) scale(.97)}
  to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes pulseGlow{
  0%%,100%%{opacity:.4}50%%{opacity:.7}
}
@keyframes shimmer{
  0%%{background-position:-200%% 0}100%%{background-position:200%% 0}
}
html{height:100%%}
body{font-family:'Barlow',sans-serif;color:#ccd6f6;min-height:100vh;
  display:flex;align-items:center;justify-content:center;flex-direction:column;
  background:#060912;overflow-x:hidden;position:relative}
body::before{content:'';position:fixed;inset:0;z-index:0;
  background:linear-gradient(135deg,#060912 0%%,#0a1628 20%%,#0d1a2e 40%%,#081a14 60%%,#0d0f20 80%%,#060912 100%%);
  background-size:400%% 400%%;animation:gradMove 25s ease infinite}
body::after{content:'';position:fixed;inset:0;z-index:0;
  background:radial-gradient(ellipse 700px 500px at 25%% 15%%,rgba(0,255,136,.05),transparent),
             radial-gradient(ellipse 600px 400px at 75%% 85%%,rgba(0,212,255,.05),transparent),
             radial-gradient(ellipse 400px 300px at 50%% 50%%,rgba(0,180,255,.02),transparent)}
.orb{position:fixed;border-radius:50%%;filter:blur(80px);z-index:0;
  animation:pulseGlow 8s ease-in-out infinite;pointer-events:none}
.orb-1{width:300px;height:300px;top:-80px;left:-60px;
  background:radial-gradient(circle,rgba(0,255,136,.12),transparent 70%%)}
.orb-2{width:250px;height:250px;bottom:-60px;right:-40px;
  background:radial-gradient(circle,rgba(0,212,255,.1),transparent 70%%);
  animation-delay:4s}
.orb-3{width:180px;height:180px;top:40%%;right:15%%;
  background:radial-gradient(circle,rgba(0,255,200,.06),transparent 70%%);
  animation-delay:2s}
.box{position:relative;z-index:1;
  background:rgba(10,15,30,.55);
  backdrop-filter:blur(32px) saturate(1.4);-webkit-backdrop-filter:blur(32px) saturate(1.4);
  border:1px solid rgba(255,255,255,.07);border-radius:28px;
  padding:48px 44px 36px;width:100%%;max-width:420px;margin:20px;
  box-shadow:0 8px 32px rgba(0,0,0,.5),0 0 80px rgba(0,212,255,.04),
    inset 0 1px 0 rgba(255,255,255,.06);
  animation:fadeUp .6s cubic-bezier(.22,1,.36,1)}
.box::before{content:'';position:absolute;inset:-1px;border-radius:28px;
  padding:1px;background:linear-gradient(160deg,rgba(0,212,255,.15),transparent 40%%,
    transparent 60%%,rgba(0,255,136,.1));
  -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.logo{text-align:center;margin-bottom:32px}
.logo-icon{font-size:52px;margin-bottom:10px;
  filter:drop-shadow(0 0 18px rgba(0,212,255,.4)) drop-shadow(0 0 40px rgba(0,255,136,.15));
  animation:pulseGlow 4s ease-in-out infinite}
.logo-name{font-size:32px;font-weight:900;letter-spacing:-1px;
  background:linear-gradient(135deg,#e0e8ff 0%%,#ccd6f6 50%%,#a0b4d0 100%%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text}
.logo-name span{background:linear-gradient(135deg,#00d4ff,#00ff88);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text}
.logo-sub{font-size:11px;color:#3a4a6a;letter-spacing:3px;
  text-transform:uppercase;margin-top:6px;font-weight:500}
.divider{height:1px;margin:0 0 24px;
  background:linear-gradient(90deg,transparent,rgba(0,212,255,.15),transparent)}
label{display:block;font-size:11px;font-weight:700;color:#5a7a9a;letter-spacing:.8px;
  text-transform:uppercase;margin-bottom:6px}
input[type="text"],input[type="password"]{width:100%%;
  background:rgba(12,18,35,.8);border:1px solid rgba(255,255,255,.06);
  border-radius:14px;padding:15px 18px;color:#ccd6f6;font-size:14px;
  font-family:'Barlow',sans-serif;outline:none;margin-bottom:18px;
  transition:border-color .3s,box-shadow .3s,background .3s}
input[type="text"]:focus,input[type="password"]:focus{
  border-color:rgba(0,212,255,.45);background:rgba(12,18,35,.95);
  box-shadow:0 0 0 3px rgba(0,212,255,.08),0 0 24px rgba(0,212,255,.06),
    0 0 60px rgba(0,212,255,.03)}
input[type="text"]::placeholder,input[type="password"]::placeholder{
  color:#3a4a6a;font-weight:400}
input[type="hidden"]{display:none;margin:0;padding:0}
.msg{font-size:12px;margin-bottom:16px;padding:11px 14px;border-radius:12px;
  display:%(msg_display)s;text-align:center;font-weight:500;
  backdrop-filter:blur(8px)}
.msg-err{background:rgba(255,61,113,.08);color:#ff5a85;
  border:1px solid rgba(255,61,113,.18)}
.msg-ok{background:rgba(0,255,136,.06);color:#00ff88;
  border:1px solid rgba(0,255,136,.18)}
button{width:100%%;padding:16px;border-radius:14px;
  background:linear-gradient(135deg,#00ff88 0%%,#00d4ff 100%%);
  color:#060912;font-size:15px;font-weight:800;border:none;cursor:pointer;
  font-family:'Barlow',sans-serif;letter-spacing:.4px;
  transition:transform .18s,box-shadow .3s;position:relative;overflow:hidden;
  box-shadow:0 4px 24px rgba(0,212,255,.2),0 0 60px rgba(0,255,136,.08)}
button::after{content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);
  background-size:200%% 100%%;animation:shimmer 3s ease-in-out infinite}
button:hover{transform:translateY(-2px);
  box-shadow:0 8px 32px rgba(0,212,255,.35),0 0 80px rgba(0,255,136,.12)}
button:active{transform:translateY(0)}
.ver{text-align:center;margin-top:24px;font-size:10px;color:#2a3a5a;
  letter-spacing:.5px;font-weight:500}
.alt-link{text-align:center;margin-top:16px;font-size:13px;color:#5a7090;font-weight:500}
.alt-link a{color:#00d4ff;text-decoration:none;transition:color .2s;font-weight:600}
.alt-link a:hover{color:#00ff88;text-shadow:0 0 12px rgba(0,255,136,.2)}
.pw-wrap{position:relative}
.pw-wrap input{padding-right:48px}
.pw-toggle{position:absolute;right:16px;top:15px;cursor:pointer;
  color:#5a7090;font-size:16px;line-height:1;user-select:none;
  transition:color .2s,transform .15s;background:none;border:none;width:auto;padding:0;
  box-shadow:none}
.pw-toggle:hover{color:#00d4ff;transform:scale(1.15)}
.lang-bar{display:flex;justify-content:center;gap:6px;margin-top:18px}
.lang-btn{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
  border-radius:8px;padding:4px 10px;font-size:11px;cursor:pointer;
  color:#4a5a7a;font-family:'Barlow',sans-serif;font-weight:600;
  transition:all .25s;width:auto;box-shadow:none;letter-spacing:.3px}
.lang-btn:hover{color:#00d4ff;border-color:rgba(0,212,255,.25);
  background:rgba(0,212,255,.06)}
.lang-btn.active{color:#00d4ff;border-color:rgba(0,212,255,.35);
  background:rgba(0,212,255,.1);box-shadow:0 0 12px rgba(0,212,255,.08)}
@media(max-width:480px){.box{margin:12px;padding:36px 28px 28px;border-radius:22px}
  .logo-name{font-size:28px}.logo-icon{font-size:44px}}
</style></head><body>
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>
<div class="orb orb-3"></div>
<div class="box">
  <div class="logo">
    <div class="logo-icon">&#9889;</div>
    <div class="logo-name">TREV<span>LIX</span></div>
    <div class="logo-sub" data-i18n="subtitle">Algorithmic Trading Bot &middot; v1.5.0</div>
  </div>
  <div class="divider"></div>
  %(body)s
  <div class="ver" data-i18n="footer">TREVLIX &middot; Open-Source Trading Bot</div>
  <div class="lang-bar">
    <button class="lang-btn" data-lang="de" title="Deutsch">DE</button>
    <button class="lang-btn active" data-lang="en" title="English">EN</button>
    <button class="lang-btn" data-lang="es" title="Espa&#241;ol">ES</button>
    <button class="lang-btn" data-lang="ru" title="&#1056;&#1091;&#1089;&#1089;&#1082;&#1080;&#1081;">RU</button>
    <button class="lang-btn" data-lang="pt" title="Portugu&#234;s">PT</button>
  </div>
</div>
<script>
(function(){
  var T={
    de:{subtitle:"Algorithmischer Trading Bot &middot; v1.5.0",footer:"TREVLIX &middot; Open-Source Trading Bot",
        username:"Benutzername",password:"Passwort",password_confirm:"Passwort best\\u00e4tigen",
        login_btn:"Anmelden &rarr;",register_btn:"Konto erstellen &rarr;",
        no_account:"Noch kein Konto?",register_link:"Registrieren",
        back_login:"&larr; Zur Anmeldung"},
    en:{subtitle:"Algorithmic Trading Bot &middot; v1.5.0",footer:"TREVLIX &middot; Open-Source Trading Bot",
        username:"Username",password:"Password",password_confirm:"Confirm Password",
        login_btn:"Sign In &rarr;",register_btn:"Create Account &rarr;",
        no_account:"No account yet?",register_link:"Register",
        back_login:"&larr; Back to Login"},
    es:{subtitle:"Bot de Trading Algor\\u00edtmico &middot; v1.5.0",footer:"TREVLIX &middot; Bot de Trading Open-Source",
        username:"Usuario",password:"Contrase\\u00f1a",password_confirm:"Confirmar Contrase\\u00f1a",
        login_btn:"Iniciar Sesi\\u00f3n &rarr;",register_btn:"Crear Cuenta &rarr;",
        no_account:"\\u00bfNo tienes cuenta?",register_link:"Registrarse",
        back_login:"&larr; Volver al Login"},
    ru:{subtitle:"\\u0410\\u043b\\u0433\\u043e\\u0440\\u0438\\u0442\\u043c\\u0438\\u0447\\u0435\\u0441\\u043a\\u0438\\u0439 \\u0422\\u0440\\u0435\\u0439\\u0434\\u0438\\u043d\\u0433 \\u0411\\u043e\\u0442 &middot; v1.5.0",
        footer:"TREVLIX &middot; \\u041e\\u043f\\u0435\\u043d-\\u0441\\u043e\\u0443\\u0440\\u0441 \\u0422\\u0440\\u0435\\u0439\\u0434\\u0438\\u043d\\u0433 \\u0411\\u043e\\u0442",
        username:"\\u0418\\u043c\\u044f \\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044f",
        password:"\\u041f\\u0430\\u0440\\u043e\\u043b\\u044c",
        password_confirm:"\\u041f\\u043e\\u0434\\u0442\\u0432\\u0435\\u0440\\u0434\\u0438\\u0442\\u0435 \\u043f\\u0430\\u0440\\u043e\\u043b\\u044c",
        login_btn:"\\u0412\\u043e\\u0439\\u0442\\u0438 &rarr;",register_btn:"\\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c &rarr;",
        no_account:"\\u041d\\u0435\\u0442 \\u0430\\u043a\\u043a\\u0430\\u0443\\u043d\\u0442\\u0430?",register_link:"\\u0420\\u0435\\u0433\\u0438\\u0441\\u0442\\u0440\\u0430\\u0446\\u0438\\u044f",
        back_login:"&larr; \\u041a \\u0432\\u0445\\u043e\\u0434\\u0443"},
    pt:{subtitle:"Bot de Trading Algor\\u00edtmico &middot; v1.5.0",footer:"TREVLIX &middot; Bot de Trading Open-Source",
        username:"Usu\\u00e1rio",password:"Senha",password_confirm:"Confirmar Senha",
        login_btn:"Entrar &rarr;",register_btn:"Criar Conta &rarr;",
        no_account:"N\\u00e3o tem conta?",register_link:"Registrar",
        back_login:"&larr; Voltar ao Login"}
  };
  function setLang(l){
    if(!T[l])return;
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      var k=el.getAttribute('data-i18n');if(T[l][k])el.innerHTML=T[l][k];
    });
    document.querySelectorAll('.lang-btn').forEach(function(b){
      b.classList.toggle('active',b.getAttribute('data-lang')===l);
    });
    try{localStorage.setItem('trevlix_lang',l);}catch(e){}
  }
  document.querySelectorAll('.lang-btn').forEach(function(b){
    b.addEventListener('click',function(){setLang(this.getAttribute('data-lang'));});
  });
  var saved;try{saved=localStorage.getItem('trevlix_lang');}catch(e){}
  if(saved&&T[saved])setLang(saved);
  document.querySelectorAll('input[type="password"]').forEach(function(inp){
    var wrap=document.createElement('div');wrap.className='pw-wrap';
    inp.parentNode.insertBefore(wrap,inp);wrap.appendChild(inp);
    var btn=document.createElement('button');btn.type='button';btn.className='pw-toggle';
    btn.innerHTML='&#128065;';btn.setAttribute('aria-label','Toggle password visibility');
    wrap.appendChild(btn);
    btn.addEventListener('click',function(){
      var t=inp.type==='password'?'text':'password';inp.type=t;
      btn.style.color=t==='text'?'#00d4ff':'';
    });
  });
})();
</script>
</body></html>"""


# Admin-Login Template (Gold/Amber Akzent statt Cyan um Admin-Bereich zu kennzeichnen)
_ADMIN_AUTH_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TREVLIX %(page_title)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700;900&display=swap"
      rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
@keyframes gradMove{
  0%%{background-position:0%% 50%%}
  25%%{background-position:50%% 100%%}
  50%%{background-position:100%% 50%%}
  75%%{background-position:50%% 0%%}
  100%%{background-position:0%% 50%%}
}
@keyframes fadeUp{from{opacity:0;transform:translateY(24px) scale(.97)}
  to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes pulseGlow{
  0%%,100%%{opacity:.4}50%%{opacity:.7}
}
@keyframes shimmer{
  0%%{background-position:-200%% 0}100%%{background-position:200%% 0}
}
html{height:100%%}
body{font-family:'Barlow',sans-serif;color:#ccd6f6;min-height:100vh;
  display:flex;align-items:center;justify-content:center;flex-direction:column;
  background:#0a0608;overflow-x:hidden;position:relative}
body::before{content:'';position:fixed;inset:0;z-index:0;
  background:linear-gradient(135deg,#0a0608 0%%,#1a0f10 20%%,#12081a 40%%,#0f0a06 60%%,#0a0814 80%%,#0a0608 100%%);
  background-size:400%% 400%%;animation:gradMove 25s ease infinite}
body::after{content:'';position:fixed;inset:0;z-index:0;
  background:radial-gradient(ellipse 700px 500px at 25%% 15%%,rgba(0,212,255,.05),transparent),
             radial-gradient(ellipse 600px 400px at 75%% 85%%,rgba(255,140,0,.03),transparent),
             radial-gradient(ellipse 400px 300px at 50%% 50%%,rgba(255,200,50,.02),transparent)}
.orb{position:fixed;border-radius:50%%;filter:blur(80px);z-index:0;
  animation:pulseGlow 8s ease-in-out infinite;pointer-events:none}
.orb-1{width:280px;height:280px;top:-70px;left:-50px;
  background:radial-gradient(circle,rgba(0,212,255,.1),transparent 70%%)}
.orb-2{width:220px;height:220px;bottom:-50px;right:-30px;
  background:radial-gradient(circle,rgba(255,140,0,.08),transparent 70%%);
  animation-delay:4s}
.box{position:relative;z-index:1;
  background:rgba(18,12,22,.6);
  backdrop-filter:blur(32px) saturate(1.4);-webkit-backdrop-filter:blur(32px) saturate(1.4);
  border:1px solid rgba(0,212,255,.08);border-radius:28px;
  padding:48px 44px 36px;width:100%%;max-width:420px;margin:20px;
  box-shadow:0 8px 32px rgba(0,0,0,.5),0 0 80px rgba(0,212,255,.04),
    inset 0 1px 0 rgba(255,255,255,.04);
  animation:fadeUp .6s cubic-bezier(.22,1,.36,1)}
.box::before{content:'';position:absolute;inset:-1px;border-radius:28px;
  padding:1px;background:linear-gradient(160deg,rgba(0,212,255,.15),transparent 40%%,
    transparent 60%%,rgba(0,255,136,.12));
  -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.logo{text-align:center;margin-bottom:28px}
.logo-icon{font-size:52px;margin-bottom:10px;
  filter:drop-shadow(0 0 18px rgba(0,212,255,.4)) drop-shadow(0 0 40px rgba(0,255,136,.15));
  animation:pulseGlow 4s ease-in-out infinite}
.logo-name{font-size:32px;font-weight:900;letter-spacing:-1px;
  background:linear-gradient(135deg,#e0e8ff 0%%,#ccd6f6 50%%,#a0b4d0 100%%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text}
.logo-name span{background:linear-gradient(135deg,#00d4ff,#00ff88);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text}
.logo-sub{font-size:11px;color:#5a4a3a;letter-spacing:3px;
  text-transform:uppercase;margin-top:6px;font-weight:500}
.admin-badge{display:inline-block;margin-top:12px;
  background:rgba(0,212,255,.1);color:#00d4ff;
  font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
  padding:5px 16px;border-radius:8px;border:1px solid rgba(0,212,255,.25);
  box-shadow:0 0 20px rgba(0,212,255,.08)}
.divider{height:1px;margin:0 0 24px;
  background:linear-gradient(90deg,transparent,rgba(0,212,255,.15),transparent)}
label{display:block;font-size:11px;font-weight:700;color:#907050;letter-spacing:.8px;
  text-transform:uppercase;margin-bottom:6px}
input[type="text"],input[type="password"]{width:100%%;
  background:rgba(12,18,35,.8);border:1px solid rgba(0,212,255,.08);
  border-radius:14px;padding:15px 18px;color:#ccd6f6;font-size:14px;
  font-family:'Barlow',sans-serif;outline:none;margin-bottom:18px;
  transition:border-color .3s,box-shadow .3s,background .3s}
input[type="text"]:focus,input[type="password"]:focus{
  border-color:rgba(0,212,255,.45);background:rgba(12,18,35,.95);
  box-shadow:0 0 0 3px rgba(0,212,255,.08),0 0 24px rgba(255,180,0,.05)}
input[type="text"]::placeholder,input[type="password"]::placeholder{
  color:#4a3a2a;font-weight:400}
input[type="hidden"]{display:none;margin:0;padding:0}
.msg{font-size:12px;margin-bottom:16px;padding:11px 14px;border-radius:12px;
  display:%(msg_display)s;text-align:center;font-weight:500;
  backdrop-filter:blur(8px)}
.msg-err{background:rgba(255,61,113,.08);color:#ff5a85;
  border:1px solid rgba(255,61,113,.18)}
button{width:100%%;padding:16px;border-radius:14px;
  background:linear-gradient(135deg,#00d4ff 0%%,#00a8d6 100%%);
  color:#0a0608;font-size:15px;font-weight:800;border:none;cursor:pointer;
  font-family:'Barlow',sans-serif;letter-spacing:.4px;
  transition:transform .18s,box-shadow .3s;position:relative;overflow:hidden;
  box-shadow:0 4px 24px rgba(255,180,0,.18),0 0 60px rgba(0,255,136,.08)}
button::after{content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.12),transparent);
  background-size:200%% 100%%;animation:shimmer 3s ease-in-out infinite}
button:hover{transform:translateY(-2px);
  box-shadow:0 8px 32px rgba(255,180,0,.3),0 0 80px rgba(0,255,136,.12)}
button:active{transform:translateY(0)}
.ver{text-align:center;margin-top:24px;font-size:10px;color:#3a2a1a;
  letter-spacing:.5px;font-weight:500}
.alt-link{text-align:center;margin-top:16px;font-size:13px;color:#5a7090;font-weight:500}
.alt-link a{color:#00d4ff;text-decoration:none;transition:color .2s;font-weight:600}
.alt-link a:hover{color:#00ff88;text-shadow:0 0 12px rgba(0,212,255,.15)}
.pw-wrap{position:relative}
.pw-wrap input{padding-right:48px}
.pw-toggle{position:absolute;right:16px;top:15px;cursor:pointer;
  color:#6a5a3a;font-size:16px;line-height:1;user-select:none;
  transition:color .2s,transform .15s;background:none;border:none;width:auto;padding:0;
  box-shadow:none}
.pw-toggle:hover{color:#00d4ff;transform:scale(1.15)}
.lang-bar{display:flex;justify-content:center;gap:6px;margin-top:18px}
.lang-btn{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
  border-radius:8px;padding:4px 10px;font-size:11px;cursor:pointer;
  color:#5a4a3a;font-family:'Barlow',sans-serif;font-weight:600;
  transition:all .25s;width:auto;box-shadow:none;letter-spacing:.3px}
.lang-btn:hover{color:#00d4ff;border-color:rgba(0,212,255,.25);
  background:rgba(0,212,255,.08)}
.lang-btn.active{color:#00d4ff;border-color:rgba(0,212,255,.4);
  background:rgba(0,212,255,.1);box-shadow:0 0 12px rgba(0,212,255,.08)}
@media(max-width:480px){.box{margin:12px;padding:36px 28px 28px;border-radius:22px}
  .logo-name{font-size:28px}.logo-icon{font-size:44px}}
</style></head><body>
<div class="orb orb-1"></div>
<div class="orb orb-2"></div>
<div class="box">
  <div class="logo">
    <div class="logo-icon">&#128274;</div>
    <div class="logo-name">TREV<span>LIX</span></div>
    <div class="logo-sub" data-i18n="subtitle">Algorithmic Trading Bot &middot; v1.5.0</div>
    <div class="admin-badge" data-i18n="admin_badge">Admin Panel</div>
  </div>
  <div class="divider"></div>
  %(body)s
  <div class="ver" data-i18n="footer">TREVLIX &middot; Admin Panel &middot; v1.5.0</div>
  <div class="lang-bar">
    <button class="lang-btn" data-lang="de" title="Deutsch">DE</button>
    <button class="lang-btn active" data-lang="en" title="English">EN</button>
    <button class="lang-btn" data-lang="es" title="Espa&#241;ol">ES</button>
    <button class="lang-btn" data-lang="ru" title="&#1056;&#1091;&#1089;&#1089;&#1082;&#1080;&#1081;">RU</button>
    <button class="lang-btn" data-lang="pt" title="Portugu&#234;s">PT</button>
  </div>
</div>
<script>
(function(){
  var T={
    de:{subtitle:"Algorithmischer Trading Bot &middot; v1.5.0",
        footer:"TREVLIX &middot; Admin-Bereich &middot; v1.5.0",
        admin_badge:"Admin-Bereich",
        admin_user:"Admin Benutzername",admin_pass:"Admin Passwort",
        admin_btn:"Admin-Anmeldung &rarr;",
        back_login:"&larr; Zum normalen Login"},
    en:{subtitle:"Algorithmic Trading Bot &middot; v1.5.0",
        footer:"TREVLIX &middot; Admin Panel &middot; v1.5.0",
        admin_badge:"Admin Panel",
        admin_user:"Admin Username",admin_pass:"Admin Password",
        admin_btn:"Admin Sign In &rarr;",
        back_login:"&larr; Back to User Login"},
    es:{subtitle:"Bot de Trading Algor\\u00edtmico &middot; v1.5.0",
        footer:"TREVLIX &middot; Panel de Admin &middot; v1.5.0",
        admin_badge:"Panel de Admin",
        admin_user:"Usuario Admin",admin_pass:"Contrase\\u00f1a Admin",
        admin_btn:"Acceso Admin &rarr;",
        back_login:"&larr; Volver al Login"},
    ru:{subtitle:"\\u0410\\u043b\\u0433\\u043e\\u0440\\u0438\\u0442\\u043c\\u0438\\u0447\\u0435\\u0441\\u043a\\u0438\\u0439 \\u0422\\u0440\\u0435\\u0439\\u0434\\u0438\\u043d\\u0433 \\u0411\\u043e\\u0442 &middot; v1.5.0",
        footer:"TREVLIX &middot; \\u041f\\u0430\\u043d\\u0435\\u043b\\u044c \\u0430\\u0434\\u043c\\u0438\\u043d\\u0430 &middot; v1.5.0",
        admin_badge:"\\u041f\\u0430\\u043d\\u0435\\u043b\\u044c \\u0430\\u0434\\u043c\\u0438\\u043d\\u0430",
        admin_user:"\\u0418\\u043c\\u044f \\u0430\\u0434\\u043c\\u0438\\u043d\\u0430",
        admin_pass:"\\u041f\\u0430\\u0440\\u043e\\u043b\\u044c \\u0430\\u0434\\u043c\\u0438\\u043d\\u0430",
        admin_btn:"\\u0412\\u0445\\u043e\\u0434 \\u0430\\u0434\\u043c\\u0438\\u043d\\u0430 &rarr;",
        back_login:"&larr; \\u041a \\u043e\\u0431\\u044b\\u0447\\u043d\\u043e\\u043c\\u0443 \\u0432\\u0445\\u043e\\u0434\\u0443"},
    pt:{subtitle:"Bot de Trading Algor\\u00edtmico &middot; v1.5.0",
        footer:"TREVLIX &middot; Painel Admin &middot; v1.5.0",
        admin_badge:"Painel Admin",
        admin_user:"Usu\\u00e1rio Admin",admin_pass:"Senha Admin",
        admin_btn:"Acesso Admin &rarr;",
        back_login:"&larr; Voltar ao Login"}
  };
  function setLang(l){
    if(!T[l])return;
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      var k=el.getAttribute('data-i18n');if(T[l][k])el.innerHTML=T[l][k];
    });
    document.querySelectorAll('.lang-btn').forEach(function(b){
      b.classList.toggle('active',b.getAttribute('data-lang')===l);
    });
    try{localStorage.setItem('trevlix_lang',l);}catch(e){}
  }
  document.querySelectorAll('.lang-btn').forEach(function(b){
    b.addEventListener('click',function(){setLang(this.getAttribute('data-lang'));});
  });
  var saved;try{saved=localStorage.getItem('trevlix_lang');}catch(e){}
  if(saved&&T[saved])setLang(saved);
  document.querySelectorAll('input[type="password"]').forEach(function(inp){
    var wrap=document.createElement('div');wrap.className='pw-wrap';
    inp.parentNode.insertBefore(wrap,inp);wrap.appendChild(inp);
    var btn=document.createElement('button');btn.type='button';btn.className='pw-toggle';
    btn.innerHTML='&#128065;';btn.setAttribute('aria-label','Toggle password visibility');
    wrap.appendChild(btn);
    btn.addEventListener('click',function(){
      var t=inp.type==='password'?'text':'password';inp.type=t;
      btn.style.color=t==='text'?'#00d4ff':'';
    });
  });
})();
</script>
</body></html>"""


def _ensure_csrf() -> str:
    """CSRF-Token in Session erzeugen/abrufen."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def create_auth_blueprint(
    db: Any,
    config: dict,
    limiter: Any,
    db_audit_fn: Callable,
    check_login_rate_fn: Callable,
    record_login_attempt_fn: Callable,
    audit_fn: Callable,
    template_dir: str,
) -> Blueprint:
    """Erstellt und konfiguriert den Auth Blueprint.

    Args:
        db: MySQLManager-Instanz für DB-Zugriffe.
        config: CONFIG-Dict mit app-weiten Einstellungen.
        limiter: Flask-Limiter Instanz für Rate-Limiting.
        db_audit_fn: Funktion zum Schreiben von Audit-Log-Einträgen.
        check_login_rate_fn: Prüft ob IP-Adresse im Ratelimit ist.
        record_login_attempt_fn: Zeichnet Login-Versuch auf.
        audit_fn: Interne Audit-Funktion (kürzer als db_audit_fn).
        template_dir: Pfad zum Templates-Verzeichnis.

    Returns:
        Konfigurierter Flask Blueprint für Auth-Routes.
    """
    bp = Blueprint("auth", __name__)

    @bp.route("/")
    def index():
        """Hauptseite - leitet zu Login um wenn nicht eingeloggt.

        Returns:
            Dashboard HTML oder Redirect zu /login.
        """
        if not session.get("user_id"):
            return redirect("/login")
        return send_file(os.path.join(template_dir, "dashboard.html"))

    @bp.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def login():
        """Login-Route für Benutzerauthentifizierung.

        GET: Zeigt Login-Formular.
        POST: Verarbeitet Login-Daten mit Brute-Force-Schutz.

        Returns:
            Login-Seite (HTML) oder Redirect nach erfolgreichem Login.
        """
        allow_reg = config.get("allow_registration", False)
        reg_link = (
            '<div class="alt-link">Noch kein Konto? <a href="/register">Registrieren</a></div>'
            if allow_reg
            else ""
        )
        if request.method == "GET":
            err = request.args.get("err", "")
            msg_cls = "msg msg-err"
            msg_txt = "Falsches Passwort oder Benutzer nicht gefunden" if err else ""
            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/login">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{"block" if err else "none"}">{msg_txt}</div>
    <label>Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Passwort</label>
    <input type="password" name="password" required autofocus autocomplete="current-password">
    <button type="submit">Anmelden &rarr;</button>
  </form>
  {reg_link}"""
            return _AUTH_TEMPLATE % {"page_title": "Login", "msg_display": "none", "body": body}

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/login?err=1")

        username = request.form.get("username", "").strip()[:64]
        password = request.form.get("password", "")
        if not username or not password or len(password) > 128:
            return redirect("/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0,
                "login_blocked",
                f"Brute-Force-Schutz: {username[:32]} von {client_ip}",
                client_ip,
            )
            return redirect("/login?err=1")
        record_login_attempt_fn(client_ip)

        user = db.get_user(username)
        if user and db.verify_password(user["password_hash"], password):
            # Session regenerieren um Session Fixation zu verhindern
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user.get("role", "user")
            now_iso = datetime.now().isoformat()
            session["last_active"] = now_iso
            session["session_created"] = now_iso
            _ensure_csrf()  # CSRF-Token nach Login neu generieren
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "login", f"Login · {client_ip}", client_ip)
            # JWT-Token als Cookie setzen für Socket.io Fallback-Auth
            resp = make_response(redirect("/"))
            try:
                jwt_secret = config.get("jwt_secret", "")
                if jwt_secret:
                    token = pyjwt.encode(
                        {
                            "user_id": user["id"],
                            "username": user["username"],
                            "exp": datetime.now(UTC) + timedelta(hours=8),
                        },
                        jwt_secret,
                        algorithm="HS256",
                    )
                    resp.set_cookie(
                        "token",
                        token,
                        httponly=False,  # JS muss lesen können
                        samesite="Lax",
                        max_age=8 * 3600,
                        path="/",
                    )
            except Exception as e:
                log.warning("JWT cookie generation failed: %s", e)
            return resp

        audit_fn("login_failed", f"user={username} ip={client_ip}")
        return redirect("/login?err=1")

    @bp.route("/register", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def register():
        """Registrierungs-Route für neue Benutzerkonten.

        Nur verfügbar wenn ``allow_registration`` in CONFIG aktiv.
        Erzwingt Passwort-Policy (min. 12 Zeichen, Groß+Klein+Zahl).

        GET: Zeigt Registrierungs-Formular.
        POST: Erstellt neues Benutzerkonto.

        Returns:
            Registrierungs-Seite (HTML) oder Redirect.
        """
        import re as _re

        if not config.get("allow_registration", False):
            body = """  <div class="msg msg-err" style="display:block">
    Registrierung ist deaktiviert. Bitte wende dich an den Administrator.
  </div>
  <div class="alt-link" style="margin-top:20px"><a href="/login">&larr; Zur Anmeldung</a></div>"""
            return _AUTH_TEMPLATE % {
                "page_title": "Registrierung",
                "msg_display": "none",
                "body": body,
            }, 403

        if request.method == "GET":
            err = request.args.get("err", "")
            ok = request.args.get("ok", "")
            if err == "exists":
                msg_txt, msg_cls, show = "Benutzername bereits vergeben.", "msg msg-err", "block"
            elif err == "uname":
                msg_txt, msg_cls, show = (
                    "Benutzername muss mind. 3 Zeichen haben.",
                    "msg msg-err",
                    "block",
                )
            elif err == "short":
                msg_txt, msg_cls, show = (
                    "Passwort muss mind. 12 Zeichen mit Groß+Klein+Zahl+Sonderzeichen"
                    " haben und darf keine gängigen Muster enthalten.",
                    "msg msg-err",
                    "block",
                )
            elif err == "match":
                msg_txt, msg_cls, show = "Passwörter stimmen nicht überein.", "msg msg-err", "block"
            elif ok:
                msg_txt, msg_cls, show = (
                    "Konto erstellt! Du kannst dich jetzt anmelden.",
                    "msg msg-ok",
                    "block",
                )
            else:
                msg_txt, msg_cls, show = "", "msg msg-err", "none"

            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/register">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{show}">{msg_txt}</div>
    <label>Benutzername</label>
    <input type="text" name="username" required autocomplete="username" minlength="3" maxlength="32">
    <label>Passwort</label>
    <input type="password" name="password" required autocomplete="new-password" minlength="12">
    <label>Passwort bestätigen</label>
    <input type="password" name="password2" required autocomplete="new-password" minlength="12">
    <button type="submit">Konto erstellen &rarr;</button>
  </form>
  <div class="alt-link"><a href="/login">&larr; Zur Anmeldung</a></div>"""
            return _AUTH_TEMPLATE % {
                "page_title": "Registrierung",
                "msg_display": "none",
                "body": body,
            }

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/register")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if len(username) < 3 or len(username) > 32:
            return redirect("/register?err=uname")
        _WEAK_PATTERNS = frozenset(
            {
                "password",
                "123456",
                "qwerty",
                "admin",
                "letmein",
                "welcome",
                "monkey",
                "dragon",
                "master",
                "abc123",
                "login",
                "princess",
                "passw0rd",
                "shadow",
                "trustno1",
            }
        )
        if len(password) > 128:
            return redirect("/register?err=short")
        has_upper = _re.search(r"[A-Z]", password)
        has_lower = _re.search(r"[a-z]", password)
        has_digit = _re.search(r"\d", password)
        has_special = _re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", password)
        pw_lower = password.lower()
        has_weak = any(w in pw_lower for w in _WEAK_PATTERNS)
        if (
            len(password) < 12
            or not (has_upper and has_lower and has_digit and has_special)
            or has_weak
        ):
            return redirect("/register?err=short")
        if not hmac.compare_digest(password, password2):
            return redirect("/register?err=match")
        if db.get_user(username):
            return redirect("/register?err=exists")

        if db.create_user(username, password, role="user"):
            db_audit_fn(
                0,
                "register",
                f"Neues Konto: {username} · {request.remote_addr}",
                request.remote_addr or "",
            )
            return redirect("/register?ok=1")
        return redirect("/register?err=exists")

    @bp.route("/logout")
    def logout():
        """Meldet den Benutzer ab und löscht die Session.

        Returns:
            Redirect zur Login-Seite.
        """
        session.clear()
        resp = make_response(redirect("/login"))
        resp.delete_cookie("token", path="/")
        return resp

    # ── Admin Login ──────────────────────────────────────────────────────

    @bp.route("/admin/login", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def admin_login():
        """Separates Admin-Login mit strengerem Rate-Limiting.

        GET: Zeigt Admin-Login-Formular.
        POST: Authentifiziert nur Benutzer mit role='admin'.

        Returns:
            Admin-Login-Seite (HTML) oder Redirect zum Dashboard.
        """
        if request.method == "GET":
            err = request.args.get("err", "")
            msg_cls = "msg msg-err"
            if err:
                msg_txt = "Falsches Passwort oder Benutzer nicht gefunden"
            else:
                msg_txt = ""
            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/admin/login">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{"block" if err else "none"}">{msg_txt}</div>
    <label>Admin Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Admin Passwort</label>
    <input type="password" name="password" required autofocus autocomplete="current-password">
    <button type="submit">Admin-Anmeldung &rarr;</button>
  </form>
  <div class="alt-link"><a href="/login">&larr; Zum normalen Login</a></div>
  <div class="alt-link" style="margin-top:8px"><a href="/admin/reset-password">Passwort vergessen?</a></div>"""
            return _ADMIN_AUTH_TEMPLATE % {
                "page_title": "Admin Login",
                "msg_display": "none",
                "body": body,
            }

        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/admin/login?err=1")

        username = request.form.get("username", "").strip()[:64]
        password = request.form.get("password", "")
        if not username or not password or len(password) > 128:
            return redirect("/admin/login?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            db_audit_fn(
                0,
                "admin_login_blocked",
                f"Brute-Force-Schutz (Admin): {username[:32]} von {client_ip}",
                client_ip,
            )
            return redirect("/admin/login?err=1")
        record_login_attempt_fn(client_ip)

        user = db.get_user(username)
        if user and db.verify_password(user["password_hash"], password):
            if user.get("role") != "admin":
                audit_fn(
                    "admin_login_denied", f"user={username} ip={client_ip} role={user.get('role')}"
                )
                return redirect("/admin/login?err=1")
            # Session regenerieren um Session Fixation zu verhindern
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = "admin"
            now_iso = datetime.now().isoformat()
            session["last_active"] = now_iso
            session["session_created"] = now_iso
            _ensure_csrf()  # CSRF-Token nach Admin-Login neu generieren
            db.update_user_login(user["id"])
            db_audit_fn(user["id"], "admin_login", f"Admin-Login · {client_ip}", client_ip)
            return redirect("/")

        audit_fn("admin_login_failed", f"user={username} ip={client_ip}")
        return redirect("/admin/login?err=1")

    @bp.route("/admin/reset-password", methods=["GET", "POST"])
    @limiter.limit("5 per minute")
    def admin_reset_password():
        """Admin-Passwort zurücksetzen ohne E-Mail-Bestätigung.

        Verifiziert den Benutzer über das aktuelle ADMIN_PASSWORD aus
        der Umgebungsvariable. Kein E-Mail-Workflow nötig.

        GET: Zeigt Passwort-Reset-Formular.
        POST: Setzt das Admin-Passwort nach Verifizierung zurück.

        Returns:
            Reset-Seite (HTML) oder Redirect nach Erfolg.
        """
        import re as _re

        if request.method == "GET":
            err = request.args.get("err", "")
            ok = request.args.get("ok", "")
            if ok:
                msg_txt = "Passwort erfolgreich geändert! Bitte neu anmelden."
                msg_cls = "msg msg-ok"
                show = "block"
            elif err == "verify":
                msg_txt = "Master-Passwort ungültig."
                msg_cls = "msg msg-err"
                show = "block"
            elif err == "policy":
                msg_txt = (
                    "Neues Passwort muss mind. 12 Zeichen mit Groß+Klein+Zahl+Sonderzeichen haben."
                )
                msg_cls = "msg msg-err"
                show = "block"
            elif err == "match":
                msg_txt = "Passwörter stimmen nicht überein."
                msg_cls = "msg msg-err"
                show = "block"
            elif err:
                msg_txt = "Fehler beim Zurücksetzen."
                msg_cls = "msg msg-err"
                show = "block"
            else:
                msg_txt = ""
                msg_cls = "msg msg-err"
                show = "none"

            csrf = _ensure_csrf()
            body = f"""  <form method="POST" action="/admin/reset-password">
    <input type="hidden" name="_csrf" value="{csrf}">
    <div class="{msg_cls}" style="display:{show}">{msg_txt}</div>
    <label>Admin Benutzername</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Master-Passwort (ADMIN_PASSWORD)</label>
    <input type="password" name="master_password" required autocomplete="off">
    <label>Neues Passwort</label>
    <input type="password" name="new_password" required autocomplete="new-password" minlength="12">
    <label>Neues Passwort bestätigen</label>
    <input type="password" name="new_password2" required autocomplete="new-password" minlength="12">
    <button type="submit">Passwort zurücksetzen &rarr;</button>
  </form>
  <div class="alt-link"><a href="/admin/login">&larr; Zum Admin-Login</a></div>"""
            return _ADMIN_AUTH_TEMPLATE % {
                "page_title": "Passwort zurücksetzen",
                "msg_display": "none",
                "body": body,
            }

        # POST
        csrf_submitted = request.form.get("_csrf", "")
        csrf_expected = session.get("_csrf_token", "")
        if not csrf_submitted or not hmac.compare_digest(csrf_submitted, csrf_expected):
            return redirect("/admin/reset-password?err=1")

        username = request.form.get("username", "").strip()[:64]
        master_password = request.form.get("master_password", "")
        new_password = request.form.get("new_password", "")
        new_password2 = request.form.get("new_password2", "")

        if not username or not master_password or not new_password:
            return redirect("/admin/reset-password?err=1")

        client_ip = request.remote_addr or "unknown"
        if not check_login_rate_fn(client_ip):
            return redirect("/admin/reset-password?err=1")
        record_login_attempt_fn(client_ip)

        # Verifiziere Master-Passwort gegen ADMIN_PASSWORD aus Config
        # Always run compare_digest to prevent timing attacks that reveal
        # whether ADMIN_PASSWORD is configured.
        admin_pw = config.get("admin_password", "") or "disabled"
        if not hmac.compare_digest(master_password, admin_pw):
            audit_fn("admin_reset_failed", f"user={username[:32]} ip={client_ip} reason=master_pw")
            return redirect("/admin/reset-password?err=verify")

        # Verifiziere, dass der User existiert und Admin ist
        user = db.get_user(username)
        if not user or user.get("role") != "admin":
            audit_fn("admin_reset_failed", f"user={username[:32]} ip={client_ip} reason=not_admin")
            return redirect("/admin/reset-password?err=verify")

        # Passwort-Policy prüfen
        if len(new_password) > 128:
            return redirect("/admin/reset-password?err=policy")
        has_upper = _re.search(r"[A-Z]", new_password)
        has_lower = _re.search(r"[a-z]", new_password)
        has_digit = _re.search(r"\d", new_password)
        has_special = _re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", new_password)
        if len(new_password) < 12 or not (has_upper and has_lower and has_digit and has_special):
            return redirect("/admin/reset-password?err=policy")

        if not hmac.compare_digest(new_password, new_password2):
            return redirect("/admin/reset-password?err=match")

        # Passwort aktualisieren
        if db.update_password(user["id"], new_password):
            db_audit_fn(
                user["id"],
                "admin_password_reset",
                f"Admin-PW-Reset für '{username[:32]}' · {client_ip}",
                client_ip,
            )
            session.clear()
            return redirect("/admin/reset-password?ok=1")

        return redirect("/admin/reset-password?err=1")

    @bp.route("/admin/logout")
    def admin_logout():
        """Admin-Abmeldung."""
        session.clear()
        return redirect("/admin/login")

    return bp
