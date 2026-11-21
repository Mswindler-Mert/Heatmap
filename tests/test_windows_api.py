"""windows_api duman testleri: gerçek Windows çağrıları hata vermeden doğru türde sonuç döndürüyor mu?

Öndeki pencere test makinesine göre değişeceği için değer kontrol edilmez, yalnızca tür.
"""

import unittest

from heatmap import windows_api


class WindowsApiTesti(unittest.TestCase):
    def test_aktif_pencere(self):
        surec, baslik = windows_api.aktif_pencereyi_oku()
        self.assertIsInstance(surec, str)
        self.assertIsInstance(baslik, str)

    def test_bosta_suresi(self):
        self.assertGreaterEqual(windows_api.bosta_suresini_oku(), 0.0)

    def test_gecersiz_pencere_cokmez(self):
        # Olmayan bir pencere tutamacı: boş ad dönmeli, hata vermemeli
        self.assertEqual(windows_api.pencerenin_sureci(0), "")


if __name__ == "__main__":
    unittest.main()
