import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from jarvis.ferramentas import ErroFerramenta, criar_ferramentas_de_skills
from jarvis.skills import Skills

SKILL_BOA = '''
from jarvis.ferramentas import Ferramenta

def criar(contexto):
    async def oi():
        return "oi " + contexto["quem"]
    return [Ferramenta("oi", "diz oi", oi, resposta_pronta=True)]
'''

SKILL_QUEBRADA = '''
raise RuntimeError("faltou uma peça")
'''


def montar_pasta(definicoes):
    """definicoes: {nome: (meta_dict, codigo)}"""
    tmp = tempfile.TemporaryDirectory()
    raiz = Path(tmp.name)
    for nome, (meta, codigo) in definicoes.items():
        pasta = raiz / nome
        pasta.mkdir()
        (pasta / "skill.json").write_text(json.dumps(meta), encoding="utf-8")
        (pasta / "skill.py").write_text(codigo, encoding="utf-8")
    return tmp, raiz


class CarregadorTests(unittest.TestCase):
    def test_carrega_skill_ativa_e_passa_o_contexto(self):
        tmp, raiz = montar_pasta({"saudacao": ({"nome": "saudacao", "descricao": "d"}, SKILL_BOA)})
        s = Skills({"quem": "Usuario"}, pasta=raiz, estado={})
        self.assertEqual(asyncio.run(s.ferramentas()["oi"].funcao()), "oi Usuario")
        tmp.cleanup()

    def test_skill_desligada_nao_entrega_ferramenta(self):
        tmp, raiz = montar_pasta({"saudacao": ({"nome": "saudacao", "ativa": False}, SKILL_BOA)})
        s = Skills({"quem": "x"}, pasta=raiz, estado={})
        self.assertEqual(s.ferramentas(), {})
        tmp.cleanup()

    def test_skill_quebrada_se_desliga_sozinha_sem_derrubar_as_outras(self):
        tmp, raiz = montar_pasta({
            "ruim": ({"nome": "ruim"}, SKILL_QUEBRADA),
            "boa": ({"nome": "boa"}, SKILL_BOA),
        })
        s = Skills({"quem": "x"}, pasta=raiz, estado={})
        self.assertIn("oi", s.ferramentas(), "a skill boa tinha que continuar de pé")
        self.assertFalse(s.skills["ruim"].ativa)
        self.assertIn("faltou uma peça", s.skills["ruim"].erro)
        tmp.cleanup()

    def test_permissao_por_voz(self):
        tmp, raiz = montar_pasta({"so_dono": ({"nome": "so_dono", "permitido": ["Usuario"]}, SKILL_BOA)})
        s = Skills({"quem": "x"}, pasta=raiz, estado={})
        self.assertIn("oi", s.ferramentas("Usuario"))
        self.assertEqual(s.ferramentas("Maria"), {})
        self.assertEqual(s.ferramentas(None), {})
        tmp.cleanup()

    def test_ligar_e_desligar_por_nome_parcial(self):
        tmp, raiz = montar_pasta({"saudacao": ({"nome": "saudacao"}, SKILL_BOA)})
        estado = {}
        s = Skills({"quem": "x"}, pasta=raiz, estado=estado)
        s._salvar_estado = lambda *_: None
        self.assertEqual(s.ligar("saud", False), "saudacao")
        self.assertEqual(s.ferramentas(), {})
        self.assertIsNone(s.ligar("inexistente", True))
        tmp.cleanup()


class FerramentasDeSkillsTests(unittest.TestCase):
    def setUp(self):
        self.tmp, raiz = montar_pasta({"saudacao": ({"nome": "saudacao"}, SKILL_BOA)})
        self.skills = Skills({"quem": "x"}, pasta=raiz, estado={})
        self.f = {f.nome: f for f in criar_ferramentas_de_skills(self.skills)}

    def tearDown(self):
        self.tmp.cleanup()

    def test_listar_diz_o_estado(self):
        self.assertIn("saudacao (ligada)", asyncio.run(self.f["listar_skills"].funcao()))

    def test_ligar_skill_inexistente_explica(self):
        with self.assertRaises(ErroFerramenta):
            asyncio.run(self.f["ligar_skill"].funcao(skill="nao existe", ligar=True))


