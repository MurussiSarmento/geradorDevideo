"""
Configurações da aplicação para melhor performance e responsividade
"""

# Configurações de UI
UI_UPDATE_INTERVAL = 500  # ms - intervalo de atualização da interface
LOG_MAX_LINES = 1000      # máximo de linhas no log
AUTO_SCROLL_LOGS = True   # auto-scroll dos logs

# Configurações de Threading
DEFAULT_MAX_THREADS = 2   # threads padrão para processamento
MAX_ALLOWED_THREADS = 10  # máximo de threads permitidas
THREAD_TIMEOUT = 600      # timeout em segundos para requisições (10 minutos)

# Configurações de Rede
REQUEST_TIMEOUT = 120     # timeout para requisições HTTP (2 minutos)
CONNECTION_RETRIES = 3    # tentativas de reconexão
RETRY_DELAY = 2.0        # delay entre tentativas (segundos)

# Configurações de Logging
LOG_LEVEL = "INFO"        # nível de log (DEBUG, INFO, WARNING, ERROR)
LOG_TO_FILE = True        # salvar logs em arquivo
LOG_FILE = "gerador_video.log"

# Configurações de Performance
BATCH_SUBMIT_DELAY = 0.1  # delay entre submissões de prompts (segundos)
UI_FORCE_UPDATE = True    # forçar atualização da UI
MEMORY_MONITORING = True  # monitorar uso de memória

# URLs e Endpoints
WEBHOOK_URL = "https://n8n.srv943626.hstgr.cloud/webhook/9a20b730-2fd6-4d92-9c62-3e7c288e241b"
# Endpoint específico para geração vertical 9:16 (Reels Premium)
REELS_WEBHOOK_URL = "https://n8n.srv943626.hstgr.cloud/webhook/testevetareelspremium"
DEFAULT_PRESENTER_URL = "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"

# Endpoint do provedor Gemini (defina seu webhook/endpoint aqui; deixe vazio se não usar)
GEMINI_WEBHOOK_URL = ""  # ex.: "https://seu-servidor.com/webhook/gemini-video"

# Configurações de Arquivos
BATCH_VIDEOS_FOLDER = "batch_videos"
SUPPORTED_LANGUAGES = ["pt", "en", "es", "fr", "de", "it"]
MAX_PROMPTS_PER_BATCH = 50

# Headers HTTP padrão
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://vetaia.cloud",
    "Referer": "https://vetaia.cloud/",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Accept": "*/*"
}

# Headers para o provedor Gemini (mínimos e neutros)
GEMINI_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}