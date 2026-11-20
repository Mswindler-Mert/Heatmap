"""Modül 5 - Tarayıcı eklentisi dedektörü.

Bu modül kendi başına bir şey ölçmez: Brave/Chrome eklentisi (eklenti/ klasörü)
birkaç saniyede bir /api/tarayici adresine rapor gönderir, web sunucusu bunu
rapor_al() ile buraya bırakır. oku() en son raporu diğer modüllere aktarır:

    alan_adi : öndeki sekmenin sitesi, örn. "youtube.com"
    sesli    : sekme ses çalıyor mu (video gerçekten oynuyor mu)

Hüküm vermez (hep FIKRIM_YOK); başlık dedektörü bu bilgiyi kullanır.
Eklenti kurulu değilse ya da rapor bayatsa "bagli: False" der ve her şey
eskisi gibi (yalnızca sekme başlığıyla) çalışır.
"""

import re
import threading
import time

from heatmap.sinyal import FIKRIM_YOK, Dedektor, Sinyal

# Eklenti olay olmasa da 30 sn'de bir rapor gönderir; bundan eski rapora güvenmeyiz.
TAZELIK_SN = 75
_ALAN_ADI = re.compile(r"^[a-z0-9.-]{1,253}$")


def alan_adini_temizle(alan_adi: str) -> str:
    """Gelen site adını küçültür, "www." atar; geçersizse boş döner."""
    alan = (alan_adi or "").strip().lower()
    if alan.startswith("www."):
        alan = alan[4:]
    return alan if _ALAN_ADI.match(alan) else ""


class TarayiciDedektoru(Dedektor):
    ad = "tarayici"

    def __init__(self, saat=time.time):
        """saat: şimdiki zamanı veren fonksiyon (testlerde sahte saat verilir)."""
        self.saat = saat
        self._kilit = threading.Lock()  # Web sunucusu yazar, takip döngüsü okur
        self._rapor = None
        self._rapor_zamani = 0.0

    def rapor_al(self, alan_adi: str, sesli: bool, odakta: bool) -> None:
        """Eklentiden gelen raporu saklar (web sunucusu thread'inden çağrılır)."""
        with self._kilit:
            self._rapor = {"alan_adi": alan_adini_temizle(alan_adi), "sesli": bool(sesli), "odakta": bool(odakta)}
            self._rapor_zamani = self.saat()

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        pencere = onceki.get("pencere")
        if pencere is None or not pencere.detay.get("tarayici"):
            return Sinyal(self.ad, FIKRIM_YOK, "Önde tarayıcı yok", {"bagli": False})

        with self._kilit:
            rapor, zaman = self._rapor, self._rapor_zamani
        if rapor is None or self.saat() - zaman > TAZELIK_SN:
            return Sinyal(self.ad, FIKRIM_YOK, "Eklentiden haber yok (yalnızca başlığa bakılıyor)", {"bagli": False})
        if not rapor["odakta"]:
            # Önde bir tarayıcı var ama eklentili tarayıcı değil (başka tarayıcı ya da profil).
            return Sinyal(self.ad, FIKRIM_YOK, "Öndeki tarayıcıda eklenti yok", {"bagli": False})

        site = rapor["alan_adi"] or "tarayıcı sayfası"
        ses = "ses çalıyor" if rapor["sesli"] else "ses yok"
        return Sinyal(self.ad, FIKRIM_YOK, f"{site} · {ses}",
                      {"bagli": True, "alan_adi": rapor["alan_adi"], "sesli": rapor["sesli"]})
