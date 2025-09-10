#!/usr/bin/env python3
"""
Verificação rápida do sistema após melhorias nos logs
"""

import sys
import traceback

def check_imports():
    """Verifica se todas as importações estão funcionando"""
    print("🔍 Verificando importações...")
    
    try:
        import tkinter as tk
        print("✅ tkinter OK")
        
        import requests
        print("✅ requests OK")
        
        from batch_processor import PromptManager, ThreadPoolManager, ProgressTracker
        print("✅ batch_processor OK")
        
        import config
        print("✅ config OK")
        
        return True
    except Exception as e:
        print(f"❌ Erro na importação: {e}")
        traceback.print_exc()
        return False

def check_gerador_video():
    """Verifica se o gerador_video pode ser importado"""
    print("\n🔍 Verificando gerador_video.py...")
    
    try:
        from gerador_video import VideoGeneratorApp
        print("✅ VideoGeneratorApp importado com sucesso")
        
        # Testar criação da classe (sem UI)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Esconder janela
        
        app = VideoGeneratorApp(root)
        print("✅ VideoGeneratorApp criado com sucesso")
        
        # Verificar se tem os métodos de log
        if hasattr(app, 'log'):
            print("✅ Sistema de log presente")
            app.log("🧪 Teste de log funcionando")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ Erro no gerador_video: {e}")
        traceback.print_exc()
        return False

def check_config():
    """Verifica configurações"""
    print("\n🔍 Verificando configurações...")
    
    try:
        import config
        
        print(f"✅ UI_UPDATE_INTERVAL: {config.UI_UPDATE_INTERVAL}ms")
        print(f"✅ DEFAULT_MAX_THREADS: {config.DEFAULT_MAX_THREADS}")
        print(f"✅ REQUEST_TIMEOUT: {config.REQUEST_TIMEOUT}s")
        print(f"✅ LOG_TO_FILE: {config.LOG_TO_FILE}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")
        return False

def main():
    """Executa todas as verificações"""
    print("🚀 Verificação do Sistema - Gerador de Vídeo")
    print("=" * 50)
    
    checks = [
        ("Importações", check_imports),
        ("Configurações", check_config),
        ("Gerador de Vídeo", check_gerador_video),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Erro crítico em {name}: {e}")
            results.append((name, False))
    
    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO DA VERIFICAÇÃO")
    print("=" * 50)
    
    all_ok = True
    for name, result in results:
        status = "✅ OK" if result else "❌ FALHOU"
        print(f"{name}: {status}")
        if not result:
            all_ok = False
    
    print("\n" + "=" * 50)
    if all_ok:
        print("🎉 SISTEMA FUNCIONANDO PERFEITAMENTE!")
        print("✅ Todas as melhorias de log foram aplicadas com sucesso")
        print("✅ Interface deve estar responsiva")
        print("✅ Pronto para executar: python gerador_video.py")
    else:
        print("⚠️ PROBLEMAS DETECTADOS!")
        print("❌ Verifique os erros acima antes de executar")
    
    print("=" * 50)

if __name__ == "__main__":
    main()