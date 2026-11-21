"""Günlük veritabanı yedeği testleri (geçici klasörde; gerçek data/ klasörüne dokunmaz)."""

import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from heatmap.depo import Depo
from heatmap.motor import Durum
from heatmap.yedek import YedekZamanlayici, eskileri_sil, gunluk_yedek_al, yedek_yolu, yedekleri_listele

BUGUN = date(2026, 11, 22)


class YedekTesti(unittest.TestCase):
    def setUp(self):
        self._gecici = tempfile.TemporaryDirectory()
        self.klasor = Path(self._gecici.name)
        self.db = self.klasor / "heatmap.db"
        self.yedekler = self.klasor / "yedek"
        self.depo = Depo(self.db)
        oid = self.depo.oturum_baslat(Durum("ders", "Code.exe", "pencere", "", "Code.exe", "x"), 1000.0)
        self.depo.oturum_bitisini_guncelle(oid, 1600.0)

    def tearDown(self):
        self._gecici.cleanup()

    def test_yedek_veriyi_icerir(self):
        yol = gunluk_yedek_al(self.db, self.yedekler, BUGUN)
        self.assertEqual(yol, yedek_yolu(self.yedekler, BUGUN))
        vt = sqlite3.connect(yol)
        try:
            self.assertEqual(vt.execute("SELECT uygulama, bitis - baslangic FROM oturumlar").fetchall(),
                             [("Code.exe", 600.0)])
        finally:
            vt.close()
        self.assertFalse(list(self.yedekler.glob("*.yaziliyor")))  # geçici dosya kalmadı

    def test_ayni_gun_ikinci_kez_alinmaz(self):
        self.assertIsNotNone(gunluk_yedek_al(self.db, self.yedekler, BUGUN))
        self.assertIsNone(gunluk_yedek_al(self.db, self.yedekler, BUGUN))
        self.assertEqual(len(yedekleri_listele(self.yedekler)), 1)

    def test_eski_yedekler_silinir_baska_dosyaya_dokunulmaz(self):
        for gun_once in range(10):
            gunluk_yedek_al(self.db, self.yedekler, BUGUN - timedelta(days=gun_once), saklanacak=100)
        (self.yedekler / "notlarim.txt").write_text("dokunma")
        eskileri_sil(self.yedekler, 7)
        kalanlar = [p.name for p in yedekleri_listele(self.yedekler)]
        self.assertEqual(len(kalanlar), 7)
        self.assertEqual(kalanlar[0], f"heatmap-{BUGUN.isoformat()}.db")   # en yeni duruyor
        self.assertTrue((self.yedekler / "notlarim.txt").exists())

    def test_veritabani_yoksa_bir_sey_yapmaz(self):
        self.assertIsNone(gunluk_yedek_al(self.klasor / "yok.db", self.yedekler, BUGUN))
        self.assertFalse(self.yedekler.exists())

    def test_zamanlayici_baslayinca_yedek_alir_ve_durur(self):
        z = YedekZamanlayici(self.db, self.yedekler, aralik_sn=60)
        z.baslat()
        z.durdur()
        self.assertEqual(len(yedekleri_listele(self.yedekler)), 1)


if __name__ == "__main__":
    unittest.main()
