"""Ayar dosyası okuma testleri: birleştirme, yazım hatası ve yanlış tür."""

import tempfile
import unittest
from pathlib import Path

from heatmap.ayarlar import ORNEK_DOSYA, UYARILAR, ayarlari_yukle

ORNEK = """
[genel]
port = 8765
acilista_arayuzu_ac = true

[tolerans]
durdurma_sn = 15

[pencere]
ders_surecleri = ["Code.exe"]

[adlar]
"Code.exe" = "VS Code"
"""


class AyarTesti(unittest.TestCase):
    def setUp(self):
        self._gecici = tempfile.TemporaryDirectory()
        klasor = Path(self._gecici.name)
        self.ornek = klasor / "config.ornek.toml"
        self.ornek.write_text(ORNEK, encoding="utf-8")
        self.kisisel = klasor / "config.toml"

    def tearDown(self):
        self._gecici.cleanup()

    def yukle(self, kisisel_metin=None):
        if kisisel_metin is not None:
            self.kisisel.write_text(kisisel_metin, encoding="utf-8")
        return ayarlari_yukle(self.ornek, self.kisisel)

    def test_ilk_acilista_ornek_kopyalanir(self):
        a = self.yukle()
        self.assertTrue(self.kisisel.exists())
        self.assertEqual(a[UYARILAR], [])
        self.assertEqual(a["tolerans"]["durdurma_sn"], 15)

    def test_kisisel_deger_ve_yeni_anahtar(self):
        a = self.yukle('[tolerans]\ndurdurma_sn = 30.5\n[adlar]\n"Yeni.exe" = "Yeni"\n')
        self.assertEqual(a["tolerans"]["durdurma_sn"], 30.5)      # float da sayı kabul edilir
        self.assertEqual(a["adlar"], {"Code.exe": "VS Code", "Yeni.exe": "Yeni"})
        self.assertEqual(a[UYARILAR], [])

    def test_yazim_hatasinda_varsayilanla_acilir(self):
        a = self.yukle('[tolerans]\ndurdurma_sn = "30\n')   # tırnak kapanmamış
        self.assertEqual(a["tolerans"]["durdurma_sn"], 15)
        self.assertEqual(len(a[UYARILAR]), 1)
        self.assertIn("line", a[UYARILAR][0])                 # hangi satır olduğu yazıyor

    def test_yanlis_turdeki_deger_atilir_digerleri_kalir(self):
        a = self.yukle('[genel]\nport = "8765"\nacilista_arayuzu_ac = 1\n'
                       '[tolerans]\ndurdurma_sn = 20\n[pencere]\nders_surecleri = "Code.exe"\n')
        self.assertEqual(a["genel"]["port"], 8765)                # metin -> varsayılan
        self.assertIs(a["genel"]["acilista_arayuzu_ac"], True)    # 1 true/false değil -> varsayılan
        self.assertEqual(a["pencere"]["ders_surecleri"], ["Code.exe"])
        self.assertEqual(a["tolerans"]["durdurma_sn"], 20)        # doğru olan korunur
        self.assertEqual(len(a[UYARILAR]), 3)
        self.assertTrue(any("genel.port" in u for u in a[UYARILAR]))

    def test_gercek_ornek_dosya_kendisiyle_uyumlu(self):
        """Depodaki örnek ayar dosyası, kişisel dosya olarak kullanıldığında hiç uyarı üretmemeli."""
        self.kisisel.write_text(ORNEK_DOSYA.read_text(encoding="utf-8"), encoding="utf-8")
        a = ayarlari_yukle(ORNEK_DOSYA, self.kisisel)
        self.assertEqual(a[UYARILAR], [])


if __name__ == "__main__":
    unittest.main()
