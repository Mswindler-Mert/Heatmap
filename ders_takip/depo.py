"""Veritabanı katmanı (SQLite). SQL cümlelerinin tamamı bu dosyadadır.

İki tablo var:
  oturumlar          : Aynı durumun kesintisiz sürdüğü zaman dilimleri.
  ogrenilen_kurallar : Senin düzeltmelerinden öğrenilen kurallar.

Zamanlar "epoch saniyesi" (1970'ten beri geçen saniye, time.time() çıktısı)
olarak saklanır; iki zamanı çıkarmak süreyi verdiği için hesap kolaydır.

Her işlemde bağlantı açılıp kapatılır. Bu en hızlı yöntem değil ama en
basit ve güvenli olanı: takip döngüsü ile web sunucusu ayrı thread'lerde
çalıştığı için ortak bir bağlantıyı paylaşmak sorun çıkarabilirdi.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from ders_takip.motor import Durum
from ders_takip.sinyal import BELIRSIZ, DERS

_SEMA = """
CREATE TABLE IF NOT EXISTS oturumlar (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    baslangic REAL NOT NULL,      -- epoch saniyesi
    bitis     REAL NOT NULL,
    hukum     TEXT NOT NULL,      -- programın kararı: ders / ders_degil / belirsiz
    duzeltme  TEXT,               -- senin düzeltmen (yoksa NULL)
    kaynak    TEXT,               -- kararı veren modül: pencere / baslik / bosta / kamera
    aciklama  TEXT,
    uygulama  TEXT,               -- süreç adı
    baslik    TEXT                -- pencere / sekme başlığı
);
CREATE INDEX IF NOT EXISTS oturumlar_baslangic ON oturumlar (baslangic);

