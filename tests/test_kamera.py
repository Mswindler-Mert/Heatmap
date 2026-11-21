"""Kamera modülü testleri. Gerçek kamera GEREKMEZ.

- Dedektör: sahte gözlem kaynağı ve sahte saatle eşikler.
- Karar motoru: SONRAKI_ADIMLAR.md 1.5'teki karar tablosu.
- Alt süreç: kamera_isci/isci.py gerçekten başlatılır (--sahte modunda).
- Gizlilik: işçinin kaynak kodunda kare kaydetme / ağ kodu olmadığı taranır.
"""

import os
import re
import tempfile
import time
import unittest
from pathlib import Path

from heatmap.dedektorler.bosta import BostaDedektoru
from heatmap.dedektorler.kamera import ISCI_BETIGI, IsciSureci, KameraDedektoru, isci_komutu
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.depo import Depo
from heatmap.motor import Durum, KararMotoru, anlik_karar
from heatmap.takipci import Takipci
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK, Sinyal

# Testler gerçek data/kamera_kalibrasyon.json dosyasını okumasın/yazmasın
_GECICI = tempfile.TemporaryDirectory()
KALIBRASYON = Path(_GECICI.name) / "kalibrasyon.json"

AYAR_PENCERE = {
    "genel": {"tarama_araligi_sn": 1},
    "pencere": {"ders_surecleri": ["Code.exe"], "ders_degil_surecleri": [], "tarayici_surecleri": [],
                "bilinmeyen_hukum": "belirsiz"},
    "bosta": {"esik_sn": 120, "video_esik_sn": 1800},
}

AYAR = {"kamera": {"yuz_yok_esik_sn": 30, "telefon_esik_sn": 20, "not_alma_esik_sn": 600,
                   "ekran_pitch": -5.0, "asagi_fark_derece": 18}}


class SahteKaynak:
    """İşçi yerine: testin verdiği son gözlemi döndürür."""

    def __init__(self):
        self.gozlem = None
        self.baslatildi = self.kapatildi = False

    def baslat(self):
        self.baslatildi = True

    def son_gozlem(self):
        return self.gozlem

    def kapat(self):
        self.kapatildi = True


class DedektorTesti(unittest.TestCase):
    def setUp(self):
        self.t = 1000.0
        self.kaynak = SahteKaynak()
        self.d = KameraDedektoru(AYAR, kaynak=self.kaynak, saat=lambda: self.t, kalibrasyon_dosyasi=KALIBRASYON)

    def gozle(self, saniye=0, **alanlar):
        """`saniye` kadar zaman ilerlet, o anki gözlemi ver ve sinyali oku."""
        self.t += saniye
        self.kaynak.gozlem = {"zaman": self.t, "hata": None, **alanlar}
        return self.d.oku({})

    def test_ilk_okumada_isci_baslar_kapatinca_durur(self):
        self.d.oku({})
        self.assertTrue(self.kaynak.baslatildi)
        self.d.kapat()
        self.assertTrue(self.kaynak.kapatildi)

    def test_veri_yoksa_ya_da_bayatsa_bilinmiyor(self):
        self.assertEqual(self.d.oku({}).detay["kamera_durumu"], "bilinmiyor")
        self.gozle(yuz_var=True, pitch=0.0)
        self.t += 11  # 10 sn'den eski gözlem
        s = self.d.oku({})
        self.assertEqual((s.hukum, s.detay["kamera_durumu"], s.detay["masada"]), (FIKRIM_YOK, "bilinmiyor", None))

    def test_hata_bildirimi(self):
        s = self.gozle(hata="Kamera açılamadı")
        self.assertEqual(s.detay["kamera_durumu"], "bilinmiyor")
        self.assertIn("Kamera açılamadı", s.aciklama)

    def test_yuz_yok_esigi(self):
        self.gozle(yuz_var=False)
        s = self.gozle(29, yuz_var=False)
        self.assertEqual((s.hukum, s.detay["kamera_durumu"], s.detay["masada"]), (FIKRIM_YOK, "kayboldu", False))
        s = self.gozle(1, yuz_var=False)
        self.assertEqual((s.hukum, s.detay["kamera_durumu"]), (DERS_DEGIL, "yok"))
        s = self.gozle(1, yuz_var=True, pitch=-5.0)   # geri geldi: sayaç sıfırlanır
        self.assertEqual(s.detay["kamera_durumu"], "ekrana_bakiyor")

    def test_kalibrasyona_gore_asagi_bakma(self):
        # ekran_pitch -5, fark 18 -> -23'ten aşağısı "aşağı bakıyor"
        self.assertEqual(self.gozle(yuz_var=True, pitch=-20.0).detay["kamera_durumu"], "ekrana_bakiyor")
        self.assertEqual(self.gozle(yuz_var=True, pitch=-30.0).detay["kamera_durumu"], "asagi_bakiyor")

    def test_not_alma_esigi(self):
        self.gozle(yuz_var=True, pitch=-30.0)
        self.assertFalse(self.gozle(599, yuz_var=True, pitch=-30.0).detay["not_alma_doldu"])
        self.assertTrue(self.gozle(1, yuz_var=True, pitch=-30.0).detay["not_alma_doldu"])

    def test_telefon_esigi(self):
        self.gozle(yuz_var=True, pitch=-30.0, telefon_var=True)
        self.assertEqual(self.gozle(19, yuz_var=True, pitch=-30.0, telefon_var=True).hukum, FIKRIM_YOK)
        s = self.gozle(1, yuz_var=True, pitch=-30.0, telefon_var=True)
        self.assertEqual((s.hukum, s.detay["kamera_durumu"]), (DERS_DEGIL, "telefon"))


