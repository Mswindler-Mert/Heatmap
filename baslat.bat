@echo off
rem ===================================================================
rem  Heatmap - cift tikla baslat
rem  Ilk calistirmada sanal ortami (.venv) kurar ve paketleri yukler.
rem  Sonraki calistirmalarda dogrudan programi baslatir.
rem  (Bu dosyada Turkce karakter kullanilmadi: cmd bozuk gosterebiliyor.)
rem ===================================================================

rem Bu .bat dosyasinin bulundugu klasore gec
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Ilk kurulum yapiliyor, bu birkac dakika surebilir...
    py -m venv .venv
    if errorlevel 1 (
        echo HATA: Sanal ortam olusturulamadi. Python kurulu mu? "py --version" ile kontrol et.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo HATA: Paketler yuklenemedi. Internet baglantini kontrol et.
        pause
        exit /b 1
    )
)

rem pythonw.exe = konsol penceresi acmadan calistirir.
rem "start" sayesinde bu pencere hemen kapanir, program arka planda devam eder.
start "" ".venv\Scripts\pythonw.exe" -m heatmap
