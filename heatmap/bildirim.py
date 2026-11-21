"""Sessiz masaüstü bildirimleri: günlük hedef tamamlandığında ve akşam zincir hatırlatması.

Karar mantığı zamandan bağımsızdır (`simdi: datetime` parametre olarak verilir); böylece
testler saati beklemeden her senaryoyu deneyebilir. Gerçek bildirim pystray'in yerleşik
Windows bildirim desteği (`ikon.notify`) ile gösterilir — ek paket gerekmez.
"""

from datetime import date, datetime

from heatmap.mini_sayac import sure_kisa


class BildirimYoneticisi:
    """Her bildirim türünü günde en fazla bir kez üretir."""

    def __init__(self):
        self._ilk_kontrol = True
        self._hedef_bildirilen_gun: date | None = None
        self._hatirlatma_gunu: date | None = None

    def kontrol_et(self, simdi: datetime, bugun_sn: int, hedef_sn: int,
                   zincir_uzunlugu: int, ayarlar: dict) -> list[tuple[str, str]]:
        """Gösterilmesi gereken (baslik, mesaj) bildirimlerinin listesini döndürür."""
        bugun = simdi.date()

        # Uygulama açıldığında hedef zaten tamamlanmışsa yeniden başlatmada tekrar bildirme.
        if self._ilk_kontrol:
            self._ilk_kontrol = False
            if hedef_sn > 0 and bugun_sn >= hedef_sn:
                self._hedef_bildirilen_gun = bugun
            return []

        if hedef_sn <= 0:
            return []

        bildirim_ayari = ayarlar.get("bildirim", {})
        zincir_ayari = ayarlar.get("zincir", {})
        sonuc: list[tuple[str, str]] = []

        # 1) Günlük hedef tamamlandı bildirimi
        if (bildirim_ayari.get("hedef_tamam", True)
                and bugun_sn >= hedef_sn
                and self._hedef_bildirilen_gun != bugun):
            self._hedef_bildirilen_gun = bugun
            ek = ("Yeni halkan zincire otomatik eklendi."
                  if zincir_ayari.get("otomatik_tak", False)
                  else "Yeni zincir halkan hazır — arayüzden takabilirsin.")
            sonuc.append((
                "Heatmap · Günlük hedef tamam!",
                f"Bugünkü {sure_kisa(hedef_sn)} hedefine ulaştın! {ek}",
            ))

        # 2) Akşam zinciri kurtarma hatırlatması
        hatirlatma_saati = int(bildirim_ayari.get("hatirlatma_saati", 22))
        if (bildirim_ayari.get("aksam_hatirlatma", True)
                and simdi.hour >= hatirlatma_saati
                and bugun_sn < hedef_sn
                and zincir_uzunlugu > 0
                and self._hatirlatma_gunu != bugun):
            self._hatirlatma_gunu = bugun
            kalan = hedef_sn - bugun_sn
            sonuc.append((
                "Heatmap · Zinciri kırma!",
                f"{zincir_uzunlugu} günlük zincirin devam ediyor. Bugünkü hedefine {sure_kisa(kalan)} kaldı.",
            ))

        return sonuc
