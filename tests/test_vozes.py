import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from jarvis.agente import Agente, extrair_nome
from jarvis.locutores import Locutores
from jarvis.ouvinte import DetectorEco
from test_agente import CerebroFalso, PlacaFalsa, Passo, montar, rodar


class ExtratorFalso:
    """Faz da 'voz' o primeiro valor do áudio: dois falantes = dois vetores."""
    def create_stream(self):
        class S:
            def accept_waveform(self, sr, a): self.a = a
            def input_finished(self): pass
        return S()

    def compute(self, s):
        base = np.zeros(8, dtype=np.float32)
        base[int(round(float(s.a[0]) * 10)) % 8] = 1.0
        return base


def voz(id_falante):
    return np.full(16000, id_falante / 10, dtype=np.float32)


class DetectorEcoTests(unittest.TestCase):
    def rodar(self, det, mic_rms, ref_rms, blocos):
        for i in range(blocos):
            det.registrar_referencia(ref_rms, t=i * 0.032)
            if det.processar(mic_rms, True):
                return i
        return None

    def test_eco_proporcional_ao_que_toca_nao_interrompe(self):
        det = DetectorEco(ganho=0.13)
        self.assertIsNone(self.rodar(det, mic_rms=0.013, ref_rms=0.1, blocos=200))

    def test_voz_muito_acima_do_eco_interrompe_rapido(self):
        det = DetectorEco(ganho=0.13)
        self.assertLessEqual(self.rodar(det, mic_rms=0.05, ref_rms=0.1, blocos=50), 8)

    def test_ruido_curto_nao_interrompe(self):
        det = DetectorEco(ganho=0.13)
        for i in range(3):
            det.registrar_referencia(0.1, t=i * 0.032)
            self.assertFalse(det.processar(0.08, True))
        for i in range(3, 40):
            det.registrar_referencia(0.1, t=i * 0.032)
            self.assertFalse(det.processar(0.013, True))

    def test_aprende_o_ganho_do_quarto(self):
        det = DetectorEco(ganho=0.15)
        self.rodar(det, mic_rms=0.04, ref_rms=0.2, blocos=60)  # eco real = 0,2 da referência
        self.assertAlmostEqual(det.ganho, 0.2, delta=0.02)

    def test_sem_nada_tocando_so_fala_acima_do_piso_conta(self):
        det = DetectorEco()
        self.assertFalse(any(det.processar(0.002, True) for _ in range(50)))


class LocutoresTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.arq = Path(self.pasta.name) / "vozes.json"
        self.loc = Locutores(arquivo=self.arq, extrator=ExtratorFalso())

    def tearDown(self):
        self.pasta.cleanup()

    def test_cadastra_e_reconhece_cada_pessoa(self):
        self.loc.cadastrar("Usuario", [voz(1), voz(1)])
        self.loc.cadastrar("Maria", [voz(2), voz(2)])
        self.assertEqual(self.loc.identificar(voz(1))[0], "Usuario")
        self.assertEqual(self.loc.identificar(voz(2))[0], "Maria")

    def test_voz_desconhecida_nao_vira_ninguem(self):
        self.loc.cadastrar("Usuario", [voz(1)])
        self.assertIsNone(self.loc.identificar(voz(5))[0])

    def test_persiste_so_impressoes_e_esquece_sob_pedido(self):
        self.loc.cadastrar("Usuario", [voz(1)])
        dados = json.loads(self.arq.read_text(encoding="utf-8"))
        self.assertEqual(list(dados), ["Usuario"])
        self.assertEqual(len(dados["Usuario"]), 8, "só o vetor da voz, nenhum áudio")
        self.assertEqual(Locutores(arquivo=self.arq, extrator=ExtratorFalso()).nomes(), ["Usuario"])
        self.assertTrue(self.loc.esquecer("Usuario"))
        self.assertEqual(Locutores(arquivo=self.arq, extrator=ExtratorFalso()).nomes(), [])


class NomeTests(unittest.TestCase):
    def test_extrai_o_nome_da_frase(self):
        for frase, nome in [("Meu nome é Usuario", "Usuario"), ("eu sou a Maria Clara.", "Maria Clara"),
                            ("Me chamo João", "João"), ("Pedro", "Pedro")]:
            self.assertEqual(extrair_nome(frase), nome)


