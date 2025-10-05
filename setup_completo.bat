@echo off
title AJHB - Configuracion Completa con Nginx
color 0A

echo ========================================
echo   AJHB - Setup Completo
echo ========================================
echo.

REM Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Requiere permisos de administrador
    echo Haz click derecho y "Ejecutar como administrador"
    pause
    exit /b 1
)

echo [1/4] Instalando dependencias Python...
pip install flask flask-cors

echo.
echo [2/4] Creando servicio del backend...
set "SCRIPT_DIR=%~dp0"
set "PYTHON_PATH=%SCRIPT_DIR%backendconta.py"

sc query "AJHBBackend" >nul 2>&1
if %errorlevel% equ 0 (
    sc stop "AJHBBackend" >nul 2>&1
    timeout /t 2 /nobreak >nul
    sc delete "AJHBBackend"
    timeout /t 2 /nobreak >nul
)

sc create "AJHBBackend" binPath= "python.exe \"%PYTHON_PATH%\"" start= auto DisplayName= "AJHB Backend Service"
sc description "AJHBBackend" "Backend AJHB Sistema Contable"
sc failure "AJHBBackend" reset= 86400 actions= restart/5000/restart/10000/restart/30000
sc start "AJHBBackend"

echo.
echo [3/4] Configurando Nginx...
if not exist "C:\nginx" (
    echo.
    echo IMPORTANTE: Debes instalar Nginx primero
    echo 1. Descarga: http://nginx.org/en/download.html
    echo 2. Extrae en C:\nginx
    echo.
    pause
    exit /b 1
)

copy /Y "%SCRIPT_DIR%nginx.conf" "C:\nginx\conf\nginx.conf"
taskkill /F /IM nginx.exe >nul 2>&1
timeout /t 2 /nobreak >nul

cd /d C:\nginx
start nginx.exe

echo.
echo [4/4] Configurando firewall...
netsh advfirewall firewall delete rule name="Nginx HTTP" >nul 2>&1
netsh advfirewall firewall add rule name="Nginx HTTP" dir=in action=allow protocol=TCP localport=80 >nul

echo.
echo ========================================
echo   INSTALACION COMPLETADA
echo ========================================
echo.
echo Backend: http://localhost:5000/api/health
echo Frontend: http://localhost
echo.
echo Ambos servicios se inician automaticamente con Windows
echo.
pause
