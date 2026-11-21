"""Başlık sınıflandırıcı ve pencere dedektörü testleri."""

import unittest

from heatmap.dedektorler.baslik import BaslikDedektoru, basligi_temizle, kelime_gecer_mi
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK

AYARLAR = {
    "pencere": {
        "ders_surecleri": ["Code.exe"],
        "ders_degil_surecleri": ["Discord.exe"],
        "tarayici_surecleri": ["chrome.exe"],
        "bilinmeyen_hukum": "belirsiz",
    },
    "baslik": {
        "ders_kelimeleri": ["ML", "Database", "Lecture"],
        "ders_degil_kelimeleri": ["Gameplay", "Trailer"],
        "video_isaretleri": ["YouTube"],
    },
}


class TemizlemeTestleri(unittest.TestCase):
    def test_chrome_soneki_ve_bildirim_sayisi(self):
        self.assertEqual(
            basligi_temizle("(3) ML Lecture 5 - YouTube - Google Chrome"),
            "ML Lecture 5 - YouTube",
        )

    def test_edge_profil_ve_sayfa_sayisi(self):
        self.assertEqual(
            # Edge, pencere adına "Microsoft" ile "Edge" arasına görünmez bir boşluk (\u200b) koyar.
            basligi_temizle("Database Notes and 4 more pages - Personal - Microsoft\u200b Edge"),
            "Database Notes",
        )

    def test_firefox(self):
        self.assertEqual(basligi_temizle("OOAD — Mozilla Firefox"), "OOAD")


class KelimeTestleri(unittest.TestCase):
    def test_tam_kelime_eslesir(self):
        self.assertTrue(kelime_gecer_mi("ml lecture 3", "ML"))
        self.assertTrue(kelime_gecer_mi("Intro to Database Systems", "database"))

    def test_kelimenin_parcasi_eslesmez(self):
        self.assertFalse(kelime_gecer_mi("HTML Crash Course", "ML"))


class SiniflandirmaTestleri(unittest.TestCase):
    def setUp(self):
        self.kurallar = []
        self.dedektor = BaslikDedektoru(AYARLAR, kural_kaynagi=lambda: self.kurallar)

    def test_ders(self):
        self.assertEqual(self.dedektor.siniflandir("Database Normalization - YouTube")[0], DERS)

    def test_ders_degil(self):
        self.assertEqual(self.dedektor.siniflandir("Elden Ring Gameplay - YouTube")[0], DERS_DEGIL)

    def test_eslesme_yoksa_belirsiz(self):
        self.assertEqual(self.dedektor.siniflandir("Bir şeyler - YouTube")[0], BELIRSIZ)

    def test_celiski_varsa_belirsiz(self):
        self.assertEqual(self.dedektor.siniflandir("ML Game Trailer")[0], BELIRSIZ)

    def test_ogrenilen_tam_baslik_onceliklidir(self):
        self.kurallar.append({"tur": "baslik", "desen": "Elden Ring Gameplay - YouTube", "hukum": DERS})
        self.assertEqual(self.dedektor.siniflandir("Elden Ring Gameplay - YouTube")[0], DERS)

    def test_ogrenilen_kelime(self):
        self.kurallar.append({"tur": "kelime", "desen": "Neso Academy", "hukum": DERS})
        self.assertEqual(self.dedektor.siniflandir("Pipelining | Neso Academy - YouTube")[0], DERS)


class PencereTestleri(unittest.TestCase):
    def dedektor(self, surec, kurallar=()):
        return PencereDedektoru(AYARLAR, kural_kaynagi=lambda: list(kurallar),
                                okuyucu=lambda: (surec, "başlık"))

    def test_listeler(self):
        self.assertEqual(self.dedektor("code.EXE").oku({}).hukum, DERS)       # harf duyarsız
        self.assertEqual(self.dedektor("Discord.exe").oku({}).hukum, DERS_DEGIL)
        self.assertEqual(self.dedektor("bilinmeyen.exe").oku({}).hukum, BELIRSIZ)

    def test_tarayicida_fikir_bildirmez(self):
        sinyal = self.dedektor("chrome.exe").oku({})
        self.assertEqual(sinyal.hukum, FIKRIM_YOK)
        self.assertTrue(sinyal.detay["tarayici"])

    def test_ogrenilen_surec_kurali(self):
        kurallar = [{"tur": "surec", "desen": "bilinmeyen.exe", "hukum": DERS}]
        self.assertEqual(self.dedektor("bilinmeyen.exe", kurallar).oku({}).hukum, DERS)


if __name__ == "__main__":
    unittest.main()
