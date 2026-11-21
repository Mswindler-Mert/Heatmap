"""Paylaşım kartı: özeti 1080x1920 (Instagram hikâyesi) PNG olarak çizer.

Dört kart türü var:
    gunluk   : bir gün; haftanın 7 günü çubuk grafik
    haftalik : bir hafta; aynı çubuk grafik
    aylik    : bir ay; takvim biçiminde ısı haritası
    yillik   : son 12 ay; her satır bir ay, her kare bir gün (ısı haritası)

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

YERLEŞİM: Instagram hikâyede üstteki ~250 ve alttaki ~250 pikseli kendi
düğmeleriyle örter. Bu yüzden bütün içerik GUVENLI_UST..GUVENLI_ALT
arasına yerleştirildi; o bantların dışında yalnızca zemin ve küçük imza var.
"""

import calendar
import io
import os
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from heatmap.depo import Depo, gun_araligi
from heatmap.ozet import GUN_ADLARI, Adlandirici, en_uzun_seri, seri_hesapla, seviye

GENISLIK, YUKSEKLIK = 1080, 1920
KENAR = 84                     # Sağ/sol boşluk
GUVENLI_UST, GUVENLI_ALT = 250, 1670
EN_COK_KAC_UYGULAMA = 4
KART_TURLERI = ("gunluk", "haftalik", "aylik", "yillik")

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
UZUN_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
TUR_ETIKETI = {"gunluk": "GÜNLÜK ÖZET", "haftalik": "HAFTALIK ÖZET",
               "aylik": "AYLIK ÖZET", "yillik": "YILLIK ÖZET"}

# Renkler (R, G, B) ve ısı haritası seviyeleri (0 = hiç ... 4 = hedef tuttu)
YAZI = (236, 238, 244)
SOLUK = (139, 147, 167)
YESIL = (62, 207, 142)
MAVI = (106, 165, 255)
SEVIYE_RENGI = {0: (255, 255, 255, 18), 1: YESIL + (70,), 2: YESIL + (125,), 3: YESIL + (190,), 4: YESIL + (255,)}

# Bölümlerin dikey konumları (piksel). Hepsi güvenli alan içinde.
Y_UST = 262          # logo ve kart türü
Y_TARIH = 316
Y_SURE_ETIKET = 410
Y_SURE_TABAN = 598   # büyük rakamların taban çizgisi
Y_MOTIVASYON = 628
Y_KUTU = (720, 860)
Y_BOLUM = 905        # orta bölümün başlığı (gün gün / takvim / son 12 ay)
Y_LISTE_BASLIK = 1300
Y_LISTE = 1350
LISTE_ADIMI = 74


# =====================================================================
#  1. Veri
# =====================================================================
def _gunlere_seviye_ekle(gunler: list[dict], hedef_sn: int, bugun: date) -> list[dict]:
    """depo.gunluk_sureler() çıktısına seviye ve "gelecek" bilgisi ekler."""
    return [{
        "tarih": g["tarih"],
        "sure_sn": g["ders_sn"],
        "seviye": seviye(g["ders_sn"], hedef_sn),
        "gelecek": date.fromisoformat(g["tarih"]) > bugun,
    } for g in gunler]


