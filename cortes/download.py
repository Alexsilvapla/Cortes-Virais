"""Baixa videos de links (YouTube, Instagram, TikTok, Facebook, X e muitos outros) com o yt-dlp."""
import glob
import os
import re
import shutil

from .util import pasta_base, pasta_ffmpeg

NAVEGADORES = {
    "Sem login": None,
    "Firefox": "firefox",
    "Chrome": "chrome",
    "Edge": "edge",
    "Brave": "brave",
}


def _preparar_deno():
    """O YouTube exige um 'motor de JavaScript' (Deno). Se ele veio junto do programa,
    coloca a pasta dele no PATH para o yt-dlp achar."""
    for pasta in (os.path.join(pasta_base(), "assets"), pasta_base()):
        for nome in ("deno.exe", "deno"):
            if os.path.exists(os.path.join(pasta, nome)):
                os.environ["PATH"] = pasta + os.pathsep + os.environ.get("PATH", "")
                return True
    return shutil.which("deno") is not None


def _traduzir_erro(texto, navegador):
    texto = re.sub(r"\x1b\[[0-9;]*m", "", texto)
    baixo = texto.lower()
    if "unsupported url" in baixo:
        return "Esse link nao e de um video que o programa consiga baixar."
    if "sign in to confirm" in baixo or "not a bot" in baixo:
        return ("O YouTube pediu confirmacao de que voce nao e um robo. Escolha seu navegador em "
                "'Entrar com' (fique logado nele) e tente de novo.")
    if ("login required" in baixo or "log in" in baixo or "rate-limit" in baixo
            or "cookies" in baixo or "private" in baixo or "authentication" in baixo):
        dica = ("" if navegador else " Escolha seu navegador em 'Entrar com' (fique logado nele).")
        return "Esse video exige login ou esta privado/limitado." + dica
    if "could not copy" in baixo and "cookie" in baixo:
        return "Nao consegui ler os cookies do navegador. Feche o navegador e tente de novo, ou teste o Firefox."
    if "unavailable" in baixo or "removed" in baixo:
        return "Esse video nao esta disponivel."
    if "ffmpeg" in baixo:
        return "Faltou o FFmpeg para juntar video e audio: " + texto[-200:]
    return "Nao consegui baixar o video: " + texto.strip()[-300:]


def baixar_video(url, pasta, navegador=None, progresso=None):
    """Devolve o caminho do arquivo baixado."""
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("O componente de download (yt-dlp) nao esta instalado.")

    os.makedirs(pasta, exist_ok=True)
    _preparar_deno()

    def gancho(d):
        if not progresso:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progresso(min(d.get("downloaded_bytes", 0) / total, 1.0))
        elif d.get("status") == "finished":
            progresso(1.0)

    opcoes = {
        # Prefere H.264 (abre em qualquer lugar), ate 1080p.
        "format": (
            "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080][vcodec^=avc1]"
            "/bv*[height<=1080]+ba/b[height<=1080]/b"
        ),
        "merge_output_format": "mp4/mkv",
        "outtmpl": os.path.join(pasta, "%(title).80s [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [gancho],
        "ffmpeg_location": pasta_ffmpeg(),
        "retries": 3,
    }
    if navegador:
        opcoes["cookiesfrombrowser"] = (navegador,)

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and info.get("entries"):
                entradas = [e for e in info["entries"] if e]
                if not entradas:
                    raise RuntimeError("Nao encontrei nenhum video nesse link.")
                info = entradas[0]
            caminho = None
            baixados = info.get("requested_downloads") or []
            if baixados:
                caminho = baixados[0].get("filepath")
            if not caminho or not os.path.exists(caminho):
                base = os.path.splitext(ydl.prepare_filename(info))[0]
                achados = glob.glob(glob.escape(base) + ".*")
                caminho = achados[0] if achados else None
    except yt_dlp.utils.DownloadError as erro:
        raise RuntimeError(_traduzir_erro(str(erro), navegador))

    if not caminho or not os.path.exists(caminho):
        raise RuntimeError("O download terminou, mas nao achei o arquivo do video.")
    return caminho