class ComandoLivreTests(unittest.TestCase):
    """A skill mais sensível: o que ela RECUSA importa mais que o que ela faz."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "skills" / "comando"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_comando_teste", ROOT / "skills" / "comando" / "skill.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_recusa_comandos_que_apagam_sem_volta(self):
        for c in ["del C:\\Windows", "format c:", "rmdir /s x", "shutdown /s /t 0",
                  "reg delete HKLM\\x", "diskpart"]:
            with self.assertRaises(ErroFerramenta, msg=c):
                self.mod.analisar(c)

    def test_recusa_destrutivo_escondido_dentro_do_powershell(self):
        with self.assertRaises(ErroFerramenta):
            self.mod.analisar("powershell -c rm -r C:\\JARVIS")

    def test_ponto_e_virgula_nao_vira_segundo_comando(self):
        programa, argumentos = self.mod.analisar("echo ola; del tudo")
        self.assertEqual(programa, "echo")
        self.assertIn("del", argumentos, "deve virar argumento literal, nunca outro comando")

    def test_deixa_passar_comando_comum(self):
        self.assertEqual(self.mod.analisar("ipconfig /all"), ("ipconfig", ["/all"]))

    def test_a_pergunta_de_confirmacao_mostra_o_comando(self):
        ferramenta = self.mod.criar({})[0]
        self.assertTrue(ferramenta.perigosa)
        self.assertIn("ipconfig", asyncio.run(ferramenta.perguntar({"comando": "ipconfig /all"})))


class ArquivosTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_arquivos_teste", ROOT / "skills" / "arquivos" / "skill.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_so_deixa_mexer_nas_pastas_pessoais(self):
        casa = Path.home()
        permitidas = [casa / "Documents"]
        self.assertIsNone(self.mod.dentro_do_permitido(r"C:\Windows\System32", permitidas))
        self.assertIsNone(self.mod.dentro_do_permitido(casa / "Documents" / ".." / ".." / "Windows", permitidas))

    def test_aceita_caminho_dentro_da_pasta_permitida(self):
        permitidas = [Path.home() / "Documents"]
        alvo = self.mod.dentro_do_permitido(Path.home() / "Documents" / "nota.txt", permitidas)
        self.assertIsNotNone(alvo)


class ProgramacaoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name) / "projetos"
        self.raiz.mkdir()
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_programacao_teste", ROOT / "skills" / "programacao" / "skill.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.f = {x.nome: x for x in self.mod.criar({"config": {
            "programacao": {"raiz": str(self.raiz)}}})}

    def tearDown(self):
        self.tmp.cleanup()

    def test_leitura_e_lista_ficam_na_raiz_do_projeto(self):
        (self.raiz / "main.py").write_text("print('ok')", encoding="utf-8")
        lista = asyncio.run(self.f["listar_projeto"].funcao())
        self.assertIn("main.py", lista)
        leitura = asyncio.run(self.f["ler_codigo"].funcao(caminho="main.py"))
        self.assertIn("print('ok')", leitura)

    def test_recusa_travessia_e_segredo(self):
        with self.assertRaises(ErroFerramenta):
            self.mod._arquivo(self.raiz, "../fora.py")
        with self.assertRaises(ErroFerramenta):
            self.mod._arquivo(self.raiz, ".env")

    def test_escrita_e_teste_exigem_confirmacao(self):
        criar = self.f["criar_codigo"]
        testar = self.f["testar_codigo"]
        self.assertTrue(criar.perigosa)
        self.assertTrue(testar.perigosa)
        self.assertIn("criar", asyncio.run(criar.perguntar({"caminho": "main.py"})))
        self.assertIn("unittest", asyncio.run(testar.perguntar({"modo": "unittest"})))

    def test_teste_de_sintaxe_python_e_falha_visivel(self):
        (self.raiz / "main.py").write_text("print('ok')", encoding="utf-8")
        resultado = asyncio.run(self.f["testar_codigo"].funcao(caminho="main.py", modo="sintaxe"))
        self.assertIn("sem saída", resultado.lower())
        (self.raiz / "ruim.py").write_text("def", encoding="utf-8")
        with self.assertRaises(ErroFerramenta):
            asyncio.run(self.f["testar_codigo"].funcao(caminho="ruim.py", modo="sintaxe"))


if __name__ == "__main__":
    unittest.main()


# Chaves que a API da Anthropic recusa num esquema com strict=true. Custou um
# JARVIS inteiro fora do ar (erro 400 em TODO pedido) por causa de minimum/maximum.
PROIBIDAS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
             "multipleOf", "minLength", "maxLength", "pattern", "format",
             "minItems", "maxItems", "uniqueItems", "default"}


def achar_proibidas(esquema, caminho=""):
    achadas = []
    if isinstance(esquema, dict):
        for chave, valor in esquema.items():
            if chave in PROIBIDAS:
                achadas.append(f"{caminho}.{chave}")
            achadas.extend(achar_proibidas(valor, f"{caminho}.{chave}"))
    elif isinstance(esquema, list):
        for i, item in enumerate(esquema):
            achadas.extend(achar_proibidas(item, f"{caminho}[{i}]"))
    return achadas


class EsquemaAceitoPelaAPITests(unittest.TestCase):
    """Valida localmente o que antes só a API recusava, já em produção."""

    def todas_as_ferramentas(self):
        from jarvis.config import carregar
        from jarvis.ferramentas import criar_ferramentas
        cfg = carregar()
        f = criar_ferramentas(cfg, None, abrir=lambda _: None)
        skills = Skills({"config": cfg, "placa": None, "janela": None,
                         "painel": None, "abrir": lambda _: None})
        f.update(skills.ferramentas())
        f.update({x.nome: x for x in criar_ferramentas_de_skills(skills)})
        return f

    def test_nenhum_esquema_usa_chave_que_a_api_recusa(self):
        problemas = []
        for nome, ferramenta in self.todas_as_ferramentas().items():
            for chave in achar_proibidas(ferramenta.esquema()):
                problemas.append(f"{nome}{chave}")
        self.assertEqual(problemas, [], "a API recusa estas chaves com strict=true")

    def test_todo_campo_obrigatorio_existe_nas_propriedades(self):
        for nome, ferramenta in self.todas_as_ferramentas().items():
            faltando = set(ferramenta.obrigatorios) - set(ferramenta.propriedades)
            self.assertEqual(faltando, set(), f"{nome} exige campo que não declarou")

    def test_toda_ferramenta_tem_descricao(self):
        for nome, ferramenta in self.todas_as_ferramentas().items():
            self.assertTrue(ferramenta.descricao.strip(), f"{nome} sem descrição")

    def test_nao_passa_do_limite_de_strict_da_api(self):
        from jarvis.cerebro import MAX_STRICT, montar_ferramentas_da_api
        lista = montar_ferramentas_da_api(self.todas_as_ferramentas())
        strict = [f["name"] for f in lista if f.get("strict")]
        self.assertLessEqual(len(strict), MAX_STRICT, "a API recusa o pedido inteiro acima disso")

    def test_acoes_perigosas_ficam_entre_as_strict(self):
        from jarvis.cerebro import montar_ferramentas_da_api
        ferramentas = self.todas_as_ferramentas()
        strict = {f["name"] for f in montar_ferramentas_da_api(ferramentas) if f.get("strict")}
        for nome, f in ferramentas.items():
            if f.perigosa and f.propriedades:
                self.assertIn(nome, strict, f"{nome} é perigosa e tem argumento")

    def test_toda_chamada_e_validada_mesmo_sem_strict(self):
        """strict é otimização; a garantia é validar() rodar sempre."""
        from jarvis.ferramentas import validar
        f = self.todas_as_ferramentas()["ajustar_volume"]
        self.assertIsNotNone(validar(f, {"nivel": 50, "extra": 1}))
        self.assertIsNotNone(validar(f, {}))


class GoogleTests(unittest.TestCase):
    """A skill do Google carrega sem credenciais e explica o que falta."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_google_teste", ROOT / "skills" / "google" / "skill.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.f = {x.nome: x for x in self.mod.criar({"abrir": lambda _: None})}

    def test_sem_token_a_ferramenta_diz_como_autorizar(self):
        self.mod.TOKEN = Path("nao_existe.json")
        with self.assertRaises(ErroFerramenta) as ctx:
            asyncio.run(self.f["ver_agenda"].funcao())
        self.assertIn("autoriza", str(ctx.exception).lower())

    def test_marcar_evento_pede_confirmacao_mostrando_o_que_vai_marcar(self):
        f = self.f["criar_evento"]
        self.assertTrue(f.perigosa)
        pergunta = asyncio.run(f.perguntar({"titulo": "dentista", "quando": "amanhã às 15h"}))
        self.assertIn("dentista", pergunta)
        self.assertIn("amanhã às 15h", pergunta)

    def test_nao_existe_ferramenta_que_apaga_no_google(self):
        for nome in self.f:
            for proibido in ("apagar", "deletar", "remover", "excluir"):
                self.assertNotIn(proibido, nome)

    def test_entende_horario_falado(self):
        from datetime import datetime
        quarta = datetime(2026, 10, 21, 10, 0)   # uma quarta-feira
        self.assertEqual(self.mod.interpretar_quando("amanhã às 15h", quarta),
                         datetime(2026, 10, 22, 15, 0))
        self.assertEqual(self.mod.interpretar_quando("hoje 9:30", quarta),
                         datetime(2026, 10, 21, 9, 30))
        self.assertEqual(self.mod.interpretar_quando("sexta às 8h", quarta),
                         datetime(2026, 10, 23, 8, 0))

    def test_horario_sem_hora_ou_impossivel_e_recusado(self):
        for ruim in ["qualquer dia desses", "amanhã às 99h"]:
            with self.assertRaises(ErroFerramenta, msg=ruim):
                self.mod.interpretar_quando(ruim)

    def test_fala_a_data_em_palavras(self):
        from datetime import datetime
        agora = datetime(2026, 10, 21, 10, 0)
        self.assertEqual(self.mod.quando_em_palavras("2026-10-21T14:00:00", agora), "hoje às 14h")
        self.assertEqual(self.mod.quando_em_palavras("2026-10-22T09:30:00", agora), "amanhã às 9h30")
        self.assertEqual(self.mod.quando_em_palavras("2026-11-15", agora), "15 de novembro")

    def test_aspas_no_nome_nao_quebram_a_busca_do_drive(self):
        # O nome entra numa consulta do Drive; uma aspa solta mudaria a consulta.
        nome = "relatório d'água"
        seguro = nome.replace("\\", "\\\\").replace("'", "\'")
        self.assertEqual(seguro, "relatório d\'água")