CREATE TABLE IF NOT EXISTS ogrenilen_kurallar (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tur       TEXT NOT NULL,      -- 'surec' | 'baslik' | 'kelime'
    desen     TEXT NOT NULL,      -- süreç adı, tam başlık ya da anahtar kelime
    hukum     TEXT NOT NULL,      -- 'ders' | 'ders_degil'
    olusturma REAL NOT NULL,
    UNIQUE (tur, desen)
);
"""

# Geçerli hüküm: düzeltme varsa o, yoksa programın kararı.
_ETKIN_HUKUM = "COALESCE(duzeltme, hukum)"


def gun_araligi(gun: date) -> tuple[float, float]:
    """Bir günün başlangıç ve bitiş anını (yerel saatle) epoch saniyesi olarak verir."""
    baslangic = datetime.combine(gun, datetime.min.time())
    bitis = baslangic + timedelta(days=1)
    return baslangic.timestamp(), bitis.timestamp()


class Depo:
    def __init__(self, yol: Path | str):
        self.yol = str(yol)
        self._kural_kilidi = threading.Lock()
        self._kural_onbellegi: list[dict] | None = None
        with self._baglan() as vt:
            vt.executescript(_SEMA)

    @contextmanager
    def _baglan(self):
        """Bağlantı aç, işi bitince kaydet (commit) ve kapat."""
        vt = sqlite3.connect(self.yol, timeout=5)
        vt.row_factory = sqlite3.Row  # Satırlara sütun adıyla erişebilmek için
        try:
            yield vt
            vt.commit()
        finally:
            vt.close()

    # ------------------------------------------------------------------
    #  Oturumlar
    # ------------------------------------------------------------------
    def oturum_baslat(self, durum: Durum, zaman: float) -> int:
        """Yeni oturum satırı ekler ve numarasını (id) döndürür."""
        with self._baglan() as vt:
            imlec = vt.execute(
                "INSERT INTO oturumlar (baslangic, bitis, hukum, kaynak, aciklama, uygulama, baslik)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (zaman, zaman, durum.hukum, durum.kaynak, durum.aciklama, durum.uygulama, durum.baslik),
            )
            return imlec.lastrowid

    def oturum_bitisini_guncelle(self, oturum_id: int, bitis: float) -> None:
        """Süren oturumun bitiş anını ileri taşır (ya da geçişte kesin bitişi yazar)."""
        with self._baglan() as vt:
            # MAX: bitiş hiçbir zaman başlangıçtan önce olmasın.
            vt.execute("UPDATE oturumlar SET bitis = MAX(baslangic, ?) WHERE id = ?", (bitis, oturum_id))

    def oturum_getir(self, oturum_id: int) -> dict | None:
        with self._baglan() as vt:
            satir = vt.execute("SELECT * FROM oturumlar WHERE id = ?", (oturum_id,)).fetchone()
            return dict(satir) if satir else None

    def oturumlari_getir(self, baslangic: float, bitis: float) -> list[dict]:
        """Verilen zaman aralığına değen oturumlar, yeniden eskiye."""
        with self._baglan() as vt:
            satirlar = vt.execute(
                "SELECT * FROM oturumlar WHERE bitis > ? AND baslangic < ? ORDER BY baslangic DESC",
                (baslangic, bitis),
            ).fetchall()
            return [dict(s) for s in satirlar]

    def oturum_duzelt(self, oturum_id: int, hukum: str) -> None:
        with self._baglan() as vt:
            vt.execute("UPDATE oturumlar SET duzeltme = ? WHERE id = ?", (hukum, oturum_id))

    def benzerleri_duzelt(self, oturum: dict, hukum: str) -> int:
        """Aynı uygulama/başlığa sahip, henüz düzeltilmemiş BELİRSİZ oturumları da düzeltir.

        Kaç oturumun değiştiğini döndürür.
        """
        if oturum["kaynak"] == "baslik":
            sutun, deger = "baslik", oturum["baslik"]
        elif oturum["kaynak"] == "pencere":
            sutun, deger = "uygulama", oturum["uygulama"]
        else:
            return 0
        with self._baglan() as vt:
            # `sutun` kullanıcıdan gelmiyor (yukarıda iki sabitten biri), o yüzden
            # sorguya doğrudan yazmak güvenli. Değerler ise her zaman "?" ile verilir.
            imlec = vt.execute(
                f"UPDATE oturumlar SET duzeltme = ?"
                f" WHERE duzeltme IS NULL AND hukum = ? AND kaynak = ? AND LOWER({sutun}) = LOWER(?)",
                (hukum, BELIRSIZ, oturum["kaynak"], deger),
            )
            return imlec.rowcount

    def ders_suresi(self, baslangic: float, bitis: float) -> float:
        """Verilen aralıktaki toplam ders süresi (saniye).

        Aralığın dışına taşan oturumlar (örn. gece yarısını geçen) kırpılır.
        """
        with self._baglan() as vt:
            satirlar = vt.execute(
                f"SELECT baslangic, bitis FROM oturumlar"
                f" WHERE {_ETKIN_HUKUM} = ? AND bitis > ? AND baslangic < ?",
                (DERS, baslangic, bitis),
            ).fetchall()
        toplam = 0.0
        for satir in satirlar:
            toplam += min(satir["bitis"], bitis) - max(satir["baslangic"], baslangic)
        return toplam

    def gunluk_sureler(self, ilk_gun: date, son_gun: date) -> list[dict]:
        """İki tarih arasındaki (ikisi de dahil) her gün için ders süresi."""
        sonuc = []
        gun = ilk_gun
        while gun <= son_gun:
            bas, bit = gun_araligi(gun)
            sonuc.append({"tarih": gun.isoformat(), "ders_sn": round(self.ders_suresi(bas, bit))})
            gun += timedelta(days=1)
        return sonuc

    # ------------------------------------------------------------------
    #  Öğrenilen kurallar
    # ------------------------------------------------------------------
    def ogrenilen_kurallar(self) -> list[dict]:
        """Bütün öğrenilen kurallar.

        Dedektörler bunu her saniye çağırdığı için sonuç bellekte tutulur;
        kural eklenince/silinince önbellek boşaltılır.
        """
        with self._kural_kilidi:
            if self._kural_onbellegi is None:
                with self._baglan() as vt:
                    satirlar = vt.execute("SELECT * FROM ogrenilen_kurallar ORDER BY olusturma DESC").fetchall()
                self._kural_onbellegi = [dict(s) for s in satirlar]
            return self._kural_onbellegi

    def kural_ekle(self, tur: str, desen: str, hukum: str) -> None:
        """Kural ekler; aynı (tür, desen) zaten varsa hükmünü günceller."""
        with self._baglan() as vt:
            vt.execute(
                "INSERT INTO ogrenilen_kurallar (tur, desen, hukum, olusturma) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (tur, desen) DO UPDATE SET hukum = excluded.hukum, olusturma = excluded.olusturma",
                (tur, desen, hukum, time.time()),
            )
        with self._kural_kilidi:
            self._kural_onbellegi = None

    def kural_sil(self, kural_id: int) -> bool:
        with self._baglan() as vt:
            imlec = vt.execute("DELETE FROM ogrenilen_kurallar WHERE id = ?", (kural_id,))
        with self._kural_kilidi:
            self._kural_onbellegi = None
        return imlec.rowcount > 0
