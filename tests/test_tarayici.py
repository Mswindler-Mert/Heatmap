"""Tarayıcı eklentisi desteği: dedektör, site listeleri, video/ses, şema güncellemesi, uçtan uca."""

import os
import sqlite3
import tempfile
import unittest

from heatmap.dedektorler.baslik import BaslikDedektoru, alan_eslesir_mi
from heatmap.dedektorler.bosta import BostaDedektoru
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.dedektorler.tarayici import TAZELIK_SN, TarayiciDedektoru, alan_adini_temizle
from heatmap.depo import Depo
from heatmap.motor import KararMotoru
from heatmap.ozet import DIGER_WEB, Adlandirici
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK, Sinyal
from heatmap.takipci import Takipci

AYARLAR = {
    "genel": {"tarama_araligi_sn": 1},
    "pencere": {"ders_surecleri": ["Code.exe"], "ders_degil_surecleri": ["Discord.exe"],
                "tarayici_surecleri": ["brave.exe"], "bilinmeyen_hukum": "belirsiz"},
    "baslik": {"ders_kelimeleri": ["Lecture"], "ders_degil_kelimeleri": ["Gameplay"],
               "video_isaretleri": ["YouTube"], "yok_sayilan_basliklar": ["Takip Paneli"],
               "ders_alanlari": ["claude.ai", "github.com"], "ders_degil_alanlari": ["instagram.com"]},
    "bosta": {"esik_sn": 120, "video_esik_sn": 1800},
}


def tarayici_penceresi(baslik="Bir sayfa - Brave"):
    return {"pencere": Sinyal("pencere", FIKRIM_YOK, "", {"surec": "brave.exe", "baslik": baslik, "tarayici": True})}


class DedektorTesti(unittest.TestCase):
    def setUp(self):
        self.saat = 1000.0
        self.d = TarayiciDedektoru(saat=lambda: self.saat)

    def test_rapor_yoksa_bagli_degil(self):
        self.assertFalse(self.d.oku(tarayici_penceresi()).detay["bagli"])

    def test_taze_rapor_aktarilir(self):
        self.d.rapor_al("WWW.YouTube.com", True, True)
        s = self.d.oku(tarayici_penceresi())
        self.assertEqual(s.hukum, FIKRIM_YOK)
        self.assertEqual(s.detay, {"bagli": True, "alan_adi": "youtube.com", "sesli": True})

    def test_bayat_rapor_kullanilmaz(self):
        self.d.rapor_al("youtube.com", True, True)
        self.saat += TAZELIK_SN + 1
        self.assertFalse(self.d.oku(tarayici_penceresi()).detay["bagli"])

    def test_eklentili_tarayici_onde_degilse_kullanilmaz(self):
        self.d.rapor_al("youtube.com", True, odakta=False)
        self.assertFalse(self.d.oku(tarayici_penceresi()).detay["bagli"])

    def test_onde_tarayici_yoksa_kullanilmaz(self):
        self.d.rapor_al("youtube.com", True, True)
        pencere = {"pencere": Sinyal("pencere", DERS, "", {"surec": "Code.exe", "tarayici": False})}
        self.assertFalse(self.d.oku(pencere).detay["bagli"])

    def test_gecersiz_alan_adi_temizlenir(self):
        self.assertEqual(alan_adini_temizle("<script>"), "")
        self.assertEqual(alan_adini_temizle(" www.GitHub.com "), "github.com")


class BaslikIleTesti(unittest.TestCase):
    def setUp(self):
        self.t = TarayiciDedektoru(saat=lambda: 0.0)
        self.b = BaslikDedektoru(AYARLAR)

    def oku(self, baslik, alan_adi=None, sesli=False):
        onceki = tarayici_penceresi(baslik)
        if alan_adi is not None:
            self.t.rapor_al(alan_adi, sesli, True)
            onceki["tarayici"] = self.t.oku(onceki)
        return self.b.oku(onceki)

    def test_site_listeleri(self):
        self.assertEqual(self.oku("Yeni sohbet", "claude.ai").hukum, DERS)
        self.assertEqual(self.oku("Gist", "gist.github.com").hukum, DERS)          # alt alan adı
        self.assertEqual(self.oku("Akış", "instagram.com").hukum, DERS_DEGIL)

    def test_listede_olmayan_sitede_baslik_kurali(self):
        self.assertEqual(self.oku("ML Lecture 3 - YouTube", "youtube.com").hukum, DERS)
        self.assertEqual(self.oku("Rastgele - YouTube", "youtube.com").hukum, BELIRSIZ)

    def test_video_bilgisi_sesten_gelir(self):
        self.assertTrue(self.oku("ML Lecture - YouTube", "youtube.com", sesli=True).detay["video"])
        self.assertFalse(self.oku("ML Lecture - YouTube", "youtube.com", sesli=False).detay["video"])
        # Eklenti yoksa eski tahmin: başlıkta "YouTube" -> video
        self.assertTrue(self.oku("ML Lecture - YouTube").detay["video"])

    def test_ogrenilen_site_kurali_ayar_listesinden_once_gelir(self):
        kurallar = [{"tur": "alan", "desen": "instagram.com", "hukum": DERS}]  # ör. ders hesabı
        b = BaslikDedektoru(AYARLAR, kural_kaynagi=lambda: kurallar)
        self.assertEqual(b.siniflandir("Akış", "instagram.com")[0], DERS)
        self.assertEqual(b.siniflandir("Rastgele", "")[0], BELIRSIZ)  # site adı yoksa kural uygulanmaz

    def test_alan_eslesmesi_kenarlari(self):
        self.assertTrue(alan_eslesir_mi("github.com", "github.com"))
        self.assertFalse(alan_eslesir_mi("notgithub.com", "github.com"))
        self.assertFalse(alan_eslesir_mi("github.com", ""))


