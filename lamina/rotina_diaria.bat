@echo off
rem Rotina diaria das laminas: uma etapa por linha, na ordem de sempre.
rem Para pular uma etapa, coloque "rem " no inicio da linha.
rem Se uma etapa der erro, as seguintes rodam mesmo assim e o resumo sai no final.

rem Python usado nas etapas. Se "python" nao estiver no PATH, defina a variavel PYTHON
rem com o caminho completo (ex.: C:\Users\...\anaconda3\python.exe) ou troque aqui.
if not defined PYTHON set "PYTHON=python"

cd /d "%~dp0"
set "FALHAS="

rem Rodar antes das 10h pois esta em oferta
call :etapa sensibilidade IFRA11 IFRI11

rem Tabelas de saida (isentos e ITAUBAs FIP): nao dependem de base
call :etapa saida isentos
call :etapa saida fip

rem RODAR DEPOIS - os isentos tem que sair cedo (10h30)
call :etapa sensibilidade isentos

rem 11h, geralmente D-2
call :etapa sensibilidade ICRI11 --data D-2
rem call :etapa sensibilidade RURA11 --data D-4

call :etapa json
call :etapa historico

echo.
if defined FALHAS (
    echo ATENCAO - etapas com erro:%FALHAS%
    pause
    exit /b 1
)
echo Todas as etapas terminaram sem erro.
pause
exit /b 0

:etapa
echo.
echo ===== python __main__.py %*
"%PYTHON%" __main__.py %*
if errorlevel 1 set "FALHAS=%FALHAS% [%*]"
exit /b
