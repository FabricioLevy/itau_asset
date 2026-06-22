@echo off
set root=%USERPROFILE%\anaconda3

call %root%\Scripts\activate.bat %root%

cd %cd%/

cd 0_update_bloomberg
python . || goto :error
cd ..

cd 1_plot
python . || goto :error
cd ..

cd 2_generate_pdf
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
