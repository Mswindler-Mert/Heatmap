"""Paylaşım kartı testleri: boyut, içerik ve (en önemlisi) gizlilik."""

import io
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from PIL import Image

from ders_takip.depo import Depo
from ders_takip.kart import kart_ciz, kart_verisi
from ders_takip.motor import Durum
from ders_takip.ozet import Adlandirici

AYARLAR = {
    "adlar": {"Code.exe": "VS Code"},
    "siteler": {"YouTube": ["YouTube"]},
}
BUGUN = date(2026, 11, 19)  # Perşembe
GIZLI = "COKGIZLI"          # Başlıklara gömdüğümüz, kartta ASLA görünmemesi gereken kelime


class KartTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "test.db"))
        self.adlandirici = Adlandirici(AYARLAR)
        # Bugün: 90 dk VS Code, 45 dk YouTube, 20 dk tanınmayan site; dün: 130 dk VS Code
        self.ekle(0, 9, 90, "pencere", "Code.exe", f"{GIZLI}_dosya.py - Visual Studio Code")
        self.ekle(0, 12, 45, "baslik", "brave.exe", f"{GIZLI} video adı - YouTube")
        self.ekle(0, 14, 20, "baslik", "brave.exe", f"{GIZLI} özel sayfa")
        self.ekle(1, 10, 130, "pencere", "Code.exe", f"{GIZLI}.py")

    def tearDown(self):
        self.klasor.cleanup()

    def ekle(self, gun_once, saat, dakika, kaynak, uygulama, baslik):
        bas = datetime.combine(BUGUN - timedelta(days=gun_once), datetime.min.time()).timestamp() + saat * 3600
        oid = self.depo.oturum_baslat(Durum("ders", uygulama, kaynak, "", uygulama, baslik), bas)
        self.depo.oturum_bitisini_guncelle(oid, bas + dakika * 60)

    def veri(self, tur):
        return kart_verisi(self.depo, self.adlandirici, 120 * 60, tur, BUGUN)

    def test_gunluk_veri(self):
        v = self.veri("gunluk")
        self.assertEqual(v["toplam_sn"], 155 * 60)
        self.assertEqual([u["ad"] for u in v["uygulamalar"]], ["VS Code", "YouTube", "Diğer web"])
        self.assertAlmostEqual(sum(u["oran"] for u in v["uygulamalar"]), 1.0)
        self.assertEqual(v["seri_gun"], 2)                       # dün ve bugün hedef (120 dk) tuttu
        self.assertEqual([g["vurgulu"] for g in v["gunler"]], [False, False, False, True, False, False, False])

    def test_haftalik_veri(self):
        v = self.veri("haftalik")
        self.assertEqual(v["toplam_sn"], (155 + 130) * 60)
        self.assertEqual(v["tarih_metni"], "16–22 Kasım 2026")
        self.assertEqual(v["en_iyi_gun"], "Per")

    def test_gizlilik_veride_baslik_yok(self):
        """Karta giden verinin hiçbir yerinde pencere/sekme başlığı bulunmamalı."""
        for tur in ("gunluk", "haftalik"):
            metin = json.dumps(self.veri(tur), ensure_ascii=False)
            self.assertNotIn(GIZLI, metin)
            self.assertNotIn("video adı", metin)

    def test_png_boyutu(self):
        for tur in ("gunluk", "haftalik"):
            png = kart_ciz(self.veri(tur))
            resim = Image.open(io.BytesIO(png))
            self.assertEqual(resim.format, "PNG")
            self.assertEqual(resim.size, (1080, 1920))

    def test_bos_veritabaniyla_da_cizilir(self):
        bos_depo = Depo(os.path.join(self.klasor.name, "bos.db"))
        png = kart_ciz(kart_verisi(bos_depo, self.adlandirici, 0, "gunluk", BUGUN))
        self.assertEqual(Image.open(io.BytesIO(png)).size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
