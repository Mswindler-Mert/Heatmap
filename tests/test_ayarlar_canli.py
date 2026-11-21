"""Ayarları arayüzden kaydetme ve yeniden başlatmadan uygulama (canlı yükleme) testleri.

Gerçek config.toml'a dokunulmaz: her test geçici bir klasörde kendi config dosyasını kullanır.
"""

import os
import tempfile
import tomllib
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from heatmap.ayarlar import ORNEK_DOSYA, ayarlari_yukle
from heatmap.dedektorler.kamera import KameraDedektoru
from heatmap.dedektorler.tarayici import TarayiciDedektoru
from heatmap.depo import Depo
from heatmap.main import dedektorleri_kur
from heatmap.motor import Durum, KararMotoru
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur

BASLIK = {"X-Heatmap": "1"}
KISISEL = """# Kişisel ayarlarım
[hedef]
gunluk_dk = 120   # günlük hedef

[pencere]
ders_surecleri = [
    "Code.exe",   # VS Code
]
"""


class AyarKaydetmeApiTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.klasor = Path(gecici.name)
        self.dosya = self.klasor / "config.toml"
        self.dosya.write_text(KISISEL, encoding="utf-8")
        ayarlar = ayarlari_yukle(ORNEK_DOSYA, self.dosya)
        depo = Depo(os.path.join(self.klasor, "t.db"))
        takipci = Takipci(ayarlar, depo, [], KararMotoru(5, 15))
        self.istemci = TestClient(
            uygulama_olustur(takipci, depo, ayarlar, ayar_dosyasi=self.dosya, yedek_klasoru=self.klasor / "yedek"),
            base_url="http://127.0.0.1")
        self.addCleanup(self.istemci.close)

    def kaydet(self, degisiklikler):
        return self.istemci.post("/api/ayarlar", json={"degisiklikler": degisiklikler}, headers=BASLIK)

    def test_alanlar_ve_degerler(self):
        d = self.istemci.get("/api/ayarlar").json()
        self.assertTrue(d["kaydedilebilir"])
        alanlar = {a["anahtar"]: a for g in d["gruplar"] for a in g["alanlar"]}
        self.assertEqual(alanlar["hedef.gunluk_dk"]["deger"], 120)
        self.assertEqual(alanlar["pencere.ders_surecleri"]["deger"], ["Code.exe"])

    def test_kaydedilen_hedef_hemen_gecerli(self):
        self.assertEqual(self.istemci.get("/api/seri").json()["hedef_sn"], 7200)
        y = self.kaydet({"hedef.gunluk_dk": 90, "kart.ust_metin": "Mert"})
        self.assertEqual(y.status_code, 200)
        self.assertEqual(y.json()["degisen"], ["hedef.gunluk_dk", "kart.ust_metin"])
        self.assertEqual(self.istemci.get("/api/seri").json()["hedef_sn"], 5400)  # yeniden başlatmadan
        metin = self.dosya.read_text(encoding="utf-8")
        self.assertIn("gunluk_dk = 90   # günlük hedef", metin)
        self.assertEqual(tomllib.loads(metin)["kart"]["ust_metin"], "Mert")
        self.assertEqual(len(list((self.klasor / "yedek").glob("config-*.toml"))), 1)

    def test_degismeyen_deger_dosyaya_yazilmaz(self):
        once = self.dosya.read_text(encoding="utf-8")
        y = self.kaydet({"hedef.gunluk_dk": 120})
        self.assertEqual(y.json()["degisen"], [])
        self.assertEqual(self.dosya.read_text(encoding="utf-8"), once)

    def test_hatali_deger_hicbir_sey_yazmaz(self):
        once = self.dosya.read_text(encoding="utf-8")
        y = self.kaydet({"hedef.gunluk_dk": 90, "tolerans.durdurma_sn": -1})
        self.assertEqual(y.status_code, 400)
        self.assertIn("tolerans.durdurma_sn", y.json()["detail"]["hatalar"])
        self.assertEqual(self.dosya.read_text(encoding="utf-8"), once)  # geçerli olan da yazılmadı

    def test_bozuk_dosyada_409(self):
        self.dosya.write_text('[hedef]\ngunluk_dk = "120\n', encoding="utf-8")
        y = self.kaydet({"hedef.gunluk_dk": 60})
        self.assertEqual(y.status_code, 409)
        self.assertIn("yazım hatası", y.json()["detail"])

    def test_basliksiz_kaydetme_reddedilir(self):
        y = self.istemci.post("/api/ayarlar", json={"degisiklikler": {"hedef.gunluk_dk": 60}})
        self.assertEqual(y.status_code, 403)

    def test_dosya_verilmezse_kaydetme_kapali(self):
        depo = Depo(os.path.join(self.klasor, "b.db"))
        ayar = ayarlari_yukle(ORNEK_DOSYA, self.dosya)
        istemci = TestClient(uygulama_olustur(Takipci(ayar, depo, [], KararMotoru(5, 15)), depo, ayar),
                             base_url="http://127.0.0.1")
        self.assertFalse(istemci.get("/api/ayarlar").json()["kaydedilebilir"])
        y = istemci.post("/api/ayarlar", json={"degisiklikler": {"hedef.gunluk_dk": 60}}, headers=BASLIK)
        self.assertEqual(y.status_code, 503)
        istemci.close()


class CanliUygulamaTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.depo = Depo(os.path.join(gecici.name, "t.db"))
        self.ayarlar = ayarlari_yukle(ORNEK_DOSYA, Path(gecici.name) / "config.toml")

    def ayar(self, **bolumler):
        yeni = {k: (dict(v) if isinstance(v, dict) else v) for k, v in self.ayarlar.items()}
        for bolum, degerler in bolumler.items():
            yeni[bolum] = {**yeni[bolum], **degerler}
        return yeni

    def test_takipci_yeni_sureleri_alir_oturum_bolunmez(self):
        motor = KararMotoru(5, 15)
        takipci = Takipci(self.ayarlar, self.depo, [], motor)
        motor.guncelle(Durum("ders", "x"), 0)
        takipci.ayarlari_uygula(self.ayar(tolerans={"baslatma_sn": 2, "durdurma_sn": 40},
                                          genel={"tarama_araligi_sn": 3}), ["yeni"])
        self.assertEqual((motor.baslatma_sn, motor.durdurma_sn), (2, 40))
        self.assertEqual(takipci.aralik_sn, 3)
        self.assertEqual(takipci.dedektorler, ["yeni"])
        self.assertIsNotNone(motor.mevcut)  # motor sıfırlanmadı

    def test_tarayici_ve_ayni_ayarli_kamera_yeniden_kurulmaz(self):
        acik = self.ayar(kamera={"etkin": True})
        ilk = dedektorleri_kur(acik, self.depo)
        tarayici = next(d for d in ilk if isinstance(d, TarayiciDedektoru))
        kamera = next(d for d in ilk if isinstance(d, KameraDedektoru))

        ikinci = dedektorleri_kur(self.ayar(kamera={"etkin": True}, hedef={"gunluk_dk": 30}), self.depo, ilk, acik)
        self.assertIs(next(d for d in ikinci if isinstance(d, TarayiciDedektoru)), tarayici)
        self.assertIs(next(d for d in ikinci if isinstance(d, KameraDedektoru)), kamera)

        farkli = self.ayar(kamera={"etkin": True, "yuz_yok_esik_sn": 60})
        ucuncu = dedektorleri_kur(farkli, self.depo, ikinci, acik)
        self.assertIsNot(next(d for d in ucuncu if isinstance(d, KameraDedektoru)), kamera)

        kapali = dedektorleri_kur(self.ayar(kamera={"etkin": False}), self.depo, ucuncu, farkli)
        self.assertFalse(any(isinstance(d, KameraDedektoru) for d in kapali))


if __name__ == "__main__":
    unittest.main()
