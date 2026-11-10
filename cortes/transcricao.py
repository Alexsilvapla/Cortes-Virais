from faster_whisper import WhisperModel

_modelos = {}


def _carregar(nome):
    if nome not in _modelos:
        _modelos[nome] = WhisperModel(nome, device="cpu", compute_type="int8")
    return _modelos[nome]


def transcrever(caminho, idioma="pt", modelo="small", progresso=None):
    """Devolve (segmentos, palavras).

    segmentos: lista de {"inicio", "fim", "texto"}
    palavras:  lista de (texto, inicio, fim)
    """
    whisper = _carregar(modelo)
    trechos, info = whisper.transcribe(
        caminho, language=idioma, word_timestamps=True, vad_filter=True
    )
    duracao = info.duration or 0
    segmentos, palavras = [], []
    for t in trechos:
        segmentos.append({"inicio": t.start, "fim": t.end, "texto": t.text.strip()})
        for p in t.words or []:
            palavras.append((p.word.strip(), p.start, p.end))
        if progresso and duracao:
            progresso(min(t.end / duracao, 1.0))
    return segmentos, palavras
