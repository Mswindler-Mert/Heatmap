"""Zinciri Kırma: hedef halkaları, sürükle-tak / otomatik tak, kalkan ve bronz kurtarma.

Barış Özcan'ın "Zinciri Kırma" yaklaşımından esinlenir:
  * Günlük hedefine ulaştığında o gün için parlak bir "tam" halka kazanırsın.
    `otomatik_tak = false` ise halka seni bekler; sürükleyip (veya tıklayıp) zincire
    takarsın. `otomatik_tak = true` ise hedefe ulaştığın an kendiliğinden takılır.
  * Yoğun/hasta günlerde ana hedefe ulaşamasan bile `kurtarma_dk` (varsayılan 30 dk)
    çalışırsan bronz bir "kurtarma" halkası takarak zincirin kopmasını önleyebilirsin.
    (Aynı gün sonradan ana hedefe ulaşırsan halka "tam" halkaya yükselir.)
  * Üst üste her 7 "tam" halka, 1 adet gümüş "kalkan" halkası kazandırır (en fazla 2
    tane birikir). Dün zinciri kaçırdıysan ve kalkan hakkın varsa dünü kalkanla kapatıp
    zinciri kurtarabilirsin.

Zaman dışarıdan `bugun: date` olarak verilir; böylece testler beklemeden her senaryoyu dener.
"""

from datetime import date, timedelta

from heatmap.ozet import GUN_ADLARI

KALKAN_ICIN_TAM_GUN = 7   # Üst üste kaç "tam" halka 1 kalkan kazandırır
EN_FAZLA_KALKAN = 2       # Aynı anda biriktirilebilecek en fazla kalkan sayısı

KILOMETRE_TASLARI = [
    (60, "efsane", "Efsane Zincir", 100),
    (30, "altin", "Altın Zincir", 60),
    (14, "gumus", "Gümüş Zincir", 30),
    (7, "turkuaz", "Haftalık Zincir", 14),
    (0, "zumrut", "Başlangıç", 7),
]


def kilometre_tasi(uzunluk: int) -> dict:
    """Zincir uzunluğuna göre kademe (renk/unvan) ve sıradaki hedef kilometre taşı."""
    for esik, kod, ad, sonraki in KILOMETRE_TASLARI:
        if uzunluk >= esik:
            if uzunluk >= 100:
                sonraki = 365
            return {"kod": kod, "ad": ad, "sonraki": sonraki, "kalan": max(0, sonraki - uzunluk)}
    return {"kod": "zumrut", "ad": "Başlangıç", "sonraki": 7, "kalan": 7}


def _gun_halkalari_hesapla(gunler: list[dict], kayitli: dict[str, str],
                           hedef_sn: int, kurtarma_sn: int, otomatik_tak: bool,
                           bugun_str: str) -> tuple[list[dict], str | None]:
    """Her günün geçerli halka türünü ve bugün için takılmayı bekleyen halkayı çıkarır."""
    sonuc = []
    bekleyen_halka: str | None = None

    for g in gunler:
        tarih = g["tarih"]
        sn = g["ders_sn"]
        kayit = kayitli.get(tarih)
        tur: str | None = None

        if tarih == bugun_str:
            if hedef_sn > 0 and sn >= hedef_sn:
                if otomatik_tak or kayit == "tam":
                    tur = "tam"
                else:
                    # Kullanıcı henüz tam halkayı takmadı (önceden bronz taktıysa o görünür, yükseltme bekler)
                    tur = "kurtarma" if kayit == "kurtarma" else None
                    bekleyen_halka = "tam"
            elif kurtarma_sn > 0 and sn >= kurtarma_sn:
                if kayit == "kurtarma":
                    tur = "kurtarma"
                else:
                    bekleyen_halka = "kurtarma"
            elif kayit == "kalkan":
                tur = "kalkan"
        else:
            # Geçmiş günler: ana hedef tuttuysa her zaman "tam"; yoksa kaydedilmiş kurtarma/kalkan geçerli.
            if hedef_sn > 0 and sn >= hedef_sn:
                tur = "tam"
            elif kayit == "kalkan":
                tur = "kalkan"
            elif kayit == "kurtarma" and (kurtarma_sn <= 0 or sn >= kurtarma_sn):
                tur = "kurtarma"

        sonuc.append({"tarih": tarih, "ders_sn": sn, "tur": tur})

    return sonuc, bekleyen_halka


def _kalkan_hesapla(gun_durumlari: list[dict]) -> tuple[int, int, int]:
    """(kalkan_hakki, kullanilan_kalkan, sonraki_kalkana_kalan) döndürür.

    Üst üste her 7 'tam' halka 1 kalkan kazandırır; en fazla EN_FAZLA_KALKAN birikir.
    """
    kazanilan = 0
    blok = 0
    for g in gun_durumlari:
        if g["tur"] == "tam":
            blok += 1
        else:
            kazanilan += blok // KALKAN_ICIN_TAM_GUN
            blok = 0
    kazanilan += blok // KALKAN_ICIN_TAM_GUN

    kullanilan = sum(1 for g in gun_durumlari if g["tur"] == "kalkan")
    hak = max(0, min(EN_FAZLA_KALKAN, kazanilan - kullanilan))

    # Mevcut tam halka bloğu (bugün henüz bitmediyse dünden geriye say)
    mevcut_tam = 0
    for sira, g in enumerate(reversed(gun_durumlari)):
        if g["tur"] == "tam":
            mevcut_tam += 1
        elif sira == 0:
            continue
        else:
            break
    kalan = KALKAN_ICIN_TAM_GUN - (mevcut_tam % KALKAN_ICIN_TAM_GUN)
    return hak, kullanilan, kalan


