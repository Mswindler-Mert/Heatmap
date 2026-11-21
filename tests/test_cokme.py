"""Açılışta / çalışırken beklenmeyen hata: günlüğe yazılır, konsolsuzsa uyarı penceresi çıkar."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from heatmap.main import calistir


def bozuk_ana():
    raise RuntimeError("deneme hatası")


class CokmeTesti(unittest.TestCase):
    def setUp(self):
        self._gecici = tempfile.TemporaryDirectory()
        self.gunluk = Path(self._gecici.name) / "data" / "heatmap.log"
        self.pencereler = []

    def tearDown(self):
        self._gecici.cleanup()

    def test_konsolsuzken_pencere_gosterilir_ve_gunluge_yazilir(self):
        eski = sys.stdout
        sys.stdout = None  # pythonw.exe ile çalışmayı taklit et
        try:
            with self.assertRaises(SystemExit) as sonuc:
                calistir(bozuk_ana, pencere=self.pencereler.append, gunluk=self.gunluk)
        finally:
            sys.stdout = eski
        self.assertEqual(sonuc.exception.code, 1)
        self.assertEqual(len(self.pencereler), 1)
        self.assertIn("RuntimeError: deneme hatası", self.pencereler[0])
        self.assertIn("deneme hatası", self.gunluk.read_text(encoding="utf-8"))
        self.assertIn("ÇÖKME", self.gunluk.read_text(encoding="utf-8"))

    def test_terminalde_pencere_yerine_ekrana_yazar(self):
        hata_ciktisi = io.StringIO()
        with redirect_stderr(hata_ciktisi), self.assertRaises(SystemExit):
            calistir(bozuk_ana, pencere=self.pencereler.append, gunluk=self.gunluk)
        self.assertEqual(self.pencereler, [])
        self.assertIn("RuntimeError", hata_ciktisi.getvalue())

    def test_ctrl_c_hata_sayilmaz(self):
        def ctrl_c():
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            calistir(ctrl_c, pencere=self.pencereler.append, gunluk=self.gunluk)
        self.assertEqual(self.pencereler, [])
        self.assertFalse(self.gunluk.exists())

    def test_sorunsuz_calisma(self):
        calistir(lambda: None, pencere=self.pencereler.append, gunluk=self.gunluk)
        self.assertEqual(self.pencereler, [])


if __name__ == "__main__":
    unittest.main()
