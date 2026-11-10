import json
import os
import shutil
import subprocess
import sys
import urllib.request

NOME_APP = "Cortes Virais"

PASTA_DADOS = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CortesVirais"
)
os.makedirs(PASTA_DADOS, exist_ok=True)
ARQ_CONFIG = os.path.join(PASTA_DADOS, "config.json")
ARQ_ERRO = os.path.join(PASTA_DADOS, "erro.log")

NOME_MODELO_ROSTO = "blaze_face_short_range.tflite"
URL_MODELO_ROSTO = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/" + NOME_MODELO_ROSTO
)


def pasta_base():
    """Pasta onde ficam os arquivos do programa (funciona instalado ou em desenvolvimento)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caminho_modelo_rosto():
    """Acha o modelo de rosto; se nao existir, baixa uma vez."""
    for pasta in (os.path.join(pasta_base(), "assets"), PASTA_DADOS):
        caminho = os.path.join(pasta, NOME_MODELO_ROSTO)
        if os.path.exists(caminho):
            return caminho
    destino = os.path.join(PASTA_DADOS, NOME_MODELO_ROSTO)
    urllib.request.urlretrieve(URL_MODELO_ROSTO, destino)
    return destino


def caminho_ffmpeg():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        achado = shutil.which("ffmpeg")
        if achado:
            return achado
    raise RuntimeError("FFmpeg nao encontrado.")


def rodar_ffmpeg(argumentos):
    comando = [caminho_ffmpeg(), "-y", "-loglevel", "error"] + argumentos
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    r = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if r.returncode != 0:
        raise RuntimeError("O FFmpeg falhou: " + r.stderr[-600:])


def carregar_config():
    try:
        with open(ARQ_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_config(dados):
    try:
        with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
