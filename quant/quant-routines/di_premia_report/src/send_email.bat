@echo off
set root=%USERPROFILE%\anaconda3

call %root%\Scripts\activate.bat %root%

cd %cd%/

cd 7_send_email
python .
cd ..

PAUSE