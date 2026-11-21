"""Ayarları arayüzden düzenleme: hangi ayarlar düzenlenebilir, nasıl doğrulanır, dosyaya nasıl yazılır.

Arayüzdeki "Ayarlar" bölümü bu dosyadaki ALANLAR listesinden OTOMATİK oluşturulur; yeni bir
ayarı arayüze eklemek için listeye bir satır eklemek yeterli.

Dosyaya yazarken `tomlkit` kullanılır: config.toml'daki yorumlar, boş satırlar ve düzen korunur.
Listelerde (örn. ders_surecleri) yalnızca çıkarılan öğeler silinir, yeniler sona eklenir; kalan
öğelerin yanındaki yorumlar ("Code.exe",  # VS Code) yerinde kalır.

Kaydetmeden önce eski dosyanın kopyası data/yedek/config-YYYYAAGG-SSDDss.toml olarak saklanır.
"""

import shutil
from datetime import datetime
from pathlib import Path

# Grup adı -> o gruptaki alanlar. Her alan:
#   anahtar  : "bolum.ayar" (config.toml'daki yeri)
#   tur      : tamsayi | metin | liste | secim | evet_hayir
#   etiket   : arayüzde görünen ad;  aciklama: kısa yardım metni
#   en_az / en_cok (tamsayi), en_uzun (metin), secenekler (secim: [(değer, görünen ad), ...])
ALANLAR: list[dict] = [
    # --- Hedef ve süreler ---
    {"grup": "Hedef ve süreler", "anahtar": "hedef.gunluk_dk", "tur": "tamsayi", "etiket": "Günlük hedef",
     "birim": "dk", "en_az": 0, "en_cok": 1440, "aciklama": "Seri ve kartlardaki hedef. 0 = hedef yok."},
    {"grup": "Hedef ve süreler", "anahtar": "tolerans.baslatma_sn", "tur": "tamsayi", "etiket": "Sayacın başlaması",
     "birim": "sn", "en_az": 0, "en_cok": 600, "aciklama": "Çalışma bu kadar kesintisiz sürünce sayaç başlar."},
    {"grup": "Hedef ve süreler", "anahtar": "tolerans.durdurma_sn", "tur": "tamsayi", "etiket": "Sayacın durması",
     "birim": "sn", "en_az": 1, "en_cok": 3600, "aciklama": "Çalışmadan bu kadar uzun ayrılınca sayaç durur."},
    {"grup": "Hedef ve süreler", "anahtar": "bosta.esik_sn", "tur": "tamsayi", "etiket": "Boşta kalma eşiği",
     "birim": "sn", "en_az": 10, "en_cok": 7200, "aciklama": "Klavye/fare bu kadar kullanılmazsa 'başında değil'."},
    {"grup": "Hedef ve süreler", "anahtar": "bosta.video_esik_sn", "tur": "tamsayi", "etiket": "Video izlerken eşik",
     "birim": "sn", "en_az": 60, "en_cok": 21600, "aciklama": "Video izlerken boşta kalmaya izin verilen süre."},

    # --- Uygulamalar ---
    {"grup": "Uygulamalar", "anahtar": "pencere.ders_surecleri", "tur": "liste", "etiket": "Çalışma uygulamaları",
     "aciklama": "Her satıra bir süreç adı (Görev Yöneticisi > Ayrıntılar), örn. Code.exe"},
    {"grup": "Uygulamalar", "anahtar": "pencere.ders_degil_surecleri", "tur": "liste",
     "etiket": "Çalışma dışı uygulamalar", "aciklama": "Her satıra bir süreç adı, örn. steam.exe"},
    {"grup": "Uygulamalar", "anahtar": "pencere.tarayici_surecleri", "tur": "liste", "etiket": "Tarayıcılar",
     "aciklama": "Bunlarda karar sekme başlığına (ve eklenti varsa siteye) göre verilir."},
    {"grup": "Uygulamalar", "anahtar": "pencere.bilinmeyen_hukum", "tur": "secim",
     "etiket": "Listede olmayan uygulama",
     "secenekler": [("belirsiz", "Belirsiz (sonra ben karar veririm)"), ("ders_degil", "Çalışma değil")],
     "aciklama": "Hiçbir listede olmayan uygulamalar nasıl sayılsın."},

    # --- Tarayıcı ve siteler ---
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.ders_kelimeleri", "tur": "liste",
     "etiket": "Çalışma kelimeleri", "aciklama": "Sekme başlığında geçerse çalışma (tam kelime), örn. Lecture"},
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.ders_degil_kelimeleri", "tur": "liste",
     "etiket": "Çalışma dışı kelimeler", "aciklama": "Sekme başlığında geçerse çalışma değil, örn. Gameplay"},
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.ders_alanlari", "tur": "liste", "etiket": "Çalışma siteleri",
     "aciklama": "Eklenti kuruluysa: bu sitelerdeki her şey çalışma, örn. github.com"},
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.ders_degil_alanlari", "tur": "liste",
     "etiket": "Çalışma dışı siteler", "aciklama": "Eklenti kuruluysa: bu siteler hiçbir zaman çalışma değil."},
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.video_isaretleri", "tur": "liste", "etiket": "Video siteleri",
     "aciklama": "Eklenti yoksa: başlıkta bunlar geçerse 'video izleniyor' sayılır."},
    {"grup": "Tarayıcı ve siteler", "anahtar": "baslik.yok_sayilan_basliklar", "tur": "liste",
     "etiket": "Yok sayılan sekmeler", "aciklama": "Bunlara bakmak sayacı etkilemez. 'Takip Paneli'ni silme."},

    # --- Öğrenen tahmin ---
    {"grup": "Öğrenen tahmin", "anahtar": "tahmin.etkin", "tur": "evet_hayir", "etiket": "Tahmin önerileri",
     "aciklama": "Karar bekleyen başlıklar için 'Tahmin: çalışma %87' önerisi göster."},
    {"grup": "Öğrenen tahmin", "anahtar": "tahmin.otomatik_karar", "tur": "evet_hayir",
     "etiket": "Tahmin karar versin",
     "aciklama": "Açıksa, kuralların karar veremediği başlıklarda yeterince emin tahmin karar verir."},
    {"grup": "Öğrenen tahmin", "anahtar": "tahmin.esik_yuzde", "tur": "tamsayi", "etiket": "Güven eşiği",
     "birim": "%", "en_az": 50, "en_cok": 99, "aciklama": "Otomatik karar için model en az bu kadar emin olmalı."},

    # --- Diğer ---
    {"grup": "Diğer", "anahtar": "kart.ust_metin", "tur": "metin", "etiket": "Kartın üst yazısı", "en_uzun": 22,
     "aciklama": "Paylaşım kartının sol üstünde görünür (örn. adın)."},
    {"grup": "Diğer", "anahtar": "yedek.saklanacak_gun", "tur": "tamsayi", "etiket": "Saklanacak yedek",
     "birim": "gün", "en_az": 1, "en_cok": 365, "aciklama": "Günlük veritabanı yedeklerinden kaç tanesi tutulsun."},
    {"grup": "Diğer", "anahtar": "genel.acilista_arayuzu_ac", "tur": "evet_hayir",
     "etiket": "Açılışta arayüzü aç", "aciklama": "Elle başlatınca tarayıcıda bu sayfa açılsın."},
    {"grup": "Diğer", "anahtar": "tarayici.etkin", "tur": "evet_hayir", "etiket": "Tarayıcı eklentisi modülü",
     "aciklama": "Eklentiden gelen site adını ve ses bilgisini kullan."},
    {"grup": "Diğer", "anahtar": "kamera.etkin", "tur": "evet_hayir", "etiket": "Kamera modülü",
     "aciklama": "Deneysel; önce kamera_isci/README.md'deki kurulum gerekir."},
]
ALAN = {a["anahtar"]: a for a in ALANLAR}
LISTE_EN_FAZLA = 500       # Bir listede en fazla bu kadar öğe
OGE_EN_UZUN = 200          # Liste öğesi en fazla bu kadar karakter
SAKLANACAK_AYAR_YEDEGI = 10


