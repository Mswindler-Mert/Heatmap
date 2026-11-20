"""Proje adı değişikliğinde eski veritabanının yeni ada taşınması."""

import tempfile
import unittest
from pathlib import Path

from heatmap.main import ESKI_VERITABANI_ADI, VERITABANI_ADI, eski_veritabanini_tasi


class TasimaTesti(unittest.TestCase):
    def setUp(self):
        self._gecici = tempfile.TemporaryDirectory()
        self.klasor = Path(self._gecici.name)

    def tearDown(self):
        self._gecici.cleanup()

    def test_eski_dosya_ve_yan_dosyalar_tasinir(self):
        (self.klasor / ESKI_VERITABANI_ADI).write_text("eski veri")
        (self.klasor / (ESKI_VERITABANI_ADI + "-wal")).write_text("wal")
        self.assertTrue(eski_veritabanini_tasi(self.klasor))
        self.assertEqual((self.klasor / VERITABANI_ADI).read_text(), "eski veri")
        self.assertTrue((self.klasor / (VERITABANI_ADI + "-wal")).exists())
        self.assertFalse((self.klasor / ESKI_VERITABANI_ADI).exists())

    def test_yeni_dosya_varsa_dokunulmaz(self):
        (self.klasor / ESKI_VERITABANI_ADI).write_text("eski")
        (self.klasor / VERITABANI_ADI).write_text("yeni")
        self.assertFalse(eski_veritabanini_tasi(self.klasor))
        self.assertEqual((self.klasor / VERITABANI_ADI).read_text(), "yeni")
        self.assertTrue((self.klasor / ESKI_VERITABANI_ADI).exists())

    def test_eski_dosya_yoksa_bir_sey_yapilmaz(self):
        self.assertFalse(eski_veritabanini_tasi(self.klasor))
        self.assertFalse((self.klasor / VERITABANI_ADI).exists())


if __name__ == "__main__":
    unittest.main()
