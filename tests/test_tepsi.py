"""Sistem tepsisi menüsü testleri. Gerçek tepsi ikonu oluşturulmaz (pystray.Icon sahteyle
değiştirilir) ve gerçek kayıt defterine dokunulmaz (otomatik başlatma çağrıları sahte)."""

import unittest
from unittest import mock

from heatmap import tepsi as tepsi_modulu
from heatmap.tepsi import Tepsi, ikon_durumu


class SahteTakipci:
    def __init__(self):
        self.duraklatildi = False

    def duraklat(self, deger):
        self.duraklatildi = deger


class SahteKamera:
    def __init__(self):
        self.acik = True

    def ayarla_acik(self, acik):
        self.acik = acik


class SahteMiniSayac:
    def __init__(self):
        self.acik = False

    def degistir(self):
        self.acik = not self.acik
        return self.acik


def tepsi_kur(kamera=None, mini_sayac=None):
    with mock.patch.object(tepsi_modulu.pystray, "Icon") as sahte_ikon:
        t = Tepsi(SahteTakipci(), "http://127.0.0.1:8765", kamera, mini_sayac=mini_sayac)
    menu = sahte_ikon.call_args.args[3]  # pystray.Icon(ad, resim, başlık, menü)
    ayirici = tepsi_modulu.pystray.Menu.SEPARATOR  # menüdeki çizgi; seçenek değil
    return t, {oge.text: oge for oge in menu.items if oge is not ayirici}


class TepsiMenuTesti(unittest.TestCase):
    def test_kamera_yoksa_secenegi_gizli(self):
        _, ogeler = tepsi_kur(kamera=None)
        self.assertFalse(ogeler["Kamera açık"].visible)
        self.assertTrue(ogeler["Arayüzü aç"].visible)
        self.assertTrue(ogeler["Arayüzü aç"].default)  # ikona tıklayınca arayüz açılır

    def test_kamera_ac_kapat(self):
        kamera = SahteKamera()
        _, ogeler = tepsi_kur(kamera)
        oge = ogeler["Kamera açık"]
        self.assertTrue(oge.visible)
        self.assertTrue(oge.checked)
        oge(None)  # menüde tıklamak
        self.assertFalse(kamera.acik)
        self.assertFalse(oge.checked)

    def test_duraklat(self):
        t, ogeler = tepsi_kur()
        ogeler["Takibi duraklat"](None)
        self.assertTrue(t.takipci.duraklatildi)
        self.assertTrue(ogeler["Takibi duraklat"].checked)

    def test_otomatik_baslatma_kayit_defterine_dokunmadan(self):
        _, ogeler = tepsi_kur()
        with mock.patch.object(tepsi_modulu.otomatik_baslatma, "acik_mi", return_value=False), \
             mock.patch.object(tepsi_modulu.otomatik_baslatma, "ayarla") as ayarla:
            self.assertFalse(ogeler["Windows açılışında başlat"].checked)
            ogeler["Windows açılışında başlat"](None)
        ayarla.assert_called_once_with(True)

    def test_mini_sayac_ac_kapat(self):
        mini = SahteMiniSayac()
        _, ogeler = tepsi_kur(mini_sayac=mini)
        oge = ogeler["Mini sayacı göster"]
        self.assertTrue(oge.visible)
        self.assertFalse(oge.checked)
        oge(None)
        self.assertTrue(mini.acik)
        self.assertTrue(oge.checked)

    def test_beklenen_secenekler(self):
        _, ogeler = tepsi_kur()
        self.assertEqual(list(ogeler), ["Arayüzü aç", "Mini sayacı göster", "Takibi duraklat",
                                        "Ayar dosyasını aç", "Kamera açık", "Windows açılışında başlat", "Çıkış"])


class IkonDurumuTesti(unittest.TestCase):
    def durum(self, **kw):
        return {"duraklatildi": False, "calisiyor": False, "hukum": "ders_degil", "bugun_ders_sn": 3725, **kw}

    def test_renkler_ve_ipucu(self):
        self.assertEqual(ikon_durumu(self.durum(calisiyor=True)),
                         ("ders", "Heatmap · bugün 1 sa 2 dk · sayaç çalışıyor"))
        self.assertEqual(ikon_durumu(self.durum(hukum="belirsiz"))[0], "belirsiz")
        self.assertEqual(ikon_durumu(self.durum())[0], "durdu")
        # Duraklatma her şeyden önce gelir
        self.assertEqual(ikon_durumu(self.durum(calisiyor=True, duraklatildi=True))[1][-12:], "duraklatıldı")

    def test_takipci_henuz_baslamadiysa(self):
        # Program yeni açıldığında durum sözlüğünde "hukum" olmayabilir
        self.assertEqual(ikon_durumu({"duraklatildi": False, "calisiyor": False, "bugun_ders_sn": 0})[0], "durdu")


if __name__ == "__main__":
    unittest.main()
