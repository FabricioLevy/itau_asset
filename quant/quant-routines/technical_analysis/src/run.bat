@echo off
set root=%USERPROFILE%\anaconda3

CALL %root%\Scripts\activate.bat %root%
CALL conda activate py36

cd %cd%/

cd 0_download_data
python . || goto :error
cd ..

cd 1_process
python . || goto :error
cd ..

cd 1b_regression
python . || goto :error
cd ..

cd 2b_pca
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