class ConversaTests(unittest.TestCase):
    def preparar(self, passos, conversa_s=30):
        agente, cerebro, painel, *_ = montar(passos)
        agente.conversa_s = conversa_s
        return agente, cerebro, painel

    def ouvir(self, agente, *eventos):
        async def tudo():
            for e in eventos:
                texto, falante = e if isinstance(e, tuple) else (e, None)
                await agente.ao_ouvir(texto, None, falante)
                if agente.tarefa:
                    await agente.tarefa
        asyncio.run(tudo())

    def test_depois_do_primeiro_jarvis_o_mic_segue_valendo(self):
        agente, cerebro, painel = self.preparar([Passo(texto="Uma."), Passo(texto="Duas.")])
        self.ouvir(agente, "Jarvis, primeira pergunta", "e a segunda pergunta?")
        self.assertEqual([h for h in cerebro.historico if h[0] == "user"],
                         [("user", "primeira pergunta"), ("user", "e a segunda pergunta?")])

    def test_conversa_fecha_depois_do_silencio(self):
        agente, cerebro, _ = self.preparar([Passo(texto="Uma.")], conversa_s=0.01)
        self.ouvir(agente, "Jarvis, primeira pergunta")
        import time; time.sleep(0.05)
        self.ouvir(agente, "isso aqui já não é comigo")
        self.assertEqual(len([h for h in cerebro.historico if h[0] == "user"]), 1)

    def test_obrigado_encerra_a_conversa(self):
        agente, cerebro, _ = self.preparar([Passo(texto="Uma.")])
        self.ouvir(agente, "Jarvis, primeira pergunta", "obrigado", "conversa de sala")
        self.assertEqual(len([h for h in cerebro.historico if h[0] == "user"]), 1)

    def test_outra_pessoa_conhecida_nao_continua_a_conversa_de_quem_chamou(self):
        agente, cerebro, _ = self.preparar([Passo(texto="Oi, Usuario.")])
        self.ouvir(agente, ("Jarvis, oi", "Usuario"), ("e aí, tudo bem?", "Maria"))
        self.assertEqual(len([h for h in cerebro.historico if h[0] == "user"]), 1)

    def test_o_modelo_recebe_o_nome_de_quem_falou(self):
        agente, cerebro, _ = self.preparar([Passo(texto="Oi.")])
        self.ouvir(agente, ("Jarvis, oi", "Usuario"))
        self.assertEqual(cerebro.historico[0], ("user", "[Usuario] oi"))

    def test_interrupcao_para_a_fala_e_mantem_a_conversa(self):
        agente, _, painel = self.preparar([])
        parou = []
        agente.voz = type("V", (), {"parar": lambda s: parou.append(1)})()
        agente._interrompido()
        self.assertEqual(parou, [1])
        self.assertTrue(agente.conversa_ativa())


class CadastroPorVozTests(unittest.TestCase):
    def test_fluxo_de_cadastro_completo(self):
        pasta = tempfile.TemporaryDirectory()
        agente, cerebro, painel, *_ = montar([])
        agente.locutores = Locutores(arquivo=Path(pasta.name) / "v.json", extrator=ExtratorFalso())
        agente.ouvinte = object()
        respostas = []
        agente._responder = lambda t, **k: _guardar(respostas, t)

        async def ouvir(texto, audio):
            await agente.ao_ouvir(texto, audio, None)
            if agente.tarefa:
                await agente.tarefa

        async def tudo():
            await ouvir("Jarvis, aprende a minha voz", None)
            await ouvir("Meu nome é Usuario", voz(1))
            for _ in range(3):
                await ouvir("uma frase qualquer para treinar", voz(1))
        asyncio.run(tudo())
        self.assertIn("Qual é o seu nome?", respostas[0])
        self.assertEqual(agente.locutores.nomes(), ["Usuario"])
        self.assertIn("reconheço a sua voz", respostas[-1])
        self.assertEqual(painel.vozes, ["Usuario"])
        pasta.cleanup()


async def _guardar(lista, texto):
    lista.append(texto)


if __name__ == "__main__":
    unittest.main()


from jarvis.fala import bip
from jarvis.narrador import Narrador, cortar_frases


