"""Verini CSV dosyası olarak dışa aktarma (Excel, Google E-Tablolar vb. için).

Dosyalar Türkçe Excel'de çift tıklayınca doğru açılsın diye:
  - Ayraç noktalı virgül (;)  -> Türkçe Excel virgülü ondalık işareti sayar
  - UTF-8 BOM ile başlar     -> Excel Türkçe karakterleri doğru gösterir
  - Sayılar tam sayıdır      -> ondalık nokta/virgül karışıklığı olmaz

GİZLİLİK: Oturum dosyasında pencere/sekme başlıkları VARSAYILAN OLARAK YOKTUR
(dosya başkasıyla paylaşılabilir). İstenirse `basliklar=True` ile eklenir.
"""

import csv
import io
from datetime import date, datetime

from heatmap.depo import Depo, gun_araligi
from heatmap.ozet import Adlandirici

_BOM = "﻿"


def _csv_metni(basliklar: list[str], satirlar: list[list]) -> str:
    tampon = io.StringIO()
    yazici = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    yazici.writerow(basliklar)
    yazici.writerows(satirlar)
    return _BOM + tampon.getvalue()


def _bos_degilse(deger):
    return "" if deger is None else deger


def gunluk_csv(depo: Depo, ilk_gun: date, son_gun: date) -> str:
    """Her gün bir satır: çalışma dakikası ve (varsa) sağlık verisi."""
    satirlar = [
        [g["tarih"], round(g["ders_sn"] / 60), _bos_degilse(g["adim"]),
         _bos_degilse(g["egzersiz_dk"]), _bos_degilse(g["uyku_dk"])]
        for g in depo.gunluk_birlesik(ilk_gun, son_gun)
    ]
    return _csv_metni(["tarih", "calisma_dk", "adim", "egzersiz_dk", "uyku_dk"], satirlar)


def oturumlar_csv(depo: Depo, adlandirici: Adlandirici, ilk_gun: date, son_gun: date,
                  basliklar: bool = False) -> str:
    """Her oturum bir satır, eskiden yeniye. Uygulama/site okunabilir adıyla yazılır."""
    bas, _ = gun_araligi(ilk_gun)
    _, bit = gun_araligi(son_gun)
    sutunlar = ["baslangic", "bitis", "sure_sn", "hukum", "duzeltildi", "uygulama", "site", "kaynak"]
    if basliklar:
        sutunlar.append("pencere_basligi")

    satirlar = []
    for o in reversed(depo.oturumlari_getir(bas, bit)):  # oturumlari_getir yeniden eskiye verir
        ad, tur = adlandirici.etiket(o) if o["kaynak"] in ("pencere", "baslik") else ("", "")
        satir = [
            datetime.fromtimestamp(o["baslangic"]).isoformat(sep=" ", timespec="seconds"),
            datetime.fromtimestamp(o["bitis"]).isoformat(sep=" ", timespec="seconds"),
            round(o["bitis"] - o["baslangic"]),
            o["duzeltme"] or o["hukum"],
            "evet" if o["duzeltme"] else "",
            ad if tur == "uygulama" else (o["uygulama"] or ""),
            ad if tur == "site" else "",
            o["kaynak"] or "",
        ]
        if basliklar:
            satir.append(o["baslik"] or "")
        satirlar.append(satir)
    return _csv_metni(sutunlar, satirlar)
