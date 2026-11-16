@echo off
setlocal
title Rasante
set "PORTA=8740"
set "PASTA=%~dp0"
if "%PASTA:~-1%"=="\" set "PASTA=%PASTA:~0,-1%"

echo Iniciando o Rasante em "%PASTA%" ...
start "Rasante_%PORTA%" /D "%PASTA%" /min cmd /k "python servidor.py"

timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:%PORTA%/

echo.
echo Rasante rodando em http://127.0.0.1:%PORTA%/
echo A vigia das rotas so funciona enquanto esta janela estiver aberta.
echo Pressione qualquer tecla nesta janela para PARAR o Rasante e fechar.
pause >nul

taskkill /FI "WINDOWTITLE eq Rasante_%PORTA%*" /T /F >nul 2>&1
echo Rasante parado.
timeout /t 1 /nobreak >nul
endlocal