class AyarDosyasiHatasi(Exception):
    """config.toml okunamıyor (yazım hatası); arayüzden kaydetmeden önce elle düzeltilmeli."""


def deger_al(ayarlar: dict, anahtar: str):
    bolum, ad = anahtar.split(".", 1)
    return ayarlar.get(bolum, {}).get(ad)


def alanlar_ve_degerler(ayarlar: dict) -> list[dict]:
    """Arayüz için: gruplara ayrılmış alanlar ve şu anki değerleri."""
    gruplar: dict[str, list] = {}
    for alan in ALANLAR:
        kopya = {k: v for k, v in alan.items() if k != "grup"}
        if "secenekler" in kopya:
            kopya["secenekler"] = [{"deger": d, "ad": ad} for d, ad in kopya["secenekler"]]
        kopya["deger"] = deger_al(ayarlar, alan["anahtar"])
        gruplar.setdefault(alan["grup"], []).append(kopya)
    return [{"ad": ad, "alanlar": alanlar} for ad, alanlar in gruplar.items()]


def _tek_degeri_dogrula(alan: dict, deger):
    """(temiz değer, hata mesajı) döndürür; hata yoksa mesaj None."""
    tur = alan["tur"]
    if tur == "tamsayi":
        if isinstance(deger, bool) or not isinstance(deger, (int, float)) or int(deger) != deger:
            return None, "Tam sayı olmalı."
        deger = int(deger)
        if not alan["en_az"] <= deger <= alan["en_cok"]:
            return None, f"{alan['en_az']} ile {alan['en_cok']} arasında olmalı."
        return deger, None
    if tur == "evet_hayir":
        return (deger, None) if isinstance(deger, bool) else (None, "Açık ya da kapalı olmalı.")
    if tur == "secim":
        gecerli = [d for d, _ in alan["secenekler"]]
        return (deger, None) if deger in gecerli else (None, "Listedeki seçeneklerden biri olmalı.")
    if tur == "metin":
        if not isinstance(deger, str):
            return None, "Metin olmalı."
        deger = deger.strip()
        if not deger:
            return None, "Boş olamaz."
        if len(deger) > alan["en_uzun"]:
            return None, f"En fazla {alan['en_uzun']} karakter."
        return deger, None
    if tur == "liste":
        if not isinstance(deger, list) or not all(isinstance(o, str) for o in deger):
            return None, "Metin listesi olmalı."
        temiz, gorulen = [], set()
        for oge in (o.strip() for o in deger):
            if not oge or oge.lower() in gorulen:  # Boş satırları ve tekrarları at
                continue
            if len(oge) > OGE_EN_UZUN:
                return None, f"Bir öğe en fazla {OGE_EN_UZUN} karakter olabilir."
            gorulen.add(oge.lower())
            temiz.append(oge)
        if len(temiz) > LISTE_EN_FAZLA:
            return None, f"En fazla {LISTE_EN_FAZLA} öğe."
        return temiz, None
    return None, "Bilinmeyen alan türü."


