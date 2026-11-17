"""Self-contained local control panel for Safari and desktop browsers."""


def control_page(_state=None):
    """Return the same-origin mobile dashboard as a small HTTP response."""
    body = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07111f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="JARVIS">
<title>JARVIS | Casa</title>
<style>
:root{color-scheme:dark;--bg:#07111f;--panel:#101f31;--line:#263d55;--text:#eff7ff;--muted:#a6bacd;--cyan:#43d9ff;--green:#61e6a5;--red:#ff808a;font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at top,#142e47,var(--bg) 65%);color:var(--text)}
main{width:min(760px,100%);margin:auto;padding:calc(20px + env(safe-area-inset-top)) 16px calc(28px + env(safe-area-inset-bottom))}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:4px 0 20px}h1{font-size:clamp(28px,8vw,40px);letter-spacing:.12em;margin:0}.eyebrow{font-size:11px;letter-spacing:.16em;color:var(--cyan);font-weight:700;margin:0 0 7px}.badge{border:1px solid var(--line);border-radius:999px;padding:8px 11px;color:var(--muted);font-size:12px;white-space:nowrap}.badge.ok{color:var(--green)}.badge.err{color:var(--red)}
.card{background:linear-gradient(145deg,#12253a,#0c1928);border:1px solid var(--line);border-radius:18px;padding:18px;margin:12px 0;box-shadow:0 14px 40px #0004}.card h2{font-size:18px;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.metric{padding:14px;border:1px solid var(--line);border-radius:14px;min-height:92px}.metric span{display:block;color:var(--muted);font-size:11px;letter-spacing:.1em}.metric strong{display:block;margin-top:9px;color:var(--cyan);font-size:24px;overflow-wrap:anywhere}
.actions{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.btn{min-height:50px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#19344b;color:var(--text);font:inherit;font-weight:650;cursor:pointer;touch-action:manipulation}.btn:focus-visible,input:focus-visible{outline:3px solid #f3ce58;outline-offset:2px}.btn.primary{background:var(--cyan);color:#031a27;border-color:var(--cyan)}.btn.danger{background:#48232b;border-color:#75404b}.hint,.feedback{color:var(--muted);font-size:13px;line-height:1.5}.feedback{min-height:1.5em;margin:12px 0 0}.field{display:block;color:var(--muted);font-size:14px;margin:14px 0 7px}input{width:100%;min-height:50px;padding:12px;border-radius:12px;border:1px solid var(--line);background:#071522;color:var(--text);font:inherit}.warn{color:#ffd58a}.footer{padding:10px 2px;color:var(--muted);font-size:12px;line-height:1.5}
@media(max-width:440px){main{padding-left:13px;padding-right:13px}.card{padding:15px}.actions{grid-template-columns:1fr}.badge{font-size:10px;padding:7px 8px}.metric strong{font-size:21px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style></head><body><main>
<header><div><p class="eyebrow">CONTROLE LOCAL · ESP32</p><h1>J.A.R.V.I.S.</h1></div><span id="connection" class="badge">conectando…</span></header>
<section class="card" aria-labelledby="sensor-title"><h2 id="sensor-title">Sensores</h2><div class="grid">
<div class="metric"><span>TEMPERATURA</span><strong id="temperature">--</strong></div>
<div class="metric"><span>UMIDADE</span><strong id="humidity">--</strong></div>
<div class="metric"><span>MOVIMENTO</span><strong id="motion">--</strong></div>
<div class="metric"><span>LED GPIO4</span><strong id="led">--</strong></div></div><p class="hint">Atualização automática a cada 3 segundos.</p></section>
<section class="card"><h2>LED do protótipo</h2><div class="actions">
<button class="btn primary" data-led="on">Ligar</button><button class="btn danger" data-led="off">Desligar</button><button class="btn" data-led="auto">Automático</button>
</div><p id="led-feedback" class="feedback" role="status" aria-live="polite"></p></section>
<section class="card"><h2>Despertar o computador</h2><p class="hint">A ESP32 envia o pedido pela rede local. O computador só acorda se o Wi-Fi/BIOS/Windows aceitarem Wake-on-WLAN e se a ESP32 estiver alimentada.</p>
<label class="field" for="wake-token">Token local (32 caracteres hexadecimais)</label><input id="wake-token" type="password" inputmode="text" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="32" placeholder="Digite o token configurado na ESP32">
<button id="wake-button" class="btn primary" style="width:100%;margin-top:10px">Enviar pedido para ligar o PC</button><p id="wake-feedback" class="feedback" role="status" aria-live="polite"></p>
<p class="hint warn">Use apenas na sua rede de casa. O painel usa HTTP local sem criptografia; não compartilhe o token nem exponha a ESP32 à internet.</p></section>
<section class="card"><h2>Desligar o computador</h2><p class="hint warn">Agenda o desligamento para 30 segundos. Salve seu trabalho antes. O agente não fecha aplicativos à força; programas podem impedir o desligamento.</p>
<div class="actions"><button id="shutdown-button" class="btn danger">Desligar em 30 segundos</button><button id="cancel-shutdown-button" class="btn">Cancelar desligamento</button></div>
<p id="pc-feedback" class="feedback" role="status" aria-live="polite"></p><p class="hint">Requer o agente JARVIS instalado e em execução no PC, conectado à mesma rede local.</p></section>
<p class="footer">Abra este endereço no Safari ou no navegador do computador, ambos conectados à mesma rede Wi-Fi. No iPhone: Compartilhar → Adicionar à Tela de Início.</p>
</main><script>
const $=id=>document.getElementById(id);const connection=$('connection');
async function refresh(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const s=await r.json();$('temperature').textContent=s.temperature===null?'Sem leitura':s.temperature+' °C';$('humidity').textContent=s.humidity===null?'Sem leitura':s.humidity+'%';$('motion').textContent=s.motion?'Detectado':'Não detectado';$('led').textContent=s.led?'Ligado':'Desligado';connection.textContent='ESP32 conectada';connection.className='badge ok'}catch(e){connection.textContent='ESP32 sem resposta';connection.className='badge err'}}
document.querySelectorAll('[data-led]').forEach(b=>b.addEventListener('click',async()=>{const f=$('led-feedback');f.textContent='Enviando…';try{const r=await fetch('/led/'+b.dataset.led,{method:'POST',cache:'no-store'});f.textContent=r.ok?'Comando enviado.':('Falha HTTP '+r.status);await refresh()}catch(e){f.textContent='Não consegui falar com a ESP32.'}}));
async function protectedPost(path,feedbackId,confirmation){const token=$('wake-token').value.trim();const f=$(feedbackId);if(!/^[a-fA-F0-9]{32}$/.test(token)){f.textContent='Confira: o token precisa ter exatamente 32 caracteres hexadecimais.';return}if(confirmation&&!window.confirm(confirmation))return;f.textContent='Enviando pela rede local…';try{const r=await fetch(path,{method:'POST',headers:{'Authorization':'Bearer '+token},cache:'no-store'});const t=await r.text();f.textContent=r.ok?t:('Não concluído ('+r.status+'): '+t)}catch(e){f.textContent='Falha de rede ao falar com a ESP32.'}}
document.getElementById('wake-button').addEventListener('click',()=>protectedPost('/wake','wake-feedback','Enviar um pedido para despertar o computador?'));
document.getElementById('shutdown-button').addEventListener('click',()=>protectedPost('/pc/shutdown','pc-feedback','Agendar o desligamento do PC em 30 segundos? Salve seu trabalho antes.'));
document.getElementById('cancel-shutdown-button').addEventListener('click',()=>protectedPost('/pc/cancel','pc-feedback',null));
refresh();setInterval(refresh,3000);
</script></body></html>"""
    content_length = len(body.encode("utf-8"))
    return ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
            "Cache-Control: no-store\r\nContent-Length: %d\r\n"
            "Connection: close\r\n\r\n" % content_length) + body


def send_response(client, response):
    """Write a full HTTP response even if TCP accepts only a partial send."""
    remaining = response.encode("utf-8")
    while remaining:
        sent = client.send(remaining)
        if sent is None or sent <= 0:
            raise OSError("HTTP client disconnected during response")
        remaining = remaining[sent:]
