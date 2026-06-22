@echo off
set root=%USERPROFILE%\anaconda3

CALL %root%\Scripts\activate.bat %root%

cd %cd%

python anbima_download_scheduler.py

::pause

@echo on