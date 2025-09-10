"""
Sistema de Processamento em Lote de Vídeos
Módulo contendo todas as classes necessárias para processamento em lote
"""

import threading
import time
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Callable, Any
import uuid
import os


class PromptStatus(Enum):
    """Estados possíveis de um prompt durante o processamento"""
    PENDING = "Pendente"
    PROCESSING = "Processando"
    COMPLETED = "Concluído"
    FAILED = "Erro"
    PAUSED = "Pausado"


@dataclass
class PromptItem:
    """Representa um prompt individual com todos os seus metadados"""
    id: str
    prompt_text: str
    language: str
    status: PromptStatus = PromptStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        """Gera ID único se não fornecido"""
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


@dataclass
class BatchConfiguration:
    """Configurações para processamento em lote"""
    max_threads: int = 3
    default_language: str = 'pt'
    request_delay: float = 0.5
    request_timeout: int = 300
    max_retries: int = 2
    auto_download: bool = False
    download_folder: Optional[str] = None


class PromptManager:
    """Gerencia a lista de prompts e seus estados"""
    
    def __init__(self):
        self.prompts: List[PromptItem] = []
        self._lock = threading.Lock()
    
    def add_prompts_from_text(self, text: str, language: str = 'pt', delimiter: str = '\n') -> int:
        """
        Adiciona prompts a partir de texto
        
        Args:
            text: Texto contendo prompts separados por delimitador
            language: Idioma padrão para os prompts
            delimiter: Separador entre prompts
            
        Returns:
            Número de prompts adicionados
        """
        with self._lock:
            lines = [line.strip() for line in text.split(delimiter) if line.strip()]
            
            # Verificar limite de 50 prompts
            current_count = len(self.prompts)
            available_slots = 50 - current_count
            
            if len(lines) > available_slots:
                lines = lines[:available_slots]
            
            added_count = 0
            for line in lines:
                if line:  # Ignorar linhas vazias
                    prompt_item = PromptItem(
                        id=str(uuid.uuid4())[:8],
                        prompt_text=line,
                        language=language
                    )
                    self.prompts.append(prompt_item)
                    added_count += 1
            
            return added_count
    
    def add_single_prompt(self, prompt: str, language: str = 'pt') -> Optional[str]:
        """
        Adiciona um prompt individual
        
        Args:
            prompt: Texto do prompt
            language: Idioma do prompt
            
        Returns:
            ID do prompt adicionado ou None se limite excedido
        """
        with self._lock:
            if len(self.prompts) >= 50:
                return None
            
            prompt_item = PromptItem(
                id=str(uuid.uuid4())[:8],
                prompt_text=prompt,
                language=language
            )
            self.prompts.append(prompt_item)
            return prompt_item.id
    
    def remove_prompt(self, prompt_id: str) -> bool:
        """
        Remove um prompt específico
        
        Args:
            prompt_id: ID do prompt a ser removido
            
        Returns:
            True se removido com sucesso
        """
        with self._lock:
            for i, prompt in enumerate(self.prompts):
                if prompt.id == prompt_id:
                    del self.prompts[i]
                    return True
            return False
    
    def update_prompt_status(self, prompt_id: str, status: PromptStatus, 
                           video_url: Optional[str] = None, 
                           error_message: Optional[str] = None) -> None:
        """
        Atualiza o status de um prompt
        
        Args:
            prompt_id: ID do prompt
            status: Novo status
            video_url: URL do vídeo se concluído
            error_message: Mensagem de erro se falhou
        """
        with self._lock:
            for prompt in self.prompts:
                if prompt.id == prompt_id:
                    prompt.status = status
                    
                    if status == PromptStatus.PROCESSING:
                        prompt.started_at = datetime.now()
                    elif status in [PromptStatus.COMPLETED, PromptStatus.FAILED]:
                        prompt.completed_at = datetime.now()
                    
                    if video_url:
                        prompt.video_url = video_url
                    if error_message:
                        prompt.error_message = error_message
                    
                    break
    
    def get_pending_prompts(self) -> List[PromptItem]:
        """Retorna prompts pendentes de processamento"""
        with self._lock:
            return [p for p in self.prompts if p.status == PromptStatus.PENDING]
    
    def get_all_prompts(self) -> List[PromptItem]:
        """Retorna todos os prompts"""
        with self._lock:
            return self.prompts.copy()
    
    def clear_all_prompts(self) -> None:
        """Remove todos os prompts"""
        with self._lock:
            self.prompts.clear()
    
    def get_prompts_by_status(self, status: PromptStatus) -> List[PromptItem]:
        """Retorna prompts com status específico"""
        with self._lock:
            return [p for p in self.prompts if p.status == status]


