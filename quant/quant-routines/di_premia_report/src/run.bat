@echo off
set root=%USERPROFILE%\anaconda3

call %root%\Scripts\activate.bat %root%

cd %cd%/

cd 0_update_data
python . || goto :error
cd ..

cd 1_process_target_cpi
python . || goto :error
cd ..

cd 2_process_focus
python . || goto :error
cd ..

cd 4_export_hike_corte
python . || goto :error
cd ..

cd 5_export_premia
python . || goto :error
cd ..

cd 6_plot
python . || goto :error
cd ..

cd 6a_new_plot
python . || goto :error
cd ..

cd 8_export_pdf
python . || goto :error
cd ..

cd 9_export_to_sql
python . || goto :error
cd ..

set user_input=%1
IF "%user_input%" NEQ "nopause" (
    echo Finished && PAUSE
)

REM __________________________________________________
REM ERROR HANDLING SECTION
goto :EOF
:error
echo ____________
echo Failed with error #%errorlevel%.
pause
exit /b %errorlevel%