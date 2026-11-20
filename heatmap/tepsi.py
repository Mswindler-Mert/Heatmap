"""Sistem tepsisi (saatin yanındaki) ikonu.

İkon yeşilse sayaç çalışıyor, sarıysa durum belirsiz, griyse sayaç durmuş.
Sağ tık menüsü: arayüzü aç, takibi duraklat, ayar dosyasını aç, çıkış.
"""

import subprocess
import time
import webbrowser

import pystray
from PIL import Image, ImageDraw

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


class Tepsi:
    def __init__(self, takipci: Takipci, adres: str):
        self.takipci = takipci
        self.adres = adres
        self._ikonlar = {"ders": _ikon_ciz(YESIL), "belirsiz": _ikon_ciz(SARI), "durdu": _ikon_ciz(GRI)}
        self._calisiyor = True

        menu = pystray.Menu(
            # default=True: ikona çift/sol tıklayınca bu çalışır.
            pystray.MenuItem("Arayüzü aç", self._arayuzu_ac, default=True),
            pystray.MenuItem("Takibi duraklat", self._duraklat_degistir,
                             checked=lambda oge: self.takipci.duraklatildi),
            pystray.MenuItem("Ayar dosyasını aç", self._ayarlari_ac),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", self._cikis),
        )
        self.ikon = pystray.Icon("ders-takip", self._ikonlar["durdu"], "Ders Takip", menu)

    # --- Menü işlemleri --------------------------------------------------
    def _arayuzu_ac(self, ikon=None, oge=None):
        webbrowser.open(self.adres)

    def _duraklat_degistir(self, ikon=None, oge=None):
        self.takipci.duraklat(not self.takipci.duraklatildi)

    def _ayarlari_ac(self, ikon=None, oge=None):
        subprocess.Popen(["notepad.exe", str(KISISEL_DOSYA)])

    def _cikis(self, ikon=None, oge=None):
        self._calisiyor = False
        self.ikon.stop()

    # --- İkonu güncel tutma ----------------------------------------------
    def _guncelleme_dongusu(self, ikon):
        """pystray bunu ayrı bir thread'de çalıştırır: her saniye ikon rengini ve ipucunu yeniler."""
        ikon.visible = True
        onceki = None
        while self._calisiyor:
            durum = self.takipci.durum()
            if durum["duraklatildi"]:
                anahtar, yazi = "durdu", "duraklatıldı"
            elif durum["calisiyor"]:
                anahtar, yazi = "ders", "sayaç çalışıyor"
            elif durum.get("hukum") == "belirsiz":
                anahtar, yazi = "belirsiz", "belirsiz"
            else:
                anahtar, yazi = "durdu", "sayaç durdu"

            if anahtar != onceki:  # Resmi sadece değişince yenile
                ikon.icon = self._ikonlar[anahtar]
                onceki = anahtar
            sn = durum["bugun_ders_sn"]
            ikon.title = f"Ders Takip · bugün {sn // 3600} sa {sn % 3600 // 60} dk · {yazi}"
            time.sleep(1)

    def calistir(self):
        """İkonu gösterir ve "Çıkış" seçilene kadar burada bekler (ana thread'i tutar)."""
        self.ikon.run(setup=self._guncelleme_dongusu)
