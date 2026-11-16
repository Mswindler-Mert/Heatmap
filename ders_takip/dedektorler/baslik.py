"""Modül 2 - Tarayıcı / YouTube başlık sınıflandırıcı.

Tarayıcı öndeyken pencere başlığı sekmenin adıdır, örn:
    "(3) Database Normalization Lecture 5 - YouTube - Google Chrome"

Bu modül başlığı temizler ve şu sırayla karar verir:
    1. Öğrenilen "tam başlık" kuralı   (bu başlığı daha önce sen düzelttin)
    2. Öğrenilen anahtar kelimeler      (düzeltme ekranında sen ekledin)
    3. Ayar dosyasındaki anahtar kelimeler
    4. Hiçbiri tutmazsa ya da çelişirse -> BELİRSİZ
"""

import re

from ders_takip.sinyal import BELIRSIZ, DERS, DERS_DEGIL, DEVAM, FIKRIM_YOK, Dedektor, Sinyal

# Başlığın sonundaki " - Google Chrome" gibi tarayıcı adını yakalar.
# (Edge, adının içine görünmez bir karakter koyduğu için "Microsoft.{0,3}Edge".)
_TARAYICI_SONEKI = re.compile(
    r"\s+[-–—]\s+(Google Chrome|Microsoft.{0,3}Edge|Mozilla Firefox( Private Browsing)?"
    r"|Brave|Opera|Vivaldi)\s*$"
)
# Edge ayrıca profil adını ve "and 3 more pages" bilgisini ekler.
_EDGE_PROFIL = re.compile(r"\s+[-–—]\s+(Personal|Kişisel|Work|İş|Profile? \d+)\s*$")
_EDGE_SAYFA = re.compile(r"\s+(and \d+ more pages?|ve \d+ sayfa daha)\s*$")
# YouTube'un başa koyduğu bildirim sayısı: "(3) Video adı"
_BILDIRIM_SAYISI = re.compile(r"^\(\d+\+?\)\s*")


def basligi_temizle(baslik: str) -> str:
    """Tarayıcı adını, profil adını ve bildirim sayısını başlıktan atar."""
    temiz = _TARAYICI_SONEKI.sub("", baslik)
    temiz = _EDGE_PROFIL.sub("", temiz)
    temiz = _EDGE_SAYFA.sub("", temiz)
    temiz = _BILDIRIM_SAYISI.sub("", temiz)
    return temiz.strip()


def _kucult(metin: str) -> str:
    """Karşılaştırma için küçük harfe çevirir (Türkçe 'İ' harfine dikkat ederek)."""
    return metin.replace("İ", "i").lower()


def kelime_gecer_mi(metin: str, kelime: str) -> bool:
    """`kelime`, `metin` içinde TAM kelime olarak geçiyor mu?

    "ML" kelimesi "ML Lecture 3" içinde geçer ama "HTML" içinde geçmez.
    (?<!\\w) = "öncesinde harf/rakam yok", (?!\\w) = "sonrasında harf/rakam yok".
    """
    kelime = kelime.strip()
    if not kelime:
        return False
    desen = r"(?<!\w)" + re.escape(_kucult(kelime)) + r"(?!\w)"
    return re.search(desen, _kucult(metin)) is not None


def _kelimelerle_karar(metin: str, ders_kelimeleri, ders_degil_kelimeleri):
    """Kelime listelerine göre (hüküm, eşleşen kelimeler) döndürür.

    Hiç eşleşme yoksa hüküm None olur. İki listeden de eşleşme varsa
    çelişki var demektir -> BELİRSİZ.
    """
    dersler = [k for k in ders_kelimeleri if kelime_gecer_mi(metin, k)]
    degiller = [k for k in ders_degil_kelimeleri if kelime_gecer_mi(metin, k)]

    if dersler and degiller:
        return BELIRSIZ, dersler + degiller
    if dersler:
        return DERS, dersler
    if degiller:
        return DERS_DEGIL, degiller
    return None, []


class BaslikDedektoru(Dedektor):
    ad = "baslik"

    def __init__(self, ayarlar: dict, kural_kaynagi=None):
        bolum = ayarlar["baslik"]
        self.ders_kelimeleri = bolum["ders_kelimeleri"]
        self.ders_degil_kelimeleri = bolum["ders_degil_kelimeleri"]
        self.video_isaretleri = bolum["video_isaretleri"]
        # Bu başlıklar sayacı hiç etkilemez (örn. takip panelinin kendi sekmesi).
        self.yok_sayilanlar = bolum.get("yok_sayilan_basliklar", [])
        self.kural_kaynagi = kural_kaynagi or (lambda: [])

    def siniflandir(self, temiz_baslik: str) -> tuple[str, str]:
        """Temizlenmiş başlık için (hüküm, açıklama) döndürür."""
        if not temiz_baslik:
            return BELIRSIZ, "Sekme başlığı boş"

        kurallar = self.kural_kaynagi()

        # 1) Bu başlığın aynısını daha önce düzelttin mi?
        for kural in kurallar:
            if kural["tur"] == "baslik" and _kucult(kural["desen"]) == _kucult(temiz_baslik):
                return kural["hukum"], "Bu başlığı daha önce sen işaretledin"

        # 2) Senin eklediğin anahtar kelimeler
        ogrenilen_ders = [k["desen"] for k in kurallar if k["tur"] == "kelime" and k["hukum"] == DERS]
        ogrenilen_degil = [k["desen"] for k in kurallar if k["tur"] == "kelime" and k["hukum"] == DERS_DEGIL]
        hukum, eslesen = _kelimelerle_karar(temiz_baslik, ogrenilen_ders, ogrenilen_degil)
        if hukum is not None:
            return hukum, "Öğrenilen kelime: " + ", ".join(eslesen)

        # 3) Ayar dosyasındaki anahtar kelimeler
        hukum, eslesen = _kelimelerle_karar(temiz_baslik, self.ders_kelimeleri, self.ders_degil_kelimeleri)
        if hukum is not None:
            return hukum, "Anahtar kelime: " + ", ".join(eslesen)

        # 4) Karar verilemedi
        return BELIRSIZ, "Başlıkta tanıdık bir kelime yok"

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        pencere = onceki.get("pencere")
        # Önde tarayıcı yoksa bu modülün söyleyeceği bir şey yok.
        if pencere is None or not pencere.detay.get("tarayici"):
            return Sinyal(self.ad, FIKRIM_YOK, "Önde tarayıcı yok")

        temiz = basligi_temizle(pencere.detay.get("baslik", ""))

        # Yok sayılan sekme: "önceki durum neyse o sürsün" de.
        if any(kelime_gecer_mi(temiz, yok) for yok in self.yok_sayilanlar):
            return Sinyal(self.ad, DEVAM, "Yok sayılan sekme: önceki durum sürüyor",
                          {"temiz_baslik": temiz, "video": False})

        video = any(_kucult(isaret) in _kucult(temiz) for isaret in self.video_isaretleri)
        hukum, aciklama = self.siniflandir(temiz)
        return Sinyal(self.ad, hukum, aciklama, {"temiz_baslik": temiz, "video": video})
