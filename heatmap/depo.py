"""Veritabanı katmanı (SQLite). SQL cümlelerinin tamamı bu dosyadadır.

Tablolar (tanımları ve sürümleri: heatmap/sema.py):
  oturumlar          : Aynı durumun kesintisiz sürdüğü zaman dilimleri.
  ogrenilen_kurallar : Senin düzeltmelerinden öğrenilen kurallar.
  saglik_gunluk      : Günlük adım / egzersiz / uyku.
  zincir_halkalari   : Zinciri Kırma halkaları (tam / kurtarma / kalkan).

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

from heatmap.motor import Durum
from heatmap.sema import semayi_guncelle
from heatmap.sinyal import BELIRSIZ, DERS

# Tablo tanımları ve sürümlü taşımalar: heatmap/sema.py


# Geçerli hüküm: düzeltme varsa o, yoksa programın kararı.
_ETKIN_HUKUM = "COALESCE(duzeltme, hukum)"


def gun_araligi(gun: date) -> tuple[float, float]:
    """Bir günün başlangıç ve bitiş anını (yerel saatle) epoch saniyesi olarak verir."""
    baslangic = datetime.combine(gun, datetime.min.time())
    bitis = baslangic + timedelta(days=1)
    return baslangic.timestamp(), bitis.timestamp()


class Depo:
    def __init__(self, yol: Path | str, yedek_klasoru: Path | None = None):
        """yol: veritabanı dosyası. yedek_klasoru: şema taşıması gerekirse önce yedeğin
        alınacağı klasör (program data/yedek verir; testler genelde vermez)."""
        self.yol = str(yol)
        self._kural_kilidi = threading.Lock()
        self._kural_onbellegi: list[dict] | None = None
        # Dosya yoksa oluşturur, eskiyse sürüm sürüm günceller (bkz. heatmap/sema.py).
        self.uygulanan_gocler = semayi_guncelle(self.yol, yedek_klasoru)

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
                "INSERT INTO oturumlar (baslangic, bitis, hukum, kaynak, aciklama, uygulama, baslik, alan_adi)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (zaman, zaman, durum.hukum, durum.kaynak, durum.aciklama, durum.uygulama, durum.baslik,
                 durum.alan_adi or None),
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

    def oturum_duzelt(self, oturum_id: int, hukum: str | None) -> None:
        """Oturumun hükmünü düzeltir. hukum=None düzeltmeyi geri alır (programın kararına döner)."""
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

    def etiketli_tarayici_oturumlari(self) -> list[dict]:
        """Tahmin modelinin eğitim verisi: geçerli hükmü çalışma / çalışma değil olan tarayıcı oturumları.

        Dönen her satırda "hukum" GEÇERLİ hükümdür (düzeltme varsa o).
        """
        with self._baglan() as vt:
            satirlar = vt.execute(
                f"SELECT baslik, alan_adi, duzeltme, {_ETKIN_HUKUM} AS hukum FROM oturumlar"
                f" WHERE kaynak = 'baslik' AND baslik IS NOT NULL AND {_ETKIN_HUKUM} IN (?, ?)",
                (DERS, "ders_degil"),
            ).fetchall()
        return [dict(s) for s in satirlar]

    def karar_bekleyenler(self, en_fazla: int = 300) -> list[dict]:
        """Bütün günlerde hâlâ BELİRSİZ olan başlıklar ve uygulamalar, toplam süreye göre çoktan aza.

        tur "baslik": aynı sekme başlığı (+ site) bir satır; tur "uygulama": aynı süreç bir satır.
        """
        with self._baglan() as vt:
            basliklar = vt.execute(
                f"SELECT 'baslik' AS tur, MIN(baslik) AS deger, alan_adi, MIN(uygulama) AS uygulama,"
                f" COUNT(*) AS oturum_sayisi, SUM(bitis - baslangic) AS sure_sn, MAX(bitis) AS son"
                f" FROM oturumlar WHERE kaynak = 'baslik' AND {_ETKIN_HUKUM} = ? AND baslik IS NOT NULL"
                f" GROUP BY LOWER(baslik), COALESCE(alan_adi, '')", (BELIRSIZ,)).fetchall()
            uygulamalar = vt.execute(
                f"SELECT 'uygulama' AS tur, MIN(uygulama) AS deger, NULL AS alan_adi, MIN(uygulama) AS uygulama,"
                f" COUNT(*) AS oturum_sayisi, SUM(bitis - baslangic) AS sure_sn, MAX(bitis) AS son"
                f" FROM oturumlar WHERE kaynak = 'pencere' AND {_ETKIN_HUKUM} = ? AND uygulama IS NOT NULL"
                f" GROUP BY LOWER(uygulama)", (BELIRSIZ,)).fetchall()
        hepsi = sorted((dict(s) for s in basliklar + uygulamalar), key=lambda s: s["sure_sn"], reverse=True)
        return hepsi[:en_fazla]

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

    def uygulama_dokumu(self, baslangic: float, bitis: float, etiketle=None) -> list[dict]:
        """Verilen aralıktaki ders süresinin uygulamalara/sitelere dağılımı, çoktan aza.

        `etiketle`: bir oturum satırını (görünen ad, tür) ikilisine çeviren fonksiyon
        (bkz. ozet.Adlandirici.etiket). Verilmezse süreç adı olduğu gibi kullanılır.

        Örn: [{"ad": "VS Code", "tur": "uygulama", "sure_sn": 5400},
              {"ad": "YouTube", "tur": "site", "sure_sn": 1800}]
        """
        if etiketle is None:
            etiketle = lambda oturum: (oturum["uygulama"] or "", "uygulama")  # noqa: E731

        with self._baglan() as vt:
            satirlar = vt.execute(
                f"SELECT uygulama, baslik, kaynak, alan_adi, baslangic, bitis FROM oturumlar"
                f" WHERE {_ETKIN_HUKUM} = ? AND bitis > ? AND baslangic < ?",
                (DERS, baslangic, bitis),
            ).fetchall()

        toplamlar: dict[tuple[str, str], float] = {}
        for satir in satirlar:
            anahtar = etiketle(dict(satir))    # (ad, tür): aynı ada sahip oturumlar toplanır
            sure = min(satir["bitis"], bitis) - max(satir["baslangic"], baslangic)
            toplamlar[anahtar] = toplamlar.get(anahtar, 0.0) + sure

        dokum = [{"ad": ad, "tur": tur, "sure_sn": round(sure)} for (ad, tur), sure in toplamlar.items()]
        dokum.sort(key=lambda kayit: kayit["sure_sn"], reverse=True)
        return dokum

    def gunluk_sureler(self, ilk_gun: date, son_gun: date) -> list[dict]:
        """İki tarih arasındaki (ikisi de dahil) her gün için ders süresi.

        Tek bir sorguyla aralıktaki bütün oturumları çeker ve her oturumu
        değdiği günlere böler (gece yarısını geçen bir oturum iki güne paylaşılır).
        Isı haritası bir yılı (365 gün) tek seferde istediği için gün başına
        ayrı sorgu atmak yerine böyle yapıyoruz.
        """
        aralik_bas, _ = gun_araligi(ilk_gun)
        _, aralik_bit = gun_araligi(son_gun)
        with self._baglan() as vt:
            satirlar = vt.execute(
                f"SELECT baslangic, bitis FROM oturumlar"
                f" WHERE {_ETKIN_HUKUM} = ? AND bitis > ? AND baslangic < ?",
                (DERS, aralik_bas, aralik_bit),
            ).fetchall()

        gunluk: dict[date, float] = {}
        for satir in satirlar:
            bas = max(satir["baslangic"], aralik_bas)
            bit = min(satir["bitis"], aralik_bit)
            gun = datetime.fromtimestamp(bas).date()
            while bas < bit:
                _, gun_sonu = gun_araligi(gun)
                parca_sonu = min(bit, gun_sonu)
                gunluk[gun] = gunluk.get(gun, 0.0) + (parca_sonu - bas)
                bas = parca_sonu
                gun += timedelta(days=1)

        sonuc = []
        gun = ilk_gun
        while gun <= son_gun:
            sonuc.append({"tarih": gun.isoformat(), "ders_sn": round(gunluk.get(gun, 0.0))})
            gun += timedelta(days=1)
        return sonuc

    def saatlik_dagilim(self, ilk_gun: date, son_gun: date) -> list[dict]:
        """İki tarih arasındaki ders süresinin günün 24 saatine (0..23) dağılımı.

        Her oturum yerel saate göre geçtiği saat dilimlerine bölünür; örneğin
        14:40–15:20 oturumu 14. saate 20 dk, 15. saate 20 dk ekler.
        """
        aralik_bas, _ = gun_araligi(ilk_gun)
        _, aralik_bit = gun_araligi(son_gun)
        with self._baglan() as vt:
            satirlar = vt.execute(
                f"SELECT baslangic, bitis FROM oturumlar"
                f" WHERE {_ETKIN_HUKUM} = ? AND bitis > ? AND baslangic < ?",
                (DERS, aralik_bas, aralik_bit),
            ).fetchall()

        saatler = [0.0] * 24
        for satir in satirlar:
            bas = max(satir["baslangic"], aralik_bas)
            bit = min(satir["bitis"], aralik_bit)
            while bas < bit:
                dt = datetime.fromtimestamp(bas)
                sonraki_saat = (dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).timestamp()
                parca_sonu = min(bit, sonraki_saat)
                saatler[dt.hour] += parca_sonu - bas
                bas = parca_sonu

        return [{"saat": s, "ders_sn": round(saatler[s])} for s in range(24)]

    # ------------------------------------------------------------------
    #  Zinciri Kırma halkaları (tam / kurtarma / kalkan)
    # ------------------------------------------------------------------
    def zincir_halkasi_kaydet(self, gun: date, tur: str, zaman: float | None = None) -> None:
        """Bir günün zincir halkasını kaydeder (varsa türünü günceller, örn. kurtarma -> tam)."""
        with self._baglan() as vt:
            vt.execute(
                "INSERT INTO zincir_halkalari (tarih, tur, eklenme) VALUES (?, ?, ?)"
                " ON CONFLICT (tarih) DO UPDATE SET tur = excluded.tur, eklenme = excluded.eklenme",
                (gun.isoformat(), tur, zaman if zaman is not None else time.time()),
            )

    def zincir_halkasi_sil(self, gun: date) -> bool:
        with self._baglan() as vt:
            imlec = vt.execute("DELETE FROM zincir_halkalari WHERE tarih = ?", (gun.isoformat(),))
        return imlec.rowcount > 0

    def zincir_halkalari_getir(self, ilk_gun: date, son_gun: date) -> dict[str, str]:
        """İki tarih arasındaki kayıtlı zincir halkaları: {"2026-11-21": "tam", ...}."""
        with self._baglan() as vt:
            satirlar = vt.execute(
                "SELECT tarih, tur FROM zincir_halkalari WHERE tarih BETWEEN ? AND ?",
                (ilk_gun.isoformat(), son_gun.isoformat()),
            ).fetchall()
        return {s["tarih"]: s["tur"] for s in satirlar}

    # ------------------------------------------------------------------
    #  Sağlık verisi (adım, egzersiz, uyku)
    # ------------------------------------------------------------------
    SAGLIK_ALANLARI = ("adim", "egzersiz_dk", "uyku_dk")

    def saglik_kaydet(self, gun: date, adim: int | None = None, egzersiz_dk: int | None = None,
                      uyku_dk: int | None = None, kaynak: str = "elle") -> None:
        """Bir günün sağlık verisini kaydeder.

        None verilen alan DEĞİŞMEZ (örn. yalnızca adımı girmek egzersizi silmez).
        Aynı gün tekrar kaydedilirse üzerine yazılır; yani içe aktarma tekrar
        çalıştırılabilir, veri çiftlenmez.
        """
        with self._baglan() as vt:
            vt.execute(
                "INSERT INTO saglik_gunluk (tarih, adim, egzersiz_dk, uyku_dk, kaynak, guncelleme)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (tarih) DO UPDATE SET"
                "  adim = COALESCE(excluded.adim, saglik_gunluk.adim),"
                "  egzersiz_dk = COALESCE(excluded.egzersiz_dk, saglik_gunluk.egzersiz_dk),"
                "  uyku_dk = COALESCE(excluded.uyku_dk, saglik_gunluk.uyku_dk),"
                "  kaynak = excluded.kaynak, guncelleme = excluded.guncelleme",
                (gun.isoformat(), adim, egzersiz_dk, uyku_dk, kaynak, time.time()),
            )

    def saglik_sil(self, gun: date) -> bool:
        with self._baglan() as vt:
            imlec = vt.execute("DELETE FROM saglik_gunluk WHERE tarih = ?", (gun.isoformat(),))
        return imlec.rowcount > 0

    def saglik_getir(self, ilk_gun: date, son_gun: date) -> dict[str, dict]:
        """İki tarih arasındaki (dahil) sağlık kayıtları: {"2026-11-21": {"adim": 8200, ...}}."""
        with self._baglan() as vt:
            satirlar = vt.execute(
                "SELECT * FROM saglik_gunluk WHERE tarih BETWEEN ? AND ?",
                (ilk_gun.isoformat(), son_gun.isoformat()),
            ).fetchall()
        return {s["tarih"]: dict(s) for s in satirlar}

    def gunluk_birlesik(self, ilk_gun: date, son_gun: date) -> list[dict]:
        """Gün gün çalışma süresi + sağlık verisi tek listede (dashboard / Health Connect için).

        Örn: {"tarih": "2026-11-21", "ders_sn": 7200, "adim": 8200, "egzersiz_dk": 30, "uyku_dk": null}
        """
        saglik = self.saglik_getir(ilk_gun, son_gun)
        sonuc = []
        for gun in self.gunluk_sureler(ilk_gun, son_gun):
            kayit = saglik.get(gun["tarih"], {})
            sonuc.append({**gun, **{alan: kayit.get(alan) for alan in self.SAGLIK_ALANLARI}})
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
