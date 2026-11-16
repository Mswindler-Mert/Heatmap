"""Modül 3 - Klavye/fare boşta kalma dedektörü.

Sadece "ne zamandır dokunulmuyor?" sorusunu yanıtlar. "Video izlerken
boşta olmak sorun değil" kuralı burada DEĞİL, karar motorundadır; çünkü
o kural iki modülün bilgisini birleştirmeyi gerektirir.
"""

from ders_takip.sinyal import DERS_DEGIL, FIKRIM_YOK, Dedektor, Sinyal


class BostaDedektoru(Dedektor):
    ad = "bosta"

    def __init__(self, ayarlar: dict, okuyucu=None):
        bolum = ayarlar["bosta"]
        self.esik_sn = bolum["esik_sn"]
        self.video_esik_sn = bolum["video_esik_sn"]
        if okuyucu is None:
            from ders_takip.windows_api import bosta_suresini_oku as okuyucu
        self.okuyucu = okuyucu

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        bosta_sn = self.okuyucu()
        detay = {
            "bosta_sn": round(bosta_sn),
            # Karar motoru video izlenirken bu ikinci, daha uzun eşiğe bakar.
            "video_esigi_asildi": bosta_sn >= self.video_esik_sn,
        }
        if bosta_sn >= self.esik_sn:
            return Sinyal(self.ad, DERS_DEGIL, f"{round(bosta_sn)} sn'dir klavye/fare kullanılmıyor", detay)
        return Sinyal(self.ad, FIKRIM_YOK, "Klavye/fare kullanılıyor", detay)
