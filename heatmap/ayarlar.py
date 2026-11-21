"""Ayar dosyasını (config/config.toml) okur.

İki dosya var:
  - config/config.ornek.toml : GitHub'a giden varsayılan ayarlar.
  - config/config.toml       : Senin kişisel ayarların (.gitignore'da).

Önce örnek dosya okunur, sonra kişisel dosyadaki değerler onun üzerine
yazılır. Böylece kişisel dosyanda bir ayar eksik olsa bile program çökmez.

Kişisel dosyada yazım hatası (örn. unutulmuş tırnak) ya da yanlış türde bir
değer (örn. sayı yerine metin) varsa program yine AÇILIR: hatalı kısım yerine
varsayılan kullanılır ve sorun ayarlar["_uyarilar"] listesine yazılır.
Arayüz bu uyarıları sayfanın üstünde gösterir.
"""

import shutil
import sys
import tomllib  # TOML okuyucu, Python 3.11'den beri standart kütüphanede
from pathlib import Path


def kok_klasorleri(donmus: bool | None = None, exe: str | None = None, paket_ici: str | None = None):
    """(KAYNAK_KOK, KOK) döndürür.

    KAYNAK_KOK: programla gelen, SALT OKUNUR dosyalar (örnek ayar dosyası, arayüz dosyaları).
    KOK       : kullanıcıya ait, YAZILABİLİR klasör (config/config.toml, data/).

    Normal çalışmada ikisi de proje klasörüdür. Tek dosya .exe olarak (PyInstaller) çalışırken
    program her açılışta geçici bir klasöre açılır: kaynaklar oradadır (sys._MEIPASS), ama ayar ve
    veriler orada kaybolurdu; bu yüzden onlar .exe'nin yanındaki klasöre yazılır.
    (Parametreler testler içindir.)
    """
    donmus = getattr(sys, "frozen", False) if donmus is None else donmus
    if donmus:
        exe_klasoru = Path(exe or sys.executable).resolve().parent
        return Path(paket_ici or getattr(sys, "_MEIPASS", exe_klasoru)), exe_klasoru
    proje = Path(__file__).resolve().parent.parent  # bu dosyanın (heatmap/ayarlar.py) iki üstü
    return proje, proje


PAKETLI = bool(getattr(sys, "frozen", False))  # Tek dosya .exe olarak mı çalışıyoruz?
KAYNAK_KOK, KOK = kok_klasorleri()
CONFIG_KLASORU = KOK / "config"
VERI_KLASORU = KOK / "data"

ORNEK_DOSYA = KAYNAK_KOK / "config" / "config.ornek.toml"
KISISEL_DOSYA = CONFIG_KLASORU / "config.toml"

UYARILAR = "_uyarilar"  # Ayar sözlüğünde uyarı listesinin anahtarı


def _toml_oku(yol: Path) -> dict:
    with open(yol, "rb") as dosya:  # tomllib dosyayı "binary" modda ister
        return tomllib.load(dosya)


def _ustune_yaz(temel: dict, ek: dict) -> dict:
    """`ek` sözlüğündeki değerleri `temel`in üzerine yazar (iç içe sözlükler dahil)."""
    sonuc = dict(temel)
    for anahtar, deger in ek.items():
        if isinstance(deger, dict) and isinstance(sonuc.get(anahtar), dict):
            sonuc[anahtar] = _ustune_yaz(sonuc[anahtar], deger)
        else:
            sonuc[anahtar] = deger
    return sonuc


def _tur_adi(deger) -> str:
    if isinstance(deger, bool):
        return "true/false"
    if isinstance(deger, (int, float)):
        return "sayı"
    if isinstance(deger, str):
        return "tırnak içinde metin"
    if isinstance(deger, list):
        return "liste [...]"
    if isinstance(deger, dict):
        return "bölüm"
    return type(deger).__name__


def _ayni_tur_mu(varsayilan, deger) -> bool:
    """Kişisel değer, varsayılanla aynı türden mi? (int ve float ikisi de "sayı" sayılır.)"""
    if isinstance(varsayilan, bool) or isinstance(deger, bool):
        return isinstance(varsayilan, bool) and isinstance(deger, bool)
    if isinstance(varsayilan, (int, float)):
        return isinstance(deger, (int, float))
    return isinstance(deger, type(varsayilan))


def _turleri_dogrula(varsayilan: dict, kisisel: dict, uyarilar: list[str], yol: str = "") -> dict:
    """Kişisel ayarlarda türü yanlış olan değerleri atar (yerine varsayılan kalır) ve uyarı ekler.

    Yalnızca örnek dosyada da bulunan ayarlar denetlenir; [adlar] gibi bölümlere senin
    eklediğin yeni anahtarlar olduğu gibi kalır.
    """
    temiz = {}
    for anahtar, deger in kisisel.items():
        if anahtar not in varsayilan:
            temiz[anahtar] = deger
            continue
        beklenen = varsayilan[anahtar]
        konum = f"{yol}.{anahtar}" if yol else anahtar
        if isinstance(beklenen, dict) and isinstance(deger, dict):
            temiz[anahtar] = _turleri_dogrula(beklenen, deger, uyarilar, konum)
        elif _ayni_tur_mu(beklenen, deger):
            temiz[anahtar] = deger
        else:
            uyarilar.append(f"'{konum}' {_tur_adi(beklenen)} olmalı ama {_tur_adi(deger)} yazılmış; "
                            f"varsayılan ({beklenen!r}) kullanılıyor.")
    return temiz


def ayarlari_yukle(ornek: Path = ORNEK_DOSYA, kisisel_dosya: Path = KISISEL_DOSYA) -> dict:
    """Ayarları iç içe sözlük olarak döndürür. Örn: ayarlar["tolerans"]["durdurma_sn"]

    Sorun varsa ayarlar["_uyarilar"] boş olmayan bir listedir.
    """
    # İlk çalıştırmada kişisel ayar dosyası yoksa örnekten kopyala.
    if not kisisel_dosya.exists():
        kisisel_dosya.parent.mkdir(parents=True, exist_ok=True)  # .exe'nin yanında config/ henüz yoksa
        shutil.copyfile(ornek, kisisel_dosya)

    varsayilan = _toml_oku(ornek)
    uyarilar: list[str] = []
    try:
        kisisel = _toml_oku(kisisel_dosya)
    except tomllib.TOMLDecodeError as hata:
        # Hata mesajı satır ve sütunu içerir: "... (at line 12, column 5)"
        uyarilar.append(f"{kisisel_dosya.name} okunamadı, bu yüzden TÜM ayarlar varsayılan: {hata}. "
                        f"Dosyayı düzeltip Heatmap'i yeniden başlat.")
        kisisel = {}
    except (OSError, UnicodeDecodeError) as hata:
        uyarilar.append(f"{kisisel_dosya.name} açılamadı ({hata}); varsayılan ayarlar kullanılıyor.")
        kisisel = {}

    ayarlar = _ustune_yaz(varsayilan, _turleri_dogrula(varsayilan, kisisel, uyarilar))
    ayarlar[UYARILAR] = uyarilar
    return ayarlar
