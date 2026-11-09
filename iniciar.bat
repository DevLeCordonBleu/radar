@echo off
title Radar - Iniciar
cd /d "%~dp0"

echo.
echo  ================================================
echo    Radar de Anuncios - Le Cordon Bleu Peru
echo  ================================================
echo.
echo  Levanta los tres servicios, cada uno en su ventana:
echo    1. Worker    (Python)  puerto 8102
echo    2. Backend   (Kotlin)  puerto 8082
echo    3. Frontend  (Vue)     puerto 5175
echo  Si ya estaban corriendo, los reinicia.
echo.

set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py --version >nul 2>&1 && set "PY=py"
if not defined PY goto NOPYTHON
where npm >nul 2>&1
if errorlevel 1 goto NONODE

REM Claves del worker: se crea el .env desde el ejemplo la primera vez.
if not exist "03_worker\.env" copy "03_worker\.env.example" "03_worker\.env" >nul

%PY% -c "import fastapi, uvicorn, httpx, PIL, playwright" >nul 2>&1
if errorlevel 1 (
  echo  Instalando librerias del worker por primera vez...
  %PY% -m pip install -r 03_worker\requirements.txt
  if errorlevel 1 goto INSTALLFAIL
)
if not exist "02_frontend\node_modules" (
  echo  Instalando dependencias del frontend por primera vez...
  pushd 02_frontend
  call npm install
  popd
)

echo  Liberando puertos 8102, 8082 y 5175...
for %%p in (8102 8082 5175) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

start "Radar - Worker (8102)" /D "%~dp003_worker" cmd /k %PY% -m uvicorn app.main:app --port 8102
start "Radar - Backend (8082)" /D "%~dp001_backend" cmd /k arrancar.bat
start "Radar - Frontend (5175)" /D "%~dp002_frontend" cmd /k npm run dev

echo.
echo  Esperando a que el backend termine de arrancar...
set /a INTENTOS=0
:ESPERA
timeout /t 1 /nobreak >nul
curl -s -o nul -f http://localhost:8082/actuator/health >nul 2>&1 && goto LISTO
set /a INTENTOS+=1
if %INTENTOS% GEQ 180 goto TARDA
goto ESPERA

:LISTO
start "" "http://localhost:5175/"
echo.
echo  Radar abierto: http://localhost:5175
echo  NO cierres las tres ventanas mientras lo usas. Para apagar todo: detener.bat
timeout /t 8 >nul
goto END

:TARDA
echo  El backend tarda mas de lo normal. Revisa la ventana "Radar - Backend (8082)".
echo  Cuando diga "Started RadarApplication", abre http://localhost:5175/
pause
goto END

:NOPYTHON
echo  ERROR: Python no esta instalado o no esta en el PATH.
pause
goto END
:NONODE
echo  ERROR: Node.js no esta instalado o no esta en el PATH.
pause
goto END
:INSTALLFAIL
echo  ERROR al instalar las librerias. Revisa tu conexion a internet.
pause
goto END
:END
