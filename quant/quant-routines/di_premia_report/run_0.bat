@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  DI PREMIA REPORT — Runner completo
:: ============================================================
::
::  Configure o Python abaixo.
::  Opção 1 — Python direto no PATH:
set PYTHON=python
::
::  Opção 2 — Ambiente Conda (descomente e ajuste o nome):
::  set CONDA_ENV=nome_do_ambiente
::  call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
::  conda activate %CONDA_ENV%
::
:: ============================================================

set ROOT=%~dp0
set SCRIPTS=%ROOT%scripts
set SRC=%ROOT%src
set ERRORS=0
set ERROR_LIST=

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
if %ERRORS%==0 (
    echo   CONCLUIDO SEM ERROS  —  %DATE%  %TIME%
) else (
    echo   CONCLUIDO COM %ERRORS% ERRO^(S^)  —  %DATE%  %TIME%
    echo.
    echo   Falhas:
    echo   %ERROR_LIST%
)
echo ============================================================
echo.
pause
exit /b %ERRORS%


:: ──────────────────────────────────────────────────────────
::  Sub-rotinas
:: ──────────────────────────────────────────────────────────

:run
::  Roda um script Python avulso
::  %1 = nome legível  %2 = executável  %3 = arquivo
echo   [%TIME%]  %~1
%~2 %~3
if errorlevel 1 (
    echo   [ERRO] %~1
    set /a ERRORS+=1
    set ERROR_LIST=!ERROR_LIST! | %~1
)
echo.
goto :EOF

:run_stage
::  Entra na pasta do stage, roda e volta
echo   [%TIME%]  Stage %~1
pushd "%SRC%\%~1"
%PYTHON% .
if errorlevel 1 (
    echo   [ERRO] Stage %~1
    set /a ERRORS+=1
    set ERROR_LIST=!ERROR_LIST! | Stage %~1
)
popd
echo.
goto :EOF
