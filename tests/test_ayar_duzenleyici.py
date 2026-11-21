"""Ayarları arayüzden düzenleme: doğrulama ve yorumları koruyarak dosyaya yazma."""

import tempfile
import tomllib
import unittest
from pathlib import Path

from heatmap.ayar_duzenleyici import (
    ALANLAR, AyarDosyasiHatasi, alanlar_ve_degerler, degisenleri_bul, dogrula, dosyaya_yaz,
)
from heatmap.ayarlar import ORNEK_DOSYA, _toml_oku

KISISEL = """# =====================================================================
#  KİŞİSEL ayar dosyam
# =====================================================================

[hedef]
gunluk_dk = 120   # günlük hedef

[pencere]
ders_surecleri = [
    # Kod
    "Code.exe",                # VS Code
    "idea64.exe",              # IntelliJ IDEA
    "Eski.exe",                # bu çıkarılacak
]
bilinmeyen_hukum = "belirsiz"  # listede olmayanlar
"""


class DogrulamaTesti(unittest.TestCase):
    def test_gecerli_degerler(self):
        temiz, hatalar = dogrula({
            "hedef.gunluk_dk": 90, "pencere.bilinmeyen_hukum": "ders_degil",
            "pencere.ders_surecleri": [" Code.exe ", "", "code.exe", "Yeni.exe"],
            "kart.ust_metin": "  Mert  ", "genel.acilista_arayuzu_ac": False,
        })
        self.assertEqual(hatalar, {})
        self.assertEqual(temiz["pencere.ders_surecleri"], ["Code.exe", "Yeni.exe"])  # boş ve tekrar atıldı
        self.assertEqual(temiz["kart.ust_metin"], "Mert")

    def test_hatali_degerler(self):
        _, hatalar = dogrula({
            "hedef.gunluk_dk": -5, "tolerans.durdurma_sn": "15", "bosta.esik_sn": 12.5,
            "pencere.bilinmeyen_hukum": "ders", "kart.ust_metin": "x" * 30,
            "genel.acilista_arayuzu_ac": 1, "genel.port": 9000, "pencere.ders_surecleri": "Code.exe",
        })
        self.assertEqual(set(hatalar), {
            "hedef.gunluk_dk", "tolerans.durdurma_sn", "bosta.esik_sn", "pencere.bilinmeyen_hukum",
            "kart.ust_metin", "genel.acilista_arayuzu_ac", "genel.port", "pencere.ders_surecleri",
        })
        self.assertIn("değiştirilemez", hatalar["genel.port"])  # port arayüzden değiştirilemez

    def test_butun_alanlar_ornek_dosyada_var_ve_gecerli(self):
        """Her düzenlenebilir alan örnek ayar dosyasında bulunmalı ve oradaki değer geçerli olmalı."""
        ornek = _toml_oku(ORNEK_DOSYA)
        for alan in ALANLAR:
            bolum, ad = alan["anahtar"].split(".")
            with self.subTest(alan=alan["anahtar"]):
                self.assertIn(ad, ornek[bolum])
                _, hatalar = dogrula({alan["anahtar"]: ornek[bolum][ad]})
                self.assertEqual(hatalar, {})

    def test_arayuz_icin_gruplar(self):
        gruplar = alanlar_ve_degerler(_toml_oku(ORNEK_DOSYA))
        self.assertEqual([g["ad"] for g in gruplar], ["Hedef ve süreler", "Uygulamalar", "Tarayıcı ve siteler", "Diğer"])
        hedef = gruplar[0]["alanlar"][0]
        self.assertEqual((hedef["anahtar"], hedef["deger"]), ("hedef.gunluk_dk", 120))

    def test_yalnizca_degisenler(self):
        ayarlar = {"hedef": {"gunluk_dk": 120}, "kart": {"ust_metin": "Heatmap"}}
        self.assertEqual(degisenleri_bul(ayarlar, {"hedef.gunluk_dk": 120, "kart.ust_metin": "Mert"}),
                         {"kart.ust_metin": "Mert"})


class DosyayaYazmaTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.klasor = Path(gecici.name)
        self.dosya = self.klasor / "config.toml"
        self.dosya.write_text(KISISEL, encoding="utf-8")
        self.yedek = self.klasor / "yedek"

    def oku(self) -> str:
        return self.dosya.read_text(encoding="utf-8")

    def test_yorumlar_korunur_liste_fark_ile_guncellenir(self):
        dosyaya_yaz(self.dosya, {"hedef.gunluk_dk": 90,
                                 "pencere.ders_surecleri": ["Code.exe", "idea64.exe", "Yeni.exe"]}, self.yedek)
        metin = self.oku()
        self.assertIn("gunluk_dk = 90   # günlük hedef", metin)       # satır sonu yorumu kaldı
        self.assertIn('"Code.exe",                # VS Code', metin)   # liste öğesi yorumu kaldı
        self.assertIn("# Kod", metin)
        self.assertIn("KİŞİSEL ayar dosyam", metin)                   # baş yorum kaldı
        self.assertNotIn("Eski.exe", metin)
        self.assertNotIn("bu çıkarılacak", metin)                      # silinen öğenin yorumu da gitti
        self.assertIn('"Yeni.exe"', metin)
        veri = tomllib.loads(metin)
        self.assertEqual(veri["pencere"]["ders_surecleri"], ["Code.exe", "idea64.exe", "Yeni.exe"])
        self.assertEqual(veri["pencere"]["bilinmeyen_hukum"], "belirsiz")  # dokunulmayan kaldı

    def test_dosyada_olmayan_bolum_ve_ayar_eklenir(self):
        dosyaya_yaz(self.dosya, {"kart.ust_metin": "Mert", "baslik.ders_alanlari": ["a.com", "b.com", "c.com",
                                                                                     "d.com"]})
        veri = tomllib.loads(self.oku())
        self.assertEqual(veri["kart"]["ust_metin"], "Mert")
        self.assertEqual(veri["baslik"]["ders_alanlari"], ["a.com", "b.com", "c.com", "d.com"])
        self.assertEqual(veri["hedef"]["gunluk_dk"], 120)

    def test_onceki_dosya_yedeklenir(self):
        dosyaya_yaz(self.dosya, {"hedef.gunluk_dk": 60}, self.yedek)
        yedekler = list(self.yedek.glob("config-*.toml"))
        self.assertEqual(len(yedekler), 1)
        self.assertIn("gunluk_dk = 120", yedekler[0].read_text(encoding="utf-8"))

    def test_bozuk_dosyaya_yazilmaz(self):
        bozuk = '[hedef]\ngunluk_dk = "120\n'
        self.dosya.write_text(bozuk, encoding="utf-8")
        with self.assertRaises(AyarDosyasiHatasi):
            dosyaya_yaz(self.dosya, {"hedef.gunluk_dk": 60}, self.yedek)
        self.assertEqual(self.oku(), bozuk)
        self.assertFalse(self.yedek.exists())
        self.assertFalse(list(self.klasor.glob("*.yaziliyor")))


if __name__ == "__main__":
    unittest.main()
