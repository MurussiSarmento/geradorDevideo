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
        
        if not api_key or not token:
            self.log("❌ API Key e Token são necessários para teste", "ERROR")
            messagebox.showerror("Erro", "Preencha API Key e Token primeiro")
            return
        
        # Teste simples
        test_data = {
            "prompt": "Hello, this is a test",
            "api_key": api_key,
            "token": token,
            "languages": ["en"],
            "auth_token": token
        }
        
        def test_in_thread():
            try:
                self.log("🚀 Enviando requisição de teste...")
                response = requests.post(
                    config.WEBHOOK_URL,
                    headers=config.DEFAULT_HEADERS,
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
        
        # Iniciar timer de atualização da interface do lote após tudo estar criado
        self.root.after(1000, self.update_batch_ui)
    
    def setup_individual_tab(self, parent):
        # Frame principal
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # API Key
        ttk.Label(main_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(main_frame, width=50, show="*")
        self.api_key_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Token
        ttk.Label(main_frame, text="Token:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.token_entry = ttk.Entry(main_frame, width=50, show="*")
        self.token_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Prompt
        ttk.Label(main_frame, text="Prompt:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
        self.prompt_text = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        self.prompt_text.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Idioma
        ttk.Label(main_frame, text="Idioma:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.language_var = tk.StringVar(value="pt")
        language_combo = ttk.Combobox(main_frame, textvariable=self.language_var, 
                                    values=["pt", "en", "es", "fr", "de", "it"], state="readonly")
        language_combo.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Botão Gerar
        self.generate_button = ttk.Button(main_frame, text="Gerar Vídeo", command=self.generate_video)
        self.generate_button.grid(row=4, column=0, columnspan=3, pady=20)
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.status_label = ttk.Label(main_frame, text="Pronto para gerar vídeo", foreground="green")
        self.status_label.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Frame para botões do vídeo
        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
        self.open_button = ttk.Button(video_frame, text="Abrir no Navegador", 
                                    command=self.open_in_browser, state="disabled")
        self.open_button.grid(row=0, column=0, padx=5)
        
        self.download_button = ttk.Button(video_frame, text="Baixar Vídeo", 
                                        command=self.download_video, state="disabled")
        self.download_button.grid(row=0, column=1, padx=5)
        
        # URL do vídeo
        ttk.Label(main_frame, text="URL do Vídeo:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.url_text = scrolledtext.ScrolledText(main_frame, width=50, height=3)
        self.url_text.grid(row=8, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Frame para preview do vídeo
        preview_frame = ttk.LabelFrame(main_frame, text="Preview do Vídeo", padding="10")
        preview_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
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
        columns = ("ID", "Prompt", "Idioma", "Status", "URL")
        self.prompts_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        # Configurar colunas
        self.prompts_tree.heading("ID", text="ID")
        self.prompts_tree.heading("Prompt", text="Prompt")
        self.prompts_tree.heading("Idioma", text="Idioma")
        self.prompts_tree.heading("Status", text="Status")
        self.prompts_tree.heading("URL", text="URL do Vídeo")
        
        self.prompts_tree.column("ID", width=80)
        self.prompts_tree.column("Prompt", width=300)
        self.prompts_tree.column("Idioma", width=80)
        self.prompts_tree.column("Status", width=100)
        self.prompts_tree.column("URL", width=200)
        
        # Scrollbar para treeview
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.prompts_tree.yview)
        self.prompts_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.prompts_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        # Menu de contexto para treeview
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Remover Prompt", command=self.remove_selected_prompt)
        self.tree_menu.add_command(label="Abrir URL", command=self.open_selected_url)
        self.tree_menu.add_command(label="Copiar URL", command=self.copy_selected_url)
        
        self.prompts_tree.bind("<Button-3>", self.show_tree_menu)
        
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
        
        self.log(f"📝 Validando campos... Prompt: {len(prompt)} chars")
        
        if not api_key:
            self.log("❌ API Key não fornecida", "ERROR")
            messagebox.showerror("Erro", "Por favor, insira a API Key")
            return
        
        if not token:
            self.log("❌ Token não fornecido", "ERROR")
            messagebox.showerror("Erro", "Por favor, insira o Token")
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
            headers = {
                "Content-Type": "application/json",
                "Referer": "https://vetaia.cloud/",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
            }
            
            self.log(f"🔧 [{thread_name}] Headers configurados")
            
            # Preparar dados para enviar ao webhook
            webhook_data = {
                "prompt": data.get("script", {}).get("input", ""),
                "api_key": self.api_key_entry.get().strip(),
                "token": self.token_entry.get().strip(),
                "languages": [self.language_var.get()],
                "auth_token": self.token_entry.get().strip()
            }
            
            # Log detalhado da requisição
            self.log(f"📤 [{thread_name}] Preparando POST para webhook...")
            self.log(f"🔗 URL: https://n8n.srv943626.hstgr.cloud/webhook/9a20b730-2fd6-4d92-9c62-3e7c288e241b")
            self.log(f"📦 Payload size: {len(json.dumps(webhook_data))} bytes")
            self.log(f"🌐 Language: {webhook_data.get('languages', ['unknown'])}")
            
            # Fazer a requisição POST para o webhook
            self.log(f"🚀 [{thread_name}] Enviando requisição...")
            start_time = time.time()
            
            response = requests.post(
                "https://n8n.srv943626.hstgr.cloud/webhook/9a20b730-2fd6-4d92-9c62-3e7c288e241b",
                headers=headers,
                data=json.dumps(webhook_data),
                timeout=30  # Timeout de 30 segundos
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
            response = requests.get(url, stream=True)
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
        if capacity <= 0:
            return
        to_submit = pending[:capacity]
        if not to_submit:
            return
        self.log(f"🚚 Despachando {len(to_submit)} prompts pendentes (capacidade: {capacity}, ativas: {active})")
        for prompt in to_submit:
            # Marcar como PROCESSING antes de submeter para evitar duplicidade
            try:
                self.prompt_manager.update_prompt_status(prompt.id, PromptStatus.PROCESSING)
                self.root.after(0, self.update_prompts_tree)
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
    
    def add_prompts_to_batch(self):
        """Adiciona prompts da área de texto à lista de processamento"""
        text = self.batch_prompts_text.get(1.0, tk.END).strip()
        if not text:
            messagebox.showwarning("Aviso", "Nenhum prompt para adicionar")
            return
        
        language = self.batch_language_var.get()
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
        for prompt in self.prompt_manager.get_all_prompts():
            # Truncar prompt se muito longo
            display_prompt = prompt.prompt_text[:50] + "..." if len(prompt.prompt_text) > 50 else prompt.prompt_text
            
            # URL truncada
            display_url = ""
            if prompt.video_url:
                display_url = prompt.video_url[:30] + "..." if len(prompt.video_url) > 30 else prompt.video_url
            
            self.prompts_tree.insert("", "end", values=(
                prompt.id,
                display_prompt,
                prompt.language,
                prompt.status.value,
                display_url
            ))
    
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
        prompt_id = self.prompts_tree.item(item)['values'][0]
        
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
        prompt_id = values[0]
        
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
        prompt_id = values[0]
        
        # Buscar prompt completo
        for prompt in self.prompt_manager.get_all_prompts():
            if prompt.id == prompt_id and prompt.video_url:
                self.root.clipboard_clear()
                self.root.clipboard_append(prompt.video_url)
                messagebox.showinfo("Sucesso", "URL copiada para área de transferência")
                return
        
        messagebox.showwarning("Aviso", "Nenhuma URL disponível para este prompt")
    
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
        
        # Processar cada prompt
        self.log(f"🎯 Submetendo {len(pending_prompts)} prompts para processamento...")
        for i, prompt in enumerate(pending_prompts, 1):
            self.log(f"📤 [{i}/{len(pending_prompts)}] Submetendo prompt {prompt.id}: {prompt.prompt_text[:30]}...")
            # Marcar como PROCESSING antes de submeter para evitar duplicidade com o despachante
            try:
                self.prompt_manager.update_prompt_status(prompt.id, PromptStatus.PROCESSING)
                self.root.after(0, self.update_prompts_tree)
            except Exception:
                pass
            self.thread_pool.submit_prompt(
                prompt, 
                self.process_single_prompt_batch,
                self.on_prompt_completed
            )
            # Pequeno delay para evitar sobrecarga
            time.sleep(0.1)
        
        # Iniciar despachante automático
        if not getattr(self, 'dispatcher_running', False):
            self.schedule_dispatcher()
        
        self.log(f"✅ Processamento iniciado com sucesso! {len(pending_prompts)} prompts em fila")
        messagebox.showinfo("Iniciado", f"Processamento iniciado para {len(pending_prompts)} prompts")
    
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
            
            headers = {
                "Content-Type": "application/json",
                "Referer": "https://vetaia.cloud/",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
            }
            
            # Preparar dados para webhook
            webhook_data = {
                "prompt": prompt_item.prompt_text,
                "api_key": self.api_key_entry.get().strip(),
                "token": self.token_entry.get().strip(),
                "languages": [prompt_item.language],
                "auth_token": self.token_entry.get().strip()
            }
            
            # Fazer requisição com retry
            self.log(f"🚀 [{thread_name}] Enviando requisição para prompt {prompt_id}...")
            start_time = time.time()
            
            max_retries = config.CONNECTION_RETRIES
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        self.log(f"🔄 [{thread_name}] Tentativa {attempt + 1}/{max_retries + 1} para prompt {prompt_id}")
                        time.sleep(config.RETRY_DELAY * attempt)
                    
                    response = requests.post(
                        config.WEBHOOK_URL,
                        headers=headers,
                        data=json.dumps(webhook_data),
                        timeout=config.REQUEST_TIMEOUT
                    )
                    
                    processing_time = time.time() - start_time
                    self.log(f"⏱️ [{thread_name}] Prompt {prompt_id} processado em {processing_time:.2f}s")
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
            
            if response.status_code in [200, 201]:
                self.log(f"✅ [{thread_name}] Resposta bem-sucedida para prompt {prompt_id}")
                self.log(f"📊 [{thread_name}] Status: {response.status_code}, Content-Length: {len(response.content)}")
                self.log(f"📋 [{thread_name}] Headers: {dict(response.headers)}")
                
                # Processar resposta
                try:
                    response_text = response.text
                    self.log(f"📄 [{thread_name}] Resposta (primeiros 200 chars): {response_text[:200]}...")
                    
                    # Verificar se é dados binários (vídeo)
                    if any(ord(char) < 32 and char not in '\n\r\t' for char in response_text[:100]):
                        self.log(f"🎬 [{thread_name}] Dados binários detectados para prompt {prompt_id}")
                        # É um arquivo de vídeo - salvar
                        video_path = self.save_batch_video(response, prompt_item.id)
                        self.log(f"💾 [{thread_name}] Vídeo salvo: {video_path}")
                        return {
                            'success': True,
                            'video_url': f"file:///{video_path.replace(chr(92), '/')}",
                            'processing_time': processing_time
                        }
                    else:
                        self.log(f"📝 [{thread_name}] Processando resposta de texto para prompt {prompt_id}")
                        # Resposta é texto
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
                                self.log(f"❓ [{thread_name}] URL não encontrada para prompt {prompt_id}", "WARNING")
                                return {
                                    'success': False,
                                    'error': 'URL do vídeo não encontrada na resposta',
                                    'processing_time': processing_time
                                }
                        except json.JSONDecodeError:
                            self.log(f"🔍 [{thread_name}] Tentando interpretar como link direto para prompt {prompt_id}")
                            # Pode ser um link direto
                            if response_text.startswith('http'):
                                self.log(f"🔗 [{thread_name}] Link direto encontrado para prompt {prompt_id}")
                                return {
                                    'success': True,
                                    'video_url': response_text.strip(),
                                    'processing_time': processing_time
                                }
                            else:
                                self.log(f"❌ [{thread_name}] Formato não reconhecido para prompt {prompt_id}", "ERROR")
                                return {
                                    'success': False,
                                    'error': 'Formato de resposta não reconhecido',
                                    'processing_time': processing_time
                                }
                                
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Erro ao processar resposta: {str(e)}',
                        'processing_time': processing_time
                    }
            else:
                error_msg = f'Erro HTTP {response.status_code}: {response.text[:200]}'
                self.log(f"❌ [{thread_name}] {error_msg}", "ERROR")
                return {
                    'success': False,
                    'error': error_msg,
                    'processing_time': processing_time
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
        """Salva vídeo do lote automaticamente"""
        # Criar pasta de downloads se não existir
        download_folder = "batch_videos"
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        # Nome do arquivo
        filename = f"video_{prompt_id}_{int(time.time())}.mp4"
        file_path = os.path.join(download_folder, filename)
        
        # Salvar arquivo
        with open(file_path, 'wb') as file:
            file.write(response.content)
        
        return file_path
    
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
        
        # Atualizar interface na thread principal
        self.log(f"🔄 [{thread_name}] Agendando atualização da interface")
        self.root.after(0, self.update_prompts_tree)
        
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
        
        # Mostrar resumo
        summary = self.progress_tracker.get_processing_summary()
        completed = summary['completed_prompts']
        failed = summary['failed_prompts']
        total = summary['total_prompts']
        
        messagebox.showinfo(
            "Processamento Concluído",
            f"Processamento finalizado!\n\n"
            f"Total: {total}\n"
            f"Concluídos: {completed}\n"
            f"Falharam: {failed}\n"
            f"Taxa de sucesso: {(completed/total*100):.1f}%"
        )
    
    def pause_batch_processing(self):
        """Pausa processamento em lote"""
        self.thread_pool.stop_all_threads()
        self.batch_processing = False
        
        self.start_batch_button.config(state="normal")
        self.pause_batch_button.config(state="disabled")
        
        messagebox.showinfo("Pausado", "Processamento pausado")
    
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
        messagebox.showinfo("Parado", "Processamento interrompido")
    
    def download_all_videos(self):
        """Baixa todos os vídeos concluídos"""
        completed_prompts = self.prompt_manager.get_prompts_by_status(PromptStatus.COMPLETED)
        
        if not completed_prompts:
            messagebox.showwarning("Aviso", "Nenhum vídeo concluído para baixar")
            return
        
        # Escolher pasta de destino
        folder_path = filedialog.askdirectory(title="Escolher pasta para downloads")
        if not folder_path:
            return
        
        # Baixar cada vídeo
        downloaded = 0
        for prompt in completed_prompts:
            if prompt.video_url and not prompt.video_url.startswith('file:'):
                try:
                    filename = f"video_{prompt.id}.mp4"
                    file_path = os.path.join(folder_path, filename)
                    
                    response = requests.get(prompt.video_url, stream=True)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                file.write(chunk)
                    
                    downloaded += 1
                except Exception as e:
                    print(f"Erro ao baixar vídeo {prompt.id}: {str(e)}")
        
        messagebox.showinfo("Download Concluído", f"{downloaded} vídeos baixados com sucesso!")
    
    def update_batch_ui(self):
        """Atualiza interface do lote periodicamente"""
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
                self.root.update_idletasks()
                
        except Exception as e:
            # Log erro mas não interromper atualização
            self.log(f"⚠️ Erro na atualização da UI: {str(e)}", "WARNING")
        
        # Reagendar próxima atualização
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