class CortarFrasesTests(unittest.TestCase):
    def test_entrega_frase_completa_e_guarda_o_resto(self):
        prontas, resto = cortar_frases("Bom dia, senhor. Os sistemas estão no ar. Ainda fal")
        self.assertEqual(prontas, ["Bom dia, senhor.", "Os sistemas estão no ar."])
        self.assertEqual(resto, "Ainda fal")

    def test_nao_corta_numero_com_ponto(self):
        prontas, resto = cortar_frases("A média foi de 28.5 graus hoje")
        self.assertEqual(prontas, [])
        self.assertEqual(resto, "A média foi de 28.5 graus hoje")

    def test_frase_curta_sai_junto_com_a_proxima_para_nao_soar_picada(self):
        prontas, _ = cortar_frases("Ok. Abri o navegador para o senhor. Mais texto vindo")
        self.assertEqual(prontas, ["Ok. Abri o navegador para o senhor."])

    def test_ultima_frase_espera_porque_pode_vir_mais_texto(self):
        prontas, resto = cortar_frases("Uma frase completa aqui. ")
        self.assertEqual(prontas, [])
        self.assertEqual(resto.strip(), "Uma frase completa aqui.")

    def test_forcar_entrega_o_que_sobrou_sem_pontuacao(self):
        prontas, resto = cortar_frases("Isso ainda não terminou", forcar=True)
        self.assertEqual((prontas, resto), (["Isso ainda não terminou"], ""))


class VozFalsa:
    sr = 22050

    def sintetizar(self, texto):
        return texto


class NarradorTests(unittest.TestCase):
    def montar(self):
        tocados = []

        async def tocar(audio):
            tocados.append(audio)
        return Narrador(VozFalsa(), tocar), tocados

    def test_fala_a_primeira_frase_antes_de_o_texto_terminar(self):
        narrador, tocados = self.montar()

        async def tudo():
            narrador.comecar()
            narrador.engolir("Primeira frase pronta. Segunda ain")
            await asyncio.sleep(0.05)
            parcial = list(tocados)
            narrador.engolir("da chegando aqui.")
            falado = await narrador.terminar()
            return parcial, falado
        parcial, falado = asyncio.run(tudo())
        self.assertEqual(parcial, ["Primeira frase pronta."])
        self.assertEqual(tocados, ["Primeira frase pronta.", "Segunda ainda chegando aqui."])
        self.assertEqual(falado, "Primeira frase pronta. Segunda ainda chegando aqui.")

    def test_interromper_descarta_o_que_faltava_falar(self):
        narrador, tocados = self.montar()

        async def tudo():
            narrador.comecar()
            narrador.engolir("Uma frase inteira aqui. Outra frase inteira aqui.")
            await asyncio.sleep(0.05)
            narrador.cancelar()
            await narrador.terminar()
        asyncio.run(tudo())
        self.assertLess(len(tocados), 2, "o resto da fala tinha que ser jogado fora")


class BipTests(unittest.TestCase):
    def test_bip_e_curto_demais_para_virar_interrupcao(self):
        som = bip(22050)
        self.assertLess(len(som) / 22050, 0.1, "o bip não pode parecer fala")
        self.assertLessEqual(float(np.abs(som).max()), 1.0)


from jarvis.ambiente import FiltroDeOrigem, alinhar, correlacao_maxima, envelope


class PCFalso:
    """Loopback de mentira: devolve o áudio que eu mandar, no tempo que pedir."""
    ligado = True

    def __init__(self, audio):
        self.audio = audio

    def trecho(self, inicio_s, duracao_s):
        return self.audio


class PCFalsoMultiplos:
    ligado = True

    def __init__(self, referencias):
        self.referencias = referencias

    def trechos(self, inicio_s, duracao_s):
        return self.referencias


def fala_sintetica(segundos, semente=1, sr=16000, silabas_por_s=4.5):
    """Ruído com envelope de fala: sobe e desce como sílabas.

    `silabas_por_s` importa: o filtro compara o RITMO, não o timbre. Duas
    falas com exatamente o mesmo ritmo pareceriam a mesma fonte — por isso
    cada voz do teste usa um ritmo diferente, como na vida real.
    """
    rng = np.random.default_rng(semente)
    t = np.arange(int(segundos * sr)) / sr
    silabas = (np.sin(2 * np.pi * silabas_por_s * t) * 0.5 + 0.5) ** 2
    return (rng.standard_normal(len(t)) * silabas * 0.1).astype(np.float32)


class EnvelopeTests(unittest.TestCase):
    def test_envelope_em_decibeis_acompanha_o_volume(self):
        alto = envelope(np.full(16000, 0.5, dtype=np.float32))
        baixo = envelope(np.full(16000, 0.05, dtype=np.float32))
        self.assertGreater(float(alto.mean()), float(baixo.mean()) + 15)

    def test_correlacao_acha_o_atraso(self):
        a = np.array([0, 0, 0, 5, 9, 4, 0, 0, 0, 0], dtype=np.float32)
        b = np.roll(a, -2)
        _, atraso = correlacao_maxima(a, b, 4)
        self.assertEqual(atraso, 2)

    def test_alinhar_deixa_os_dois_do_mesmo_tamanho(self):
        a, b = alinhar(np.arange(10.0), np.arange(8.0), 3)
        self.assertEqual(len(a), len(b))


