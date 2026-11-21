"""Veritabanının günlük otomatik yedeği.

Her gün bir kez data/yedek/heatmap-YYYY-AA-GG.db dosyası oluşturulur ve en yeni
`saklanacak` kadar yedek tutulur, eskileri silinir. data/ klasörü Git'e girmez.

Neden dosyayı düz kopyalamıyoruz? Program çalışırken veritabanına yazıyor olabilir;
yarım yazılmış bir anın kopyası bozuk olur. SQLite'ın kendi yedekleme yöntemi
(Connection.backup) tutarlı bir anlık görüntü alır.

Yedekten geri dönmek için: Heatmap'i kapat, data/heatmap.db dosyasını başka bir adla
sakla, istediğin yedeği data/heatmap.db adıyla kopyala, Heatmap'i aç.
"""

import re
import sqlite3
import threading
from datetime import date
from pathlib import Path

_YEDEK_ADI = re.compile(r"^heatmap-(\d{4}-\d{2}-\d{2})\.db$")


def yedek_yolu(yedek_klasoru: Path, gun: date) -> Path:
    return Path(yedek_klasoru) / f"heatmap-{gun.isoformat()}.db"


def gunluk_yedek_al(db_yolu: Path, yedek_klasoru: Path, bugun: date, saklanacak: int = 7) -> Path | None:
    """Bugünün yedeği yoksa alır; fazla eski yedekleri siler.

    Yeni yedek alındıysa onun yolunu, bugünün yedeği zaten varsa ya da veritabanı
    henüz yoksa None döndürür.
    """
    db_yolu, yedek_klasoru = Path(db_yolu), Path(yedek_klasoru)
    if not db_yolu.exists():
        return None
    yedek_klasoru.mkdir(parents=True, exist_ok=True)
    hedef = yedek_yolu(yedek_klasoru, bugun)
    yeni = None
    if not hedef.exists():
        # Önce geçici adla yaz, bitince yeniden adlandır: yarıda kalırsa bozuk yedek kalmasın.
        gecici = hedef.with_suffix(".db.yaziliyor")
        kaynak = sqlite3.connect(db_yolu, timeout=5)
        try:
            hedef_vt = sqlite3.connect(gecici)
            try:
                kaynak.backup(hedef_vt)
            finally:
                hedef_vt.close()
        finally:
            kaynak.close()
        gecici.replace(hedef)
        yeni = hedef
    eskileri_sil(yedek_klasoru, saklanacak)
    return yeni


def yedekleri_listele(yedek_klasoru: Path) -> list[Path]:
    """Yedek dosyaları, yeniden eskiye."""
    klasor = Path(yedek_klasoru)
    if not klasor.exists():
        return []
    yedekler = [p for p in klasor.iterdir() if _YEDEK_ADI.match(p.name)]
    return sorted(yedekler, key=lambda p: p.name, reverse=True)  # Ad tarih içerdiği için sıralama tarihe göre


def eskileri_sil(yedek_klasoru: Path, saklanacak: int) -> list[Path]:
    """En yeni `saklanacak` yedek dışındakileri siler; silinenleri döndürür.

    Yalnızca heatmap-YYYY-AA-GG.db adlı dosyalara dokunur; klasördeki başka dosyalar kalır.
    """
    silinenler = yedekleri_listele(yedek_klasoru)[max(1, saklanacak):]
    for yol in silinenler:
        yol.unlink(missing_ok=True)
    return silinenler


class YedekZamanlayici:
    """Arka planda saatte bir "bugünün yedeği var mı?" diye bakar.

    Program günlerce açık kalabildiği için (Windows açılışında başlatma) yalnızca
    açılışta yedek almak yetmez; gün değişince de yedek alınsın diye düzenli bakılır.
    """

    def __init__(self, db_yolu: Path, yedek_klasoru: Path, saklanacak: int = 7, aralik_sn: float = 3600):
        self.db_yolu = db_yolu
        self.yedek_klasoru = yedek_klasoru
        self.saklanacak = saklanacak
        self.aralik_sn = aralik_sn
        self._dur = threading.Event()
        self._thread: threading.Thread | None = None

    def _dongu(self) -> None:
        while True:
            try:
                yol = gunluk_yedek_al(self.db_yolu, self.yedek_klasoru, date.today(), self.saklanacak)
                if yol:
                    print(f"Veritabanı yedeklendi: {yol.name}", flush=True)
            except (OSError, sqlite3.Error) as hata:  # Yedek alınamaması programı durdurmasın
                print(f"UYARI: yedek alınamadı ({hata})", flush=True)
            if self._dur.wait(self.aralik_sn):
                return

    def baslat(self) -> None:
        self._thread = threading.Thread(target=self._dongu, name="yedek", daemon=True)
        self._thread.start()

    def durdur(self) -> None:
        self._dur.set()
        if self._thread:
            self._thread.join(timeout=5)
