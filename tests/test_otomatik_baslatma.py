"""Otomatik başlatma testleri.

Gerçek "Run" anahtarına DOKUNMAZ: testler HKEY_CURRENT_USER altında geçici bir
test anahtarı kullanır ve sonunda siler. Böylece testler bilgisayarın açılışını etkilemez.
"""

import unittest
import winreg

from heatmap import otomatik_baslatma as ob

TEST_ANAHTARI = r"Software\HeatmapTestOtomatikBaslatma"


class OtomatikBaslatmaTesti(unittest.TestCase):
    def tearDown(self):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_ANAHTARI)
        except FileNotFoundError:
            pass

    def test_ac_kapat(self):
        self.assertFalse(ob.acik_mi(TEST_ANAHTARI))
        self.assertTrue(ob.ayarla(True, TEST_ANAHTARI))
        self.assertEqual(ob._kayitli_komut(TEST_ANAHTARI), ob.baslatma_komutu())
        self.assertFalse(ob.ayarla(False, TEST_ANAHTARI))
        ob.kapat(TEST_ANAHTARI)  # Zaten kapalıyken hata vermemeli

    def test_komut_baslaticiyi_sessiz_calistirir(self):
        komut = ob.baslatma_komutu()
        self.assertIn("pythonw.exe", komut.lower())
        self.assertIn("baslat.pyw", komut)
        self.assertTrue(komut.endswith("--sessiz"))
        self.assertTrue(ob.BASLATICI.exists())

    def test_eski_komut_guncellenir(self):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, TEST_ANAHTARI, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, ob.DEGER_ADI, 0, winreg.REG_SZ, r'"C:\eski\yol\pythonw.exe" "C:\eski\baslat.pyw"')
        self.assertTrue(ob.guncel_tut(TEST_ANAHTARI))
        self.assertEqual(ob._kayitli_komut(TEST_ANAHTARI), ob.baslatma_komutu())
        self.assertFalse(ob.guncel_tut(TEST_ANAHTARI))  # Artık güncel

    def test_kapaliyken_guncel_tut_acmaz(self):
        self.assertFalse(ob.guncel_tut(TEST_ANAHTARI))
        self.assertFalse(ob.acik_mi(TEST_ANAHTARI))


if __name__ == "__main__":
    unittest.main()
