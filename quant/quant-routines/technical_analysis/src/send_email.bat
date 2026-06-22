@echo off
set root=%USERPROFILE%\anaconda3

CALL %root%\Scripts\activate.bat %root%

cd %cd%/

cd 3_send_email
python .
cd ..

pause

@echo on