class AdlandirmaTesti(unittest.TestCase):
    def test_alan_adi_site_adina_cevrilir(self):
        a = Adlandirici({"siteler": {"YouTube": ["YouTube", "youtube.com"]}})
        tarayici = {"kaynak": "baslik", "uygulama": "brave.exe", "baslik": "Gizli video"}
        self.assertEqual(a.etiket({**tarayici, "alan_adi": "m.youtube.com"}), ("YouTube", "site"))
        self.assertEqual(a.etiket({**tarayici, "alan_adi": "geeksforgeeks.org"}), ("geeksforgeeks.org", "site"))
        self.assertEqual(a.etiket({**tarayici, "alan_adi": None}), (DIGER_WEB, "site"))  # eski kayıt


class SemaGuncellemeTesti(unittest.TestCase):
    def test_eski_veritabanina_sutun_eklenir_veri_kalir(self):
        with tempfile.TemporaryDirectory() as klasor:
            yol = os.path.join(klasor, "eski.db")
            vt = sqlite3.connect(yol)  # alan_adi sütunu OLMAYAN eski şema
            vt.execute("CREATE TABLE oturumlar (id INTEGER PRIMARY KEY AUTOINCREMENT, baslangic REAL NOT NULL,"
                       " bitis REAL NOT NULL, hukum TEXT NOT NULL, duzeltme TEXT, kaynak TEXT, aciklama TEXT,"
                       " uygulama TEXT, baslik TEXT)")
            vt.execute("INSERT INTO oturumlar (baslangic, bitis, hukum, uygulama) VALUES (0, 60, 'ders', 'Code.exe')")
            vt.commit()
            vt.close()

            depo = Depo(yol)
            satir = depo.oturum_getir(1)
            self.assertEqual(satir["uygulama"], "Code.exe")
            self.assertIn("alan_adi", satir)
            Depo(yol)  # İkinci açılış hata vermemeli


class UctanUcaTesti(unittest.TestCase):
    """Duraklatılmış ders videosu: eklenti varken boşta kalma kuralına takılır."""

    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "t.db"))
        self.t = 1_800_000_000.0
        self.bosta = 0.0
        self.tarayici = TarayiciDedektoru(saat=lambda: self.t)
        dedektorler = [
            PencereDedektoru(AYARLAR, okuyucu=lambda: ("brave.exe", "ML Lecture 5 - YouTube - Brave")),
            self.tarayici,
            BaslikDedektoru(AYARLAR),
            BostaDedektoru(AYARLAR, okuyucu=lambda: self.bosta),
        ]
        self.takipci = Takipci(AYARLAR, self.depo, dedektorler, KararMotoru(5, 15))

    def tearDown(self):
        self.klasor.cleanup()

    def ilerle(self, saniye, sesli):
        for _ in range(saniye):
            self.t += 1
            self.tarayici.rapor_al("youtube.com", sesli, True)
            self.takipci.tik(self.t)

    def test_oynayan_video_sayilir_duraklatilan_sayilmaz(self):
        self.ilerle(10, sesli=True)
        self.bosta = 600                                    # 10 dk klavye/fare yok
        self.ilerle(30, sesli=True)
        self.assertTrue(self.takipci.durum()["calisiyor"])  # video oynuyor: izliyor
        self.ilerle(30, sesli=False)                        # video duraklatıldı
        self.assertFalse(self.takipci.durum()["calisiyor"])

    def test_site_adi_oturuma_kaydedilir(self):
        self.ilerle(10, sesli=True)
        oturum = self.depo.oturumlari_getir(self.t - 100, self.t + 1)[0]
        self.assertEqual(oturum["alan_adi"], "youtube.com")


if __name__ == "__main__":
    unittest.main()
