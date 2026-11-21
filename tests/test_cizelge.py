"""Günlük zaman çizelgesi testleri."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from heatmap.depo import Depo
from heatmap.motor import Durum, KararMotoru
from heatmap.ozet import Adlandirici, zaman_cizelgesi
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur

GUN = date(2026, 11, 20)
GIZLI = "COKGIZLIBASLIK"


class CizelgeTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.depo = Depo(os.path.join(gecici.name, "t.db"))
        self.adl = Adlandirici({"adlar": {"Code.exe": "VS Code"}, "siteler": {"YouTube": ["youtube.com"]}})
        self.gun_bas = datetime.combine(GUN, datetime.min.time()).timestamp()

    def ekle(self, hukum, kaynak, uygulama, bas_dk, sure_dk, alan="", duzeltme=None):
        bas = self.gun_bas + bas_dk * 60
        oid = self.depo.oturum_baslat(Durum(hukum, uygulama, kaynak, "", uygulama, f"{GIZLI} başlık", alan), bas)
        self.depo.oturum_bitisini_guncelle(oid, bas + sure_dk * 60)
        if duzeltme:
            self.depo.oturum_duzelt(oid, duzeltme)
        return oid

    def test_parcalar_sirali_okunabilir_adli_ve_basliksiz(self):
        self.ekle("ders", "pencere", "Code.exe", 9 * 60, 30)
        self.ekle("ders", "baslik", "brave.exe", 9 * 60 + 30, 20, alan="youtube.com")
        self.ekle("ders_degil", "bosta", "", 10 * 60, 10)
        self.ekle("belirsiz", "pencere", "Bilinmeyen.exe", 11 * 60, 15, duzeltme="ders")
        c = zaman_cizelgesi(self.depo, self.adl, GUN)
        self.assertEqual([(p["ad"], p["tur"], p["hukum"]) for p in c["parcalar"]], [
            ("VS Code", "uygulama", "ders"),
            ("YouTube", "site", "ders"),
            ("Bilgisayar başında değil", "bosta", "ders_degil"),
            ("Bilinmeyen", "uygulama", "ders"),        # düzeltme geçerli hüküm
        ])
        self.assertEqual((c["parcalar"][0]["bas_dk"], c["parcalar"][0]["bit_dk"]), (540, 570))
        self.assertTrue(c["parcalar"][3]["duzeltildi"])
        self.assertEqual(c["toplam_sn"]["ders"], (30 + 20 + 15) * 60)
        self.assertNotIn(GIZLI, json.dumps(c, ensure_ascii=False))

    def test_gece_yarisini_gecen_oturum_kirpilir(self):
        self.ekle("ders", "pencere", "Code.exe", 23 * 60 + 30, 60)  # 23:30 - 00:30
        bugun = zaman_cizelgesi(self.depo, self.adl, GUN)["parcalar"]
        ertesi = zaman_cizelgesi(self.depo, self.adl, GUN + timedelta(days=1))["parcalar"]
        self.assertEqual((bugun[0]["bas_dk"], bugun[0]["bit_dk"]), (1410, 1440))
        self.assertEqual((ertesi[0]["bas_dk"], ertesi[0]["bit_dk"]), (0, 30))

    def test_bos_gun_ve_cok_kisa_parca(self):
        self.ekle("ders", "pencere", "Code.exe", 600, 0.005)  # 0,3 sn: çizilmez
        c = zaman_cizelgesi(self.depo, self.adl, GUN)
        self.assertEqual(c["parcalar"], [])

    def test_api_ucu(self):
        self.ekle("ders", "pencere", "Code.exe", 60, 5)
        app = uygulama_olustur(Takipci({"genel": {"tarama_araligi_sn": 1}}, self.depo, [], KararMotoru(5, 15)),
                               self.depo, {"adlar": {"Code.exe": "VS Code"}})
        with TestClient(app, base_url="http://127.0.0.1") as istemci:
            d = istemci.get(f"/api/zaman-cizelgesi?tarih={GUN.isoformat()}").json()
        self.assertEqual(d["parcalar"][0]["ad"], "VS Code")
        self.assertNotIn(GIZLI, json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