class FiltroDeOrigemTests(unittest.TestCase):
    """O risco real é o INVERSO: ignorar o usuário. Por isso o filtro erra para
    o lado de deixar passar."""

    def test_o_que_o_pc_tocou_e_reconhecido(self):
        som = fala_sintetica(3.0)
        filtro = FiltroDeOrigem(PCFalso(som))
        self.assertTrue(filtro.veio_do_pc(som * 0.3, 0.0))

    def test_pessoa_falando_por_cima_nao_e_ignorada(self):
        filme = fala_sintetica(3.0, semente=1)
        pessoa = fala_sintetica(1.2, semente=99, silabas_por_s=6.5) * 3
        misturado = (filme * 0.3).copy()
        misturado[:len(pessoa)] += pessoa
        filtro = FiltroDeOrigem(PCFalso(filme))
        self.assertFalse(filtro.veio_do_pc(misturado, 0.0))

    def test_pc_em_silencio_nunca_explica_nada(self):
        filtro = FiltroDeOrigem(PCFalso(np.zeros(16000 * 3, dtype=np.float32)))
        self.assertFalse(filtro.veio_do_pc(fala_sintetica(2.0), 0.0))
        self.assertFalse(filtro.ultimo["pc_tocando"])

    def test_sem_loopback_o_filtro_nao_atrapalha(self):
        self.assertFalse(FiltroDeOrigem(None).veio_do_pc(fala_sintetica(2.0), 0.0))

    def test_som_sem_relacao_com_o_pc_passa(self):
        filtro = FiltroDeOrigem(PCFalso(fala_sintetica(3.0, semente=1, silabas_por_s=3.0)))
        self.assertFalse(filtro.veio_do_pc(fala_sintetica(3.0, semente=7, silabas_por_s=7.0), 0.0))

    def test_limite_conhecido_ritmo_igual_parece_a_mesma_fonte(self):
        """Documenta onde o filtro erra: mesmo ritmo, fontes diferentes.

        Não acontece com fala humana de verdade (ninguém fala no compasso exato
        de um filme), mas se um dia aparecer falso positivo, é por aqui.
        """
        filtro = FiltroDeOrigem(PCFalso(fala_sintetica(3.0, semente=1)))
        outro = fala_sintetica(3.0, semente=7)   # mesmo ritmo, ruído diferente
        self.assertTrue(filtro.veio_do_pc(outro, 0.0))

    def test_varias_saidas_usam_a_fonte_que_explica_o_microfone(self):
        notebook = fala_sintetica(3.0, semente=7, silabas_por_s=7.0)
        echo = fala_sintetica(3.0, semente=1)
        filtro = FiltroDeOrigem(PCFalsoMultiplos({"notebook": notebook, "echo": echo}))
        self.assertTrue(filtro.veio_do_pc(echo * 0.3, 0.0))
        self.assertIn("echo", filtro.ultimos)


class VozConhecidaTests(unittest.TestCase):
    def preparar(self, exigir):
        agente, cerebro, painel, *_ = montar([Passo(texto="ok"), Passo(texto="ok de novo")])
        agente.exigir_voz_conhecida = exigir
        agente.locutores = type("L", (), {"nomes": lambda s: ["Usuario"]})()
        return agente, cerebro

    def ouvir(self, agente, *eventos):
        async def tudo():
            for texto, falante in eventos:
                await agente.ao_ouvir(texto, None, falante)
                if agente.tarefa:
                    await agente.tarefa
        asyncio.run(tudo())

    def test_voz_desconhecida_na_conversa_aberta_e_ignorada(self):
        agente, cerebro = self.preparar(True)
        self.ouvir(agente, ("Jarvis, oi", "Usuario"), ("alguém na TV falando", None))
        self.assertEqual(len([h for h in cerebro.historico if h[0] == "user"]), 1)

    def test_desligado_o_comportamento_antigo_continua(self):
        agente, cerebro = self.preparar(False)
        self.ouvir(agente, ("Jarvis, oi", "Usuario"), ("continuando a conversa", None))
        self.assertEqual(len([h for h in cerebro.historico if h[0] == "user"]), 2)


