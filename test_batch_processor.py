"""
Testes unitários para o sistema de processamento em lote
"""

import unittest
import threading
import time
from datetime import datetime, timedelta
from batch_processor import (
    PromptItem, PromptStatus, BatchConfiguration,
    PromptManager, ThreadPoolManager, ProgressTracker
)


class TestPromptItem(unittest.TestCase):
    """Testes para a classe PromptItem"""
    
    def test_prompt_item_creation(self):
        """Testa criação de PromptItem"""
        prompt = PromptItem(
            id="test123",
            prompt_text="Test prompt",
            language="pt"
        )
        
        self.assertEqual(prompt.id, "test123")
        self.assertEqual(prompt.prompt_text, "Test prompt")
        self.assertEqual(prompt.language, "pt")
        self.assertEqual(prompt.status, PromptStatus.PENDING)
        self.assertIsInstance(prompt.created_at, datetime)
    
    def test_prompt_item_auto_id(self):
        """Testa geração automática de ID"""
        prompt = PromptItem(
            id="",
            prompt_text="Test prompt",
            language="pt"
        )
        
        self.assertIsNotNone(prompt.id)
        self.assertGreater(len(prompt.id), 0)


class TestPromptManager(unittest.TestCase):
    """Testes para a classe PromptManager"""
    
    def setUp(self):
        """Configuração inicial para cada teste"""
        self.manager = PromptManager()
    
    def test_add_single_prompt(self):
        """Testa adição de prompt individual"""
        prompt_id = self.manager.add_single_prompt("Test prompt", "pt")
        
        self.assertIsNotNone(prompt_id)
        self.assertEqual(len(self.manager.prompts), 1)
        self.assertEqual(self.manager.prompts[0].prompt_text, "Test prompt")
        self.assertEqual(self.manager.prompts[0].language, "pt")
    
    def test_add_prompts_from_text(self):
        """Testa adição de múltiplos prompts"""
        text = "Prompt 1\nPrompt 2\nPrompt 3"
        count = self.manager.add_prompts_from_text(text, "en")
        
        self.assertEqual(count, 3)
        self.assertEqual(len(self.manager.prompts), 3)
        self.assertEqual(self.manager.prompts[0].prompt_text, "Prompt 1")
        self.assertEqual(self.manager.prompts[1].language, "en")
    
    def test_limit_50_prompts(self):
        """Testa limite de 50 prompts"""
        # Adicionar 50 prompts
        for i in range(50):
            self.manager.add_single_prompt(f"Prompt {i}", "pt")
        
        # Tentar adicionar mais um
        result = self.manager.add_single_prompt("Extra prompt", "pt")
        
        self.assertIsNone(result)
        self.assertEqual(len(self.manager.prompts), 50)
    
    def test_remove_prompt(self):
        """Testa remoção de prompt"""
        prompt_id = self.manager.add_single_prompt("Test prompt", "pt")
        
        result = self.manager.remove_prompt(prompt_id)
        
        self.assertTrue(result)
        self.assertEqual(len(self.manager.prompts), 0)
    
    def test_update_prompt_status(self):
        """Testa atualização de status"""
        prompt_id = self.manager.add_single_prompt("Test prompt", "pt")
        
        self.manager.update_prompt_status(
            prompt_id, 
            PromptStatus.COMPLETED, 
            video_url="http://example.com/video.mp4"
        )
        
        prompt = self.manager.prompts[0]
        self.assertEqual(prompt.status, PromptStatus.COMPLETED)
        self.assertEqual(prompt.video_url, "http://example.com/video.mp4")
        self.assertIsNotNone(prompt.completed_at)
    
    def test_get_pending_prompts(self):
        """Testa busca de prompts pendentes"""
        # Adicionar prompts com diferentes status
        id1 = self.manager.add_single_prompt("Prompt 1", "pt")
        id2 = self.manager.add_single_prompt("Prompt 2", "pt")
        id3 = self.manager.add_single_prompt("Prompt 3", "pt")
        
        self.manager.update_prompt_status(id2, PromptStatus.COMPLETED)
        
        pending = self.manager.get_pending_prompts()
        
        self.assertEqual(len(pending), 2)
        self.assertIn(id1, [p.id for p in pending])
        self.assertIn(id3, [p.id for p in pending])


