"""Paylaşım kartı: günlük/haftalık özeti 1080x1920 (Instagram hikâyesi) PNG olarak çizer.

İki adım var:
    kart_verisi(...) -> kartta görünecek HER ŞEYİ içeren sade bir sözlük
    kart_ciz(veri)   -> o sözlükten PNG üretir

--------------------------------------------------------------------
GİZLİLİK: Kart başkalarıyla paylaşılır. Bu yüzden kart_verisi() içine
pencere başlığı, sekme başlığı ya da video adı ASLA girmez. Uygulama ve
site adları yalnızca Adlandirici.etiket() üzerinden gelir; o da sadece
ayar dosyasındaki adları döndürür. kart_ciz() veritabanına hiç erişmez,
yani veride olmayan bir şeyi çizmesi mümkün değildir.
(tests/test_kart.py bunu kontrol eder.)
--------------------------------------------------------------------
"""

import io
import os
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from heatmap.depo import Depo, gun_araligi
from heatmap.ozet import GUN_ADLARI, Adlandirici, seri_hesapla

GENISLIK, YUKSEKLIK = 1080, 1920
KENAR = 84                     # Sağ/sol boşluk
EN_COK_KAC_UYGULAMA = 5

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
UZUN_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Renkler (R, G, B)
YAZI = (236, 238, 244)
SOLUK = (139, 147, 167)
YESIL = (62, 207, 142)
MAVI = (106, 165, 255)


# =====================================================================
#  1. Veri
# =====================================================================
def _tarih_metni(tur: str, bugun: date, pazartesi: date) -> str:
    if tur == "gunluk":
        return f"{bugun.day} {AYLAR[bugun.month - 1]} {bugun.year}, {UZUN_GUNLER[bugun.weekday()]}"
    pazar = pazartesi + timedelta(days=6)
    if pazartesi.month == pazar.month:
        return f"{pazartesi.day}–{pazar.day} {AYLAR[pazar.month - 1]} {pazar.year}"
    return f"{pazartesi.day} {AYLAR[pazartesi.month - 1]} – {pazar.day} {AYLAR[pazar.month - 1]} {pazar.year}"


def kart_verisi(depo: Depo, adlandirici: Adlandirici, hedef_sn: int, tur: str, bugun: date) -> dict:
    """Kartta görünecek bütün bilgiyi toplar. `tur`: "gunluk" ya da "haftalik"."""
    pazartesi = bugun - timedelta(days=bugun.weekday())
    hafta = depo.gunluk_sureler(pazartesi, pazartesi + timedelta(days=6))

    if tur == "haftalik":
        ilk, son = pazartesi, pazartesi + timedelta(days=6)
    else:
        ilk = son = bugun
    bas, _ = gun_araligi(ilk)
    _, bit = gun_araligi(son)

    dokum = depo.uygulama_dokumu(bas, bit, adlandirici.etiket)
    toplam = sum(d["sure_sn"] for d in dokum)
    en_cok = [
        {"ad": d["ad"], "sure_sn": d["sure_sn"], "oran": d["sure_sn"] / toplam if toplam else 0}
        for d in dokum[:EN_COK_KAC_UYGULAMA]
    ]

    gunler = []
    for sira, gun in enumerate(hafta):
        gun_tarihi = pazartesi + timedelta(days=sira)
        gunler.append({
            "ad": GUN_ADLARI[sira],
            "sure_sn": gun["ders_sn"],
            # Günlük kartta yalnızca bugün, haftalık kartta bütün günler vurgulanır.
            "vurgulu": gun_tarihi == bugun if tur == "gunluk" else gun_tarihi <= bugun,
        })

    hafta_toplam = sum(g["sure_sn"] for g in gunler)
    gecen_gun_sayisi = bugun.weekday() + 1
    en_iyi = max(gunler, key=lambda g: g["sure_sn"])

    return {
        "tur": tur,
        "tarih_metni": _tarih_metni(tur, bugun, pazartesi),
        "toplam_sn": toplam,
        "gunler": gunler,
        "uygulamalar": en_cok,
        "seri_gun": seri_hesapla(depo, hedef_sn, bugun),
        "hedef_sn": hedef_sn,
        "hafta_toplam_sn": hafta_toplam,
        "gunluk_ortalama_sn": round(hafta_toplam / gecen_gun_sayisi),
        "en_iyi_gun": en_iyi["ad"] if en_iyi["sure_sn"] else "",
        "en_iyi_gun_sn": en_iyi["sure_sn"],
        "hedefe_ulasilan_gun": sum(1 for g in gunler if hedef_sn and g["sure_sn"] >= hedef_sn),
    }


