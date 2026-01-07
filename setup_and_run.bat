@echo off
echo ======================================================
echo   PAESTRO - AUTOMACAO DE AMBIENTE E EXECUCAO
echo ======================================================
===== RODAR: .\setup_and_run.bat =====
:: Verifica se a pasta venv existe. Se nao existir, cria.
if not exist venv python -m venv venv

echo [1/2] Atualizando componentes do ambiente...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install gunicorn

echo [2/2] Iniciando o Paestro...
echo Acesso local: http://127.0.0.1:5000
echo Pressione Ctrl+C para encerrar.

venv\Scripts\python.exe -m backend.app

pause