"""Özet yardımcıları: okunabilir adlar ve seri (üst üste gün) hesabı.

Veritabanında süreç adları ("Code.exe") ve ham sekme başlıkları durur.
Dökümde ve paylaşım kartında bunların yerine okunabilir adlar gösteririz:
    Code.exe                      -> "VS Code"      (ayar dosyası: [adlar])
    "... - YouTube" başlıklı sekme -> "YouTube"     (ayar dosyası: [siteler])
"""

import re
from datetime import date, timedelta

from heatmap.dedektorler.baslik import alan_eslesir_mi, son_gecis_yeri

GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
DIGER_WEB = "Diğer web"
DIGER_KATEGORI = "Diğer"
BILGISAYAR_DISI = "Bilgisayar dışı"


class Adlandirici:
    """Bir oturumu dökümde görünecek ada çevirir."""

    def __init__(self, ayarlar: dict):
        # Süreç adı karşılaştırması büyük/küçük harfe duyarsız olsun.
        self._adlar = {surec.lower(): ad for surec, ad in ayarlar.get("adlar", {}).items()}
        # {"YouTube": ["YouTube"], "claude.ai": ["Claude"], ...}
        self._siteler = ayarlar.get("siteler", {})
        # Görünen ad -> kategori, örn. {"vs code": "Kod", "youtube": "Video ve kurs"}
        self._kategori = {ad.lower(): kategori
                          for kategori, adlar in ayarlar.get("kategoriler", {}).items() for ad in adlar}

    def kategori(self, gorunen_ad: str) -> str:
        """'VS Code' -> 'Kod'. Hiçbir kategoride yoksa 'Diğer'."""
        return self._kategori.get(gorunen_ad.lower(), DIGER_KATEGORI)

    def kategorilere_grupla(self, dokum: list[dict]) -> list[dict]:
        """Uygulama/site dökümünü kategorilere toplar, çoktan aza.

        Girdi : [{"ad": "VS Code", "sure_sn": 5400, ...}, ...]
        Çıktı : [{"ad": "Kod", "tur": "kategori", "sure_sn": 5400, "icerik": ["VS Code", ...]}, ...]
        """
        gruplar: dict[str, dict] = {}
        for u in dokum:  # dokum zaten çoktan aza sıralı; içerik de öyle kalır
            kat = self.kategori(u["ad"])
            grup = gruplar.setdefault(kat, {"ad": kat, "tur": "kategori", "sure_sn": 0, "icerik": []})
            grup["sure_sn"] += u["sure_sn"]
            grup["icerik"].append(u["ad"])
        return sorted(gruplar.values(), key=lambda g: g["sure_sn"], reverse=True)

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

    def alan_adindan_site(self, alan_adi: str) -> str:
        """'www.youtube.com' -> 'YouTube' ([siteler] içinde nokta içeren öğelerle eşleşirse),
        eşleşmezse site adının kendisi ('geeksforgeeks.org')."""
        for site, kelimeler in self._siteler.items():
            if any("." in k and alan_eslesir_mi(alan_adi, k) for k in kelimeler):
                return site
        return alan_adi

    def etiket(self, oturum: dict) -> tuple[str, str]:
        """Bir oturum satırı için (görünen ad, tür) döndürür. Tür: 'site' ya da 'uygulama'.

        DİKKAT (gizlilik): Buradan dönen ad asla sekme başlığının kendisi değildir;
        yalnızca ayar dosyasındaki site/uygulama adlarından biridir.
        """
        if oturum.get("kaynak") == "baslik":  # Tarayıcı oturumu
            if oturum.get("alan_adi"):  # Eklenti site adını bildirmişse en güvenilir bilgi o
                return self.alan_adindan_site(oturum["alan_adi"]), "site"
            return self.site_adi(oturum.get("baslik") or ""), "site"
        return self.uygulama_adi(oturum.get("uygulama") or ""), "uygulama"