def _motivasyon(veri: dict) -> str:
    """Kartın ortasındaki tek satırlık cümle."""
    if veri["toplam_sn"] == 0:
        return "Yeni bir başlangıç için güzel bir gün."
    if veri["seri_gun"] >= 2:
        return f"{veri['seri_gun']} gündür üst üste hedefte."
    if veri["tur"] == "gunluk":
        if veri["hedef_sn"] and veri["toplam_sn"] >= veri["hedef_sn"]:
            return "Günlük hedef tamam."
    elif veri["hedefe_ulasilan_gun"]:
        return f"Bu hafta {veri['hedefe_ulasilan_gun']} gün hedefe ulaşıldı."
    return "Her dakika sayılır."


# =====================================================================
#  2. Çizim yardımcıları
# =====================================================================
_YAZI_KLASORU = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
_YAZI_DOSYALARI = {"normal": "segoeui.ttf", "yari": "seguisb.ttf", "kalin": "segoeuib.ttf"}


@lru_cache(maxsize=None)
def _yazi(boyut: int, agirlik: str = "normal"):
    """Windows'un Segoe UI yazı tipini yükler; bulunamazsa Pillow'un varsayılanına döner."""
    try:
        return ImageFont.truetype(str(_YAZI_KLASORU / _YAZI_DOSYALARI[agirlik]), boyut)
    except OSError:
        return ImageFont.load_default(boyut)


def _sure_metni(sn: int) -> str:
    """5400 -> "1 sa 30 dk",  1500 -> "25 dk" """
    dakika = sn // 60
    if dakika < 60:
        return f"{dakika} dk"
    return f"{dakika // 60} sa {dakika % 60} dk" if dakika % 60 else f"{dakika // 60} sa"


def _kisa_sure(sn: int) -> str:
    """Grafik çubuklarının üstü için çok kısa biçim: "45dk", "2,5sa" """
    if sn < 60:
        return ""
    if sn < 3600:
        return f"{sn // 60}dk"
    return f"{sn / 3600:.1f}".replace(".", ",") + "sa"


def _aralikli_yazi(cizim, x: float, y: float, metin: str, yazi, renk, aralik: int = 6) -> None:
    """Harf aralığı açılmış küçük başlık yazısı (örn. "AKTİF SÜRE")."""
    for harf in metin:
        cizim.text((x, y), harf, font=yazi, fill=renk)
        x += cizim.textlength(harf, font=yazi) + aralik


def _sigdir(cizim, metin: str, yazi, en_fazla: float) -> str:
    """Metin `en_fazla` pikselden genişse sonunu "…" ile keser."""
    if cizim.textlength(metin, font=yazi) <= en_fazla:
        return metin
    while metin and cizim.textlength(metin + "…", font=yazi) > en_fazla:
        metin = metin[:-1]
    return metin.rstrip() + "…"


