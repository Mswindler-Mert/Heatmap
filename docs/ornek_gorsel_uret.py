"""README'deki örnek kart görselini (docs/ornek-kartlar.png) üretir.

Tamamen UYDURMA veriyle çalışır: geçici bir veritabanına rastgele (ama tekrarlanabilir)
oturumlar yazar, dört kart türünü çizer ve yan yana tek bir resimde birleştirir.
Gerçek verine dokunmaz.

Çalıştırma (proje klasöründe):
    .venv\\Scripts\\python docs\\ornek_gorsel_uret.py
"""

import io
import os
import random
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from PIL import Image  # noqa: E402

from heatmap.depo import Depo  # noqa: E402
from heatmap.kart import kart_ciz, kart_verisi  # noqa: E402
from heatmap.motor import Durum  # noqa: E402
from heatmap.ozet import Adlandirici  # noqa: E402

BUGUN = date(2026, 11, 21)   # Sabit tarih: görsel her üretimde aynı çıksın
ORNEK = [  # (süreç, kaynak, başlık, site)
    ("Code.exe", "pencere", "", ""),
    ("brave.exe", "baslik", "", "youtube.com"),
    ("claude.exe", "pencere", "", ""),
    ("POWERPNT.EXE", "pencere", "", ""),
    ("brave.exe", "baslik", "", "github.com"),
    ("ms-teams.exe", "pencere", "", ""),
]


def ornek_depo() -> Depo:
    depo = Depo(os.path.join(tempfile.mkdtemp(), "ornek.db"))
    rastgele = random.Random(3)
    for gun_once in range(0, 380):
        gun = BUGUN - timedelta(days=gun_once)
        if rastgele.random() < 0.22:
            continue  # boş gün
        bas = datetime.combine(gun, datetime.min.time()).timestamp() + 9 * 3600
        for _ in range(rastgele.randint(1, 6)):
            surec, kaynak, baslik, site = rastgele.choice(ORNEK)
            sure = rastgele.choice([900, 1800, 2700, 3600])
            oid = depo.oturum_baslat(Durum("ders", surec, kaynak, "", surec, baslik, site), bas)
            depo.oturum_bitisini_guncelle(oid, bas + sure)
            bas += sure + 300
    return depo


def main() -> None:
    depo = ornek_depo()
    adlandirici = Adlandirici({
        "adlar": {"Code.exe": "VS Code", "claude.exe": "Claude", "POWERPNT.EXE": "PowerPoint", "ms-teams.exe": "Teams"},
        "siteler": {"YouTube": ["youtube.com"], "GitHub": ["github.com"]},
    })
    genislik, yukseklik, bosluk = 405, 720, 24
    birlesik = Image.new("RGB", (4 * genislik + 3 * bosluk, yukseklik), (13, 17, 23))
    for sira, tur in enumerate(("gunluk", "haftalik", "aylik", "yillik")):
        png = kart_ciz(kart_verisi(depo, adlandirici, 7200, tur, BUGUN, BUGUN))
        kart = Image.open(io.BytesIO(png)).convert("RGB").resize((genislik, yukseklik), Image.LANCZOS)
        birlesik.paste(kart, (sira * (genislik + bosluk), 0))
    cikti = KOK / "docs" / "ornek-kartlar.png"
    birlesik.save(cikti, optimize=True)
    print(f"{cikti} ({cikti.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
