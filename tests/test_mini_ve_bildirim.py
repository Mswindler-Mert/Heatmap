"""Kayan mini sayaç görünüm mantığı, pencere yok sayma ve masaüstü bildirim testleri."""

import unittest
from datetime import datetime

from heatmap.bildirim import BildirimYoneticisi
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.mini_sayac import MINI_SAYAC_BASLIK, RENK_SARI, RENK_YESIL, mini_gorunum_verisi
from heatmap.sinyal import DEVAM


class MiniSayacMantikTesti(unittest.TestCase):
    def test_calisiyor_ve_kalan_hedef(self):
        v = mini_gorunum_verisi({"calisiyor": True, "duraklatildi": False, "bugun_ders_sn": 3600}, hedef_sn=7200)
        self.assertEqual(v["zaman"], "01:00:00")
        self.assertEqual(v["yuzde"], "%50")
        self.assertEqual(v["nokta_renk"], RENK_YESIL)
        self.assertAlmostEqual(v["cubuk_oran"], 0.5)
        self.assertEqual(v["alt_sag"], "Kalan 1 sa 0 dk")

    def test_hedef_tamamlaninca_altin_cubuk(self):
        v = mini_gorunum_verisi({"calisiyor": True, "duraklatildi": False, "bugun_ders_sn": 7500}, hedef_sn=7200)
        self.assertEqual(v["yuzde"], "%104")
        self.assertEqual(v["cubuk_oran"], 1.0)
        self.assertEqual(v["cubuk_renk"], RENK_SARI)
        self.assertEqual(v["alt_sag"], "Hedef tamam!")

    def test_odak_kronometresi_alt_satirda(self):
        v = mini_gorunum_verisi({"calisiyor": True, "duraklatildi": False, "bugun_ders_sn": 600},
                                hedef_sn=3600, odak_sn=125)
        self.assertEqual(v["alt_sol"], "Odak 00:02:05")

    def test_pencere_dedektoru_mini_sayaci_yok_sayar(self):
        ayar = {"pencere": {"ders_surecleri": [], "ders_degil_surecleri": [], "tarayici_surecleri": []}}
        d = PencereDedektoru(ayar, okuyucu=lambda: ("pythonw.exe", MINI_SAYAC_BASLIK))
        sinyal = d.oku({})
        self.assertEqual(sinyal.hukum, DEVAM)


class BildirimTesti(unittest.TestCase):
    def _ayar(self, **ek):
        b = {"hedef_tamam": True, "aksam_hatirlatma": True, "hatirlatma_saati": 22}
        b.update(ek)
        return {"bildirim": b, "zincir": {"otomatik_tak": False}}

    def test_acilista_hedef_zaten_tammamsa_tekrar_bildirmez(self):
        y = BildirimYoneticisi()
        t = datetime(2026, 11, 21, 15, 0)
        self.assertEqual(y.kontrol_et(t, 7200, 7200, 3, self._ayar()), [])
        self.assertEqual(y.kontrol_et(t, 7300, 7200, 3, self._ayar()), [])

    def test_hedef_gecilince_gunde_bir_kez_bildirir(self):
        y = BildirimYoneticisi()
        t1 = datetime(2026, 11, 21, 14, 0)
        self.assertEqual(y.kontrol_et(t1, 3000, 7200, 2, self._ayar()), [])  # İlk kontrol

        t2 = datetime(2026, 11, 21, 16, 0)
        bildirimler = y.kontrol_et(t2, 7200, 7200, 2, self._ayar())
        self.assertEqual(len(bildirimler), 1)
        self.assertIn("hedef tamam", bildirimler[0][0].lower())

        # Aynı gün ikinci kez bildirmez
        self.assertEqual(y.kontrol_et(t2, 7800, 7200, 3, self._ayar()), [])

        # Ertesi gün tekrar bildirir
        t3 = datetime(2026, 11, 22, 17, 0)
        self.assertEqual(len(y.kontrol_et(t3, 7200, 7200, 3, self._ayar())), 1)

    def test_aksam_zincir_hatirlatmasi(self):
        y = BildirimYoneticisi()
        y.kontrol_et(datetime(2026, 11, 21, 20, 0), 3600, 7200, 5, self._ayar())

        # Saat 21:59'da henüz hatırlatmaz
        self.assertEqual(y.kontrol_et(datetime(2026, 11, 21, 21, 59), 3600, 7200, 5, self._ayar()), [])

        # Saat 22:00'de zincir > 0 ve hedef bitmediyse 1 kez hatırlatır
        b = y.kontrol_et(datetime(2026, 11, 21, 22, 0), 3600, 7200, 5, self._ayar())
        self.assertEqual(len(b), 1)
        self.assertIn("Zinciri kırma", b[0][0])
        self.assertEqual(y.kontrol_et(datetime(2026, 11, 21, 22, 15), 4000, 7200, 5, self._ayar()), [])

    def test_kapali_ayarda_bildirim_yok(self):
        y = BildirimYoneticisi()
        ayar = self._ayar(hedef_tamam=False, aksam_hatirlatma=False)
        y.kontrol_et(datetime(2026, 11, 21, 10, 0), 0, 7200, 4, ayar)
        self.assertEqual(y.kontrol_et(datetime(2026, 11, 21, 22, 30), 1000, 7200, 4, ayar), [])
        self.assertEqual(y.kontrol_et(datetime(2026, 11, 21, 23, 0), 7200, 7200, 4, ayar), [])


if __name__ == "__main__":
    unittest.main()
