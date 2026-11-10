"""Conversa com qualquer IA: na nuvem (Claude, OpenAI, Gemini, Groq...) ou local
(Ollama, LM Studio, llama.cpp...). Usa so a biblioteca padrao do Python."""
import json
import re
import urllib.error
import urllib.request

# Rotulos mostrados na tela (chave interna -> texto)
TIPOS = {
    "gratis": "Modo gratuito (sem IA)",
    "anthropic": "Claude (Anthropic)",
    "nuvem": "Nuvem: OpenAI e compativeis",
    "local": "IA local (Ollama, LM Studio...)",
}

# Servicos prontos: nome -> (endereco, modelo sugerido).
# Os nomes de modelo mudam com o tempo: confira no site do servico e edite se precisar.
PRESETS_NUVEM = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Google Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "Groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "OpenRouter": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "DeepSeek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "Mistral": ("https://api.mistral.ai/v1", "mistral-small-latest"),
    "Outro (digitar o endereco)": ("", ""),
}
PRESETS_LOCAL = {
    "Ollama": ("http://localhost:11434/v1", "llama3.1"),
    "LM Studio": ("http://localhost:1234/v1", ""),
    "llama.cpp / llamafile": ("http://localhost:8080/v1", ""),
    "Outro (digitar o endereco)": ("", ""),
}

MODELO_CLAUDE_PADRAO = "claude-haiku-5-5"
URL_CLAUDE = "https://api.anthropic.com/v1"


class ErroIA(Exception):
    pass


class ErroConexao(ErroIA):
    """Nao deu para falar com o servidor (nao adianta tentar de novo)."""


def _chamar(url, corpo=None, cabecalhos=None, timeout=120, local=False):
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    cab = {"content-type": "application/json"}
    cab.update(cabecalhos or {})
    pedido = urllib.request.Request(url, data=dados, headers=cab)
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")[:300]
        raise ErroIA(f"erro {e.code}: {detalhe}")
    except urllib.error.URLError as e:
        if local:
            raise ErroConexao(
                f"nao consegui conectar em {url}. O programa da IA local "
                "(Ollama, LM Studio...) esta aberto e com o servidor ligado?"
            )
        raise ErroConexao(f"sem conexao com {url} ({e.reason})")
    except TimeoutError:
        raise ErroIA("a IA demorou demais para responder")


def _cab_anthropic(chave):
    return {"x-api-key": chave, "anthropic-version": "2023-06-01"}


def _cab_compativel(chave):
    return {"authorization": f"Bearer {chave}"} if chave else {}


def perguntar(ia, prompt):
    """ia: {"formato": "anthropic"|"openai", "url", "modelo", "chave", "local": bool}"""
    if ia["formato"] == "anthropic":
        dados = _chamar(
            URL_CLAUDE + "/messages",
            {
                "model": ia["modelo"] or MODELO_CLAUDE_PADRAO,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            _cab_anthropic(ia["chave"]),
            timeout=180,
        )
        texto = "".join(
            b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text"
        )
    else:
        local = bool(ia.get("local"))
        dados = _chamar(
            ia["url"].rstrip("/") + "/chat/completions",
            # So os campos basicos: funcionam em praticamente qualquer servico.
            {"model": ia["modelo"], "messages": [{"role": "user", "content": prompt}]},
            _cab_compativel(ia.get("chave", "")),
            timeout=900 if local else 180,
            local=local,
        )
        try:
            texto = dados["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ErroIA("resposta inesperada da IA")
    # Alguns modelos locais "pensam em voz alta" dentro de <think>...</think>
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()


def listar_modelos(ia):
    """Testa a conexao. Devolve a lista de modelos disponiveis."""
    if ia["formato"] == "anthropic":
        dados = _chamar(URL_CLAUDE + "/models", None, _cab_anthropic(ia["chave"]), timeout=30)
    else:
        dados = _chamar(
            ia["url"].rstrip("/") + "/models", None,
            _cab_compativel(ia.get("chave", "")), timeout=30, local=bool(ia.get("local")),
        )
    itens = dados.get("data") or dados.get("models") or []
    nomes = []
    for item in itens:
        nome = item.get("id") or item.get("name") if isinstance(item, dict) else None
        if nome:
            nomes.append(nome.replace("models/", ""))
    return nomes


def extrair_lista_json(texto):
    """Acha uma lista JSON na resposta, mesmo com texto extra ou cercas de codigo."""
    texto = re.sub(r"```(?:json)?", "", texto)
    candidatos = [texto]
    achado = re.search(r"\[.*\]", texto, re.S)
    if achado:
        candidatos.append(achado.group(0))
    achado = re.search(r"\{.*\}", texto, re.S)
    if achado:
        candidatos.append(achado.group(0))
    for c in candidatos:
        try:
            dados = json.loads(c)
        except ValueError:
            continue
        if isinstance(dados, list):
            return dados
        if isinstance(dados, dict):
            for v in dados.values():
                if isinstance(v, list):
                    return v
    raise ErroIA("a resposta da IA nao tinha uma lista de trechos")
