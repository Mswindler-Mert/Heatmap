"""Modül 4 - Kamera dedektörü.

Kameraya kendisi DOKUNMAZ. Kamera analizi ayrı bir süreçte, kamera_isci/isci.py
içinde yapılır (MediaPipe kendi Python ortamında çalışabilsin diye). Bu modül:

  1. İşçiyi alt süreç olarak başlatır ve çökerse artan aralıklarla yeniden başlatır.
  2. İşçinin her satırda yazdığı küçük JSON'u (yüz var mı, kafa açısı...) okur.
  3. Süre koşullarını uygular: "yüz 30 sn'dir yok", "kafa 10 dk'dır aşağıda"...
  4. Karar motoruna bir Sinyal verir (detay["kamera_durumu"] ve detay["masada"]).

--------------------------------------------------------------------
GİZLİLİK KURALLARI:
  1. Kamera karesi ASLA diske yazılmaz, ASLA ağa gönderilmez (bkz. kamera_isci/isci.py).
  2. Bu sürece görüntü hiç gelmez; yalnızca evet/hayır ve açı değerleri gelir.
  3. Veritabanına giden tek şey, kamera kararı verdiğinde oturumun kısa açıklamasıdır
     ("Kamerada yüz görünmüyor" gibi). Açı değerleri yalnızca canlı durumda gösterilir.
--------------------------------------------------------------------

kamera_durumu değerleri ve verilen hüküm:

    ekrana_bakiyor : yüz var, kafa düz                          -> FIKRIM_YOK
    asagi_bakiyor  : yüz var, kafa aşağıda (not / telefon?)     -> FIKRIM_YOK
    kayboldu       : yüz kısa süredir görünmüyor                -> FIKRIM_YOK
    yok            : yüz `yuz_yok_esik_sn` boyunca görünmüyor    -> DERS_DEGIL
    telefon        : telefon görüldü, `telefon_esik_sn` doldu    -> DERS_DEGIL
    bilinmiyor     : işçi çalışmıyor / veri bayat / kamera meşgul -> FIKRIM_YOK
    kapali         : kullanıcı kamerayı arayüzden/tepsiden kapattı -> FIKRIM_YOK

Kamera hiçbir zaman "ders" demez; yalnızca veto eder ya da (motor.py) boşta kalma
kuralını askıya alır. Kuralların nasıl birleştiği motor.anlik_karar() içinde.
"""

import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from heatmap.ayarlar import KOK, PAKETLI, VERI_KLASORU
from heatmap.sinyal import DERS_DEGIL, FIKRIM_YOK, Dedektor, Sinyal

ISCI_BETIGI = KOK / "kamera_isci" / "isci.py"
KAMERA_VENV_PYTHON = KOK / ".venv-kamera" / "Scripts" / "python.exe"
BAYAT_SN = 10  # Bundan eski gözleme güvenme (işçi takıldı ya da kapandı)
# Arayüzdeki "Kalibre et" düğmesinin sonucu burada saklanır (data/ Git dışıdır).
# Ayar dosyasına yazmıyoruz: program config.toml'u yeniden yazarsa senin yorumların silinirdi.
KALIBRASYON_DOSYASI = VERI_KLASORU / "kamera_kalibrasyon.json"


def isci_komutu(bolum: dict, paketli: bool = PAKETLI) -> list[str] | None:
    """Ayarlara göre işçiyi başlatacak komutu kurar.

    Tek dosya .exe olarak çalışırken sys.executable Heatmap.exe'nin kendisidir; işçiyi onunla
    başlatmak programı ikinci kez açardı. Bu durumda kamera için ayrı bir Python ortamı
    (.venv-kamera ya da [kamera] python) şarttır; yoksa None döner ve kamera "bilinmiyor" kalır.
    """
    if bolum.get("python"):
        python = bolum["python"]
    elif KAMERA_VENV_PYTHON.exists():
        python = str(KAMERA_VENV_PYTHON)
    elif paketli:
        return None
    else:
        python = sys.executable
    komut = [python, str(ISCI_BETIGI), "--aralik", str(bolum.get("kare_araligi_sn", 2)),
             "--kamera", str(bolum.get("kamera_no", 0)),
             "--model", str(KOK / bolum.get("model", "modeller/face_landmarker.task"))]
    if bolum.get("sahte_senaryo"):  # Kamera olmadan arayüzü denemek için
        komut += ["--sahte", bolum["sahte_senaryo"]]
    return komut


