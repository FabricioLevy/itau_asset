@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  DI PREMIA REPORT — Runner completo
:: ============================================================
::
::  Ambiente Python (Anaconda):
set root=%USERPROFILE%\anaconda3
call %root%\Scripts\activate.bat %root%
set PYTHON=python
::
:: ============================================================

set ROOT=%~dp0
set SCRIPTS=%ROOT%scripts
set SRC=%ROOT%src
set LOG=%ROOT%run_errors.txt
set ERRORS=0
set ERROR_LIST=

:: Inicializa o log
echo ============================================================ > "%LOG%"
echo   DI PREMIA REPORT >> "%LOG%"
echo   %DATE%  %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo. >> "%LOG%"

echo.
echo ============================================================
echo   DI PREMIA REPORT
echo   %DATE%  %TIME%
echo ============================================================


:: ──────────────────────────────────────────────────────────
::  BLOCO 1 — Atualização do banco de dados
:: ──────────────────────────────────────────────────────────

echo.
echo [BANCO] Atualizando dados...
echo.
echo [BANCO] Atualizando dados... >> "%LOG%"
echo. >> "%LOG%"

call :run "SELIC TARGET"       "%PYTHON%" "%SCRIPTS%\update_selic.py"
call :run "CDI"                "%PYTHON%" "%SCRIPTS%\update_cdi.py"
call :run "Focus BCB"          "%PYTHON%" "%SCRIPTS%\update_focus.py"
call :run "COPOM"              "%PYTHON%" "%SCRIPTS%\update_copom.py"
call :run "Inflation Target"   "%PYTHON%" "%SCRIPTS%\seed_inflation_target.py"
call :run "Curvas DI/DAP BEI"  "%PYTHON%" "%SCRIPTS%\update_interest_rate_curves.py"


:: ──────────────────────────────────────────────────────────
::  BLOCO 2 — Pipeline de cálculo e geração de relatório
:: ──────────────────────────────────────────────────────────

echo.
echo [PIPELINE] Rodando stages...
echo.
echo [PIPELINE] Rodando stages... >> "%LOG%"
echo. >> "%LOG%"

call :run_stage "0_update_data"
call :run_stage "1_process_target_cpi"
call :run_stage "2_process_focus"
call :run_stage "4_export_hike_corte"
call :run_stage "5_export_premia"
call :run_stage "6_plot"
call :run_stage "6a_new_plot"
call :run_stage "8_export_pdf"
call :run_stage "9_export_to_sql"


:: ──────────────────────────────────────────────────────────
::  RESULTADO FINAL
:: ──────────────────────────────────────────────────────────

echo.
echo ============================================================
echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"

if %ERRORS%==0 (
    echo   CONCLUIDO SEM ERROS  —  %DATE%  %TIME%
    echo   CONCLUIDO SEM ERROS  —  %DATE%  %TIME% >> "%LOG%"
) else (
    echo   CONCLUIDO COM %ERRORS% ERRO^(S^)  —  %DATE%  %TIME%
    echo   CONCLUIDO COM %ERRORS% ERRO^(S^)  —  %DATE%  %TIME% >> "%LOG%"
    echo. >> "%LOG%"
    echo   Falhas: %ERROR_LIST% >> "%LOG%"
    echo.
    echo   Falhas:
    echo   %ERROR_LIST%
    echo.
    echo   Log de erros: %LOG%
)

echo ============================================================
echo ============================================================ >> "%LOG%"
echo.
pause
exit /b %ERRORS%


:: ──────────────────────────────────────────────────────────
::  Sub-rotinas
:: ──────────────────────────────────────────────────────────

:run
::  %1 = nome legível  %2 = executável  %3 = arquivo
echo   [%TIME%]  %~1
echo. >> "%LOG%"
echo   [%TIME%]  %~1 >> "%LOG%"
%~2 %~3 2>> "%LOG%"
if errorlevel 1 (
    echo   [ERRO] %~1
    echo   [ERRO] %~1 >> "%LOG%"
    set /a ERRORS+=1
    set ERROR_LIST=!ERROR_LIST!, %~1
)
echo.
goto :EOF

:run_stage
::  Entra na pasta do stage, roda e volta
echo   [%TIME%]  Stage %~1
echo. >> "%LOG%"
echo   [%TIME%]  Stage %~1 >> "%LOG%"
pushd "%SRC%\%~1"
%PYTHON% . 2>> "%LOG%"
if errorlevel 1 (
    echo   [ERRO] Stage %~1
    echo   [ERRO] Stage %~1 >> "%LOG%"
    set /a ERRORS+=1
    set ERROR_LIST=!ERROR_LIST!, Stage %~1
)
popd
echo.
goto :EOF