def zaman_cizelgesi(depo, adlandirici: "Adlandirici", gun: date) -> dict:
    """Bir günün saat saat şeridi için oturum parçaları (gece yarısını geçenler o güne kırpılır).

    Her parça: başlangıç/bitiş (günün başından itibaren dakika), geçerli hüküm, okunabilir ad.
    GİZLİLİK: pencere/sekme başlığı DÖNMEZ; yalnızca uygulama/site adı.
    """
    from heatmap.depo import gun_araligi  # döngüsel içe aktarmayı önlemek için burada

    gun_bas, gun_bit = gun_araligi(gun)
    parcalar = []
    toplamlar = {"ders": 0.0, "ders_degil": 0.0, "belirsiz": 0.0}
    for o in reversed(depo.oturumlari_getir(gun_bas, gun_bit)):  # eskiden yeniye
        bas, bit = max(o["baslangic"], gun_bas), min(o["bitis"], gun_bit)
        if bit - bas < 1:
            continue  # 1 saniyeden kısa parçalar çizilmez
        hukum = o["duzeltme"] or o["hukum"]
        if o["kaynak"] == "bosta":
            ad, tur = "Bilgisayar başında değil", "bosta"
        elif o["kaynak"] in ("pencere", "baslik"):
            ad, tur = adlandirici.etiket(o)
        else:
            ad, tur = adlandirici.uygulama_adi(o["uygulama"] or ""), "uygulama"
        parcalar.append({
            "id": o["id"],
            "bas_dk": round((bas - gun_bas) / 60, 2),
            "bit_dk": round((bit - gun_bas) / 60, 2),
            "sure_sn": round(bit - bas),
            "hukum": hukum,
            "ad": ad,
            "tur": tur,
            "duzeltildi": bool(o["duzeltme"]),
        })
        toplamlar[hukum] = toplamlar.get(hukum, 0.0) + (bit - bas)
    return {
        "tarih": gun.isoformat(),
        "parcalar": parcalar,
        "toplam_sn": {k: round(v) for k, v in toplamlar.items()},
    }


def seri_hesapla(depo, hedef_sn: int, bugun: date) -> int:
    """Günlük hedefe üst üste kaç gündür ulaşıldığını sayar.

    Bugün hedefe henüz ulaşılmadıysa seri bozulmuş sayılmaz (gün daha bitmedi);
    dünden geriye doğru sayılır.
    """
    if hedef_sn <= 0:
        return 0
    # Son bir yılı tek sorguda al, sonra bugünden geriye doğru say.
    gunler = depo.gunluk_sureler(bugun - timedelta(days=365), bugun)
    seri = 0
    for sira, gun in enumerate(reversed(gunler)):
        if gun["ders_sn"] >= hedef_sn:
            seri += 1
        elif sira != 0:  # sira 0 = bugün; bugün henüz bitmedi, seriyi bozmaz
            break
    return seri


def en_uzun_seri(gunler: list[dict], hedef_sn: int) -> int:
    """Verilen gün listesinde hedefe üst üste ulaşılan en uzun gün sayısı."""
    if hedef_sn <= 0:
        return 0
    en_uzun = simdiki = 0
    for gun in gunler:
        simdiki = simdiki + 1 if gun["ders_sn"] >= hedef_sn else 0
        en_uzun = max(en_uzun, simdiki)
    return en_uzun


def seviye(sure_sn: int, hedef_sn: int) -> int:
    """Isı haritasındaki renk koyuluğu: 0 (hiç) ... 4 (hedef tuttu).

    Hedef varsa seviyeler hedefe göre: 1 = hedefin üçte birinden az,
    2 = üçte ikisinden az, 3 = hedefe yakın, 4 = hedef tuttu.
    Hedef yoksa sabit eşikler: 30 dk, 1 sa, 2 sa.
    """
    if sure_sn <= 0:
        return 0
    if hedef_sn > 0:
        oran = sure_sn / hedef_sn
        return 1 if oran < 1 / 3 else 2 if oran < 2 / 3 else 3 if oran < 1 else 4
    return 1 if sure_sn < 1800 else 2 if sure_sn < 3600 else 3 if sure_sn < 7200 else 4


