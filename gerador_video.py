import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import json
import threading
import time
import webbrowser
import base64
import os
from urllib.parse import urlparse

class VideoGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Vídeo D-ID")
        self.root.geometry("650x800")
        
        # Variáveis
        self.video_id = None
        self.video_url = None
        self.checking = False
        self.check_thread = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # API Key
        ttk.Label(main_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(main_frame, width=50, show="*")
        self.api_key_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Prompt
        ttk.Label(main_frame, text="Prompt:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=5)
        self.prompt_text = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        self.prompt_text.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Idioma
        ttk.Label(main_frame, text="Idioma:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.language_var = tk.StringVar(value="pt")
        language_combo = ttk.Combobox(main_frame, textvariable=self.language_var, 
                                    values=["pt", "en", "es", "fr", "de", "it"], state="readonly")
        language_combo.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Botão Gerar
        self.generate_button = ttk.Button(main_frame, text="Gerar Vídeo", command=self.generate_video)
        self.generate_button.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_label = ttk.Label(main_frame, text="Pronto para gerar vídeo", foreground="green")
        self.status_label.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Frame para botões do vídeo
        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        self.open_button = ttk.Button(video_frame, text="Abrir no Navegador", 
                                    command=self.open_in_browser, state="disabled")
        self.open_button.grid(row=0, column=0, padx=5)
        
        self.download_button = ttk.Button(video_frame, text="Baixar Vídeo", 
                                        command=self.download_video, state="disabled")
        self.download_button.grid(row=0, column=1, padx=5)
        
        # URL do vídeo
        ttk.Label(main_frame, text="URL do Vídeo:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.url_text = scrolledtext.ScrolledText(main_frame, width=50, height=3)
        self.url_text.grid(row=7, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Frame para preview do vídeo
        preview_frame = ttk.LabelFrame(main_frame, text="Preview do Vídeo", padding="10")
        preview_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.video_info_label = ttk.Label(preview_frame, text="Nenhum vídeo carregado")
        self.video_info_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        self.play_button = ttk.Button(preview_frame, text="▶ Reproduzir", 
                                    command=self.play_video, state="disabled")
        self.play_button.grid(row=1, column=0, padx=5, pady=5)
        
        self.video_status_label = ttk.Label(preview_frame, text="")
        self.video_status_label.grid(row=1, column=1, padx=5, pady=5)
        
        # Configurar redimensionamento
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def generate_video(self):
        # Validar campos
        api_key = self.api_key_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        
        if not api_key:
            messagebox.showerror("Erro", "Por favor, insira a API Key")
            return
        
        if not prompt:
            messagebox.showerror("Erro", "Por favor, insira o prompt")
            return
        
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
        self.generate_button.config(state="disabled")
        self.progress.start()
        self.update_status("Enviando requisição...")
        
        # Enviar requisição em thread separada
        thread = threading.Thread(target=self.send_request, args=(data,), daemon=True)
        thread.start()
    
    def send_request(self, data):
        try:
            headers = {
                "Content-Type": "application/json",
                "Referer": "https://vetaia.cloud/",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
            }
            
            # Preparar dados para enviar ao webhook
            webhook_data = {
                "prompt": data.get("script", {}).get("input", ""),
                "api_key": self.api_key_entry.get().strip(),
                "languages": [self.language_var.get()],
                "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb2RpZ28iOiIiLCJpYXQiOjE3NTY5MzA2MDh9.LVfTl4kYrRjR9a89EZny_vkmzsAId9jRpLAmvodiexI"
            }
            
            # Mostrar no console o POST que será enviado
            print("=== POST REQUEST ===")
            print(f"URL: https://n8n.srv943626.hstgr.cloud/webhook/9a20b730-2fd6-4d92-9c62-3e7c288e241b")
            print(f"Headers: {json.dumps(headers, indent=2)}")
            print(f"Data: {json.dumps(webhook_data, indent=2)}")
            print("===================")
            
            # Fazer a requisição POST para o webhook
            response = requests.post(
                "https://n8n.srv943626.hstgr.cloud/webhook/9a20b730-2fd6-4d92-9c62-3e7c288e241b",
                headers=headers,
                data=json.dumps(webhook_data)
            )
            
            # Verificar a resposta
            if response.status_code == 200 or response.status_code == 201:
                self.update_status("Requisição enviada com sucesso para o webhook!")
                
                # Verificar se a resposta contém dados binários
                try:
                    # Tentar decodificar como texto
                    response_text = response.text
                    
                    # Verificar se contém caracteres não imprimíveis (dados binários)
                    if any(ord(char) < 32 and char not in '\n\r\t' for char in response_text[:100]):
                        print("Resposta contém dados binários - possível arquivo de vídeo")
                        
                        # Verificar headers para tipo de conteúdo
                        content_type = response.headers.get('content-type', '').lower()
                        if 'video' in content_type or 'application/octet-stream' in content_type:
                            # É um arquivo de vídeo - salvar diretamente
                            self.save_video_from_response(response)
                        else:
                            self.update_status("Resposta em formato binário não reconhecido")
                            print(f"Content-Type: {content_type}")
                    else:
                        # Resposta é texto - processar normalmente
                        print(f"Resposta: {response_text}")
                        
                        # Processar resposta do webhook
                        try:
                            response_data = response.json()
                            video_url = response_data.get('video_url') or response_data.get('url') or response_data.get('link')
                            
                            if video_url:
                                self.video_url = video_url
                                self.update_video_info(video_url)
                                self.update_status("Vídeo gerado com sucesso!")
                            else:
                                self.update_status("Vídeo enviado para processamento. Aguarde o retorno.")
                                
                        except json.JSONDecodeError:
                            # Se não for JSON, pode ser um link direto
                            if response_text.startswith('http'):
                                self.video_url = response_text.strip()
                                self.update_video_info(self.video_url)
                                self.update_status("Vídeo gerado com sucesso!")
                            else:
                                self.update_status("Resposta recebida, mas formato não reconhecido.")
                                
                except Exception as e:
                    print(f"Erro ao processar resposta: {str(e)}")
                    self.update_status("Erro ao processar resposta do servidor")
                        
            else:
                error_msg = f"Erro na requisição: {response.status_code} - {response.text[:200]}..."
                self.update_status(error_msg)
                print(error_msg)
        except Exception as e:
            error_msg = f"Erro ao enviar requisição: {str(e)}"
            self.update_status(error_msg)
            print(error_msg)
        finally:
            # Reabilitar botão e parar progress
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

def main():
    root = tk.Tk()
    app = VideoGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()