def zincir_durumu(depo, hedef_sn: int, kurtarma_sn: int, otomatik_tak: bool,
                  bugun: date, gorunen_gun: int = 14) -> dict:
    """Zinciri Kırma ekranı için eksiksiz durum özeti."""
    ilk_gun = bugun - timedelta(days=365)
    gunler = depo.gunluk_sureler(ilk_gun, bugun)
    kayitli = depo.zincir_halkalari_getir(ilk_gun, bugun)
    bugun_str = bugun.isoformat()

    durumlar, bekleyen_halka = _gun_halkalari_hesapla(
        gunler, kayitli, hedef_sn, kurtarma_sn, otomatik_tak, bugun_str
    )

    # Mevcut zincir uzunluğu (bugün henüz takılmadıysa/bitmediyse dünden geriye say)
    zincir_uzunlugu = 0
    for sira, g in enumerate(reversed(durumlar)):
        if g["tur"] is not None:
            zincir_uzunlugu += 1
        elif sira == 0:
            continue
        else:
            break

    # Son 1 yıldaki en uzun kesintisiz zincir
    en_uzun = simdiki = 0
    for g in durumlar:
        simdiki = simdiki + 1 if g["tur"] is not None else 0
        en_uzun = max(en_uzun, simdiki)

    kalkan_hakki, kullanilan_kalkan, sonraki_kalkana_kalan = _kalkan_hesapla(durumlar)

    # Dün boşsa, evvelsi gün halkalıysa ve kalkan hakkı varsa dün kalkanla kurtarılabilir.
    kalkan_tarihi: str | None = None
    if len(durumlar) >= 3 and kalkan_hakki > 0:
        dun_durum = durumlar[-2]
        onceki_durum = durumlar[-3]
        if dun_durum["tur"] is None and onceki_durum["tur"] is not None:
            kalkan_tarihi = dun_durum["tarih"]

    # Arayüzde çizilecek son N günün halkaları
    son_gunler = durumlar[-gorunen_gun:]
    halkalar = []
    for g in son_gunler:
        d = date.fromisoformat(g["tarih"])
        halkalar.append({
            "tarih": g["tarih"],
            "gun_adi": GUN_ADLARI[d.weekday()],
            "gun_no": d.day,
            "bugun": g["tarih"] == bugun_str,
            "ders_sn": g["ders_sn"],
            "tur": g["tur"],
            "bekliyor": bekleyen_halka if g["tarih"] == bugun_str else None,
            "kalkan_adayi": g["tarih"] == kalkan_tarihi,
        })

    return {
        "hedef_sn": hedef_sn,
        "kurtarma_sn": kurtarma_sn,
        "otomatik_tak": otomatik_tak,
        "zincir_uzunlugu": zincir_uzunlugu,
        "en_uzun_zincir": en_uzun,
        "kilometre_tasi": kilometre_tasi(zincir_uzunlugu),
        "bekleyen_halka": bekleyen_halka,        # 'tam' | 'kurtarma' | None (bugün için)
        "kalkan_hakki": kalkan_hakki,
        "en_fazla_kalkan": EN_FAZLA_KALKAN,
        "kullanilan_kalkan": kullanilan_kalkan,
        "sonraki_kalkana_kalan": sonraki_kalkana_kalan,
        "kalkan_kullanilabilir_tarih": kalkan_tarihi,
        "halkalar": halkalar,
    }


def halka_tak_dogrula(durum: dict, tarih: date, tur: str, bugun: date) -> str | None:
    """Halka takma isteği geçerliyse None, değilse kullanıcıya gösterilecek hata mesajı döner."""
    tarih_str = tarih.isoformat()
    if tur == "tam":
        if tarih != bugun:
            return "Tam halka yalnızca bugün için takılabilir."
        if durum["bekleyen_halka"] != "tam":
            bugun_halka = durum["halkalar"][-1] if durum["halkalar"] else {}
            if bugun_halka.get("tur") == "tam":
                return "Bugünün halkası zaten takılı."
            return "Tam halka için önce günlük hedefe ulaşmalısın."
        return None
    if tur == "kurtarma":
        if tarih != bugun:
            return "Kurtarma halkası yalnızca bugün için takılabilir."
        if durum["bekleyen_halka"] not in ("kurtarma", "tam"):
            return "Bronz kurtarma halkası için gereken en az süreye henüz ulaşılmadı."
        return None
    if tur == "kalkan":
        if durum["kalkan_kullanilabilir_tarih"] != tarih_str:
            return "Bu gün için kullanılabilir kalkan halkası yok."
        return None
    return "Geçersiz halka türü."
