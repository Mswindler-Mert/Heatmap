"""Modül 1 - Aktif pencere / süreç dedektörü.

Öndeki uygulamanın exe adına bakar ve ayar dosyasındaki listelere göre
hüküm verir. Tarayıcılarda hüküm vermez; orada kararı başlık dedektörü
(baslik.py) verir.
"""

from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, FIKRIM_YOK, Dedektor, Sinyal


class PencereDedektoru(Dedektor):
    ad = "pencere"

    def __init__(self, ayarlar: dict, kural_kaynagi=None, okuyucu=None):
        """
        ayarlar       : ayarlari_yukle() çıktısı
        kural_kaynagi : çağrılınca "öğrenilen kurallar" listesini döndüren fonksiyon
        okuyucu       : (süreç adı, başlık) döndüren fonksiyon. Testlerde sahte
                        bir okuyucu verebilmek için parametre yaptık.
        """
        bolum = ayarlar["pencere"]
        # Karşılaştırmayı büyük/küçük harfe duyarsız yapmak için hepsini küçültüyoruz.
        self.ders = {ad.lower() for ad in bolum["ders_surecleri"]}
        self.ders_degil = {ad.lower() for ad in bolum["ders_degil_surecleri"]}
        self.tarayicilar = {ad.lower() for ad in bolum["tarayici_surecleri"]}

        self.bilinmeyen_hukum = bolum.get("bilinmeyen_hukum", BELIRSIZ)
        if self.bilinmeyen_hukum not in (BELIRSIZ, DERS_DEGIL):
            self.bilinmeyen_hukum = BELIRSIZ

        self.kural_kaynagi = kural_kaynagi or (lambda: [])
        if okuyucu is None:
            # Windows'a özel kodu sadece gerçekten gerekince içe aktarıyoruz.
            from heatmap.windows_api import aktif_pencereyi_oku as okuyucu
        self.okuyucu = okuyucu

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        surec, baslik = self.okuyucu()
        # Bu ham bilgiyi başlık dedektörü ve karar motoru da kullanacak.
        detay = {"surec": surec, "baslik": baslik, "tarayici": False}
        kucuk = surec.lower()

        if not surec:
            return Sinyal(self.ad, FIKRIM_YOK, "Öndeki pencere okunamadı", detay)

        # Tarayıcıysa karar bizde değil.
        if kucuk in self.tarayicilar:
            detay["tarayici"] = True
            return Sinyal(self.ad, FIKRIM_YOK, f"{surec}: tarayıcı, karar sekme başlığına göre", detay)

        # Önce senin düzeltmelerinden öğrenilen kurallar (ayar dosyasından önceliklidir).
        for kural in self.kural_kaynagi():
            if kural["tur"] == "surec" and kural["desen"].lower() == kucuk:
                return Sinyal(self.ad, kural["hukum"], f"{surec}: senin düzeltmenden öğrenildi", detay)

        if kucuk in self.ders:
            return Sinyal(self.ad, DERS, f"{surec}: çalışma uygulamaları listesinde", detay)
        if kucuk in self.ders_degil:
            return Sinyal(self.ad, DERS_DEGIL, f"{surec}: çalışma dışı uygulamalar listesinde", detay)

        return Sinyal(self.ad, self.bilinmeyen_hukum, f"{surec}: hiçbir listede yok", detay)
