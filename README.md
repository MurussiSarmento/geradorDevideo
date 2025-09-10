# Gerador de Vídeo D-ID - Individual e Lote

Uma aplicação desktop completa para geração de vídeos usando inteligência artificial através da API D-ID. O programa oferece uma interface gráfica intuitiva para criar vídeos a partir de prompts de texto, com suporte tanto para geração individual quanto **processamento em lote de até 50 vídeos simultaneamente**.

## 🚀 Funcionalidades

### Geração Individual
- **Interface Gráfica Completa**: Campo API Key, Token, editor de prompt
- **Suporte a Múltiplos Idiomas**: PT, EN, ES, FR, DE, IT
- **Preview e Reprodução**: Visualização no navegador e player local
- **Download Inteligente**: Com barra de progresso e detecção automática
- **Threading Assíncrono**: Interface não trava durante processamento

### 🆕 Processamento em Lote
- **Processamento Simultâneo**: Até 10 threads paralelas configuráveis
- **Gerenciamento de Prompts**: Até 50 prompts por lote
- **Controle de Progresso**: Acompanhamento em tempo real com estatísticas
- **Carregamento de Arquivos**: Importar prompts de arquivos .txt
- **Download Automático**: Salvar vídeos automaticamente em pasta organizada
- **Controles Avançados**: Pausar, parar e retomar processamento
- **Interface em Abas**: Separação clara entre individual e lote
- **Menu de Contexto**: Ações rápidas na lista de prompts
- **Estatísticas Detalhadas**: Taxa de sucesso, tempo estimado, progresso

## 📋 Requisitos

### Para Executar o Código Python
- Python 3.7 ou superior
- Bibliotecas Python (ver `requirements.txt`):
  - `requests==2.31.0` - Para requisições HTTP
  - `Pillow==10.0.0` - Para processamento de imagens
  - `tkinter` - Interface gráfica (incluída no Python)

### Para Executar o Executável
- Windows 10/11 (64-bit)
- Nenhuma dependência adicional necessária

## 🛠️ Instalação e Execução

