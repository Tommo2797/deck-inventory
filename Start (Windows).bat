@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem Deck Inventory - avvio con doppio clic su Windows.
rem Tutto cio' che viene scaricato (uv, Python, librerie, eventuale browser)
rem resta in .app\runtime\ dentro questa cartella.
rem
rem Variabile per test automatici: DECK_INVENTORY_NO_DIALOG=1 salta i dialog
rem del launcher (prima installazione ed errori) e scrive i messaggi qui.

rem Si rilancia ridotto a icona, cosi' la finestra nera non resta in primo piano.
rem (Niente blocco tra parentesi: la ")" di "(Windows)" nel nome lo chiuderebbe.)
rem Nota: il percorso della cartella non deve contenere & o %% (non verificato).
if /i "%~1"=="min" goto minimized
start "" /min cmd /c ""%~f0" min"
exit /b
:minimized

set "UV_VERSION=0.13.1"
set "UV_TARGET=x86_64-pc-windows-msvc"
set "OSARCH=windows-x64"

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

set "RT=%ROOT%\.app\runtime"
set "SRC=%ROOT%\.app\src"
set "UV=%RT%\uv\uv.exe"
set "STATE_FILE=%RT%\install-state.txt"

set "UV_CACHE_DIR=%RT%\uv-cache"
set "UV_PYTHON_INSTALL_DIR=%RT%\python"
set "UV_PROJECT_ENVIRONMENT=%RT%\venv"
set "PLAYWRIGHT_BROWSERS_PATH=%RT%\browsers"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_NO_CONFIG=1"
rem pyproject ha package = false: il pacchetto si importa da .app\src.
set "PYTHONPATH=%SRC%"
set "VIRTUAL_ENV="

rem .app nascosta in Esplora risorse (idempotente).
attrib +h "%ROOT%\.app" >nul 2>&1

rem Guard: cartella spostata/copiata (venv con percorsi assoluti) o altra piattaforma.
set "OLD_STATE="
set "OLD_ROOT="
set "OLD_OSARCH="
if exist "%STATE_FILE%" set /p OLD_STATE=<"%STATE_FILE%"
if not defined OLD_STATE goto guard_done
for /f "tokens=1,2 delims=|" %%A in ("%OLD_STATE%") do (
    set "OLD_ROOT=%%A"
    set "OLD_OSARCH=%%B"
)
if /i not "%OLD_OSARCH%"=="%OSARCH%" goto guard_platform
if /i not "%OLD_ROOT%"=="%ROOT%" goto guard_moved
goto guard_done
:guard_platform
if exist "%RT%\python" rmdir /s /q "%RT%\python"
if exist "%RT%\uv" rmdir /s /q "%RT%\uv"
if exist "%RT%\browsers" rmdir /s /q "%RT%\browsers"
:guard_moved
if exist "%RT%\venv" rmdir /s /q "%RT%\venv"
:guard_done

if exist "%UV%" goto uv_ready
set "DI_MSG=Prima installazione: Deck Inventory scaricherà i componenti necessari dentro la sua cartella. Può richiedere qualche minuto. Al termine si aprirà la pagina."
call :dialog Information
set "DL=%RT%\uv-download"
if exist "%DL%" rmdir /s /q "%DL%"
mkdir "%DL%"
if not exist "%RT%\uv" mkdir "%RT%\uv"
rem curl e tar di Windows, per percorso: un tar GNU nel PATH (es. Git) non apre gli zip.
"%SystemRoot%\System32\curl.exe" -fL --retry 2 -o "%DL%\uv.zip" "https://github.com/astral-sh/uv/releases/download/%UV_VERSION%/uv-%UV_TARGET%.zip"
if errorlevel 1 goto uv_failed
"%SystemRoot%\System32\tar.exe" -xf "%DL%\uv.zip" -C "%DL%"
if errorlevel 1 goto uv_failed
rem Copia come .part e poi rinomina: se si interrompe a meta' non resta un uv.exe
rem troncato che al prossimo avvio sembrerebbe gia' installato.
for /r "%DL%" %%F in (uv*.exe) do copy /y "%%F" "%RT%\uv\%%~nF.part" >nul
if not exist "%RT%\uv\uv.part" goto uv_failed
for %%F in ("%RT%\uv\*.part") do if /i not "%%~nF"=="uv" move /y "%%F" "%RT%\uv\%%~nF.exe" >nul
move /y "%RT%\uv\uv.part" "%UV%" >nul
if not exist "%UV%" goto uv_failed
rmdir /s /q "%DL%"
goto uv_ready
:uv_failed
if exist "%DL%" rmdir /s /q "%DL%"
if exist "%RT%\uv" rmdir /s /q "%RT%\uv"
set "DI_MSG=Non riesco a scaricare i componenti di Deck Inventory. Controlla la connessione a internet e riprova."
call :dialog Error
exit /b 1
:uv_ready

"%UV%" sync --project "%SRC%" --frozen --no-dev
if errorlevel 1 goto sync_failed
rem Espansione ritardata solo qui: un percorso con & ^ ( ) non viene interpretato.
setlocal EnableDelayedExpansion
>"!STATE_FILE!" echo(!ROOT!^|!OSARCH!
endlocal

rem Aggiornamento automatico (logica tutta in Python, che si aggiorna da se').
rem Non blocca mai l'avvio: il codice d'uscita si ignora.
set "DECK_INVENTORY_LAUNCHER=1"
set "DECK_INVENTORY_UV=%UV%"
"%UV%" run --project "%SRC%" --frozen --no-dev python -m deck_inventory.update "%ROOT%"

rem In caso di errore Deck Inventory ha già mostrato il suo messaggio.
"%UV%" run --project "%SRC%" --frozen --no-dev python -m deck_inventory "%ROOT%"
exit /b %errorlevel%

:sync_failed
set "DI_MSG=Installazione non riuscita, controlla la connessione e riprova."
call :dialog Error
exit /b 1

rem Dialog nativo; il testo arriva da DI_MSG (variabile d'ambiente: niente
rem problemi di virgolette o accenti sulla riga di comando). %1 = icona.
:dialog
if not "%DECK_INVENTORY_NO_DIALOG%"=="1" goto dialog_show
echo [dialog] %DI_MSG%
exit /b 0
:dialog_show
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; [void][System.Windows.Forms.MessageBox]::Show($owner, $env:DI_MSG, 'Deck Inventory', 'OK', '%~1')"
exit /b 0
