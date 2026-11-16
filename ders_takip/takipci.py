"""Takip döngüsü: programın kalbi.

Arka planda (ayrı bir thread'de) saniyede bir şunları yapar:
    1. Bütün dedektörleri sırayla okur            -> sinyaller
    2. Sinyalleri birleştirir                      -> anlık karar
    3. Anlık kararı tolerans süzgecinden geçirir   -> (varsa) geçiş
    4. Geçiş olduysa eski oturumu kapatır, yenisini açar
    5. Arayüzün göstereceği "şu anki durum" özetini günceller
"""

import threading
import time
from datetime import date, datetime

from ders_takip.depo import Depo, gun_araligi
from ders_takip.motor import KararMotoru, anlik_karar
from ders_takip.sinyal import DERS, FIKRIM_YOK, Dedektor, Sinyal

# İki tarama arasında bundan uzun boşluk varsa bilgisayar uyumuş demektir.
UYKU_ESIGI_SN = 30
# Süren oturumun bitiş anı veritabanına bu sıklıkta yazılır. Program çökse
# ya da elektrik kesilse bile en fazla bu kadar saniye kaybolur.
KAYIT_ARALIGI_SN = 5


class Takipci:
    def __init__(self, ayarlar: dict, depo: Depo, dedektorler: list[Dedektor], motor: KararMotoru):
        self.aralik_sn = ayarlar["genel"]["tarama_araligi_sn"]
        self.depo = depo
        self.dedektorler = dedektorler
        self.motor = motor

        self.duraklatildi = False
        self._oturum_id = None          # Şu an açık olan oturumun veritabanı numarası
        self._oturum_baslangic = None
        self._son_kayit = 0.0           # Açık oturumun veritabanına yazılmış son bitiş anı
        self._son_tik = None            # Bir önceki taramanın zamanı
        self._goruntu = {}              # Arayüz için hazır tutulan özet

        # Takip thread'i ile web sunucusu aynı değişkenlere dokunuyor;
        # kilit, ikisinin aynı anda girmesini engeller.
        self._kilit = threading.RLock()
        self._dur = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------
    #  Başlat / durdur
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        self._thread = threading.Thread(target=self._dongu, name="takipci", daemon=True)
        self._thread.start()

    def durdur(self) -> None:
        """Programdan çıkarken: döngüyü bitir, açık oturumu kapat."""
        self._dur.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._kilit:
            self._oturumu_kapat(time.time())
        for dedektor in self.dedektorler:
            dedektor.kapat()

    def duraklat(self, deger: bool) -> None:
        """Takibi elle duraklat / devam ettir (tepsi menüsünden)."""
        with self._kilit:
            self.duraklatildi = deger
            if deger:
                self._oturumu_kapat(time.time())
                self.motor.sifirla()
                self._goruntu = {}

    def _dongu(self) -> None:
        # wait(): aralık kadar bekler; durdur() çağrılırsa beklemeyi kesip True döner.
        while not self._dur.wait(self.aralik_sn):
            try:
                self.tik(time.time())
            except Exception as hata:  # Tek bir hata bütün takibi öldürmesin
                print(f"[takipci] hata: {hata!r}", flush=True)

    # ------------------------------------------------------------------
    #  Tek bir tarama
    # ------------------------------------------------------------------
    def tik(self, simdi: float) -> None:
        with self._kilit:
            if self.duraklatildi:
                self._son_tik = simdi
                return

            # Bilgisayar uykudan döndüyse: eski oturumu uyumadan önceki anda kapat.
            if self._son_tik is not None and simdi - self._son_tik > UYKU_ESIGI_SN:
                self._oturumu_kapat(self._son_tik)
                self.motor.sifirla()
            self._son_tik = simdi

            # 1) Dedektörleri sırayla oku. Her biri öncekilerin sinyallerini görebilir.
            sinyaller: dict[str, Sinyal] = {}
            for dedektor in self.dedektorler:
                try:
                    sinyaller[dedektor.ad] = dedektor.oku(sinyaller)
                except Exception as hata:
                    # Bozuk bir modül diğerlerini etkilemesin.
                    sinyaller[dedektor.ad] = Sinyal(dedektor.ad, FIKRIM_YOK, f"Modül hatası: {hata}")

            # 2) ve 3) Karar
            anlik = anlik_karar(sinyaller)
            gecis = self.motor.guncelle(anlik, simdi)

            # 4) Durum değiştiyse veritabanını güncelle
            if gecis is not None:
                self._oturumu_kapat(gecis.zaman)
                self._oturum_id = self.depo.oturum_baslat(gecis.durum, gecis.zaman)
                self._oturum_baslangic = gecis.zaman
                self._son_kayit = gecis.zaman

            if self._oturum_id is not None and simdi - self._son_kayit >= KAYIT_ARALIGI_SN:
                self.depo.oturum_bitisini_guncelle(self._oturum_id, simdi)
                self._son_kayit = simdi

            # 5) Arayüz için özet
            mevcut = self.motor.mevcut
            if mevcut is None:
                # Program açılır açılmaz yok sayılan bir sekmeye bakılıyor: henüz durum yok.
                self._goruntu = {}
                return
            self._goruntu = {
                "hukum": mevcut.hukum,
                "kaynak": mevcut.kaynak,
                "aciklama": mevcut.aciklama,
                "uygulama": mevcut.uygulama,
                "baslik": mevcut.baslik,
                "oturum_id": self._oturum_id,
                "oturum_baslangic": datetime.fromtimestamp(self._oturum_baslangic).isoformat(timespec="seconds"),
                "oturum_suresi_sn": round(simdi - self._oturum_baslangic),
                "anlik": {
                    "hukum": anlik.hukum,
                    "uygulama": anlik.uygulama,
                    "baslik": anlik.baslik,
                    "aciklama": anlik.aciklama,
                },
                "bekleyen_gecis": self.motor.bekleyen(anlik, simdi),
                "sinyaller": [
                    {"kaynak": s.kaynak, "hukum": s.hukum, "aciklama": s.aciklama}
                    for s in sinyaller.values()
                ],
            }

    def _oturumu_kapat(self, zaman: float) -> None:
        if self._oturum_id is not None:
            self.depo.oturum_bitisini_guncelle(self._oturum_id, zaman)
        self._oturum_id = None
        self._oturum_baslangic = None

    # ------------------------------------------------------------------
    #  Arayüz / API için
    # ------------------------------------------------------------------
    def durum(self) -> dict:
        """Şu an ne algılanıyor, sayaç ne durumda, bugün toplam ne kadar çalışıldı."""
        with self._kilit:
            goruntu = dict(self._goruntu)
            calisiyor = goruntu.get("hukum") == DERS and not self.duraklatildi
            # Veritabanına henüz yazılmamış son birkaç saniye (sayaç akıcı görünsün diye).
            yazilmamis = (self._son_tik - self._son_kayit) if calisiyor else 0.0
            duraklatildi = self.duraklatildi

        bas, bit = gun_araligi(date.today())
        bugun = self.depo.ders_suresi(bas, bit) + yazilmamis
        return {
            "duraklatildi": duraklatildi,
            "calisiyor": calisiyor,          # Sayaç şu an ilerliyor mu?
            "bugun_ders_sn": round(bugun),
            **goruntu,
        }
