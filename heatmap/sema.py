"""Veritabanı şeması ve sürümlü taşımalar (migration).

Veritabanı dosyası kendi sürüm numarasını taşır (SQLite'ın `PRAGMA user_version` alanı).
Program açılınca bu numaraya bakılır ve eksik taşımalar SIRAYLA uygulanır:

    sürüm 0  ->  1 : ilk tablolar (oturumlar, öğrenilen kurallar)
    sürüm 1  ->  2 : oturumlar.alan_adi sütunu (tarayıcı eklentisi)
    sürüm 2  ->  3 : saglik_gunluk tablosu
    sürüm 3  ->  4 : oturumlar(bitis) dizini (tarih aralığı sorguları hızlansın)

Kurallar:
  * Var olan bir taşıma ASLA değiştirilmez; şema değişecekse listenin sonuna YENİ bir
    taşıma eklenir. (Kullanıcıların veritabanları farklı sürümlerde olabilir.)
  * Her taşıma tek bir işlem (transaction) içinde çalışır: yarıda hata olursa o taşıma
    hiç uygulanmamış sayılır ve sürüm numarası yükselmez.
  * İçinde veri olan bir veritabanında taşımadan ÖNCE yedek alınır.

Sürüm numarası tutulmaya başlamadan önceki veritabanlarında numara 0'dır; böyle bir
dosyanın gerçekte hangi aşamada olduğu tablolara ve sütunlara bakılarak anlaşılır.
"""

import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path


# ======================================================================
#  Taşımalar (sıra önemli; sadece SONUNA ekle)
# ======================================================================
def _g1_ilk_tablolar(vt) -> None:
    vt.execute("""
        CREATE TABLE IF NOT EXISTS oturumlar (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            baslangic REAL NOT NULL,      -- epoch saniyesi
            bitis     REAL NOT NULL,
            hukum     TEXT NOT NULL,      -- programın kararı: ders / ders_degil / belirsiz
            duzeltme  TEXT,               -- kullanıcının düzeltmesi (yoksa NULL)
            kaynak    TEXT,               -- kararı veren modül: pencere / baslik / bosta / kamera
            aciklama  TEXT,
            uygulama  TEXT,               -- süreç adı
            baslik    TEXT                -- pencere / sekme başlığı
        )""")
    vt.execute("CREATE INDEX IF NOT EXISTS oturumlar_baslangic ON oturumlar (baslangic)")
    vt.execute("""
        CREATE TABLE IF NOT EXISTS ogrenilen_kurallar (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tur       TEXT NOT NULL,      -- 'surec' | 'baslik' | 'kelime' | 'alan'
            desen     TEXT NOT NULL,      -- süreç adı, tam başlık, anahtar kelime ya da site
            hukum     TEXT NOT NULL,      -- 'ders' | 'ders_degil'
            olusturma REAL NOT NULL,
            UNIQUE (tur, desen)
        )""")


def _g2_alan_adi(vt) -> None:
    # Eski bir sürüm bu sütunu kendi eklemiş olabilir; varsa tekrar ekleme.
    if "alan_adi" not in _sutunlar(vt, "oturumlar"):
        vt.execute("ALTER TABLE oturumlar ADD COLUMN alan_adi TEXT")  # eklentiden gelen site adı


def _g3_saglik(vt) -> None:
    vt.execute("""
        CREATE TABLE IF NOT EXISTS saglik_gunluk (
            tarih       TEXT PRIMARY KEY,   -- 'YYYY-AA-GG' (yerel gün)
            adim        INTEGER,
            egzersiz_dk INTEGER,
            uyku_dk     INTEGER,
            kaynak      TEXT NOT NULL,      -- 'elle' | 'health_connect'
            guncelleme  REAL NOT NULL
        )""")


def _g4_bitis_dizini(vt) -> None:
    # Neredeyse her sorgu "bitis > ? AND baslangic < ?" biçiminde; bitiş için de dizin.
    vt.execute("CREATE INDEX IF NOT EXISTS oturumlar_bitis ON oturumlar (bitis)")


GOCLER: list[tuple[int, str, Callable]] = [
    (1, "İlk tablolar: oturumlar, öğrenilen kurallar", _g1_ilk_tablolar),
    (2, "oturumlar.alan_adi sütunu (tarayıcı eklentisi)", _g2_alan_adi),
    (3, "saglik_gunluk tablosu (adım, egzersiz, uyku)", _g3_saglik),
    (4, "oturumlar(bitis) dizini", _g4_bitis_dizini),
]
GUNCEL_SURUM = GOCLER[-1][0]


