"""Programın giriş noktası: bütün parçaları kurar ve birbirine bağlar.

Çalıştırma:
    py -m heatmap              -> tepsi ikonuyla (normal kullanım)
    py -m heatmap --tepsisiz   -> tepsi ikonu olmadan; terminalde Ctrl+C ile kapanır
    py -m heatmap --sessiz     -> açılışta tarayıcıyı açma
"""

import socket
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import uvicorn

from heatmap import otomatik_baslatma
from heatmap.ayarlar import KISISEL_DOSYA, UYARILAR, VERI_KLASORU, ayarlari_yukle
from heatmap.dedektorler.baslik import BaslikDedektoru
from heatmap.dedektorler.bosta import BostaDedektoru
from heatmap.dedektorler.kamera import KameraDedektoru
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.dedektorler.tarayici import TarayiciDedektoru
from heatmap.depo import Depo
from heatmap.motor import KararMotoru
from heatmap.tahmin import Tahminci
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur
from heatmap.yedek import YedekZamanlayici


GUNLUK_DOSYASI = VERI_KLASORU / "heatmap.log"


def _ciktiyi_dosyaya_yonlendir() -> None:
    """Konsolsuz (pythonw.exe ile) çalışırken print çıktıları kaybolmasın, dosyaya gitsin."""
    if sys.stdout is not None:
        return  # Normal terminalde çalışıyoruz, dokunma
    gunluk = GUNLUK_DOSYASI
    # Dosya çok büyüdüyse baştan başla.
    if gunluk.exists() and gunluk.stat().st_size > 1_000_000:
        gunluk.unlink()
    dosya = open(gunluk, "a", encoding="utf-8", buffering=1)
    sys.stdout = dosya
    sys.stderr = dosya


VERITABANI_ADI = "heatmap.db"
ESKI_VERITABANI_ADI = "ders_takip.db"  # Proje "Ders Takip" adındayken kullanılan dosya


def eski_veritabanini_tasi(klasor: Path) -> bool:
    """Proje adı değişmeden önceki veritabanını (ders_takip.db) yeni adına taşır.

    Sadece yeni dosya henüz YOKSA taşır; böylece hiçbir veri üzerine yazılmaz.
    SQLite'ın yan dosyaları (-wal, -shm, -journal) varsa onlar da birlikte taşınır.
    Taşıma yapıldıysa True döndürür.
    """
    eski = klasor / ESKI_VERITABANI_ADI
    yeni = klasor / VERITABANI_ADI
    if not eski.exists() or yeni.exists():
        return False
    for ek in ("", "-wal", "-shm", "-journal"):
        eski_dosya = klasor / (ESKI_VERITABANI_ADI + ek)
        if eski_dosya.exists():
            eski_dosya.rename(klasor / (VERITABANI_ADI + ek))
    return True


