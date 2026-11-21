"""Web API testleri: FastAPI'nin test istemcisiyle gerçek istekler.

Sunucu başlatılmaz; istekler doğrudan uygulamaya gider. Geçici bir veritabanı kullanılır.
Gerekli paket: httpx (requirements-dev.txt).

NOT: /api/otomatik-baslatma POST burada BİLEREK test edilmez; gerçek kayıt defterini
değiştirirdi. O modülün kendi testleri (test_otomatik_baslatma.py) geçici bir anahtar kullanır.
"""

import io
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from PIL import Image

from heatmap.dedektorler.tarayici import TarayiciDedektoru
from heatmap.depo import Depo
from heatmap.motor import Durum, KararMotoru
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur

AYARLAR = {
    "genel": {"tarama_araligi_sn": 1},
    "hedef": {"gunluk_dk": 120},
    "adlar": {"Code.exe": "VS Code"},
    "siteler": {"YouTube": ["YouTube", "youtube.com"]},
}
BASLIK = {"X-Heatmap": "1"}   # Veri değiştiren isteklerde zorunlu başlık
GIZLI = "COKGIZLIBASLIK"


class ApiTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.depo = Depo(os.path.join(self.klasor.name, "api.db"))
        self.tarayici = TarayiciDedektoru()
        takipci = Takipci(AYARLAR, self.depo, [], KararMotoru(5, 15))
        app = uygulama_olustur(takipci, self.depo, AYARLAR, self.tarayici)
        # base_url önemli: sunucu yalnızca 127.0.0.1 / localhost adını kabul eder.
        self.istemci = TestClient(app, base_url="http://127.0.0.1")
        self.bugun = date.today()

    def tearDown(self):
        self.istemci.close()
        self.klasor.cleanup()

    def oturum_ekle(self, uygulama, kaynak, baslik, dakika, alan_adi=""):
        bas = datetime.combine(self.bugun, datetime.min.time()).timestamp() + 3600
        oid = self.depo.oturum_baslat(Durum("ders", uygulama, kaynak, "", uygulama, baslik, alan_adi), bas)
        self.depo.oturum_bitisini_guncelle(oid, bas + dakika * 60)
        return oid

    # --- Güvenlik ---------------------------------------------------------
    def test_basliksiz_degistiren_istek_reddedilir(self):
        self.assertEqual(self.istemci.post("/api/duraklat", json={"duraklat": True}).status_code, 403)
        self.assertEqual(self.istemci.post("/api/duraklat", json={"duraklat": True}, headers=BASLIK).status_code, 200)
        self.assertEqual(self.istemci.delete("/api/kurallar/1").status_code, 403)

    def test_okuma_istekleri_baslik_istemez(self):
        self.assertEqual(self.istemci.get("/api/durum").status_code, 200)

    def test_yabanci_host_reddedilir(self):
        # DNS rebinding gibi saldırılara karşı: Host başlığı 127.0.0.1/localhost olmalı
        self.assertEqual(self.istemci.get("/api/durum", headers={"Host": "kotu.example"}).status_code, 400)

    # --- Sağlık verisi ----------------------------------------------------
    def test_saglik_kaydet_kismi_guncelle_sil(self):
        gun = self.bugun.isoformat()
        y = self.istemci.post("/api/saglik", json={"tarih": gun, "adim": 8200, "egzersiz_dk": 30}, headers=BASLIK)
        self.assertEqual(y.status_code, 200)
        # Yalnızca uykuyu gir: adım ve egzersiz silinmemeli
        self.istemci.post("/api/saglik", json={"tarih": gun, "uyku_dk": 450}, headers=BASLIK)
        kayit = self.istemci.get("/api/saglik").json()[0]
        self.assertEqual((kayit["adim"], kayit["egzersiz_dk"], kayit["uyku_dk"]), (8200, 30, 450))
        self.assertEqual(self.istemci.delete(f"/api/saglik/{gun}", headers=BASLIK).status_code, 200)
        self.assertEqual(self.istemci.get("/api/saglik").json(), [])
        self.assertEqual(self.istemci.delete(f"/api/saglik/{gun}", headers=BASLIK).status_code, 404)

    def test_saglik_dogrulama(self):
        yarin = (self.bugun + timedelta(days=1)).isoformat()
        bugun = self.bugun.isoformat()
        self.assertEqual(self.istemci.post("/api/saglik", json={"tarih": yarin, "adim": 5}, headers=BASLIK).status_code, 400)
        self.assertEqual(self.istemci.post("/api/saglik", json={"tarih": bugun}, headers=BASLIK).status_code, 400)
        self.assertEqual(self.istemci.post("/api/saglik", json={"tarih": bugun, "adim": -1}, headers=BASLIK).status_code, 422)
        self.assertEqual(self.istemci.post("/api/saglik", json={"tarih": bugun, "uyku_dk": 2000}, headers=BASLIK).status_code, 422)

    def test_gunluk_calisma_ve_saglik_birlesik(self):
        self.oturum_ekle("Code.exe", "pencere", "main.py", 90)
        self.depo.saglik_kaydet(self.bugun, adim=10_000)
        gun = self.bugun.isoformat()
        sonuc = self.istemci.get(f"/api/gunluk?baslangic={gun}&bitis={gun}").json()
        self.assertEqual(sonuc, [{"tarih": gun, "ders_sn": 5400, "adim": 10_000, "egzersiz_dk": None, "uyku_dk": None}])

    # --- Tarayıcı eklentisi -----------------------------------------------
    def test_eklenti_raporu_dedektore_ulasir(self):
        y = self.istemci.post("/api/tarayici", json={"alan_adi": "WWW.YouTube.com", "sesli": True}, headers=BASLIK)
        self.assertEqual(y.json(), {"tamam": True})
        self.assertEqual(self.tarayici._rapor["alan_adi"], "youtube.com")

    # --- Gizlilik: dashboard ve kart başlık sızdırmaz ----------------------
    def test_dashboard_baslik_icermez(self):
        self.oturum_ekle("brave.exe", "baslik", f"{GIZLI} - YouTube", 40, alan_adi="youtube.com")
        self.oturum_ekle("Code.exe", "pencere", f"{GIZLI}.py", 20)
        metin = self.istemci.get("/api/dashboard").text
        self.assertNotIn(GIZLI, metin)
        self.assertIn("YouTube", metin)
        self.assertIn("VS Code", metin)

    def test_kart_png_ve_gelecek_tarih(self):
        self.oturum_ekle("Code.exe", "pencere", f"{GIZLI}.py", 20)
        for tur in ("gunluk", "haftalik", "aylik", "yillik"):
            y = self.istemci.get(f"/api/kart?tur={tur}")
            self.assertEqual(y.headers["content-type"], "image/png")
            self.assertEqual(Image.open(io.BytesIO(y.content)).size, (1080, 1920))
        yarin = (self.bugun + timedelta(days=1)).isoformat()
        self.assertEqual(self.istemci.get(f"/api/kart?tarih={yarin}").status_code, 400)
        self.assertEqual(self.istemci.get("/api/kart?tur=bilinmeyen").status_code, 422)

    # --- Düzeltme ve öğrenme ----------------------------------------------
    def test_duzeltme_site_kurali_ogrenir(self):
        oid = self.oturum_ekle("brave.exe", "baslik", "Bir sayfa", 10, alan_adi="geeksforgeeks.org")
        y = self.istemci.post(f"/api/oturumlar/{oid}/duzelt",
                              json={"hukum": "ders", "ogren": False, "site_ogren": True}, headers=BASLIK)
        self.assertEqual(y.json()["ogrenilenler"], [{"tur": "alan", "desen": "geeksforgeeks.org"}])
        kurallar = self.istemci.get("/api/kurallar").json()
        self.assertEqual([(k["tur"], k["desen"], k["hukum"]) for k in kurallar], [("alan", "geeksforgeeks.org", "ders")])


if __name__ == "__main__":
    unittest.main()
