"""Kamera modülü testleri. Gerçek kamera GEREKMEZ.

- Dedektör: sahte gözlem kaynağı ve sahte saatle eşikler.
- Karar motoru: SONRAKI_ADIMLAR.md 1.5'teki karar tablosu.
- Alt süreç: kamera_isci/isci.py gerçekten başlatılır (--sahte modunda).
- Gizlilik: işçinin kaynak kodunda kare kaydetme / ağ kodu olmadığı taranır.
"""

import re
import time
import unittest

from heatmap.dedektorler.kamera import ISCI_BETIGI, IsciSureci, KameraDedektoru, isci_komutu
from heatmap.motor import anlik_karar
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK, Sinyal

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
        self.d = KameraDedektoru(AYAR, kaynak=self.kaynak, saat=lambda: self.t)

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
        s["kamera"] = Sinyal("kamera", hukum, durum,
                             {"kamera_durumu": durum, "masada": masada, "not_alma_doldu": doldu})
    return s


EKRANA = (FIKRIM_YOK, "ekrana_bakiyor", True, False)
ASAGI = (FIKRIM_YOK, "asagi_bakiyor", True, False)
ASAGI_UZUN = (FIKRIM_YOK, "asagi_bakiyor", True, True)
TELEFON = (DERS_DEGIL, "telefon", True, False)
YOK = (DERS_DEGIL, "yok", False, False)
BILINMIYOR = (FIKRIM_YOK, "bilinmiyor", None, False)


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
        self.assertEqual(self.hukum(bosta=False, kamera=YOK), DERS)                    # klavye kullanılıyor

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
            d = KameraDedektoru(AYAR, kaynak=isci)
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
