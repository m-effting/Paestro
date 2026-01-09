@echo off
echo ======================================================
echo   PAESTRO - AUTOMACAO DE AMBIENTE E EXECUCAO
echo ======================================================

:: 1. Verifica se a pasta venv existe. Se nao existir, cria.
if not exist venv python -m venv venv

:: 2. Atualiza dependencias
echo [1/2] Atualizando componentes do ambiente...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install gunicorn

:: 3. Carrega a senha do arquivo .env (Cofre Local)
echo [2/2] Iniciando o Paestro...
if exist .env (
    echo [OK] Carregando senha do arquivo .env local.
    for /f "usebackq delims=" %%x in (".env") do set "%%x"
) else (
    echo [AVISO] Arquivo .env nao encontrado. Usando configuracao padrao.
)

echo Acesso local: http://127.0.0.1:5000
echo Pressione Ctrl+C para encerrar.

:: 4. Roda o app com a senha carregada na memoria
venv\Scripts\python.exe -m backend.app

pause