def _port_dolu_mu(port: int) -> bool:
    """Bu portu dinleyen biri var mı? (Varsa program zaten açık demektir.)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soket:
        soket.settimeout(0.5)
        return soket.connect_ex(("127.0.0.1", port)) == 0


def dedektorleri_kur(ayarlar: dict, depo: Depo, onceki: list | None = None,
                     onceki_ayarlar: dict | None = None, tahminci=None) -> list:
    """Ayar dosyasında etkin olan modülleri oluşturur.

    SIRA ÖNEMLİ: başlık dedektörü hem pencere dedektörünün okuduğu başlığı hem de
    tarayıcı dedektörünün (eklentiden gelen) site adını kullanır; ikisinden sonra gelmeli.
    Yeni bir modül eklemek için buraya bir satır eklemen yeterli.

    onceki / onceki_ayarlar: ayarlar çalışırken değişince verilir. Tarayıcı dedektörü (son
    eklenti raporunu tutar) ve ayarı değişmediyse kamera dedektörü (işçi süreci, ışık yanıp
    sönmesin) YENİDEN KURULMAZ, eskisi kullanılır. Diğerleri ucuz; her seferinde yenilenir.
    """
    onceki = onceki or []
    eski_tarayici = next((d for d in onceki if isinstance(d, TarayiciDedektoru)), None)
    eski_kamera = next((d for d in onceki if isinstance(d, KameraDedektoru)), None)
    kamera_ayari_ayni = onceki_ayarlar is not None and onceki_ayarlar.get("kamera") == ayarlar.get("kamera")

    dedektorler = []
    if ayarlar["pencere"]["etkin"]:
        dedektorler.append(PencereDedektoru(ayarlar, depo.ogrenilen_kurallar))
    if ayarlar.get("tarayici", {}).get("etkin", True):
        dedektorler.append(eski_tarayici or TarayiciDedektoru())
    if ayarlar["baslik"]["etkin"]:
        dedektorler.append(BaslikDedektoru(ayarlar, depo.ogrenilen_kurallar, tahminci))
    if ayarlar["bosta"]["etkin"]:
        dedektorler.append(BostaDedektoru(ayarlar))
    if ayarlar["kamera"]["etkin"]:
        dedektorler.append(eski_kamera if (eski_kamera and kamera_ayari_ayni) else KameraDedektoru(ayarlar))
    return dedektorler


def hata_penceresi(mesaj: str) -> None:
    """Windows uyarı penceresi gösterir (konsolsuz çalışırken kullanıcı hatayı görsün diye)."""
    import ctypes
    MB_ICONERROR, MB_TOPMOST = 0x10, 0x40000
    ctypes.windll.user32.MessageBoxW(None, mesaj, "Heatmap", MB_ICONERROR | MB_TOPMOST)


def calistir(ana=None, pencere=hata_penceresi, gunluk=None) -> None:
    """main()'i çalıştırır. Beklenmeyen bir hata olursa programı sessizce kapatmak yerine:
    hatayı günlük dosyasına yazar ve konsolsuz çalışıyorsa bir uyarı penceresi gösterir.

    ana / pencere / gunluk parametreleri testler içindir.
    """
    ana = ana or main
    gunluk = gunluk or GUNLUK_DOSYASI
    konsolsuz = sys.stdout is None or getattr(sys.stdout, "name", "") == str(gunluk)
    try:
        ana()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as hata:  # Programın en dış katmanı: her türlü hatayı yakala
        ayrinti = traceback.format_exc()
        try:
            gunluk.parent.mkdir(parents=True, exist_ok=True)
            with open(gunluk, "a", encoding="utf-8") as dosya:
                dosya.write(f"\n=== ÇÖKME {datetime.now():%Y-%m-%d %H:%M:%S} ===\n{ayrinti}\n")
        except OSError:
            pass
        if konsolsuz or sys.stdout is None:
            pencere(f"Heatmap başlatılamadı ya da beklenmedik biçimde kapandı.\n\n"
                    f"{type(hata).__name__}: {hata}\n\nAyrıntılar: {gunluk}")
        else:
            print(ayrinti, file=sys.stderr)
        raise SystemExit(1) from hata


def main() -> None:
    VERI_KLASORU.mkdir(exist_ok=True)
    _ciktiyi_dosyaya_yonlendir()

    ayarlar = ayarlari_yukle()
    for uyari in ayarlar.get(UYARILAR, []):  # Arayüz de bunları sayfanın üstünde gösterir
        print(f"AYAR UYARISI: {uyari}", flush=True)
    port = ayarlar["genel"]["port"]
    adres = f"http://127.0.0.1:{port}"

    # Program zaten açıksa ikincisini başlatma, sadece arayüzü göster.
    if _port_dolu_mu(port):
        # --sessiz ile (örn. Windows açılışında) gelindiyse tarayıcı da açma, sessizce çık.
        if "--sessiz" not in sys.argv:
            print("Heatmap zaten çalışıyor, arayüz açılıyor.")
            webbrowser.open(adres)
        return

    # Eski adla biriken veriyi koru. (Eski sürüm hâlâ açıkken buraya gelinmez:
    # port dolu olduğu için yukarıda çıkılır, yani dosya kullanımdayken taşınmaz.)
    try:
        if eski_veritabanini_tasi(VERI_KLASORU):
            print(f"Eski veritabanı {ESKI_VERITABANI_ADI} -> {VERITABANI_ADI} olarak taşındı.", flush=True)
    except OSError as hata:
        print(f"UYARI: eski veritabanı taşınamadı ({hata}); yeni bir veritabanıyla devam ediliyor.", flush=True)

    # Otomatik başlatma açıksa ve proje klasörü taşındıysa kayıtlı komutu düzelt.
    try:
        if otomatik_baslatma.guncel_tut():
            print("Otomatik başlatma komutu yeni klasöre göre güncellendi.", flush=True)
    except OSError as hata:
        print(f"UYARI: otomatik başlatma kontrol edilemedi ({hata}).", flush=True)

    # --- Parçaları kur ---
    depo = Depo(VERI_KLASORU / VERITABANI_ADI, yedek_klasoru=VERI_KLASORU / "yedek")
    if depo.uygulanan_gocler:
        print(f"Veritabanı şeması güncellendi (taşımalar: {depo.uygulanan_gocler}); "
              f"öncesinin yedeği data/yedek/ içinde.", flush=True)

    # Günlük otomatik yedek (data/yedek/). Açılışta ve sonra saatte bir kontrol edilir.
    yedek_ayari = ayarlar.get("yedek", {})
    yedekci = None
    if yedek_ayari.get("etkin", True):
        yedekci = YedekZamanlayici(VERI_KLASORU / VERITABANI_ADI, VERI_KLASORU / "yedek",
                                   saklanacak=yedek_ayari.get("saklanacak_gun", 7))
        yedekci.baslat()
    motor = KararMotoru(ayarlar["tolerans"]["baslatma_sn"], ayarlar["tolerans"]["durdurma_sn"])
    # Düzeltmelerden öğrenen model (heatmap/tahmin.py); düzeltme yapıldıkça API yeniden eğitir.
    tahminci = Tahminci(depo)
    bilgi = tahminci.yeniden_egit()
    print(f"Tahmin modeli: {bilgi['ornek_sayisi']} örnek, hazır: {bilgi['hazir']}", flush=True)
    dedektorler = dedektorleri_kur(ayarlar, depo, tahminci=tahminci)
    takipci = Takipci(ayarlar, depo, dedektorler, motor)
    # Eklenti raporlarını web sunucusu bu dedektöre bırakır (modül kapalıysa None).
    tarayici = next((d for d in dedektorler if isinstance(d, TarayiciDedektoru)), None)
    kamera = next((d for d in dedektorler if isinstance(d, KameraDedektoru)), None)
    takipci.baslat()

    # --- Ayarlar arayüzden değişince: yeniden başlatmadan uygula ---
    calisan = {"ayarlar": ayarlar, "tepsi": None}  # Değişebilen parçalar (tepsi aşağıda kurulur)

    def ayarlari_yeniden_yukle():
        """config.toml'u yeniden okur ve takipçiye, tepsiye, yedekçiye uygular.
        Web arayüzü (api.py) "Kaydet"ten sonra bunu çağırır."""
        yeni = ayarlari_yukle()
        eski_dedektorler = takipci.dedektorler
        yeni_dedektorler = dedektorleri_kur(yeni, depo, eski_dedektorler, calisan["ayarlar"], tahminci)
        takipci.ayarlari_uygula(yeni, yeni_dedektorler)
        for dedektor in eski_dedektorler:  # Artık kullanılmayanları kapat (örn. kamera işçisi)
            if dedektor not in yeni_dedektorler:
                dedektor.kapat()
        if yedekci:
            yedekci.saklanacak = yeni.get("yedek", {}).get("saklanacak_gun", 7)
        yeni_tarayici = next((d for d in yeni_dedektorler if isinstance(d, TarayiciDedektoru)), None)
        yeni_kamera = next((d for d in yeni_dedektorler if isinstance(d, KameraDedektoru)), None)
        if calisan["tepsi"] is not None:
            calisan["tepsi"].kamera = yeni_kamera
        calisan["ayarlar"] = yeni
        print("Ayarlar arayüzden değişti ve uygulandı.", flush=True)
        for uyari in yeni.get(UYARILAR, []):
            print(f"AYAR UYARISI: {uyari}", flush=True)
        return yeni, yeni_tarayici, yeni_kamera

    # --- Web sunucusu (ayrı thread'de) ---
    # host="127.0.0.1": sadece bu bilgisayardan erişilebilir, ağdaki diğer cihazlardan değil.
    sunucu = uvicorn.Server(uvicorn.Config(
        uygulama_olustur(takipci, depo, ayarlar, tarayici, kamera,
                         ayar_dosyasi=KISISEL_DOSYA, yedek_klasoru=VERI_KLASORU / "yedek", tahminci=tahminci,
                         yeniden_yukleyici=ayarlari_yeniden_yukle),
        host="127.0.0.1", port=port, log_level="warning",
    ))
    sunucu_thread = threading.Thread(target=sunucu.run, name="web", daemon=True)
    sunucu_thread.start()

    print(f"Heatmap çalışıyor: {adres}", flush=True)
    if ayarlar["genel"]["acilista_arayuzu_ac"] and "--sessiz" not in sys.argv:
        webbrowser.open(adres)

    # --- Ana thread: tepsi ikonu (ya da Ctrl+C bekle) ---
    try:
        if "--tepsisiz" in sys.argv:
            while True:
                time.sleep(1)
        else:
            from heatmap.tepsi import Tepsi  # pystray'i sadece gerekince yükle
            calisan["tepsi"] = Tepsi(takipci, adres, kamera)
            calisan["tepsi"].calistir()
    except KeyboardInterrupt:
        pass
    finally:
        # --- Düzgün kapanış: açık oturumu veritabanına yaz ---
        takipci.durdur()
        if yedekci:
            yedekci.durdur()
        sunucu.should_exit = True
        sunucu_thread.join(timeout=5)
        print("Heatmap kapandı.", flush=True)
