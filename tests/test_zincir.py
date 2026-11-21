"""Zinciri Kırma ve 24 saatlik en verimli saatler testleri."""

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from heatmap.depo import Depo, gun_araligi
from heatmap.motor import Durum
from heatmap.ozet import verimli_saatler
from heatmap.sinyal import DERS
from heatmap.zincir import halka_tak_dogrula, kilometre_tasi, zincir_durumu


def _ders_ekle(depo: Depo, gun: date, bas_saat: int, bas_dk: int, sure_dk: int) -> None:
    """Belirli gün ve saatte `sure_dk` dakikalık DERS oturumu ekler."""
    bas = datetime(gun.year, gun.month, gun.day, bas_saat, bas_dk).timestamp()
    bit = bas + sure_dk * 60
    oid = depo.oturum_baslat(Durum(DERS, "pencere", "VS Code", "Code.exe"), bas)
    depo.oturum_bitisini_guncelle(oid, bit)


class ZincirVeSaatlerTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.depo = Depo(Path(gecici.name) / "test.db")
        self.bugun = date(2026, 11, 21)

    def test_elle_takma_ve_hedef_dogrulama(self):
        # Hedef 60 dk, henüz 20 dk çalışılmış: tam halka takılamaz
        _ders_ekle(self.depo, self.bugun, 10, 0, 20)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertIsNone(d["bekleyen_halka"])
        self.assertIsNotNone(halka_tak_dogrula(d, self.bugun, "tam", self.bugun))

        # 45 dk daha çalış -> toplam 65 dk -> tam halka bekler
        _ders_ekle(self.depo, self.bugun, 11, 0, 45)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["bekleyen_halka"], "tam")
        self.assertEqual(d["zincir_uzunlugu"], 0)  # Henüz takılmadı
        self.assertIsNone(halka_tak_dogrula(d, self.bugun, "tam", self.bugun))

        # Kullanıcı halkayı takar -> zincir 1 olur
        self.depo.zincir_halkasi_kaydet(self.bugun, "tam", zaman=gun_araligi(self.bugun)[0] + 100)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertIsNone(d["bekleyen_halka"])
        self.assertEqual(d["zincir_uzunlugu"], 1)

    def test_otomatik_tak_hedefe_ulasinca_bekletmez(self):
        _ders_ekle(self.depo, self.bugun, 9, 0, 60)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=True, bugun=self.bugun)
        self.assertIsNone(d["bekleyen_halka"])
        self.assertEqual(d["zincir_uzunlugu"], 1)
        self.assertEqual(d["halkalar"][-1]["tur"], "tam")

    def test_bronz_kurtarma_ve_tam_halkaya_yukselme(self):
        _ders_ekle(self.depo, self.bugun, 14, 0, 35)  # 30 dk kurtarma eşiğini geçti, 60 dk hedefin altında
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["bekleyen_halka"], "kurtarma")
        self.assertIsNone(halka_tak_dogrula(d, self.bugun, "kurtarma", self.bugun))

        # Bronz halkayı tak
        self.depo.zincir_halkasi_kaydet(self.bugun, "kurtarma")
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["zincir_uzunlugu"], 1)
        self.assertEqual(d["halkalar"][-1]["tur"], "kurtarma")

        # Aynı gün 30 dk daha çalışınca tam halkaya yükseltme açılır
        _ders_ekle(self.depo, self.bugun, 16, 0, 30)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["bekleyen_halka"], "tam")

    def test_kalkan_hakki_kazanma_ve_dunu_kurtarma(self):
        # Dünden önceki 7 gün üst üste tam hedef (bugün - 8 .. bugün - 2); dün boş!
        for fark in range(2, 9):
            _ders_ekle(self.depo, self.bugun - timedelta(days=fark), 10, 0, 60)

        dun = self.bugun - timedelta(days=1)
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["kalkan_hakki"], 1)
        self.assertEqual(d["kalkan_kullanilabilir_tarih"], dun.isoformat())
        self.assertEqual(d["zincir_uzunlugu"], 0)  # Dün boş olduğu için zincir kopuk
        self.assertIsNone(halka_tak_dogrula(d, dun, "kalkan", self.bugun))

        # Düne kalkan tak -> 7 + 1 = 8 günlük kesintisiz zincir kurtuldu, kalkan hakkı 0'a indi!
        self.depo.zincir_halkasi_kaydet(dun, "kalkan")
        d = zincir_durumu(self.depo, hedef_sn=3600, kurtarma_sn=1800, otomatik_tak=False, bugun=self.bugun)
        self.assertEqual(d["kalkan_hakki"], 0)
        self.assertIsNone(d["kalkan_kullanilabilir_tarih"])
        self.assertEqual(d["zincir_uzunlugu"], 8)

    def test_kilometre_taslari(self):
        self.assertEqual(kilometre_tasi(0)["kod"], "zumrut")
        self.assertEqual(kilometre_tasi(7)["kod"], "turkuaz")
        self.assertEqual(kilometre_tasi(14)["kod"], "gumus")
        self.assertEqual(kilometre_tasi(30)["kod"], "altin")
        self.assertEqual(kilometre_tasi(60)["kod"], "efsane")
        self.assertEqual(kilometre_tasi(105)["sonraki"], 365)

    def test_en_verimli_saatler_bolme(self):
        # 20:40 -> 21:30 (20 dk saat 20'ye, 30 dk saat 21'e) + 21:30 -> 21:50 (20 dk daha saat 21'e)
        _ders_ekle(self.depo, self.bugun, 20, 40, 50)
        _ders_ekle(self.depo, self.bugun, 21, 30, 20)
        v = verimli_saatler(self.depo, self.bugun, gun_sayisi=7)
        self.assertEqual(len(v["saatler"]), 24)
        self.assertEqual(v["saatler"][20]["ders_sn"], 20 * 60)
        self.assertEqual(v["saatler"][21]["ders_sn"], 50 * 60)
        self.assertEqual(v["en_verimli_saat"], 21)
        self.assertIn("Akşam", v["en_verimli_dilim"])


if __name__ == "__main__":
    unittest.main()
