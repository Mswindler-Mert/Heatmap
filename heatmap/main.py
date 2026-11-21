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
import webbrowser
from pathlib import Path

import uvicorn

from heatmap import otomatik_baslatma
from heatmap.ayarlar import VERI_KLASORU, ayarlari_yukle
from heatmap.dedektorler.baslik import BaslikDedektoru
from heatmap.dedektorler.bosta import BostaDedektoru
from heatmap.dedektorler.kamera import KameraDedektoru
from heatmap.dedektorler.pencere import PencereDedektoru
from heatmap.dedektorler.tarayici import TarayiciDedektoru
from heatmap.depo import Depo
from heatmap.motor import KararMotoru
from heatmap.takipci import Takipci
from heatmap.web.api import uygulama_olustur


def _ciktiyi_dosyaya_yonlendir() -> None:
    """Konsolsuz (pythonw.exe ile) çalışırken print çıktıları kaybolmasın, dosyaya gitsin."""
    if sys.stdout is not None:
        return  # Normal terminalde çalışıyoruz, dokunma
    gunluk = VERI_KLASORU / "heatmap.log"
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


def dedektorleri_kur(ayarlar: dict, depo: Depo) -> list:
    """Ayar dosyasında etkin olan modülleri oluşturur.

    SIRA ÖNEMLİ: başlık dedektörü hem pencere dedektörünün okuduğu başlığı hem de
    tarayıcı dedektörünün (eklentiden gelen) site adını kullanır; ikisinden sonra gelmeli.
    Yeni bir modül eklemek için buraya bir satır eklemen yeterli.
    """
    dedektorler = []
    if ayarlar["pencere"]["etkin"]:
        dedektorler.append(PencereDedektoru(ayarlar, depo.ogrenilen_kurallar))
    if ayarlar.get("tarayici", {}).get("etkin", True):
        dedektorler.append(TarayiciDedektoru())
    if ayarlar["baslik"]["etkin"]:
        dedektorler.append(BaslikDedektoru(ayarlar, depo.ogrenilen_kurallar))
    if ayarlar["bosta"]["etkin"]:
        dedektorler.append(BostaDedektoru(ayarlar))
    if ayarlar["kamera"]["etkin"]:
        dedektorler.append(KameraDedektoru(ayarlar))
    return dedektorler


def main() -> None:
    VERI_KLASORU.mkdir(exist_ok=True)
    _ciktiyi_dosyaya_yonlendir()

    ayarlar = ayarlari_yukle()
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
    depo = Depo(VERI_KLASORU / VERITABANI_ADI)
    motor = KararMotoru(ayarlar["tolerans"]["baslatma_sn"], ayarlar["tolerans"]["durdurma_sn"])
    dedektorler = dedektorleri_kur(ayarlar, depo)
    takipci = Takipci(ayarlar, depo, dedektorler, motor)
    # Eklenti raporlarını web sunucusu bu dedektöre bırakır (modül kapalıysa None).
    tarayici = next((d for d in dedektorler if isinstance(d, TarayiciDedektoru)), None)
    kamera = next((d for d in dedektorler if isinstance(d, KameraDedektoru)), None)
    takipci.baslat()

    # --- Web sunucusu (ayrı thread'de) ---
    # host="127.0.0.1": sadece bu bilgisayardan erişilebilir, ağdaki diğer cihazlardan değil.
    sunucu = uvicorn.Server(uvicorn.Config(
        uygulama_olustur(takipci, depo, ayarlar, tarayici, kamera), host="127.0.0.1", port=port, log_level="warning",
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
            Tepsi(takipci, adres, kamera).calistir()
    except KeyboardInterrupt:
        pass
    finally:
        # --- Düzgün kapanış: açık oturumu veritabanına yaz ---
        takipci.durdur()
        sunucu.should_exit = True
        sunucu_thread.join(timeout=5)
        print("Heatmap kapandı.", flush=True)
