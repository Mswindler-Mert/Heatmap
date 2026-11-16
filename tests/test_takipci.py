"""Uçtan uca test: sahte dedektörler + geçici veritabanı ile takip döngüsü."""

import os
import tempfile
import unittest

from ders_takip.dedektorler.baslik import BaslikDedektoru
from ders_takip.dedektorler.bosta import BostaDedektoru
from ders_takip.dedektorler.pencere import PencereDedektoru
from ders_takip.depo import Depo
from ders_takip.motor import KararMotoru
from ders_takip.ozet import Adlandirici
from ders_takip.takipci import Takipci

AYARLAR = {
    "genel": {"tarama_araligi_sn": 1},
    "pencere": {
        "ders_surecleri": ["Code.exe"],
        "ders_degil_surecleri": ["Discord.exe"],
        "tarayici_surecleri": ["chrome.exe"],
        "bilinmeyen_hukum": "belirsiz",
    },
    "baslik": {"ders_kelimeleri": ["Lecture"], "ders_degil_kelimeleri": [], "video_isaretleri": ["YouTube"],
               "yok_sayilan_basliklar": ["Takip Paneli"]},
    "bosta": {"esik_sn": 120, "video_esik_sn": 1800},
}

T0 = 1_800_000_000.0  # Testlerdeki "şimdi"nin başlangıcı (herhangi bir an)


class TakipciTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "test.db"))
        # Testin "öndeki pencere" ve "boşta süresi" diye uyduracağı değerler:
        self.pencere = ("Code.exe", "main.py")
        self.bosta_sn = 0.0
        dedektorler = [
            PencereDedektoru(AYARLAR, self.depo.ogrenilen_kurallar, okuyucu=lambda: self.pencere),
            BaslikDedektoru(AYARLAR, self.depo.ogrenilen_kurallar),
            BostaDedektoru(AYARLAR, okuyucu=lambda: self.bosta_sn),
        ]
        self.takipci = Takipci(AYARLAR, self.depo, dedektorler, KararMotoru(5, 15))
        self.t = T0

    def tearDown(self):
        self.klasor.cleanup()

    def ilerle(self, saniye: int):
        """Zamanı saniye saniye ilerletip her adımda bir tarama yapar."""
        for _ in range(saniye):
            self.t += 1
            self.takipci.tik(self.t)

    def ders_sn(self) -> float:
        return self.depo.ders_suresi(T0, self.t + 1)

    def test_ders_sonra_discord(self):
        self.ilerle(60)                          # 60 sn VS Code
        self.pencere = ("Discord.exe", "Sohbet")
        self.ilerle(40)                          # 40 sn Discord
        self.assertAlmostEqual(self.ders_sn(), 60, delta=2)
        oturumlar = self.depo.oturumlari_getir(T0, self.t + 1)
        self.assertEqual([o["hukum"] for o in oturumlar], ["ders_degil", "ders"])

    def test_kisa_kacamak_dersi_bolmez(self):
        self.ilerle(30)
        self.pencere = ("Discord.exe", "Sohbet")
        self.ilerle(8)                           # toleransın altında
        self.pencere = ("Code.exe", "main.py")
        self.ilerle(30)
        self.assertEqual(len(self.depo.oturumlari_getir(T0, self.t + 1)), 1)
        self.assertAlmostEqual(self.ders_sn(), 68, delta=6)  # son yazım en fazla 5 sn geriden gelir

    def test_ders_videosu_izlerken_bosta_kalmak_durdurmaz(self):
        self.pencere = ("chrome.exe", "OS Lecture 4 - YouTube - Google Chrome")
        self.ilerle(10)
        self.bosta_sn = 600                      # 10 dakikadır dokunulmuyor
        self.ilerle(60)
        self.assertTrue(self.takipci.durum()["calisiyor"])

    def test_belirsiz_oturum_duzeltilince_ogrenilir(self):
        self.pencere = ("chrome.exe", "Pipelining Explained - YouTube - Google Chrome")
        self.ilerle(60)
        self.assertEqual(self.ders_sn(), 0)      # belirsiz süre sayılmaz
        oturum = self.depo.oturumlari_getir(T0, self.t + 1)[0]
        self.assertEqual(oturum["hukum"], "belirsiz")

        # Kullanıcı "dersti" dedi ve başlık öğrenildi
        self.depo.oturum_duzelt(oturum["id"], "ders")
        self.depo.kural_ekle("baslik", oturum["baslik"], "ders")
        self.assertGreater(self.ders_sn(), 50)   # geçmiş süre artık sayılıyor

        self.ilerle(10)                          # aynı video artık doğrudan ders
        self.assertTrue(self.takipci.durum()["calisiyor"])

    def test_takip_paneline_bakmak_onceki_durumu_surdurur(self):
        panel = ("chrome.exe", "Takip Paneli - Google Chrome")

        # Ders çalışırken panele bakmak: sayaç çalışmaya devam eder, oturum bölünmez
        self.ilerle(30)
        self.pencere = panel
        self.ilerle(60)
        self.assertTrue(self.takipci.durum()["calisiyor"])
        self.assertEqual(len(self.depo.oturumlari_getir(T0, self.t + 1)), 1)

        # Ders dışındayken panele bakmak: sayaç durmuş kalır
        self.pencere = ("Discord.exe", "Sohbet")
        self.ilerle(30)
        self.pencere = panel
        self.ilerle(60)
        self.assertFalse(self.takipci.durum()["calisiyor"])
        self.assertAlmostEqual(self.ders_sn(), 90, delta=2)

    def test_program_panel_acikken_baslarsa_cokmez(self):
        self.pencere = ("chrome.exe", "Takip Paneli - Google Chrome")
        self.ilerle(5)
        self.assertFalse(self.takipci.durum()["calisiyor"])
        self.assertEqual(self.depo.oturumlari_getir(T0, self.t + 1), [])

    def test_uygulama_dokumu(self):
        self.ilerle(60)                                              # 60 sn VS Code
        self.pencere = ("chrome.exe", "OS Lecture 4 - YouTube - Google Chrome")
        self.ilerle(40)                                              # 40 sn ders videosu
        self.pencere = ("Discord.exe", "Sohbet")
        self.ilerle(40)                                              # sayılmaz
        self.pencere = ("code.exe", "main.py")                       # farklı harfle aynı uygulama
        self.ilerle(30)

        # Küçük/büyük harf farkı aynı ada çevrilip tek satırda toplanmalı
        adlandirici = Adlandirici({"adlar": {"Code.exe": "VS Code"}})
        dokum = self.depo.uygulama_dokumu(T0, self.t + 1, adlandirici.etiket)
        self.assertEqual([d["ad"] for d in dokum], ["VS Code", "Diğer web"])
        self.assertAlmostEqual(dokum[0]["sure_sn"], 90, delta=7)
        self.assertAlmostEqual(dokum[1]["sure_sn"], 40, delta=2)

    def test_uykudan_donus_araya_sure_eklemez(self):
        self.ilerle(30)
        self.t += 3600                           # bilgisayar 1 saat uyudu
        self.ilerle(30)
        self.assertAlmostEqual(self.ders_sn(), 60, delta=8)


if __name__ == "__main__":
    unittest.main()
