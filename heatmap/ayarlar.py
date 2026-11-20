"""Ayar dosyasını (config/config.toml) okur.

İki dosya var:
  - config/config.ornek.toml : GitHub'a giden varsayılan ayarlar.
  - config/config.toml       : Senin kişisel ayarların (.gitignore'da).

Önce örnek dosya okunur, sonra kişisel dosyadaki değerler onun üzerine
yazılır. Böylece kişisel dosyanda bir ayar eksik olsa bile program çökmez.
"""

import shutil
import tomllib  # TOML okuyucu, Python 3.11'den beri standart kütüphanede
from pathlib import Path

# Proje kök klasörü: bu dosyanın (heatmap/ayarlar.py) iki üstü.
KOK = Path(__file__).resolve().parent.parent
CONFIG_KLASORU = KOK / "config"
VERI_KLASORU = KOK / "data"

ORNEK_DOSYA = CONFIG_KLASORU / "config.ornek.toml"
KISISEL_DOSYA = CONFIG_KLASORU / "config.toml"


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


def ayarlari_yukle() -> dict:
    """Ayarları iç içe sözlük olarak döndürür. Örn: ayarlar["tolerans"]["durdurma_sn"]"""
    # İlk çalıştırmada kişisel ayar dosyası yoksa örnekten kopyala.
    if not KISISEL_DOSYA.exists():
        shutil.copyfile(ORNEK_DOSYA, KISISEL_DOSYA)

    varsayilan = _toml_oku(ORNEK_DOSYA)
    kisisel = _toml_oku(KISISEL_DOSYA)
    return _ustune_yaz(varsayilan, kisisel)
