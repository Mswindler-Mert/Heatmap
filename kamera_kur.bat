@echo off
rem ===================================================================
rem  Heatmap - kamera modulu kurulumu (istege bagli)
rem  Kamera iscisi icin ayri bir sanal ortam (.venv-kamera) kurar.
rem  MediaPipe icin Python 3.12 onerilir: https://www.python.org/downloads/
rem  Model dosyasi ayrica indirilmelidir (kamera_isci/README.md).
rem ===================================================================

cd /d "%~dp0"

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 bulunamadi. Kurulu surumlerle deneniyor: py -3.14
    set PYSURUM=-3.14
) else (
    set PYSURUM=-3.12
)

if not exist ".venv-kamera\Scripts\python.exe" (
    py %PYSURUM% -m venv .venv-kamera
    if errorlevel 1 (
        echo HATA: Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

".venv-kamera\Scripts\python.exe" -m pip install --disable-pip-version-check -r kamera_isci\requirements.txt
if errorlevel 1 (
    echo HATA: Paketler kurulamadi. MediaPipe bu Python surumunu desteklemiyor olabilir; Python 3.12 kur.
    pause
    exit /b 1
)

echo.
echo Kurulum tamam. Simdi model dosyasini indir (kamera_isci/README.md) ve
echo config\config.toml icinde [kamera] etkin = true yap, sonra Heatmap'i yeniden baslat.
pause
