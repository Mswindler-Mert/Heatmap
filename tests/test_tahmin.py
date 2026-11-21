"""Öğrenen sınıflandırıcı testleri: model, eğitim verisi, öneriler, otomatik karar ve API."""

import os
import random
import tempfile
import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from heatmap.dedektorler.baslik import BaslikDedektoru
from heatmap.depo import Depo
from heatmap.motor import Durum, KararMotoru
from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL
from heatmap.tahmin import EN_AZ_ORNEK, NaiveBayes, Tahminci, capraz_dogrulama, kelimelere_bol
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur

BASLIK = {"X-Heatmap": "1"}
# Kuralların tanımadığı ama kanal / konu kelimeleri ortak olan başlıklar
CALISMA = ["Neso Academy Pipelining Explained", "Neso Academy Cache Memory", "Neso Academy TCP Handshake",
           "Abdul Bari Dijkstra Algorithm", "Abdul Bari Dynamic Programming", "MIT OpenCourseWare Recursion",
           "MIT OpenCourseWare Graph Search", "Neso Academy Virtual Memory"]
EGLENCE = ["Elden Ring Boss Fight", "Elden Ring Funny Moments", "Minecraft Hardcore Day 100",
           "Minecraft Speedrun World Record", "Valorant Clutch Montage", "Valorant Ranked Highlights",
           "Elden Ring DLC Trailer Reaction"]
AYAR = {
    "baslik": {"ders_kelimeleri": [], "ders_degil_kelimeleri": [], "video_isaretleri": [],
               "ders_alanlari": [], "ders_degil_alanlari": [], "yok_sayilan_basliklar": []},
    "tahmin": {"etkin": True, "otomatik_karar": True, "esik_yuzde": 80},
}


def ornekler(basliklar, sinif):
    return [(kelimelere_bol(b), sinif, 1) for b in basliklar]


class ModelTesti(unittest.TestCase):
    def test_kelimelere_bolme(self):
        self.assertEqual(kelimelere_bol("(3) İşletim Sistemleri — Ders 5 | YouTube", "www.YouTube.com"),
                         ["işletim", "sistemleri", "ders", "@www.youtube.com"])  # tek harf/rakam (bildirim sayısı) atılır

    def test_benzer_basliklari_tanir(self):
        model = NaiveBayes(ornekler(CALISMA, DERS) + ornekler(EGLENCE, DERS_DEGIL))
        self.assertEqual(model.tahmin(kelimelere_bol("Neso Academy Deadlock"))[0], DERS)
        self.assertEqual(model.tahmin(kelimelere_bol("Elden Ring Lore Explained"))[0], DERS_DEGIL)
        sinif, olasilik, kelimeler = model.tahmin(kelimelere_bol("Abdul Bari Heap Sort"))
        self.assertEqual(sinif, DERS)
        self.assertGreater(olasilik, 0.8)
        self.assertIn("bari", kelimeler)

    def test_capraz_dogrulama(self):
        veri = ornekler(CALISMA, DERS) + ornekler(EGLENCE, DERS_DEGIL)
        dogruluk, kapsam = capraz_dogrulama(veri)
        self.assertEqual(dogruluk, 1.0)          # Tahmin yaptığı her başlıkta doğru
        self.assertGreaterEqual(kapsam, 0.7)     # Kanalın tek örneği teste düşerse tahmin yapılamaz
        self.assertIsNone(capraz_dogrulama(veri[:3]))  # örnek azsa ölçülmez

    def test_rastgele_etiketle_dogruluk_dusuk(self):
        """Model gerçekten öğreniyor mu? Etiketler rastgele karışınca doğruluk belirgin düşmeli."""
        basliklar = CALISMA + EGLENCE
        rastgele = random.Random(1)
        karisik = [(kelimelere_bol(b), rastgele.choice((DERS, DERS_DEGIL)), 1) for b in basliklar]
        gercek, _ = capraz_dogrulama(ornekler(CALISMA, DERS) + ornekler(EGLENCE, DERS_DEGIL))
        rastgele_dogruluk, _ = capraz_dogrulama(karisik)
        self.assertLess(rastgele_dogruluk, gercek)


class TahminciTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.depo = Depo(os.path.join(gecici.name, "t.db"))
        self.t = datetime(2026, 11, 20, 9).timestamp()

    def oturum(self, baslik, hukum, duzeltme=None, alan=""):
        oid = self.depo.oturum_baslat(Durum(hukum, "brave.exe", "baslik", "", "brave.exe", baslik, alan), self.t)
        self.depo.oturum_bitisini_guncelle(oid, self.t + 600)
        self.t += 700
        if duzeltme:
            self.depo.oturum_duzelt(oid, duzeltme)
        return oid

    def doldur(self):
        for b in CALISMA:
            self.oturum(b, BELIRSIZ, duzeltme=DERS)
        for b in EGLENCE:
            self.oturum(b, DERS_DEGIL)

    def test_az_ornekle_hazir_degil(self):
        for b in CALISMA[:3]:
            self.oturum(b, DERS)
        t = Tahminci(self.depo)
        bilgi = t.yeniden_egit()
        self.assertFalse(bilgi["hazir"])
        self.assertLess(bilgi["ornek_sayisi"], EN_AZ_ORNEK)
        self.assertIsNone(t.tahmin_et("Neso Academy Deadlock"))

    def test_egitim_ve_tahmin(self):
        self.doldur()
        self.oturum("Neso Academy Pipelining Explained", DERS)   # aynı başlık tekrar: tek örnek sayılır
        t = Tahminci(self.depo)
        bilgi = t.yeniden_egit()
        self.assertTrue(bilgi["hazir"])
        self.assertEqual(bilgi["ornek_sayisi"], len(CALISMA) + len(EGLENCE))
        self.assertEqual(t.tahmin_et("Neso Academy Deadlock")["hukum"], DERS)
        self.assertIsNone(t.tahmin_et("Tamamen yabancı kelimeler"))  # hiç tanıdık kelime yok

    def test_otomatik_karar_yalnizca_izinle(self):
        self.doldur()
        t = Tahminci(self.depo)
        t.yeniden_egit()
        acik = BaslikDedektoru(AYAR, tahminci=t)
        hukum, aciklama = acik.siniflandir("Neso Academy Deadlock")
        self.assertEqual(hukum, DERS)
        self.assertIn("Tahmin", aciklama)
        kapali = BaslikDedektoru({**AYAR, "tahmin": {"otomatik_karar": False}}, tahminci=t)
        self.assertEqual(kapali.siniflandir("Neso Academy Deadlock")[0], BELIRSIZ)  # varsayılan davranış
        cok_yuksek_esik = BaslikDedektoru({**AYAR, "tahmin": {"otomatik_karar": True, "esik_yuzde": 99.99}},
                                          tahminci=t)
        self.assertEqual(cok_yuksek_esik.siniflandir("Neso Elden")[0], BELIRSIZ)  # emin değil

    def test_kural_her_zaman_tahminden_once(self):
        self.doldur()
        t = Tahminci(self.depo)
        t.yeniden_egit()
        ayar = {**AYAR, "baslik": {**AYAR["baslik"], "ders_degil_kelimeleri": ["Academy"]}}
        self.assertEqual(BaslikDedektoru(ayar, tahminci=t).siniflandir("Neso Academy Deadlock")[0], DERS_DEGIL)

    def test_api_oneri_toplu_karar_ve_yeniden_egitim(self):
        self.doldur()
        bekleyen = [self.oturum("Neso Academy Deadlock", BELIRSIZ), self.oturum("Neso Academy Deadlock", BELIRSIZ)]
        t = Tahminci(self.depo)
        t.yeniden_egit()
        ayar = {"genel": {"tarama_araligi_sn": 1}, "tahmin": {"etkin": True}}
        app = uygulama_olustur(Takipci(ayar, self.depo, [], KararMotoru(5, 15)), self.depo, ayar, tahminci=t)
        with TestClient(app, base_url="http://127.0.0.1") as istemci:
            oturumlar = istemci.get("/api/oturumlar?tarih=2026-11-20").json()
            oneri = next(o for o in oturumlar if o["id"] == bekleyen[0])["oneri"]
            self.assertEqual(oneri["hukum"], DERS)

            liste = istemci.get("/api/karar-bekleyenler").json()
            self.assertEqual([(k["deger"], k["oturum_sayisi"]) for k in liste], [("Neso Academy Deadlock", 2)])
            self.assertEqual(liste[0]["oneri"]["hukum"], DERS)

            once = istemci.get("/api/tahmin").json()["ornek_sayisi"]
            y = istemci.post("/api/karar-bekleyenler", headers=BASLIK, json={
                "tur": "baslik", "deger": "Neso Academy Deadlock", "hukum": "ders", "ogren": True})
            self.assertEqual(y.json()["duzeltilen"], 2)
            self.assertEqual(istemci.get("/api/karar-bekleyenler").json(), [])
            self.assertEqual(istemci.get("/api/tahmin").json()["ornek_sayisi"], once + 1)  # yeniden eğitildi
            kurallar = istemci.get("/api/kurallar").json()
            self.assertIn(("baslik", "Neso Academy Deadlock"), [(k["tur"], k["desen"]) for k in kurallar])

    def test_oneriler_kapatilabilir(self):
        self.doldur()
        self.oturum("Neso Academy Deadlock", BELIRSIZ)
        t = Tahminci(self.depo)
        t.yeniden_egit()
        ayar = {"genel": {"tarama_araligi_sn": 1}, "tahmin": {"etkin": False}}
        app = uygulama_olustur(Takipci(ayar, self.depo, [], KararMotoru(5, 15)), self.depo, ayar, tahminci=t)
        with TestClient(app, base_url="http://127.0.0.1") as istemci:
            self.assertIsNone(istemci.get("/api/karar-bekleyenler").json()[0]["oneri"])


if __name__ == "__main__":
    unittest.main()
