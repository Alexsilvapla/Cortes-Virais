import cv2

from .legendas import desenhar_legenda
from .rosto import achar_rosto, criar_detector

# formato: (largura, altura) de saida
FORMATOS = {
    "9:16": (1080, 1920),  # TikTok, Reels, Shorts, Facebook Reels
    "4:5": (1080, 1350),   # Feed do Instagram e do Facebook
    "1:1": (1080, 1080),   # Quadrado
}


def calcular_recorte(larg, alt, formato):
    saida_l, saida_a = FORMATOS[formato]
    proporcao = saida_l / saida_a
    if larg / alt > proporcao:
        return int(round(alt * proporcao)), alt
    return larg, int(round(larg / proporcao))


def posicao_recorte(cx, cy, cw, ch, larg, alt):
    x0 = int(round(cx - cw / 2))
    y0 = int(round(cy - ch / 2))
    x0 = max(0, min(x0, larg - cw))
    y0 = max(0, min(y0, alt - ch))
    return x0, y0


def reenquadrar_clipe(entrada, saida, formato, blocos_legenda=None,
                      suavizacao=0.1, detector=None, progresso=None):
    """Gera um video (sem audio) reenquadrado seguindo o rosto."""
    detector = detector or criar_detector()
    video = cv2.VideoCapture(entrada)
    fps = video.get(cv2.CAP_PROP_FPS) or 30.0
    larg = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    alt = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    cw, ch = calcular_recorte(larg, alt, formato)
    saida_l, saida_a = FORMATOS[formato]
    ampliando = cw < saida_l
    escritor = cv2.VideoWriter(
        saida, cv2.VideoWriter_fourcc(*"mp4v"), fps, (saida_l, saida_a)
    )

    cx, cy = larg / 2, alt / 2
    alvo_x, alvo_y = cx, cy
    n = 0
    while True:
        ok, quadro = video.read()
        if not ok:
            break

        if n % 2 == 0:
            rosto = achar_rosto(detector, quadro)
            if rosto:
                alvo_x, alvo_y = rosto[0], rosto[1]
        cx += (alvo_x - cx) * suavizacao
        cy += (alvo_y - cy) * suavizacao

        x0, y0 = posicao_recorte(cx, cy, cw, ch, larg, alt)
        recorte = quadro[y0:y0 + ch, x0:x0 + cw]
        recorte = cv2.resize(
            recorte, (saida_l, saida_a),
            interpolation=cv2.INTER_CUBIC if ampliando else cv2.INTER_AREA,
        )
        if blocos_legenda:
            recorte = desenhar_legenda(recorte, n / fps, blocos_legenda)
        escritor.write(recorte)

        n += 1
        if progresso and n % 15 == 0:
            progresso(min(n / total, 1.0))

    video.release()
    escritor.release()
    if progresso:
        progresso(1.0)
