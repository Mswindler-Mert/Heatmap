"""Okunabilir adlar, site ayırma ve seri hesabı testleri."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from ders_takip.depo import Depo
from ders_takip.motor import Durum
from ders_takip.ozet import BILGISAYAR_DISI, DIGER_WEB, Adlandirici, seri_hesapla

AYARLAR = {
    "adlar": {"Code.exe": "VS Code", "POWERPNT.EXE": "PowerPoint"},
    "siteler": {"YouTube": ["YouTube"], "GitHub": ["GitHub"], "claude.ai": ["Claude"]},
}


class AdTestleri(unittest.TestCase):
    def setUp(self):
        self.a = Adlandirici(AYARLAR)

    def test_eslesen_surec(self):
        self.assertEqual(self.a.uygulama_adi("code.exe"), "VS Code")   # harf duyarsız
        self.assertEqual(self.a.uygulama_adi("POWERPNT.EXE"), "PowerPoint")

    def test_eslesmeyen_surecte_exe_atilir(self):
        self.assertEqual(self.a.uygulama_adi("Discord.exe"), "Discord")

    def test_bos_surec(self):
        self.assertEqual(self.a.uygulama_adi(""), BILGISAYAR_DISI)

    def test_site_adi(self):
        self.assertEqual(self.a.site_adi("ML Lecture 5 - YouTube"), "YouTube")
        self.assertEqual(self.a.site_adi("Slayt özeti - Claude"), "claude.ai")
        self.assertEqual(self.a.site_adi("Rastgele bir sayfa"), DIGER_WEB)

    def test_birden_cok_site_kelimesinde_sondaki_kazanir(self):
        self.assertEqual(self.a.site_adi("GitHub Tutorial for Beginners - YouTube"), "YouTube")

    def test_etiket_tarayici_ve_uygulama(self):
        tarayici = {"kaynak": "baslik", "uygulama": "brave.exe", "baslik": "Gizli Video Adı - YouTube"}
        uygulama = {"kaynak": "pencere", "uygulama": "Code.exe", "baslik": "gizli_dosya.py"}
        self.assertEqual(self.a.etiket(tarayici), ("YouTube", "site"))
        self.assertEqual(self.a.etiket(uygulama), ("VS Code", "uygulama"))


class SeriTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "test.db"))
        self.bugun = date(2026, 11, 16)

    def tearDown(self):
        self.klasor.cleanup()

    def calis(self, gun_once: int, dakika: int):
        """`gun_once` gün önce öğlen başlayan `dakika` dakikalık ders oturumu ekler."""
        bas = datetime.combine(self.bugun - timedelta(days=gun_once), datetime.min.time()).timestamp() + 12 * 3600
        oid = self.depo.oturum_baslat(Durum("ders", "Code.exe", "pencere", "", "Code.exe", ""), bas)
        self.depo.oturum_bitisini_guncelle(oid, bas + dakika * 60)

    def test_ust_uste_gunler(self):
        for gun_once in (0, 1, 2):
            self.calis(gun_once, 130)
        self.calis(4, 130)                       # arada 3 gün önce boş: seri orada kesilir
        self.assertEqual(seri_hesapla(self.depo, 120 * 60, self.bugun), 3)

    def test_bugun_henuz_ulasilmadiysa_seri_bozulmaz(self):
        self.calis(0, 10)                        # bugün daha yolun başı
        self.calis(1, 130)
        self.calis(2, 130)
        self.assertEqual(seri_hesapla(self.depo, 120 * 60, self.bugun), 2)

    def test_hedef_tutmayan_gun_seriyi_keser(self):
        self.calis(1, 30)
        self.calis(2, 130)
        self.assertEqual(seri_hesapla(self.depo, 120 * 60, self.bugun), 0)


if __name__ == "__main__":
    unittest.main()
