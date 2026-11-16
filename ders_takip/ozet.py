"""Özet yardımcıları: okunabilir adlar ve seri (üst üste gün) hesabı.

Veritabanında süreç adları ("Code.exe") ve ham sekme başlıkları durur.
Dökümde ve paylaşım kartında bunların yerine okunabilir adlar gösteririz:
    Code.exe                      -> "VS Code"      (ayar dosyası: [adlar])
    "... - YouTube" başlıklı sekme -> "YouTube"     (ayar dosyası: [siteler])
"""

import re
from datetime import date, timedelta

from ders_takip.dedektorler.baslik import son_gecis_yeri

DIGER_WEB = "Diğer web"
BILGISAYAR_DISI = "Bilgisayar dışı"


class Adlandirici:
    """Bir oturumu dökümde görünecek ada çevirir."""

    def __init__(self, ayarlar: dict):
        # Süreç adı karşılaştırması büyük/küçük harfe duyarsız olsun.
        self._adlar = {surec.lower(): ad for surec, ad in ayarlar.get("adlar", {}).items()}
        # {"YouTube": ["YouTube"], "claude.ai": ["Claude"], ...}
        self._siteler = ayarlar.get("siteler", {})

    def uygulama_adi(self, surec: str) -> str:
        """'Code.exe' -> 'VS Code'. Eşleme yoksa sadece '.exe' uzantısı atılır."""
        if not surec:
            return BILGISAYAR_DISI
        ad = self._adlar.get(surec.lower())
        if ad:
            return ad
        return re.sub(r"\.exe$", "", surec, flags=re.IGNORECASE)

    def site_adi(self, baslik: str) -> str:
        """Sekme başlığından site adını çıkarır; tanınmıyorsa 'Diğer web'.

        Site adı başlığın genellikle SONUNDA yer alır ("Video adı - YouTube").
        Bu yüzden birden çok site kelimesi geçiyorsa başlıkta en sonda geçeni
        seçiyoruz: "GitHub Tutorial - YouTube" -> YouTube.
        """
        en_iyi_site, en_iyi_yer = DIGER_WEB, -1
        for site, kelimeler in self._siteler.items():
            for kelime in kelimeler:
                yer = son_gecis_yeri(baslik, kelime)
                if yer > en_iyi_yer:
                    en_iyi_site, en_iyi_yer = site, yer
        return en_iyi_site

    def etiket(self, oturum: dict) -> tuple[str, str]:
        """Bir oturum satırı için (görünen ad, tür) döndürür. Tür: 'site' ya da 'uygulama'.

        DİKKAT (gizlilik): Buradan dönen ad asla sekme başlığının kendisi değildir;
        yalnızca ayar dosyasındaki site/uygulama adlarından biridir.
        """
        if oturum.get("kaynak") == "baslik":  # Tarayıcı oturumu
            return self.site_adi(oturum.get("baslik") or ""), "site"
        return self.uygulama_adi(oturum.get("uygulama") or ""), "uygulama"


def seri_hesapla(depo, hedef_sn: int, bugun: date) -> int:
    """Günlük hedefe üst üste kaç gündür ulaşıldığını sayar.

    Bugün hedefe henüz ulaşılmadıysa seri bozulmuş sayılmaz (gün daha bitmedi);
    dünden geriye doğru sayılır.
    """
    if hedef_sn <= 0:
        return 0
    seri = 0
    gun = bugun
    for _ in range(366):  # En fazla bir yıl geriye bak
        sure = depo.gunluk_sureler(gun, gun)[0]["ders_sn"]
        if sure >= hedef_sn:
            seri += 1
        elif gun != bugun:
            break
        gun -= timedelta(days=1)
    return seri
