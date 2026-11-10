# Cortes Virais

Programa para Windows que transforma um video longo (podcast, live, aula) em cortes
prontos para TikTok, Instagram Reels, YouTube Shorts e Facebook.

## O que ele faz

1. **Transcreve** o audio (Whisper, roda no seu computador).
2. **Escolhe os melhores momentos** com a IA que voce preferir: na nuvem, local ou pelo modo gratuito (veja abaixo).
3. **Corta** cada trecho e **reenquadra** no formato escolhido, seguindo o rosto de quem fala.
4. **Legendas animadas** (opcional, desligadas por padrao).
5. Salva tudo numa pasta, com um `resumo.txt` explicando cada corte.

Formatos: **9:16** (TikTok, Reels, Shorts, Facebook Reels), **4:5** (feed) e **1:1** (quadrado).

## Qual IA usar para escolher os momentos

No painel de ajustes, em **Como escolher os momentos**:

| Opcao | Para que serve |
|---|---|
| **Modo gratuito (sem IA)** | Regras do proprio programa. Nao precisa de internet nem de chave. |
| **Claude (Anthropic)** | Cole a chave da API. |
| **Nuvem: OpenAI e compativeis** | OpenAI, Google Gemini, Groq, OpenRouter, DeepSeek, Mistral ou qualquer servico compativel com a API da OpenAI (escolha "Outro" e digite o endereco). |
| **IA local** | Ollama, LM Studio, llama.cpp/llamafile ou qualquer servidor local compativel. Tudo fica no seu computador. |

- Use o botao **Testar conexao** para conferir o endereco, a chave e ver os modelos disponiveis.
- Com IA na nuvem, o **texto da transcricao** e enviado ao servico escolhido. Com IA local, nada sai do computador.
- IA local: abra o programa (por exemplo o Ollama, com `ollama pull llama3.1`) e ligue o servidor antes de gerar.
- Se a IA falhar, o programa avisa e continua pelo modo gratuito.
- Os nomes de modelo mudam com o tempo. Confira o nome atual no site do servico e edite o campo **Modelo**.

## Gerar o instalador pelo GitHub

1. Crie um repositorio no GitHub e envie todos estes arquivos (incluindo a pasta `.github`).
2. Abra a aba **Actions**, escolha **Gerar instalador do Windows** e clique em **Run workflow**.
3. Espere terminar (de 15 a 40 minutos na primeira vez).
4. Clique na execucao concluida e baixe **CortesVirais-Instalador** em *Artifacts*.
5. Descompacte o `.zip` e execute `CortesVirais-Setup.exe`.

Para publicar na aba **Releases**, crie uma tag, por exemplo `v1.0.0`.

## Rodar sem instalar (para testar)

```
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Observacoes

- Na primeira vez, o programa baixa o modelo de voz (cerca de 500 MB). Depois funciona offline,
  exceto as IAs de nuvem, que precisam de internet e de chave de API (geralmente custam centavos por video).
- O modo gratuito de escolha de momentos funciona melhor em portugues.
- Se houver mais de uma pessoa na tela, o enquadramento segue o maior rosto.
- Se algo der erro, os detalhes ficam em `%LOCALAPPDATA%\CortesVirais\erro.log`.
- As chaves de API preenchidas ficam salvas, sem criptografia, em `%LOCALAPPDATA%\CortesVirais\config.json`.

## Estrutura

```
main.py                  ponto de partida
cortes/ui.py             interface (CustomTkinter)
cortes/pipeline.py       junta todas as etapas
cortes/transcricao.py    Whisper
cortes/momentos.py       escolha dos melhores momentos
cortes/ia.py             conversa com IAs da nuvem e locais
cortes/rosto.py          deteccao de rosto (MediaPipe)
cortes/reenquadrar.py    recorte vertical seguindo o rosto
cortes/legendas.py       legendas animadas
cortes/util.py           caminhos, FFmpeg, configuracao
installer.iss            receita do instalador (Inno Setup)
.github/workflows/       build automatico no GitHub
```
