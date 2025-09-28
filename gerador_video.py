import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import json
import threading
import time
import webbrowser
import base64
import os
import logging
from PIL import Image, ImageTk
from datetime import datetime
from urllib.parse import urlparse
from batch_processor import (
    PromptManager, ThreadPoolManager, ProgressTracker,
    PromptItem, PromptStatus, BatchConfiguration
)
import config

class VideoGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Vídeo D-ID - Individual e Lote")
        self.root.geometry("800x900")
        
        # Configurar logging
        self.setup_logging()
        self.log("🚀 Iniciando aplicação...")
        
        # Variáveis individuais
        self.video_id = None
        self.video_url = None
        self.checking = False
        self.check_thread = None
        
        # Sistema de processamento em lote
        self.prompt_manager = PromptManager()
        self.thread_pool = ThreadPoolManager(max_threads=config.DEFAULT_MAX_THREADS)
        self.progress_tracker = ProgressTracker()
        self.batch_config = BatchConfiguration()
        self.batch_processing = False
        self.dispatcher_running = False
        
        # Controle de UI responsiva
        self.ui_update_interval = config.UI_UPDATE_INTERVAL
        self.last_ui_update = time.time()
        
        self.setup_ui()
        self.log("✅ Interface configurada com sucesso")
    
    def setup_logging(self):
        """Configura sistema de logging"""
        # Configurar logging para arquivo
        handlers = [logging.StreamHandler()]
        if config.LOG_TO_FILE:
            handlers.append(logging.FileHandler(config.LOG_FILE, encoding='utf-8'))
            
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message, level="INFO"):
        """Log thread-safe com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Log para arquivo
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)
        
        # Log para console da UI (thread-safe)
        def update_console():
            if hasattr(self, 'log_text'):
                self.log_text.insert(tk.END, formatted_message + "\n")
                self.log_text.see(tk.END)
                # Limitar linhas do log (manter últimas 1000)
                lines = int(self.log_text.index('end-1c').split('.')[0])
                if lines > 1000:
                    self.log_text.delete('1.0', '100.0')
        
        # Executar na thread principal
        if threading.current_thread() == threading.main_thread():
            update_console()
        else:
            self.root.after(0, update_console)
    
    def setup_ui(self):
        self.log("🔧 Configurando interface...")
        
        # Header com logo e branding
        self.setup_header()
        
        # Notebook para abas
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Aba Individual
        individual_frame = ttk.Frame(notebook)
        notebook.add(individual_frame, text="Vídeo Individual")
        
        # Aba Lote
        batch_frame = ttk.Frame(notebook)
        notebook.add(batch_frame, text="Processamento em Lote")
        
        # Aba Logs
        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Logs do Sistema")
        
        self.setup_individual_tab(individual_frame)
        self.setup_batch_tab(batch_frame)
        self.setup_logs_tab(logs_frame)
        
        # Iniciar timer de atualização da UI
        self.schedule_ui_update()
        
        # Iniciar ciclo de atualização do lote (apenas uma vez)
        if not hasattr(self, '_update_batch_ui_started'):
            self._update_batch_ui_started = True
            self.root.after(self.ui_update_interval, self.update_batch_ui)
    
    def setup_header(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=(10, 0))

        top_bar = ttk.Frame(header)
        top_bar.pack(fill="x")

        content = ttk.Frame(header)
        content.pack(fill="x", pady=(8, 12))

        logo_path_candidates = [
            os.path.join(os.path.dirname(__file__), "assets", "logo.png"),
            os.path.join(os.path.dirname(__file__), "logo.png"),
            os.path.join(os.path.dirname(__file__), "logo.jpg")
        ]
        logo_img = None
        for p in logo_path_candidates:
            if os.path.exists(p):
                try:
                    img = Image.open(p)
                    img.thumbnail((96, 96), Image.LANCZOS)
                    logo_img = ImageTk.PhotoImage(img)
                    self._logo_img_ref = logo_img
                    break
                except Exception:
                    pass

        content.grid_columnconfigure(1, weight=1)

        if logo_img:
            logo_lbl = ttk.Label(content, image=logo_img)
            logo_lbl.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        else:
            placeholder = ttk.Label(content, text="VEO3", font=("Segoe UI", 20, "bold"))
            placeholder.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))

        title = ttk.Label(content, text="VEO3", font=("Segoe UI Semibold", 18))
        subtitle = ttk.Label(content, text="AUTOMATIC VIDEO SEQUENCE", font=("Segoe UI", 10))
        title.grid(row=0, column=1, sticky="w")
        subtitle.grid(row=1, column=1, sticky="w")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=(0, 8))
    
    def setup_logs_tab(self, parent):
        """Configura aba de logs"""
        self.log("📋 Configurando aba de logs...")
        
        logs_main = ttk.Frame(parent, padding="10")
        logs_main.pack(fill="both", expand=True)
        
        # Controles do log
        controls_frame = ttk.Frame(logs_main)
        controls_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(controls_frame, text="Limpar Logs", command=self.clear_logs).pack(side="left", padx=(0, 5))
        ttk.Button(controls_frame, text="Salvar Logs", command=self.save_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Atualizar", command=self.refresh_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="🧪 Testar API", command=self.test_api_connection).pack(side="left", padx=5)
        
        # Checkbox para auto-scroll
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_frame, text="Auto-scroll", variable=self.auto_scroll_var).pack(side="right")
        
        # Área de texto para logs
        log_frame = ttk.Frame(logs_main)
        log_frame.pack(fill="both", expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        
        # Status do sistema
        status_frame = ttk.LabelFrame(logs_main, text="Status do Sistema", padding="10")
        status_frame.pack(fill="x", pady=(10, 0))
        
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill="x")
        
        # Labels de status
        ttk.Label(status_grid, text="Threads ativas:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.threads_status_label = ttk.Label(status_grid, text="0")
        self.threads_status_label.grid(row=0, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Memória UI:").grid(row=0, column=2, sticky="w", padx=(20, 10))
        self.memory_status_label = ttk.Label(status_grid, text="OK")
        self.memory_status_label.grid(row=0, column=3, sticky="w")
        
        ttk.Label(status_grid, text="Última atualização:").grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.last_update_label = ttk.Label(status_grid, text="Nunca")
        self.last_update_label.grid(row=1, column=1, sticky="w")
        
        ttk.Label(status_grid, text="Status da API:").grid(row=1, column=2, sticky="w", padx=(20, 10))
        self.api_status_label = ttk.Label(status_grid, text="Não testada")
        self.api_status_label.grid(row=1, column=3, sticky="w")
    
    def clear_logs(self):
        """Limpa área de logs"""
        self.log_text.delete(1.0, tk.END)
        self.log("🧹 Logs limpos pelo usuário")
    
    def save_logs(self):
        """Salva logs em arquivo"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
                title="Salvar logs como..."
            )
            
            if file_path:
                content = self.log_text.get(1.0, tk.END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"💾 Logs salvos em: {file_path}")
                messagebox.showinfo("Sucesso", "Logs salvos com sucesso!")
        except Exception as e:
            self.log(f"❌ Erro ao salvar logs: {str(e)}", "ERROR")
            messagebox.showerror("Erro", f"Erro ao salvar logs: {str(e)}")
    
    def refresh_logs(self):
        """Força atualização dos logs"""
        self.log("🔄 Logs atualizados manualmente")
        self.update_system_status()
    
    def test_api_connection(self):
        """Testa conexão com a API"""
        self.log("🧪 Testando conexão com a API...")
        
        api_key = self.api_key_entry.get().strip()
        token = self.token_entry.get().strip()
        
        provider = self.provider_var.get() if hasattr(self, 'provider_var') else 'Veta'
        self.log(f"🏷️ Provedor selecionado: {provider}")

        # Seleciona endpoint/headers/payload conforme provedor
        if provider == "Gemini":
            if not api_key:
                self.log("❌ API Key é necessária para testar a Gemini API", "ERROR")
                messagebox.showerror("Erro", "Informe a sua Gemini API Key para testar a conexão")
                return
            endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
            headers = {
                "Accept": "application/json",
                "x-goog-api-key": api_key,
            }
            test_data = None
        elif provider == "WAN":
            if not api_key:
                self.log("❌ API Key é necessária para testar a WAN (DashScope)", "ERROR")
                messagebox.showerror("Erro", "Informe sua DashScope API Key para testar a conexão")
                return
            endpoint = config.WAN_TASK_QUERY_URL.format(task_id="nonexistent-task-id")
            headers = dict(config.WAN_HEADERS_BASE)
            headers["Authorization"] = f"Bearer {api_key}"
            test_data = None
        else:
            # Veta (atual)
            if not api_key or not token:
                self.log("❌ API Key e Token são necessários para teste", "ERROR")
                messagebox.showerror("Erro", "Preencha API Key e Token primeiro")
                return
            use_reels = hasattr(self, 'aspect_var') and self.aspect_var.get() == '9:16'
            endpoint = config.REELS_WEBHOOK_URL if use_reels else config.WEBHOOK_URL
            headers = config.DEFAULT_HEADERS
            test_data = {
                "prompt": "Hello, this is a test",
                "api_key": api_key,
                "languages": ["en"],
                "auth_token": token
            }
            if not use_reels:
                test_data["token"] = token
        
        def test_in_thread():
            try:
                self.log("🚀 Enviando requisição de teste...")
                if provider == "Gemini":
                    self.log("📐 Formato: N/A (Gemini)")
                    self.log(f"🔗 Endpoint de teste: {endpoint}")
                    response = requests.get(
                        endpoint,
                        headers=headers,
                        timeout=config.REQUEST_TIMEOUT
                    )
                elif provider == "WAN":
                    self.log("📐 Formato: N/A (WAN)")
                    self.log(f"🔗 Endpoint de teste: {endpoint}")
                    response = requests.get(
                        endpoint,
                        headers=headers,
                        timeout=config.REQUEST_TIMEOUT
                    )
                else:
                    self.log(f"📐 Formato: {'9:16 (REELS)' if use_reels else '16:9'}")
                    self.log(f"🔗 Endpoint de teste: {endpoint}")
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        data=json.dumps(test_data),
                        timeout=config.REQUEST_TIMEOUT
                    )
                
                self.log(f"📨 Status da resposta: {response.status_code}")
                self.log(f"📊 Tamanho da resposta: {len(response.content)} bytes")
                self.log(f"📋 Content-Type: {response.headers.get('content-type', 'N/A')}")
                self.log(f"📄 Resposta: {response.text[:500]}...")
                
                if response.status_code in [200, 201]:
                    self.log("✅ API respondeu com sucesso!")
                    messagebox.showinfo("Sucesso", "API está funcionando!")
                else:
                    self.log(f"❌ API retornou erro: {response.status_code}", "ERROR")
                    messagebox.showerror("Erro", f"API retornou erro: {response.status_code}")
                    
            except Exception as e:
                self.log(f"❌ Erro no teste da API: {str(e)}", "ERROR")
                messagebox.showerror("Erro", f"Erro no teste: {str(e)}")
        
        # Executar teste em thread separada
        thread = threading.Thread(target=test_in_thread, daemon=True, name="APITestThread")
        thread.start()
    
    def schedule_ui_update(self):
        """Agenda próxima atualização da UI"""
        self.update_system_status()
        self.root.after(self.ui_update_interval, self.schedule_ui_update)
    
    def update_system_status(self):
        """Atualiza status do sistema na aba de logs"""
        try:
            if hasattr(self, 'threads_status_label'):
                # Threads ativas
                active_threads = self.thread_pool.get_active_count() if hasattr(self, 'thread_pool') else 0
                self.threads_status_label.config(text=str(active_threads))
                
                # Última atualização
                current_time = datetime.now().strftime("%H:%M:%S")
                self.last_update_label.config(text=current_time)
                
                # Status da memória (simples verificação)
                try:
                    import psutil
                    memory_percent = psutil.virtual_memory().percent
                    if memory_percent > 90:
                        self.memory_status_label.config(text="ALTA", foreground="red")
                    elif memory_percent > 70:
                        self.memory_status_label.config(text="MÉDIA", foreground="orange")
                    else:
                        self.memory_status_label.config(text="OK", foreground="green")
                except ImportError:
                    self.memory_status_label.config(text="N/A", foreground="gray")
                
                # Auto-scroll se habilitado
                if self.auto_scroll_var.get() and hasattr(self, 'log_text'):
                    self.log_text.see(tk.END)
                    
        except Exception as e:
            # Não logar erros de atualização para evitar loop
            pass
        
        # Agendamento do update_batch_ui é feito uma única vez em setup_ui
    
    def setup_individual_tab(self, parent):
        # Frame principal
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Provedor
        ttk.Label(main_frame, text="Provedor:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.provider_var = tk.StringVar(value="Veta")
        provider_combo = ttk.Combobox(main_frame, textvariable=self.provider_var, 
                                    values=["Veta", "Gemini", "WAN"], state="readonly")
        provider_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Links de ajuda ao lado do combobox quando apropriado
        # Container para links
        if not hasattr(self, 'provider_links_frame'):
            self.provider_links_frame = ttk.Frame(main_frame)
            self.provider_links_frame.grid(row=0, column=2, sticky=tk.W, padx=(10,0))
        else:
            # Limpar se já existir (reconfigurações)
            for child in self.provider_links_frame.winfo_children():
                child.destroy()

        def render_provider_links(*_):
            # Limpa links existentes
            for child in self.provider_links_frame.winfo_children():
                child.destroy()
            current = self.provider_var.get()

            # Link para assinar o Veta (sempre visível)
            def open_veta():
                try:
                    webbrowser.open_new_tab("https://pay.kiwify.com.br/PaxY52r?afid=xWFfnFvw")
                except Exception:
                    pass
            link_veta = ttk.Label(self.provider_links_frame, text="assine o veta", foreground="blue", cursor="hand2")
            link_veta.bind("<Button-1>", lambda e: open_veta())
            link_veta.grid(row=0, column=0, padx=(0,10))

            # Link para gerar API do Gemini (apenas quando Gemini estiver selecionado)
            if current == "Gemini":
                def open_gemini_api():
                    try:
                        webbrowser.open_new_tab("https://aistudio.google.com/app/apikey")
                    except Exception:
                        pass
                link_gemini = ttk.Label(self.provider_links_frame, text="Gerar API do Gemini", foreground="blue", cursor="hand2")
                link_gemini.bind("<Button-1>", lambda e: open_gemini_api())
                link_gemini.grid(row=0, column=1)

            # Link para obter API Key do WAN (apenas quando WAN estiver selecionado)
            if current == "WAN":
                def open_wan_api():
                    try:
                        webbrowser.open_new_tab("https://dashscope.console.aliyun.com/")
                    except Exception:
                        pass
                link_wan = ttk.Label(self.provider_links_frame, text="Obter API Key do WAN", foreground="blue", cursor="hand2")
                link_wan.bind("<Button-1>", lambda e: open_wan_api())
                link_wan.grid(row=0, column=1)

        # Render inicial e bind de mudança
        render_provider_links()
        provider_combo.bind("<<ComboboxSelected>>", render_provider_links)
        
        # API Key
        ttk.Label(main_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(main_frame, width=50, show="*")
        self.api_key_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Token
        ttk.Label(main_frame, text="Token:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.token_entry = ttk.Entry(main_frame, width=50, show="*")
        self.token_entry.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Prompt
        ttk.Label(main_frame, text="Prompt:").grid(row=3, column=0, sticky=(tk.W, tk.N), pady=5)
        self.prompt_text = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        self.prompt_text.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Idioma
        ttk.Label(main_frame, text="Idioma:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.language_var = tk.StringVar(value="pt")
        language_combo = ttk.Combobox(main_frame, textvariable=self.language_var, 
                                    values=["pt", "en", "es", "fr", "de", "it"], state="readonly")
        language_combo.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Botão Gerar
        self.generate_button = ttk.Button(main_frame, text="Gerar Vídeo", command=self.generate_video)
        self.generate_button.grid(row=5, column=0, columnspan=3, pady=20)
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.status_label = ttk.Label(main_frame, text="Pronto para gerar vídeo", foreground="green")
        self.status_label.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Frame para botões do vídeo
        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=8, column=0, columnspan=3, pady=10)
        
        self.open_button = ttk.Button(video_frame, text="Abrir no Navegador", 
                                    command=self.open_in_browser, state="disabled")
        self.open_button.grid(row=0, column=0, padx=5)
        
        self.download_button = ttk.Button(video_frame, text="Baixar Vídeo", 
                                        command=self.download_video, state="disabled")
        self.download_button.grid(row=0, column=1, padx=5)
        
        # URL do vídeo
        ttk.Label(main_frame, text="URL do Vídeo:").grid(row=9, column=0, sticky=tk.W, pady=5)
        self.url_text = scrolledtext.ScrolledText(main_frame, width=50, height=3)
        self.url_text.grid(row=9, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Frame para preview do vídeo
        preview_frame = ttk.LabelFrame(main_frame, text="Preview do Vídeo", padding="10")
        preview_frame.grid(row=10, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.video_info_label = ttk.Label(preview_frame, text="Nenhum vídeo carregado")
        self.video_info_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        self.play_button = ttk.Button(preview_frame, text="▶ Reproduzir", 
                                    command=self.play_video, state="disabled")
        self.play_button.grid(row=1, column=0, padx=5, pady=5)
        
        self.video_status_label = ttk.Label(preview_frame, text="")
        self.video_status_label.grid(row=1, column=1, padx=5, pady=5)
        
        # Configurar redimensionamento
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def setup_batch_tab(self, parent):
        # Frame principal do lote
        batch_main = ttk.Frame(parent, padding="10")
        batch_main.pack(fill="both", expand=True)
        
        # Configurações do lote
        config_frame = ttk.LabelFrame(batch_main, text="Configurações do Lote", padding="10")
        config_frame.pack(fill="x", pady=(0, 10))
        
        # Threads simultâneas
        ttk.Label(config_frame, text="Threads simultâneas:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.threads_var = tk.IntVar(value=config.DEFAULT_MAX_THREADS)
        threads_spin = ttk.Spinbox(config_frame, from_=1, to=10, textvariable=self.threads_var, width=10)
        threads_spin.grid(row=0, column=1, sticky=tk.W, pady=5)
        threads_spin.bind('<FocusOut>', self.update_thread_count)
        
        # Idioma padrão para lote
        ttk.Label(config_frame, text="Idioma padrão:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=5)
        self.batch_language_var = tk.StringVar(value="pt")
        batch_lang_combo = ttk.Combobox(config_frame, textvariable=self.batch_language_var, 
                                       values=["pt", "en", "es", "fr", "de", "it"], state="readonly", width=10)
        batch_lang_combo.grid(row=0, column=3, sticky=tk.W, pady=5)

        # Retries em caso de erro
        ttk.Label(config_frame, text="Retries (erros):").grid(row=0, column=4, sticky=tk.W, padx=(20, 5), pady=5)
        self.batch_retries_var = tk.IntVar(value=getattr(self.batch_config, 'max_retries', config.CONNECTION_RETRIES))
        retries_spin = ttk.Spinbox(config_frame, from_=0, to=10, increment=1, textvariable=self.batch_retries_var, width=10)
        retries_spin.grid(row=0, column=5, sticky=tk.W, pady=5)
        retries_spin.bind('<FocusOut>', self.update_batch_retries)

        # Formato do vídeo (proporção)
        ttk.Label(config_frame, text="Formato:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.aspect_var = tk.StringVar(value="16:9")
        ttk.Radiobutton(config_frame, text="16:9 (padrão)", variable=self.aspect_var, value="16:9").grid(row=1, column=1, sticky=tk.W)
        ttk.Radiobutton(config_frame, text="9:16 (vertical)", variable=self.aspect_var, value="9:16").grid(row=1, column=2, sticky=tk.W)
        # Aplica defaults quando o formato é alterado (ex.: 9:16 -> 1 thread e 120s)
        self.aspect_var.trace_add("write", self.on_aspect_change)
        
        # Delay opcional entre gerações (segundos)
        ttk.Label(config_frame, text="Delay entre gerações (s):").grid(row=1, column=3, sticky=tk.W, padx=(20, 5), pady=5)
        self.batch_delay_var = tk.DoubleVar(value=self.batch_config.request_delay if hasattr(self, 'batch_config') else 0.0)
        delay_spin = ttk.Spinbox(config_frame, from_=0.0, to=120.0, increment=0.1, textvariable=self.batch_delay_var, width=10)
        delay_spin.grid(row=1, column=4, sticky=tk.W, pady=5)
        delay_spin.bind('<FocusOut>', self.update_batch_delay)
        
        # Modo sequencial (força 1 thread)
        self.sequential_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="Modo sequencial", variable=self.sequential_mode_var, command=self.on_toggle_sequential_mode).grid(row=1, column=5, sticky=tk.W, pady=5)
        
        # Imagem de referência para 9:16 (aplicada a todos os prompts)
        ttk.Label(config_frame, text="Imagem referência (9:16):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.batch_ref_image_path = tk.StringVar(value="")
        ref_entry = ttk.Entry(config_frame, textvariable=self.batch_ref_image_path, width=40, state="readonly")
        ref_entry.grid(row=2, column=1, columnspan=3, sticky=tk.W, pady=5)
        ttk.Button(config_frame, text="Selecionar...", command=self.select_batch_ref_image).grid(row=2, column=4, sticky=tk.W, pady=5)
        ttk.Button(config_frame, text="Limpar", command=self.clear_batch_ref_image).grid(row=2, column=5, sticky=tk.W, pady=5)
        # Preview da imagem de referência
        ttk.Label(config_frame, text="Prévia:").grid(row=2, column=6, sticky=tk.W, padx=(10, 5))
        self.ref_preview_label = ttk.Label(config_frame, text="—")
        self.ref_preview_label.grid(row=2, column=7, sticky=tk.W)
        # Atualiza preview ao mudar o caminho
        self.batch_ref_image_path.trace_add("write", self.on_ref_image_changed)
        # Inicializa preview
        self.update_ref_preview()
        
        # --- Módulo influencer (habilitado apenas com modo sequencial) ---
        self.influencer_module_var = tk.BooleanVar(value=False)
        self.influencer_module_check = ttk.Checkbutton(
            config_frame, text="Módulo influencer", variable=self.influencer_module_var,
            command=self.on_toggle_influencer_module
        )
        self.influencer_module_check.grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(config_frame, text="Foto da influencer:").grid(row=3, column=1, sticky=tk.W, pady=5)
        self.influencer_image_path = tk.StringVar(value="")
        self.influencer_entry = ttk.Entry(config_frame, textvariable=self.influencer_image_path, width=40, state="readonly")
        self.influencer_entry.grid(row=3, column=2, columnspan=2, sticky=tk.W, pady=5)
        self.influencer_select_btn = ttk.Button(config_frame, text="Selecionar...", command=self.select_influencer_image)
        self.influencer_select_btn.grid(row=3, column=4, sticky=tk.W, pady=5)
        self.influencer_clear_btn = ttk.Button(config_frame, text="Limpar", command=self.clear_influencer_image)
        self.influencer_clear_btn.grid(row=3, column=5, sticky=tk.W, pady=5)
        ttk.Label(config_frame, text="Prévia influencer:").grid(row=3, column=6, sticky=tk.W, padx=(10, 5))
        self.influencer_preview_label = ttk.Label(config_frame, text="—")
        self.influencer_preview_label.grid(row=3, column=7, sticky=tk.W)
        self.influencer_image_path.trace_add("write", lambda *args: self.update_influencer_preview())
        self.update_influencer_preview()
        self.update_influencer_controls_state()
        
        # Entrada de prompts
        prompts_frame = ttk.LabelFrame(batch_main, text="Prompts (máximo 50)", padding="10")
        prompts_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Área de texto para prompts
        ttk.Label(prompts_frame, text="Digite os prompts (um por linha):").pack(anchor="w")
        self.batch_prompts_text = scrolledtext.ScrolledText(prompts_frame, height=8)
        self.batch_prompts_text.pack(fill="both", expand=True, pady=5)
        
        # Botões de controle
        control_frame = ttk.Frame(prompts_frame)
        control_frame.pack(fill="x", pady=5)
        
        ttk.Button(control_frame, text="Carregar de Arquivo", command=self.load_prompts_from_file).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text="Limpar Prompts", command=self.clear_batch_prompts).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Adicionar à Lista", command=self.add_prompts_to_batch).pack(side="left", padx=5)
        
        # Lista de prompts
        list_frame = ttk.LabelFrame(batch_main, text="Lista de Prompts", padding="10")
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Treeview para mostrar prompts
        columns = ("N", "ID", "Prompt", "Idioma", "Imagem", "Status", "URL")
        self.prompts_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        # Configurar colunas
        self.prompts_tree.heading("N", text="#")
        self.prompts_tree.heading("ID", text="ID")
        self.prompts_tree.heading("Prompt", text="Prompt")
        self.prompts_tree.heading("Idioma", text="Idioma")
        self.prompts_tree.heading("Imagem", text="Imagem")
        self.prompts_tree.heading("Status", text="Status")
        self.prompts_tree.heading("URL", text="URL do Vídeo")
        
        self.prompts_tree.column("N", width=40, anchor="center")
        self.prompts_tree.column("ID", width=80)
        self.prompts_tree.column("Prompt", width=260)
        self.prompts_tree.column("Idioma", width=80)
        self.prompts_tree.column("Imagem", width=90, anchor="center")
        self.prompts_tree.column("Status", width=100)
        self.prompts_tree.column("URL", width=200)
        
        # Scrollbar para treeview
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.prompts_tree.yview)
        self.prompts_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.prompts_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        # Controles da lista
        list_controls = ttk.Frame(list_frame)
        list_controls.pack(side="bottom", fill="x", pady=5)
        self.clear_prompt_list_button = ttk.Button(list_controls, text="Limpar Lista de Prompts", command=self.clear_prompt_list)
        self.clear_prompt_list_button.pack(side="left")
        
        # Menu de contexto para treeview
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Remover Prompt", command=self.remove_selected_prompt)
        self.tree_menu.add_command(label="Abrir URL", command=self.open_selected_url)
        self.tree_menu.add_command(label="Copiar URL", command=self.copy_selected_url)
        # Novas ações: editar e reprocessar
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Editar Prompt...", command=self.edit_selected_prompt)
        self.tree_menu.add_command(label="Tentar Novamente", command=self.retry_selected_prompt)
        self.tree_menu.add_command(label="Editar e Tentar Novamente...", command=self.edit_and_retry_selected_prompt)
        # Ações para imagem do prompt
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Definir Imagem do Prompt...", command=self.set_image_for_selected_prompt)
        self.tree_menu.add_command(label="Abrir Imagem...", command=self.open_image_for_selected_prompt)
        self.tree_menu.add_command(label="Limpar Imagem do Prompt", command=self.clear_image_for_selected_prompt)
        
        self.prompts_tree.bind("<Button-3>", self.show_tree_menu)
        self.prompts_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # Controles de processamento
        process_frame = ttk.LabelFrame(batch_main, text="Processamento", padding="10")
        process_frame.pack(fill="x", pady=(0, 10))
        
        # Botões de controle
        buttons_frame = ttk.Frame(process_frame)
        buttons_frame.pack(fill="x")
        
        self.start_batch_button = ttk.Button(buttons_frame, text="Iniciar Processamento", command=self.start_batch_processing)
        self.start_batch_button.pack(side="left", padx=(0, 5))
        
        self.pause_batch_button = ttk.Button(buttons_frame, text="Pausar", command=self.pause_batch_processing, state="disabled")
        self.pause_batch_button.pack(side="left", padx=5)
        
        self.stop_batch_button = ttk.Button(buttons_frame, text="Parar", command=self.stop_batch_processing, state="disabled")
        self.stop_batch_button.pack(side="left", padx=5)
        
        ttk.Button(buttons_frame, text="Unir Vídeos", command=self.merge_videos_button).pack(side="right", padx=(5, 0))
        ttk.Button(buttons_frame, text="Baixar Todos", command=self.download_all_videos).pack(side="right")
        
        # Progresso
        progress_info_frame = ttk.Frame(process_frame)
        progress_info_frame.pack(fill="x", pady=(10, 0))
        
        # Barra de progresso
        self.batch_progress = ttk.Progressbar(progress_info_frame, mode='determinate')
        self.batch_progress.pack(fill="x", pady=(0, 5))
        
        # Labels de informação
        info_frame = ttk.Frame(progress_info_frame)
        info_frame.pack(fill="x")
        
        self.batch_status_label = ttk.Label(info_frame, text="Pronto para processar")
        self.batch_status_label.pack(side="left")
        
        self.batch_progress_label = ttk.Label(info_frame, text="0/0 (0%)")
        self.batch_progress_label.pack(side="right")
        
        # Timer para atualizar interface será iniciado após a criação completa
    
    def generate_video(self):
        self.log("🎬 Iniciando geração de vídeo individual...")
        
        # Validar campos
        api_key = self.api_key_entry.get().strip()
        token = self.token_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        provider = self.provider_var.get() if hasattr(self, 'provider_var') else 'Veta'
        
        self.log(f"📝 Validando campos... Prompt: {len(prompt)} chars")
        
        if not api_key:
            self.log("❌ API Key não fornecida", "ERROR")
            messagebox.showerror("Erro", "Por favor, insira a API Key")
            return
        
        # Token é obrigatório apenas para Veta
        if provider == "Veta" and not token:
            self.log("❌ Token não fornecido (obrigatório para Veta)", "ERROR")
            messagebox.showerror("Erro", "Por favor, insira o Token (obrigatório para Veta)")
            return
        
        if not prompt:
            self.log("❌ Prompt não fornecido", "ERROR")
            messagebox.showerror("Erro", "Por favor, insira o prompt")
            return
        
        self.log("✅ Validação concluída, preparando requisição...")
        
        # Preparar dados
        data = {
            "script": {
                "type": "text",
                "input": prompt
            },
            "config": {
                "fluent": False,
                "pad_audio": 0.0
            },
            "source_url": "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"
        }
        
        # Desabilitar botão e iniciar progress
        self.log("🔄 Desabilitando interface e iniciando progresso...")
        self.generate_button.config(state="disabled")
        self.progress.start()
        self.update_status("Enviando requisição...")
        
        # Enviar requisição em thread separada
        self.log("🚀 Iniciando thread de requisição...")
        thread = threading.Thread(target=self.send_request, args=(data,), daemon=True, name="VideoGenThread")
        thread.start()
        self.log(f"✅ Thread iniciada: {thread.name}")
    
    def send_request(self, data):
        thread_name = threading.current_thread().name
        self.log(f"📡 [{thread_name}] Iniciando envio de requisição...")
        
        try:
            provider = self.provider_var.get() if hasattr(self, 'provider_var') else 'Veta'
            self.log(f"🏷️ [{thread_name}] Provedor: {provider}")

            if provider == "Gemini":
                # Chamada direta à Gemini API (Veo 3 - Long Running Operation)
                api_key = self.api_key_entry.get().strip()
                if not api_key:
                    self.log(f"⚠️ [{thread_name}] Gemini API Key não informada", "WARNING")
                    self.update_status("Informe sua Gemini API Key para continuar")
                    return
                prompt_text = data.get("script", {}).get("input", "").strip()
                if not prompt_text:
                    self.update_status("Prompt vazio. Nada para enviar.")
                    return
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "x-goog-api-key": api_key,
                }
                start_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/veo-3.0-generate-001:predictLongRunning"
                payload = {
                    "instances": [
                        {"prompt": prompt_text}
                    ]
                }
                self.log(f"📤 [{thread_name}] Iniciando operação Veo 3 (predictLongRunning)...")
                self.log(f"🔗 URL: {start_endpoint}")
                self.log(f"📦 Payload size: {len(json.dumps(payload))} bytes")
                start_time = time.time()
                start_resp = requests.post(start_endpoint, headers=headers, data=json.dumps(payload), timeout=config.REQUEST_TIMEOUT)
                elapsed = time.time() - start_time
                self.log(f"⏱️ [{thread_name}] Requisição de início concluída em {elapsed:.2f}s")
                if start_resp.status_code not in (200, 201):
                    self.log(f"❌ [{thread_name}] Erro ao iniciar operação: {start_resp.status_code} - {start_resp.text[:300]}", "ERROR")
                    self.update_status("Falha ao iniciar geração de vídeo na Gemini API")
                    return
                op = start_resp.json()
                op_name = op.get("name") or op.get("operation")
                if not op_name:
                    self.log(f"❌ [{thread_name}] Resposta sem nome de operação: {op}", "ERROR")
                    self.update_status("Resposta inválida da Gemini API (sem operação)")
                    return
                self.log(f"🆔 [{thread_name}] Operação: {op_name}")
                poll_url = op_name
                if not poll_url.startswith("http"):
                    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name.lstrip('/')}"
                self.update_status("Aguardando geração do vídeo (Gemini)...")
                while True:
                    time.sleep(8)
                    self.log(f"🔄 [{thread_name}] Polling operação...")
                    poll_resp = requests.get(poll_url, headers={"Accept": "application/json", "x-goog-api-key": api_key}, timeout=config.REQUEST_TIMEOUT)
                    if poll_resp.status_code != 200:
                        self.log(f"⚠️ [{thread_name}] Falha no polling: {poll_resp.status_code} - {poll_resp.text[:200]}", "WARNING")
                        continue
                    op_state = poll_resp.json()
                    if op_state.get("done") is True:
                        self.log(f"✅ [{thread_name}] Operação concluída")
                        if op_state.get("error"):
                            self.log(f"❌ [{thread_name}] Erro na operação: {op_state.get('error')}", "ERROR")
                            self.update_status("A geração falhou na Gemini API")
                            return
                        resp = op_state.get("response") or {}
                        video_uri = None
                        try:
                            gen = resp.get("generated_videos") or []
                            if gen:
                                vid_obj = gen[0].get("video") or {}
                                video_uri = vid_obj.get("uri") or vid_obj.get("videoUri")
                                if not video_uri and isinstance(vid_obj, dict):
                                    inner = vid_obj.get("video") or {}
                                    if isinstance(inner, dict):
                                        video_uri = inner.get("uri") or inner.get("videoUri")
                        except Exception:
                            video_uri = None
                        if not video_uri:
                            self.log(f"❓ [{thread_name}] Não foi possível extrair a URI do vídeo: {json.dumps(op_state)[:400]}", "WARNING")
                            self.update_status("Geração concluída, mas não encontrei a URI do vídeo")
                            return
                        self.log(f"🎯 [{thread_name}] URI do vídeo obtida: {video_uri}")
                        self.video_url = video_uri
                        self.update_video_info(self.video_url)
                        self.update_status("Vídeo gerado com sucesso (Gemini)!")
                        return
                    else:
                        self.update_status("Processando vídeo na Gemini API... (aguarde)")
            elif provider == "WAN":
                # Integração com Wan (DashScope) - criação de tarefa e polling
                api_key = self.api_key_entry.get().strip()
                if not api_key:
                    self.log(f"⚠️ [{thread_name}] WAN API Key não informada", "WARNING")
                    self.update_status("Informe sua WAN (DashScope) API Key para continuar")
                    return
                prompt_text = data.get("script", {}).get("input", "").strip()
                if not prompt_text:
                    self.update_status("Prompt vazio. Nada para enviar.")
                    return

                headers = dict(config.WAN_HEADERS_BASE)
                headers["Authorization"] = f"Bearer {api_key}"

                # Monta payload mínimo de T2V (sem imagem de referência local)
                create_payload = {
                    "model": config.WAN_DEFAULT_T2V_MODEL,
                    "input": {
                        "prompt": prompt_text
                    }
                }
                # Dica: para acelerar/diagnosticar, você pode ativar parâmetros leves
                # create_payload["parameters"] = {"size": "832*480", "duration": 5}

                # Logs detalhados do modelo e parâmetros
                self.log(f"🧩 [{thread_name}] WAN modelo: {create_payload.get('model')}")
                self.log(f"📝 [{thread_name}] Prompt (chars): {len(prompt_text)}")
                if 'parameters' in create_payload:
                    self.log(f"⚙️ [{thread_name}] Parameters: {create_payload['parameters']}")
                else:
                    self.log(f"⚙️ [{thread_name}] Parameters: (não definidos; usando defaults do modelo)")

                self.log(f"📤 [{thread_name}] Criando tarefa no WAN (video-synthesis)...")
                self.log(f"🔗 URL: {config.WAN_VIDEO_CREATE_URL}")
                self.log(f"📦 Payload size: {len(json.dumps(create_payload))} bytes")
                start_time = time.time()
                create_resp = requests.post(
                    config.WAN_VIDEO_CREATE_URL,
                    headers=headers,
                    data=json.dumps(create_payload),
                    timeout=config.REQUEST_TIMEOUT
                )
                elapsed = time.time() - start_time
                self.log(f"⏱️ [{thread_name}] Criação da tarefa concluída em {elapsed:.2f}s")
                if create_resp.status_code not in (200, 201, 202):
                    self.log(f"❌ [{thread_name}] Erro ao criar tarefa WAN: {create_resp.status_code} - {create_resp.text[:300]}", "ERROR")
                    self.update_status("Falha ao iniciar geração de vídeo na WAN (DashScope)")
                    return

                try:
                    create_json = create_resp.json()
                except Exception:
                    create_json = {}
                # Debug da resposta de criação
                try:
                    preview = create_resp.text[:300]
                except Exception:
                    preview = "<sem preview>"
                self.log(f"🧪 [{thread_name}] Debug criação (preview): {preview}")
                self.log(f"🧪 [{thread_name}] Keys criação topo: {list(create_json.keys())}")
                out_create = (create_json.get("output") or {})
                if isinstance(out_create, dict):
                    self.log(f"🧪 [{thread_name}] Keys criação output: {list(out_create.keys())}")
                task_id = (
                    (create_json.get("output") or {}).get("task_id")
                    or create_json.get("task_id")
                    or create_json.get("id")
                )
                if not task_id:
                    self.log(f"❓ [{thread_name}] Não foi possível obter task_id: {create_resp.text[:400]}", "WARNING")
                    self.update_status("Tarefa iniciada mas task_id não encontrado")
                    return

                self.log(f"🆔 [{thread_name}] task_id: {task_id}")
                poll_url = config.WAN_TASK_QUERY_URL.format(task_id=task_id)
                self.log(f"🔎 [{thread_name}] Poll URL: {poll_url}")
                self.update_status("Aguardando geração do vídeo (WAN)...")

                # Controle de tempo e backoff para o polling
                gen_start = time.time()
                poll_interval = 8  # segundos
                warned_timeout = False

                # Polling até completar
                while True:
                    time.sleep(poll_interval)
                    self.log(f"🔄 [{thread_name}] Polling tarefa WAN...")
                    poll_resp = requests.get(poll_url, headers=headers, timeout=config.REQUEST_TIMEOUT)
                    if poll_resp.status_code not in (200, 201):
                        self.log(f"⚠️ [{thread_name}] Falha no polling: {poll_resp.status_code} - {poll_resp.text[:200]}", "WARNING")
                        continue
                    try:
                        state = poll_resp.json()
                    except Exception as pe:
                        self.log(f"⚠️ [{thread_name}] Polling JSON inválido: {pe}", "WARNING")
                        continue

                    # Debug do polling
                    try:
                        poll_preview = poll_resp.text[:400]
                    except Exception:
                        poll_preview = "<sem preview>"
                    self.log(f"🧪 [{thread_name}] Debug polling (preview): {poll_preview}")
                    self.log(f"🧪 [{thread_name}] Keys polling topo: {list(state.keys())}")
                    out = state.get("output") or {}
                    if isinstance(out, dict):
                        self.log(f"🧪 [{thread_name}] Keys polling output: {list(out.keys())}")
                    code = state.get("code") or out.get("code")
                    message = state.get("message") or out.get("message")
                    if code or message:
                        self.log(f"🧪 [{thread_name}] code={code} message={message}")

                    # Logs de status/progresso para confirmar geração
                    out = state.get("output") or {}
                    raw_status = (
                        out.get("status")
                        or state.get("status")
                        or out.get("task_status")
                        or state.get("task_status")
                        or out.get("phase")
                        or state.get("phase")
                    )
                    progress = (
                        out.get("progress")
                        or out.get("percent")
                        or out.get("progress_percent")
                        or out.get("progress_in_percent")
                        or out.get("task_progress")
                        or out.get("stage")
                    )
                    self.log(f"📊 [{thread_name}] Status WAN: {raw_status}")
                    if progress:
                        self.log(f"⏳ [{thread_name}] Progresso WAN: {progress}")
                    else:
                        self.log(f"⏳ [{thread_name}] Progresso WAN: (não informado)")

                    # Se nenhum status, exibir resumo do estado para diagnóstico
                    if raw_status is None:
                        try:
                            compact = json.dumps(state)[:500]
                        except Exception:
                            compact = str(state)[:500]
                        self.log(f"🧪 [{thread_name}] Status ausente, estado compacto: {compact}")

                    # Timeout/backoff: alerta após THREAD_TIMEOUT e corte duro após WAN_MAX_WAIT_SECONDS (default 30 min)
                    elapsed_total = time.time() - gen_start
                    if (not warned_timeout) and elapsed_total > getattr(config, "THREAD_TIMEOUT", 600):
                        self.log(f"⏰ [{thread_name}] 10+ minutos de processamento. Mantendo tarefa, mas ampliando intervalo de polling para 15s para reduzir carga.")
                        warned_timeout = True
                        poll_interval = 15
                    if elapsed_total > getattr(config, "WAN_MAX_WAIT_SECONDS", 1800):
                        self.log(f"🛑 [{thread_name}] Tempo máximo de espera atingido ({int(elapsed_total)}s). Interrompendo polling desta tarefa.", "ERROR")
                        self.update_status("Tempo esgotado na geração (WAN). Tente novamente mais tarde ou ajuste parâmetros (ex.: size=832*480, duration=5s).")
                        return

                    # Tenta extrair status e url do vídeo de forma resiliente
                    status = (
                        (state.get("output") or {}).get("status")
                        or state.get("status")
                        or (state.get("output") or {}).get("task_status")
                        or state.get("task_status")
                        or (state.get("output") or {}).get("phase")
                        or state.get("phase")
                    )
                    if status and str(status).lower() in ("succeeded", "success", "completed", "done", "finished"):
                        # Buscar URL do vídeo
                        video_url = None
                        try:
                            out = state.get("output") or {}
                            video_url = (
                                out.get("video_url") or out.get("url") or out.get("result_url")
                                or out.get("video") or out.get("result")
                            )
                            if not isinstance(video_url, str):
                                video_url = None
                                def find_url(obj):
                                    if isinstance(obj, str) and obj.startswith("http"):
                                        return obj
                                    if isinstance(obj, dict):
                                        for v in obj.values():
                                            u = find_url(v)
                                            if u:
                                                return u
                                    if isinstance(obj, list):
                                        for v in obj:
                                            u = find_url(v)
                                            if u:
                                                return u
                                    return None
                                video_url = find_url(out)
                        except Exception:
                            video_url = None

                        if not video_url:
                            self.log(f"❓ [{thread_name}] Tarefa concluída, mas não encontrei URL do vídeo: {json.dumps(state)[:400]}", "WARNING")
                            self.update_status("Geração concluída no WAN, mas URL do vídeo não encontrada")
                            return

                        self.log(f"🎯 [{thread_name}] URL do vídeo (WAN): {video_url}")
                        self.video_url = video_url
                        self.update_video_info(video_url)
                        self.update_status("Vídeo gerado com sucesso (WAN)!")
                        return
                    elif status and str(status).lower() in ("failed", "error", "canceled"):
                        self.log(f"❌ [{thread_name}] Tarefa falhou no WAN: {json.dumps(state)[:300]}", "ERROR")
                        self.update_status("A geração falhou no WAN (DashScope)")
                        return
                    else:
                        self.update_status("Processando vídeo no WAN (DashScope)... (aguarde)")
            else:
                headers = dict(config.DEFAULT_HEADERS)
                # Selecionar endpoint conforme formato 16:9 ou 9:16
                use_reels = hasattr(self, 'aspect_var') and self.aspect_var.get() == '9:16'
                endpoint = config.REELS_WEBHOOK_URL if use_reels else config.WEBHOOK_URL
                # Preparar dados para enviar ao webhook (Veta)
                if use_reels:
                    webhook_data = {
                        "prompt": data.get("script", {}).get("input", ""),
                        "api_key": self.api_key_entry.get().strip(),
                        "languages": [self.language_var.get()],
                        "auth_token": self.token_entry.get().strip()
                    }
                else:
                    webhook_data = {
                        "prompt": data.get("script", {}).get("input", ""),
                        "api_key": self.api_key_entry.get().strip(),
                        "token": self.token_entry.get().strip(),
                        "languages": [self.language_var.get()],
                        "auth_token": self.token_entry.get().strip()
                    }
                    # Se houver imagem de referência configurada no lote, reutilizar também para 16:9 no modo individual
                    ref_path = self.batch_ref_image_path.get() if hasattr(self, 'batch_ref_image_path') else ""
                    if ref_path:
                        try:
                            with open(ref_path, 'rb') as f:
                                b64_data = base64.b64encode(f.read()).decode('utf-8')
                            ext = os.path.splitext(ref_path)[1].lower()
                            if ext == '.png':
                                mime = 'image/png'
                            elif ext in ('.jpg', '.jpeg'):
                                mime = 'image/jpeg'
                            elif ext == '.webp':
                                mime = 'image/webp'
                            elif ext == '.bmp':
                                mime = 'image/bmp'
                            else:
                                mime = 'application/octet-stream'
                            webhook_data["images"] = [{
                                "name": os.path.basename(ref_path),
                                "type": mime,
                                "data": b64_data
                            }]
                            self.log(f"🖼️ [{thread_name}] Incluindo imagem de referência no payload (individual 16:9)")
                        except Exception as e:
                            self.log(f"⚠️ [{thread_name}] Falha ao ler imagem de referência (individual 16:9): {e}", "WARNING")
            
            # Log detalhado da requisição
            self.log(f"📤 [{thread_name}] Preparando POST para webhook...")
            self.log(f"🔗 URL: {endpoint}")
            self.log(f"📦 Payload size: {len(json.dumps(webhook_data))} bytes")
            self.log(f"🌐 Language: {webhook_data.get('languages', ['unknown'])}")
            if provider != "Gemini":
                self.log(f"📐 [{thread_name}] Formato: {'9:16 (REELS)' if use_reels else '16:9'}")
            
            # Fazer a requisição POST para o webhook
            self.log(f"🚀 [{thread_name}] Enviando requisição...")
            start_time = time.time()
            
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(webhook_data),
                timeout=config.REQUEST_TIMEOUT
            )
            
            request_time = time.time() - start_time
            self.log(f"⏱️ [{thread_name}] Requisição completada em {request_time:.2f}s")
            
            # Verificar a resposta
            self.log(f"📨 [{thread_name}] Status: {response.status_code}, Size: {len(response.content)} bytes")
            
            if response.status_code == 200 or response.status_code == 201:
                self.log(f"✅ [{thread_name}] Requisição bem-sucedida!")
                self.update_status("Requisição enviada com sucesso para o webhook!")
                
                # Verificar se a resposta contém dados binários
                try:
                    # Tentar decodificar como texto
                    response_text = response.text
                    self.log(f"📄 [{thread_name}] Analisando resposta de texto...")
                    
                    # Verificar se contém caracteres não imprimíveis (dados binários)
                    if any(ord(char) < 32 and char not in '\n\r\t' for char in response_text[:100]):
                        self.log(f"🎬 [{thread_name}] Resposta contém dados binários - possível arquivo de vídeo")
                        
                        # Verificar headers para tipo de conteúdo
                        content_type = response.headers.get('content-type', '').lower()
                        self.log(f"📋 [{thread_name}] Content-Type: {content_type}")
                        
                        if 'video' in content_type or 'application/octet-stream' in content_type:
                            # É um arquivo de vídeo - salvar diretamente
                            self.log(f"💾 [{thread_name}] Salvando vídeo binário...")
                            self.save_video_from_response(response)
                        else:
                            self.log(f"❓ [{thread_name}] Formato binário não reconhecido", "WARNING")
                            self.update_status("Resposta em formato binário não reconhecido")
                    else:
                        # Resposta é texto - processar normalmente
                        self.log(f"📝 [{thread_name}] Processando resposta de texto: {len(response_text)} chars")
                        
                        # Processar resposta do webhook
                        try:
                            response_data = response.json()
                            video_url = response_data.get('video_url') or response_data.get('url') or response_data.get('link')
                            
                            if video_url:
                                self.log(f"🎯 [{thread_name}] URL do vídeo encontrada: {video_url[:50]}...")
                                self.video_url = video_url
                                self.update_video_info(video_url)
                                self.update_status("Vídeo gerado com sucesso!")
                            else:
                                self.log(f"⏳ [{thread_name}] URL não encontrada, vídeo em processamento")
                                self.update_status("Vídeo enviado para processamento. Aguarde o retorno.")
                                
                        except json.JSONDecodeError:
                            self.log(f"🔍 [{thread_name}] Não é JSON, verificando se é link direto...")
                            # Se não for JSON, pode ser um link direto
                            if response_text.startswith('http'):
                                self.log(f"🔗 [{thread_name}] Link direto encontrado")
                                self.video_url = response_text.strip()
                                self.update_video_info(self.video_url)
                                self.update_status("Vídeo gerado com sucesso!")
                            else:
                                self.log(f"❓ [{thread_name}] Formato de resposta não reconhecido", "WARNING")
                                self.update_status("Resposta recebida, mas formato não reconhecido.")
                                
                except Exception as e:
                    self.log(f"❌ [{thread_name}] Erro ao processar resposta: {str(e)}", "ERROR")
                    self.update_status("Erro ao processar resposta do servidor")
                        
            else:
                error_msg = f"Erro na requisição: {response.status_code} - {response.text[:200]}..."
                self.log(f"❌ [{thread_name}] {error_msg}", "ERROR")
                self.update_status(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout na requisição (30s)"
            self.log(f"⏰ [{thread_name}] {error_msg}", "ERROR")
            self.update_status(error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Erro de conexão com o servidor"
            self.log(f"🌐 [{thread_name}] {error_msg}", "ERROR")
            self.update_status(error_msg)
        except Exception as e:
            error_msg = f"Erro ao enviar requisição: {str(e)}"
            self.log(f"❌ [{thread_name}] {error_msg}", "ERROR")
            self.update_status(error_msg)
        finally:
            # Reabilitar botão e parar progress
            self.log(f"🔄 [{thread_name}] Finalizando requisição...")
            self.after_request_complete()
    
    def after_request_complete(self):
        """Executado após completar a requisição"""
        def update():
            self.generate_button.config(state="normal")
            self.progress.stop()
        
        self.root.after(0, update)
    
    def update_status(self, message):
        """Atualiza o status na interface"""
        def update():
            self.status_label.config(text=message)
            if "sucesso" in message.lower():
                self.status_label.config(foreground="green")
            elif "erro" in message.lower():
                self.status_label.config(foreground="red")
            else:
                self.status_label.config(foreground="blue")
        
        self.root.after(0, update)
    
    def update_video_info(self, video_url):
        """Atualiza as informações do vídeo na interface"""
        def update():
            self.url_text.delete(1.0, tk.END)
            self.url_text.insert(1.0, video_url)
            
            # Habilitar botões
            self.open_button.config(state="normal")
            self.download_button.config(state="normal")
            self.play_button.config(state="normal")
            
            # Atualizar info do vídeo
            parsed_url = urlparse(video_url)
            if 'drive.google.com' in parsed_url.netloc:
                self.video_info_label.config(text="📁 Vídeo no Google Drive")
            elif parsed_url.path.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                self.video_info_label.config(text="🎬 Arquivo de vídeo direto")
            else:
                self.video_info_label.config(text="🔗 Link do vídeo")
                
            self.video_status_label.config(text="✅ Pronto para reproduzir")
        
        self.root.after(0, update)
    
    def open_in_browser(self):
        """Abre o vídeo no navegador"""
        if self.video_url:
            webbrowser.open(self.video_url)
        else:
            messagebox.showwarning("Aviso", "Nenhum vídeo disponível para abrir")
    
    def play_video(self):
        """Reproduz o vídeo no player padrão do sistema"""
        if self.video_url:
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(self.video_url)
                elif os.name == 'posix':  # macOS e Linux
                    os.system(f'open "{self.video_url}"')
                self.video_status_label.config(text="🎬 Reproduzindo...")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao reproduzir vídeo: {str(e)}")
        else:
            messagebox.showwarning("Aviso", "Nenhum vídeo disponível para reproduzir")
    
    def download_video(self):
        """Baixa o vídeo para o computador"""
        if not self.video_url:
            messagebox.showwarning("Aviso", "Nenhum vídeo disponível para download")
            return
        
        try:
            # Escolher local para salvar
            file_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("Vídeos MP4", "*.mp4"), ("Todos os arquivos", "*.*")],
                title="Salvar vídeo como..."
            )
            
            if file_path:
                self.update_status("Baixando vídeo...")
                self.video_status_label.config(text="⬇️ Baixando...")
                
                # Baixar em thread separada
                download_thread = threading.Thread(
                    target=self._download_file, 
                    args=(self.video_url, file_path), 
                    daemon=True
                )
                download_thread.start()
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar download: {str(e)}")
    
    def _download_file(self, url, file_path):
        """Baixa o arquivo em thread separada"""
        try:
            # Incluir API key para downloads da Gemini Files API quando necessário
            headers = {}
            try:
                if url.startswith("https://generativelanguage.googleapis.com") or "ai.googleusercontent.com" in url or "googleapis.com" in url:
                    api_key = self.api_key_entry.get().strip()
                    if api_key:
                        headers["x-goog-api-key"] = api_key
            except Exception:
                pass

            response = requests.get(url, stream=True, headers=headers if headers else None)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        
                        # Atualizar progresso
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.root.after(0, lambda: self.video_status_label.config(
                                text=f"⬇️ Baixando... {progress:.1f}%"
                            ))
            
            # Download concluído
            self.root.after(0, lambda: [
                self.update_status("Download concluído com sucesso!"),
                self.video_status_label.config(text="✅ Download concluído"),
                messagebox.showinfo("Sucesso", f"Vídeo salvo em:\n{file_path}")
            ])
            
        except Exception as e:
            self.root.after(0, lambda: [
                 self.update_status(f"Erro no download: {str(e)}"),
                 self.video_status_label.config(text="❌ Erro no download"),
                 messagebox.showerror("Erro", f"Erro ao baixar vídeo: {str(e)}")
             ])
    
    def save_video_from_response(self, response):
        """Salva vídeo diretamente da resposta binária"""
        try:
            # Escolher local para salvar
            file_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("Vídeos MP4", "*.mp4"), ("Todos os arquivos", "*.*")],
                title="Salvar vídeo como..."
            )
            
            if file_path:
                self.update_status("Salvando vídeo...")
                
                # Salvar arquivo
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                
                # Definir como vídeo local
                self.video_url = f"file:///{file_path.replace(chr(92), '/')}"
                self.update_video_info(self.video_url)
                self.update_status("Vídeo salvo com sucesso!")
                messagebox.showinfo("Sucesso", f"Vídeo salvo em:\n{file_path}")
            else:
                self.update_status("Salvamento cancelado")
                
        except Exception as e:
            error_msg = f"Erro ao salvar vídeo: {str(e)}"
            self.update_status(error_msg)
            messagebox.showerror("Erro", error_msg)
    
    # ==================== MÉTODOS DO PROCESSAMENTO EM LOTE ====================
    
    def update_thread_count(self, event=None):
        """Atualiza número de threads simultâneas"""
        new_count = self.threads_var.get()
        self.thread_pool.update_max_threads(new_count)
        self.batch_config.max_threads = new_count
        # Se estivermos processando, tentar despachar mais imediatamente
        if getattr(self, 'batch_processing', False):
            try:
                self.dispatch_pending_prompts()
            except Exception as e:
                self.log(f"Erro ao despachar após mudar threads: {e}", "ERROR")

    def update_batch_retries(self, event=None):
        """Atualiza o número de retries em caso de erro no processamento em lote"""
        try:
            retries = int(self.batch_retries_var.get()) if hasattr(self, 'batch_retries_var') else config.CONNECTION_RETRIES
            retries = max(0, min(10, retries))
            if hasattr(self, 'batch_retries_var'):
                self.batch_retries_var.set(retries)
            # Persistir na configuração do lote
            if hasattr(self, 'batch_config'):
                self.batch_config.max_retries = retries
            self.log(f"🔁 Retries configurados para {retries}")
        except Exception as e:
            self.log(f"Erro ao atualizar retries: {e}", "ERROR")

    def update_batch_delay(self, event=None):
        """Atualiza o delay entre gerações do processamento em lote"""
        try:
            delay = float(self.batch_delay_var.get()) if hasattr(self, 'batch_delay_var') else 0.0
            if delay < 0:
                delay = 0.0
            if hasattr(self, 'batch_delay_var'):
                self.batch_delay_var.set(delay)
            self.batch_config.request_delay = delay
            self.log(f"⏳ Delay entre gerações ajustado para {delay:.2f}s")
        except Exception as e:
            self.log(f"Erro ao atualizar delay: {e}", "ERROR")
    
    def select_batch_ref_image(self):
        path = filedialog.askopenfilename(title="Selecionar imagem de referência",
                                          filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("Todos", "*.*")])
        if path:
            self.batch_ref_image_path.set(path)
            self.log(f"🖼️ Imagem de referência selecionada para lote: {path}")
            # Atualiza prévia e tabela
            self.update_ref_preview()
            self.schedule_tree_update()

    def clear_batch_ref_image(self):
        try:
            self.batch_ref_image_path.set("")
        except Exception:
            self.batch_ref_image_path = tk.StringVar(value="")
        self.log("🧹 Imagem de referência do lote limpa")
        # Atualiza prévia e tabela
        self.update_ref_preview()
        self.schedule_tree_update()
    
    # --- Prévia da imagem de referência ---
    def on_ref_image_changed(self, *args):
        """Callback disparado quando o caminho da imagem de referência muda."""
        try:
            self.update_ref_preview()
        finally:
            try:
                self.schedule_tree_update()
            except Exception:
                pass

    def update_ref_preview(self):
        """Atualiza o thumbnail da imagem de referência ao lado do campo do caminho."""
        try:
            if not hasattr(self, 'ref_preview_label'):
                return
            path = self.batch_ref_image_path.get() if hasattr(self, 'batch_ref_image_path') else ""
            if not path or not os.path.isfile(path):
                self.ref_preview_label.config(image="", text="—")
                self._ref_preview_photo = None
                return
            img = Image.open(path)
            img.thumbnail((64, 64), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._ref_preview_photo = photo
            self.ref_preview_label.config(image=self._ref_preview_photo, text="")
        except Exception as e:
            self._ref_preview_photo = None
            if hasattr(self, 'ref_preview_label'):
                self.ref_preview_label.config(image="", text="(erro)")
            self.log(f"⚠️ Falha ao carregar prévia da imagem de referência: {e}", "WARNING")
    
    # --- Módulo influencer: handlers e utilitários ---
    def on_toggle_influencer_module(self):
        """Ativa/desativa o módulo influencer (habilitado somente com modo sequencial)."""
        try:
            enabled = bool(self.influencer_module_var.get()) if hasattr(self, 'influencer_module_var') else False
            self.log("👤 Módulo influencer " + ("ativado" if enabled else "desativado"))
            self.update_influencer_controls_state()
        except Exception as e:
            self.log(f"⚠️ Erro ao alternar módulo influencer: {e}", "ERROR")

    def select_influencer_image(self):
        try:
            if not hasattr(self, 'influencer_image_path'):
                return
            path = filedialog.askopenfilename(title="Selecionar foto da influencer",
                                              filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("Todos", "*.*")])
            if path:
                self.influencer_image_path.set(path)
                self.log(f"📸 Foto da influencer selecionada: {path}")
                self.update_influencer_preview()
        except Exception as e:
            self.log(f"⚠️ Erro ao selecionar foto da influencer: {e}", "ERROR")

    def clear_influencer_image(self):
        try:
            if hasattr(self, 'influencer_image_path'):
                self.influencer_image_path.set("")
            self.update_influencer_preview()
            self.log("🧹 Foto da influencer limpa")
        except Exception as e:
            self.log(f"⚠️ Erro ao limpar foto da influencer: {e}", "ERROR")

    def update_influencer_preview(self):
        """Atualiza o thumbnail da imagem da influencer ao lado do campo do caminho."""
        try:
            if not hasattr(self, 'influencer_preview_label') or not hasattr(self, 'influencer_image_path'):
                return
            path = self.influencer_image_path.get().strip()
            if not path or not os.path.isfile(path):
                self.influencer_preview_label.config(image="", text="—")
                self._influencer_preview_photo = None
                return
            img = Image.open(path)
            img.thumbnail((64, 64), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._influencer_preview_photo = photo
            self.influencer_preview_label.config(image=self._influencer_preview_photo, text="")
        except Exception as e:
            self._influencer_preview_photo = None
            if hasattr(self, 'influencer_preview_label'):
                self.influencer_preview_label.config(image="", text="(erro)")
            self.log(f"⚠️ Falha ao carregar prévia da influencer: {e}", "WARNING")

    def update_influencer_controls_state(self):
        """Habilita/desabilita os controles do módulo influencer conforme o modo sequencial e o checkbox."""
        try:
            sequential_enabled = bool(self.sequential_mode_var.get()) if hasattr(self, 'sequential_mode_var') else False
            # O checkbox do módulo influencer só habilita se o modo sequencial estiver ativo
            if hasattr(self, 'influencer_module_check'):
                state = ("normal" if sequential_enabled else "disabled")
                try:
                    self.influencer_module_check.state(["!disabled"]) if sequential_enabled else self.influencer_module_check.state(["disabled"])
                except Exception:
                    # ttk.Checkbutton pode não aceitar .state em algumas versões, usar configure
                    self.influencer_module_check.configure(state=state)
                if not sequential_enabled and hasattr(self, 'influencer_module_var'):
                    # Se desligou sequencial, também desliga o módulo influencer
                    self.influencer_module_var.set(False)
            influencer_on = sequential_enabled and hasattr(self, 'influencer_module_var') and bool(self.influencer_module_var.get())
            # Controles dependentes da ativação do módulo
            entry_state = "readonly" if influencer_on else "disabled"
            btn_state = ("normal" if influencer_on else "disabled")
            if hasattr(self, 'influencer_entry'):
                try:
                    self.influencer_entry.configure(state=entry_state)
                except Exception:
                    pass
            if hasattr(self, 'influencer_select_btn'):
                try:
                    self.influencer_select_btn.configure(state=btn_state)
                except Exception:
                    pass
            if hasattr(self, 'influencer_clear_btn'):
                try:
                    self.influencer_clear_btn.configure(state=btn_state)
                except Exception:
                    pass
            # Atualiza a prévia para refletir possível limpeza/desativação
            self.update_influencer_preview()
        except Exception as e:
            self.log(f"⚠️ Erro ao atualizar estado dos controles do influencer: {e}", "ERROR")

    def on_aspect_change(self, *args):
        """Ajusta threads e delay automaticamente quando o formato é alterado"""
        try:
            value = self.aspect_var.get() if hasattr(self, 'aspect_var') else '16:9'
            if value == '9:16':
                # Defaults para vertical (Reels)
                if hasattr(self, 'threads_var'):
                    self.threads_var.set(1)
                    self.update_thread_count()
                if hasattr(self, 'batch_delay_var'):
                    self.batch_delay_var.set(120.0)
                    self.update_batch_delay()
                self.log("⚙️  Formato 9:16 selecionado: threads=1 e delay=120s aplicados automaticamente")
            else:
                # Restaurar defaults para horizontal
                if hasattr(self, 'threads_var'):
                    self.threads_var.set(config.DEFAULT_MAX_THREADS)
                    self.update_thread_count()
                if hasattr(self, 'batch_delay_var'):
                    self.batch_delay_var.set(0.0)
                    self.update_batch_delay()
                self.log(f"⚙️  Formato {value} selecionado: threads={config.DEFAULT_MAX_THREADS} e delay=0s aplicados")
        except Exception as e:
            self.log(f"⚠️ Erro ao aplicar defaults de formato: {e}", level="ERROR")
    
    def on_toggle_sequential_mode(self):
        """Ativa/desativa o modo sequencial (força 1 thread)"""
        try:
            enabled = bool(self.sequential_mode_var.get()) if hasattr(self, 'sequential_mode_var') else False
            self.sequential_mode = enabled
            if enabled:
                if hasattr(self, 'threads_var'):
                    self.threads_var.set(1)
                    self.update_thread_count()
                self.log("🧩 Modo sequencial ativado (threads=1)")
            else:
                # Restaurar threads padrão se não estiver em 9:16, que já força 1
                aspect = self.aspect_var.get() if hasattr(self, 'aspect_var') else '16:9'
                if aspect != '9:16' and hasattr(self, 'threads_var'):
                    default_threads = getattr(config, 'DEFAULT_MAX_THREADS', 2)
                    self.threads_var.set(default_threads)
                    self.update_thread_count()
                self.log("🧩 Modo sequencial desativado")
            # Atualiza estado dos controles do módulo influencer
            try:
                self.update_influencer_controls_state()
            except Exception:
                pass
        except Exception as e:
            self.log(f"⚠️ Erro ao alternar modo sequencial: {e}", "ERROR")
    
    def schedule_dispatcher(self):
        """Agenda loop leve para despachar prompts pendentes automaticamente durante o lote"""
        if getattr(self, 'dispatcher_running', False):
            return
        self.dispatcher_running = True
        
        def run():
            try:
                self.dispatch_pending_prompts()
            except Exception as e:
                self.log(f"⚠️ Erro no despachante: {e}", "ERROR")
            finally:
                if getattr(self, 'batch_processing', False):
                    self.root.after(300, run)
                else:
                    self.dispatcher_running = False
        # Iniciar após pequeno atraso
        self.root.after(300, run)
    
    def dispatch_pending_prompts(self):
        """Despacha prompts pendentes respeitando o limite de threads do pool"""
        if not getattr(self, 'batch_processing', False):
            return
        pending = self.prompt_manager.get_pending_prompts()
        if not pending:
            return
        active = self.thread_pool.get_active_count()
        capacity = max(0, self.thread_pool.max_threads - active)
        # Forçar capacidade 1 quando modo sequencial estiver ativo
        if getattr(self, 'sequential_mode', False):
            capacity = min(1, capacity)
        if capacity <= 0:
            return
        # Guardar janela de espera para delay pós-conclusão
        try:
            delay_guard = getattr(self.batch_config, 'request_delay', 0.0)
        except Exception:
            delay_guard = 0.0
        if delay_guard and delay_guard > 0:
            next_at = getattr(self, 'next_allowed_dispatch_at', 0)
            now = time.time()
            if now < next_at:
                # Aguardando janela de delay para despachar novamente
                return
        # STRICT SEQUENTIAL GUARD
        if getattr(self, 'sequential_mode', False):
            all_prompts = self.prompt_manager.get_all_prompts()
            next_prompt = None
            next_index = None
            for i, p in enumerate(all_prompts):
                if p.status == PromptStatus.PENDING:
                    next_prompt = p
                    next_index = i
                    break
            if next_prompt is None:
                return
            prior_prompts = all_prompts[:next_index]
            if any(pr.status == PromptStatus.FAILED for pr in prior_prompts):
                self.log("🛑 Modo sequencial: um prompt anterior falhou. Pausando até editar o prompt ou tentar novamente.", "ERROR")
                try:
                    self.pause_batch_processing()
                except Exception:
                    pass
                return
            if any(pr.status != PromptStatus.COMPLETED for pr in prior_prompts):
                self.log("⏳ Modo sequencial: aguardando conclusão do prompt anterior antes de despachar o próximo.")
                return
            to_submit = [next_prompt]
        else:
            to_submit = pending[:capacity]
        if not to_submit:
            return
        self.log(f"🚚 Despachando {len(to_submit)} prompts pendentes (capacidade: {capacity}, ativas: {active})")
        
        # Respeitar delay opcional entre submissões usando agendamento (não bloqueia UI)
        delay_seconds = getattr(self.batch_config, 'request_delay', 0.0)
        if delay_seconds and delay_seconds > 0:
            delay_ms = int(max(0.0, delay_seconds) * 1000)
            for idx, prompt in enumerate(to_submit):
                # Marcar como PROCESSING imediatamente para evitar agendamentos duplicados em próximos ciclos
                try:
                    self.prompt_manager.update_prompt_status(prompt.id, PromptStatus.PROCESSING)
                    self.schedule_tree_update()
                except Exception:
                    pass
                def _submit(p=prompt):
                    # Apenas submeter (status já marcado)
                    self.thread_pool.submit_prompt(
                        p,
                        self.process_single_prompt_batch,
                        self.on_prompt_completed
                    )
                try:
                    self.root.after(delay_ms * idx, _submit)
                except Exception:
                    _submit()
        else:
            for prompt in to_submit:
                # Marcar como PROCESSING antes de submeter para evitar duplicidade
                try:
                    self.prompt_manager.update_prompt_status(prompt.id, PromptStatus.PROCESSING)
                    self.schedule_tree_update()
                except Exception:
                    pass
                self.thread_pool.submit_prompt(
                    prompt,
                    self.process_single_prompt_batch,
                    self.on_prompt_completed
                )
    
    def load_prompts_from_file(self):
        """Carrega prompts de um arquivo de texto"""
        file_path = filedialog.askopenfilename(
            title="Carregar Prompts",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.batch_prompts_text.delete(1.0, tk.END)
                    self.batch_prompts_text.insert(1.0, content)
                messagebox.showinfo("Sucesso", "Prompts carregados com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar arquivo: {str(e)}")
    
    def clear_batch_prompts(self):
        """Limpa a área de texto de prompts"""
        self.batch_prompts_text.delete(1.0, tk.END)
    
    def clear_prompt_list(self):
        """Limpa a lista de prompts já adicionados na Treeview e no gerenciador"""
        # Bloquear durante processamento em andamento
        if getattr(self, 'batch_processing', False) or (hasattr(self, 'thread_pool') and self.thread_pool.get_active_count() > 0):
            messagebox.showwarning(
                "Indisponível",
                "Não é possível limpar a lista enquanto o processamento estiver em andamento.\nPause ou pare o processamento primeiro."
            )
            return
        
        # Limpar prompts do gerenciador
        try:
            self.prompt_manager.clear_all_prompts()
        except Exception:
            pass
        
        # Atualizar árvore e progresso
        self.update_prompts_tree()
        try:
            self.progress_tracker.start_tracking(0)
        except Exception:
            pass
        if hasattr(self, 'batch_progress'):
            self.batch_progress['value'] = 0
        if hasattr(self, 'batch_progress_label'):
            self.batch_progress_label.config(text="0/0 (0%)")
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.config(text="Lista de prompts limpa")
        
        self.log("🧹 Lista de prompts limpa pelo usuário")
    
    def add_prompts_to_batch(self):
        """Adiciona prompts da área de texto à lista de processamento"""
        text = self.batch_prompts_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("Aviso", "Nenhum prompt para adicionar")
            return
        
        language = self.batch_language_var.get()
        # Tenta interpretar como JSON (suporta um ou vários objetos); se não adicionar nada, faz fallback para linhas
        added_count = self.prompt_manager.add_prompts_from_json_text(text, language)
        if added_count == 0:
            added_count = self.prompt_manager.add_prompts_from_text(text, language)
        
        if added_count > 0:
            self.update_prompts_tree()
            messagebox.showinfo("Sucesso", f"{added_count} prompts adicionados à lista")
            self.batch_prompts_text.delete(1.0, tk.END)
            # Se estiver processando, ajustar total e despachar
            if getattr(self, 'batch_processing', False):
                try:
                    self.progress_tracker.add_to_total(added_count)
                except Exception:
                    pass
                self.dispatch_pending_prompts()
        else:
            messagebox.showwarning("Aviso", "Limite de 50 prompts atingido")
    
    def update_prompts_tree(self):
        """Atualiza a visualização da lista de prompts"""
        # Limpar árvore
        for item in self.prompts_tree.get_children():
            self.prompts_tree.delete(item)
        
        # Adicionar prompts
        for idx, prompt in enumerate(self.prompt_manager.get_all_prompts(), start=1):
            # Truncar prompt se muito longo
            display_prompt = prompt.prompt_text[:50] + "..." if len(prompt.prompt_text) > 50 else prompt.prompt_text
            
            # URL truncada
            display_url = ""
            if prompt.video_url:
                display_url = prompt.video_url[:30] + "..." if len(prompt.video_url) > 30 else prompt.video_url
            
            # Indicador de imagem: "Prompt" quando imagem própria definida, "Ref" quando usa imagem de referência do lote, "—" quando não há
            has_prompt_image = bool(getattr(prompt, 'image_path', None))
            has_ref_image = bool(hasattr(self, 'batch_ref_image_path') and self.batch_ref_image_path.get())
            image_marker = "Prompt" if has_prompt_image else ("Ref" if has_ref_image else "—")
            self.prompts_tree.insert("", "end", iid=str(prompt.id), values=(
                idx,
                prompt.id,
                display_prompt,
                prompt.language,
                image_marker,
                prompt.status.value,
                display_url
            ))
    
    def schedule_tree_update(self):
        """Agenda atualização da TreeView com debounce para evitar múltiplas reconstruções seguidas"""
        try:
            if not hasattr(self, '_tree_update_scheduled'):
                self._tree_update_scheduled = False
            if self._tree_update_scheduled:
                return
            self._tree_update_scheduled = True
            def _apply():
                try:
                    self.update_prompts_tree()
                finally:
                    self._tree_update_scheduled = False
            self.root.after(100, _apply)
        except Exception:
            # Fallback em caso de erro
            self.update_prompts_tree()
    
    def show_tree_menu(self, event):
        """Mostra menu de contexto na árvore"""
        item = self.prompts_tree.selection()
        if item:
            self.tree_menu.post(event.x_root, event.y_root)
    
    def remove_selected_prompt(self):
        """Remove prompt selecionado"""
        selection = self.prompts_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        prompt_id = self.prompts_tree.item(item)['values'][1]
        
        if self.prompt_manager.remove_prompt(prompt_id):
            self.update_prompts_tree()
            messagebox.showinfo("Sucesso", "Prompt removido")
    
    def open_selected_url(self):
        """Abre URL do prompt selecionado"""
        selection = self.prompts_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.prompts_tree.item(item)['values']
        prompt_id = values[1]
        
        # Buscar prompt completo
        for prompt in self.prompt_manager.get_all_prompts():
            if prompt.id == prompt_id and prompt.video_url:
                webbrowser.open(prompt.video_url)
                return
        
        messagebox.showwarning("Aviso", "Nenhuma URL disponível para este prompt")
    
    def copy_selected_url(self):
        """Copia URL do prompt selecionado"""
        selection = self.prompts_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.prompts_tree.item(item)['values']
        prompt_id = values[1]
        
        # Buscar prompt completo
        for prompt in self.prompt_manager.get_all_prompts():
            if prompt.id == prompt_id and prompt.video_url:
                self.root.clipboard_clear()
                self.root.clipboard_append(prompt.video_url)
                messagebox.showinfo("Sucesso", "URL copiada para área de transferência")
                return
        
        messagebox.showwarning("Aviso", "Nenhuma URL disponível para este prompt")

    def on_tree_double_click(self, event):
        """Abre a imagem quando o usuário dá duplo clique na coluna 'Imagem'."""
        try:
            col = self.prompts_tree.identify_column(event.x)
            row = self.prompts_tree.identify_row(event.y)
            # A coluna 'Imagem' é a quinta no array de colunas => '#5'
            if col == '#5' and row:
                values = self.prompts_tree.item(row)['values']
                if values and len(values) >= 2:
                    prompt_id = values[1]
                    self.open_image_for_selected_prompt(prompt_id=prompt_id)
        except Exception:
            pass

    def open_image_for_selected_prompt(self, prompt_id=None):
        """Abre a imagem associada ao prompt (imagem própria ou referência do lote)."""
        try:
            if prompt_id is None:
                prompt_id = self._get_selected_prompt_id()
                if prompt_id is None:
                    sel = self.prompts_tree.selection()
                    if not sel:
                        messagebox.showinfo("Imagem", "Selecione um prompt para abrir a imagem.")
                        return
                    prompt_id = sel[0]
            # Buscar prompt localmente, pois get_prompt_by_id pode não existir
            prompt_item = None
            try:
                for p in self.prompt_manager.get_all_prompts():
                    if p.id == prompt_id:
                        prompt_item = p
                        break
            except Exception:
                prompt_item = None
            img_path = None
            if prompt_item and getattr(prompt_item, 'image_path', None):
                img_path = prompt_item.image_path
            elif hasattr(self, 'batch_ref_image_path') and self.batch_ref_image_path.get():
                img_path = self.batch_ref_image_path.get()
            if not img_path:
                messagebox.showinfo("Imagem", "Nenhuma imagem associada ao prompt ou referência do lote.")
                return
            try:
                if os.path.exists(img_path):
                    try:
                        os.startfile(img_path)
                    except Exception:
                        webbrowser.open(f"file:///{img_path.replace(chr(92), '/')}" )
                else:
                    webbrowser.open(img_path)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao abrir imagem: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao abrir imagem: {e}")

    # --- Novas ações: editar e reprocessar ---
    def _get_selected_prompt_id(self):
        selection = self.prompts_tree.selection()
        if not selection:
            return None
        item = selection[0]
        values = self.prompts_tree.item(item)['values']
        if values and len(values) > 1 and values[1]:
            return values[1]
        # Fallback: usa o iid do item (definido como o próprio prompt.id em update_prompts_tree)
        return item

    def edit_selected_prompt(self):
        prompt_id = self._get_selected_prompt_id()
        if not prompt_id:
            return
        prompt = self.prompt_manager.find_prompt(prompt_id)
        if not prompt:
            messagebox.showerror("Erro", "Prompt não encontrado")
            return
        if prompt.status == PromptStatus.PROCESSING:
            messagebox.showwarning("Indisponível", "Não é possível editar enquanto está processando.")
            return
        
        def on_save(new_text, new_lang, do_retry=False):
            updated = self.prompt_manager.update_prompt(prompt_id, new_text, new_lang)
            if not updated:
                messagebox.showerror("Erro", "Falha ao atualizar prompt")
                return
            if do_retry:
                if not self.prompt_manager.reset_for_retry(prompt_id):
                    messagebox.showwarning("Aviso", "Não foi possível preparar para nova tentativa.")
                else:
                    if getattr(self, 'batch_processing', False):
                        try:
                            self.progress_tracker.add_to_total(1)
                        except Exception:
                            pass
            self.schedule_tree_update()
            if do_retry:
                if getattr(self, 'batch_processing', False):
                    try:
                        self.dispatch_pending_prompts()
                    except Exception:
                        pass
                else:
                    if messagebox.askyesno("Iniciar", "Deseja iniciar o processamento agora?"):
                        self.start_batch_processing()
            messagebox.showinfo("Sucesso", "Prompt atualizado" + (" e reprocessamento iniciado." if do_retry else "."))
        
        self._open_edit_prompt_dialog(prompt, on_save, allow_retry=False)

    def retry_selected_prompt(self):
        prompt_id = self._get_selected_prompt_id()
        if not prompt_id:
            return
        prompt = self.prompt_manager.find_prompt(prompt_id)
        if not prompt:
            messagebox.showerror("Erro", "Prompt não encontrado")
            return
        if prompt.status == PromptStatus.PROCESSING:
            messagebox.showwarning("Indisponível", "Este prompt já está processando.")
            return
        
        if not self.prompt_manager.reset_for_retry(prompt_id):
            messagebox.showwarning("Aviso", "Não foi possível preparar para nova tentativa.")
            return
        
        self.schedule_tree_update()
        if getattr(self, 'batch_processing', False):
            try:
                self.progress_tracker.add_to_total(1)
            except Exception:
                pass
            try:
                self.dispatch_pending_prompts()
            except Exception:
                pass
            messagebox.showinfo("Reprocessando", "Prompt reenfileirado para processamento.")
        else:
            if messagebox.askyesno("Iniciar", "Deseja iniciar o processamento agora?"):
                self.start_batch_processing()

    def edit_and_retry_selected_prompt(self):
        prompt_id = self._get_selected_prompt_id()
        if not prompt_id:
            return
        prompt = self.prompt_manager.find_prompt(prompt_id)
        if not prompt:
            messagebox.showerror("Erro", "Prompt não encontrado")
            return
        if prompt.status == PromptStatus.PROCESSING:
            messagebox.showwarning("Indisponível", "Não é possível editar enquanto está processando.")
            return
        
        def on_save(new_text, new_lang, do_retry=True):
            updated = self.prompt_manager.update_prompt(prompt_id, new_text, new_lang)
            if not updated:
                messagebox.showerror("Erro", "Falha ao atualizar prompt")
                return
            if do_retry:
                if not self.prompt_manager.reset_for_retry(prompt_id):
                    messagebox.showwarning("Aviso", "Não foi possível preparar para nova tentativa.")
                else:
                    if getattr(self, 'batch_processing', False):
                        try:
                            self.progress_tracker.add_to_total(1)
                        except Exception:
                            pass
            self.schedule_tree_update()
            if do_retry:
                if getattr(self, 'batch_processing', False):
                    try:
                        self.dispatch_pending_prompts()
                    except Exception:
                        pass
                else:
                    if messagebox.askyesno("Iniciar", "Deseja iniciar o processamento agora?"):
                        self.start_batch_processing()
            messagebox.showinfo("Sucesso", "Prompt atualizado e reenfileirado para processamento.")
        
        self._open_edit_prompt_dialog(prompt, on_save, allow_retry=True)

    def set_image_for_selected_prompt(self):
        """Abre diálogo para escolher imagem e aplica ao prompt selecionado."""
        prompt_id = self._get_selected_prompt_id()
        if not prompt_id:
            return
        path = filedialog.askopenfilename(
            title="Selecione a imagem do prompt",
            filetypes=[
                ("Imagens", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("Todos", "*.*")
            ]
        )
        if not path:
            return
        try:
            self.prompt_manager.set_prompt_image(prompt_id, path)
            self.schedule_tree_update()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao definir imagem: {e}")

    def clear_image_for_selected_prompt(self):
        """Remove a imagem específica do prompt selecionado."""
        prompt_id = self._get_selected_prompt_id()
        if not prompt_id:
            return
        try:
            self.prompt_manager.set_prompt_image(prompt_id, None)
            self.schedule_tree_update()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao limpar imagem: {e}")

    def _open_edit_prompt_dialog(self, prompt_item, on_save, allow_retry: bool):
        dialog = tk.Toplevel(self.root)
        dialog.title("Editar Prompt")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("500x350")
        
        # Prompt text
        ttk.Label(dialog, text="Prompt:").pack(anchor="w", padx=10, pady=(10, 2))
        text_widget = scrolledtext.ScrolledText(dialog, height=8)
        text_widget.pack(fill="both", expand=True, padx=10)
        text_widget.insert("1.0", prompt_item.prompt_text)
        
        # Language combobox
        ttk.Label(dialog, text="Idioma:").pack(anchor="w", padx=10, pady=(10, 2))
        lang_var = tk.StringVar(value=prompt_item.language)
        try:
            langs = list(getattr(config, 'SUPPORTED_LANGUAGES', [prompt_item.language]))
        except Exception:
            langs = [prompt_item.language]
        lang_combo = ttk.Combobox(dialog, textvariable=lang_var, values=langs, state="readonly")
        lang_combo.pack(fill="x", padx=10)
        
        # Retry checkbox (opcional)
        retry_var = tk.BooleanVar(value=allow_retry)
        if allow_retry:
            retry_check = ttk.Checkbutton(dialog, text="Tentar novamente após salvar", variable=retry_var)
            retry_check.pack(anchor="w", padx=10, pady=(8, 0))
        
        # Seção: Imagem do Prompt (prioridade sobre referência)
        img_frame = ttk.LabelFrame(dialog, text="Imagem do Prompt (prioridade sobre referência)")
        img_frame.pack(fill="x", padx=10, pady=8)
        img_var = tk.StringVar(value=getattr(prompt_item, 'image_path', '') or '')
        img_row = ttk.Frame(img_frame)
        img_row.pack(fill="x", padx=5, pady=5)
        ttk.Label(img_row, text="Arquivo:").pack(side="left")
        img_entry = ttk.Entry(img_row, textvariable=img_var)
        img_entry.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(img_row, text="Escolher...", command=lambda: img_var.set(filedialog.askopenfilename(title="Selecione a imagem do prompt", filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("Todos", "*.*")]) or img_var.get())).pack(side="left", padx=5)
        ttk.Button(img_row, text="Limpar", command=lambda: img_var.set("")).pack(side="left")
        
        def _open_current_image():
            p = img_var.get().strip()
            if not p:
                messagebox.showinfo("Imagem", "Nenhuma imagem selecionada.")
                return
            try:
                if os.path.exists(p):
                    try:
                        os.startfile(p)
                    except Exception:
                        webbrowser.open(f"file:///{p.replace(chr(92), '/')}" )
                else:
                    webbrowser.open(p)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao abrir imagem: {e}")
        ttk.Button(img_row, text="Abrir", command=_open_current_image).pack(side="left", padx=5)
        
        # Prévia/Link
        img_preview = ttk.Label(img_frame, text="(sem prévia)")
        img_preview.pack(anchor="w", padx=5, pady=(0,5))
        link_lbl = tk.Label(img_frame, text="", fg="blue", cursor="hand2")
        link_lbl.pack(anchor="w", padx=5, pady=(0,5))
        
        def _update_preview(*_):
            path = img_var.get().strip()
            if path:
                try:
                    im = Image.open(path)
                    im.thumbnail((120, 120))
                    photo = ImageTk.PhotoImage(im)
                    img_preview.configure(image=photo, text="")
                    dialog._img_preview_photo = photo
                    name = os.path.basename(path)
                    link_lbl.configure(text=f"Abrir: {name}")
                    link_lbl.bind("<Button-1>", lambda e: _open_current_image())
                except Exception as e:
                    img_preview.configure(image="", text=f"(erro ao pré-visualizar: {e})")
                    link_lbl.configure(text="")
            else:
                img_preview.configure(image="", text="(sem prévia)")
                link_lbl.configure(text="")
        img_var.trace_add("write", _update_preview)
        _update_preview()
        
        # Buttons
        btns = ttk.Frame(dialog)
        btns.pack(fill="x", pady=10)
        
        def _on_confirm():
            new_text = text_widget.get("1.0", tk.END).strip()
            new_lang = lang_var.get().strip() or prompt_item.language
            if not new_text:
                messagebox.showwarning("Aviso", "O texto do prompt não pode estar vazio.")
                return
            try:
                on_save(new_text, new_lang, retry_var.get() if allow_retry else False)
                # Persistir imagem do prompt no gerenciador
                try:
                    self.prompt_manager.set_prompt_image(prompt_item.id, img_var.get().strip() or None)
                except Exception as e:
                    print(f"Erro ao salvar imagem do prompt {prompt_item.id}: {e}")
                self.schedule_tree_update()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao salvar: {e}")
        
        ttk.Button(btns, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(0, 10))
        ttk.Button(btns, text="Salvar", command=_on_confirm).pack(side="right", padx=10)
    
    def start_batch_processing(self):
        """Inicia processamento em lote"""
        self.log("🚀 Iniciando processamento em lote...")
        
        # Validar credenciais
        api_key = self.api_key_entry.get().strip()
        token = self.token_entry.get().strip()
        
        self.log("🔐 Validando credenciais...")
        if not api_key or not token:
            self.log("❌ Credenciais não fornecidas", "ERROR")
            messagebox.showerror("Erro", "API Key e Token são obrigatórios")
            return
        
        # Verificar se há prompts pendentes
        pending_prompts = self.prompt_manager.get_pending_prompts()
        self.log(f"📋 Prompts pendentes encontrados: {len(pending_prompts)}")
        
        if not pending_prompts:
            self.log("⚠️ Nenhum prompt pendente para processar", "WARNING")
            messagebox.showwarning("Aviso", "Nenhum prompt pendente para processar")
            return
        
        # Capturar credenciais e formato selecionado para uso nas threads
        self.batch_api_key = api_key
        self.batch_token = token
        self.batch_aspect_choice = self.aspect_var.get() if hasattr(self, 'aspect_var') else "16:9"
        self.log(f"📐 Formato selecionado: {self.batch_aspect_choice}")
        
        # Capturar delay configurado (segundos)
        try:
            self.batch_config.request_delay = float(self.batch_delay_var.get()) if hasattr(self, 'batch_delay_var') else self.batch_config.request_delay
            self.log(f"⏳ Delay configurado: {self.batch_config.request_delay:.2f}s")
        except Exception:
            pass
        
        # Capturar retries configurados
        try:
            self.batch_config.max_retries = int(self.batch_retries_var.get()) if hasattr(self, 'batch_retries_var') else getattr(self.batch_config, 'max_retries', config.CONNECTION_RETRIES)
            self.log(f"🔁 Retries configurados: {self.batch_config.max_retries}")
        except Exception:
            pass
        
        # Permitir primeiro despacho imediatamente ao iniciar
        self.next_allowed_dispatch_at = 0
        
        # Iniciar processamento
        self.log(f"⚡ Configurando processamento para {len(pending_prompts)} prompts...")
        self.batch_processing = True
        self.progress_tracker.start_tracking(len(pending_prompts))
        try:
            self.thread_pool.resume_threads()
        except Exception:
            pass
        
        # Atualizar interface
        self.log("🔧 Atualizando controles da interface...")
        self.start_batch_button.config(state="disabled")
        self.pause_batch_button.config(state="normal")
        self.stop_batch_button.config(state="normal")
        
        # Não submeter em loop no main thread; iniciar despachante que fará a submissão incremental
        self.log("🎯 Iniciando despacho incremental de prompts...")
        if not getattr(self, 'dispatcher_running', False):
            self.schedule_dispatcher()
        # Disparar um despacho imediato leve
        try:
            self.dispatch_pending_prompts()
        except Exception as e:
            self.log(f"Erro ao despachar imediatamente: {e}", "ERROR")
        
        self.log(f"✅ Processamento iniciado com sucesso! {len(pending_prompts)} prompts em fila")
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.config(text=f"Processamento iniciado: {len(pending_prompts)} prompts")
        try:
            self.root.after(0, lambda: self.root.title(f"Iniciado — {len(pending_prompts)} prompts"))
        except Exception:
            pass
    
    def process_single_prompt_batch(self, prompt_item):
        """Processa um prompt individual no lote"""
        thread_name = threading.current_thread().name
        prompt_id = prompt_item.id
        
        self.log(f"🎬 [{thread_name}] Iniciando processamento do prompt {prompt_id}")
        
        try:
            # Marcar como processando
            self.log(f"🔄 [{thread_name}] Marcando prompt {prompt_id} como processando...")
            self.prompt_manager.update_prompt_status(prompt_item.id, PromptStatus.PROCESSING)
            
            # Preparar dados
            self.log(f"📦 [{thread_name}] Preparando dados para prompt {prompt_id}...")
            data = {
                "script": {
                    "type": "text",
                    "input": prompt_item.prompt_text
                },
                "config": {
                    "fluent": False,
                    "pad_audio": 0.0
                },
                "source_url": "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"
            }
            
            headers = dict(config.DEFAULT_HEADERS)
            
            # Selecionar endpoint conforme formato 16:9 ou 9:16 (vertical)
            use_reels = getattr(self, 'batch_aspect_choice', '16:9') == '9:16'
            endpoint = config.REELS_WEBHOOK_URL if use_reels else config.WEBHOOK_URL
            
            # Preparar dados para webhook
            if use_reels:
                webhook_data = {
                    "prompt": prompt_item.prompt_text,
                    "api_key": getattr(self, 'batch_api_key', self.api_key_entry.get().strip()),
                    "languages": [prompt_item.language],
                    "auth_token": getattr(self, 'batch_token', self.token_entry.get().strip())
                }
                # Selecionar imagem do prompt (prioridade) ou referência do lote
                prompt_img = getattr(prompt_item, 'image_path', None)
                chosen_path = prompt_img if (prompt_img and os.path.isfile(prompt_img)) else (self.batch_ref_image_path.get() if hasattr(self, 'batch_ref_image_path') else "")
                if chosen_path:
                    try:
                        with open(chosen_path, 'rb') as f:
                            b64_data = base64.b64encode(f.read()).decode('utf-8')
                        ext = os.path.splitext(chosen_path)[1].lower()
                        if ext == '.png':
                            mime = 'image/png'
                        elif ext in ('.jpg', '.jpeg'):
                            mime = 'image/jpeg'
                        elif ext == '.webp':
                            mime = 'image/webp'
                        elif ext == '.bmp':
                            mime = 'image/bmp'
                        else:
                            mime = 'application/octet-stream'
                        webhook_data["images"] = [{
                            "name": os.path.basename(chosen_path),
                            "type": mime,
                            "data": b64_data
                        }]
                        if prompt_img and os.path.isfile(prompt_img):
                            self.log(f"🖼️ [{thread_name}] Incluindo imagem do prompt no payload (9:16)")
                        else:
                            self.log(f"🖼️ [{thread_name}] Incluindo imagem de referência no payload (9:16)")
                    except Exception as e:
                        self.log(f"⚠️ [{thread_name}] Falha ao ler imagem: {e}", "WARNING")
            else:
                webhook_data = {
                    "prompt": prompt_item.prompt_text,
                    "api_key": getattr(self, 'batch_api_key', self.api_key_entry.get().strip()),
                    "token": getattr(self, 'batch_token', self.token_entry.get().strip()),
                    "languages": [prompt_item.language],
                    "auth_token": getattr(self, 'batch_token', self.token_entry.get().strip())
                }
                # Selecionar imagem do prompt (prioridade) ou referência do lote também para 16:9
                prompt_img = getattr(prompt_item, 'image_path', None)
                chosen_path = prompt_img if (prompt_img and os.path.isfile(prompt_img)) else (self.batch_ref_image_path.get() if hasattr(self, 'batch_ref_image_path') else "")
                if chosen_path:
                    try:
                        with open(chosen_path, 'rb') as f:
                            b64_data = base64.b64encode(f.read()).decode('utf-8')
                        ext = os.path.splitext(chosen_path)[1].lower()
                        if ext == '.png':
                            mime = 'image/png'
                        elif ext in ('.jpg', '.jpeg'):
                            mime = 'image/jpeg'
                        elif ext == '.webp':
                            mime = 'image/webp'
                        elif ext == '.bmp':
                            mime = 'image/bmp'
                        else:
                            mime = 'application/octet-stream'
                        webhook_data["images"] = [{
                            "name": os.path.basename(chosen_path),
                            "type": mime,
                            "data": b64_data
                        }]
                        if prompt_img and os.path.isfile(prompt_img):
                            self.log(f"🖼️ [{thread_name}] Incluindo imagem do prompt no payload (16:9)")
                        else:
                            self.log(f"🖼️ [{thread_name}] Incluindo imagem de referência no payload (16:9)")
                    except Exception as e:
                        self.log(f"⚠️ [{thread_name}] Falha ao ler imagem (16:9): {e}", "WARNING")
            
            # Fazer requisição com retry (inclui retry para erros de parsing/formato)
            self.log(f"🚀 [{thread_name}] Enviando requisição para prompt {prompt_id}...")
            start_time = time.time()
            
            max_retries = getattr(self.batch_config, 'max_retries', config.CONNECTION_RETRIES)
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        self.log(f"🔄 [{thread_name}] Tentativa {attempt + 1}/{max_retries + 1} para prompt {prompt_id}")
                        # Aguardar delay configurado antes de nova tentativa
                        try:
                            delay_between_attempts = float(getattr(self.batch_config, 'request_delay', 0.0))
                        except Exception:
                            delay_between_attempts = 0.0
                        if delay_between_attempts and delay_between_attempts > 0:
                            self.log(f"⏳ [{thread_name}] Aguardando {delay_between_attempts:.2f}s antes da próxima tentativa")
                            time.sleep(delay_between_attempts)
                        else:
                            # Fallback: manter backoff baseado em RETRY_DELAY
                            fallback = max(0.0, float(getattr(config, 'RETRY_DELAY', 1.0)) * attempt)
                            if fallback > 0:
                                self.log(f"⏳ [{thread_name}] Aguardando {fallback:.2f}s (fallback) antes da próxima tentativa")
                                time.sleep(fallback)
                    
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        data=json.dumps(webhook_data),
                        timeout=config.REQUEST_TIMEOUT
                    )
                    
                    processing_time = time.time() - start_time
                    status_code = response.status_code
                    if status_code in [200, 201]:
                        # Processar resposta já nesta tentativa; se falhar, tentar novamente
                        self.log(f"✅ [{thread_name}] Resposta HTTP OK para prompt {prompt_id} (tentativa {attempt + 1})")
                        self.log(f"📊 [{thread_name}] Status: {response.status_code}, Content-Length: {len(response.content)}")
                        self.log(f"📋 [{thread_name}] Headers: {dict(response.headers)}")
                        try:
                            response_text = response.text
                            self.log(f"📄 [{thread_name}] Resposta (primeiros 200 chars): {response_text[:200]}...")
                            # Verificar se é dados binários (vídeo)
                            if any(ord(char) < 32 and char not in '\n\r\t' for char in response_text[:100]):
                                self.log(f"🎬 [{thread_name}] Dados binários detectados para prompt {prompt_id}")
                                video_path = self.save_batch_video(response, prompt_item.id)
                                self.log(f"💾 [{thread_name}] Vídeo salvo: {video_path}")
                                return {
                                    'success': True,
                                    'video_url': f"file:///{video_path.replace(chr(92), '/')}",
                                    'processing_time': processing_time
                                }
                            else:
                                self.log(f"📝 [{thread_name}] Processando resposta de texto para prompt {prompt_id}")
                                try:
                                    response_data = response.json()
                                    video_url = response_data.get('video_url') or response_data.get('url') or response_data.get('link')
                                    if video_url:
                                        self.log(f"🎯 [{thread_name}] URL encontrada para prompt {prompt_id}: {video_url[:50]}...")
                                        return {
                                            'success': True,
                                            'video_url': video_url,
                                            'processing_time': processing_time
                                        }
                                    else:
                                        last_error = 'URL do vídeo não encontrada na resposta'
                                        self.log(f"❓ [{thread_name}] {last_error}", "WARNING")
                                        if attempt < max_retries:
                                            self.log(f"🔁 [{thread_name}] Reintentando devido a resposta sem URL (tentativa {attempt + 1}/{max_retries + 1})", "WARNING")
                                            continue
                                        return {
                                            'success': False,
                                            'error': last_error,
                                            'processing_time': processing_time
                                        }
                                except json.JSONDecodeError:
                                    self.log(f"🔍 [{thread_name}] Tentando interpretar como link direto para prompt {prompt_id}")
                                    if response_text.startswith('http'):
                                        self.log(f"🔗 [{thread_name}] Link direto encontrado para prompt {prompt_id}")
                                        return {
                                            'success': True,
                                            'video_url': response_text.strip(),
                                            'processing_time': processing_time
                                        }
                                    else:
                                        last_error = 'Formato de resposta não reconhecido'
                                        self.log(f"❌ [{thread_name}] {last_error} para prompt {prompt_id}", "ERROR")
                                        if attempt < max_retries:
                                            self.log(f"🔁 [{thread_name}] Reintentando devido a formato não reconhecido (tentativa {attempt + 1}/{max_retries + 1})", "WARNING")
                                            continue
                                        return {
                                            'success': False,
                                            'error': last_error,
                                            'processing_time': processing_time
                                        }
                        except Exception as e:
                            last_error = f'Erro ao processar resposta: {str(e)}'
                            self.log(f"⚠️ [{thread_name}] {last_error}", "WARNING")
                            if attempt < max_retries:
                                self.log(f"🔁 [{thread_name}] Reintentando devido a erro ao processar resposta (tentativa {attempt + 1}/{max_retries + 1})", "WARNING")
                                continue
                            return {
                                'success': False,
                                'error': last_error,
                                'processing_time': processing_time
                            }
                    else:
                        # HTTP não-sucesso: decidir se é caso de retry
                        retryable = (status_code == 429) or (500 <= status_code < 600)
                        if retryable and attempt < max_retries:
                            self.log(f"⚠️ [{thread_name}] HTTP {status_code} na tentativa {attempt + 1}, reintentando...", "WARNING")
                            continue
                        last_error = f'Erro HTTP {response.status_code}: {response.text[:200]}'
                        break
                    
                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        self.log(f"⏰ [{thread_name}] Timeout na tentativa {attempt + 1}, tentando novamente...", "WARNING")
                        continue
                    else:
                        raise
                except requests.exceptions.ConnectionError:
                    if attempt < max_retries:
                        self.log(f"🌐 [{thread_name}] Erro de conexão na tentativa {attempt + 1}, tentando novamente...", "WARNING")
                        continue
                    else:
                        raise
            
            # Se chegou aqui, não obteve sucesso após as tentativas
            final_time = time.time() - start_time
            error_msg = last_error or 'Falha desconhecida após tentativas'
            self.log(f"❌ [{thread_name}] {error_msg}", "ERROR")
            return {
                'success': False,
                'error': error_msg,
                'processing_time': final_time
            }
            
        except Exception as e:
            error_msg = f'Erro na requisição: {str(e)}'
            self.log(f"❌ [{thread_name}] {error_msg}", "ERROR")
            return {
                'success': False,
                'error': error_msg,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0
            }
    
    def save_batch_video(self, response, prompt_id):
        """Salva vídeo do lote automaticamente com prefixo da ordem na lista (1_, 2_, 3_, ...)"""
        # Criar pasta de downloads se não existir
        download_folder = "batch_videos"
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        # Determinar posição (ordem) do prompt na lista para prefixo
        try:
            order_index = next((idx for idx, p in enumerate(self.prompt_manager.get_all_prompts(), start=1) if p.id == prompt_id), 0)
        except Exception:
            order_index = 0
        
        # Nome do arquivo com prefixo
        base_name = f"video_{prompt_id}_{int(time.time())}.mp4"
        filename = f"{order_index}_{base_name}" if order_index else base_name
        file_path = os.path.join(download_folder, filename)
        
        # Salvar arquivo
        with open(file_path, 'wb') as file:
            file.write(response.content)
        
        return file_path

    def save_batch_video_from_url(self, video_url: str, prompt_id: str) -> str:
        """Baixa um vídeo remoto (URL) e salva no diretório batch_videos com o mesmo padrão de nomenclatura.
        Retorna o caminho salvo ou string vazia em caso de falha."""
        try:
            download_folder = "batch_videos"
            if not os.path.exists(download_folder):
                os.makedirs(download_folder)
            try:
                order_index = next((idx for idx, p in enumerate(self.prompt_manager.get_all_prompts(), start=1) if p.id == prompt_id), 0)
            except Exception:
                order_index = 0
            base_name = f"video_{prompt_id}_{int(time.time())}.mp4"
            filename = f"{order_index}_{base_name}" if order_index else base_name
            file_path = os.path.join(download_folder, filename)

            # Download com stream
            resp = requests.get(video_url, stream=True, timeout=max(30, int(getattr(config, 'REQUEST_TIMEOUT', 60))))
            resp.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return file_path
        except Exception as e:
            try:
                self.log(f"⚠️ Falha ao baixar vídeo de URL para salvar localmente: {e}", "WARNING")
            except Exception:
                pass
            return ""
    
    def _extract_last_frame(self, video_path: str) -> str:
        """Extrai o último frame de um vídeo MP4 e salva como JPG temporário.
        Retorna o caminho do JPG ou string vazia em caso de falha.
        """
        try:
            import imageio
        except Exception:
            imageio = None
        try:
            from moviepy.editor import VideoFileClip
        except Exception:
            VideoFileClip = None
        try:
            import tempfile, os
            if not os.path.isfile(video_path):
                return ""
            tmp_dir = tempfile.gettempdir()
            out_path = os.path.join(tmp_dir, f"last_frame_{os.path.basename(video_path)}.jpg")
            if VideoFileClip is not None:
                try:
                    clip = VideoFileClip(video_path)
                    t = max(0.0, clip.duration - 0.05)
                    frame = clip.get_frame(t)
                    from PIL import Image
                    img = Image.fromarray(frame)
                    img.save(out_path, format='JPEG', quality=90)
                    clip.close()
                    return out_path
                except Exception:
                    pass
            if imageio is not None:
                try:
                    reader = imageio.get_reader(video_path)
                    last = None
                    for frame in reader:
                        last = frame
                    reader.close()
                    if last is not None:
                        from PIL import Image
                        img = Image.fromarray(last)
                        img.save(out_path, format='JPEG', quality=90)
                        return out_path
                except Exception:
                    pass
            return ""
        except Exception:
            return ""
    
    def _maybe_generate_influencer_composite(self, last_frame_path: str, prompt_id: str):
        """Gera uma imagem lado-a-lado (esquerda = último frame; direita = influencer) quando o módulo
        influencer estiver habilitado. A saída será salva em batch_videos/combined/combined_<id>_<ts>.jpg"""
        try:
            if not getattr(self, 'sequential_mode', False):
                return
            if not hasattr(self, 'influencer_module_var') or not self.influencer_module_var.get():
                return
            right_path = self.influencer_image_path.get().strip() if hasattr(self, 'influencer_image_path') else ""
            if not right_path or not os.path.isfile(right_path):
                self.log("ℹ️ Módulo influencer ativo, mas nenhuma foto válida foi selecionada.")
                return
            if not last_frame_path or not os.path.isfile(last_frame_path):
                return
            # Carregar e alinhar alturas
            left_img = Image.open(last_frame_path).convert('RGB')
            right_img = Image.open(right_path).convert('RGB')
            target_h = max(left_img.height, right_img.height)
            def _resize_keep_aspect(img, target_h):
                if img.height <= 0:
                    return img
                new_w = max(1, int(img.width * (target_h / img.height)))
                return img.resize((new_w, target_h), Image.LANCZOS)
            left_res = _resize_keep_aspect(left_img, target_h)
            right_res = _resize_keep_aspect(right_img, target_h)
            total_w = left_res.width + right_res.width
            canvas = Image.new('RGB', (total_w, target_h), color=(0, 0, 0))
            canvas.paste(left_res, (0, 0))
            canvas.paste(right_res, (left_res.width, 0))
            # Salvar
            base_folder = getattr(config, 'BATCH_VIDEOS_FOLDER', 'batch_videos')
            out_dir = os.path.join(base_folder, 'combined')
            os.makedirs(out_dir, exist_ok=True)
            ts = int(time.time())
            out_path = os.path.join(out_dir, f"combined_{prompt_id}_{ts}.jpg")
            canvas.save(out_path, format='JPEG', quality=92)
            self.last_combined_image_path = out_path
            self.log(f"🖼️ Imagem combinada criada: {out_path}")
        except Exception as e:
            self.log(f"⚠️ Falha ao gerar imagem combinada do módulo influencer: {e}", "WARNING")
    
    def on_prompt_completed(self, prompt_id, result):
        """Callback chamado quando um prompt é concluído"""
        thread_name = threading.current_thread().name
        
        self.log(f"📞 [{thread_name}] Callback recebido para prompt {prompt_id}")
        
        if result['success']:
            self.log(f"✅ [{thread_name}] Prompt {prompt_id} concluído com sucesso!")
            self.prompt_manager.update_prompt_status(
                prompt_id, 
                PromptStatus.COMPLETED,
                video_url=result['video_url']
            )
            self.progress_tracker.update_progress(
                prompt_id, 
                PromptStatus.COMPLETED,
                result.get('processing_time', 0)
            )
            # Auto-save: se retornou apenas URL remota, salvar localmente com o mesmo padrão do modo binário
            try:
                video_url = result.get('video_url', '') or ''
                if video_url.startswith('http'):
                    self.log(f"⬇️ [{thread_name}] Salvando automaticamente vídeo remoto do prompt {prompt_id}...")
                    local_path = self.save_batch_video_from_url(video_url, prompt_id)
                    local_url = f"file:///{local_path.replace(os.sep, '/')}"
                    # Atualiza o prompt para apontar para o arquivo local
                    self.prompt_manager.update_prompt_status(
                        prompt_id,
                        PromptStatus.COMPLETED,
                        video_url=local_url
                    )
                    # Atualiza o resultado para que o restante do fluxo (encadeamento) use o arquivo local
                    result['video_url'] = local_url
                    self.log(f"💾 [{thread_name}] Vídeo salvo automaticamente em: {local_path}")
            except Exception as e:
                self.log(f"⚠️ [{thread_name}] Falha ao auto-salvar vídeo remoto: {e}", "WARNING")
            # Encadeamento: se modo sequencial ativo, extrair último frame e usar como referência
            try:
                if getattr(self, 'sequential_mode', False):
                    self.log(f"🧩 [{thread_name}] Modo sequencial ativo: preparando encadeamento de imagem de referência")
                    video_url = result.get('video_url', '') or ''
                    if video_url.startswith('file:///'):
                        # Vídeo local salvo pelo app
                        local_path = video_url.replace('file:///', '').replace('/', os.sep)
                        if os.path.isfile(local_path):
                            self.log(f"🎞️ [{thread_name}] Extraindo último frame do vídeo local: {os.path.basename(local_path)}")
                            img_path = self._extract_last_frame(local_path)
                            if img_path:
                                if hasattr(self, 'batch_ref_image_path'):
                                    self.batch_ref_image_path.set(img_path)
                                    self.log(f"🔗 [{thread_name}] Referência atualizada (último frame local): {img_path}")
                                self.next_allowed_dispatch_at = time.time() + max(0.0, float(getattr(self.batch_config, 'request_delay', 0.0)))
                                # Módulo influencer: gera imagem combinada
                                try:
                                    self._maybe_generate_influencer_composite(img_path, prompt_id)
                                except Exception as _e:
                                    self.log(f"⚠️ Erro ao gerar imagem combinada do influencer: {_e}", "WARNING")
                            else:
                                self.log(f"⚠️ [{thread_name}] Não foi possível extrair último frame do arquivo local", "WARNING")
                    elif video_url.startswith('http'):
                        # Vídeo remoto: baixar temporariamente e extrair último frame
                        try:
                            import tempfile
                            import requests
                            self.log(f"⬇️ [{thread_name}] Baixando vídeo remoto para encadeamento...")
                            tmp_dir = tempfile.gettempdir()
                            tmp_path = os.path.join(tmp_dir, f"tmp_batch_{prompt_id}_{int(time.time())}.mp4")
                            with requests.get(video_url, stream=True, timeout=max(10, int(getattr(config, 'REQUEST_TIMEOUT', 30)))) as r:
                                r.raise_for_status()
                                with open(tmp_path, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                            self.log(f"🎞️ [{thread_name}] Extraindo último frame do vídeo remoto baixado")
                            img_path = self._extract_last_frame(tmp_path)
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            if img_path:
                                if hasattr(self, 'batch_ref_image_path'):
                                    self.batch_ref_image_path.set(img_path)
                                    self.log(f"🔗 [{thread_name}] Referência atualizada (último frame remoto): {img_path}")
                                self.next_allowed_dispatch_at = time.time() + max(0.0, float(getattr(self.batch_config, 'request_delay', 0.0)))
                                # Módulo influencer: gera imagem combinada
                                try:
                                    self._maybe_generate_influencer_composite(img_path, prompt_id)
                                except Exception as _e:
                                    self.log(f"⚠️ Erro ao gerar imagem combinada do influencer: {_e}", "WARNING")
                            else:
                                self.log(f"⚠️ [{thread_name}] Não foi possível extrair último frame do vídeo remoto", "WARNING")
                        except Exception as de:
                            self.log(f"⚠️ [{thread_name}] Falha ao baixar vídeo remoto para encadeamento: {de}", "WARNING")
                    else:
                        self.log(f"ℹ️ [{thread_name}] URL de vídeo não reconhecida para encadeamento: {video_url}")
            except Exception as e:
                self.log(f"⚠️ [{thread_name}] Falha no encadeamento de imagem de referência: {e}", "WARNING")
        else:
            self.log(f"❌ [{thread_name}] Prompt {prompt_id} falhou: {result.get('error', 'Erro desconhecido')}", "ERROR")
            self.prompt_manager.update_prompt_status(
                prompt_id,
                PromptStatus.FAILED,
                error_message=result['error']
            )
            self.progress_tracker.update_progress(
                prompt_id,
                PromptStatus.FAILED,
                result.get('processing_time', 0)
            )
            # Pausar imediatamente em modo sequencial para evitar avanço de cenas
            if getattr(self, 'sequential_mode', False):
                self.log(f"🛑 [{thread_name}] Modo sequencial: falha detectada. Pausando o lote para que você edite o prompt ou tente novamente.", "ERROR")
                try:
                    self.root.after(0, self.pause_batch_processing)
                except Exception:
                    self.pause_batch_processing()
                # Atualiza UI e encerra callback sem despachar mais
                self.schedule_tree_update()
                return
        
        # Atualizar interface na thread principal
        self.log(f"🔄 [{thread_name}] Agendando atualização da interface")
        self.schedule_tree_update()
        
        # Verificar se processamento terminou
        pending = self.prompt_manager.get_pending_prompts()
        processing = self.prompt_manager.get_prompts_by_status(PromptStatus.PROCESSING)
        active_threads = self.thread_pool.get_active_count()
        
        self.log(f"📊 [{thread_name}] Status atual: {len(pending)} pendentes, {len(processing)} processando, {active_threads} threads ativas")
        
        if not pending and not processing:
            self.log(f"🎉 [{thread_name}] Todos os prompts foram processados!")
            self.root.after(0, self.on_batch_completed)
        else:
            self.log(f"⏳ [{thread_name}] Processamento continua...")
            # Aplicar delay pós-conclusão antes de despachar próximo(s)
            delay = getattr(self.batch_config, 'request_delay', 0.0)
            if delay and delay > 0:
                self.next_allowed_dispatch_at = time.time() + delay
                try:
                    self.root.after(int(delay * 1000), self.dispatch_pending_prompts)
                except Exception as e:
                    self.log(f"Falha ao agendar pós-conclusão, despachante cuidará do timing: {e}", "WARNING")
            else:
                # Tentar despachar imediatamente mais prompts para ocupar slots liberados
                try:
                    self.dispatch_pending_prompts()
                except Exception as e:
                    self.log(f"Erro ao despachar após conclusão: {e}", "ERROR")
    
    def on_batch_completed(self):
        """Chamado quando o lote é concluído"""
        self.batch_processing = False
        
        # Atualizar botões
        self.start_batch_button.config(state="normal")
        self.pause_batch_button.config(state="disabled")
        self.stop_batch_button.config(state="disabled")
        
        # Mostrar resumo sem diálogo modal para evitar travamento
        summary = self.progress_tracker.get_processing_summary()
        completed = summary['completed_prompts']
        failed = summary['failed_prompts']
        total = summary['total_prompts']
        try:
            rate = (completed / total * 100) if total else 0.0
        except Exception:
            rate = 0.0
        summary_text = (
            f"Processamento finalizado! Total: {total} | Concluídos: {completed} | Falharam: {failed} | Sucesso: {rate:.1f}%"
        )
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.config(text=summary_text)
        self.log("✅ " + summary_text)
        try:
            self.root.after(0, lambda: self.root.title(f"Concluído — {completed}/{total} (Sucesso {rate:.1f}%)"))
        except Exception:
            pass
    
    def pause_batch_processing(self):
        """Pausa processamento em lote"""
        self.thread_pool.stop_all_threads()
        self.batch_processing = False
        
        self.start_batch_button.config(state="normal")
        self.pause_batch_button.config(state="disabled")
        
        # Feedback não bloqueante
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.config(text="Processamento pausado")
        self.log("⏸️ Processamento pausado")
        try:
            self.root.after(0, lambda: self.root.title("Pausado — processamento em lote"))
        except Exception:
            pass
    
    def stop_batch_processing(self):
        """Para processamento em lote"""
        self.thread_pool.stop_all_threads()
        self.batch_processing = False
        
        # Marcar prompts em processamento como pendentes
        processing_prompts = self.prompt_manager.get_prompts_by_status(PromptStatus.PROCESSING)
        for prompt in processing_prompts:
            self.prompt_manager.update_prompt_status(prompt.id, PromptStatus.PENDING)
        
        self.start_batch_button.config(state="normal")
        self.pause_batch_button.config(state="disabled")
        self.stop_batch_button.config(state="disabled")
        
        self.update_prompts_tree()
        
        # Feedback não bloqueante
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.config(text="Processamento interrompido")
        self.log("🛑 Processamento interrompido")
        try:
            self.root.after(0, lambda: self.root.title("Parado — processamento em lote"))
        except Exception:
            pass
    
    def download_all_videos(self):
        """Compacta todos os vídeos concluídos em um único ZIP, salvando no local escolhido e limpando os downloads temporários"""
        completed_prompts = self.prompt_manager.get_prompts_by_status(PromptStatus.COMPLETED)
        
        if not completed_prompts:
            messagebox.showwarning("Aviso", "Nenhum vídeo concluído para baixar")
            return
        
        # Escolher arquivo ZIP de destino
        zip_save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Arquivos ZIP", "*.zip")],
            title="Salvar ZIP com todos os vídeos"
        )
        if not zip_save_path:
            return
        
        self.batch_status_label.config(text="Preparando ZIP com vídeos...")
        
        def _worker_zip():
            import zipfile, tempfile, shutil, re
            from urllib.parse import urlparse
            temp_dir = tempfile.mkdtemp(prefix="gv_videos_")
            try:
                # Mapa de ordem dos prompts (topo -> base)
                order_map = {p.id: idx + 1 for idx, p in enumerate(self.prompt_manager.get_all_prompts())}
                # Ordenar concluídos pela ordem original
                ordered_prompts = sorted(completed_prompts, key=lambda pr: order_map.get(pr.id, 10**9))
                
                downloaded_files = []
                for p in ordered_prompts:
                    url = getattr(p, 'video_url', None)
                    if not url:
                        continue
                    order_idx = order_map.get(p.id, len(downloaded_files) + 1)
                    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(p.id))
                    filename = f"{order_idx:03d}_video_{safe_id}.mp4"
                    dest_path = os.path.join(temp_dir, filename)
                    
                    try:
                        if url.startswith('file:'):
                            # Converter file URL para caminho local
                            parsed = urlparse(url)
                            local_path = parsed.path
                            if os.name == 'nt' and local_path.startswith('/'):
                                local_path = local_path.lstrip('/')
                            local_path = local_path.replace('/', os.sep)
                            shutil.copy2(local_path, dest_path)
                        else:
                            # Download remoto
                            resp = requests.get(url, stream=True, timeout=120)
                            resp.raise_for_status()
                            with open(dest_path, 'wb') as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                        downloaded_files.append(dest_path)
                    except Exception as e:
                        self.log(f"Erro ao obter vídeo {p.id}: {e}", "ERROR")
                        continue
                
                if not downloaded_files:
                    self.root.after(0, lambda: messagebox.showerror("Erro", "Não foi possível obter nenhum vídeo para zipar."))
                    return
                
                # Criar ZIP
                with zipfile.ZipFile(zip_save_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                    for f in downloaded_files:
                        zf.write(f, arcname=os.path.basename(f))
                
                # Limpeza: deletar arquivos baixados temporários
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                self.root.after(0, lambda: [
                    self.batch_status_label.config(text="✅ ZIP salvo com sucesso"),
                    messagebox.showinfo("Sucesso", f"ZIP salvo em:\n{zip_save_path}")
                ])
            except Exception as e:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
                self.root.after(0, lambda: [
                    self.batch_status_label.config(text="❌ Erro ao criar ZIP"),
                    messagebox.showerror("Erro", f"Erro ao criar ZIP: {e}")
                ])
        
        threading.Thread(target=_worker_zip, daemon=True).start()
    
    def merge_videos_button(self):
        """Inicia fluxo para unir vídeos em um único arquivo, a partir da sessão atual, ZIPs ou pasta, com logs detalhados e barra de progresso."""
        try:
            import tempfile, shutil, re, zipfile
            from urllib.parse import urlparse

            self.log("🧩 Iniciando união de vídeos...")

            use_session = messagebox.askyesnocancel(
                "Fonte de Vídeos",
                "Usar vídeos concluídos desta sessão?\nSim = usar sessão atual\nNão = selecionar arquivos ZIP/MP4 ou uma pasta"
            )
            if use_session is None:
                self.log("❎ União de vídeos cancelada pelo usuário")
                return

            temp_dir = tempfile.mkdtemp(prefix="gv_merge_")
            collected_files = []

            def natural_key(s: str):
                parts = re.split(r'(\d+)', os.path.basename(s))
                return [int(p) if p.isdigit() else p.lower() for p in parts]

            if use_session:
                self.log("🔎 Coletando vídeos concluídos da sessão atual na ordem dos prompts...")
                completed_prompts = self.prompt_manager.get_prompts_by_status(PromptStatus.COMPLETED)
                if not completed_prompts:
                    messagebox.showwarning("Aviso", "Nenhum vídeo concluído na sessão atual")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return
                order_map = {p.id: idx + 1 for idx, p in enumerate(self.prompt_manager.get_all_prompts())}
                ordered = sorted(completed_prompts, key=lambda pr: order_map.get(pr.id, 10**9))
                for p in ordered:
                    url = getattr(p, 'video_url', None)
                    if not url:
                        continue
                    order_idx = order_map.get(p.id, len(collected_files) + 1)
                    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(p.id))
                    dest_name = f"{order_idx:03d}_video_{safe_id}.mp4"
                    dest_path = os.path.join(temp_dir, dest_name)
                    try:
                        if url.startswith('file:'):
                            parsed = urlparse(url)
                            local_path = parsed.path
                            if os.name == 'nt' and local_path.startswith('/'):
                                local_path = local_path.lstrip('/')
                            local_path = local_path.replace('/', os.sep)
                            shutil.copy2(local_path, dest_path)
                        else:
                            resp = requests.get(url, stream=True, timeout=120)
                            resp.raise_for_status()
                            with open(dest_path, 'wb') as f:
                                for chunk in resp.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                        collected_files.append(dest_path)
                    except Exception as e:
                        self.log(f"Erro ao obter vídeo {p.id}: {e}", "ERROR")
                        continue
                self.log(f"📦 Vídeos coletados da sessão: {len(collected_files)}")
            else:
                self.log("📂 Selecionando arquivos ZIP/MP4 ou pasta contendo MP4s...")
                file_paths = filedialog.askopenfilenames(
                    title="Selecionar arquivos ZIP ou MP4",
                    filetypes=[("Arquivos ZIP", "*.zip"), ("Vídeos MP4", "*.mp4"), ("Todos os arquivos", "*.*")]
                )
                if not file_paths:
                    folder = filedialog.askdirectory(title="Selecionar pasta com vídeos MP4")
                    if not folder:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.log("❎ União de vídeos cancelada: nenhuma fonte selecionada")
                        return
                    # Coletar todos MP4s na pasta (apenas nível atual)
                    for name in os.listdir(folder):
                        if name.lower().endswith('.mp4'):
                            collected_files.append(os.path.join(folder, name))
                    self.log(f"📦 Vídeos coletados da pasta: {len(collected_files)}")
                else:
                    for path in file_paths:
                        if path.lower().endswith('.zip'):
                            try:
                                with zipfile.ZipFile(path, 'r') as zf:
                                    zf.extractall(temp_dir)
                            except Exception as e:
                                self.log(f"Erro ao extrair ZIP {os.path.basename(path)}: {e}", "ERROR")
                        elif path.lower().endswith('.mp4'):
                            collected_files.append(path)
                    # Após extrair, coletar todos MP4s do temp_dir também
                    for root_dir, _dirs, files in os.walk(temp_dir):
                        for name in files:
                            if name.lower().endswith('.mp4'):
                                collected_files.append(os.path.join(root_dir, name))
                    self.log(f"📦 Vídeos coletados de arquivos selecionados: {len(collected_files)}")

            # Ordenar arquivos (ordem natural por nome)
            collected_files = [f for f in collected_files if os.path.isfile(f)]
            if not collected_files:
                messagebox.showerror("Erro", "Nenhum arquivo de vídeo encontrado para unir")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            collected_files.sort(key=natural_key)
            try:
                preview_names = ", ".join(os.path.basename(f) for f in collected_files[:5])
                more = "" if len(collected_files) <= 5 else f" ... (+{len(collected_files)-5})"
                self.log(f"🧮 Ordem de união: {preview_names}{more}")
            except Exception:
                pass

            # Escolher destino
            out_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("Vídeos MP4", "*.mp4")],
                title="Salvar vídeo unido como..."
            )
            if not out_path:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.log("❎ União de vídeos cancelada: destino não escolhido")
                return

            # Preparar barra de progresso
            try:
                self.batch_progress.config(mode='determinate', maximum=100, value=0)
                self.batch_progress_label.config(text="Unindo vídeos: 0%")
            except Exception:
                pass
            self.batch_status_label.config(text="Unindo vídeos... isso pode levar alguns minutos")

            def _worker_merge(files, output_path, work_dir):
                try:
                    # Import tardio
                    from moviepy.editor import VideoFileClip, concatenate_videoclips
                    try:
                        from proglog import ProgressBarLogger
                    except Exception:
                        ProgressBarLogger = None

                    self.log(f"🔧 Preparando {len(files)} clipes para união...")

                    clips = []
                    for idx, fpath in enumerate(files, start=1):
                        try:
                            self.log(f"📥 Abrindo clipe {idx}/{len(files)}: {os.path.basename(fpath)}")
                            clip = VideoFileClip(fpath)
                            # Mitigar avisos de último frame incompleto: recorta ~1 frame do final (mín. 40-50ms)
                            try:
                                fps = float(getattr(clip, "fps", 0) or 0) or 24.0
                                epsilon = max(0.05, 1.0 / fps)  # pelo menos um frame
                                if getattr(clip, "duration", None) and clip.duration > epsilon:
                                    clip = clip.subclip(0, clip.duration - epsilon)
                            except Exception as _e:
                                # Em caso de falha no ajuste, segue com o clipe original
                                pass
                            clips.append(clip)
                        except Exception as e:
                            self.log(f"Ignorando arquivo inválido: {fpath} ({e})", "WARNING")
                    if not clips:
                        self.root.after(0, lambda: [
                            self.batch_status_label.config(text="❌ Nenhum clipe válido para unir"),
                            messagebox.showerror("Erro", "Nenhum clipe válido encontrado para unir")
                        ])
                        return

                    # Info de duração
                    try:
                        total_dur = sum([c.duration or 0 for c in clips])
                        self.log(f"⏱️ Duração total aproximada dos clipes: {total_dur:.1f}s")
                    except Exception:
                        pass

                    self.log("🧵 Concatenando clipes (compose)...")
                    final = concatenate_videoclips(clips, method='compose')

                    # Callback de progresso do MoviePy
                    def on_progress(pct, elapsed, eta):
                        try:
                            self.root.after(0, lambda: [
                                self.batch_progress.config(value=max(0, min(100, int(pct)))),
                                self.batch_progress_label.config(text=f"Unindo vídeos: {int(pct)}%"),
                                self.batch_status_label.config(text=f"Unindo... {int(pct)}% | ⏱ {int(elapsed)}s, ETA {int(eta)}s")
                            ])
                        except Exception:
                            pass

                    logger_obj = None
                    if ProgressBarLogger is not None:
                        class TkMergeLogger(ProgressBarLogger):
                            def __init__(self, cb):
                                super().__init__()
                                self._cb = cb
                            def callback(self, **changes):
                                try:
                                    tbar = self.state.get('bars', {}).get('t')
                                    if tbar and tbar.get('total'):
                                        idx = tbar.get('index') or 0
                                        total = tbar.get('total') or 1
                                        elapsed = tbar.get('elapsed') or 0
                                        eta = tbar.get('eta') or 0
                                        pct = (idx / total) * 100.0
                                        self._cb(pct, elapsed, eta)
                                except Exception:
                                    pass
                        logger_obj = TkMergeLogger(on_progress)

                    self.log("💾 Escrevendo arquivo de saída (libx264/aac)...")
                    write_kwargs = dict(codec='libx264', audio_codec='aac')
                    try:
                        # logger_obj pode ser None; o MoviePy aceita None
                        final.write_videofile(output_path, logger=logger_obj, verbose=False, **write_kwargs)
                    except Exception as e:
                        # Tentar novamente sem logger e verbose
                        self.log(f"Tentativa com logger falhou: {e}. Repetindo sem logger...", "WARNING")
                        final.write_videofile(output_path, **write_kwargs)

                    # Fechamento cuidadoso
                    try:
                        final.close()
                    except Exception:
                        pass
                    for c in clips:
                        try:
                            c.close()
                        except Exception:
                            pass

                    shutil.rmtree(work_dir, ignore_errors=True)

                    self.root.after(0, lambda: [
                        self.batch_progress.config(value=100),
                        self.batch_progress_label.config(text="Unindo vídeos: 100%"),
                        self.batch_status_label.config(text="✅ Vídeo unido salvo com sucesso"),
                        messagebox.showinfo("Sucesso", f"Vídeo salvo em:\n{output_path}")
                    ])
                except ImportError:
                    self.root.after(0, lambda: [
                        self.batch_status_label.config(text="❌ Dependência ausente (moviepy)"),
                        messagebox.showerror("Erro", "Dependência ausente: moviepy. Instale as dependências e tente novamente.")
                    ])
                except Exception as e:
                    shutil.rmtree(work_dir, ignore_errors=True)
                    self.root.after(0, lambda: [
                        self.batch_status_label.config(text="❌ Erro ao unir vídeos"),
                        messagebox.showerror("Erro", f"Erro ao unir vídeos: {e}")
                    ])

            thread = threading.Thread(target=_worker_merge, args=(collected_files, out_path, temp_dir), daemon=True)
            thread.start()
            self.log(f"🚀 Thread de união iniciada: {thread.name}")
        except Exception as e:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            self.log(f"❌ Erro ao iniciar união de vídeos: {e}", "ERROR")
            messagebox.showerror("Erro", f"Erro ao iniciar união de vídeos: {e}")

    def update_batch_ui(self):
        """Atualiza interface do lote periodicamente"""
        # Evitar reentrância/overlap caso timers se sobreponham
        if getattr(self, '_update_batch_ui_executing', False):
            self.root.after(self.ui_update_interval, self.update_batch_ui)
            return
        self._update_batch_ui_executing = True
        try:
            if hasattr(self, 'batch_progress'):
                # Atualizar progresso
                summary = self.progress_tracker.get_processing_summary()
                
                if summary['total_prompts'] > 0:
                    progress_percent = summary['progress_percentage']
                    
                    # Atualizar barra de progresso de forma suave
                    current_value = self.batch_progress['value']
                    if abs(current_value - progress_percent) > 0.1:
                        self.batch_progress['value'] = progress_percent
                    
                    completed = summary['completed_prompts']
                    failed = summary['failed_prompts']
                    total = summary['total_prompts']
                    
                    # Atualizar label de progresso
                    progress_text = f"{completed + failed}/{total} ({progress_percent:.1f}%)"
                    if self.batch_progress_label.cget('text') != progress_text:
                        self.batch_progress_label.config(text=progress_text)
                    
                    # Status com mais detalhes
                    if self.batch_processing:
                        active_threads = self.thread_pool.get_active_count()
                        pending_count = len(self.prompt_manager.get_pending_prompts())
                        status_text = f"Processando... ({active_threads} threads, {pending_count} na fila)"
                        
                        # Adicionar tempo estimado se disponível
                        if summary.get('estimated_remaining'):
                            eta = summary['estimated_remaining']
                            eta_str = f"{int(eta.total_seconds()//60)}:{int(eta.total_seconds()%60):02d}"
                            status_text += f" - ETA: {eta_str}"
                            
                        self.batch_status_label.config(text=status_text)
                    else:
                        if completed + failed == total and total > 0:
                            elapsed = summary.get('elapsed_time')
                            if elapsed:
                                elapsed_str = f"{int(elapsed.total_seconds()//60)}:{int(elapsed.total_seconds()%60):02d}"
                                self.batch_status_label.config(text=f"Concluído em {elapsed_str}")
                            else:
                                self.batch_status_label.config(text="Processamento concluído")
                        else:
                            self.batch_status_label.config(text="Pronto para processar")
                else:
                    self.batch_progress['value'] = 0
                    self.batch_progress_label.config(text="0/0 (0%)")
                    self.batch_status_label.config(text="Pronto para processar")
                    
                # Forçar atualização da interface
                # Habilitar/desabilitar botão "Limpar Lista de Prompts" conforme estado
                try:
                    if hasattr(self, 'clear_prompt_list_button'):
                        should_disable = self.batch_processing or self.thread_pool.get_active_count() > 0
                        self.clear_prompt_list_button.config(state=("disabled" if should_disable else "normal"))
                except Exception:
                    pass
                self.root.update_idletasks()
                
        except Exception as e:
            # Log erro mas não interromper atualização
            self.log(f"⚠️ Erro na atualização da UI: {str(e)}", "WARNING")
        finally:
            # Marcar como concluído e reagendar próxima atualização
            self._update_batch_ui_executing = False
            self.root.after(self.ui_update_interval, self.update_batch_ui)

def main():
    root = tk.Tk()
    
    # Configurar ícone e propriedades da janela
    try:
        root.iconbitmap(default='icon.ico')  # Se tiver ícone
    except:
        pass
    
    # Centralizar janela
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    app = VideoGeneratorApp(root)
    
    # Configurar fechamento da aplicação
    def on_closing():
        if app.batch_processing:
            if messagebox.askokcancel("Fechar", "Processamento em andamento. Deseja realmente fechar?"):
                app.thread_pool.stop_all_threads()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()