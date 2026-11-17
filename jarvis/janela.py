"""Janelas do JARVIS (pywebview / Edge WebView2).

Comportamento pedido: em repouso ela fica na tela secundária; quando o
usuário chama "Jarvis", ela vem para a tela de chamada (a principal, por
padrão). "Muda de tela" / "chega pra lá" leva para o outro monitor.

O modo de bloqueio pós-login é um bloqueio de interface do aplicativo. Ele
cria uma janela sem moldura em cada monitor e deixa a janela normal escondida
até a frase local de liberação ser reconhecida. Não tenta substituir o secure
desktop do Windows nem instala um gancho global de teclado.
"""
import re
import threading
import unicodedata

NOMES_TELA = {"primeira": 0, "segunda": 1}


def normalizar_frase(texto):
    """Normaliza uma frase curta para comparação local, sem IA."""
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-zA-Z0-9]+", " ", texto.lower())
    return " ".join(texto.split())


class Janela:
    def __init__(self, config):
        self.tela_chamada = config.get("tela_chamada", 0)
        self.tela_repouso = config.get("tela_repouso", 1)
        bloqueio = config.get("bloqueio_pos_login", {}) or {}
        # A frase não é senha: é apenas um comando local fixo para sair do
        # overlay. Nenhuma credencial do Windows fica aqui.
        self.bloqueio_ativo = bool(bloqueio.get("ativar", False))
        self.frase_liberar = normalizar_frase(
            bloqueio.get("frase_liberar", "liberar tela")
        ) or "liberar tela"
        self.exigir_voz_conhecida = bool(bloqueio.get("exigir_voz_conhecida", False))
        self.vozes_permitidas = {
            normalizar_frase(nome)
            for nome in (bloqueio.get("vozes_permitidas", []) or [])
            if normalizar_frase(nome)
        }
        self.bloqueada = self.bloqueio_ativo
        self.janela = None
        self.janelas_bloqueio = []
        self.atual = None
        self.minimizada = False
        self.trava = threading.Lock()

    @staticmethod
    def _gui(janela, operacao, *args):
        """Chama o backend diretamente, sem esperar ``events.shown``.

        A janela normal é criada escondida enquanto o overlay cobre os
        monitores. A API pública de pywebview (`show`, `destroy`, `move`...)
        espera o evento ``shown`` e pode bloquear por 20 segundos nesse caso.
        O backend já encaminha essas operações para a thread gráfica; usá-lo
        diretamente permite liberar o overlay sem travar a rota HTTP.
        """
        gui = getattr(janela, "gui", None)
        uid = getattr(janela, "uid", None)
        if gui is None or uid is None:
            return False
        try:
            if operacao in {"show", "destroy_window", "restore", "minimize"}:
                getattr(gui, operacao)(uid)
            elif operacao == "move":
                getattr(gui, operacao)(args[0], args[1], uid)
            elif operacao == "resize":
                from webview.window import FixPoint
                getattr(gui, operacao)(args[0], args[1], uid,
                                       FixPoint.NORTH | FixPoint.WEST)
            else:
                return False
            return True
        except Exception:
            return False

    # ---- criação (thread principal) -------------------------------------------

    def criar(self, url, ocultar=False):
        import webview
        self.janela = webview.create_window(
            "J.A.R.V.I.S.", url, frameless=True, easy_drag=False,
            background_color="#06080a", text_select=True, hidden=ocultar,
        )
        return self.janela

    def criar_bloqueio(self, url):
        """Cria uma janela de bloqueio para cada monitor disponível.

        O pywebview só deve posicionar uma janela depois do evento ``shown``;
        por isso o ajuste é registrado antes de iniciar o loop gráfico.
        """
        import webview

        self.bloqueada = True
        telas = self.telas()
        self.janelas_bloqueio = []

        def posicionar(janela, tela):
            try:
                janela.move(tela.x, tela.y)
                janela.resize(tela.width, tela.height)
                janela.on_top = True
            except Exception:
                # A janela continua utilizável mesmo se um driver rejeitar a
                # mudança de geometria; o Windows segue tendo a recuperação.
                pass

        if not telas:
            # Fallback raro: o backend ainda não publicou os monitores.
            self.janelas_bloqueio.append(webview.create_window(
                "J.A.R.V.I.S. — bloqueado", url, frameless=True,
                easy_drag=False, resizable=False, on_top=True,
                background_color="#06080a", text_select=False,
                zoomable=False, draggable=False,
            ))
            return self.janelas_bloqueio

        for numero, tela in enumerate(telas):
            janela = webview.create_window(
                "J.A.R.V.I.S. — bloqueado", url,
                x=tela.x, y=tela.y, width=tela.width, height=tela.height,
                frameless=True, easy_drag=False, resizable=False,
                on_top=True, focus=numero == 0, background_color="#06080a",
                text_select=False, zoomable=False, draggable=False,
            )
            janela.events.shown += lambda j=janela, t=tela: posicionar(j, t)
            self.janelas_bloqueio.append(janela)
        return self.janelas_bloqueio

    def telas(self):
        import webview
        # Principal primeiro: é a que o Windows põe em (0, 0).
        return sorted(webview.screens, key=lambda s: (s.x != 0 or s.y != 0, s.x, s.y))

    def frase_de_liberacao_confere(self, frase):
        """Compara somente a frase local configurada; não consulta o cérebro."""
        return normalizar_frase(frase) == self.frase_liberar

    def voz_de_liberacao_confere(self, falante):
        """Exige uma voz cadastrada quando o modo seguro estiver configurado.

        A impressão de voz é uma conveniência local, não autenticação forte;
        o código local continua sendo a recuperação quando ela falhar.
        """
        if not self.exigir_voz_conhecida:
            return True
        nome = normalizar_frase(falante)
        if not nome:
            return False
        return not self.vozes_permitidas or nome in self.vozes_permitidas

    def desbloquear(self):
        """Marca a sessão como liberada sem bloquear a thread HTTP.

        Os overlays são janelas nativas criadas pelo pywebview. Fechá-los a
        partir da thread do FastAPI pode esperar indefinidamente pelo evento
        ``shown`` quando há mais de um monitor. A própria página de bloqueio
        acompanha este estado e navega para ``/`` assim que ele muda; assim a
        mesma janela vira o painel funcional imediatamente.
        """
        with self.trava:
            if not self.bloqueada:
                return False
            self.janelas_bloqueio = []
            self.bloqueada = False
        return True

    # ---- movimentos (podem vir de qualquer thread) -----------------------------

    def ir_para(self, indice):
        if not self.janela:
            return None
        telas = self.telas()
        if not telas:
            return None
        indice = indice % len(telas)
        t = telas[indice]
        with self.trava:
            self._gui(self.janela, "restore")
            self._gui(self.janela, "move", t.x, t.y)
            self._gui(self.janela, "resize", t.width, t.height)
            self.atual = indice
            self.minimizada = False
        return indice

    def minimizar(self):
        """Minimiza somente a janela do JARVIS, sem suspender o Windows."""
        if not self.janela:
            return False
        with self.trava:
            ok = self._gui(self.janela, "minimize")
            if ok:
                self.minimizada = True
            return ok

    def restaurar(self):
        """Restaura a janela sem forçar foco ou mudar de monitor."""
        if not self.janela:
            return False
        with self.trava:
            ok = self._gui(self.janela, "restore")
            if ok:
                self.minimizada = False
            return ok

    def chamar(self):
        indice = self.ir_para(self.tela_chamada)
        if self.janela:
            # on_top liga e desliga: só para a janela furar a fila e vir para frente.
            self.janela.on_top = True
            self.janela.on_top = False
        return indice

    def repousar(self):
        if self.atual != self.tela_repouso:
            return self.ir_para(self.tela_repouso)
        return self.atual

    def mudar(self, qual):
        """qual: 'primeira', 'segunda' ou 'outra'. Devolve o número da tela (1 ou 2)."""
        if qual == "outra":
            destino = 1 - (self.atual or 0) if len(self.telas()) > 1 else 0
        else:
            destino = NOMES_TELA[qual]
        indice = self.ir_para(destino)
        if self.janela:
            self.janela.on_top = True
            self.janela.on_top = False
        return (indice or 0) + 1