def _araligi_belirle(tur: str, tarih: date) -> tuple[date, date]:
    """Kart türüne göre kapsanan ilk ve son gün."""
    if tur == "gunluk":
        return tarih, tarih
    if tur == "haftalik":
        pazartesi = tarih - timedelta(days=tarih.weekday())
        return pazartesi, pazartesi + timedelta(days=6)
    if tur == "aylik":
        son_gun = calendar.monthrange(tarih.year, tarih.month)[1]
        return tarih.replace(day=1), tarih.replace(day=son_gun)
    # yillik: tarihin ayı ve ondan önceki 11 ay
    ay_index = tarih.year * 12 + tarih.month - 1 - 11
    ilk = date(ay_index // 12, ay_index % 12 + 1, 1)
    son_gun = calendar.monthrange(tarih.year, tarih.month)[1]
    return ilk, tarih.replace(day=son_gun)


def _tarih_metni(tur: str, ilk: date, son: date, tarih: date) -> str:
    if tur == "gunluk":
        return f"{tarih.day} {AYLAR[tarih.month - 1]} {tarih.year}, {UZUN_GUNLER[tarih.weekday()]}"
    if tur == "aylik":
        return f"{AYLAR[tarih.month - 1]} {tarih.year}"
    if tur == "yillik":
        return f"{AYLAR[ilk.month - 1]} {ilk.year} – {AYLAR[son.month - 1]} {son.year}"
    if ilk.month == son.month:
        return f"{ilk.day}–{son.day} {AYLAR[son.month - 1]} {son.year}"
    return f"{ilk.day} {AYLAR[ilk.month - 1]} – {son.day} {AYLAR[son.month - 1]} {son.year}"


def kart_verisi(depo: Depo, adlandirici: Adlandirici, hedef_sn: int, tur: str,
                tarih: date, bugun: date | None = None, uygulamalari_goster: bool = True) -> dict:
    """Kartta görünecek bütün bilgiyi toplar.

    tur   : "gunluk", "haftalik", "aylik" ya da "yillik"
    tarih : kartın ait olduğu gün (geçmiş bir gün de olabilir)
    bugun : gerçek bugün; bundan sonraki günler "henüz gelmedi" diye boş çizilir
    uygulamalari_goster: False ise kartta "en çok zaman geçenler" listesi hiç yer almaz
                         (yalnızca süreyi paylaşmak isteyenler için; veride de bulunmaz)
    """
    if tur not in KART_TURLERI:
        raise ValueError(f"Bilinmeyen kart türü: {tur}")
    bugun = bugun or date.today()
    ilk, son = _araligi_belirle(tur, tarih)
    gecmis_son = min(son, bugun)  # Sayılabilecek son gün

    # Uygulama/site dökümü (yalnızca okunabilir adlar; bkz. GİZLİLİK notu)
    bas, _ = gun_araligi(ilk)
    _, bit = gun_araligi(max(ilk, gecmis_son))
    dokum = depo.uygulama_dokumu(bas, bit, adlandirici.etiket) if ilk <= bugun else []
    toplam = sum(d["sure_sn"] for d in dokum)
    en_cok = [
        {"ad": d["ad"], "sure_sn": d["sure_sn"], "oran": d["sure_sn"] / toplam if toplam else 0}
        for d in dokum[:EN_COK_KAC_UYGULAMA]
    ]

    veri = {
        "tur": tur,
        "tarih_metni": _tarih_metni(tur, ilk, son, tarih),
        "toplam_sn": toplam,
        "uygulamalar": en_cok if uygulamalari_goster else [],
        "uygulamalar_gizli": not uygulamalari_goster,
        "seri_gun": seri_hesapla(depo, hedef_sn, min(tarih, bugun)),
        "hedef_sn": hedef_sn,
    }

    if tur in ("gunluk", "haftalik"):
        pazartesi = tarih - timedelta(days=tarih.weekday())
        hafta = depo.gunluk_sureler(pazartesi, pazartesi + timedelta(days=6))
        gunler = []
        for sira, gun in enumerate(hafta):
            gun_tarihi = pazartesi + timedelta(days=sira)
            gunler.append({
                "ad": GUN_ADLARI[sira],
                "sure_sn": gun["ders_sn"],
                # Günlük kartta yalnızca o gün, haftalık kartta geçmiş bütün günler vurgulanır.
                "vurgulu": gun_tarihi == tarih if tur == "gunluk" else gun_tarihi <= bugun,
            })
        gecen = [g for sira, g in enumerate(gunler) if pazartesi + timedelta(days=sira) <= bugun]
        hafta_toplam = sum(g["sure_sn"] for g in gunler)
        en_iyi = max(gunler, key=lambda g: g["sure_sn"])
        veri.update({
            "gunler": gunler,
            "hafta_toplam_sn": hafta_toplam,
            "gunluk_ortalama_sn": round(hafta_toplam / len(gecen)) if gecen else 0,
            "en_iyi_gun": en_iyi["ad"] if en_iyi["sure_sn"] else "",
            "en_iyi_gun_sn": en_iyi["sure_sn"],
            "hedefe_ulasilan_gun": sum(1 for g in gunler if hedef_sn and g["sure_sn"] >= hedef_sn),
        })
        return veri

    # aylik / yillik: günlük ısı haritası
    gunler = _gunlere_seviye_ekle(depo.gunluk_sureler(ilk, son), hedef_sn, bugun)
    gecmis = [{"ders_sn": g["sure_sn"]} for g in gunler if not g["gelecek"]]
    aktif = sum(1 for g in gecmis if g["ders_sn"] > 0)
    veri.update({
        "aktif_gun": aktif,
        "gecen_gun": len(gecmis),
        "hedefe_ulasilan_gun": sum(1 for g in gecmis if hedef_sn and g["ders_sn"] >= hedef_sn),
        "en_uzun_seri": en_uzun_seri(gecmis, hedef_sn),
        "gunluk_ortalama_sn": round(toplam / len(gecmis)) if gecmis else 0,
    })
    if tur == "aylik":
        veri["takvim"] = {"ilk_hafta_gunu": ilk.weekday(), "secili_gun": tarih.day,
                          "gunler": [{**g, "gun": i + 1} for i, g in enumerate(gunler)]}
    else:
        aylar: list[dict] = []
        for g in gunler:  # Günleri aylara grupla: her ay kartta bir satır
            ay = int(g["tarih"][5:7])
            if not aylar or aylar[-1]["ay"] != ay:
                aylar.append({"ay": ay, "ad": AY_KISA[ay - 1], "gunler": []})
            aylar[-1]["gunler"].append(g)
        veri["aylar"] = aylar
    return veri


def _motivasyon(veri: dict) -> str:
    """Büyük sürenin altındaki tek satırlık cümle."""
    tur = veri["tur"]
    if veri["toplam_sn"] == 0:
        return "Yeni bir başlangıç için güzel bir gün." if tur == "gunluk" else "Bu dönemde henüz kayıt yok."
    if veri["seri_gun"] >= 2:
        return f"{veri['seri_gun']} gündür üst üste hedefte."
    if tur == "gunluk":
        if veri["hedef_sn"] and veri["toplam_sn"] >= veri["hedef_sn"]:
            return "Günlük hedef tamam."
    elif tur == "haftalik" and veri["hedefe_ulasilan_gun"]:
        return f"Bu hafta {veri['hedefe_ulasilan_gun']} gün hedefe ulaşıldı."
    elif tur == "aylik":
        return f"Bu ay {veri['aktif_gun']} gün aktif, {veri['hedefe_ulasilan_gun']} gün hedefte."
    elif tur == "yillik":
        return f"Son 12 ayda {veri['aktif_gun']} aktif gün."
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
    k.ellipse((-70, 10, 170, 250), fill=YESIL + (70,))       # sol üst: yeşil
    k.ellipse((150, 280, 380, 500), fill=MAVI + (38,))       # sağ alt: mavi
    kucuk = kucuk.filter(ImageFilter.GaussianBlur(55))
    parilti = kucuk.resize((GENISLIK, YUKSEKLIK), Image.BILINEAR)
    return Image.alpha_composite(zemin.convert("RGBA"), parilti).convert("RGB")


# =====================================================================
#  3. Kartın bölümleri
# =====================================================================
def _ust_bolum(c, veri: dict) -> None:
    # Küçük logo (tepsi ikonundaki halka) + uygulama adı
    c.ellipse((KENAR, Y_UST, KENAR + 34, Y_UST + 34), fill=YESIL)
    c.ellipse((KENAR + 10, Y_UST + 10, KENAR + 24, Y_UST + 24), fill=(13, 16, 22))
    _aralikli_yazi(c, KENAR + 50, Y_UST - 1, "HEATMAP", _yazi(27, "yari"), YAZI, aralik=5)

    etiket = TUR_ETIKETI[veri["tur"]]
    yazi = _yazi(25, "yari")
    genislik = sum(c.textlength(h, font=yazi) + 5 for h in etiket) - 5
    _aralikli_yazi(c, GENISLIK - KENAR - genislik, Y_UST + 1, etiket, yazi, SOLUK, aralik=5)

    c.text((KENAR, Y_TARIH), veri["tarih_metni"], font=_yazi(42, "yari"), fill=YAZI)


def _buyuk_sure(c, veri: dict) -> None:
    """Kartın kahramanı: dev rakamlarla toplam aktif süre."""
    _aralikli_yazi(c, KENAR, Y_SURE_ETIKET, "AKTİF SÜRE", _yazi(30, "yari"), YESIL, aralik=7)

    dakika = veri["toplam_sn"] // 60
    saat = dakika // 60
    parcalar = []  # (metin, yazı tipi, renk)
    rakam, birim = _yazi(176, "kalin"), _yazi(62, "yari")
    if saat:
        parcalar += [(str(saat), rakam, YAZI), (" sa  ", birim, SOLUK)]
    if saat < 100:  # 100 saati geçince dakika gösterilmez (yıllık kartta sığsın diye)
        parcalar += [(str(dakika % 60), rakam, YAZI), (" dk", birim, SOLUK)]

    x = KENAR - 6
    for metin, yazi, renk in parcalar:
        # anchor="ls": verilen nokta yazının SOL-TABAN çizgisidir; böylece büyük
        # rakamlarla küçük birimler aynı hizaya oturur.
        c.text((x, Y_SURE_TABAN), metin, font=yazi, fill=renk, anchor="ls")
        x += c.textlength(metin, font=yazi)

    c.text((KENAR, Y_MOTIVASYON), _motivasyon(veri), font=_yazi(38, "yari"), fill=YAZI)


def _kutucuklar(c, veri: dict) -> None:
    """Üç küçük istatistik kutusu; içerik kart türüne göre değişir."""
    tur, hedef = veri["tur"], veri["hedef_sn"]
    seri = (f"{veri['seri_gun']} gün" if veri["seri_gun"] else "—", "SERİ")
    if tur == "gunluk":
        yuzde = f"%{min(999, round(veri['toplam_sn'] / hedef * 100))}" if hedef else "—"
        kutular = [seri, (yuzde, "GÜNLÜK HEDEF"), (_sure_metni(veri["hafta_toplam_sn"]), "BU HAFTA")]
    elif tur == "haftalik":
        en_iyi = f"{veri['en_iyi_gun']} · {_kisa_sure(veri['en_iyi_gun_sn'])}" if veri["en_iyi_gun"] else "—"
        kutular = [seri, (_sure_metni(veri["gunluk_ortalama_sn"]), "GÜNLÜK ORT."), (en_iyi, "EN İYİ GÜN")]
    elif tur == "aylik":
        kutular = [seri, (f"{veri['aktif_gun']}/{veri['gecen_gun']}", "AKTİF GÜN"),
                   (_sure_metni(veri["gunluk_ortalama_sn"]), "GÜNLÜK ORT.")]
    else:
        kutular = [seri, (f"{veri['aktif_gun']} gün", "AKTİF GÜN"),
                   (f"{veri['en_uzun_seri']} gün" if veri["en_uzun_seri"] else "—", "EN UZUN SERİ")]

    bosluk = 20
    en = (GENISLIK - 2 * KENAR - 2 * bosluk) / 3
    ust, alt = Y_KUTU
    for sira, (deger, etiket) in enumerate(kutular):
        sol = KENAR + sira * (en + bosluk)
        c.rounded_rectangle((sol, ust, sol + en, alt), radius=26,
                            fill=(255, 255, 255, 13), outline=(255, 255, 255, 26), width=2)
        deger_yazi = _yazi(44, "kalin")
        if c.textlength(deger, font=deger_yazi) > en - 44:  # Uzun değerler için küçült
            deger_yazi = _yazi(34, "kalin")
        c.text((sol + 24, ust + 60), deger, font=deger_yazi, fill=YAZI, anchor="ls")
        _aralikli_yazi(c, sol + 24, ust + 92, etiket, _yazi(21, "yari"), SOLUK, aralik=3)


def _gun_grafigi(c, veri: dict) -> None:
    """Haftanın yedi günü için çubuk grafik + kesikli hedef çizgisi (günlük/haftalık kart)."""
    _aralikli_yazi(c, KENAR, Y_BOLUM, "GÜN GÜN", _yazi(27, "yari"), SOLUK, aralik=6)

    taban, en_yuksek = 1210, 200          # Çubukların oturduğu y ve en uzun çubuğun boyu
    hedef = veri["hedef_sn"]
    olcek = max([g["sure_sn"] for g in veri["gunler"]] + [hedef, 1800])
    dilim = (GENISLIK - 2 * KENAR) / 7
    cubuk_eni = 80

    if hedef:  # Hedef çizgisi (kesikli)
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
        c.text((orta, taban - boy - 12), _kisa_sure(gun["sure_sn"]), font=_yazi(25, "yari"),
               fill=YAZI if gun["vurgulu"] else SOLUK, anchor="ms")
        c.text((orta, taban + 18), gun["ad"], font=_yazi(27, "yari" if gun["vurgulu"] else "normal"),
               fill=YAZI if gun["vurgulu"] else SOLUK, anchor="mt")


def _ay_takvimi(c, veri: dict) -> None:
    """Aylık kart: takvim; her gün bir kutu, renk koyuluğu o günün süresi."""
    _aralikli_yazi(c, KENAR, Y_BOLUM, "AYIN GÜNLERİ", _yazi(27, "yari"), SOLUK, aralik=6)
    takvim = veri["takvim"]
    satir_sayisi = (takvim["ilk_hafta_gunu"] + len(takvim["gunler"]) + 6) // 7
    adim_x = (GENISLIK - 2 * KENAR) / 7
    ust, alt = 990, 1262
    adim_y = min(56, (alt - ust) / satir_sayisi)

    for sira, ad in enumerate(GUN_ADLARI):  # Gün adları başlığı
        c.text((KENAR + adim_x * sira + adim_x / 2, 952), ad, font=_yazi(22), fill=SOLUK, anchor="mt")

    for g in takvim["gunler"]:
        konum = takvim["ilk_hafta_gunu"] + g["gun"] - 1
        x = KENAR + adim_x * (konum % 7)
        y = ust + adim_y * (konum // 7)
        kutu = (x + 4, y + 3, x + adim_x - 4, y + adim_y - 3)
        if g["gelecek"]:
            c.rounded_rectangle(kutu, radius=10, outline=(255, 255, 255, 22), width=2)
        else:
            c.rounded_rectangle(kutu, radius=10, fill=SEVIYE_RENGI[g["seviye"]])
        if g["gun"] == takvim["secili_gun"]:
            c.rounded_rectangle(kutu, radius=10, outline=YAZI, width=3)
        koyu_zemin = g["seviye"] >= 3 and not g["gelecek"]
        c.text((x + 16, y + 9), str(g["gun"]), font=_yazi(21, "yari"),
               fill=(10, 30, 20) if koyu_zemin else SOLUK)


def _yil_haritasi(c, veri: dict) -> None:
    """Yıllık kart: her satır bir ay, her kare o ayın bir günü."""
    _aralikli_yazi(c, KENAR, Y_BOLUM, "SON 12 AY", _yazi(27, "yari"), SOLUK, aralik=6)
    etiket_eni = 64
    adim_x = (GENISLIK - 2 * KENAR - etiket_eni) / 31
    ust, adim_y = 952, 26
    for sira, ay in enumerate(veri["aylar"]):
        y = ust + sira * adim_y
        c.text((KENAR, y + adim_y / 2), ay["ad"], font=_yazi(20, "yari"), fill=SOLUK, anchor="lm")
        for i, g in enumerate(ay["gunler"]):
            x = KENAR + etiket_eni + i * adim_x
            kutu = (x + 2, y + 2, x + adim_x - 2, y + adim_y - 2)
            if g["gelecek"]:
                c.rounded_rectangle(kutu, radius=4, outline=(255, 255, 255, 22), width=1)
            else:
                c.rounded_rectangle(kutu, radius=4, fill=SEVIYE_RENGI[g["seviye"]])

    # Lejant: Az [] [] [] [] [] Hedef
    y = ust + 12 * adim_y + 6
    x = GENISLIK - KENAR
    c.text((x, y + 10), "hedef", font=_yazi(19), fill=SOLUK, anchor="rm")
    x -= c.textlength("hedef", font=_yazi(19)) + 10
    for s in (4, 3, 2, 1, 0):
        c.rounded_rectangle((x - 18, y + 1, x, y + 19), radius=4, fill=SEVIYE_RENGI[s])
        x -= 24
    c.text((x - 4, y + 10), "az", font=_yazi(19), fill=SOLUK, anchor="rm")


def _uygulama_listesi(c, veri: dict) -> None:
    """En çok zaman geçen uygulamalar/siteler: ad, süre, yüzde ve ince bir çubuk."""
    _aralikli_yazi(c, KENAR, Y_LISTE_BASLIK, "EN ÇOK ZAMAN GEÇENLER", _yazi(27, "yari"), SOLUK, aralik=6)

    if not veri["uygulamalar"]:
        c.text((KENAR, Y_LISTE + 10), "Bu aralıkta kayıt yok.", font=_yazi(34), fill=SOLUK)
        return

    en_buyuk = veri["uygulamalar"][0]["oran"] or 1
    sag = GENISLIK - KENAR
    y = Y_LISTE
    for u in veri["uygulamalar"]:
        ad_yazi = _yazi(36, "yari")
        c.text((KENAR, y), _sigdir(c, u["ad"], ad_yazi, 500), font=ad_yazi, fill=YAZI)
        c.text((sag, y), f"%{round(u['oran'] * 100)}", font=_yazi(36, "kalin"), fill=YAZI, anchor="ra")
        c.text((sag - 120, y + 7), _sure_metni(u["sure_sn"]), font=_yazi(28), fill=SOLUK, anchor="ra")
        # Çubuk: önce soluk ray, üstüne orantılı dolgu
        c.rounded_rectangle((KENAR, y + 54, sag, y + 63), radius=5, fill=(255, 255, 255, 20))
        dolgu = max(10, (sag - KENAR) * u["oran"] / en_buyuk)
        c.rounded_rectangle((KENAR, y + 54, KENAR + dolgu, y + 63), radius=5, fill=YESIL)
        y += LISTE_ADIMI


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
    if veri["tur"] == "aylik":
        _ay_takvimi(c, veri)
    elif veri["tur"] == "yillik":
        _yil_haritasi(c, veri)
    else:
        _gun_grafigi(c, veri)
    if not veri.get("uygulamalar_gizli"):
        _uygulama_listesi(c, veri)
    # İmza güvenli alanın dışında: Instagram örterse sorun değil.
    c.text((GENISLIK / 2, YUKSEKLIK - 60), "heatmap  ·  otomatik çalışma takibi",
           font=_yazi(24), fill=(139, 147, 167, 150), anchor="ms")

    tampon = io.BytesIO()  # Diske yazmadan, bellekte PNG oluştur
    resim.save(tampon, format="PNG")
    return tampon.getvalue()
