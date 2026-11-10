import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .util import caminho_modelo_rosto


def criar_detector():
    # Le o modelo como bytes para funcionar mesmo com acentos no nome da pasta.
    with open(caminho_modelo_rosto(), "rb") as f:
        modelo = f.read()
    opcoes = vision.FaceDetectorOptions(
        base_options=mp_python.BaseOptions(model_asset_buffer=modelo),
        running_mode=vision.RunningMode.IMAGE,
    )
    return vision.FaceDetector.create_from_options(opcoes)


def achar_rosto(detector, quadro_bgr):
    """Devolve (centro_x, centro_y, largura, altura) do maior rosto, ou None."""
    rgb = cv2.cvtColor(quadro_bgr, cv2.COLOR_BGR2RGB)
    imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    resultado = detector.detect(imagem)
    if not resultado.detections:
        return None
    maior = max(
        resultado.detections,
        key=lambda d: d.bounding_box.width * d.bounding_box.height,
    )
    c = maior.bounding_box
    return (c.origin_x + c.width / 2, c.origin_y + c.height / 2, c.width, c.height)
