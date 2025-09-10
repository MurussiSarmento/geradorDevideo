# Design Document - Sistema de Processamento em Lote de Vídeos

## Overview

O sistema de processamento em lote será implementado como uma extensão da aplicação atual, adicionando uma nova interface com abas que permite gerenciar múltiplos prompts e processá-los simultaneamente. A arquitetura manterá a compatibilidade com o sistema atual enquanto adiciona capacidades avançadas de gerenciamento de threads e monitoramento de progresso.

## Architecture

### Componentes Principais

```
VideoGeneratorApp (Existente)
├── BatchProcessorManager (Novo)
│   ├── PromptManager
│   ├── ThreadPoolManager  
│   ├── ProgressTracker
│   └── ResultsManager
├── BatchUI (Novo)
│   ├── PromptListWidget
│   ├── ConfigurationPanel
│   ├── ProgressPanel
│   └── ResultsPanel
└── PersistenceManager (Novo)
    ├── SessionSaver
    └── SessionLoader
```

### Fluxo de Dados

```
User Input → PromptManager → ThreadPoolManager → API Requests
     ↓              ↓              ↓              ↓
UI Updates ← ProgressTracker ← Response Handler ← API Response
     ↓
ResultsManager → File System / UI Display
```

## Components and Interfaces

### 1. BatchProcessorManager

**Responsabilidade**: Coordenar todo o processamento em lote

```python
class BatchProcessorManager:
    def __init__(self, api_key: str, token: str, max_threads: int = 3):
        self.prompt_manager = PromptManager()
        self.thread_pool = ThreadPoolManager(max_threads)
        self.progress_tracker = ProgressTracker()
        self.results_manager = ResultsManager()
        
    def start_batch_processing(self) -> None:
        """Inicia o processamento em lote de todos os prompts"""
        
    def pause_processing(self) -> None:
        """Pausa o processamento atual"""
        
    def resume_processing(self) -> None:
        """Retoma o processamento pausado"""
        
    def stop_processing(self) -> None:
        """Para completamente o processamento"""
```

### 2. PromptManager

**Responsabilidade**: Gerenciar a lista de prompts e seus estados

```python
class PromptManager:
    def __init__(self):
        self.prompts: List[PromptItem] = []
        
    def add_prompts_from_text(self, text: str, delimiter: str = '\n') -> int:
        """Adiciona prompts a partir de texto, retorna quantidade adicionada"""
        
    def add_single_prompt(self, prompt: str, language: str = 'pt') -> str:
        """Adiciona um prompt individual, retorna ID"""
        
    def remove_prompt(self, prompt_id: str) -> bool:
        """Remove um prompt específico"""
        
    def update_prompt_status(self, prompt_id: str, status: PromptStatus) -> None:
        """Atualiza o status de um prompt"""
        
    def get_pending_prompts(self) -> List[PromptItem]:
        """Retorna prompts pendentes de processamento"""
```

### 3. ThreadPoolManager

**Responsabilidade**: Gerenciar threads de processamento simultâneo

```python
class ThreadPoolManager:
    def __init__(self, max_threads: int = 3):
        self.max_threads = max_threads
        self.active_threads: Dict[str, threading.Thread] = {}
        self.thread_semaphore = threading.Semaphore(max_threads)
        
    def submit_prompt(self, prompt_item: PromptItem, callback: Callable) -> None:
        """Submete um prompt para processamento"""
        
    def update_max_threads(self, new_max: int) -> None:
        """Atualiza o número máximo de threads"""
        
    def get_active_count(self) -> int:
        """Retorna número de threads ativas"""
```

### 4. ProgressTracker

**Responsabilidade**: Rastrear e calcular progresso do processamento

```python
class ProgressTracker:
    def __init__(self):
        self.total_prompts = 0
        self.completed_prompts = 0
        self.failed_prompts = 0
        self.start_time = None
        
    def update_progress(self, prompt_id: str, status: PromptStatus) -> None:
        """Atualiza progresso baseado no status do prompt"""
        
    def get_progress_percentage(self) -> float:
        """Retorna porcentagem de conclusão"""
        
    def get_estimated_time_remaining(self) -> Optional[timedelta]:
        """Calcula tempo estimado restante"""
        
    def get_processing_summary(self) -> Dict[str, Any]:
        """Retorna resumo completo do processamento"""
```

### 5. BatchUI

**Responsabilidade**: Interface gráfica para funcionalidades de lote

