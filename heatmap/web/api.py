"""FastAPI uygulaması: JSON API + arayüz dosyaları.

Bütün veri uçları /api/ altında ve JSON döndürür. İleride Windows
dashboard'u ya da Health Connect birleştirmesi de aynı uçları okuyabilir.
Otomatik API dokümantasyonu: http://127.0.0.1:8765/api/docs
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from heatmap import otomatik_baslatma
from heatmap.dedektorler.kamera import KameraDedektoru
from heatmap.dedektorler.tarayici import TarayiciDedektoru
from heatmap.depo import Depo, gun_araligi
from heatmap.kart import kart_ciz, kart_verisi
from heatmap.ozet import GUN_ADLARI, Adlandirici, isi_haritasi, seri_hesapla
from heatmap.takipci import Takipci

STATIK_KLASOR = Path(__file__).parent / "static"


# --- İstek gövdeleri (FastAPI gelen JSON'u bu kalıplara göre doğrular) ---
class DuzeltmeIstegi(BaseModel):
    hukum: Literal["ders", "ders_degil"]
    ogren: bool = True                 # Bu uygulama/başlık için kalıcı kural da oluşturulsun mu
    kelime: str | None = Field(default=None, max_length=80)  # İsteğe bağlı anahtar kelime
    site_ogren: bool = False           # Oturumun sitesini (eklentiden gelen alan adı) hep böyle say


class DuraklatIstegi(BaseModel):
    duraklat: bool


class OtomatikBaslatmaIstegi(BaseModel):
    acik: bool


class KameraIstegi(BaseModel):
    acik: bool


class SaglikKaydi(BaseModel):
    """Elle girilen günlük sağlık verisi. Boş bırakılan (null) alan değişmez."""
    tarih: date
    adim: int | None = Field(default=None, ge=0, le=200_000)
    egzersiz_dk: int | None = Field(default=None, ge=0, le=1440)
    uyku_dk: int | None = Field(default=None, ge=0, le=1440)


class TarayiciRaporu(BaseModel):
    """Tarayıcı eklentisinin gönderdiği rapor (bkz. eklenti/arkaplan.js)."""
    alan_adi: str = Field(default="", max_length=253)
    sesli: bool = False
    odakta: bool = True


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
        "alan_adi": oturum.get("alan_adi") or "",  # eklenti kuruluysa site adı
    }


def uygulama_olustur(takipci: Takipci, depo: Depo, ayarlar: dict,
                     tarayici: TarayiciDedektoru | None = None,
                     kamera: KameraDedektoru | None = None) -> FastAPI:
    """tarayici: eklenti raporlarının bırakılacağı dedektör (modül kapalıysa None).
    kamera  : aç/kapat ve kalibrasyon için kamera dedektörü (modül kapalıysa None)."""
    adlandirici = Adlandirici(ayarlar)  # Süreç adı / sekme başlığı -> okunabilir ad
    hedef_sn = int(ayarlar.get("hedef", {}).get("gunluk_dk", 0) * 60)  # Günlük hedef (saniye)

    # Başlık "Takip Paneli" ile başlıyor ki API dokümantasyon sekmesi de yok sayılsın.
    app = FastAPI(title="Takip Paneli API", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Güvenlik: sadece bu bilgisayardan, 127.0.0.1/localhost adresiyle gelen
    # istekleri kabul et. (Kötü niyetli bir web sitesinin tarayıcın üzerinden
    # bu API'ye ulaşmasını zorlaştırır.)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    # Güvenlik: veri DEĞİŞTİREN istekler "X-Heatmap" başlığı taşımak zorunda.
    # Neden? Açtığın herhangi bir web sitesi, tarayıcın üzerinden 127.0.0.1'e
    # gizlice form/istek gönderebilir. Ama özel bir başlık eklemeye çalışırsa
    # tarayıcı önce izin sorar (CORS) ve bu sunucu izin vermediği için istek
    # hiç gönderilmez. Kendi arayüzümüz ve eklentimiz bu başlığı ekler.
    @app.middleware("http")
    async def degistiren_istekleri_koru(istek, sonraki):
        if istek.method not in ("GET", "HEAD", "OPTIONS") and istek.headers.get("x-heatmap") != "1":
            return JSONResponse({"detail": "X-Heatmap başlığı eksik"}, status_code=403)
        return await sonraki(istek)

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
        gunler = depo.gunluk_birlesik(pazartesi, pazartesi + timedelta(days=6))
        for sira, gun in enumerate(gunler):
            gun["gun_adi"] = GUN_ADLARI[sira]
            gun["bugun"] = gun["tarih"] == bugun.isoformat()
        return {"gunler": gunler, "toplam_sn": sum(g["ders_sn"] for g in gunler)}

    @app.get("/api/gunluk")
    def gunluk(baslangic: date, bitis: date):
        """Tarih aralığı için gün gün çalışma süresi + sağlık verisi (adım, egzersiz, uyku).

        Örn: /api/gunluk?baslangic=2026-11-01&bitis=2026-11-30
        Sağlık alanları o gün için kayıt yoksa null'dır.
        """
        if bitis < baslangic:
            raise HTTPException(400, "bitis, baslangic tarihinden önce olamaz")
        if (bitis - baslangic).days > 366:
            raise HTTPException(400, "En fazla 366 günlük aralık istenebilir")
        return depo.gunluk_birlesik(baslangic, bitis)

    @app.get("/api/saglik")
    def saglik_listesi(baslangic: date | None = None, bitis: date | None = None):
        """Kayıtlı sağlık verisi (varsayılan: bu hafta). Yalnızca kaydı olan günler döner."""
        bugun = date.today()
        ilk = baslangic or bugun - timedelta(days=bugun.weekday())
        son = bitis or ilk + timedelta(days=6)
        if son < ilk:
            raise HTTPException(400, "bitis, baslangic tarihinden önce olamaz")
        return sorted(depo.saglik_getir(ilk, son).values(), key=lambda k: k["tarih"])

    @app.post("/api/saglik")
    def saglik_kaydet(kayit: SaglikKaydi):
        """Bir günün adım / egzersiz / uyku verisini elle kaydeder."""
        if kayit.tarih > date.today():
            raise HTTPException(400, "Gelecekteki bir gün için veri girilemez")
        if kayit.adim is None and kayit.egzersiz_dk is None and kayit.uyku_dk is None:
            raise HTTPException(400, "En az bir değer girilmeli")
        depo.saglik_kaydet(kayit.tarih, kayit.adim, kayit.egzersiz_dk, kayit.uyku_dk, kaynak="elle")
        return depo.saglik_getir(kayit.tarih, kayit.tarih)[kayit.tarih.isoformat()]

    @app.delete("/api/saglik/{tarih}")
    def saglik_sil(tarih: date):
        if not depo.saglik_sil(tarih):
            raise HTTPException(404, "Bu gün için sağlık kaydı yok")
        return {"tamam": True}

    @app.get("/api/dokum")
    def dokum(baslangic: date | None = None, bitis: date | None = None):
        """Ders süresinin uygulamalara dağılımı. Tarih verilmezse bugün; iki tarih de dahildir.

        Örn: /api/dokum?baslangic=2026-11-16&bitis=2026-11-22
        """
        ilk = baslangic or date.today()
        son = bitis or ilk
        if son < ilk:
            raise HTTPException(400, "bitis, baslangic tarihinden önce olamaz")
        bas, _ = gun_araligi(ilk)
        _, bit = gun_araligi(son)
        uygulamalar = depo.uygulama_dokumu(bas, bit, adlandirici.etiket)
        toplam = sum(u["sure_sn"] for u in uygulamalar)
        for u in uygulamalar:
            u["oran"] = round(u["sure_sn"] / toplam, 3) if toplam else 0  # 0-1 arası pay
        return {
            "baslangic": ilk.isoformat(),
            "bitis": son.isoformat(),
            "toplam_sn": toplam,
            "uygulamalar": uygulamalar,
        }

    @app.get("/api/dashboard")
    def dashboard_verisi():
        """Masaüstü dashboard'u için tek seferde özet. Pencere/sekme BAŞLIĞI İÇERMEZ.

        Dashboard ekranda sürekli açık durduğu (ekran paylaşımında, ekran görüntülerinde
        görünebileceği) için yalnızca okunabilir uygulama/site adları ve sayılar döner.
        """
        d = takipci.durum()
        if d.get("kaynak") in ("pencere", "baslik"):
            simdiki, _ = adlandirici.etiket({k: d.get(k) for k in ("kaynak", "uygulama", "baslik", "alan_adi")})
        elif d.get("kaynak") == "bosta":
            simdiki = "Bilgisayar başında değil"
        else:
            simdiki = ""
        bugun = date.today()
        bas, bit = gun_araligi(bugun)
        dokum = depo.uygulama_dokumu(bas, bit, adlandirici.etiket)
        toplam = sum(u["sure_sn"] for u in dokum) or 1
        isi = isi_haritasi(depo, hedef_sn, bugun, 20)
        return {
            "calisiyor": d["calisiyor"],
            "duraklatildi": d["duraklatildi"],
            "durum": "duraklatildi" if d["duraklatildi"] else "calisiyor" if d["calisiyor"]
                     else "belirsiz" if d.get("hukum") == "belirsiz" else "durdu",
            "simdiki": simdiki,
            "bugun_sn": d["bugun_ders_sn"],
            "hedef_sn": hedef_sn,
            "seri_gun": isi["simdiki_seri"],
            "hafta": ozet_hafta()["gunler"],
            "isi": [{"tarih": g["tarih"], "seviye": g["seviye"], "gelecek": g["gelecek"]} for g in isi["gunler"]],
            "en_cok": [{"ad": u["ad"], "sure_sn": u["sure_sn"], "oran": round(u["sure_sn"] / toplam, 3)}
                       for u in dokum[:3]],
        }

    @app.get("/api/seri")
    def seri():
        """Günlük hedef ve seri: hedefe üst üste kaç gündür ulaşıldı."""
        bugun = date.today()
        bugun_sn = depo.gunluk_sureler(bugun, bugun)[0]["ders_sn"]
        return {
            "hedef_sn": hedef_sn,
            "seri_gun": seri_hesapla(depo, hedef_sn, bugun),
            "bugun_sn": bugun_sn,
            "bugun_hedefe_ulasildi": bool(hedef_sn) and bugun_sn >= hedef_sn,
        }

    @app.get("/api/isi-haritasi")
    def isi_haritasi_ucu(bitis: date | None = None, hafta: int = 53):
        """GitHub katkı grafiği gibi ısı haritası: Pazartesi'den başlayan `hafta` hafta.

        Her gün için {tarih, ders_sn, seviye (0-4), gelecek} ve aralığın özeti döner.
        """
        if not 1 <= hafta <= 106:
            raise HTTPException(400, "hafta 1 ile 106 arasında olmalı")
        return isi_haritasi(depo, hedef_sn, bitis or date.today(), hafta)

    @app.get("/api/kart")
    def kart(tur: Literal["gunluk", "haftalik", "aylik", "yillik"] = "gunluk",
             tarih: date | None = None, indir: bool = False):
        """Paylaşım kartı: 1080x1920 PNG. `indir=true` verilirse tarayıcı dosya olarak kaydeder.

        `tarih`: kartın ait olduğu gün (varsayılan bugün; geçmiş bir gün de olabilir).
        Kartta pencere/sekme başlığı bulunmaz; yalnızca uygulama ve site adları (bkz. kart.py).
        """
        bugun = date.today()
        tarih = tarih or bugun
        if tarih > bugun:
            raise HTTPException(400, "Gelecekteki bir gün için kart oluşturulamaz")
        png = kart_ciz(kart_verisi(depo, adlandirici, hedef_sn, tur, tarih, bugun))
        basliklar = {"Cache-Control": "no-store"}  # Her istekte güncel kart üretilsin
        if indir:
            basliklar["Content-Disposition"] = f'attachment; filename="heatmap-{tur}-{tarih.isoformat()}.png"'
        return Response(png, media_type="image/png", headers=basliklar)

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

        if istek.site_ogren and oturum.get("alan_adi"):
            depo.kural_ekle("alan", oturum["alan_adi"], istek.hukum)
            ogrenilenler.append({"tur": "alan", "desen": oturum["alan_adi"]})

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

    @app.post("/api/tarayici")
    def tarayici_raporu(rapor: TarayiciRaporu):
        """Tarayıcı eklentisi buraya öndeki sekmenin site adını ve ses durumunu bildirir."""
        if tarayici is None:
            return {"tamam": False, "neden": "Tarayıcı modülü ayarlardan kapatılmış"}
        tarayici.rapor_al(rapor.alan_adi, rapor.sesli, rapor.odakta)
        return {"tamam": True}

    @app.get("/api/kamera")
    def kamera_durumu():
        """Kamera modülü açık mı, kalibrasyon, canlı kafa açısı (açı kaydedilmez)."""
        if kamera is None:
            return {"etkin": False}
        return {"etkin": True, **kamera.durum_bilgisi()}

    @app.post("/api/kamera")
    def kamera_ac_kapat(istek: KameraIstegi):
        """Kamerayı geçici olarak kapatır/açar (kapalıyken işçi durur, kamera ışığı söner)."""
        if kamera is None:
            raise HTTPException(400, "Kamera modülü ayarlardan kapalı ([kamera] etkin = false)")
        kamera.ayarla_acik(istek.acik)
        return {"acik": kamera.acik}

    @app.post("/api/kamera/kalibre")
    def kamera_kalibre():
        """~6 sn boyunca kafa açısını ölçer ve "ekrana bakma açısı" olarak kaydeder.
        Bu sırada kullanıcı ekrana normal bakmalı. (Normal def: FastAPI bunu ayrı bir
        thread'de çalıştırır, beklerken diğer istekler etkilenmez.)"""
        if kamera is None:
            raise HTTPException(400, "Kamera modülü ayarlardan kapalı ([kamera] etkin = false)")
        try:
            return {"ekran_pitch": kamera.kalibre_et()}
        except ValueError as hata:
            raise HTTPException(400, str(hata))

    @app.post("/api/duraklat")
    def duraklat(istek: DuraklatIstegi):
        """Takibi elle duraklat / devam ettir."""
        takipci.duraklat(istek.duraklat)
        return {"duraklatildi": takipci.duraklatildi}

    @app.get("/api/otomatik-baslatma")
    def otomatik_baslatma_durumu():
        """Windows açılışında otomatik başlatma açık mı?"""
        return {"acik": otomatik_baslatma.acik_mi()}

    @app.post("/api/otomatik-baslatma")
    def otomatik_baslatma_ayarla(istek: OtomatikBaslatmaIstegi):
        """Windows açılışında otomatik başlatmayı açar/kapatır (kullanıcının kayıt defteri)."""
        return {"acik": otomatik_baslatma.ayarla(istek.acik)}

    # ------------------------------------------------------------------
    #  Arayüz (HTML/CSS/JS dosyaları)
    # ------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def ana_sayfa():
        return FileResponse(STATIK_KLASOR / "index.html")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard():
        """Masaüstü dashboard'u: duvar kâğıdı aracında (örn. Lively Wallpaper) bu adres açılır.
        ?saydam=1 eklenirse zemin saydam olur."""
        return FileResponse(STATIK_KLASOR / "dashboard.html")

    app.mount("/static", StaticFiles(directory=STATIK_KLASOR), name="static")
    return app