### Opção 1: Código Python (Recomendado para desenvolvimento)
1. Clone ou baixe este repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```
3. Execute o programa:
```bash
python gerador_video.py
```

### Opção 2: Script de Inicialização
Execute o arquivo `iniciar.bat` que automaticamente roda o código Python.

### Opção 3: Executável Standalone
1. Execute `executar.bat` (se disponível)
2. Ou execute diretamente `dist/GeradorDeVideo.exe`

## 📖 Como Usar

### Aba Individual
1. **Configuração**: Insira API Key e Token da D-ID
2. **Criação**: Digite o prompt e selecione o idioma
3. **Geração**: Clique em "Gerar Vídeo"
4. **Resultado**: Abra no navegador, reproduza ou baixe

### 🆕 Aba Processamento em Lote

#### 1. Configuração do Lote
- **Threads Simultâneas**: Configure de 1 a 10 (padrão: 3)
- **Idioma Padrão**: Selecione o idioma para todos os prompts

#### 2. Adição de Prompts
- **Digitação Manual**: Digite prompts (um por linha)
- **Carregamento de Arquivo**: Use "Carregar de Arquivo" para importar .txt
- **Adição à Lista**: Clique em "Adicionar à Lista" (máximo 50 prompts)

#### 3. Gerenciamento da Lista
- **Visualização**: Lista com ID, Prompt, Idioma, Status e URL
- **Menu de Contexto**: Clique direito para remover, abrir URL ou copiar
- **Estados**: Pendente → Processando → Concluído/Erro

#### 4. Processamento
- **Iniciar**: Clique em "Iniciar Processamento"
- **Controlar**: Use "Pausar" ou "Parar" conforme necessário
- **Acompanhar**: Veja progresso em tempo real e threads ativas

#### 5. Resultados
- **Download Individual**: Menu de contexto → "Abrir URL"
- **Download em Massa**: Botão "Baixar Todos"
- **Organização**: Vídeos salvos em pasta `batch_videos/`

## 📁 Arquivos de Exemplo

### `prompts_exemplo.txt`
Arquivo com 10 prompts de exemplo para testar o processamento em lote:
```
Olá, bem-vindos ao nosso canal! Hoje vamos falar sobre inteligência artificial.
Apresento a vocês nossa nova linha de produtos inovadores.
Obrigado por assistir nosso vídeo. Não esqueçam de se inscrever no canal.
...
```

## 🔧 Arquitetura Técnica

### Estrutura do Projeto
```
gerador-de-video/
├── gerador_video.py          # Aplicação principal com interface em abas
├── batch_processor.py        # Sistema de processamento em lote
├── test_batch_processor.py   # Testes unitários do sistema de lote
├── requirements.txt          # Dependências Python
├── prompts_exemplo.txt       # Arquivo de exemplo com prompts
├── iniciar.bat              # Script de inicialização Python
├── executar.bat             # Script para executar o .exe
└── README.md               # Esta documentação
```

### 🆕 Classes do Sistema de Lote

#### `PromptManager`
- Gerencia até 50 prompts com estados individuais
- Thread-safe para operações simultâneas
- Métodos: add, remove, update_status, get_by_status

#### `ThreadPoolManager`
- Controla threads de processamento (1-10 simultâneas)
- Semáforo para limitar recursos
- Métodos: submit_prompt, update_max_threads, stop_all

#### `ProgressTracker`
- Calcula progresso, tempo estimado e estatísticas
- Rastreia tempos de processamento individuais
- Métodos: start_tracking, update_progress, get_summary

#### `PromptItem`
- Representa um prompt individual com metadados
- Estados: PENDING, PROCESSING, COMPLETED, FAILED, PAUSED
- Timestamps: created_at, started_at, completed_at

### Fluxo do Processamento em Lote
1. **Configuração**: Definir threads e idioma padrão
2. **Adição**: Carregar prompts (manual ou arquivo)
3. **Validação**: Verificar credenciais e prompts pendentes
4. **Distribuição**: Submeter prompts para threads disponíveis
5. **Processamento**: Requisições paralelas à API D-ID
6. **Callback**: Atualização de status e interface
7. **Finalização**: Estatísticas e opções de download

## 🎯 Recursos Avançados do Lote

### Sistema de Estados
```python
class PromptStatus(Enum):
    PENDING = "Pendente"      # Aguardando processamento
    PROCESSING = "Processando" # Em processamento
    COMPLETED = "Concluído"   # Processado com sucesso
    FAILED = "Erro"           # Falhou no processamento
    PAUSED = "Pausado"        # Pausado pelo usuário
```

### Controle de Threads
- **Semáforo**: Limita threads simultâneas
- **Thread-Safe**: Operações seguras entre threads
- **Daemon Threads**: Não bloqueiam fechamento da aplicação
- **Timeout**: Controle de tempo limite por requisição

### Interface Responsiva
- **Atualização em Tempo Real**: Status e progresso atualizados a cada segundo
- **Barra de Progresso**: Porcentagem visual do lote
- **Contador de Threads**: Mostra threads ativas
- **Estimativa de Tempo**: Baseada em processamentos anteriores

### Organização de Arquivos
```
batch_videos/
├── video_abc12345_1703123456.mp4
├── video_def67890_1703123478.mp4
└── video_ghi11121_1703123501.mp4
```
- Nomenclatura: `video_{prompt_id}_{timestamp}.mp4`
- Pasta automática criada se não existir
- Evita conflitos de nomes

## 🔒 Segurança e Validação

### Medidas de Segurança
- **Campos Mascarados**: API Key e Token não visíveis
- **Validação de Entrada**: Verificação antes do processamento
- **Limite de Prompts**: Máximo 50 para evitar sobrecarga
- **Timeout de Requisição**: Evita travamentos
- **Thread Daemon**: Fechamento seguro da aplicação

### Validações Implementadas
- **Credenciais Obrigatórias**: API Key e Token necessários
- **Prompts Não Vazios**: Verificação de conteúdo
- **Limite de Threads**: Entre 1 e 10 threads
- **Formato de Arquivo**: Validação de arquivos .txt

## 🧪 Testes Unitários

### Arquivo `test_batch_processor.py`
- **TestPromptItem**: Criação e validação de prompts
- **TestPromptManager**: Gerenciamento de lista de prompts
- **TestThreadPoolManager**: Controle de threads simultâneas
- **TestProgressTracker**: Cálculos de progresso e estatísticas

### Executar Testes
```bash
python -m unittest test_batch_processor.py
```

### Cenários Testados
- ✅ Adição e remoção de prompts
- ✅ Limite de 50 prompts
- ✅ Atualização de status thread-safe
- ✅ Controle de threads simultâneas
- ✅ Cálculo de progresso e tempo estimado
- ✅ Processamento com callback

## 📊 Estatísticas e Monitoramento

### Informações Exibidas
- **Progresso Total**: X/Y prompts (Z%)
- **Threads Ativas**: Número de processamentos simultâneos
- **Taxa de Sucesso**: Porcentagem de sucessos vs falhas
- **Tempo Estimado**: Baseado em processamentos anteriores
- **Tempo Decorrido**: Desde o início do lote

### Exemplo de Resumo Final
```
Processamento Concluído!