def _zemin() -> Image.Image:
    """Koyu geçişli zemin + köşelerde yumuşak renkli parıltılar."""
    zemin = Image.new("RGB", (GENISLIK, YUKSEKLIK))
    cizim = ImageDraw.Draw(zemin)
    ust, alt = (17, 22, 31), (9, 11, 15)
    for y in range(YUKSEKLIK):  # Yukarıdan aşağı satır satır renk geçişi
        oran = y / YUKSEKLIK
        cizim.line([(0, y), (GENISLIK, y)], fill=tuple(round(u + (a - u) * oran) for u, a in zip(ust, alt)))

    # Parıltıyı hız için 1/4 boyutta çizip bulanıklaştırıyor, sonra büyütüyoruz.
    kucuk = Image.new("RGBA", (GENISLIK // 4, YUKSEKLIK // 4), (0, 0, 0, 0))
    k = ImageDraw.Draw(kucuk)
    k.ellipse((-70, -40, 170, 200), fill=YESIL + (70,))      # sol üst: yeşil
    k.ellipse((150, 300, 380, 520), fill=MAVI + (38,))       # sağ alt: mavi
    kucuk = kucuk.filter(ImageFilter.GaussianBlur(55))
    parilti = kucuk.resize((GENISLIK, YUKSEKLIK), Image.BILINEAR)
    return Image.alpha_composite(zemin.convert("RGBA"), parilti).convert("RGB")


# =====================================================================
#  3. Kartın bölümleri
# =====================================================================
def _ust_bolum(c, veri: dict) -> None:
    # Küçük logo (tepsi ikonundaki halka) + uygulama adı
    c.ellipse((KENAR, 100, KENAR + 36, 136), fill=YESIL)
    c.ellipse((KENAR + 11, 111, KENAR + 25, 125), fill=(13, 16, 22))
    _aralikli_yazi(c, KENAR + 54, 100, "DERS TAKİP", _yazi(28, "yari"), YAZI, aralik=5)

    etiket = "GÜNLÜK ÖZET" if veri["tur"] == "gunluk" else "HAFTALIK ÖZET"
    yazi = _yazi(26, "yari")
    genislik = sum(c.textlength(h, font=yazi) + 5 for h in etiket)
    _aralikli_yazi(c, GENISLIK - KENAR - genislik, 102, etiket, yazi, SOLUK, aralik=5)

    c.text((KENAR, 196), veri["tarih_metni"], font=_yazi(44, "yari"), fill=YAZI)


def _buyuk_sure(c, veri: dict) -> None:
    """Kartın kahramanı: dev rakamlarla toplam aktif süre."""
    _aralikli_yazi(c, KENAR, 318, "AKTİF SÜRE", _yazi(30, "yari"), YESIL, aralik=7)

    dakika = veri["toplam_sn"] // 60
    parcalar = []  # (metin, yazı tipi, renk)
    rakam, birim = _yazi(196, "kalin"), _yazi(68, "yari")
    if dakika >= 60:
        parcalar += [(str(dakika // 60), rakam, YAZI), (" sa  ", birim, SOLUK)]
    parcalar += [(str(dakika % 60), rakam, YAZI), (" dk", birim, SOLUK)]

    x, taban = KENAR - 6, 548
    for metin, yazi, renk in parcalar:
        # anchor="ls": verilen nokta yazının SOL-TABAN çizgisidir; böylece büyük
        # rakamlarla küçük birimler aynı hizaya oturur.
        c.text((x, taban), metin, font=yazi, fill=renk, anchor="ls")
        x += c.textlength(metin, font=yazi)

    c.text((KENAR, 590), _motivasyon(veri), font=_yazi(42, "yari"), fill=YAZI)


def _kutucuklar(c, veri: dict) -> None:
    """Üç küçük istatistik kutusu."""
    hedef = veri["hedef_sn"]
    seri = (f"{veri['seri_gun']} gün" if veri["seri_gun"] else "—", "SERİ")
    if veri["tur"] == "gunluk":
        yuzde = f"%{min(999, round(veri['toplam_sn'] / hedef * 100))}" if hedef else "—"
        kutular = [seri, (yuzde, "GÜNLÜK HEDEF"), (_sure_metni(veri["hafta_toplam_sn"]), "BU HAFTA")]
    else:
        en_iyi = f"{veri['en_iyi_gun']} · {_kisa_sure(veri['en_iyi_gun_sn'])}" if veri["en_iyi_gun"] else "—"
        kutular = [seri, (_sure_metni(veri["gunluk_ortalama_sn"]), "GÜNLÜK ORT."), (en_iyi, "EN İYİ GÜN")]

    bosluk = 20
    en = (GENISLIK - 2 * KENAR - 2 * bosluk) / 3
    ust, alt = 690, 856
    for sira, (deger, etiket) in enumerate(kutular):
        sol = KENAR + sira * (en + bosluk)
        c.rounded_rectangle((sol, ust, sol + en, alt), radius=26,
                            fill=(255, 255, 255, 13), outline=(255, 255, 255, 26), width=2)
        deger_yazi = _yazi(46, "kalin")
        if c.textlength(deger, font=deger_yazi) > en - 44:  # Uzun değerler için küçült
            deger_yazi = _yazi(36, "kalin")
        c.text((sol + 24, ust + 62), deger, font=deger_yazi, fill=YAZI, anchor="ls")
        _aralikli_yazi(c, sol + 24, ust + 100, etiket, _yazi(22, "yari"), SOLUK, aralik=3)


def _gun_grafigi(c, veri: dict) -> None:
    """Haftanın yedi günü için çubuk grafik + kesikli hedef çizgisi."""
    _aralikli_yazi(c, KENAR, 930, "GÜN GÜN", _yazi(28, "yari"), SOLUK, aralik=6)

    taban, en_yuksek = 1270, 220          # Çubukların oturduğu y ve en uzun çubuğun boyu
    hedef = veri["hedef_sn"]
    olcek = max([g["sure_sn"] for g in veri["gunler"]] + [hedef, 1800])
    dilim = (GENISLIK - 2 * KENAR) / 7
    cubuk_eni = 82

    # Hedef çizgisi (kesikli)
    if hedef:
        y = taban - hedef / olcek * en_yuksek
        for x in range(KENAR, GENISLIK - KENAR, 22):
            c.line([(x, y), (x + 10, y)], fill=(255, 255, 255, 60), width=2)
        c.text((GENISLIK - KENAR, y - 8), "hedef", font=_yazi(22), fill=SOLUK, anchor="rs")

    for sira, gun in enumerate(veri["gunler"]):
        orta = KENAR + dilim * sira + dilim / 2
        boy = max(8, gun["sure_sn"] / olcek * en_yuksek)
        renk = YESIL if gun["vurgulu"] and gun["sure_sn"] else (255, 255, 255, 38)
        c.rounded_rectangle((orta - cubuk_eni / 2, taban - boy, orta + cubuk_eni / 2, taban),
                            radius=min(16, boy / 2), fill=renk)
        c.text((orta, taban - boy - 12), _kisa_sure(gun["sure_sn"]), font=_yazi(26, "yari"),
               fill=YAZI if gun["vurgulu"] else SOLUK, anchor="ms")
        c.text((orta, taban + 20), gun["ad"], font=_yazi(28, "yari" if gun["vurgulu"] else "normal"),
               fill=YAZI if gun["vurgulu"] else SOLUK, anchor="mt")


def _uygulama_listesi(c, veri: dict) -> None:
    """En çok zaman geçen uygulamalar/siteler: ad, süre, yüzde ve ince bir çubuk."""
    _aralikli_yazi(c, KENAR, 1384, "EN ÇOK ZAMAN GEÇENLER", _yazi(28, "yari"), SOLUK, aralik=6)

    if not veri["uygulamalar"]:
        c.text((KENAR, 1460), "Bu aralıkta kayıt yok.", font=_yazi(36), fill=SOLUK)
        return

    en_buyuk = veri["uygulamalar"][0]["oran"] or 1
    sag = GENISLIK - KENAR
    y = 1440
    for u in veri["uygulamalar"]:
        ad_yazi = _yazi(38, "yari")
        c.text((KENAR, y), _sigdir(c, u["ad"], ad_yazi, 500), font=ad_yazi, fill=YAZI)
        c.text((sag, y), f"%{round(u['oran'] * 100)}", font=_yazi(38, "kalin"), fill=YAZI, anchor="ra")
        c.text((sag - 130, y + 8), _sure_metni(u["sure_sn"]), font=_yazi(30), fill=SOLUK, anchor="ra")
        # Çubuk: önce soluk ray, üstüne orantılı dolgu
        c.rounded_rectangle((KENAR, y + 58, sag, y + 68), radius=5, fill=(255, 255, 255, 20))
        dolgu = max(10, (sag - KENAR) * u["oran"] / en_buyuk)
        c.rounded_rectangle((KENAR, y + 58, KENAR + dolgu, y + 68), radius=5, fill=YESIL)
        y += 78


# =====================================================================
#  4. Hepsini birleştir
# =====================================================================
def kart_ciz(veri: dict) -> bytes:
    """kart_verisi() çıktısından 1080x1920 PNG üretir ve dosya içeriğini (bytes) döndürür."""
    resim = _zemin()
    # "RGBA" modu: yarı saydam renklerle (4. sayı = saydamlık) çizim yapabilmek için.
    c = ImageDraw.Draw(resim, "RGBA")

    _ust_bolum(c, veri)
    _buyuk_sure(c, veri)
    _kutucuklar(c, veri)
    _gun_grafigi(c, veri)
    _uygulama_listesi(c, veri)
    c.text((GENISLIK / 2, YUKSEKLIK - 40), "ders-takip  ·  otomatik çalışma takibi",
           font=_yazi(24), fill=(139, 147, 167, 150), anchor="ms")

    tampon = io.BytesIO()  # Diske yazmadan, bellekte PNG oluştur
    resim.save(tampon, format="PNG")
    return tampon.getvalue()