class IsciSureci:
    """Kamera işçisini alt süreç olarak çalıştırır ve son gözlemini tutar."""

    def __init__(self, komut: list[str] | None):
        """komut None ise işçi başlatılamaz (örn. .exe sürümünde kamera ortamı yok); hata bildirilir."""
        self.komut = komut
        self._kilit = threading.Lock()
        self._son: dict | None = None
        self._dur = threading.Event()
        self._surec: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def baslat(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._yonet, name="kamera-isci", daemon=True)
            self._thread.start()

    def son_gozlem(self) -> dict | None:
        with self._kilit:
            return self._son

    def _yonet(self) -> None:
        """İşçiyi çalıştırır; kapanırsa 5, 10, 20... en fazla 300 sn bekleyip yeniden başlatır."""
        if self.komut is None:
            while not self._dur.is_set():  # Sürekli yenile ki "bayat veri" sayılmasın
                with self._kilit:
                    self._son = {"zaman": time.time(), "hata": "Kamera için ayrı Python ortamı gerekli "
                                 "(kamera_kur.bat ya da [kamera] python ayarı)"}
                self._dur.wait(5)
            return
        bekleme = 5
        while not self._dur.is_set():
            baslangic = time.time()
            try:
                self._surec = subprocess.Popen(
                    self.komut, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                    # Windows'ta konsol penceresi açılmasın
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                for satir in self._surec.stdout:  # İşçi her gözlemde bir satır yazar
                    if self._dur.is_set():
                        break
                    try:
                        gozlem = json.loads(satir.decode("ascii", errors="replace"))
                    except ValueError:
                        continue  # JSON olmayan satırı (örn. kütüphane uyarısı) yok say
                    with self._kilit:
                        self._son = gozlem
            except OSError as hata:  # Python bulunamadı vb.
                with self._kilit:
                    self._son = {"zaman": time.time(), "hata": f"Kamera işçisi başlatılamadı: {hata}"}
            finally:
                self._sureci_bitir()
            if time.time() - baslangic > 60:
                bekleme = 5  # Uzun süre çalıştıysa sayacı sıfırla
            self._dur.wait(bekleme)
            bekleme = min(bekleme * 2, 300)

    def _sureci_bitir(self) -> None:
        if self._surec is None:
            return
        if self._surec.poll() is None:
            self._surec.terminate()
            try:
                self._surec.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._surec.kill()
        if self._surec.stdout:
            self._surec.stdout.close()  # Boruyu kapat (açık dosya kalmasın)

    def kapat(self) -> None:
        """Program kapanırken: işçiyi durdur (kamera ışığı sönsün)."""
        self._dur.set()
        self._sureci_bitir()
        if self._thread:
            self._thread.join(timeout=5)


class KameraDedektoru(Dedektor):
    ad = "kamera"

    def __init__(self, ayarlar: dict, kaynak=None, saat=time.time, kalibrasyon_dosyasi: Path = KALIBRASYON_DOSYASI):
        """kaynak: son_gozlem() / baslat() / kapat() metotları olan nesne (testlerde sahte verilir).
        saat  : şimdiki zamanı veren fonksiyon (testlerde sahte saat verilir).
        kalibrasyon_dosyasi: "Kalibre et" sonucunun saklandığı dosya (testlerde geçici dosya)."""
        bolum = ayarlar.get("kamera", {})
        self.yuz_yok_esik_sn = bolum.get("yuz_yok_esik_sn", 30)
        self.telefon_esik_sn = bolum.get("telefon_esik_sn", 20)
        self.not_alma_esik_sn = bolum.get("not_alma_esik_sn", 600)
        self.asagi_fark_derece = bolum.get("asagi_fark_derece", 18)
        self.kalibrasyon_dosyasi = Path(kalibrasyon_dosyasi)
        # Kalibrasyon: ekrana normal bakarkenki açı. Önce düğmeyle ölçülen değer, yoksa ayar dosyası.
        self.ekran_pitch = self._kalibrasyonu_oku(bolum.get("ekran_pitch", 0.0))
        # Kullanıcı kamerayı kapatıp açınca işçi yeniden kurulabilsin diye "fabrika" tutulur.
        self._kaynak_fabrikasi = None if kaynak is not None else (lambda: IsciSureci(isci_komutu(bolum)))
        self.kaynak = kaynak if kaynak is not None else self._kaynak_fabrikasi()
        self.saat = saat
        self.acik = True        # Kullanıcı arayüzden/tepsiden kapatabilir (kamera ışığı söner)
        self._baslatildi = False
        # "Ne zamandan beri" sayaçları (None = o durum şu an yok)
        self._yok_baslangic = None
        self._asagi_baslangic = None
        self._telefon_baslangic = None

    def _sifirla(self) -> None:
        self._yok_baslangic = self._asagi_baslangic = self._telefon_baslangic = None

    # ------------------------------------------------------------------
    #  Aç / kapat ve kalibrasyon (arayüz ve tepsi menüsü kullanır)
    # ------------------------------------------------------------------
    def ayarla_acik(self, acik: bool) -> None:
        """Kamerayı kapatır (işçi durur, kamera ışığı söner) ya da yeniden açar."""
        if acik == self.acik:
            return
        self.acik = acik
        if not acik:
            if self._baslatildi:
                self.kaynak.kapat()
                self._baslatildi = False
            if self._kaynak_fabrikasi:  # Kapanan işçi yeniden başlatılamaz; yenisini hazırla
                self.kaynak = self._kaynak_fabrikasi()
            self._sifirla()

    def _kalibrasyonu_oku(self, varsayilan: float) -> float:
        try:
            return float(json.loads(self.kalibrasyon_dosyasi.read_text(encoding="utf-8"))["ekran_pitch"])
        except (OSError, ValueError, KeyError, TypeError):
            return float(varsayilan)

    def kalibre_et(self, sure_sn: float = 6.0, bekle=time.sleep) -> float:
        """`sure_sn` boyunca kafa açısını ölçer, ortancasını "ekrana bakma açısı" olarak kaydeder.

        Kullanıcı bu sırada ekrana normal bakmalı. Yeni ekran açısını döndürür;
        yeterli ölçüm yoksa (kamera kapalı, yüz görünmüyor) ValueError verir.
        """
        if not self.acik or not self._baslatildi:
            raise ValueError("Kamera kapalı ya da henüz başlamadı")
        ornekler, son_zaman = [], None
        bitis = self.saat() + sure_sn
        while self.saat() < bitis:
            g = self.kaynak.son_gozlem() or {}
            if g.get("yuz_var") and g.get("pitch") is not None and g.get("zaman") != son_zaman:
                ornekler.append(g["pitch"])
                son_zaman = g.get("zaman")
            bekle(0.25)
        if len(ornekler) < 2:
            raise ValueError("Yeterli ölçüm alınamadı: kamera açık ve yüzün görünür olmalı")
        self.ekran_pitch = round(statistics.median(ornekler), 1)
        self.kalibrasyon_dosyasi.parent.mkdir(parents=True, exist_ok=True)
        self.kalibrasyon_dosyasi.write_text(json.dumps({"ekran_pitch": self.ekran_pitch}), encoding="utf-8")
        return self.ekran_pitch

    def durum_bilgisi(self) -> dict:
        """Arayüz için canlı bilgi. Açı yalnızca burada gösterilir, kaydedilmez."""
        g = self.kaynak.son_gozlem() if self._baslatildi else None
        taze = bool(g) and not g.get("hata") and self.saat() - g.get("zaman", 0) <= BAYAT_SN
        return {
            "acik": self.acik,
            "ekran_pitch": self.ekran_pitch,
            "asagi_esigi": round(self.ekran_pitch - self.asagi_fark_derece, 1),
            "anlik_pitch": round(g["pitch"], 1) if taze and g.get("pitch") is not None else None,
            "hata": (g or {}).get("hata"),
        }

    # ------------------------------------------------------------------
    def oku(self, onceki: dict[str, Sinyal]) -> Sinyal:
        if not self.acik:
            return Sinyal(self.ad, FIKRIM_YOK, "Kamera kapalı (sen kapattın)",
                          {"kamera_durumu": "kapali", "masada": None})
        if not self._baslatildi:  # İşçiyi ilk okumada başlat: program hızlı açılsın
            self.kaynak.baslat()
            self._baslatildi = True

        simdi = self.saat()
        g = self.kaynak.son_gozlem()
        if g is None or g.get("hata") or simdi - g.get("zaman", 0) > BAYAT_SN:
            self._sifirla()
            aciklama = (g or {}).get("hata") or "Kamera verisi yok (işçi başlıyor ya da çalışmıyor)"
            return Sinyal(self.ad, FIKRIM_YOK, aciklama, {"kamera_durumu": "bilinmiyor", "masada": None})

        # --- Yüz yok ---------------------------------------------------
        if g.get("yuz_var") is False:
            self._asagi_baslangic = self._telefon_baslangic = None
            if self._yok_baslangic is None:
                self._yok_baslangic = simdi
            sure = simdi - self._yok_baslangic
            if sure >= self.yuz_yok_esik_sn:
                # sure_sn: motor geçişi yüzün kaybolduğu ana çeker (bkz. motor.Durum.geriye_sn)
                return Sinyal(self.ad, DERS_DEGIL, "Kamerada yüz görünmüyor",
                              {"kamera_durumu": "yok", "masada": False, "sure_sn": sure})
            return Sinyal(self.ad, FIKRIM_YOK, f"Yüz {round(sure)} sn'dir görünmüyor",
                          {"kamera_durumu": "kayboldu", "masada": False})
        self._yok_baslangic = None

        # --- Yüz var: telefon ve kafa açısı -------------------------------
        if g.get("telefon_var") is True:
            if self._telefon_baslangic is None:
                self._telefon_baslangic = simdi
            if simdi - self._telefon_baslangic >= self.telefon_esik_sn:
                return Sinyal(self.ad, DERS_DEGIL, "Telefona bakıyor gibi",
                              {"kamera_durumu": "telefon", "masada": True,
                               "sure_sn": simdi - self._telefon_baslangic})
        else:
            self._telefon_baslangic = None

        pitch = g.get("pitch")
        asagi = pitch is not None and pitch < self.ekran_pitch - self.asagi_fark_derece
        aci = f" (açı {pitch:.0f}°)" if pitch is not None else ""
        if asagi:
            if self._asagi_baslangic is None:
                self._asagi_baslangic = simdi
            sure = simdi - self._asagi_baslangic
            return Sinyal(self.ad, FIKRIM_YOK, f"Masada, {round(sure)} sn'dir aşağı bakıyor{aci}", {
                "kamera_durumu": "asagi_bakiyor", "masada": True,
                "not_alma_doldu": sure >= self.not_alma_esik_sn,
            })
        self._asagi_baslangic = None
        return Sinyal(self.ad, FIKRIM_YOK, f"Masada, ekrana bakıyor{aci}",
                      {"kamera_durumu": "ekrana_bakiyor", "masada": True})

    def kapat(self) -> None:
        if self._baslatildi:
            self.kaynak.kapat()
