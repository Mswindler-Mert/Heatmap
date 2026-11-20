"""Kamera işçisi: ayrı bir süreçte çalışır, kameradan kare alıp analiz eder.

Ana uygulama (heatmap/dedektorler/kamera.py) bu dosyayı alt süreç olarak başlatır
ve ÇIKTISINI satır satır okur. Her gözlem tek satırlık bir JSON'dur:

    {"zaman": 1794860000.0, "yuz_var": true, "pitch": -12.5, "yaw": 3.1,
     "telefon_var": false, "hata": null}

Neden ayrı süreç? MediaPipe yeni Python sürümlerine geç gelir; bu işçi kendi
sanal ortamında (örn. Python 3.12, .venv-kamera) çalışabilir, ana uygulama
Python 3.14'te kalır. Ayrıca kamera tarafı çökerse takip etkilenmez.

--------------------------------------------------------------------
GİZLİLİK KURALLARI (tests/test_kamera.py bu dosyayı tarar):
  1. Kare ASLA diske yazılmaz.
  2. Kare ASLA ağa gönderilmez; bu dosya ağ kütüphanesi kullanmaz.
  3. Kare analiz biter bitmez silinir. Dışarı çıkan tek şey yukarıdaki JSON'dur.
--------------------------------------------------------------------

Bu dosya ana uygulamadan HİÇBİR ŞEY içe aktarmaz (kendi ortamında çalışabilsin diye).

Kullanım:
    python isci.py --model modeller/face_landmarker.task [--aralik 2] [--kamera 0]
    python isci.py --sahte senaryo        # kamera ve MediaPipe olmadan deneme (testler için)

DURUM: Sahte mod test edildi. Gerçek kamera + MediaPipe kısmı HENÜZ GERÇEK KAMERAYLA
DENENMEDİ; ilk çalıştırmada açı işaretini ve değerlerini kontrol et (SONRAKI_ADIMLAR.md 1.4).
"""

import argparse
import json
import math
import os
import sys
import time


def yaz(gozlem: dict) -> None:
    """Gözlemi tek satır JSON olarak yazar. flush şart: yoksa ana uygulama geç görür.

    ensure_ascii=True: Türkçe karakterler ş gibi kaçış dizisine çevrilir; Windows'ta
    borunun kod sayfası ne olursa olsun JSON bozulmadan okunur.
    """
    print(json.dumps(gozlem, ensure_ascii=True), flush=True)


def gozlem(yuz_var=None, pitch=None, yaw=None, telefon_var=None, hata=None) -> dict:
    return {"zaman": time.time(), "yuz_var": yuz_var, "pitch": pitch, "yaw": yaw,
            "telefon_var": telefon_var, "hata": hata}


# =====================================================================
#  Sahte mod: kamera olmadan, ana uygulamanın alt süreç hattını denemek için
# =====================================================================
SENARYOLAR = {
    # Her öğe: (kaç gözlem, gözlem alanları)
    "masada": [(10_000, {"yuz_var": True, "pitch": 0.0, "yaw": 0.0, "telefon_var": False})],
    "yok": [(10_000, {"yuz_var": False, "telefon_var": False})],
    "not_aliyor": [(10_000, {"yuz_var": True, "pitch": -30.0, "yaw": 0.0, "telefon_var": False})],
    "telefon": [(10_000, {"yuz_var": True, "pitch": -30.0, "yaw": 0.0, "telefon_var": True})],
    "hata": [(10_000, {"hata": "Kamera açılamadı (sahte)"})],
}


def sahte_calistir(senaryo: str, aralik: float) -> None:
    for adet, alanlar in SENARYOLAR[senaryo]:
        for _ in range(adet):
            yaz(gozlem(**alanlar))
            time.sleep(aralik)


# =====================================================================
#  Gerçek mod: OpenCV ile kare al, MediaPipe Face Landmarker ile analiz et
# =====================================================================
def _acilar(matris) -> tuple[float, float]:
    """4x4 yüz dönüşüm matrisinden (pitch, yaw) açısını derece olarak çıkarır.

    pitch < 0 : kafa aşağı eğik (işaret kameraya göre ters olabilir; kalibrasyon bunu dengeler)
    ❓ İşaret ve eksen sırası gerçek kamerayla doğrulanmalı.
    """
    r = [[float(matris[i][j]) for j in range(3)] for i in range(3)]
    pitch = math.degrees(math.atan2(r[2][1], r[2][2]))
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, -r[2][0]))))
    return pitch, yaw


def gercek_calistir(model_yolu: str, aralik: float, kamera_no: int) -> None:
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except ImportError as hata:
        yaz(gozlem(hata=f"Kütüphane eksik: {hata.name} (kamera_kur.bat çalıştırılmalı)"))
        return

    try:
        secenekler = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_yolu),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            output_facial_transformation_matrixes=True,
        )
        bulucu = vision.FaceLandmarker.create_from_options(secenekler)
    except Exception as hata:  # Model dosyası yok / bozuk
        yaz(gozlem(hata=f"Model yüklenemedi: {hata}"))
        return

    # CAP_DSHOW: Windows'ta kamerayı daha hızlı açar.
    kamera = cv2.VideoCapture(kamera_no, cv2.CAP_DSHOW)
    try:
        while True:
            if not kamera.isOpened():
                yaz(gozlem(hata="Kamera açılamadı (başka bir uygulama kullanıyor olabilir)"))
                time.sleep(10)
                kamera.open(kamera_no, cv2.CAP_DSHOW)
                continue
            basarili, kare = kamera.read()
            if not basarili:
                yaz(gozlem(hata="Kameradan kare alınamadı"))
                time.sleep(aralik)
                continue

            # Analiz: kare yalnızca bu blokta yaşar.
            rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
            sonuc = bulucu.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            del kare, rgb  # Kareyi hemen bırak

            if not sonuc.face_landmarks:
                yaz(gozlem(yuz_var=False, telefon_var=False))
            else:
                pitch = yaw = None
                if sonuc.facial_transformation_matrixes:
                    pitch, yaw = _acilar(sonuc.facial_transformation_matrixes[0])
                # Telefon nesne tespiti henüz yok (SONRAKI_ADIMLAR.md 1.4-B): bilinmiyor.
                yaz(gozlem(yuz_var=True, pitch=pitch, yaw=yaw, telefon_var=None))
            time.sleep(aralik)
    finally:
        kamera.release()  # Kamera ışığı sönsün


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Heatmap kamera işçisi")
    ayristirici.add_argument("--model", default="modeller/face_landmarker.task")
    ayristirici.add_argument("--aralik", type=float, default=2.0, help="İki kare arası saniye")
    ayristirici.add_argument("--kamera", type=int, default=0, help="Kamera numarası")
    ayristirici.add_argument("--sahte", choices=sorted(SENARYOLAR), help="Kamera olmadan sahte gözlem üret")
    secim = ayristirici.parse_args()
    try:
        if secim.sahte:
            sahte_calistir(secim.sahte, secim.aralik)
        else:
            gercek_calistir(secim.model, secim.aralik, secim.kamera)
    except (KeyboardInterrupt, BrokenPipeError, OSError):
        # Ana uygulama kapandı (boru kapandı). Windows'ta bu OSError olarak gelir.
        # Çıkışta Python'un tekrar yazmaya çalışıp hata basmaması için çıktıyı boşa yönlendir.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
