"""Şema sürümleme testleri: her eski hâlden güncel şemaya veri kaybetmeden geçiş."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from heatmap.depo import Depo
from heatmap.sema import GOCLER, GUNCEL_SURUM, SemaHatasi, eski_surumu_tani, semayi_guncelle, surumu_oku

# İlk "Ders Takip" sürümünün (v1) oluşturduğu şema: alan_adi yok, sağlık tablosu yok, user_version 0
ESKI_V1 = """
CREATE TABLE oturumlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT, baslangic REAL NOT NULL, bitis REAL NOT NULL,
    hukum TEXT NOT NULL, duzeltme TEXT, kaynak TEXT, aciklama TEXT, uygulama TEXT, baslik TEXT);
CREATE INDEX oturumlar_baslangic ON oturumlar (baslangic);
CREATE TABLE ogrenilen_kurallar (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tur TEXT NOT NULL, desen TEXT NOT NULL,
    hukum TEXT NOT NULL, olusturma REAL NOT NULL, UNIQUE (tur, desen));
INSERT INTO oturumlar (baslangic, bitis, hukum, duzeltme, kaynak, uygulama, baslik)
    VALUES (100, 700, 'belirsiz', 'ders', 'pencere', 'Code.exe', 'main.py');
INSERT INTO ogrenilen_kurallar (tur, desen, hukum, olusturma) VALUES ('surec', 'Code.exe', 'ders', 1);
"""
# v2: alan_adi sütunu sonradan ALTER ile eklenmiş hâl
ESKI_V2 = ESKI_V1 + "ALTER TABLE oturumlar ADD COLUMN alan_adi TEXT;"
# v3: sağlık tablosu da var, ama sürüm numarası hâlâ 0 (sürümleme öncesi son hâl)
ESKI_V3 = ESKI_V2 + """
CREATE TABLE saglik_gunluk (tarih TEXT PRIMARY KEY, adim INTEGER, egzersiz_dk INTEGER,
    uyku_dk INTEGER, kaynak TEXT NOT NULL, guncelleme REAL NOT NULL);
INSERT INTO saglik_gunluk VALUES ('2026-11-20', 8000, NULL, NULL, 'elle', 1);
"""


class SemaTesti(unittest.TestCase):
    def setUp(self):
        gecici = tempfile.TemporaryDirectory()
        self.addCleanup(gecici.cleanup)
        self.klasor = Path(gecici.name)
        self.db = self.klasor / "heatmap.db"
        self.yedekler = self.klasor / "yedek"

    def eski_olustur(self, betik: str) -> None:
        vt = sqlite3.connect(self.db)
        vt.executescript(betik)
        vt.close()

    def vt(self):
        """Kullanım: with self.vt() as vt: ...  (blok bitince bağlantı kapanır; Windows açık
        dosyayı silmeye izin vermediği için bu önemli)"""
        return closing(sqlite3.connect(self.db))

    def guncel_mi(self) -> None:
        with self.vt() as vt:
            self.assertEqual(surumu_oku(vt), GUNCEL_SURUM)
            self.assertIn("alan_adi", {s[1] for s in vt.execute("PRAGMA table_info(oturumlar)")})
            tablolar = {s[0] for s in vt.execute("SELECT name FROM sqlite_master")}
        self.assertTrue({"oturumlar", "ogrenilen_kurallar", "saglik_gunluk",
                         "zincir_halkalari", "oturumlar_bitis"} <= tablolar)

    def test_yeni_dosya(self):
        self.assertEqual(semayi_guncelle(self.db, self.yedekler), [n for n, _, _ in GOCLER])
        self.guncel_mi()
        self.assertFalse(self.yedekler.exists())  # Boş dosya için yedek gereksiz

    def test_ikinci_acilista_tasima_yok(self):
        semayi_guncelle(self.db)
        self.assertEqual(semayi_guncelle(self.db, self.yedekler), [])
        self.assertFalse(self.yedekler.exists())

    def test_her_eski_halden_gecis_veri_kaybetmeden(self):
        for betik, beklenen_ilk in ((ESKI_V1, 2), (ESKI_V2, 3), (ESKI_V3, 4)):
            with self.subTest(baslangic=beklenen_ilk - 1):
                self.db.unlink(missing_ok=True)
                self.eski_olustur(betik)
                with self.vt() as vt:
                    self.assertEqual(eski_surumu_tani(vt), beklenen_ilk - 1)
                uygulanan = semayi_guncelle(self.db, self.yedekler)
                self.assertEqual(uygulanan, list(range(beklenen_ilk, GUNCEL_SURUM + 1)))
                self.guncel_mi()
                depo = Depo(self.db)
                oturum = depo.oturum_getir(1)
                self.assertEqual((oturum["uygulama"], oturum["duzeltme"], oturum["alan_adi"]),
                                 ("Code.exe", "ders", None))
                self.assertEqual(depo.ogrenilen_kurallar()[0]["desen"], "Code.exe")

    def test_veri_varsa_tasimadan_once_yedek_alinir(self):
        self.eski_olustur(ESKI_V1)
        semayi_guncelle(self.db, self.yedekler)
        yedekler = list(self.yedekler.glob("heatmap-gocmeden-once-v1-*.db"))
        self.assertEqual(len(yedekler), 1)
        vt = sqlite3.connect(yedekler[0])
        try:  # Yedek, taşıma ÖNCESİ hâli içerir
            self.assertNotIn("alan_adi", {s[1] for s in vt.execute("PRAGMA table_info(oturumlar)")})
            self.assertEqual(vt.execute("SELECT COUNT(*) FROM oturumlar").fetchone()[0], 1)
        finally:
            vt.close()

    def test_hatali_tasima_geri_alinir(self):
        semayi_guncelle(self.db)

        def bozuk(vt):
            vt.execute("CREATE TABLE yari_kalan (x)")
            raise RuntimeError("taşıma yarıda kaldı")

        with self.assertRaises(RuntimeError):
            semayi_guncelle(self.db, gocler=GOCLER + [(GUNCEL_SURUM + 1, "bozuk", bozuk)])
        with self.vt() as vt:
            self.assertEqual(surumu_oku(vt), GUNCEL_SURUM)  # Sürüm yükselmedi
            tablolar = {s[0] for s in vt.execute("SELECT name FROM sqlite_master")}
        self.assertNotIn("yari_kalan", tablolar)

    def test_daha_yeni_surumlu_dosya_bozulmaz(self):
        semayi_guncelle(self.db)
        vt = sqlite3.connect(self.db)
        vt.execute(f"PRAGMA user_version = {GUNCEL_SURUM + 5}")
        vt.close()
        with self.assertRaises(SemaHatasi):
            semayi_guncelle(self.db)

    def test_numaralar_sirali_ve_benzersiz(self):
        numaralar = [n for n, _, _ in GOCLER]
        self.assertEqual(numaralar, list(range(1, len(GOCLER) + 1)))


if __name__ == "__main__":
    unittest.main()
