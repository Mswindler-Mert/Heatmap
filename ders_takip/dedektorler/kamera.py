"""Modül 4 - Kamera dedektörü (ŞİMDİLİK SADECE İSKELET).

Bu dosya kameraya DOKUNMAZ; sadece ileride yazılacak kodun oturacağı
kalıbı tanımlar. Ayar dosyasında [kamera] etkin = true yapılsa bile
şimdilik her zaman "fikrim yok" döner.

--------------------------------------------------------------------
GİZLİLİK KURALLARI (geliştirirken bunlara uy):
  1. Kamera karesi ASLA diske yazılmaz (cv2.imwrite, VideoWriter YOK).
  2. Kare ASLA ağ üzerinden gönderilmez; analiz tamamen bu bilgisayarda yapılır.
  3. Kare, analiz biter bitmez bellekten atılır; bu sınıfın dışına ÇIKMAZ.
  4. Dışarıya (karar motoruna, veritabanına, API'ye) giden tek şey
     KameraGozlemi içindeki evet/hayır değerleridir.
--------------------------------------------------------------------

Geliştirme planı SONRAKI_ADIMLAR.md dosyasında.
"""

from dataclasses import dataclass

from ders_takip.sinyal import DERS_DEGIL, FIKRIM_YOK, Dedektor, Sinyal


@dataclass
class KameraGozlemi:
    """Bir karenin analiz SONUCU. Görüntünün kendisi burada yer almaz.

    None = "ölçülemedi / bilinmiyor".
    """

    yuz_var: bool | None = None           # Kadrajda yüz var mı
    kafa_asagi_egik: bool | None = None   # Kafa belirgin biçimde aşağı eğik mi
    telefona_bakiyor: bool | None = None  # Bakış/duruş telefona bakmaya benziyor mu


class KameraDedektoru(Dedektor):
    ad = "kamera"

    def __init__(self, ayarlar: dict):
        bolum = ayarlar.get("kamera", {})
        # İleride eklenecek ayarlar için örnekler (config.ornek.toml'a da eklenmeli):
        self.yuz_yok_esik_sn = bolum.get("yuz_yok_esik_sn", 30)
        self.kafa_egik_esik_sn = bolum.get("kafa_egik_esik_sn", 60)
        # TODO: Kamerayı burada açma; ilk oku() çağrısında aç (program hızlı açılsın).

    def _gozlemle(self) -> KameraGozlemi | None:
        """Kameradan TEK kare al, analiz et, kareyi at, sonucu döndür.

        TODO (ileride):
            kare = self._kamera.read()
            sonuc = mediapipe ile yüz / kafa açısı analizi
            del kare                      # kareyi saklama!
            return KameraGozlemi(yuz_var=..., kafa_asagi_egik=..., telefona_bakiyor=...)

        Şimdilik None döndürür = "kamera modülü çalışmıyor".
        """
        return None

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        gozlem = self._gozlemle()
        if gozlem is None:
            return Sinyal(self.ad, FIKRIM_YOK, "Kamera modülü henüz geliştirilmedi")

        # TODO: Tek kareye göre karar verme. "Yüz 30 sn'dir yok" ya da "kafa 60 sn'dir
        # eğik" gibi SÜRE koşulları için son gözlemlerin zamanını burada tut.
        # Aşağısı sadece sinyalin nasıl görüneceğine dair örnek:
        detay = {
            "yuz_var": gozlem.yuz_var,
            "kafa_asagi_egik": gozlem.kafa_asagi_egik,
            "telefona_bakiyor": gozlem.telefona_bakiyor,
        }
        if gozlem.yuz_var is False:
            return Sinyal(self.ad, DERS_DEGIL, "Kamerada yüz görünmüyor", detay)
        if gozlem.telefona_bakiyor:
            return Sinyal(self.ad, DERS_DEGIL, "Telefona bakıyor gibi", detay)
        # Kamera hiçbir zaman tek başına "ders" demez; sadece veto eder.
        return Sinyal(self.ad, FIKRIM_YOK, "Masada görünüyor", detay)

    def kapat(self) -> None:
        """TODO: self._kamera.release() - kamerayı serbest bırak."""
