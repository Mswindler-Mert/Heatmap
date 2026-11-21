"""CSV dışa aktarma testleri."""

import csv
import io
import os
import tempfile
import unittest
from datetime import date, datetime

from heatmap.depo import Depo
from heatmap.disa_aktar import gunluk_csv, oturumlar_csv
from heatmap.motor import Durum
from heatmap.ozet import Adlandirici

GUN = date(2026, 11, 20)
GIZLI = "GIZLIBASLIK"


def oku(metin: str) -> list[list[str]]:
    assert metin.startswith("﻿"), "Excel için UTF-8 BOM eksik"
    return list(csv.reader(io.StringIO(metin[1:]), delimiter=";"))


class DisaAktarTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "t.db"))
        bas = datetime.combine(GUN, datetime.min.time()).timestamp() + 9 * 3600
        for i, (surec, kaynak, baslik, alan, dk) in enumerate([
            ("Code.exe", "pencere", f"{GIZLI}.py", "", 90),
            ("brave.exe", "baslik", f"{GIZLI} - YouTube", "youtube.com", 30),
        ]):
            oid = self.depo.oturum_baslat(Durum("ders", surec, kaynak, "", surec, baslik, alan), bas + i * 7200)
            self.depo.oturum_bitisini_guncelle(oid, bas + i * 7200 + dk * 60)
        self.depo.saglik_kaydet(GUN, adim=8200)
        self.adl = Adlandirici({"adlar": {"Code.exe": "VS Code"}, "siteler": {"YouTube": ["youtube.com"]}})

    def tearDown(self):
        self.klasor.cleanup()

    def test_gunluk(self):
        satirlar = oku(gunluk_csv(self.depo, GUN, GUN))
        self.assertEqual(satirlar, [["tarih", "calisma_dk", "adim", "egzersiz_dk", "uyku_dk"],
                                    ["2026-11-20", "120", "8200", "", ""]])

    def test_oturumlar_basliksiz_varsayilan(self):
        metin = oturumlar_csv(self.depo, self.adl, GUN, GUN)
        self.assertNotIn(GIZLI, metin)
        satirlar = oku(metin)
        self.assertEqual(satirlar[0][-1], "kaynak")
        self.assertEqual([(s[2], s[3], s[5], s[6]) for s in satirlar[1:]],
                         [("5400", "ders", "VS Code", ""), ("1800", "ders", "brave.exe", "YouTube")])

    def test_basliklar_istenirse_eklenir(self):
        satirlar = oku(oturumlar_csv(self.depo, self.adl, GUN, GUN, basliklar=True))
        self.assertEqual(satirlar[0][-1], "pencere_basligi")
        self.assertEqual(satirlar[1][-1], f"{GIZLI}.py")


if __name__ == "__main__":
    unittest.main()
