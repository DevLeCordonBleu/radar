@echo off
title Radar - Detener
echo  Apagando worker (8102), backend (8082) y frontend (5175)...
for %%p in (8102 8082 5175) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >nul 2>&1
)
echo  Listo.
timeout /t 3 >nul
