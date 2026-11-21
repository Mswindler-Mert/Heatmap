"""Heatmap'i Python kurmadan çalışan tek dosya Windows programına paketler: dist/Heatmap.exe

Çalıştırma (proje klasöründe):
    .venv\\Scripts\\python -m pip install -r requirements-build.txt
    .venv\\Scripts\\python paketle.py

Nasıl çalışır? PyInstaller; Python'u, gerekli paketleri ve programın dosyalarını tek bir .exe
içine koyar. .exe açılınca kendini geçici bir klasöre açıp oradan çalışır. Kullanıcının ayar ve
verileri (config/, data/) ise .exe'nin YANINDA oluşur (bkz. heatmap/ayarlar.py: kok_klasorleri).

Kamera işçisi pakete GİRMEZ (MediaPipe çok büyük); .exe sürümünde kamera için ayrı Python
ortamı gerekir (kamera_isci/README.md).
"""

import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
INSA = KOK / "build"          # Ara dosyalar (Git dışı)
CIKTI = KOK / "dist"          # Heatmap.exe buraya (Git dışı)


def ikon_uret() -> Path:
    """Tepsi ikonundaki yeşil halkayı .ico dosyası olarak kaydeder (birden çok boyutla)."""
    from heatmap.tepsi import YESIL, _ikon_ciz

    INSA.mkdir(exist_ok=True)
    yol = INSA / "heatmap.ico"
    _ikon_ciz(YESIL).resize((256, 256)).save(yol, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                                         (128, 128), (256, 256)])
    return yol


def pyinstaller_secenekleri(ikon: Path) -> list[str]:
    ayrac = os.pathsep  # --add-data "kaynak;hedef" (Windows'ta ";")
    return [
        str(KOK / "baslat.pyw"),                  # Giriş noktası: heatmap.main.calistir()
        "--name", "Heatmap",
        "--onefile",                              # Tek dosya
        "--windowed",                             # Konsol penceresi açılmasın (pythonw gibi)
        "--icon", str(ikon),
        "--noconfirm", "--clean",
        "--distpath", str(CIKTI),
        "--workpath", str(INSA / "pyinstaller"),
        "--specpath", str(INSA),
        # Programla gelen salt okunur dosyalar (paketin içinde, sys._MEIPASS altında)
        "--add-data", f"{KOK / 'heatmap' / 'web' / 'static'}{ayrac}heatmap/web/static",
        "--add-data", f"{KOK / 'config' / 'config.ornek.toml'}{ayrac}config",
        # PyInstaller'ın kendi bulamadığı, çalışırken adıyla yüklenen modüller
        "--collect-submodules", "uvicorn",
        "--hidden-import", "pystray._win32",
        # Gerekmeyen büyük paketler (varsa) pakete girmesin (tkinter mini sayaç için gerekli)
        "--exclude-module", "PyInstaller",
    ]


def main() -> None:
    import PyInstaller.__main__

    ikon = ikon_uret()
    PyInstaller.__main__.run(pyinstaller_secenekleri(ikon))
    exe = CIKTI / "Heatmap.exe"
    print(f"\nHazır: {exe} ({exe.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