class TestThreadPoolManager(unittest.TestCase):
    """Testes para a classe ThreadPoolManager"""
    
    def setUp(self):
        """Configuração inicial para cada teste"""
        self.manager = ThreadPoolManager(max_threads=2)
        self.results = []
    
    def test_thread_pool_creation(self):
        """Testa criação do pool de threads"""
        self.assertEqual(self.manager.max_threads, 2)
        self.assertEqual(self.manager.get_active_count(), 0)
    
    def test_submit_prompt(self):
        """Testa submissão de prompt para processamento"""
        prompt = PromptItem(id="test1", prompt_text="Test", language="pt")
        
        def mock_process(prompt_item):
            time.sleep(0.1)  # Simular processamento
            return {"success": True}
        
        def callback(prompt_id, result):
            self.results.append((prompt_id, result))
        
        self.manager.submit_prompt(prompt, mock_process, callback)
        
        # Aguardar processamento
        time.sleep(0.2)
        
        self.assertEqual(len(self.results), 1)
        self.assertEqual(self.results[0][0], "test1")
        self.assertTrue(self.results[0][1]["success"])
    
    def test_max_threads_limit(self):
        """Testa limite de threads simultâneas"""
        prompts = [
            PromptItem(id=f"test{i}", prompt_text=f"Test {i}", language="pt")
            for i in range(5)
        ]
        
        def slow_process(prompt_item):
            time.sleep(0.2)
            return {"success": True}
        
        # Submeter 5 prompts (mais que o limite de 2)
        for prompt in prompts:
            self.manager.submit_prompt(prompt, slow_process)
        
        # Verificar que não mais que 2 threads estão ativas
        time.sleep(0.05)  # Dar tempo para threads iniciarem
        active_count = self.manager.get_active_count()
        self.assertLessEqual(active_count, 2)
    
    def test_update_max_threads(self):
        """Testa atualização do número máximo de threads"""
        self.manager.update_max_threads(5)
        self.assertEqual(self.manager.max_threads, 5)
        
        # Testar limite inválido
        self.manager.update_max_threads(15)  # Acima do limite
        self.assertEqual(self.manager.max_threads, 5)  # Não deve mudar


class TestProgressTracker(unittest.TestCase):
    """Testes para a classe ProgressTracker"""
    
    def setUp(self):
        """Configuração inicial para cada teste"""
        self.tracker = ProgressTracker()
    
    def test_start_tracking(self):
        """Testa início do tracking"""
        self.tracker.start_tracking(10)
        
        self.assertEqual(self.tracker.total_prompts, 10)
        self.assertEqual(self.tracker.completed_prompts, 0)
        self.assertEqual(self.tracker.failed_prompts, 0)
        self.assertIsNotNone(self.tracker.start_time)
    
    def test_update_progress(self):
        """Testa atualização de progresso"""
        self.tracker.start_tracking(5)
        
        self.tracker.update_progress("test1", PromptStatus.COMPLETED, 2.5)
        self.tracker.update_progress("test2", PromptStatus.FAILED)
        
        self.assertEqual(self.tracker.completed_prompts, 1)
        self.assertEqual(self.tracker.failed_prompts, 1)
        self.assertEqual(len(self.tracker.processing_times), 1)
        self.assertEqual(self.tracker.processing_times[0], 2.5)
    
    def test_progress_percentage(self):
        """Testa cálculo de porcentagem"""
        self.tracker.start_tracking(10)
        
        self.tracker.update_progress("test1", PromptStatus.COMPLETED)
        self.tracker.update_progress("test2", PromptStatus.COMPLETED)
        self.tracker.update_progress("test3", PromptStatus.FAILED)
        
        percentage = self.tracker.get_progress_percentage()
        self.assertEqual(percentage, 30.0)  # 3 de 10 = 30%
    
    def test_estimated_time_remaining(self):
        """Testa estimativa de tempo restante"""
        self.tracker.start_tracking(4)
        
        # Simular 2 prompts completados com tempos conhecidos
        self.tracker.update_progress("test1", PromptStatus.COMPLETED, 2.0)
        self.tracker.update_progress("test2", PromptStatus.COMPLETED, 3.0)
        
        estimated = self.tracker.get_estimated_time_remaining()
        
        self.assertIsNotNone(estimated)
        # Tempo médio: 2.5s, restam 2 prompts = 5s estimados
        self.assertAlmostEqual(estimated.total_seconds(), 5.0, places=1)
    
    def test_processing_summary(self):
        """Testa resumo de processamento"""
        self.tracker.start_tracking(5)
        
        self.tracker.update_progress("test1", PromptStatus.COMPLETED, 2.0)
        self.tracker.update_progress("test2", PromptStatus.FAILED)
        
        summary = self.tracker.get_processing_summary()
        
        self.assertEqual(summary['total_prompts'], 5)
        self.assertEqual(summary['completed_prompts'], 1)
        self.assertEqual(summary['failed_prompts'], 1)
        self.assertEqual(summary['progress_percentage'], 40.0)
        self.assertIsNotNone(summary['elapsed_time'])


if __name__ == '__main__':
    unittest.main()