```python
class BatchUI:
    def __init__(self, parent_frame, batch_manager: BatchProcessorManager):
        self.batch_manager = batch_manager
        self.setup_batch_interface(parent_frame)
        
    def setup_batch_interface(self, parent) -> None:
        """Configura toda a interface de lote"""
        
    def update_prompt_list_display(self) -> None:
        """Atualiza a exibição da lista de prompts"""
        
    def update_progress_display(self) -> None:
        """Atualiza displays de progresso"""
        
    def show_results_summary(self) -> None:
        """Exibe resumo final dos resultados"""
```

## Data Models

### PromptItem

```python
@dataclass
class PromptItem:
    id: str
    prompt_text: str
    language: str
    status: PromptStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
```

### PromptStatus

```python
class PromptStatus(Enum):
    PENDING = "Pendente"
    PROCESSING = "Processando"
    COMPLETED = "Concluído"
    FAILED = "Erro"
    PAUSED = "Pausado"
```

### BatchConfiguration

```python
@dataclass
class BatchConfiguration:
    max_threads: int = 3
    default_language: str = 'pt'
    request_delay: float = 0.5
    request_timeout: int = 300
    max_retries: int = 2
    auto_download: bool = False
    download_folder: Optional[str] = None
```

## Error Handling

### Estratégias de Tratamento de Erro

1. **Erro de Rede**: Retry automático com backoff exponencial
2. **Erro de API**: Log do erro e marcação do prompt como falhado
3. **Erro de Thread**: Liberação da thread e resubmissão do prompt
4. **Erro de Interface**: Notificação ao usuário sem interromper processamento

### Sistema de Retry

```python
class RetryManager:
    def __init__(self, max_retries: int = 2, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        
    def should_retry(self, prompt_item: PromptItem, error: Exception) -> bool:
        """Determina se deve tentar novamente baseado no erro"""
        
    def get_retry_delay(self, attempt: int) -> float:
        """Calcula delay para próxima tentativa (backoff exponencial)"""
```

## Testing Strategy

### Testes Unitários

1. **PromptManager**: Testes de adição, remoção e atualização de prompts
2. **ThreadPoolManager**: Testes de gerenciamento de threads e limites
3. **ProgressTracker**: Testes de cálculos de progresso e tempo
4. **PersistenceManager**: Testes de salvamento e carregamento de sessões

### Testes de Integração

1. **Processamento Completo**: Teste end-to-end com múltiplos prompts
2. **Gerenciamento de Threads**: Teste com diferentes números de threads
3. **Recuperação de Sessão**: Teste de persistência e recuperação
4. **Tratamento de Erros**: Teste com falhas simuladas de API

### Testes de Performance

1. **Carga Máxima**: Teste com 50 prompts simultâneos
2. **Uso de Memória**: Monitoramento durante processamento longo
3. **Responsividade da UI**: Teste de interface durante processamento intenso

## Implementation Plan

### Fase 1: Estrutura Base (Semana 1)
- Implementar classes base (PromptManager, ThreadPoolManager)
- Criar modelos de dados (PromptItem, PromptStatus)
- Implementar interface básica com abas

### Fase 2: Processamento Core (Semana 2)
- Implementar BatchProcessorManager
- Integrar com API existente
- Implementar sistema de threads

### Fase 3: Interface e Monitoramento (Semana 3)
- Completar BatchUI com todos os componentes
- Implementar ProgressTracker
- Adicionar displays de progresso em tempo real

### Fase 4: Persistência e Configuração (Semana 4)
- Implementar PersistenceManager
- Adicionar configurações avançadas
- Implementar sistema de retry

### Fase 5: Testes e Refinamento (Semana 5)
- Testes completos de todas as funcionalidades
- Otimizações de performance
- Documentação e exemplos de uso

## Security Considerations

1. **Validação de Input**: Sanitização de prompts antes do processamento
2. **Rate Limiting**: Respeitar limites da API para evitar bloqueios
3. **Armazenamento Seguro**: Criptografia de dados sensíveis salvos
4. **Thread Safety**: Sincronização adequada entre threads
5. **Resource Management**: Limpeza adequada de recursos em caso de erro

## Performance Optimizations

1. **Connection Pooling**: Reutilizar conexões HTTP
2. **Memory Management**: Limpeza periódica de dados antigos
3. **UI Updates**: Batch updates para evitar travamentos
4. **Lazy Loading**: Carregar resultados sob demanda
5. **Caching**: Cache de configurações e metadados