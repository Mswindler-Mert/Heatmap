"""Karar motoru testleri.

Çalıştırmak için proje klasöründe:
    .venv\\Scripts\\python -m unittest -v
"""

import unittest

from heatmap.motor import Durum, KararMotoru, anlik_karar
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK, Sinyal

# Testlerde kullanacağımız hazır durumlar
KOD = Durum(DERS, "Code.exe")
DISCORD = Durum(DERS_DEGIL, "Discord.exe")
SAYFA = Durum(BELIRSIZ, "chrome.exe|Rastgele sayfa")
VIDEO_1 = Durum(DERS, "chrome.exe|ML Lecture 1 - YouTube")
VIDEO_2 = Durum(DERS, "chrome.exe|ML Lecture 2 - YouTube")


def yeni_motor() -> KararMotoru:
    return KararMotoru(baslatma_sn=5, durdurma_sn=15)


class ToleransTestleri(unittest.TestCase):
    def test_ilk_durum_hemen_kabul_edilir(self):
        motor = yeni_motor()
        gecis = motor.guncelle(KOD, simdi=100)
        self.assertEqual(gecis.durum, KOD)
        self.assertEqual(gecis.zaman, 100)

    def test_kisa_kacamak_sayaci_durdurmaz(self):
        motor = yeni_motor()
        motor.guncelle(KOD, 0)
        # 10 saniye Discord'a bak, sonra geri dön
        for t in range(1, 11):
            self.assertIsNone(motor.guncelle(DISCORD, t))
        self.assertIsNone(motor.guncelle(KOD, 11))
        self.assertEqual(motor.mevcut, KOD)
        # Geri dönünce sayaç sıfırlanmalı: yeni bir 10 saniyelik kaçamak da durdurmamalı
        for t in range(12, 22):
            self.assertIsNone(motor.guncelle(DISCORD, t))
        self.assertEqual(motor.mevcut, KOD)

    def test_uzun_ayrilik_durdurur_ve_gecis_geriye_donuktur(self):
        motor = yeni_motor()
        motor.guncelle(KOD, 0)
        gecis = None
        for t in range(10, 26):  # Discord'a t=10'da geçildi
            gecis = motor.guncelle(DISCORD, t)
            if gecis:
                break
        self.assertIsNotNone(gecis)
        self.assertEqual(gecis.durum, DISCORD)
        self.assertEqual(gecis.zaman, 10)   # Karar t=25'te verildi ama oturum t=10'da bitti
        self.assertEqual(t, 25)

    def test_belirsiz_ile_ders_disi_arasinda_gezinmek_de_durdurur(self):
        motor = yeni_motor()
        motor.guncelle(KOD, 0)
        gecis = None
        for t in range(1, 30):
            anlik = DISCORD if t % 2 else SAYFA  # Her saniye değişiyor
            gecis = motor.guncelle(anlik, t)
            if gecis:
                break
        self.assertIsNotNone(gecis)
        self.assertNotEqual(gecis.durum.hukum, DERS)
        self.assertEqual(gecis.zaman, 1)

    def test_ders_baslamasi_icin_kesintisiz_sure_gerekir(self):
        motor = yeni_motor()
        motor.guncelle(DISCORD, 0)
        # 3 sn ders, sonra geri: başlamamalı
        for t in (1, 2, 3):
            self.assertIsNone(motor.guncelle(KOD, t))
        self.assertIsNone(motor.guncelle(DISCORD, 4))
        # 5 sn kesintisiz ders: başlamalı ve başlangıç geriye dönük olmalı
        for t in (10, 11, 12, 13, 14):
            self.assertIsNone(motor.guncelle(KOD, t))
        gecis = motor.guncelle(KOD, 15)
        self.assertEqual(gecis.durum, KOD)
        self.assertEqual(gecis.zaman, 10)

    def test_belirsizden_sonra_gelen_ders_geriye_fazla_sayilmaz(self):
        motor = yeni_motor()
        motor.guncelle(DISCORD, 0)
        for t in range(1, 11):          # 10 sn belirsiz sayfa
            motor.guncelle(SAYFA, t)
        gecis = None
        for t in range(11, 20):         # sonra ders
            gecis = motor.guncelle(KOD, t)
            if gecis:
                break
        self.assertEqual(gecis.durum, KOD)
        self.assertEqual(gecis.zaman, 11)  # Belirsiz geçen 10 sn derse eklenmedi

    def test_ayni_hukumde_sekme_degisince_oturum_bolunur(self):
        motor = yeni_motor()
        motor.guncelle(VIDEO_1, 0)
        gecis = None
        for t in range(100, 120):
            gecis = motor.guncelle(VIDEO_2, t)
            if gecis:
                break
        self.assertEqual(gecis.durum, VIDEO_2)
        self.assertEqual(gecis.zaman, 100)


def sinyaller(pencere_hukum=FIKRIM_YOK, tarayici=False, baslik_hukum=None, video=False,
              bosta=False, video_esigi_asildi=False):
    """Testler için sahte sinyal seti üretir."""
    sonuc = {
        "pencere": Sinyal("pencere", pencere_hukum, "",
                          {"surec": "chrome.exe" if tarayici else "Code.exe",
                           "baslik": "ham başlık", "tarayici": tarayici}),
        "bosta": Sinyal("bosta", DERS_DEGIL if bosta else FIKRIM_YOK, "boşta",
                        {"bosta_sn": 999 if bosta else 0, "video_esigi_asildi": video_esigi_asildi}),
    }
    if baslik_hukum is not None:
        sonuc["baslik"] = Sinyal("baslik", baslik_hukum, "", {"temiz_baslik": "temiz başlık", "video": video})
    return sonuc


class AnlikKararTestleri(unittest.TestCase):
    def test_ders_uygulamasi(self):
        durum = anlik_karar(sinyaller(pencere_hukum=DERS))
        self.assertEqual(durum.hukum, DERS)
        self.assertEqual(durum.kaynak, "pencere")

    def test_tarayicida_karari_baslik_verir(self):
        durum = anlik_karar(sinyaller(tarayici=True, baslik_hukum=BELIRSIZ))
        self.assertEqual(durum.hukum, BELIRSIZ)
        self.assertEqual(durum.kaynak, "baslik")
        self.assertEqual(durum.baslik, "temiz başlık")

    def test_bosta_kalmak_ders_uygulamasini_durdurur(self):
        durum = anlik_karar(sinyaller(pencere_hukum=DERS, bosta=True))
        self.assertEqual(durum.hukum, DERS_DEGIL)
        self.assertEqual(durum.kaynak, "bosta")

    def test_video_izlerken_bosta_kalmak_durdurmaz(self):
        durum = anlik_karar(sinyaller(tarayici=True, baslik_hukum=DERS, video=True, bosta=True))
        self.assertEqual(durum.hukum, DERS)

    def test_video_esigi_de_asilirsa_durur(self):
        durum = anlik_karar(sinyaller(tarayici=True, baslik_hukum=DERS, video=True,
                                      bosta=True, video_esigi_asildi=True))
        self.assertEqual(durum.hukum, DERS_DEGIL)

    def test_kamera_vetosu(self):
        s = sinyaller(pencere_hukum=DERS)
        s["kamera"] = Sinyal("kamera", DERS_DEGIL, "Yüz görünmüyor")
        self.assertEqual(anlik_karar(s).hukum, DERS_DEGIL)


if __name__ == "__main__":
    unittest.main()
