import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONTES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_cache = {}

BRANCO = (255, 255, 255)
AMARELO = (255, 214, 0)


def _fonte(tamanho):
    if tamanho not in _cache:
        fonte = None
        for caminho in _FONTES:
            if os.path.exists(caminho):
                fonte = ImageFont.truetype(caminho, tamanho)
                break
        _cache[tamanho] = fonte or ImageFont.load_default()
    return _cache[tamanho]


def agrupar_palavras(palavras, por_bloco=3):
    """palavras: lista de (texto, inicio, fim). Devolve lista de blocos."""
    return [palavras[i:i + por_bloco] for i in range(0, len(palavras), por_bloco)]


def _bloco_ativo(blocos, t):
    ativo = None
    for bloco in blocos:
        if bloco[0][1] - 0.05 <= t <= bloco[-1][2] + 0.25:
            ativo = bloco
    return ativo


def desenhar_legenda(quadro_bgr, t, blocos):
    bloco = _bloco_ativo(blocos, t)
    if bloco is None:
        return quadro_bgr

    altura, largura = quadro_bgr.shape[:2]
    imagem = Image.fromarray(cv2.cvtColor(quadro_bgr, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(imagem)
    textos = [p[0].upper() for p in bloco]

    tamanho = int(largura * 0.085)
    while True:
        fonte = _fonte(tamanho)
        espaco = d.textlength(" ", font=fonte)
        larguras = [d.textlength(tx, font=fonte) for tx in textos]
        total = sum(larguras) + espaco * (len(textos) - 1)
        if total <= largura * 0.9 or tamanho <= 20:
            break
        tamanho -= 4

    x = (largura - total) / 2
    y = int(altura * 0.70)
    contorno = max(4, tamanho // 12)
    for tx, w, p in zip(textos, larguras, bloco):
        ativa = p[1] <= t <= p[2] + 0.1
        d.text(
            (x, y), tx, font=fonte,
            fill=AMARELO if ativa else BRANCO,
            stroke_width=contorno, stroke_fill=(0, 0, 0),
        )
        x += w + espaco
    return cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR)
