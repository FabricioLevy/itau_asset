@echo off
set root=%USERPROFILE%\anaconda3

CALL %root%\Scripts\activate.bat %root%

cd %cd%

python curves_main.py

pause

@echo on