# --------------------------------------------------------------------------
#  Karar tablosu (SONRAKI_ADIMLAR.md 1.5)
# --------------------------------------------------------------------------
def sinyaller(icerik=DERS, video=False, bosta=False, video_esigi_asildi=False, kamera=None):
    """icerik: ekrandaki içeriğin hükmü. kamera: (hüküm, durum, masada, not_alma_doldu) ya da None."""
    s = {
        "pencere": Sinyal("pencere", FIKRIM_YOK, "", {"surec": "brave.exe", "baslik": "x", "tarayici": True}),
        "baslik": Sinyal("baslik", icerik, "", {"temiz_baslik": "Ders videosu", "video": video, "alan_adi": ""}),
        "bosta": Sinyal("bosta", DERS_DEGIL if bosta else FIKRIM_YOK, "boşta",
                        {"bosta_sn": 999 if bosta else 0, "video_esigi_asildi": video_esigi_asildi}),
    }
    if kamera:
        hukum, durum, masada, doldu = kamera
        # sure_sn 31: durum (örn. yüz yok) 31 sn'dir sürüyor
        s["kamera"] = Sinyal("kamera", hukum, durum,
                             {"kamera_durumu": durum, "masada": masada, "not_alma_doldu": doldu, "sure_sn": 31})
    return s


EKRANA = (FIKRIM_YOK, "ekrana_bakiyor", True, False)
ASAGI = (FIKRIM_YOK, "asagi_bakiyor", True, False)
ASAGI_UZUN = (FIKRIM_YOK, "asagi_bakiyor", True, True)
TELEFON = (DERS_DEGIL, "telefon", True, False)
YOK = (DERS_DEGIL, "yok", False, False)
BILINMIYOR = (FIKRIM_YOK, "bilinmiyor", None, False)


class AcKapatKalibrasyonTesti(unittest.TestCase):
    def setUp(self):
        self.t = 1000.0
        self.kaynak = SahteKaynak()
        self.dosya = Path(_GECICI.name) / f"kal_{id(self)}.json"
        self.d = KameraDedektoru(AYAR, kaynak=self.kaynak, saat=lambda: self.t, kalibrasyon_dosyasi=self.dosya)

    def ilerle(self, saniye):
        """kalibre_et() içindeki beklemeyi taklit eder: zamanı ilerletir, yeni bir gözlem üretir."""
        self.t += saniye
        self._sira = getattr(self, "_sira", -1) + 1
        pitch = (-12.0, -11.0, -10.0)[self._sira % 3]  # Sırayla -12, -11, -10: ortanca -11
        self.kaynak.gozlem = {"zaman": self.t, "yuz_var": True, "pitch": pitch, "hata": None}

    def test_kapatinca_isci_durur_sinyal_kapali(self):
        self.d.oku({})
        self.d.ayarla_acik(False)
        self.assertTrue(self.kaynak.kapatildi)
        self.assertEqual(self.d.oku({}).detay["kamera_durumu"], "kapali")
        self.d.ayarla_acik(True)
        self.kaynak.gozlem = {"zaman": self.t, "yuz_var": True, "pitch": -5.0, "hata": None}
        self.assertEqual(self.d.oku({}).detay["kamera_durumu"], "ekrana_bakiyor")

    def test_kalibrasyon_ortancayi_kaydeder_ve_yeniden_okunur(self):
        self.d.oku({})  # işçiyi başlat
        deger = self.d.kalibre_et(sure_sn=6, bekle=self.ilerle)
        self.assertEqual(deger, -11.0)
        self.assertEqual(self.d.durum_bilgisi()["asagi_esigi"], -29.0)   # -11 - 18
        yeni = KameraDedektoru(AYAR, kaynak=SahteKaynak(), kalibrasyon_dosyasi=self.dosya)
        self.assertEqual(yeni.ekran_pitch, -11.0)                        # ayardaki -5 yerine ölçülen

    def test_yuz_yokken_kalibrasyon_hata_verir(self):
        self.d.oku({})
        with self.assertRaises(ValueError):
            self.d.kalibre_et(sure_sn=2, bekle=lambda s: setattr(self, "t", self.t + s))
        self.assertFalse(self.dosya.exists())


