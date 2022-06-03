@echo off
taskkill /f /im MultiClient.exe
taskkill /f /im RobloxPlayerBeta.exe
for /f "tokens=2" %%a in ('tasklist /nh ^| findstr .bin') do (taskkill /f /im %%a)
START "" "files\MultiClient.exe"
cd Synapse-X
START "" "Synapse X.exe"
cd ../
python main/filter.py
pause