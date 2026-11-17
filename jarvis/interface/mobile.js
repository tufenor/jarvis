(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var socket = null;
  var retry = 0;
  var lastMotion = false;
  var nextPresenceCheck = 0;
  var deferredInstall = null;

  function dispositivoAtual() {
    var salvo = localStorage.getItem("jarvis-dispositivo");
    if (salvo === "a53" || salvo === "iphone") return salvo;
    return /iPhone|iPad|iPod/i.test(navigator.userAgent) ? "iphone" : "a53";
  }

  var dispositivo = dispositivoAtual();

  function notice(text, kind) {
    $("notice").textContent = text;
    $("notice").dataset.kind = kind || "";
  }

  function setConnection(state, text) {
    $("connection").dataset.state = state;
    $("connection").textContent = text;
  }

  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }

  function render(r) {
    var a = r.agente || {}, p = r.placa || {}, todos = r.presencas_moveis || {};
    var pres = todos[dispositivo] || r.presenca_mobile || {};
    $("pc-state").textContent = (a.estado || "—").toUpperCase();
    $("board-state").textContent = p.online ? "ONLINE" : "OFFLINE";
    $("motion-state").textContent = p.movimento ? "DETECTADO" : "NENHUM";
    $("temperature").textContent = p.temperatura == null ? "—" : Number(p.temperatura).toFixed(0) + " °C";
    $("humidity").textContent = p.umidade == null ? "—" : Number(p.umidade).toFixed(0) + "%";
    $("phone-state").textContent = pres.presente === true ? "PRESENTE" : pres.presente === false ? "AUSENTE" : "INDETERMINADO";
    $("phone-label").textContent = dispositivo === "iphone" ? "iPHONE" : "A53";
    $("hero-detail").textContent = a.detalhe || "aguardando comando";
    $("response").textContent = a.ultima_resposta || "—";
    $("last-speech").textContent = a.ultima_fala ? "Última fala: " + a.ultima_fala : "Nenhum comando enviado.";
    if (pres.quando) $("presence-detail").textContent = "Última verificação: " + new Date(pres.quando).toLocaleString("pt-BR") + " · " + (pres.origem || dispositivo);

    var movimento = !!p.movimento;
    if (movimento && !lastMotion && Date.now() >= nextPresenceCheck) {
      nextPresenceCheck = Date.now() + 60 * 60 * 1000;
      enviarPresenca("movimento");
    }
    lastMotion = movimento;
  }

  function enviarPresenca(evento) {
    var payload = { presente: null, origem: dispositivo, evento: evento };
    if (!navigator.geolocation) {
      return post("/api/presenca", payload).catch(function () {});
    }
    navigator.geolocation.getCurrentPosition(function (pos) {
      payload.presente = true;
      payload.latitude = pos.coords.latitude;
      payload.longitude = pos.coords.longitude;
      payload.precisao_m = pos.coords.accuracy;
      post("/api/presenca", payload).then(function () { notice("Presença de " + dispositivo.toUpperCase() + " atualizada.", "ok"); }).catch(function () { notice("Não consegui atualizar a presença.", "error"); });
    }, function () {
      post("/api/presenca", payload).then(function () { notice("Localização indisponível; presença ficou indeterminada.", ""); }).catch(function () {});
    }, { enableHighAccuracy: false, maximumAge: 15 * 60 * 1000, timeout: 8000 });
  }

  function conectar() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(proto + "//" + location.host + "/ws");
    socket.onopen = function () { retry = 0; setConnection("online", "ONLINE"); notice("Canal seguro conectado.", "ok"); };
    socket.onmessage = function (ev) { try { var msg = JSON.parse(ev.data); if (msg.tipo === "estado") render(msg); } catch (_) {} };
    socket.onclose = function () { setConnection("error", "RECONNECTANDO"); setTimeout(conectar, Math.min(10000, 500 * Math.pow(2, retry++))); };
    socket.onerror = function () { setConnection("error", "ERRO"); };
  }

  function enviarComando(texto) {
    texto = (texto || "").trim();
    if (!texto) return Promise.resolve();
    return post("/api/comando", { texto: texto })
      .then(function () { notice("Comando enviado ao JARVIS.", "ok"); })
      .catch(function (e) { notice("Comando recusado: " + e.message, "error"); });
  }

  $("command-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var texto = $("command").value.trim();
    if (!texto) return;
    $("command").value = "";
    enviarComando(texto);
  });

  // Push-to-talk usa o Web Speech API do navegador. Funciona offline em Chrome
  // Android recentes; sem suporte (iOS Safari antigo), o botão fica desligado.
  var Reco = window.SpeechRecognition || window.webkitSpeechRecognition;
  var ptt = $("push-to-talk");
  if (!Reco) {
    ptt.disabled = true;
    ptt.textContent = "FALAR (SEM SUPORTE)";
  } else {
    var reco = new Reco();
    reco.lang = "pt-BR";
    reco.continuous = false;
    reco.interimResults = false;
    var escutando = false;
    reco.onstart = function () { escutando = true; ptt.setAttribute("aria-pressed", "true"); ptt.textContent = "OUVINDO…"; notice("Fale agora.", "ok"); };
    reco.onerror = function (e) { escutando = false; ptt.setAttribute("aria-pressed", "false"); ptt.textContent = "FALAR"; notice("Reconhecimento falhou: " + (e.error || "sem permissão"), "error"); };
    reco.onend = function () { escutando = false; ptt.setAttribute("aria-pressed", "false"); ptt.textContent = "FALAR"; };
    reco.onresult = function (ev) {
      var texto = "";
      for (var i = 0; i < ev.results.length; i++) texto += ev.results[i][0].transcript;
      texto = texto.trim();
      if (!texto) { notice("Não entendi o que você falou.", "error"); return; }
      $("command").value = texto;
      enviarComando(texto);
    };
    ptt.addEventListener("click", function () {
      if (escutando) { try { reco.stop(); } catch (_) {} return; }
      try { reco.start(); } catch (_) { /* já ativo */ }
    });
  }
  $("listen").addEventListener("click", function () { post("/api/escutar").then(function () { notice("Microfone do PC aberto.", "ok"); }).catch(function () { notice("Não consegui abrir o microfone.", "error"); }); });
  $("cancel").addEventListener("click", function () { post("/api/cancelar").then(function () { notice("Tarefa cancelada.", "ok"); }).catch(function () { notice("Não consegui cancelar.", "error"); }); });
  $("check-presence").addEventListener("click", function () { nextPresenceCheck = Date.now() + 60 * 60 * 1000; enviarPresenca("manual"); });
  $("device-select").value = dispositivo;
  $("device-select").addEventListener("change", function () {
    dispositivo = this.value;
    localStorage.setItem("jarvis-dispositivo", dispositivo);
    $("phone-label").textContent = dispositivo === "iphone" ? "iPHONE" : "A53";
    notice("Aparelho selecionado: " + dispositivo.toUpperCase() + ".", "ok");
  });

  window.addEventListener("beforeinstallprompt", function (ev) { ev.preventDefault(); deferredInstall = ev; $("install").hidden = false; });
  $("install").addEventListener("click", function () { if (!deferredInstall) return; deferredInstall.prompt(); deferredInstall = null; $("install").hidden = true; });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/mobile-sw.js").catch(function () {});
  conectar();
}());
