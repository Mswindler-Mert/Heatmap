"""Tek dosya .exe (PyInstaller) olarak çalışırken yolların ve davranışların doğruluğu.

Gerçek paketleme burada yapılmaz (uzun sürer); paketlenmiş hâl parametrelerle taklit edilir.
Gerçek .exe derlemesi: paketle.py (ve GitHub'da .github/workflows/surum.yml).
"""

import tempfile
import time
import unittest
from pathlib import Path

from heatmap.ayarlar import kok_klasorleri
from heatmap.dedektorler.kamera import IsciSureci, isci_komutu


class PaketYollariTesti(unittest.TestCase):
    def test_normalde_iki_kok_da_proje_klasoru(self):
        kaynak, kok = kok_klasorleri(donmus=False)
        self.assertEqual(kaynak, kok)
        self.assertTrue((kok / "heatmap" / "ayarlar.py").exists())
        self.assertTrue((kaynak / "config" / "config.ornek.toml").exists())

    def test_paketliyken_veriler_exe_yaninda_kaynaklar_paket_icinde(self):
        kaynak, kok = kok_klasorleri(donmus=True, exe=r"C:\Programlar\Heatmap\Heatmap.exe",
                                     paket_ici=r"C:\Temp\_MEI12345")
        self.assertEqual(kok, Path(r"C:\Programlar\Heatmap"))
        self.assertEqual(kaynak, Path(r"C:\Temp\_MEI12345"))

    def test_paketliyken_kamera_kendini_tekrar_calistirmaz(self):
        # Ayrı Python ortamı yoksa .exe'nin kendisiyle işçi başlatılmamalı (program ikinci kez açılırdı)
        if not _kamera_ortami_var():  # .venv-kamera kuruluysa onu kullanır; o durumda bu kontrol anlamsız
            self.assertIsNone(isci_komutu({}, paketli=True))
        self.assertEqual(isci_komutu({"python": r"C:\py312\python.exe"}, paketli=True)[0], r"C:\py312\python.exe")

    def test_komutsuz_isci_hata_bildirir(self):
        isci = IsciSureci(None)
        isci.baslat()
        try:
            bitis = time.time() + 5
            while isci.son_gozlem() is None and time.time() < bitis:
                time.sleep(0.05)
            self.assertIn("ayrı Python ortamı", isci.son_gozlem()["hata"])
        finally:
            isci.kapat()

    def test_paketleme_betigi_gerekli_dosyalari_ekliyor(self):
        import paketle
        with tempfile.TemporaryDirectory() as klasor:
            secenekler = paketle.pyinstaller_secenekleri(Path(klasor) / "x.ico")
        metin = " ".join(secenekler)
        for gerekli in ("--onefile", "--windowed", "heatmap/web/static", "config.ornek.toml",
                        "pystray._win32", "uvicorn"):
            self.assertIn(gerekli, metin)
        for kaynak in [s.split(";")[0] for s in secenekler if ";" in s]:  # --add-data kaynakları var mı
            self.assertTrue(Path(kaynak).exists(), kaynak)


def _kamera_ortami_var() -> bool:
    from heatmap.dedektorler.kamera import KAMERA_VENV_PYTHON
    return KAMERA_VENV_PYTHON.exists()


if __name__ == "__main__":
    unittest.main()
