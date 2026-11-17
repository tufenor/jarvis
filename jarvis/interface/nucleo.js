/* Núcleo: a presença viva do JARVIS.
 *
 * Cada estado é uma FORMA, não só uma cor — quem não distingue cores precisa
 * ler o estado igual. As partículas não saltam de uma forma para outra: cada
 * uma persegue seu alvo, então a troca de estado vira uma metamorfose.
 */
(function () {
  "use strict";

  var N = 560;
  var RAIOS = 24;
  var SEGMENTOS_ERRO = 9;
  var AUREO = Math.PI * (3 - Math.sqrt(5));
  var TAU = Math.PI * 2;

  function Nucleo(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.estado = "repouso";
    this.nivelAlvo = 0;
    this.nivel = 0;
    this.inicio = performance.now();
    this.parado = window.matchMedia("(prefers-reduced-motion: reduce)");
    this.particulas = [];
    for (var i = 0; i < N; i++) this.particulas.push({ x: 0, y: 0, a: 0 });
    // deslocamentos fixos dos fragmentos do erro: aleatórios, mas iguais a cada quadro
    this.desvioErro = [];
    for (var s = 0; s < SEGMENTOS_ERRO; s++) {
      this.desvioErro.push({ r: (Math.random() - 0.5) * 0.22, g: (Math.random() - 0.5) * 0.12 });
    }
    this.lerCores();
    this.redimensionar();
    var self = this;
    window.addEventListener("resize", function () { self.redimensionar(); self.desenharSeParado(); });
    this.parado.addEventListener("change", function () { self.iniciar(); });
    this.posicionarTudo(0);
    this.iniciar();
  }

  Nucleo.prototype.lerCores = function () {
    var css = getComputedStyle(document.documentElement);
    this.cor = css.getPropertyValue("--acento").trim() || "#2ee6ea";
    this.corErro = css.getPropertyValue("--critico").trim() || "#f04848";
    this.corLinha = css.getPropertyValue("--linha-forte").trim() || "#26323a";
  };

  Nucleo.prototype.redimensionar = function () {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var r = this.canvas.getBoundingClientRect();
    this.dpr = dpr;
    this.l = Math.max(1, r.width * dpr);
    this.a = Math.max(1, r.height * dpr);
    this.canvas.width = this.l;
    this.canvas.height = this.a;
    this.R = Math.min(this.l, this.a) * 0.3;
  };

  Nucleo.prototype.mudarEstado = function (estado) {
    if (estado === this.estado) return;
    this.estado = estado;
    this.canvas.setAttribute("aria-label", "Núcleo: " + estado);
    this.desenharSeParado();
  };

  Nucleo.prototype.definirNivel = function (v) { this.nivelAlvo = Math.max(0, Math.min(1, v)); };

  // ---- formas ------------------------------------------------------------

  Nucleo.prototype.alvo = function (i, t, saida) {
    var R = this.R, n = this.nivel, ang, r, k;
    switch (this.estado) {
      case "ouvindo": {
        var noAnel = Math.floor(N * 0.7);
        if (i < noAnel) {
          ang = (i / noAnel) * TAU + t * 0.3;
          r = R * (1 + n * 0.1);
          saida.x = Math.cos(ang) * r; saida.y = Math.sin(ang) * r; saida.a = 0.85;
        } else {
          // feixe vertical: o comprimento acompanha o volume do microfone
          k = (i - noAnel) / (N - noAnel);
          var meia = R * (0.25 + n * 1.15);
          saida.x = Math.sin(i * 12.9898) * 1.2 * this.dpr;
          saida.y = (k * 2 - 1) * meia;
          saida.a = 1 - Math.abs(k * 2 - 1) * 0.6;
        }
        return;
      }
      case "pensando": {
        // esfera de Fibonacci girando rápido; a profundidade vira opacidade
        var y = 1 - (2 * (i + 0.5)) / N;
        var rr = Math.sqrt(1 - y * y);
        var phi = i * AUREO + t * 1.7;
        var x = Math.cos(phi) * rr, z = Math.sin(phi) * rr;
        var inc = 0.45, yy = y * Math.cos(inc) - z * Math.sin(inc), zz = y * Math.sin(inc) + z * Math.cos(inc);
        saida.x = x * R * 0.78; saida.y = yy * R * 0.78; saida.a = 0.25 + 0.75 * (zz + 1) / 2;
        return;
      }
      case "executando": {
        // partículas alinhadas em raios, correndo de dentro para fora
        var raio = i % RAIOS;
        var porRaio = N / RAIOS;
        var s = ((Math.floor(i / RAIOS) / porRaio) + t * 0.4) % 1;
        ang = (raio / RAIOS) * TAU + t * 0.05;
        r = R * (0.3 + 0.8 * s);
        saida.x = Math.cos(ang) * r; saida.y = Math.sin(ang) * r; saida.a = 1 - s * 0.85;
        return;
      }
      case "respondendo": {
        ang = (i / N) * TAU + t * 0.2;
        r = R * (1 + (0.025 + n * 0.16) * Math.sin(ang * 6 + t * 8));
        saida.x = Math.cos(ang) * r; saida.y = Math.sin(ang) * r; saida.a = 0.9;
        return;
      }
      case "erro": {
        // anel partido e PARADO: nada gira enquanto há erro
        ang = (i / N) * TAU;
        var seg = Math.floor(ang / (TAU / SEGMENTOS_ERRO));
        var d = this.desvioErro[seg];
        var dentro = (ang % (TAU / SEGMENTOS_ERRO)) / (TAU / SEGMENTOS_ERRO);
        if (dentro < 0.12) { saida.a = 0; } else { saida.a = 0.9; }
        ang += d.g;
        r = R * (1 + d.r);
        saida.x = Math.cos(ang) * r; saida.y = Math.sin(ang) * r;
        return;
      }
      default: { // repouso: anel fino girando devagar
        ang = (i / N) * TAU + t * 0.12;
        saida.x = Math.cos(ang) * R; saida.y = Math.sin(ang) * R; saida.a = 0.75;
      }
    }
  };

  Nucleo.prototype.posicionarTudo = function (t) {
    var alvo = { x: 0, y: 0, a: 0 };
    for (var i = 0; i < N; i++) {
      this.alvo(i, t, alvo);
      var p = this.particulas[i];
      p.x = alvo.x; p.y = alvo.y; p.a = alvo.a;
    }
  };

  // ---- desenho ------------------------------------------------------------

  Nucleo.prototype.desenharMoldura = function () {
    var c = this.ctx, cx = this.l / 2, cy = this.a / 2, R = this.R;
    c.strokeStyle = this.estado === "erro" ? this.corErro : this.corLinha;
    c.globalAlpha = this.estado === "erro" ? 0.5 : 1;
    c.lineWidth = this.dpr;
    // marcações de escala ao redor, como um mostrador
    c.beginPath();
    for (var m = 0; m < 72; m++) {
      var ang = (m / 72) * TAU;
      var r1 = R * 1.38, r2 = R * (m % 6 === 0 ? 1.46 : 1.42);
      c.moveTo(cx + Math.cos(ang) * r1, cy + Math.sin(ang) * r1);
      c.lineTo(cx + Math.cos(ang) * r2, cy + Math.sin(ang) * r2);
    }
    // cruz central curta
    c.moveTo(cx - R * 0.08, cy); c.lineTo(cx + R * 0.08, cy);
    c.moveTo(cx, cy - R * 0.08); c.lineTo(cx, cy + R * 0.08);
    c.stroke();
    c.globalAlpha = 1;
  };

  Nucleo.prototype.quadro = function (agora, suave) {
    var t = (agora - this.inicio) / 1000;
    this.nivel += (this.nivelAlvo - this.nivel) * 0.25;
    var c = this.ctx, cx = this.l / 2, cy = this.a / 2;
    c.clearRect(0, 0, this.l, this.a);
    this.desenharMoldura();

    var alvo = { x: 0, y: 0, a: 0 };
    var tam = 1.6 * this.dpr;
    var k = suave ? 0.09 : 1;
    c.fillStyle = this.estado === "erro" ? this.corErro : this.cor;
    for (var i = 0; i < N; i++) {
      this.alvo(i, t, alvo);
      var p = this.particulas[i];
      p.x += (alvo.x - p.x) * k;
      p.y += (alvo.y - p.y) * k;
      p.a += (alvo.a - p.a) * k;
      if (p.a < 0.02) continue;
      c.globalAlpha = p.a;
      c.fillRect(cx + p.x - tam / 2, cy + p.y - tam / 2, tam, tam);
    }
    c.globalAlpha = 1;
  };

  Nucleo.prototype.iniciar = function () {
    var self = this;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    if (this.parado.matches) { this.desenharSeParado(); return; }
    function laco(agora) {
      self.quadro(agora, true);
      self.raf = requestAnimationFrame(laco);
    }
    this.raf = requestAnimationFrame(laco);
  };

  // Com movimento reduzido: desenha a forma final do estado, sem animar.
  Nucleo.prototype.desenharSeParado = function () {
    if (!this.parado.matches) return;
    this.nivel = 0;
    this.quadro(this.inicio, false);
  };

  window.Nucleo = Nucleo;
})();
