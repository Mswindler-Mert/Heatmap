"""Heatmap'i konsol penceresi açmadan başlatır.

Windows açılışında otomatik başlatma bu dosyayı kullanır (bkz. heatmap/otomatik_baslatma.py).
Python bir dosyayı çalıştırırken o dosyanın klasörünü (proje kökünü) arama yoluna
ekler; bu sayede "heatmap" paketi, Windows programı hangi klasörden başlatırsa
başlatsın bulunur.

Elle de çalıştırılabilir: .venv\\Scripts\\pythonw.exe baslat.pyw
"""

try:
    from heatmap.main import calistir
except Exception as hata:  # Örn. bir paket kurulmamış: konsol olmadığı için hatayı pencereyle göster
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        None, f"Heatmap başlatılamadı (içe aktarma hatası):\n\n{hata}\n\n"
              "baslat.bat ile paketleri yeniden kurmayı dene.", "Heatmap", 0x10 | 0x40000)
    raise SystemExit(1) from hata

calistir()