Total: 10
Concluídos: 8
Falharam: 2
Taxa de sucesso: 80.0%
```

## 🚀 Melhorias Implementadas

### Versão com Lote vs Individual
| Funcionalidade | Individual | Lote |
|---|---|---|
| Prompts simultâneos | 1 | Até 50 |
| Threads paralelas | 1 | 1-10 configurável |
| Controle de progresso | Básico | Avançado com estatísticas |
| Organização de arquivos | Manual | Automática |
| Interface | Simples | Abas com controles avançados |
| Carregamento de arquivo | ❌ | ✅ |
| Pausar/Retomar | ❌ | ✅ |
| Download em massa | ❌ | ✅ |

## 🐛 Solução de Problemas

### Problemas Específicos do Lote
1. **"Limite de 50 prompts atingido"**: Remova prompts ou processe o lote atual
2. **"Nenhum prompt pendente"**: Adicione prompts à lista primeiro
3. **"Threads travadas"**: Use "Parar" e reinicie o processamento
4. **"Erro de download em massa"**: Verifique permissões da pasta de destino

### Dicas de Performance
- **Threads Ideais**: 3-5 threads para melhor performance
- **Tamanho do Lote**: Lotes menores (10-20) são mais gerenciáveis
- **Conexão**: Conexão estável é essencial para lotes grandes
- **Recursos**: Monitor uso de CPU/memória com lotes grandes

## 📞 Suporte e Contribuição

### Para Dúvidas
1. Consulte os logs no console da aplicação
2. Execute os testes unitários para verificar funcionamento
3. Verifique se as credenciais estão corretas
4. Teste primeiro com lotes pequenos (2-3 prompts)

### Contribuições
- Reporte bugs ou sugestões
- Contribua com novos testes unitários
- Melhore a documentação
- Otimize o código de threading

## 📄 Licença

Este projeto é fornecido como está, para fins educacionais e de desenvolvimento.

---

## 🎉 Novidades da Versão com Lote

### ✨ Principais Adições
- **Interface em Abas**: Separação clara entre individual e lote
- **Sistema de Threading**: Processamento paralelo configurável
- **Gerenciamento de Estado**: Controle completo do ciclo de vida dos prompts
- **Carregamento de Arquivos**: Importação fácil de listas de prompts
- **Download Automático**: Organização automática de vídeos gerados
- **Controles Avançados**: Pausar, parar, retomar processamento
- **Estatísticas em Tempo Real**: Progresso, tempo estimado, taxa de sucesso
- **Testes Unitários**: Cobertura completa das funcionalidades de lote

### 🔧 Melhorias Técnicas
- **Arquitetura Modular**: Separação clara entre UI e lógica de negócio
- **Thread Safety**: Operações seguras entre múltiplas threads
- **Error Handling**: Tratamento robusto de erros em processamento paralelo
- **Resource Management**: Controle eficiente de recursos do sistema
- **Code Quality**: Código limpo, documentado e testado

### 📈 Benefícios
- **Produtividade**: Processe dezenas de vídeos simultaneamente
- **Eficiência**: Aproveite melhor os recursos do sistema
- **Confiabilidade**: Sistema robusto com controle de erros
- **Usabilidade**: Interface intuitiva para operações complexas
- **Escalabilidade**: Configurável para diferentes necessidades