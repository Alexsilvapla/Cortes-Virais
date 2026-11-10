import math

from .ia import ErroConexao, ErroIA, extrair_lista_json, perguntar

# Tamanho (em letras) de cada pedaco da transcricao enviado a IA.
# IA local tem memoria menor, entao recebe pedacos menores.
LIMITE_NUVEM = 60000
LIMITE_LOCAL = 5000

PALAVRAS_GANCHO = [
    "segredo", "erro", "nunca", "ninguem", "ninguém", "verdade", "dinheiro",
    "cuidado", "atencao", "atenção", "descobri", "incrivel", "incrível",
    "jamais", "pare", "melhor", "pior", "mentira", "problema", "resultado",
    "primeiro", "ultimo", "último", "motivo", "por que", "como", "cuidado",
]
COMECO_FRACO = ("e ", "mas ", "entao ", "então ", "porque ", "ou ", "que ", "ai ", "aí ")


def escolher_momentos(segmentos, duracao_total, quantidade, dur_min, dur_max,
                      ia=None, log=None):
    """ia: configuracao da IA (veja ia.perguntar) ou None para o modo gratuito."""
    log = log or (lambda m: None)
    momentos = []
    if segmentos and ia:
        try:
            log("A IA esta lendo a transcricao para escolher os melhores momentos...")
            momentos = _via_ia(
                segmentos, duracao_total, quantidade, dur_min, dur_max, ia, log
            )
        except Exception as erro:
            log(f"Nao deu para usar a IA ({erro}). Usando o modo gratuito.")
    if segmentos and not momentos:
        log("Escolhendo os momentos pelo modo gratuito...")
        momentos = _via_regras(segmentos, duracao_total, quantidade, dur_min, dur_max)
    if not momentos:
        log("Nao encontrei fala no video. Dividindo em partes iguais.")
        momentos = _partes_iguais(duracao_total, quantidade, dur_max)
    return momentos


# ---------------------------------------------------------------------- IA

def _linha(s):
    return f"[{s['inicio']:.1f}-{s['fim']:.1f}] {s['texto']}"


def _dividir(segmentos, limite):
    blocos, atual, tamanho = [], [], 0
    for s in segmentos:
        t = len(_linha(s)) + 1
        if atual and tamanho + t > limite:
            blocos.append(atual)
            atual, tamanho = [], 0
        atual.append(s)
        tamanho += t
    if atual:
        blocos.append(atual)
    return blocos


def _prompt(bloco, pedir, dur_min, dur_max):
    return (
        "Voce e um editor de videos virais para TikTok, Reels e Shorts. "
        "Abaixo esta um trecho da transcricao de um video, com tempos em segundos.\n"
        f"Escolha ate {pedir} melhores trechos para virar cortes. Regras:\n"
        f"- cada trecho deve ter entre {dur_min} e {dur_max} segundos;\n"
        "- comece em um gancho forte (pergunta, afirmacao forte, promessa ou inicio "
        "de historia) e termine quando a ideia estiver completa;\n"
        "- os trechos nao podem se sobrepor;\n"
        "- use tempos de inicio e fim que existam na transcricao;\n"
        "- de uma nota de 1 a 10 para o potencial de viralizar.\n"
        "Responda APENAS com JSON, sem nenhum texto antes ou depois, neste formato:\n"
        '[{"inicio": 12.3, "fim": 58.0, "titulo": "titulo curto", '
        '"motivo": "por que pode viralizar", "nota": 8}]\n\n'
        "TRANSCRICAO:\n" + "\n".join(_linha(s) for s in bloco)
    )