class ThreadPoolManager:
    """Gerencia threads de processamento simultâneo"""
    
    def __init__(self, max_threads: int = 3):
        self.max_threads = max_threads
        self.active_threads: Dict[str, threading.Thread] = {}
        self.thread_semaphore = threading.Semaphore(max_threads)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
    
    def submit_prompt(self, prompt_item: PromptItem, process_function: Callable, 
                     callback: Optional[Callable] = None) -> None:
        """
        Submete um prompt para processamento
        
        Args:
            prompt_item: Item do prompt a ser processado
            process_function: Função que processará o prompt
            callback: Função de callback para notificação de conclusão
        """
        def worker():
            try:
                # Aguardar semáforo (slot de thread disponível)
                self.thread_semaphore.acquire()
                
                if self._stop_event.is_set():
                    return
                
                # Registrar thread ativa
                with self._lock:
                    self.active_threads[prompt_item.id] = threading.current_thread()
                
                # Processar prompt
                result = process_function(prompt_item)
                
                # Chamar callback se fornecido
                if callback:
                    callback(prompt_item.id, result)
                    
            except Exception as e:
                if callback:
                    callback(prompt_item.id, {'error': str(e)})
            finally:
                # Limpar thread ativa
                with self._lock:
                    self.active_threads.pop(prompt_item.id, None)
                
                # Liberar semáforo
                self.thread_semaphore.release()
        
        # Iniciar thread
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def update_max_threads(self, new_max: int) -> None:
        """
        Atualiza o número máximo de threads
        
        Args:
            new_max: Novo número máximo de threads
        """
        if 1 <= new_max <= 10:
            self.max_threads = new_max
            # Criar novo semáforo com novo limite
            current_value = self.thread_semaphore._value
            self.thread_semaphore = threading.Semaphore(new_max)
            # Ajustar valor atual se necessário
            if current_value > new_max:
                for _ in range(current_value - new_max):
                    self.thread_semaphore.acquire()
    
    def get_active_count(self) -> int:
        """Retorna número de threads ativas"""
        with self._lock:
            return len(self.active_threads)
    
    def stop_all_threads(self) -> None:
        """Para todas as threads"""
        self._stop_event.set()
        
        # Aguardar threads terminarem
        with self._lock:
            threads = list(self.active_threads.values())
        
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=5)
    
    def resume_threads(self) -> None:
        """Retoma processamento de threads"""
        self._stop_event.clear()


class ProgressTracker:
    """Rastreia e calcula progresso do processamento"""
    
    def __init__(self):
        self.total_prompts = 0
        self.completed_prompts = 0
        self.failed_prompts = 0
        self.start_time: Optional[datetime] = None
        self._lock = threading.Lock()
        self.processing_times: List[float] = []
    
    def start_tracking(self, total_prompts: int) -> None:
        """Inicia o tracking de progresso"""
        with self._lock:
            self.total_prompts = total_prompts
            self.completed_prompts = 0
            self.failed_prompts = 0
            self.start_time = datetime.now()
            self.processing_times.clear()
    
    def update_progress(self, prompt_id: str, status: PromptStatus, 
                       processing_time: Optional[float] = None) -> None:
        """
        Atualiza progresso baseado no status do prompt
        
        Args:
            prompt_id: ID do prompt
            status: Novo status do prompt
            processing_time: Tempo de processamento em segundos
        """
        with self._lock:
            if status == PromptStatus.COMPLETED:
                self.completed_prompts += 1
                if processing_time:
                    self.processing_times.append(processing_time)
            elif status == PromptStatus.FAILED:
                self.failed_prompts += 1
    
    def get_progress_percentage(self) -> float:
        """Retorna porcentagem de conclusão"""
        with self._lock:
            if self.total_prompts == 0:
                return 0.0
            processed = self.completed_prompts + self.failed_prompts
            return (processed / self.total_prompts) * 100
    
    def get_estimated_time_remaining(self) -> Optional[timedelta]:
        """Calcula tempo estimado restante"""
        with self._lock:
            if not self.processing_times or self.total_prompts == 0:
                return None
            
            avg_time = sum(self.processing_times) / len(self.processing_times)
            remaining_prompts = self.total_prompts - self.completed_prompts - self.failed_prompts
            
            if remaining_prompts <= 0:
                return timedelta(0)
            
            estimated_seconds = remaining_prompts * avg_time
            return timedelta(seconds=estimated_seconds)
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Retorna resumo completo do processamento"""
        with self._lock:
            elapsed_time = None
            if self.start_time:
                elapsed_time = datetime.now() - self.start_time
            
            return {
                'total_prompts': self.total_prompts,
                'completed_prompts': self.completed_prompts,
                'failed_prompts': self.failed_prompts,
                'progress_percentage': self.get_progress_percentage(),
                'elapsed_time': elapsed_time,
                'estimated_remaining': self.get_estimated_time_remaining(),
                'average_processing_time': sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
            }