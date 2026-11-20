"""Heatmap'i konsol penceresi açmadan başlatır.

Windows açılışında otomatik başlatma bu dosyayı kullanır (bkz. heatmap/otomatik_baslatma.py).
Python bir dosyayı çalıştırırken o dosyanın klasörünü (proje kökünü) arama yoluna
ekler; bu sayede "heatmap" paketi, Windows programı hangi klasörden başlatırsa
başlatsın bulunur.

Elle de çalıştırılabilir: .venv\\Scripts\\pythonw.exe baslat.pyw
"""

from heatmap.main import main

main()