class GeriyeDonukTesti(unittest.TestCase):
    """Masadan kalkınca yüzün görünmediği 30 sn çalışma sayılmamalı."""

    def test_motor_gecisi_geriye_ceker(self):
        motor = KararMotoru(5, 15)
        motor.guncelle(Durum(DERS, "Code.exe"), 0)
        gecis = motor.guncelle(Durum(DERS_DEGIL, "kamera", geriye_sn=30), 130)
        self.assertIsNotNone(gecis)          # 30 sn >= 15 sn tolerans: hemen karar
        self.assertEqual(gecis.zaman, 100)   # oturum yüzün kaybolduğu anda biter

    def test_mevcut_durumun_baslangicindan_geriye_gidilmez(self):
        motor = KararMotoru(5, 15)
        motor.guncelle(Durum(DERS, "Code.exe"), 120)
        self.assertIsNone(motor.guncelle(Durum(DERS_DEGIL, "kamera", geriye_sn=30), 130))
        self.assertEqual(motor.guncelle(Durum(DERS_DEGIL, "kamera", geriye_sn=35), 135).zaman, 120)

    def test_uctan_uca_veritabani(self):
        with tempfile.TemporaryDirectory() as klasor:
            depo = Depo(os.path.join(klasor, "t.db"))
            kaynak = SahteKaynak()
            saat = {"t": 1_800_000_000.0}
            kamera = KameraDedektoru(AYAR, kaynak=kaynak, saat=lambda: saat["t"],
                                     kalibrasyon_dosyasi=KALIBRASYON)
            bosta = {"sn": 0.0}
            dedektorler = [
                PencereDedektoru(AYAR_PENCERE, okuyucu=lambda: ("Code.exe", "main.py")),
                BostaDedektoru(AYAR_PENCERE, okuyucu=lambda: bosta["sn"]),
                kamera,
            ]
            takipci = Takipci(AYAR_PENCERE, depo, dedektorler, KararMotoru(5, 15))
            bas = saat["t"]

            def ilerle(saniye, yuz):
                for _ in range(saniye):
                    saat["t"] += 1
                    if not yuz:
                        bosta["sn"] += 1  # masadan kalkınca klavye/fare de durur
                    kaynak.gozlem = {"zaman": saat["t"], "yuz_var": yuz, "pitch": -5.0, "hata": None}
                    takipci.tik(saat["t"])

            ilerle(60, yuz=True)    # 60 sn çalışma
            ilerle(60, yuz=False)   # kalktı
            sure = depo.ders_suresi(bas, saat["t"] + 1)
            self.assertAlmostEqual(sure, 60, delta=2)   # eskiden ~90 sn sayılırdı


