"""Bütün modüllerin ortak dili: Sinyal ve Dedektor.

Her dedektör (pencere, başlık, boşta, kamera...) saniyede bir kez `oku()`
ile bir Sinyal üretir. Karar motoru sadece bu sinyallere bakar; dedektörün
içeride ne yaptığını bilmez. Yeni bir modül eklemek = Dedektor sınıfından
türetip `oku()` yazmak.
"""

from dataclasses import dataclass, field

# Bir dedektörün verebileceği hükümler.
DERS = "ders"                # "Bence şu an ders çalışıyor"
DERS_DEGIL = "ders_degil"    # "Bence şu an ders çalışmıyor"
BELIRSIZ = "belirsiz"        # "Baktım ama karar veremedim" (kullanıcı sonra düzeltebilir)
FIKRIM_YOK = "fikrim_yok"    # "Bu durum benim alanım değil, beni sayma"
DEVAM = "devam"              # "Bunu yok say: sayaç az önce ne durumdaysa öyle kalsın"
                             # (örn. takip panelinin kendi sekmesine bakarken)


@dataclass
class Sinyal:
    """Bir dedektörün tek bir andaki gözlemi."""

    kaynak: str               # Sinyali üreten dedektörün adı, örn. "pencere"
    hukum: str                # Yukarıdaki dört sabitten biri
    aciklama: str = ""        # Arayüzde gösterilecek kısa gerekçe
    detay: dict = field(default_factory=dict)  # Diğer modüllerin işine yarayabilecek ham bilgi


class Dedektor:
    """Bütün dedektörlerin uyması gereken kalıp (arayüz)."""

    ad = "isimsiz"  # Her alt sınıf kendi adını verir; sinyaller bu adla saklanır.

    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        """Şu anki durumu ölç ve bir Sinyal döndür.

        `onceki`: bu turda senden ÖNCE çalışan dedektörlerin sinyalleri.
        Örn. başlık dedektörü, pencere dedektörünün okuduğu başlığı buradan alır.
        """
        raise NotImplementedError

    def kapat(self) -> None:
        """Program kapanırken çağrılır (örn. kamerayı serbest bırakmak için)."""
