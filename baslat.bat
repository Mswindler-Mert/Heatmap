@echo off
rem ===================================================================
rem  Heatmap - cift tikla baslat
rem  Ilk calistirmada sanal ortami (.venv) kurar ve paketleri yukler.
rem  requirements.txt degistiyse (yeni surumde yeni paket varsa) paketleri
rem  yeniden yukler. Sonra programi konsol penceresi acmadan baslatir.
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
)

rem Paketler en son hangi requirements.txt ile kurulduysa onun kopyasi burada durur.
rem Kopya yoksa ya da requirements.txt'den farkliysa paketler (yeniden) kurulur.
set DAMGA=.venv\heatmap-kurulu-gereksinimler.txt
fc /b requirements.txt "%DAMGA%" >nul 2>&1
if errorlevel 1 (
    echo Paketler kuruluyor ya da guncelleniyor...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo HATA: Paketler yuklenemedi. Internet baglantini kontrol et.
        pause
        exit /b 1
    )
    copy /y requirements.txt "%DAMGA%" >nul
)

rem pythonw.exe = konsol penceresi acmadan calistirir.
rem "start" sayesinde bu pencere hemen kapanir, program arka planda devam eder.
start "" ".venv\Scripts\pythonw.exe" -m heatmap