class ProgramasTests(unittest.TestCase):
    """winget: o que ele RECUSA e como monta a pergunta importam mais que instalar."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "skill_programas_teste", ROOT / "skills" / "programas" / "skill.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.f = {x.nome: x for x in self.mod.criar({})}

    # saída real do winget desta máquina, em português
    TABELA = (
        "Nome             ID           Versão\n"
        "------------------------------------\n"
        "VLC media player VideoLAN.VLC 3.0.24\n"
    )
    TABELA_EN = (
        "Name             Id           Version  Source\n"
        "---------------------------------------------\n"
        "VLC media player VideoLAN.VLC 3.0.24   winget\n"
    )

    def test_le_a_tabela_em_portugues_e_em_ingles(self):
        for tabela in (self.TABELA, self.TABELA_EN):
            itens = self.mod.ler_tabela(tabela)
            self.assertEqual(itens[0]["nome"], "VLC media player")
            self.assertEqual(itens[0]["id"], "VideoLAN.VLC")
            self.assertEqual(itens[0]["versao"], "3.0.24")

    def test_saida_sem_tabela_nao_quebra(self):
        self.assertEqual(self.mod.ler_tabela("Nenhum pacote encontrado."), [])

    def test_identificador_estranho_e_recusado_antes_do_winget(self):
        for ruim in ["VLC; del C:\\", "--source msstore", "../../etc", "", "a b"]:
            self.assertIsNone(self.mod.ID_VALIDO.match(ruim), ruim)
        self.assertIsNotNone(self.mod.ID_VALIDO.match("VideoLAN.VLC"))

    def test_instalar_e_perigosa_e_a_pergunta_diz_o_nome_do_programa(self):
        f = self.f["instalar_programa"]
        self.assertTrue(f.perigosa)

        async def catalogo_falso(procurado):
            return {"nome": "VLC media player", "id": procurado, "versao": "3.0.24"}
        self.mod.achar_pacote = catalogo_falso
        pergunta = asyncio.run(f.perguntar({"programa": "VideoLAN.VLC"}))
        self.assertIn("VLC media player", pergunta)
        self.assertIn("3.0.24", pergunta)

    def test_nome_com_caractere_estranho_e_recusado(self):
        import asyncio as aio
        for ruim in ["VLC; del C:", "VLC && formatar", "VLC`whoami`"]:
            with self.assertRaises(ErroFerramenta, msg=ruim):
                aio.run(self.mod.achar_pacote(ruim))

    def test_busca_nao_encerra_o_turno(self):
        """Ela existe para o modelo AGIR no resultado; se encerrasse, "instala o
        VLC" pararia na lista. Foi exatamente o que aconteceu no teste real."""
        self.assertFalse(self.f["procurar_programa"].resposta_pronta)

    def test_nao_existe_desinstalar_por_voz(self):
        for nome in self.f:
            self.assertNotIn("desinstalar", nome)
            self.assertNotIn("remover", nome)

    def test_so_usa_o_catalogo_oficial(self):
        fonte = (ROOT / "skills" / "programas" / "skill.py").read_text(encoding="utf-8")
        self.assertNotIn('"msstore"', fonte, "nunca instalar de fonte que não seja o catálogo winget")
        # toda chamada ao winget trava a fonte; se alguém somar uma sem travar,
        # este número para de bater e o teste reclama.
        chamadas = fonte.count("_winget(")  - 1   # menos a própria definição
        self.assertEqual(fonte.count('"--source", "winget"'), chamadas,
                         "toda chamada ao winget tem que travar --source winget")

    def test_ja_instalado_nao_vira_falha(self):
        """winget devolve erro quando o programa já está lá; isso não é falha.
        Aconteceu de verdade ao reinstalar o VLC."""
        chamadas = []

        async def winget_falso(args, tempo):
            chamadas.append(args[0])
            if args[0] == "install":
                return 2316632107, "Nenhuma versão de pacote mais recente está disponível."
            if args[0] == "list":
                return 0, self.TABELA
            return 0, self.TABELA
        self.mod._winget = winget_falso
        f = {x.nome: x for x in self.mod.criar({})}
        resposta = asyncio.run(f["instalar_programa"].funcao(programa="VideoLAN.VLC"))
        self.assertIn("já estava instalado", resposta)
        self.assertIn("list", chamadas, "tinha que conferir o estado real")

    def test_falha_de_verdade_continua_sendo_falha(self):
        async def winget_falso(args, tempo):
            if args[0] == "install":
                return 1, "Falha ao baixar o instalador."
            if args[0] == "list":
                return 0, "Nenhum pacote instalado foi encontrado."
            return 0, self.TABELA
        self.mod._winget = winget_falso
        f = {x.nome: x for x in self.mod.criar({})}
        with self.assertRaises(ErroFerramenta):
            asyncio.run(f["instalar_programa"].funcao(programa="VideoLAN.VLC"))
