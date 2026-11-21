"""Okunabilir adlar, site ayırma ve seri hesabı testleri."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from heatmap.depo import Depo
from heatmap.motor import Durum
from heatmap.ozet import (
    BILGISAYAR_DISI, DIGER_WEB, Adlandirici, en_uzun_seri, isi_haritasi, seri_hesapla, seviye,
)

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


class KategoriTestleri(unittest.TestCase):
    def test_kategorilere_grupla(self):
        a = Adlandirici({"kategoriler": {"Kod": ["VS Code", "GitHub"], "Video": ["youtube"]}})
        dokum = [{"ad": "VS Code", "sure_sn": 300}, {"ad": "YouTube", "sure_sn": 200},
                 {"ad": "GitHub", "sure_sn": 150}, {"ad": "Discord", "sure_sn": 50}]
        sonuc = a.kategorilere_grupla(dokum)
        self.assertEqual([(g["ad"], g["sure_sn"], g["icerik"]) for g in sonuc], [
            ("Kod", 450, ["VS Code", "GitHub"]),
            ("Video", 200, ["YouTube"]),        # büyük/küçük harf önemsiz
            ("Diğer", 50, ["Discord"]),
        ])

    def test_ornek_ayardaki_kategoriler_gecerli(self):
        from heatmap.ayarlar import ORNEK_DOSYA, _toml_oku
        a = Adlandirici(_toml_oku(ORNEK_DOSYA))
        self.assertEqual(a.kategori("VS Code"), "Kod")
        self.assertEqual(a.kategori("claude.ai"), "Yapay zekâ")
        self.assertEqual(a.kategori("Bilinmeyen Uygulama"), "Diğer")
        self.assertEqual(a.kategori(a.uygulama_adi("POWERPNT.EXE")), "Belge ve not")


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


class IsiHaritasiTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "test.db"))
        self.bugun = date(2026, 11, 19)  # Perşembe

    def tearDown(self):
        self.klasor.cleanup()

    def oturum(self, gun: date, saat: float, dakika: int):
        bas = datetime.combine(gun, datetime.min.time()).timestamp() + saat * 3600
        oid = self.depo.oturum_baslat(Durum("ders", "Code.exe", "pencere", "", "Code.exe", ""), bas)
        self.depo.oturum_bitisini_guncelle(oid, bas + dakika * 60)

    def test_gece_yarisini_gecen_oturum_iki_gune_bolunur(self):
        dun = self.bugun - timedelta(days=1)
        self.oturum(dun, 23.5, 60)  # 23:30 - 00:30
        gunler = self.depo.gunluk_sureler(dun, self.bugun)
        self.assertEqual([g["ders_sn"] for g in gunler], [1800, 1800])

    def test_isi_haritasi_izgarasi(self):
        self.oturum(self.bugun, 10, 130)
        self.oturum(self.bugun - timedelta(days=1), 10, 125)
        self.oturum(self.bugun - timedelta(days=3), 10, 30)
        v = isi_haritasi(self.depo, 120 * 60, self.bugun)
        self.assertEqual(len(v["gunler"]), 53 * 7)                  # tam ızgara
        self.assertEqual(date.fromisoformat(v["baslangic"]).weekday(), 0)  # Pazartesi'den başlar
        self.assertEqual(sum(g["gelecek"] for g in v["gunler"]), 3)   # Cuma, Cmt, Paz
        self.assertEqual(v["aktif_gun"], 3)
        self.assertEqual(v["hedef_gunu"], 2)
        self.assertEqual(v["en_uzun_seri"], 2)
        bugun_kaydi = next(g for g in v["gunler"] if g["tarih"] == self.bugun.isoformat())
        self.assertEqual(bugun_kaydi["seviye"], 4)

    def test_seviyeler(self):
        self.assertEqual([seviye(s, 7200) for s in (0, 600, 3000, 6000, 7200)], [0, 1, 2, 3, 4])
        self.assertEqual([seviye(s, 0) for s in (0, 600, 3000, 6000, 9000)], [0, 1, 2, 3, 4])

    def test_en_uzun_seri(self):
        gunler = [{"ders_sn": s} for s in (100, 200, 200, 0, 200, 200, 200)]
        self.assertEqual(en_uzun_seri(gunler, 150), 3)


if __name__ == "__main__":
    unittest.main()