class NarradorNaoVazaTests(unittest.TestCase):
    """"Task was destroyed but it is pending" aparecia no log a cada pedido que
    saía por um caminho sem passar por _responder."""

    def montar(self, passos):
        agente, cerebro, painel, *_ = montar(passos)
        agente.voz = type("V", (), {
            "sr": 22050, "sintetizar": lambda s, t: t, "parar": lambda s: None})()

        async def tocar(_audio):
            pass
        agente._tocar = tocar

        async def sem_espera(_s, _g):
            pass
        agente._niveis = sem_espera
        return agente

    def pedir(self, agente, texto):
        # processar() cria uma tarefa: precisa de um loop rodando.
        async def tudo():
            await agente.processar(texto)
        asyncio.run(tudo())

    def test_caminho_de_erro_fecha_o_narrador(self):
        agente = self.montar([Passo(problema="resposta vazia")])
        self.pedir(agente, "alguma coisa")
        self.assertIsNone(agente.narrador, "narrador ficou pendurado")

    def test_resposta_normal_tambem_fecha(self):
        agente = self.montar([Passo(texto="Tudo certo.")])
        self.pedir(agente, "me conta uma curiosidade")
        self.assertIsNone(agente.narrador)

    def test_pedido_novo_cancela_o_narrador_do_anterior(self):
        from jarvis.narrador import Narrador
        agente = self.montar([Passo(texto="ok")])

        async def tocar(_a):
            pass

        async def tudo():
            agente.narrador = Narrador(agente.voz, tocar)
            agente.narrador.comecar()
            antigo = agente.narrador
            agente._iniciar(asyncio.sleep(0))
            await agente.tarefa
            self.assertTrue(antigo.cancelado, "o narrador antigo tinha que ser cancelado")
            self.assertIsNone(agente.narrador)
        asyncio.run(tudo())


from jarvis.fala import engrossar
from jarvis.ouvinte import RMS_ALVO, normalizar, texto_repetitivo


class NormalizarTests(unittest.TestCase):
    """Nivelar pelo PICO não ajudava (14,1% de erro, igual a não fazer nada);
    pelo RMS caiu para 9,1% em fala comum."""

    def test_fala_baixa_e_fala_alta_saem_no_mesmo_nivel(self):
        baixa = fala_sintetica(2.0) * 0.05
        alta = fala_sintetica(2.0) * 2.0
        rms = lambda x: float(np.sqrt(np.mean(x ** 2)))
        self.assertAlmostEqual(rms(normalizar(baixa)), rms(normalizar(alta)), delta=0.01)

    def test_um_estalo_nao_manda_no_ganho_da_frase(self):
        """O problema do pico: um clique fazia a frase inteira ficar baixa."""
        fala = fala_sintetica(2.0) * 0.05
        com_estalo = fala.copy()
        com_estalo[1000] = 0.95
        rms = lambda x: float(np.sqrt(np.mean(x ** 2)))
        self.assertAlmostEqual(rms(normalizar(fala)), rms(normalizar(com_estalo)), delta=0.01)

    def test_silencio_nao_e_amplificado(self):
        silencio = np.zeros(16000, dtype=np.float32)
        self.assertLess(float(np.abs(normalizar(silencio)).max()), 1e-6)

    def test_nunca_estoura(self):
        self.assertLessEqual(float(np.abs(normalizar(fala_sintetica(1.0) * 50)).max()), 1.0)

    def test_chega_perto_do_alvo(self):
        """O alvo vale para a parte FALADA, não para a média com as pausas."""
        saida = normalizar(fala_sintetica(2.0) * 0.1)
        self.assertAlmostEqual(float(np.sqrt(np.mean(saida ** 2))), RMS_ALVO, delta=0.02)


class RepeticaoDaTranscricaoTests(unittest.TestCase):
    def test_detecta_hallucinacao_repetida(self):
        texto = "abrir o computador de notas " * 4
        self.assertTrue(texto_repetitivo(texto))

    def test_nao_rejeita_frase_normal(self):
        self.assertFalse(texto_repetitivo("Jarvis, abra o bloco de notas"))


class EngrossarTests(unittest.TestCase):
    def test_baixa_o_tom(self):
        sr = 22050
        t = np.arange(sr) / sr
        onda = np.sin(2 * np.pi * 200 * t).astype(np.float32)
        grave = engrossar(onda, sr, 0.88)

        def frequencia(x):
            espectro = np.abs(np.fft.rfft(x))
            return float(np.fft.rfftfreq(len(x), 1 / sr)[int(np.argmax(espectro))])
        self.assertLess(frequencia(grave), frequencia(onda) - 10)

    def test_fator_1_nao_mexe_em_nada(self):
        onda = fala_sintetica(1.0)
        self.assertIs(engrossar(onda, 16000, 1.0), onda)

    def test_fica_mais_longo_porque_o_tom_desceu(self):
        onda = fala_sintetica(1.0)
        self.assertGreater(len(engrossar(onda, 16000, 0.88)), len(onda))
