"""Programın giriş noktası: bütün parçaları kurar ve birbirine bağlar.

Çalıştırma:
    py -m ders_takip              -> tepsi ikonuyla (normal kullanım)
    py -m ders_takip --tepsisiz   -> tepsi ikonu olmadan; terminalde Ctrl+C ile kapanır
    py -m ders_takip --sessiz     -> açılışta tarayıcıyı açma
"""

import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from ders_takip.ayarlar import VERI_KLASORU, ayarlari_yukle
from ders_takip.dedektorler.baslik import BaslikDedektoru
from ders_takip.dedektorler.bosta import BostaDedektoru
from ders_takip.dedektorler.kamera import KameraDedektoru
from ders_takip.dedektorler.pencere import PencereDedektoru
from ders_takip.depo import Depo
from ders_takip.motor import KararMotoru
from ders_takip.takipci import Takipci
from ders_takip.web.api import uygulama_olustur


def _ciktiyi_dosyaya_yonlendir() -> None:
    """Konsolsuz (pythonw.exe ile) çalışırken print çıktıları kaybolmasın, dosyaya gitsin."""
    if sys.stdout is not None:
        return  # Normal terminalde çalışıyoruz, dokunma
    gunluk = VERI_KLASORU / "ders_takip.log"
    # Dosya çok büyüdüyse baştan başla.
    if gunluk.exists() and gunluk.stat().st_size > 1_000_000:
        gunluk.unlink()
    dosya = open(gunluk, "a", encoding="utf-8", buffering=1)
    sys.stdout = dosya
    sys.stderr = dosya


def _port_dolu_mu(port: int) -> bool:
    """Bu portu dinleyen biri var mı? (Varsa program zaten açık demektir.)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as soket:
        soket.settimeout(0.5)
        return soket.connect_ex(("127.0.0.1", port)) == 0


def dedektorleri_kur(ayarlar: dict, depo: Depo) -> list:
    """Ayar dosyasında etkin olan modülleri oluşturur.

    SIRA ÖNEMLİ: başlık dedektörü, pencere dedektörünün okuduğu başlığı kullanır.
    Yeni bir modül eklemek için buraya bir satır eklemen yeterli.
    """
    dedektorler = []
    if ayarlar["pencere"]["etkin"]:
        dedektorler.append(PencereDedektoru(ayarlar, depo.ogrenilen_kurallar))
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
        print("Ders Takip zaten çalışıyor, arayüz açılıyor.")
        webbrowser.open(adres)
        return

    # --- Parçaları kur ---
    depo = Depo(VERI_KLASORU / "ders_takip.db")
    motor = KararMotoru(ayarlar["tolerans"]["baslatma_sn"], ayarlar["tolerans"]["durdurma_sn"])
    takipci = Takipci(ayarlar, depo, dedektorleri_kur(ayarlar, depo), motor)
    takipci.baslat()

    # --- Web sunucusu (ayrı thread'de) ---
    # host="127.0.0.1": sadece bu bilgisayardan erişilebilir, ağdaki diğer cihazlardan değil.
    sunucu = uvicorn.Server(uvicorn.Config(
        uygulama_olustur(takipci, depo), host="127.0.0.1", port=port, log_level="warning",
    ))
    sunucu_thread = threading.Thread(target=sunucu.run, name="web", daemon=True)
    sunucu_thread.start()

    print(f"Ders Takip çalışıyor: {adres}", flush=True)
    if ayarlar["genel"]["acilista_arayuzu_ac"] and "--sessiz" not in sys.argv:
        webbrowser.open(adres)

    # --- Ana thread: tepsi ikonu (ya da Ctrl+C bekle) ---
    try:
        if "--tepsisiz" in sys.argv:
            while True:
                time.sleep(1)
        else:
            from ders_takip.tepsi import Tepsi  # pystray'i sadece gerekince yükle
            Tepsi(takipci, adres).calistir()
    except KeyboardInterrupt:
        pass
    finally:
        # --- Düzgün kapanış: açık oturumu veritabanına yaz ---
        takipci.durdur()
        sunucu.should_exit = True
        sunucu_thread.join(timeout=5)
        print("Ders Takip kapandı.", flush=True)