def _via_ia(segmentos, duracao_total, quantidade, dur_min, dur_max, ia, log):
    limite = LIMITE_LOCAL if ia.get("local") else LIMITE_NUVEM
    blocos = _dividir(segmentos, limite)
    if len(blocos) == 1:
        pedir = quantidade
    else:
        pedir = max(1, min(quantidade, math.ceil(quantidade * 2 / len(blocos))))

    candidatos, falhas, ultimo_erro = [], 0, None
    for i, bloco in enumerate(blocos, 1):
        if len(blocos) > 1:
            log(f"IA: lendo a parte {i} de {len(blocos)} da transcricao...")
        try:
            resposta = perguntar(ia, _prompt(bloco, pedir, dur_min, dur_max))
            lista = extrair_lista_json(resposta)
        except ErroConexao:
            raise
        except ErroIA as erro:
            falhas += 1
            ultimo_erro = erro
            log(f"IA: a parte {i} falhou ({erro}).")
            continue
        for item in lista:
            try:
                ini, fim = float(item["inicio"]), float(item["fim"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                nota = float(item.get("nota", 5))
            except (TypeError, ValueError):
                nota = 5.0
            candidatos.append({
                "inicio": ini, "fim": fim, "nota": nota,
                "titulo": str(item.get("titulo", "corte")),
                "motivo": str(item.get("motivo", "")),
            })

    if not candidatos:
        raise ErroIA(str(ultimo_erro) if ultimo_erro else "a IA nao devolveu trechos")
    candidatos.sort(key=lambda c: c["nota"], reverse=True)
    return _ajustar(candidatos, duracao_total, quantidade, dur_min, dur_max)


# ------------------------------------------------------------ Modo gratuito

def _termina_frase(texto):
    return texto.rstrip().endswith((".", "?", "!"))


def _pontuar(janela):
    texto = " ".join(s["texto"] for s in janela)
    minusculo = texto.lower()
    duracao = max(janela[-1]["fim"] - janela[0]["inicio"], 1.0)
    palavras = len(texto.split())

    pontos = palavras / duracao                      # fala densa = mais energia
    pontos += 2.0 * texto.count("?")
    pontos += 1.5 * texto.count("!")
    primeiros = " ".join(s["texto"].lower() for s in janela[:2])
    if "?" in primeiros:
        pontos += 3.0
    pontos += 3.0 * sum(1 for g in PALAVRAS_GANCHO if g in primeiros)
    pontos += 0.7 * sum(1 for g in PALAVRAS_GANCHO if g in minusculo)
    if janela[0]["texto"].lower().startswith(COMECO_FRACO):
        pontos -= 3.0
    if _termina_frase(janela[-1]["texto"]):
        pontos += 2.0
    return pontos


def _via_regras(segmentos, duracao_total, quantidade, dur_min, dur_max):
    candidatos = []
    n = len(segmentos)
    for i in range(n):
        inicio = segmentos[i]["inicio"]
        j = i
        while j < n - 1 and segmentos[j]["fim"] - inicio < dur_min:
            j += 1
        while (j < n - 1 and not _termina_frase(segmentos[j]["texto"])
               and segmentos[j + 1]["fim"] - inicio <= dur_max):
            j += 1
        duracao = segmentos[j]["fim"] - inicio
        if duracao < dur_min * 0.7 or duracao > dur_max * 1.1:
            continue
        janela = segmentos[i:j + 1]
        candidatos.append({
            "inicio": inicio,
            "fim": segmentos[j]["fim"],
            "pontos": _pontuar(janela),
            "titulo": " ".join(janela[0]["texto"].split()[:6]),
            "motivo": "Escolhido pelo modo gratuito (energia da fala, perguntas e palavras de gancho).",
        })

    candidatos.sort(key=lambda c: c["pontos"], reverse=True)
    escolhidos = []
    for c in candidatos:
        if all(c["fim"] <= e["inicio"] or c["inicio"] >= e["fim"] for e in escolhidos):
            escolhidos.append(c)
        if len(escolhidos) >= quantidade:
            break
    return _ajustar(escolhidos, duracao_total, quantidade, dur_min, dur_max)


# ------------------------------------------------------------------- Comum

def _ajustar(momentos, duracao_total, quantidade, dur_min, dur_max):
    """Corrige tempos, limita a duracao, remove sobreposicoes e ordena por tempo."""
    prontos = []
    for m in momentos:
        ini = max(0.0, min(m["inicio"], duracao_total))
        fim = max(0.0, min(m["fim"], duracao_total))
        if fim - ini > dur_max:
            fim = ini + dur_max
        if fim - ini < dur_min:
            fim = min(duracao_total, ini + dur_min)
            ini = max(0.0, fim - dur_min)
        if fim - ini < 3:
            continue
        prontos.append({
            "inicio": ini, "fim": fim,
            "titulo": m.get("titulo", "corte"), "motivo": m.get("motivo", ""),
        })

    escolhidos = []
    for m in prontos:
        if all(m["fim"] <= e["inicio"] or m["inicio"] >= e["fim"] for e in escolhidos):
            escolhidos.append(m)
        if len(escolhidos) >= quantidade:
            break
    escolhidos.sort(key=lambda m: m["inicio"])
    return escolhidos


def _partes_iguais(duracao_total, quantidade, dur_max):
    if duracao_total <= dur_max:
        return [{"inicio": 0.0, "fim": duracao_total,
                 "titulo": "video completo", "motivo": "Video curto."}]
    partes = []
    passo = dur_max
    inicio = 0.0
    while inicio + 3 < duracao_total and len(partes) < quantidade:
        partes.append({
            "inicio": inicio, "fim": min(inicio + passo, duracao_total),
            "titulo": f"parte {len(partes) + 1}", "motivo": "Divisao em partes iguais.",
        })
        inicio += passo
    return partes
