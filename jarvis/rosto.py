"""Verificação facial local para a tela de bloqueio do JARVIS.

O módulo é opcional: o aplicativo continua iniciando mesmo sem OpenCV, sem os
modelos ou sem uma câmera. A inscrição guarda apenas um vetor normalizado do
rosto em ``dados/rosto.json``; imagens da câmera nunca são gravadas.

Isto é uma conveniência pós-login com webcam RGB. A prova de presença usa um
pequeno movimento lateral da cabeça e não substitui o Windows Hello.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np


RAIZ = (Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1])
_BASE_MODELOS = (RAIZ / "modelos" if (RAIZ / "modelos").is_dir()
                 else RAIZ / "_internal" / "modelos")
PASTA_MODELOS = _BASE_MODELOS / "rosto"
ARQUIVO_PERFIL = RAIZ / "dados" / "rosto.json"
MODELO_DETECCAO = PASTA_MODELOS / "face_detection_yunet_2023mar.onnx"
MODELO_RECONHECIMENTO = PASTA_MODELOS / "face_recognition_sface_2021dec.onnx"


class RostoIndisponivel(RuntimeError):
    """OpenCV, modelos ou câmera não estão disponíveis."""


@dataclass
class ResultadoRosto:
    reconhecido: bool
    nome: str = ""
    pontuacao: float = 0.0
    prova_vida: bool = False
    motivo: str = ""


def _normalizar(vetor):
    vetor = np.asarray(vetor, dtype=np.float32).reshape(-1)
    norma = float(np.linalg.norm(vetor))
    if norma <= 1e-8:
        raise ValueError("vetor facial vazio")
    return vetor / norma


class AutenticadorFacial:
    """Detecção YuNet + embedding SFace, ambos executados localmente."""

    def __init__(self, camera=0, limiar=0.363, exigir_prova_vida=True,
                 nome="usuario", arquivo_perfil=ARQUIVO_PERFIL,
                 tempo_desafio_s=8.0):
        self.camera = camera
        self.limiar = float(limiar)
        self.exigir_prova_vida = bool(exigir_prova_vida)
        self.nome = str(nome or "usuario")
        self.arquivo_perfil = Path(arquivo_perfil)
        self.tempo_desafio_s = max(2.0, float(tempo_desafio_s))
        self._detector = None
        self._reconhecedor = None
        self._dimensao = None
        self.ultimo_status = "aguardando câmera"
        self.ultimo_resultado = ResultadoRosto(False, motivo="ainda não testado")

    @property
    def modelos_prontos(self):
        return MODELO_DETECCAO.is_file() and MODELO_RECONHECIMENTO.is_file()

    @property
    def perfil_configurado(self):
        try:
            dados = json.loads(self.arquivo_perfil.read_text(encoding="utf-8"))
            return bool(dados.get("embedding") and dados.get("nome"))
        except (OSError, ValueError, TypeError):
            return False

    def diagnostico(self):
        return {
            "ativado": True,
            "modelos": self.modelos_prontos,
            "perfil": self.perfil_configurado,
            "camera": self.camera,
            "limiar": self.limiar,
            "prova_vida": self.exigir_prova_vida,
            "status": self.ultimo_status,
            "ultimo": {
                "reconhecido": self.ultimo_resultado.reconhecido,
                "nome": self.ultimo_resultado.nome,
                "pontuacao": round(self.ultimo_resultado.pontuacao, 4),
                "prova_vida": self.ultimo_resultado.prova_vida,
                "motivo": self.ultimo_resultado.motivo,
            },
        }

    def _carregar_modelos(self):
        if not self.modelos_prontos:
            raise RostoIndisponivel(
                "modelos faciais ausentes; execute preparar_reconhecimento_facial.ps1"
            )
        if self._detector is not None:
            return
        try:
            import cv2
            self._detector = cv2.FaceDetectorYN_create(
                str(MODELO_DETECCAO), "", (320, 320), 0.7, 0.3, 500
            )
            self._reconhecedor = cv2.FaceRecognizerSF_create(
                str(MODELO_RECONHECIMENTO), ""
            )
        except Exception as exc:
            raise RostoIndisponivel(f"OpenCV facial indisponível: {exc}") from exc

    def _abrir_camera(self):
        try:
            import cv2
            captura = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW)
            if not captura.isOpened():
                captura.release()
                captura = cv2.VideoCapture(self.camera)
            if not captura.isOpened():
                raise RostoIndisponivel("não foi possível abrir a câmera")
            captura.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            captura.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return captura
        except RostoIndisponivel:
            raise
        except Exception as exc:
            raise RostoIndisponivel(f"câmera indisponível: {exc}") from exc

    def _detectar(self, frame):
        altura, largura = frame.shape[:2]
        dimensao = (largura, altura)
        if dimensao != self._dimensao:
            self._detector.setInputSize(dimensao)
            self._dimensao = dimensao
        _, rostos = self._detector.detect(frame)
        if rostos is None or len(rostos) == 0:
            return None
        # A maior face é a que está diante do operador; rostos ao fundo não
        # devem decidir a liberação do overlay.
        return max(rostos, key=lambda f: float(f[2] * f[3]))

    def _caracteristica(self, frame, rosto):
        alinhado = self._reconhecedor.alignCrop(frame, rosto)
        return _normalizar(self._reconhecedor.feature(alinhado))

    def _ler_perfil(self):
        try:
            dados = json.loads(self.arquivo_perfil.read_text(encoding="utf-8"))
            return str(dados["nome"]), _normalizar(dados["embedding"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RostoIndisponivel("perfil facial ainda não cadastrado") from exc

    def cadastrar(self, quantidade=12, tempo_max_s=20.0, ao_status: Callable[[str], None] | None = None):
        """Cadastra um vetor médio a partir de várias imagens ao vivo."""
        self._carregar_modelos()
        captura = self._abrir_camera()
        vetores = []
        inicio = time.monotonic()
        try:
            while len(vetores) < quantidade and time.monotonic() - inicio < tempo_max_s:
                ok, frame = captura.read()
                if not ok:
                    continue
                rosto = self._detectar(frame)
                if rosto is None or float(rosto[14]) < 0.75:
                    self._notificar("olhando para a câmera", ao_status)
                    continue
                vetores.append(self._caracteristica(frame, rosto))
                self._notificar(f"captura {len(vetores)}/{quantidade}", ao_status)
                time.sleep(0.08)
        finally:
            captura.release()
        if len(vetores) < max(5, quantidade // 2):
            raise RostoIndisponivel(
                f"poucas capturas válidas ({len(vetores)}); melhore luz e enquadramento"
            )
        vetor = _normalizar(np.mean(np.stack(vetores), axis=0))
        dados = {
            "versao": 1,
            "nome": self.nome,
            "embedding": [round(float(x), 8) for x in vetor],
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "observacao": "vetor local; nenhuma imagem foi armazenada",
        }
        self.arquivo_perfil.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo_perfil.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        self.ultimo_status = "perfil cadastrado"
        return dados

    def verificar(self, tempo_max_s=None, ao_status: Callable[[str], None] | None = None):
        """Procura o operador durante uma janela curta e retorna o resultado."""
        nome, perfil = self._ler_perfil()
        self._carregar_modelos()
        captura = self._abrir_camera()
        inicio = time.monotonic()
        scores = []
        posicoes = []
        limite = float(tempo_max_s or self.tempo_desafio_s)
        try:
            while time.monotonic() - inicio < limite:
                ok, frame = captura.read()
                if not ok:
                    continue
                rosto = self._detectar(frame)
                if rosto is None or float(rosto[14]) < 0.75:
                    self._notificar("aguardando rosto", ao_status)
                    continue
                feature = self._caracteristica(frame, rosto)
                score = self._comparar(feature, perfil)
                scores.append(score)
                # O nariz (índices 8/9 do YuNet) dá um sinal simples de giro.
                centro = max(0.0, min(1.0, float((rosto[8] - rosto[0]) / max(1.0, rosto[2]))))
                posicoes.append(centro)
                self._notificar(f"rosto {score:.2f}", ao_status)
                if len(scores) >= 5 and sum(s >= self.limiar for s in scores[-5:]) >= 5:
                    vida = (max(posicoes) - min(posicoes) >= 0.12) if self.exigir_prova_vida else True
                    if vida:
                        resultado = ResultadoRosto(True, nome, float(np.mean(scores[-5:])), True)
                        self.ultimo_resultado = resultado
                        self.ultimo_status = "identificação visual confirmada"
                        return resultado
                time.sleep(0.04)
        finally:
            captura.release()
        resultado = ResultadoRosto(False, nome, max(scores or [0.0]), False, "rosto não confirmado")
        self.ultimo_resultado = resultado
        self.ultimo_status = resultado.motivo
        return resultado

    @staticmethod
    def _comparar(esquerda, direita):
        return float(np.dot(_normalizar(esquerda), _normalizar(direita)))

    @staticmethod
    def _notificar(texto, callback):
        if callback:
            try:
                callback(texto)
            except Exception:
                pass


class MonitorFacial:
    """Thread de tentativas curtas enquanto o overlay está bloqueado."""

    def __init__(self, autenticador: AutenticadorFacial, bloqueada: Callable[[], bool],
                 ao_reconhecer: Callable[[ResultadoRosto], None]):
        self.autenticador = autenticador
        self.bloqueada = bloqueada
        self.ao_reconhecer = ao_reconhecer
        self.parar_evento = threading.Event()
        self.thread = None

    def iniciar(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._rodar, name="reconhecimento-facial", daemon=True)
        self.thread.start()

    def parar(self):
        self.parar_evento.set()

    def _rodar(self):
        while not self.parar_evento.is_set():
            if not self.bloqueada():
                self.parar_evento.wait(0.5)
                continue
            try:
                resultado = self.autenticador.verificar()
                if resultado.reconhecido:
                    self.ao_reconhecer(resultado)
                    return
            except RostoIndisponivel as exc:
                self.autenticador.ultimo_status = str(exc)
                self.parar_evento.wait(2.0)
            except Exception as exc:
                self.autenticador.ultimo_status = f"falha facial: {exc}"
                self.parar_evento.wait(2.0)
            self.parar_evento.wait(0.5)
