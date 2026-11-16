"""FastAPI uygulaması: JSON API + arayüz dosyaları.

Bütün veri uçları /api/ altında ve JSON döndürür. İleride Windows
dashboard'u ya da Health Connect birleştirmesi de aynı uçları okuyabilir.
Otomatik API dokümantasyonu: http://127.0.0.1:8765/api/docs
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ders_takip.depo import Depo, gun_araligi
from ders_takip.takipci import Takipci

STATIK_KLASOR = Path(__file__).parent / "static"
GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


# --- İstek gövdeleri (FastAPI gelen JSON'u bu kalıplara göre doğrular) ---
class DuzeltmeIstegi(BaseModel):
    hukum: Literal["ders", "ders_degil"]
    ogren: bool = True                 # Bu uygulama/başlık için kalıcı kural da oluşturulsun mu
    kelime: str | None = Field(default=None, max_length=80)  # İsteğe bağlı anahtar kelime


class DuraklatIstegi(BaseModel):
    duraklat: bool


def _saat(epoch: float) -> str:
    """Epoch saniyesini okunur ISO metnine çevirir: 2026-11-16T14:05:00"""
    return datetime.fromtimestamp(epoch).isoformat(timespec="seconds")


def _oturum_json(oturum: dict, acik_oturum_id) -> dict:
    return {
        "id": oturum["id"],
        "baslangic": _saat(oturum["baslangic"]),
        "bitis": _saat(oturum["bitis"]),
        "sure_sn": round(oturum["bitis"] - oturum["baslangic"]),
        "hukum": oturum["hukum"],                              # programın kararı
        "duzeltme": oturum["duzeltme"],                        # senin düzeltmen (yoksa null)
        "etkin_hukum": oturum["duzeltme"] or oturum["hukum"],  # geçerli olan
        "kaynak": oturum["kaynak"],
        "aciklama": oturum["aciklama"],
        "uygulama": oturum["uygulama"],
        "baslik": oturum["baslik"],
        "suruyor": oturum["id"] == acik_oturum_id,
    }


def uygulama_olustur(takipci: Takipci, depo: Depo) -> FastAPI:
    app = FastAPI(title="Ders Takip", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Güvenlik: sadece bu bilgisayardan, 127.0.0.1/localhost adresiyle gelen
    # istekleri kabul et. (Kötü niyetli bir web sitesinin tarayıcın üzerinden
    # bu API'ye ulaşmasını zorlaştırır.)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    # ------------------------------------------------------------------
    #  Okuma uçları
    # ------------------------------------------------------------------
    @app.get("/api/durum")
    def durum():
        """Şu an ne algılanıyor, sayaç çalışıyor mu, bugünkü toplam."""
        return takipci.durum()

    @app.get("/api/ozet/bugun")
    def ozet_bugun():
        bugun = date.today()
        return depo.gunluk_sureler(bugun, bugun)[0]

    @app.get("/api/ozet/hafta")
    def ozet_hafta():
        """Bu haftanın (Pazartesi-Pazar) gün gün ders süreleri."""
        bugun = date.today()
        pazartesi = bugun - timedelta(days=bugun.weekday())
        gunler = depo.gunluk_sureler(pazartesi, pazartesi + timedelta(days=6))
        for sira, gun in enumerate(gunler):
            gun["gun_adi"] = GUN_ADLARI[sira]
            gun["bugun"] = gun["tarih"] == bugun.isoformat()
        return {"gunler": gunler, "toplam_sn": sum(g["ders_sn"] for g in gunler)}

    @app.get("/api/gunluk")
    def gunluk(baslangic: date, bitis: date):
        """Tarih aralığı için gün gün ders süresi. Örn: /api/gunluk?baslangic=2026-11-01&bitis=2026-11-30"""
        if bitis < baslangic:
            raise HTTPException(400, "bitis, baslangic tarihinden önce olamaz")
        if (bitis - baslangic).days > 366:
            raise HTTPException(400, "En fazla 366 günlük aralık istenebilir")
        return depo.gunluk_sureler(baslangic, bitis)

    @app.get("/api/oturumlar")
    def oturumlar(tarih: date | None = None):
        """Bir güne ait oturumlar (varsayılan: bugün), yeniden eskiye."""
        bas, bit = gun_araligi(tarih or date.today())
        acik = takipci.durum().get("oturum_id")
        return [_oturum_json(o, acik) for o in depo.oturumlari_getir(bas, bit)]

    @app.get("/api/kurallar")
    def kurallar():
        """Düzeltmelerinden öğrenilen kurallar."""
        return depo.ogrenilen_kurallar()

    # ------------------------------------------------------------------
    #  Değiştiren uçlar
    # ------------------------------------------------------------------
    @app.post("/api/oturumlar/{oturum_id}/duzelt")
    def oturum_duzelt(oturum_id: int, istek: DuzeltmeIstegi):
        """Bir oturumu "dersti" / "ders değildi" diye düzeltir ve istenirse kural öğrenir."""
        oturum = depo.oturum_getir(oturum_id)
        if oturum is None:
            raise HTTPException(404, "Oturum bulunamadı")

        depo.oturum_duzelt(oturum_id, istek.hukum)

        ogrenilenler = []
        benzer_sayisi = 0
        if istek.ogren:
            # Tarayıcı oturumuysa başlığın tamamını, uygulamaysa süreç adını öğren.
            if oturum["kaynak"] == "baslik" and oturum["baslik"]:
                depo.kural_ekle("baslik", oturum["baslik"], istek.hukum)
                ogrenilenler.append({"tur": "baslik", "desen": oturum["baslik"]})
            elif oturum["kaynak"] == "pencere" and oturum["uygulama"]:
                depo.kural_ekle("surec", oturum["uygulama"], istek.hukum)
                ogrenilenler.append({"tur": "surec", "desen": oturum["uygulama"]})
            # Aynı şeye ait diğer belirsiz oturumları da tek seferde düzelt.
            benzer_sayisi = depo.benzerleri_duzelt(oturum, istek.hukum)

        kelime = (istek.kelime or "").strip()
        if len(kelime) >= 2:
            depo.kural_ekle("kelime", kelime, istek.hukum)
            ogrenilenler.append({"tur": "kelime", "desen": kelime})

        return {"tamam": True, "ogrenilenler": ogrenilenler, "benzer_duzeltilen": benzer_sayisi}

    @app.delete("/api/kurallar/{kural_id}")
    def kural_sil(kural_id: int):
        if not depo.kural_sil(kural_id):
            raise HTTPException(404, "Kural bulunamadı")
        return {"tamam": True}

    @app.post("/api/duraklat")
    def duraklat(istek: DuraklatIstegi):
        """Takibi elle duraklat / devam ettir."""
        takipci.duraklat(istek.duraklat)
        return {"duraklatildi": takipci.duraklatildi}

    # ------------------------------------------------------------------
    #  Arayüz (HTML/CSS/JS dosyaları)
    # ------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def ana_sayfa():
        return FileResponse(STATIK_KLASOR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIK_KLASOR), name="static")
    return app
