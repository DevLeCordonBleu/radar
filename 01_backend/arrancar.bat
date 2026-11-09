@echo off
REM Arranca el backend sin pasar por Gradle cuando no hace falta (mismo
REM criterio que Monetizacion y manuales-modulo): "gradlew bootRun" tarda ~45 s
REM en frio; el jar ya compilado arranca en ~5 s. Solo se recompila si algun
REM archivo de src, del build o del esquema (04_bd) es mas nuevo que el jar.
cd /d "%~dp0"
set "JAR=build\libs\radar-0.0.1-SNAPSHOT.jar"

powershell -NoProfile -Command "$j = Get-Item '%JAR%' -ErrorAction SilentlyContinue; if (-not $j) { exit 1 }; $n = Get-ChildItem src, build.gradle.kts, settings.gradle.kts, ..\04_bd -Recurse -File | Where-Object { $_.LastWriteTime -gt $j.LastWriteTime } | Select-Object -First 1; if ($n) { exit 1 }"
if not errorlevel 1 goto RUN

echo  Hay cambios en el codigo: compilando el backend...
call "%~dp0gradlew.bat" bootJar
if errorlevel 1 (
  echo  ERROR al compilar el backend. Revisa el mensaje de arriba.
  exit /b 1
)
copy /b "%JAR%"+,, "%JAR%" >nul

:RUN
REM Se ejecuta una copia: si alguien recompila con el backend en marcha, el jar en uso no
REM cambia por debajo (Java carga clases del jar a demanda y una peticion se quedaba colgada).
if not exist "build\run" mkdir "build\run"
copy /y "%JAR%" "build\run\radar.jar" >nul
if errorlevel 1 (
  echo  ERROR: no se pudo copiar el jar. Puede quedar otro backend abierto: cierra su ventana y vuelve a iniciar.
  exit /b 1
)
java -XX:TieredStopAtLevel=1 -jar "build\run\radar.jar"
