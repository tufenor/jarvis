(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var nucleo = new window.Nucleo($("nucleo"));
  var socket = null;
  var tentativas = 0;

  var NOMES_ESTADO = {
    repouso: "REPOUSO", ouvindo: "OUVINDO", pensando: "PENSANDO",
    executando: "EXECUTANDO", respondendo: "RESPONDENDO", erro: "ERRO"
  };

  // ---- relógio --------------------------------------------------------------

  function relogio() {
    var d = new Date();
    $("relogio").textContent = d.toLocaleDateString("pt-BR") + " · " + d.toLocaleTimeString("pt-BR");
  }
  relogio();
  setInterval(relogio, 1000);

  // ---- utilidades -------------------------------------------------------------

  function indicador(id, ok, texto) {
    var el = $(id);
    el.dataset.ok = ok ? "true" : "false";
    el.querySelector("b").textContent = texto;
  }

  function horaCurta(iso) {
    if (!iso) return "--";
    return iso.slice(11, 19);
  }

  function duracao(s) {
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), seg = s % 60;
    function d2(n) { return (n < 10 ? "0" : "") + n; }
    return d2(h) + ":" + d2(m) + ":" + d2(seg);
  }

  function numero(v, casas) {
    return v === null || v === undefined ? "--" : Number(v).toFixed(casas);
  }

  // ---- estado local (retorno imediato, antes do servidor responder) ------------

  // Enquanto pensa ou executa, o detalhe ganha um cronômetro: espera com
  // número andando é espera explicada; sem ele parece travado.
  var cronometro = { desde: 0, base: "" };

  function mostrarEstado(estado, detalhe) {
    if (estado !== document.body.dataset.estado || (detalhe !== undefined && detalhe !== cronometro.base)) {
      cronometro.desde = performance.now();
    }
    document.body.dataset.estado = estado;
    nucleo.mudarEstado(estado);
    $("estado").textContent = NOMES_ESTADO[estado] || estado.toUpperCase();
    if (detalhe !== undefined) cronometro.base = detalhe;
    atualizarDetalhe();
  }

  function atualizarDetalhe() {
    var estado = document.body.dataset.estado;
    var texto = cronometro.base;
    if (estado === "pensando" || estado === "executando") {
      texto += " · " + ((performance.now() - cronometro.desde) / 1000).toFixed(1) + " s";
    }
    $("detalhe").textContent = texto;
  }
  setInterval(atualizarDetalhe, 100);

  // ---- render do retrato do servidor -------------------------------------------

  function render(r) {
    var a = r.agente, p = r.placa, s = r.sistema;
    mostrarEstado(a.estado, a.detalhe);
    $("ultima-fala").textContent = a.ultima_fala || "—";
    $("rotulo-falante").textContent = a.falante ? a.falante.toUpperCase() : "VOCÊ";
    $("v-vozes").textContent = (r.vozes && r.vozes.length) ? r.vozes.join(", ") : "nenhuma";
    $("ultima-resposta").textContent = a.ultima_resposta || "—";

    indicador("ind-placa", p.online, p.online ? "ONLINE" : "OFFLINE");
    indicador("ind-cerebro", r.cerebro.online, r.cerebro.nome.toUpperCase());
    $("ind-cerebro").title = r.cerebro.online ? "" : (r.cerebro.motivo || "");
    var rec = r.recursos || {};
    indicador("ind-mic", !!rec.microfone, rec.microfone ? "ABERTO" : "DESLIGADO");
    $("versao").textContent = rec.voz ? "VOZ ATIVA · DIGA “JARVIS”" : "MODO TEXTO";
    $("linha-luz").hidden = rec.luz === false;
    document.querySelectorAll('[data-acao^="luz"]').forEach(function (b) { b.hidden = rec.luz === false; });

    $("v-temp").textContent = p.online ? numero(p.temperatura, 0) : "--";
    $("v-umid").textContent = p.online ? numero(p.umidade, 0) : "--";
    var mov = $("v-mov");
    mov.textContent = !p.online ? "--" : (p.movimento ? "DETECTADO" : "NENHUM");
    mov.dataset.nivel = p.online && p.movimento ? "atencao" : "";
    var led = $("v-led");
    led.textContent = !p.online ? "--" : (p.led ? "ACESA" : "APAGADA") + (p.led_manual ? " · MANUAL" : " · AUTO");
    led.dataset.nivel = p.online && p.led ? "ativo" : "";
    $("v-contato").textContent = horaCurta(p.ultimo_contato);

    barra("cpu", s.cpu);
    barra("mem", s.memoria);
    var en = $("v-energia");
    en.textContent = s.agente_energia === null ? "--" : (s.agente_energia ? "ONLINE" : "OFFLINE");
    en.dataset.nivel = s.agente_energia === false ? "atencao" : "";
    $("v-uptime").textContent = duracao(s.ligado_ha_s);

    renderAlertas(r.alertas);
    renderLog(r.atividade);
  }

  function barra(nome, valor) {
    $("v-" + nome).textContent = valor === null || valor === undefined ? "--" : numero(valor, 0).padStart(3, " ") + "%";
    var b = $("b-" + nome);
    b.style.width = (valor || 0) + "%";
    b.dataset.nivel = valor >= 85 ? "atencao" : "";
  }

  function renderAlertas(lista) {
    var ul = $("alertas");
    ul.textContent = "";
    var cont = $("n-alertas");
    cont.textContent = lista.length;
    cont.dataset.nivel = lista.some(function (x) { return x.nivel === "critico"; }) ? "critico"
      : (lista.length ? "atencao" : "");
    if (!lista.length) {
      var vazio = document.createElement("li");
      vazio.className = "vazio";
      vazio.textContent = "Nenhum alerta";
      ul.appendChild(vazio);
      return;
    }
    lista.forEach(function (al) {
      var li = document.createElement("li");
      li.dataset.nivel = al.nivel;
      var span = document.createElement("span");
      span.textContent = al.texto;
      li.appendChild(span);
      ul.appendChild(li);
    });
  }

  var ultimaAtividade = "";
  function renderLog(itens) {
    // só redesenha se mudou, para não perder a rolagem do usuário
    var chave = itens.length ? itens[0].quando + itens[0].texto + itens.length : "";
    if (chave === ultimaAtividade) return;
    ultimaAtividade = chave;
    var ol = $("log");
    ol.textContent = "";
    itens.forEach(function (it) {
      var li = document.createElement("li");
      li.dataset.tipo = it.tipo;
      [["hora", horaCurta(it.quando)], ["tipo", it.tipo], ["txt", it.texto]].forEach(function (c) {
        var sp = document.createElement("span");
        sp.className = c[0];
        sp.textContent = c[1];
        li.appendChild(sp);
      });
      ol.appendChild(li);
    });
  }

  // ---- WebSocket com reconexão ---------------------------------------------------

  function conectar() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(proto + "//" + location.host + "/ws");
    socket.onopen = function () {
      tentativas = 0;
      document.body.dataset.conectado = "true";
      indicador("ind-conexao", true, "AO VIVO");
    };
    socket.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      if (msg.tipo === "estado") render(msg);
      else if (msg.tipo === "nivel") nucleo.definirNivel(msg.valor);
    };
    socket.onclose = function () {
      document.body.dataset.conectado = "false";
      indicador("ind-conexao", false, "RECONECTANDO");
      // espera crescente até 10 s: não martelar um servidor que acabou de cair
      var espera = Math.min(10000, 500 * Math.pow(2, tentativas++));
      setTimeout(conectar, espera);
    };
  }
  conectar();

  // ---- comandos ---------------------------------------------------------------

  function post(url, corpo) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  $("form-comando").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var entrada = $("entrada");
    var texto = entrada.value.trim();
    if (!texto) return;
    entrada.value = "";
    mostrarEstado("pensando", "enviando comando…");
    $("ultima-fala").textContent = texto;
    post("/api/comando", { texto: texto }).catch(function () {
      mostrarEstado("erro", "não consegui falar com o servidor do JARVIS");
    });
  });

  $("mic").addEventListener("click", function () {
    mostrarEstado("ouvindo", "abrindo microfone…");
    post("/api/escutar").catch(function () {
      mostrarEstado("erro", "não consegui falar com o servidor do JARVIS");
    });
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      mostrarEstado("repouso", "cancelando…");
      post("/api/cancelar").catch(function () {});
    }
  });

  document.querySelectorAll("[data-acao],[data-demo]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var url = botao.dataset.acao ? "/api/acao/" + botao.dataset.acao : "/api/demonstracao/" + botao.dataset.demo;
      botao.setAttribute("aria-busy", "true");
      botao.dataset.falhou = "false";
      post(url)
        .catch(function () { botao.dataset.falhou = "true"; })
        .then(function () { botao.removeAttribute("aria-busy"); });
    });
  });

  $("entrada").focus();
})();
