Paestro - Sistema de Gestão e Busca Ativa Educacional
O Paestro é um ecossistema de ferramentas desenvolvido para otimizar o monitoramento escolar e a Busca Ativa.

Funcionalidades Principais

 1.Modulo de Chamada (Visitas) Este módulo é utilizado para realizar o controle de presença presencial durante as visitas às unidades escolares.

 -Importação: Realiza o parseamento de arquivos HTML (listas de alunos) exportados do EducarWeb.
 -Operação: Gera uma interface interativa para marcação de presença, faltas e registo de observações.
 -Destino: Exporta a planilha formatada (.xlsx) diretamente para a pasta da unidade correspondente no Google Drive via API.

 2.Modulo de Analise (Busca Ativa) Este módulo é focado na inteligência de dados para identificar alunos com infrequência crítica.

 -Entrada: Processa arquivos brutos de registos de chamadas extraídos do sistema escolar.
 -Inteligência: O backend (attendance_analyser.py) executa regras de cruzamento para filtrar alunos que atingiram níveis de falta que exigem atenção.
 -Saída: Gera uma lista consolidada com os alunos em atenção e estatísticas detalhadas de presença.

 3.Modulo de Relatorio (Consolidado) Este módulo unifica as informações recolhidas em campo com os dados do sistema.

 -Operação: Recebe os arquivos de Chamada e de Análise gerados pelo próprio aplicativo.
 -Resultado: Cria um relatório final cruzando a realidade verificada na visita presencial com os dados oficiais do sistema, gerando um documento unificado.

-Guia de Configuracao para Novas Maquinas-
Siga este passo a passo para configurar o ambiente de forma correta e segura.

 Preparacao Inicial

 -Instale o Python 3.10 ou superior e marque a opção "Add Python to PATH" durante a instalação.
 -Clone o repositório ou copie a pasta do projeto para o novo computador.
 -Certifique-se de que o e-mail do usuário da nova máquina foi adicionado como "Usuário de Teste" no Google Cloud Console do projeto.

Configuracao de Seguranca

 -O arquivo .env e o arquivo token.pickle nunca devem ser enviados para o GitHub (já configurados no .gitignore).
 -Crie um arquivo texto chamado .env na raiz do projeto.
 -Cole a credencial JSON no formato: GOOGLE_CREDENTIALS_JSON={"installed":{...}}
 -Importante: O conteúdo do JSON deve ser mantido em segredo e compartilhado apenas com os responsáveis pela execução do projeto.

Execucao do Sistema

 -Execute o arquivo setup_and_run.bat. Este script criará o ambiente virtual e instalará as dependências automaticamente.
 -No primeiro uso da função de exportação, o navegador abrirá uma aba para login.
 -Realize o login com a conta da Central de Matrículas.
 -Na tela de aviso do Google, clique em "Configurações Avançadas" e depois em "Acessar Paestro (não seguro)".

Informacoes Tecnicas

 -Backend: Flask (backend/app.py).
 -Processamento: Pandas e BeautifulSoup.
 -Integracao Drive: Mapeamento de pastas configurado em FOLDER_MAP dentro de backend/drive_exporter.py.
 -Logs: Em caso de falha no processamento de arquivos, consulte o arquivo attendance_parser.log.