def dogrula(degisiklikler: dict) -> tuple[dict, dict]:
    """(temiz değişiklikler, hatalar) döndürür. Hatalar: {anahtar: mesaj}."""
    temiz, hatalar = {}, {}
    for anahtar, deger in degisiklikler.items():
        alan = ALAN.get(anahtar)
        if alan is None:
            hatalar[anahtar] = "Bu ayar arayüzden değiştirilemez."
            continue
        sonuc, hata = _tek_degeri_dogrula(alan, deger)
        if hata:
            hatalar[anahtar] = hata
        else:
            temiz[anahtar] = sonuc
    return temiz, hatalar


def _listeyi_guncelle(dizi, yeni: list[str]) -> None:
    """tomlkit dizisini yerinde günceller: çıkanları sil, yenileri sona ekle (yorumlar korunur)."""
    yeni_kucuk = {o.lower() for o in yeni}
    for i in reversed(range(len(dizi))):
        if str(dizi[i]).lower() not in yeni_kucuk:
            del dizi[i]
    mevcut = {str(o).lower() for o in dizi}
    for oge in yeni:
        if oge.lower() not in mevcut:
            dizi.append(oge)


def _tomlkit():
    """tomlkit'i yalnızca gerektiğinde yükler: paket kurulu değilse program yine açılır,
    sadece arayüzden kaydetme açıklayıcı bir hata verir."""
    try:
        import tomlkit
    except ImportError as hata:
        raise AyarDosyasiHatasi("Ayarları kaydetmek için 'tomlkit' paketi gerekli; "
                                "baslat.bat'ı çalıştırınca kendiliğinden kurulur.") from hata
    return tomlkit


