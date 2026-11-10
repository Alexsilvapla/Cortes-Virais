import os
import queue
import threading
import traceback
from tkinter import filedialog

import customtkinter as ctk
import cv2
from PIL import Image

from . import ia as servico_ia
from .download import NAVEGADORES, baixar_video
from .pipeline import gerar_cortes
from .reenquadrar import calcular_recorte, posicao_recorte
from .rosto import achar_rosto, criar_detector
from .util import ARQ_ERRO, carregar_config, salvar_config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FUNDO = "#0e1014"
CARTAO = "#171a21"
CARTAO_2 = "#1f2430"
DESTAQUE = "#7c5cff"
DESTAQUE_HOVER = "#6a49f0"
SUAVE = "#9aa3b2"

DESCRICAO_FORMATO = {
    "9:16": "TikTok, Reels, Shorts e Facebook Reels",
    "4:5": "Feed do Instagram e do Facebook",
    "1:1": "Quadrado: feed e publicacoes",
}
DURACOES = {
    "Curtos (15 a 30 s)": (15, 30),
    "Medios (30 a 60 s)": (30, 60),
    "Longos (60 a 90 s)": (60, 90),
}
IDIOMAS = {"Portugues": "pt", "English": "en", "Espanol": "es", "Automatico": None}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cortes Virais")
        self.geometry("1200x740")
        self.minsize(1050, 660)
        self.configure(fg_color=FUNDO)

        self.salvo = carregar_config()
        self.video = None
        self.pasta_saida = self.salvo.get(
            "pasta_saida",
            os.path.join(os.path.expanduser("~"), "Videos", "CortesVirais"),
        )
        self.pasta_resultado = None
        self.fila = queue.Queue()
        self.quadro_preview = None
        self.rosto_preview = None
        self.trabalhando = False
        self.link_baixado = None  # (link, caminho)
        self.ia_salva = dict(self.salvo.get("ia", {}))
        if self.salvo.get("chave_api") and "anthropic" not in self.ia_salva:
            self.ia_salva["anthropic"] = {"chave": self.salvo["chave_api"]}
        self.tipo_atual = self.salvo.get("tipo_ia", "gratis")
        if self.tipo_atual not in servico_ia.TIPOS:
            self.tipo_atual = "gratis"

        self._montar()
        self.after(100, self._processar_fila)

    # ------------------------------------------------------------ Layout
    def _cartao(self, pai, **kw):
        return ctk.CTkFrame(pai, fg_color=CARTAO, corner_radius=18, **kw)

    def _montar(self):
        self.grid_columnconfigure(0, weight=3, uniform="c")
        self.grid_columnconfigure(1, weight=4, uniform="c")
        self.grid_columnconfigure(2, weight=3, uniform="c")
        self.grid_rowconfigure(1, weight=1)

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, columnspan=3, sticky="ew", padx=24, pady=(18, 8))
        ctk.CTkLabel(
            cab, text="Cortes Virais", font=ctk.CTkFont(size=26, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            cab, text="   Transforme videos longos em cortes prontos para postar",
            text_color=SUAVE, font=ctk.CTkFont(size=14),
        ).pack(side="left", pady=(6, 0))

        self._montar_esquerda()
        self._montar_centro()
        self._montar_direita()
        self._montar_rodape()

    def _montar_esquerda(self):
        c = self._cartao(self)
        c.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=8)
        ctk.CTkLabel(
            c, text="1. Escolha o video", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        zona = ctk.CTkScrollableFrame(c, fg_color=CARTAO_2, corner_radius=16)
        zona.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ctk.CTkLabel(zona, text="🎬", font=ctk.CTkFont(size=40)).pack(pady=(10, 4))
        self.lbl_arquivo = ctk.CTkLabel(
            zona, text="Nenhum video escolhido", text_color=SUAVE,
            wraplength=230, justify="center",
        )
        self.lbl_arquivo.pack(padx=12, pady=(0, 2))
        self.lbl_info = ctk.CTkLabel(zona, text="", text_color=SUAVE)
        self.lbl_info.pack(pady=(0, 10))
        ctk.CTkButton(
            zona, text="Escolher arquivo", height=42, corner_radius=12,
            fg_color=DESTAQUE, hover_color=DESTAQUE_HOVER,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._escolher_video,
        ).pack(padx=14, fill="x")

        ctk.CTkLabel(
            zona, text="ou cole o link do video", text_color=SUAVE
        ).pack(pady=(16, 4))
        self.entrada_link = ctk.CTkEntry(
            zona, placeholder_text="YouTube, Instagram, TikTok...", fg_color=CARTAO,
            border_width=0, height=38,
        )
        self.entrada_link.pack(padx=14, fill="x")
        ctk.CTkLabel(zona, text="Entrar com (se o video exigir login)", text_color=SUAVE,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=(10, 2))
        self.menu_cookies = ctk.CTkOptionMenu(
            zona, values=list(NAVEGADORES), fg_color=CARTAO, button_color=DESTAQUE,
            button_hover_color=DESTAQUE_HOVER,
        )
        self.menu_cookies.set(self.salvo.get("navegador", "Sem login"))
        self.menu_cookies.pack(padx=14, fill="x")
        self.btn_baixar = ctk.CTkButton(
            zona, text="Baixar do link", height=38, corner_radius=12, fg_color=CARTAO,
            hover_color="#2a3040", command=self._baixar,
        )
        self.btn_baixar.pack(padx=14, pady=(10, 4), fill="x")
        ctk.CTkLabel(
            zona,
            text="Use so videos seus ou com autorizacao. Para Instagram e videos "
                 "privados, fique logado no navegador escolhido e feche-o antes.",
            text_color=SUAVE, font=ctk.CTkFont(size=11), wraplength=230, justify="left",
        ).pack(anchor="w", padx=14, pady=(2, 10))

    def _montar_centro(self):
        c = self._cartao(self)
        c.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        ctk.CTkLabel(
            c, text="Pre-visualizacao do enquadramento",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 10))
        self.lbl_preview = ctk.CTkLabel(
            c, text="Escolha um video para ver\nonde o corte vai enquadrar o rosto",
            text_color=SUAVE, fg_color=CARTAO_2, corner_radius=16,
        )
        self.lbl_preview.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.lbl_preview.bind("<Configure>", lambda e: self._desenhar_preview())

    def _montar_direita(self):
        c = self._cartao(self)
        c.grid(row=1, column=2, sticky="nsew", padx=(8, 24), pady=8)
        ctk.CTkLabel(
            c, text="2. Ajustes", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 6))

        rolagem = ctk.CTkScrollableFrame(c, fg_color="transparent")
        rolagem.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        def titulo(texto):
            ctk.CTkLabel(rolagem, text=texto, text_color=SUAVE).pack(
                anchor="w", padx=12, pady=(10, 2)
            )

        titulo("Formato")
        self.seg_formato = ctk.CTkSegmentedButton(
            rolagem, values=["9:16", "4:5", "1:1"], command=self._trocar_formato,
            selected_color=DESTAQUE, selected_hover_color=DESTAQUE_HOVER,
        )
        self.seg_formato.set(self.salvo.get("formato", "9:16"))
        self.seg_formato.pack(fill="x", padx=12)
        self.lbl_formato = ctk.CTkLabel(rolagem, text="", text_color=SUAVE, font=ctk.CTkFont(size=12))
        self.lbl_formato.pack(anchor="w", padx=12, pady=(2, 0))

        titulo("Duracao dos cortes")
        self.menu_duracao = ctk.CTkOptionMenu(
            rolagem, values=list(DURACOES), fg_color=CARTAO_2, button_color=DESTAQUE,
            button_hover_color=DESTAQUE_HOVER,
        )
        self.menu_duracao.set(self.salvo.get("duracao", "Medios (30 a 60 s)"))
        self.menu_duracao.pack(fill="x", padx=12)

        self.lbl_qtd = ctk.CTkLabel(rolagem, text="", text_color=SUAVE)
        self.lbl_qtd.pack(anchor="w", padx=12, pady=(12, 2))
        self.slider_qtd = ctk.CTkSlider(
            rolagem, from_=1, to=10, number_of_steps=9, command=self._mudou_qtd,
            progress_color=DESTAQUE, button_color=DESTAQUE, button_hover_color=DESTAQUE_HOVER,
        )
        self.slider_qtd.set(self.salvo.get("quantidade", 3))
        self.slider_qtd.pack(fill="x", padx=12)
        self._mudou_qtd(self.slider_qtd.get())

        titulo("Idioma do video")
        self.menu_idioma = ctk.CTkOptionMenu(
            rolagem, values=list(IDIOMAS), fg_color=CARTAO_2, button_color=DESTAQUE,
            button_hover_color=DESTAQUE_HOVER,
        )
        self.menu_idioma.set(self.salvo.get("idioma", "Portugues"))
        self.menu_idioma.pack(fill="x", padx=12)

        self.sw_legendas = ctk.CTkSwitch(
            rolagem, text="Legendas animadas", progress_color=DESTAQUE
        )
        if self.salvo.get("legendas", False):
            self.sw_legendas.select()
        self.sw_legendas.pack(anchor="w", padx=12, pady=(16, 0))

        titulo("Como escolher os momentos")
        self.menu_ia = ctk.CTkOptionMenu(
            rolagem, values=list(servico_ia.TIPOS.values()), fg_color=CARTAO_2,
            button_color=DESTAQUE, button_hover_color=DESTAQUE_HOVER,
            command=self._trocar_ia,
        )
        self.menu_ia.set(servico_ia.TIPOS[self.tipo_atual])
        self.menu_ia.pack(fill="x", padx=12)

        self.quadro_ia = ctk.CTkFrame(rolagem, fg_color="transparent")
        self.quadro_ia.pack(fill="x", padx=0, pady=0)
        self.lbl_servico = ctk.CTkLabel(self.quadro_ia, text="Servico", text_color=SUAVE)
        self.menu_servico = ctk.CTkOptionMenu(
            self.quadro_ia, values=[""], fg_color=CARTAO_2, button_color=DESTAQUE,
            button_hover_color=DESTAQUE_HOVER, command=self._escolheu_servico,
        )
        self.lbl_url = ctk.CTkLabel(self.quadro_ia, text="Endereco da API", text_color=SUAVE)
        self.entrada_url = ctk.CTkEntry(self.quadro_ia, fg_color=CARTAO_2, border_width=0)
        self.lbl_modelo = ctk.CTkLabel(self.quadro_ia, text="Modelo", text_color=SUAVE)
        self.entrada_modelo = ctk.CTkEntry(self.quadro_ia, fg_color=CARTAO_2, border_width=0)
        self.lbl_chave = ctk.CTkLabel(self.quadro_ia, text="Chave da API", text_color=SUAVE)
        self.entrada_chave = ctk.CTkEntry(
            self.quadro_ia, show="•", fg_color=CARTAO_2, border_width=0,
        )
        self.btn_testar = ctk.CTkButton(
            self.quadro_ia, text="Testar conexao", fg_color=CARTAO_2, hover_color="#2a3040",
            command=self._testar_ia,
        )
        self.lbl_ia_msg = ctk.CTkLabel(
            self.quadro_ia, text="", text_color=SUAVE, font=ctk.CTkFont(size=12),
            wraplength=250, justify="left",
        )
        self.lbl_ia_dica = ctk.CTkLabel(
            rolagem, text="", text_color=SUAVE, font=ctk.CTkFont(size=12),
            wraplength=270, justify="left",
        )
        self.lbl_ia_dica.pack(anchor="w", padx=12, pady=(2, 0))
        self._montar_campos_ia(self.tipo_atual)

        titulo("Pasta de saida")
        self.btn_pasta = ctk.CTkButton(
            rolagem, text=self._nome_pasta(), fg_color=CARTAO_2, hover_color="#2a3040",
            command=self._escolher_pasta, anchor="w",
        )
        self.btn_pasta.pack(fill="x", padx=12, pady=(0, 10))

        self._trocar_formato(self.seg_formato.get())

    # ------------------------------------------------------------- IA
    def _tipo_ia(self):
        for chave, rotulo in servico_ia.TIPOS.items():
            if rotulo == self.menu_ia.get():
                return chave
        return "gratis"

    def _presets(self, tipo):
        return servico_ia.PRESETS_LOCAL if tipo == "local" else servico_ia.PRESETS_NUVEM

    def _guardar_campos(self):
        tipo = self.tipo_atual
        if tipo == "gratis":
            return
        dados = {
            "modelo": self.entrada_modelo.get().strip(),
            "chave": self.entrada_chave.get().strip(),
        }
        if tipo in ("nuvem", "local"):
            dados["servico"] = self.menu_servico.get()
            dados["url"] = self.entrada_url.get().strip()
        self.ia_salva[tipo] = dados

    def _montar_campos_ia(self, tipo):
        """Mostra so os campos que fazem sentido para o tipo de IA escolhido."""
        for w in (self.lbl_servico, self.menu_servico, self.lbl_url, self.entrada_url,
                  self.lbl_modelo, self.entrada_modelo, self.lbl_chave, self.entrada_chave,
                  self.btn_testar, self.lbl_ia_msg):
            w.pack_forget()
        self.lbl_ia_msg.configure(text="")
        if tipo == "gratis":
            self.lbl_ia_dica.configure(
                text="Escolhe pelas regras do programa (energia da fala, perguntas e "
                     "palavras de gancho). Nao precisa de internet nem de chave."
            )
            return

        dados = self.ia_salva.get(tipo, {})
        if tipo in ("nuvem", "local"):
            presets = self._presets(tipo)
            self.menu_servico.configure(values=list(presets))
            servico = dados.get("servico", list(presets)[0])
            if servico not in presets:
                servico = list(presets)[0]
            self.menu_servico.set(servico)
            url_padrao, modelo_padrao = presets[servico]
            self.entrada_url.delete(0, "end")
            self.entrada_url.insert(0, dados.get("url", url_padrao))
            modelo = dados.get("modelo", modelo_padrao)
        else:
            modelo = dados.get("modelo", servico_ia.MODELO_CLAUDE_PADRAO)
        self.entrada_modelo.delete(0, "end")
        self.entrada_modelo.insert(0, modelo)
        self.entrada_chave.delete(0, "end")
        self.entrada_chave.insert(0, dados.get("chave", ""))
        self.lbl_chave.configure(
            text="Chave (geralmente nao precisa)" if tipo == "local" else "Chave da API"
        )

        if tipo in ("nuvem", "local"):
            self.lbl_servico.pack(anchor="w", padx=12, pady=(10, 2))
            self.menu_servico.pack(fill="x", padx=12)
            self.lbl_url.pack(anchor="w", padx=12, pady=(10, 2))
            self.entrada_url.pack(fill="x", padx=12)
        self.lbl_modelo.pack(anchor="w", padx=12, pady=(10, 2))
        self.entrada_modelo.pack(fill="x", padx=12)
        self.lbl_chave.pack(anchor="w", padx=12, pady=(10, 2))
        self.entrada_chave.pack(fill="x", padx=12)
        self.btn_testar.pack(fill="x", padx=12, pady=(10, 0))
        self.lbl_ia_msg.pack(anchor="w", padx=12, pady=(4, 0))

        dicas = {
            "anthropic": "A transcricao do video e enviada a Anthropic pela internet.",
            "nuvem": "Serve para OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Mistral ou qualquer "
                     "servico compativel. A transcricao e enviada a esse servico pela internet. "
                     "Confira o nome do modelo no site do servico.",
            "local": "Tudo fica no seu computador. Abra o Ollama, o LM Studio ou outro programa "
                     "e ligue o servidor local antes de gerar.",
        }
        self.lbl_ia_dica.configure(text=dicas[tipo])

    def _trocar_ia(self, _valor=None):
        self._guardar_campos()
        self.tipo_atual = self._tipo_ia()
        self._montar_campos_ia(self.tipo_atual)

    def _escolheu_servico(self, servico):
        url, modelo = self._presets(self.tipo_atual)[servico]
        if url or modelo:
            self.entrada_url.delete(0, "end")
            self.entrada_url.insert(0, url)
            self.entrada_modelo.delete(0, "end")
            self.entrada_modelo.insert(0, modelo)

    def _config_ia(self):
        """Monta a configuracao da IA a partir dos campos. None = modo gratuito."""
        tipo = self._tipo_ia()
        if tipo == "gratis":
            return None
        return {
            "formato": "anthropic" if tipo == "anthropic" else "openai",
            "url": self.entrada_url.get().strip() if tipo != "anthropic" else servico_ia.URL_CLAUDE,
            "modelo": self.entrada_modelo.get().strip(),
            "chave": self.entrada_chave.get().strip(),
            "local": tipo == "local",
        }

    def _testar_ia(self):
        ia = self._config_ia()
        if not ia:
            return
        self.lbl_ia_msg.configure(text="Testando...", text_color=SUAVE)

        def tarefa():
            try:
                modelos = servico_ia.listar_modelos(ia)
                self.fila.put(("ia_teste", True, modelos))
            except Exception as erro:
                self.fila.put(("ia_teste", False, str(erro)))

        threading.Thread(target=tarefa, daemon=True).start()

    def _validar_ia(self, ia):
        """Devolve um texto de aviso se faltar algo, ou None se estiver tudo certo."""
        if ia is None:
            return None
        if ia["formato"] == "anthropic" and not ia["chave"]:
            return "Cole a chave da API do Claude, ou escolha outro modo."
        if ia["formato"] == "openai":
            if not ia["url"]:
                return "Preencha o endereco da API da IA."
            if not ia["modelo"]:
                return "Preencha o nome do modelo (use Testar conexao para ver os disponiveis)."
            if not ia["local"] and not ia["chave"]:
                return "Cole a chave da API do servico de IA."
        return None

    def _montar_rodape(self):
        r = self._cartao(self)
        r.grid(row=2, column=0, columnspan=3, sticky="ew", padx=24, pady=(8, 20))
        r.grid_columnconfigure(1, weight=1)

        self.btn_gerar = ctk.CTkButton(
            r, text="✨  Gerar cortes", height=52, width=210, corner_radius=14,
            fg_color=DESTAQUE, hover_color=DESTAQUE_HOVER,
            font=ctk.CTkFont(size=17, weight="bold"), command=self._gerar,
        )
        self.btn_gerar.grid(row=0, column=0, rowspan=2, padx=20, pady=18)

        self.lbl_status = ctk.CTkLabel(r, text="Pronto para comecar.", text_color=SUAVE, anchor="w")
        self.lbl_status.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(18, 0))
        self.barra = ctk.CTkProgressBar(r, progress_color=DESTAQUE, height=12)
        self.barra.set(0)
        self.barra.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(6, 18))

        self.btn_abrir = ctk.CTkButton(
            r, text="Abrir pasta", width=130, height=40, fg_color=CARTAO_2,
            hover_color="#2a3040", state="disabled", command=self._abrir_pasta,
        )
        self.btn_abrir.grid(row=0, column=2, rowspan=2, padx=20)

        self.log = ctk.CTkTextbox(r, height=90, fg_color=CARTAO_2, text_color=SUAVE, state="disabled")
        self.log.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(0, 18))

    # ----------------------------------------------------------- Acoes
    def _nome_pasta(self):
        return "📁  " + self.pasta_saida

    def _mudou_qtd(self, valor):
        self.lbl_qtd.configure(text=f"Quantidade de cortes: {int(round(valor))}")

    def _trocar_formato(self, valor):
        self.lbl_formato.configure(text=DESCRICAO_FORMATO[valor])
        self._desenhar_preview()

    def _escolher_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_saida)
        if pasta:
            self.pasta_saida = pasta
            self.btn_pasta.configure(text=self._nome_pasta())

    def _escolher_video(self):
        caminho = filedialog.askopenfilename(
            filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("Todos", "*.*")]
        )
        if not caminho:
            return
        self.entrada_link.delete(0, "end")
        self._usar_video(caminho)

    def _usar_video(self, caminho):
        self.video = caminho
        self.lbl_arquivo.configure(text=os.path.basename(caminho))
        self.lbl_info.configure(text="Lendo o video...")
        self.quadro_preview = None
        threading.Thread(target=self._carregar_preview, args=(caminho,), daemon=True).start()

    def _pasta_downloads(self):
        return os.path.join(self.pasta_saida, "downloads")

    def _link_digitado(self):
        link = self.entrada_link.get().strip()
        return link if link else None

    def _baixar(self):
        if self.trabalhando:
            return
        link = self._link_digitado()
        if not link or not link.lower().startswith(("http://", "https://")):
            self.lbl_status.configure(text="Cole um link que comece com http:// ou https://")
            return
        navegador = NAVEGADORES[self.menu_cookies.get()]
        self.trabalhando = True
        self.btn_baixar.configure(state="disabled", text="Baixando...")
        self.btn_gerar.configure(state="disabled")
        self.barra.set(0)
        self.lbl_status.configure(text="Baixando o video...")
        self._escrever_log(f"Baixando: {link}")

        def tarefa():
            try:
                caminho = baixar_video(
                    link, self._pasta_downloads(), navegador,
                    progresso=lambda f: self.fila.put(("progresso", f, "Baixando o video...")),
                )
                self.fila.put(("baixado", link, caminho, True))
            except Exception as erro:
                self.fila.put(("erro_download", str(erro)))

        threading.Thread(target=tarefa, daemon=True).start()

    def _carregar_preview(self, caminho):
        try:
            cap = cv2.VideoCapture(caminho)
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            larg = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            alt = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * 0.1))
            ok, quadro = cap.read()
            cap.release()
            if not ok:
                raise RuntimeError("nao foi possivel ler um quadro")
            rosto = achar_rosto(criar_detector(), quadro)
            seg = int(total / fps)
            info = f"{larg}x{alt}  •  {seg // 60}:{seg % 60:02d}"
            self.fila.put(("preview", quadro, rosto, info))
        except Exception as erro:
            self.fila.put(("info", f"Nao consegui ler o video ({erro})"))

    def _desenhar_preview(self):
        if self.quadro_preview is None:
            return
        quadro = self.quadro_preview.copy()
        alt, larg = quadro.shape[:2]
        cw, ch = calcular_recorte(larg, alt, self.seg_formato.get())
        cx, cy = (self.rosto_preview[0], self.rosto_preview[1]) if self.rosto_preview else (larg / 2, alt / 2)
        x0, y0 = posicao_recorte(cx, cy, cw, ch, larg, alt)

        escuro = (quadro * 0.30).astype(quadro.dtype)
        escuro[y0:y0 + ch, x0:x0 + cw] = quadro[y0:y0 + ch, x0:x0 + cw]
        cv2.rectangle(escuro, (x0, y0), (x0 + cw, y0 + ch), (255, 92, 124), max(3, larg // 300))

        imagem = Image.fromarray(cv2.cvtColor(escuro, cv2.COLOR_BGR2RGB))
        area_l = max(self.lbl_preview.winfo_width() - 16, 100)
        area_a = max(self.lbl_preview.winfo_height() - 16, 100)
        escala = min(area_l / imagem.width, area_a / imagem.height)
        tam = (max(int(imagem.width * escala), 1), max(int(imagem.height * escala), 1))
        foto = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=tam)
        self.lbl_preview.configure(image=foto, text="")
        self.lbl_preview.image = foto

    def _gerar(self):
        if self.trabalhando:
            return
        link = self._link_digitado()
        usar_link = None
        if link:
            if not link.lower().startswith(("http://", "https://")):
                self.lbl_status.configure(text="O link precisa comecar com http:// ou https://")
                return
            if self.link_baixado and self.link_baixado[0] == link and os.path.exists(self.link_baixado[1]):
                self.video = self.link_baixado[1]
            else:
                usar_link = link
        elif not self.video:
            self._escrever_log("Escolha um video ou cole um link primeiro.")
            self.lbl_status.configure(text="Escolha um video ou cole um link primeiro.")
            return

        ia = self._config_ia()
        aviso = self._validar_ia(ia)
        if aviso:
            self.lbl_status.configure(text=aviso)
            self._escrever_log(aviso)
            return

        dur_min, dur_max = DURACOES[self.menu_duracao.get()]
        cfg = {
            "video": self.video,
            "pasta_saida": self.pasta_saida,
            "formato": self.seg_formato.get(),
            "legendas": bool(self.sw_legendas.get()),
            "quantidade": int(round(self.slider_qtd.get())),
            "dur_min": dur_min,
            "dur_max": dur_max,
            "idioma": IDIOMAS[self.menu_idioma.get()],
            "ia": ia,
            "modelo_whisper": "small",
            "link": usar_link,
            "navegador": NAVEGADORES[self.menu_cookies.get()],
        }
        self._guardar_campos()
        salvar_config({
            "pasta_saida": self.pasta_saida,
            "formato": cfg["formato"],
            "duracao": self.menu_duracao.get(),
            "quantidade": cfg["quantidade"],
            "idioma": self.menu_idioma.get(),
            "legendas": cfg["legendas"],
            "tipo_ia": self._tipo_ia(),
            "ia": self.ia_salva,
            "navegador": self.menu_cookies.get(),
        })

        self.trabalhando = True
        self.btn_gerar.configure(state="disabled", text="Gerando...")
        self.btn_baixar.configure(state="disabled")
        self.btn_abrir.configure(state="disabled")
        self.barra.set(0)
        threading.Thread(target=self._trabalho, args=(cfg,), daemon=True).start()

    def _trabalho(self, cfg):
        try:
            if cfg.get("link"):
                self.fila.put(("log", f"Baixando o video do link: {cfg['link']}"))
                caminho = baixar_video(
                    cfg["link"], os.path.join(cfg["pasta_saida"], "downloads"), cfg.get("navegador"),
                    progresso=lambda f: self.fila.put(("progresso", f, "Baixando o video...")),
                )
                cfg["video"] = caminho
                self.fila.put(("baixado", cfg["link"], caminho, False))
                self.fila.put(("log", "Download concluido."))
            pasta = gerar_cortes(
                cfg,
                log=lambda m: self.fila.put(("log", m)),
                progresso=lambda f, t: self.fila.put(("progresso", f, t)),
            )
            self.fila.put(("fim", pasta))
        except Exception as erro:
            try:
                with open(ARQ_ERRO, "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except Exception:
                pass
            self.fila.put(("erro", str(erro)))

    def _abrir_pasta(self):
        if self.pasta_resultado and os.path.isdir(self.pasta_resultado):
            os.startfile(self.pasta_resultado)

    def _escrever_log(self, texto):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _processar_fila(self):
        try:
            while True:
                msg = self.fila.get_nowait()
                tipo = msg[0]
                if tipo == "log":
                    self._escrever_log(msg[1])
                elif tipo == "progresso":
                    self.barra.set(msg[1])
                    self.lbl_status.configure(text=msg[2])
                elif tipo == "preview":
                    self.quadro_preview, self.rosto_preview = msg[1], msg[2]
                    self.lbl_info.configure(text=msg[3])
                    self._desenhar_preview()
                elif tipo == "baixado":
                    self.link_baixado = (msg[1], msg[2])
                    self._usar_video(msg[2])
                    if msg[3]:  # download feito pelo botao "Baixar do link"
                        self.trabalhando = False
                        self.btn_baixar.configure(state="normal", text="Baixar do link")
                        self.btn_gerar.configure(state="normal")
                        self.barra.set(1)
                        self.lbl_status.configure(text="Video baixado! Agora e so gerar os cortes.")
                        self._escrever_log("Video baixado: " + os.path.basename(msg[2]))
                elif tipo == "erro_download":
                    self.trabalhando = False
                    self.btn_baixar.configure(state="normal", text="Baixar do link")
                    self.btn_gerar.configure(state="normal")
                    self.lbl_status.configure(text="Nao deu para baixar o video.")
                    self._escrever_log("ERRO: " + msg[1])
                elif tipo == "ia_teste":
                    if msg[1]:
                        modelos = msg[2]
                        atual = self.entrada_modelo.get().strip()
                        if modelos and self.tipo_atual == "local" and atual not in modelos:
                            self.entrada_modelo.delete(0, "end")
                            self.entrada_modelo.insert(0, modelos[0])
                            extra = f" Usei o modelo {modelos[0]}."
                        else:
                            extra = ""
                        amostra = ", ".join(modelos[:4]) if modelos else "nenhum listado"
                        self.lbl_ia_msg.configure(
                            text=f"Conectou! Modelos: {amostra}.{extra}", text_color="#5ad18f"
                        )
                    else:
                        self.lbl_ia_msg.configure(text=f"Falhou: {msg[2]}", text_color="#ff7a8a")
                elif tipo == "info":
                    self.lbl_info.configure(text=msg[1])
                elif tipo == "fim":
                    self.trabalhando = False
                    self.pasta_resultado = msg[1]
                    self.btn_gerar.configure(state="normal", text="✨  Gerar cortes")
                    self.btn_baixar.configure(state="normal", text="Baixar do link")
                    self.btn_abrir.configure(state="normal")
                    self.lbl_status.configure(text="Tudo pronto! Seus cortes estao na pasta de saida.")
                elif tipo == "erro":
                    self.trabalhando = False
                    self.btn_gerar.configure(state="normal", text="✨  Gerar cortes")
                    self.btn_baixar.configure(state="normal", text="Baixar do link")
                    self.lbl_status.configure(text="Deu um erro. Veja os detalhes abaixo.")
                    self._escrever_log(f"ERRO: {msg[1]}")
                    self._escrever_log(f"Detalhes tecnicos salvos em: {ARQ_ERRO}")
        except queue.Empty:
            pass
        self.after(100, self._processar_fila)


def iniciar():
    App().mainloop()