# ======================================================================
#  Yardımcılar
# ======================================================================
def _tablolar(vt) -> set[str]:
    return {s[0] for s in vt.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _sutunlar(vt, tablo: str) -> set[str]:
    return {s[1] for s in vt.execute(f"PRAGMA table_info({tablo})")}


def surumu_oku(vt) -> int:
    return vt.execute("PRAGMA user_version").fetchone()[0]


def eski_surumu_tani(vt) -> int:
    """Sürüm numarası 0 olan bir veritabanının gerçekte hangi aşamada olduğunu bulur.

    Sürüm tutulmaya başlamadan önceki programlar tabloları/sütunları kendileri ekliyordu.
    """
    tablolar = _tablolar(vt)
    if "oturumlar" not in tablolar:
        return 0                                   # Boş (yeni) dosya
    if "alan_adi" not in _sutunlar(vt, "oturumlar"):
        return 1                                   # İlk "Ders Takip" sürümü
    if "saglik_gunluk" not in tablolar:
        return 2
    return 3                                       # Sürüm numarasından hemen önceki hâl


def _veri_var_mi(vt) -> bool:
    if "oturumlar" not in _tablolar(vt):
        return False
    return vt.execute("SELECT EXISTS (SELECT 1 FROM oturumlar)").fetchone()[0] == 1


def _yedek_al(db_yolu: Path, yedek_klasoru: Path, surum: int) -> Path:
    yedek_klasoru.mkdir(parents=True, exist_ok=True)
    hedef = yedek_klasoru / f"heatmap-gocmeden-once-v{surum}-{date.today().isoformat()}.db"
    kaynak = sqlite3.connect(db_yolu)
    try:
        hedef_vt = sqlite3.connect(hedef)
        try:
            kaynak.backup(hedef_vt)
        finally:
            hedef_vt.close()
    finally:
        kaynak.close()
    return hedef


# ======================================================================
#  Ana iş
# ======================================================================
class SemaHatasi(Exception):
    """Veritabanı, bu programın bildiğinden daha yeni bir sürümde (eski programla açılmış)."""


def semayi_guncelle(db_yolu: Path | str, yedek_klasoru: Path | None = None,
                    gocler: list | None = None) -> list[int]:
    """Veritabanını güncel şemaya getirir; uygulanan taşıma numaralarını döndürür.

    yedek_klasoru verilirse ve veritabanında veri varsa, taşımadan önce yedek alınır.
    gocler: testler için başka bir taşıma listesi verilebilir.
    """
    gocler = gocler if gocler is not None else GOCLER
    guncel = gocler[-1][0]
    db_yolu = Path(db_yolu)
    # isolation_level=None: işlemleri (BEGIN/COMMIT) kendimiz yönetiyoruz.
    vt = sqlite3.connect(db_yolu, timeout=5, isolation_level=None)
    try:
        surum = surumu_oku(vt)
        if surum == 0:
            surum = eski_surumu_tani(vt)
        if surum > guncel:
            raise SemaHatasi(f"Veritabanı sürümü ({surum}) bu programın bildiğinden ({guncel}) yeni. "
                             "Heatmap'in daha yeni bir sürümüyle oluşturulmuş olabilir.")

        bekleyen = [g for g in gocler if g[0] > surum]
        if not bekleyen:
            if surumu_oku(vt) != surum:  # Eski dosya, taşıma gerekmedi: yalnızca numarayı yaz
                vt.execute(f"PRAGMA user_version = {int(surum)}")
            return []

        if yedek_klasoru is not None and _veri_var_mi(vt):
            _yedek_al(db_yolu, Path(yedek_klasoru), surum)

        uygulanan = []
        for numara, _aciklama, fonksiyon in bekleyen:
            vt.execute("BEGIN")
            try:
                fonksiyon(vt)
                vt.execute(f"PRAGMA user_version = {int(numara)}")
                vt.execute("COMMIT")
            except Exception:
                vt.execute("ROLLBACK")  # Bu taşıma hiç olmamış gibi; önceki taşımalar kalır
                raise
            uygulanan.append(numara)
        return uygulanan
    finally:
        vt.close()