def _yeni_dizi(degerler: list[str]):
    tomlkit = _tomlkit()
    dizi = tomlkit.array()
    dizi.extend(degerler)
    if len(degerler) > 3:
        dizi.multiline(True)  # Uzun listeler her öğe ayrı satırda yazılsın
    return dizi


def dosyaya_yaz(dosya: Path, degisiklikler: dict, yedek_klasoru: Path | None = None) -> None:
    """Doğrulanmış değişiklikleri config.toml'a yorumları koruyarak yazar.

    Dosya okunamıyorsa (yazım hatası) AyarDosyasiHatasi verir ve HİÇBİR ŞEY yazmaz.
    """
    tomlkit = _tomlkit()
    dosya = Path(dosya)
    metin = dosya.read_text(encoding="utf-8") if dosya.exists() else ""
    try:
        belge = tomlkit.parse(metin)
    except tomlkit.exceptions.ParseError as hata:
        raise AyarDosyasiHatasi(f"{dosya.name} okunamıyor ({hata}); önce dosyadaki yazım hatasını düzelt.") from hata

    for anahtar, deger in degisiklikler.items():
        bolum, ad = anahtar.split(".", 1)
        if bolum not in belge:
            belge.add(tomlkit.nl())
            belge.add(bolum, tomlkit.table())
        tablo = belge[bolum]
        if isinstance(deger, list):
            if ad in tablo and isinstance(tablo[ad], list):
                _listeyi_guncelle(tablo[ad], deger)
            else:
                tablo[ad] = _yeni_dizi(deger)
        else:
            tablo[ad] = deger  # tomlkit satırın yanındaki yorumu korur

    if yedek_klasoru is not None and dosya.exists():
        _yedekle(dosya, Path(yedek_klasoru))
    gecici = dosya.with_suffix(".toml.yaziliyor")
    gecici.write_text(tomlkit.dumps(belge), encoding="utf-8", newline="\n")
    gecici.replace(dosya)  # Yarıda kesilirse eski dosya bozulmadan kalır


def _yedekle(dosya: Path, yedek_klasoru: Path) -> Path:
    yedek_klasoru.mkdir(parents=True, exist_ok=True)
    hedef = yedek_klasoru / f"config-{datetime.now():%Y%m%d-%H%M%S}.toml"
    shutil.copyfile(dosya, hedef)
    # En yeni SAKLANACAK_AYAR_YEDEGI dışındakileri sil (yalnızca config-*.toml dosyaları)
    for eski in sorted(yedek_klasoru.glob("config-*.toml"), reverse=True)[SAKLANACAK_AYAR_YEDEGI:]:
        eski.unlink(missing_ok=True)
    return hedef


def degisenleri_bul(ayarlar: dict, temiz: dict) -> dict:
    """Yalnızca şu anki değerden FARKLI olanları döndürür (dosyaya gereksiz satır yazılmasın)."""
    return {k: v for k, v in temiz.items() if deger_al(ayarlar, k) != v}
