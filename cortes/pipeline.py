import os
import re
import shutil
import tempfile

import cv2

from .legendas import agrupar_palavras
from .momentos import escolher_momentos
from .reenquadrar import reenquadrar_clipe
from .rosto import criar_detector
from .transcricao import transcrever
from .util import rodar_ffmpeg


def _limpar_nome(texto):
    limpo = re.sub(r"[^\w\- ]", "", texto, flags=re.UNICODE).strip().replace(" ", "_")
    return limpo[:40] or "corte"


def _duracao_do_video(caminho):
    video = cv2.VideoCapture(caminho)
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    quadros = video.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    video.release()
    return quadros / fps


def gerar_cortes(cfg, log, progresso):
    """Roda tudo: transcreve, escolhe momentos, corta, reenquadra e (opcional) legenda.

    cfg: video, pasta_saida, formato, legendas, quantidade, dur_min, dur_max,
         idioma, ia, modelo_whisper
    log(texto) e progresso(fracao_0_a_1, texto) sao funcoes de aviso para a tela.
    Devolve a pasta onde os cortes foram salvos.
    """
    video = cfg["video"]
    base = os.path.splitext(os.path.basename(video))[0]
    pasta = os.path.join(cfg["pasta_saida"], _limpar_nome(base) + "_cortes")
    os.makedirs(pasta, exist_ok=True)

    duracao_total = _duracao_do_video(video)
    if duracao_total <= 0:
        raise RuntimeError("Nao consegui ler esse video.")

    # 1) Transcricao (0% a 35%)
    log("Transcrevendo o audio. Na primeira vez o programa baixa o modelo de voz (cerca de 500 MB).")
    segmentos, palavras = transcrever(
        video, cfg.get("idioma"), cfg.get("modelo_whisper", "small"),
        progresso=lambda f: progresso(0.35 * f, "Transcrevendo o audio..."),
    )
    log(f"Transcricao pronta: {len(segmentos)} trechos de fala.")

    # 2) Escolha dos momentos (35% a 40%)
    progresso(0.36, "Escolhendo os melhores momentos...")
    momentos = escolher_momentos(
        segmentos, duracao_total, cfg["quantidade"], cfg["dur_min"], cfg["dur_max"],
        ia=cfg.get("ia"), log=log,
    )
    log(f"{len(momentos)} momentos escolhidos.")
    progresso(0.40, "Preparando os cortes...")

    detector = criar_detector()
    resumo = []
    formato_nome = cfg["formato"].replace(":", "x")

    for n, m in enumerate(momentos, 1):
        inicio_barra = 0.40 + 0.60 * (n - 1) / len(momentos)
        fatia = 0.60 / len(momentos)

        def avisar(f, texto, _i=inicio_barra, _f=fatia, _n=n):
            progresso(_i + _f * f, f"Corte {_n} de {len(momentos)}: {texto}")

        ini, fim = m["inicio"], m["fim"]
        log(f"Corte {n}: {ini:.0f}s a {fim:.0f}s - {m['titulo']}")
        tmp = tempfile.mkdtemp(prefix="cortes_")
        try:
            trecho = os.path.join(tmp, "trecho.mp4")
            mudo = os.path.join(tmp, "mudo.mp4")
            saida = os.path.join(
                pasta, f"corte{n:02d}_{formato_nome}_{_limpar_nome(m['titulo'])}.mp4"
            )

            avisar(0.0, "recortando o trecho")
            rodar_ffmpeg([
                "-ss", f"{ini:.2f}", "-i", video, "-t", f"{fim - ini:.2f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", trecho,
            ])
            avisar(0.1, "seguindo o rosto")

            blocos = None
            if cfg.get("legendas"):
                do_corte = [
                    (t, a - ini, b - ini) for (t, a, b) in palavras
                    if a >= ini - 0.1 and b <= fim + 0.1
                ]
                blocos = agrupar_palavras(do_corte) or None

            reenquadrar_clipe(
                trecho, mudo, cfg["formato"], blocos_legenda=blocos, detector=detector,
                progresso=lambda f: avisar(0.1 + 0.8 * f, "seguindo o rosto"),
            )

            avisar(0.9, "juntando o audio")
            rodar_ffmpeg([
                "-i", mudo, "-i", trecho, "-map", "0:v", "-map", "1:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", "-shortest", saida,
            ])
            avisar(1.0, "pronto")
            resumo.append(
                f"Corte {n:02d}: {ini:.0f}s a {fim:.0f}s | {m['titulo']}\n"
                f"  Arquivo: {os.path.basename(saida)}\n"
                f"  Motivo: {m['motivo']}\n"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    with open(os.path.join(pasta, "resumo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(resumo))
    progresso(1.0, "Tudo pronto!")
    log("Tudo pronto! Os cortes estao na pasta de saida.")
    return pasta
