"""Sistem tepsisi (saatin yanındaki) ikonu.

İkon yeşilse sayaç çalışıyor, sarıysa durum belirsiz, griyse sayaç durmuş.
Sağ tık menüsü: arayüzü aç, takibi duraklat, ayar dosyasını aç,
Windows açılışında başlat (aç/kapat), çıkış.
"""

import subprocess
import time
import webbrowser

import pystray
from PIL import Image, ImageDraw

from heatmap import otomatik_baslatma
from heatmap.ayarlar import KISISEL_DOSYA
from heatmap.takipci import Takipci

YESIL = (62, 207, 142)
SARI = (245, 183, 79)
GRI = (120, 128, 145)


def _ikon_ciz(renk: tuple[int, int, int]) -> Image.Image:
    """Verilen renkte basit, yuvarlak bir ikon resmi üretir."""
    resim = Image.new("RGBA", (64, 64), (0, 0, 0, 0))  # Saydam zemin
    cizim = ImageDraw.Draw(resim)
    cizim.ellipse((6, 6, 58, 58), fill=renk)
    cizim.ellipse((22, 22, 42, 42), fill=(15, 17, 21))  # Ortadaki koyu nokta
    return resim


def ikon_durumu(durum: dict) -> tuple[str, str]:
    """Takipçi durumundan (ikon rengi anahtarı, fare üstüne gelince görünen ipucu) üretir.

    Anahtar: "ders" (yeşil), "belirsiz" (sarı) ya da "durdu" (gri).
    """
    if durum["duraklatildi"]:
        anahtar, yazi = "durdu", "duraklatıldı"
    elif durum["calisiyor"]:
        anahtar, yazi = "ders", "sayaç çalışıyor"
    elif durum.get("hukum") == "belirsiz":
        anahtar, yazi = "belirsiz", "belirsiz"
    else:
        anahtar, yazi = "durdu", "sayaç durdu"
    sn = durum["bugun_ders_sn"]
    return anahtar, f"Heatmap · bugün {sn // 3600} sa {sn % 3600 // 60} dk · {yazi}"


class Tepsi:
    def __init__(self, takipci: Takipci, adres: str, kamera=None):
        """kamera: KameraDedektoru (modül ayarlardan kapalıysa None; o zaman menüde görünmez)."""
        self.takipci = takipci
        self.adres = adres
        self.kamera = kamera
        self._ikonlar = {"ders": _ikon_ciz(YESIL), "belirsiz": _ikon_ciz(SARI), "durdu": _ikon_ciz(GRI)}
        self._calisiyor = True

        menu = pystray.Menu(
            # default=True: ikona çift/sol tıklayınca bu çalışır.
            pystray.MenuItem("Arayüzü aç", self._arayuzu_ac, default=True),
            pystray.MenuItem("Takibi duraklat", self._duraklat_degistir,
                             checked=lambda oge: self.takipci.duraklatildi),
            pystray.MenuItem("Ayar dosyasını aç", self._ayarlari_ac),
            pystray.MenuItem("Kamera açık", self._kamera_degistir,
                             checked=lambda oge: bool(self.kamera and self.kamera.acik),
                             visible=self.kamera is not None),
            # İşaret, kayıt defterindeki gerçek duruma göre her menü açılışında yeniden okunur.
            pystray.MenuItem("Windows açılışında başlat", self._otomatik_baslatma_degistir,
                             checked=lambda oge: otomatik_baslatma.acik_mi()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", self._cikis),
        )
        self.ikon = pystray.Icon("heatmap", self._ikonlar["durdu"], "Heatmap", menu)

    # --- Menü işlemleri --------------------------------------------------
    def _arayuzu_ac(self, ikon=None, oge=None):
        webbrowser.open(self.adres)

    def _duraklat_degistir(self, ikon=None, oge=None):
        self.takipci.duraklat(not self.takipci.duraklatildi)

    def _ayarlari_ac(self, ikon=None, oge=None):
        subprocess.Popen(["notepad.exe", str(KISISEL_DOSYA)])

    def _kamera_degistir(self, ikon=None, oge=None):
        if self.kamera is not None:
            self.kamera.ayarla_acik(not self.kamera.acik)

    def _otomatik_baslatma_degistir(self, ikon=None, oge=None):
        otomatik_baslatma.ayarla(not otomatik_baslatma.acik_mi())

    def _cikis(self, ikon=None, oge=None):
        self._calisiyor = False
        self.ikon.stop()

    # --- İkonu güncel tutma ----------------------------------------------
    def _guncelleme_dongusu(self, ikon):
        """pystray bunu ayrı bir thread'de çalıştırır: her saniye ikon rengini ve ipucunu yeniler."""
        ikon.visible = True
        onceki = None
        while self._calisiyor:
            anahtar, ipucu = ikon_durumu(self.takipci.durum())
            if anahtar != onceki:  # Resmi sadece değişince yenile
                ikon.icon = self._ikonlar[anahtar]
                onceki = anahtar
            ikon.title = ipucu
            time.sleep(1)

    def calistir(self):
        """İkonu gösterir ve "Çıkış" seçilene kadar burada bekler (ana thread'i tutar)."""
        self.ikon.run(setup=self._guncelleme_dongusu)