def isi_haritasi(depo, hedef_sn: int, bugun: date, hafta_sayisi: int = 53) -> dict:
    """GitHub katkı grafiği gibi ısı haritası verisi.

    Izgara Pazartesi'den başlayan `hafta_sayisi` haftadan oluşur ve bugünün haftasıyla
    biter. Her gün: tarih, süre, seviye (0-4); bugünden sonraki günler `gelecek=True`.
    """
    bu_pazartesi = bugun - timedelta(days=bugun.weekday())
    ilk_gun = bu_pazartesi - timedelta(weeks=hafta_sayisi - 1)
    son_gun = bu_pazartesi + timedelta(days=6)
    gecmis = depo.gunluk_sureler(ilk_gun, bugun)

    gunler = []
    for kayit in gecmis:
        gunler.append({**kayit, "seviye": seviye(kayit["ders_sn"], hedef_sn), "gelecek": False})
    gun = bugun + timedelta(days=1)
    while gun <= son_gun:  # Bu haftanın kalan günleri (ızgara tam olsun diye)
        gunler.append({"tarih": gun.isoformat(), "ders_sn": 0, "seviye": 0, "gelecek": True})
        gun += timedelta(days=1)

    aktif = [g for g in gecmis if g["ders_sn"] > 0]
    toplam = sum(g["ders_sn"] for g in gecmis)
    return {
        "baslangic": ilk_gun.isoformat(),
        "bitis": son_gun.isoformat(),
        "hedef_sn": hedef_sn,
        "gunler": gunler,
        "toplam_sn": toplam,
        "aktif_gun": len(aktif),
        "hedef_gunu": sum(1 for g in gecmis if hedef_sn and g["ders_sn"] >= hedef_sn),
        "en_uzun_seri": en_uzun_seri(gecmis, hedef_sn),
        "simdiki_seri": seri_hesapla(depo, hedef_sn, bugun),
        "aktif_gun_ortalamasi_sn": round(toplam / len(aktif)) if aktif else 0,
    }


def verimli_saatler(depo, bugun: date, gun_sayisi: int = 30) -> dict:
    """Son `gun_sayisi` günde hangi saatlerde daha çok çalışıldığını çıkarır (0..23)."""
    ilk_gun = bugun - timedelta(days=max(0, gun_sayisi - 1))
    saatler = depo.saatlik_dagilim(ilk_gun, bugun)
    toplam = sum(s["ders_sn"] for s in saatler)
    en_cok = max((s["ders_sn"] for s in saatler), default=0)

    for s in saatler:
        s["oran"] = round(s["ders_sn"] / en_cok, 3) if en_cok else 0.0

    en_verimli_saat = max(saatler, key=lambda s: s["ders_sn"])["saat"] if en_cok > 0 else None

    # Günün 4 zaman diliminden hangisinde daha çok çalışma var?
    dilimler = [
        ("Sabah (06:00–12:00)", range(6, 12)),
        ("Öğleden sonra (12:00–18:00)", range(12, 18)),
        ("Akşam (18:00–22:00)", range(18, 22)),
        ("Gece (22:00–06:00)", [22, 23, 0, 1, 2, 3, 4, 5]),
    ]
    dilim_toplamlari = [(ad, sum(saatler[h]["ders_sn"] for h in aral)) for ad, aral in dilimler]
    en_iyi_dilim = max(dilim_toplamlari, key=lambda d: d[1])[0] if toplam > 0 else None

    return {
        "gun_sayisi": gun_sayisi,
        "baslangic": ilk_gun.isoformat(),
        "bitis": bugun.isoformat(),
        "toplam_sn": toplam,
        "en_verimli_saat": en_verimli_saat,
        "en_verimli_dilim": en_iyi_dilim,
        "saatler": saatler,
    }
