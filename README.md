# Paestro - Sistema de Gestão e Busca Ativa Educacional

O Paestro é um ecossistema de ferramentas desenvolvido para otimizar o monitoramento escolar e a Busca Ativa, utilizando como base os dados exportados do sistema EducarWeb.

## Funcionalidades Principais

**Módulo de Chamada (Visitas)**
Este módulo é utilizado para realizar o controlo de presença presencial durante as visitas às unidades escolares.
- Importação: Realiza o parseamento de arquivos HTML (listas de alunos) exportados do EducarWeb.
- Operação: Gera uma interface interativa para marcação de presença e registo de observações via Tablet ou PC.
- Destino: Exporta a planilha formatada (.xlsx) diretamente para a pasta da unidade no Google Drive via Conta de Serviço (Robô).

**Módulo de Análise (Busca Ativa)**
Este módulo identifica alunos com infrequência crítica através de dados do sistema.
- Entrada: Processa arquivos brutos de registos de chamadas do EducarWeb.
- Inteligência: O backend (attendance_analyser.py) filtra alunos que atingiram níveis de falta que exigem atenção.
- Saída: Gera uma lista consolidada com estatísticas detalhadas de presença.

**Módulo de Relatório (Consolidado)**
Este módulo unifica as informações recolhidas em campo com os dados do sistema.
- Operação: Recebe os arquivos de Chamada e de Análise gerados pelo próprio aplicativo.
- Resultado: Cria um relatório final cruzando a visita presencial com os dados oficiais do sistema.

## Guia de Configuração (Service Account)

Para que o sistema funcione em servidores (Render) e Tablets sem exigir login manual, utilizamos uma Conta de Serviço do Google.

**Passo 1: Preparação do Google Drive**
- Abra o arquivo .env e copie o e-mail que está no campo client_email (ex: paestro@...iam.gserviceaccount.com).
- Vá ao Google Drive da Central de Matrículas.
- Clique com o botão direito na pasta raiz do projeto (ex: Projeto Paestro).
- Selecione Compartilhar.
- Cole o e-mail do robô e dê permissão de EDITOR.
- Sem isso, o sistema dará erro de cota ou permissão negada.

**Passo 2: Configuração do Arquivo .env**
Crie um arquivo chamado .env na raiz do projeto. Este arquivo deve conter a chave JSON completa da Service Account em uma única linha:
- GOOGLE_CREDENTIALS_JSON={"type": "service_account", "project_id": "...", ...}
- APP_PASSWORD=

**Passo 3: Arquivos Ignorados (.gitignore)**
Para segurança, certifique-se de que estes arquivos nunca subam para o GitHub:
- venv
- .env
- __pycache__
- *.py[cod]
- session_data/
- *.log
- token.pickle (não mais utilizado nesta versão, mas mantenha ignorado por segurança)

## Execução do Sistema

- Localmente: Execute o arquivo setup_and_run.bat.
- Web/Tablet: Acesse a URL do deploy (Render). O sistema já estará autenticado automaticamente pelo servidor.

## Informações Técnicas

- Backend: Flask (backend/app.py).
- Autenticação: Google Service Account (Server-side).
- Integração Drive: IDs configurados em FOLDER_MAP no arquivo backend/drive_exporter.py.

---
Este documento serve como guia oficial para operação e manutenção do sistema Paestro.