class KararTablosuTesti(unittest.TestCase):
    def hukum(self, **kw):
        return anlik_karar(sinyaller(**kw)).hukum

    def test_video_bosta_ekrana_bakiyor_sure_siniri_yok(self):
        # Video eşiği aşılmış olsa bile masada olduğu için sayılır
        self.assertEqual(self.hukum(video=True, bosta=True, video_esigi_asildi=True, kamera=EKRANA), DERS)

    def test_video_bosta_not_aliyor(self):
        self.assertEqual(self.hukum(video=True, bosta=True, kamera=ASAGI), DERS)
        self.assertEqual(self.hukum(video=True, bosta=True, kamera=ASAGI_UZUN), BELIRSIZ)

    def test_telefon_her_zaman_veto(self):
        self.assertEqual(self.hukum(video=True, bosta=True, kamera=TELEFON), DERS_DEGIL)
        self.assertEqual(self.hukum(bosta=False, kamera=TELEFON), DERS_DEGIL)

    def test_yuz_yok_bostaysa_veto_girdi_varsa_degil(self):
        self.assertEqual(self.hukum(video=True, bosta=True, kamera=YOK), DERS_DEGIL)   # video eşiği beklenmez
        self.assertEqual(self.hukum(bosta=False, kamera=YOK), DERS)   # yüz kaybolduktan sonra klavye kullanıldı

    def test_yuz_kaybolduktan_sonra_girdi_yoksa_esik_beklenmeden_veto(self):
        # Boşta eşiği (120 sn) dolmamış ama yüz kaybolduğundan beri (31 sn) hiç girdi yok: kalkmış
        s = sinyaller(bosta=False, kamera=YOK)
        s["bosta"].detay["bosta_sn"] = 40
        self.assertEqual(anlik_karar(s).hukum, DERS_DEGIL)

    def test_pdf_okurken_masada(self):
        # Video değil (PDF/IDE), klavye boşta, masada ekrana bakıyor: okuyor
        self.assertEqual(self.hukum(video=False, bosta=True, kamera=EKRANA), DERS)

    def test_calisma_disi_icerigi_kamera_yukseltmez(self):
        self.assertEqual(self.hukum(icerik=DERS_DEGIL, bosta=True, kamera=EKRANA), DERS_DEGIL)

    def test_belirsiz_icerik_belirsiz_kalir(self):
        self.assertEqual(self.hukum(icerik=BELIRSIZ, bosta=True, kamera=EKRANA), BELIRSIZ)

    def test_klavye_kullanilirken_asagi_bakmak_sorun_degil(self):
        self.assertEqual(self.hukum(bosta=False, kamera=ASAGI_UZUN), DERS)

    def test_kamera_bilinmiyorsa_eski_davranis(self):
        self.assertEqual(self.hukum(video=False, bosta=True, kamera=BILINMIYOR), DERS_DEGIL)
        self.assertEqual(self.hukum(video=True, bosta=True, kamera=BILINMIYOR), DERS)
        self.assertEqual(self.hukum(video=True, bosta=True, video_esigi_asildi=True, kamera=BILINMIYOR), DERS_DEGIL)


# --------------------------------------------------------------------------
#  Gerçek alt süreç (kamera yok, --sahte modu)
# --------------------------------------------------------------------------
class AltSurecTesti(unittest.TestCase):
    def bekle(self, isci, kosul, sure=15):
        bitis = time.time() + sure
        while time.time() < bitis:
            g = isci.son_gozlem()
            if g and kosul(g):
                return g
            time.sleep(0.1)
        self.fail(f"İşçiden beklenen gözlem gelmedi; son: {isci.son_gozlem()}")

    def test_sahte_isci_ile_hat(self):
        komut = isci_komutu({"sahte_senaryo": "not_aliyor", "kare_araligi_sn": 0.2})
        isci = IsciSureci(komut)
        isci.baslat()
        try:
            g = self.bekle(isci, lambda g: g.get("yuz_var") is True)
            self.assertEqual(g["pitch"], -30.0)
            d = KameraDedektoru(AYAR, kaynak=isci, kalibrasyon_dosyasi=KALIBRASYON)
            self.assertEqual(d.oku({}).detay["kamera_durumu"], "asagi_bakiyor")
        finally:
            isci.kapat()
        self.assertIsNotNone(isci._surec)
        self.assertIsNotNone(isci._surec.poll(), "işçi süreci kapanmadı")

    def test_hata_mesaji_turkce_bozulmadan_gelir(self):
        isci = IsciSureci(isci_komutu({"sahte_senaryo": "hata", "kare_araligi_sn": 0.2}))
        isci.baslat()
        try:
            g = self.bekle(isci, lambda g: g.get("hata"))
            self.assertEqual(g["hata"], "Kamera açılamadı (sahte)")
        finally:
            isci.kapat()

    def test_baslatilamayan_isci_hata_verir_cokmez(self):
        isci = IsciSureci([r"C:\olmayan\python.exe", "x.py"])
        isci.baslat()
        try:
            g = self.bekle(isci, lambda g: g.get("hata"), sure=5)
            self.assertIn("başlatılamadı", g["hata"])
        finally:
            isci.kapat()


class GizlilikTesti(unittest.TestCase):
    def test_iscide_kare_kaydetme_ve_ag_kodu_yok(self):
        kaynak = ISCI_BETIGI.read_text(encoding="utf-8")
        kod = "\n".join(s for s in kaynak.splitlines() if not s.strip().startswith("#"))
        kod = re.sub(r'"""[\s\S]*?"""', "", kod)  # Açıklama metinlerini (docstring) atla
        for yasak in ("imwrite", "VideoWriter", ".save(", "socket", "requests", "urllib", "http.client"):
            self.assertNotIn(yasak, kod, f"kamera işçisinde yasak kullanım: {yasak}")


if __name__ == "__main__":
    unittest.main()
