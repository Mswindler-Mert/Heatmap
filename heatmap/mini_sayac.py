"""Her zaman üstte duran, sürüklenebilir, yarı saydam mini masaüstü sayacı.

Kullanıcı istediği zaman tepsi menüsünden veya web arayüzünden açıp kapatabilir.
Ek kütüphane gerektirmez (Python ile gelen tkinter kullanılır). Pencere başlığı
"Takip Paneli · Mini Sayaç" olduğu için üzerine tıklamak/sürüklemek sayacı kesmez.

GİZLİLİK: Mini sayaçta ham pencere/sekme başlıkları ASLA gösterilmez; yalnızca
bugünkü çalışma süresi, hedef yüzdesi ve genel durum (çalışıyor/durdu) görünür.
"""

from collections.abc import Callable
import threading
import time
import webbrowser

MINI_SAYAC_BASLIK = "Takip Paneli · Mini Sayaç"

# Koyu tema renkleri (web arayüzüyle uyumlu)
RENK_ZEMIN = "#0f141e"
RENK_KENAR = "#253147"
RENK_RAY = "#1d2638"
RENK_YAZI = "#eef2f8"
RENK_SOLUK = "#8d99b2"
RENK_YESIL = "#3ecf8e"
RENK_SARI = "#fbbf24"
RENK_KIRMIZI = "#f87171"
RENK_MAVI = "#38bdf8"


def saat_bicimi(sn: int) -> str:
    """3725 -> '01:02:05'."""
    sn = max(0, int(sn))
    return f"{sn // 3600:02d}:{(sn % 3600) // 60:02d}:{sn % 60:02d}"


def sure_kisa(sn: int) -> str:
    """Kalan süre için kısa Türkçe metin: '1 sa 12 dk' veya '18 dk'."""
    sn = max(0, int(sn))
    if sn < 60:
        return f"{sn} sn"
    saat, dk = sn // 3600, (sn % 3600) // 60
    return f"{saat} sa {dk} dk" if saat else f"{dk} dk"


def mini_gorunum_verisi(durum: dict, hedef_sn: int, odak_sn: int | None = None) -> dict:
    """Takipçi durumundan mini pencerede gösterilecek metin ve renkleri üretir (saf fonksiyon)."""
    sn = int(durum.get("bugun_ders_sn", 0))
    if durum.get("duraklatildi"):
        nokta, durum_yazi = RENK_SOLUK, "Duraklatıldı"
    elif durum.get("calisiyor"):
        nokta, durum_yazi = RENK_YESIL, "Çalışma sayılıyor"
    elif durum.get("hukum") == "belirsiz":
        nokta, durum_yazi = RENK_SARI, "Belirsiz"
    else:
        nokta, durum_yazi = RENK_KIRMIZI, "Sayaç durdu"

    if hedef_sn > 0:
        oran = sn / hedef_sn
        yuzde = round(oran * 100)
        yuzde_yazi = f"%{yuzde}"
        cubuk_oran = min(1.0, max(0.0, oran))
        if sn >= hedef_sn:
            cubuk_renk = RENK_SARI
            hedef_yazi = "Hedef tamam!"
        else:
            cubuk_renk = RENK_YESIL
            hedef_yazi = f"Kalan {sure_kisa(hedef_sn - sn)}"
    else:
        yuzde_yazi = ""
        cubuk_oran = 0.0
        cubuk_renk = RENK_YESIL
        hedef_yazi = ""

    alt_sol = f"Odak {saat_bicimi(odak_sn)}" if odak_sn is not None else durum_yazi
    return {
        "zaman": saat_bicimi(sn),
        "nokta_renk": nokta,
        "yuzde": yuzde_yazi,
        "cubuk_oran": cubuk_oran,
        "cubuk_renk": cubuk_renk,
        "alt_sol": alt_sol,
        "alt_sag": hedef_yazi,
        "duraklatildi": bool(durum.get("duraklatildi")),
    }


class MiniSayac:
    """Tkinter tabanlı kayan mini sayaç penceresinin yaşam döngüsünü yönetir.

    Tkinter yalnızca kendi oluşturduğu thread içinden çağrılır; dışarıdan ac() / kapat()
    çağrıları thread güvenlidir.
    """

    def __init__(self, takipci, hedef_kaynagi: Callable[[], int], adres: str):
        self.takipci = takipci
        self.hedef_kaynagi = hedef_kaynagi
        self.adres = adres
        self._kilit = threading.Lock()
        self._thread: threading.Thread | None = None
        self._acik = False
        self._kapat_istendi = False
        self._konum: tuple[int, int] | None = None  # Son bırakılan ekran konumu (x, y)

    @property
    def acik(self) -> bool:
        with self._kilit:
            return self._acik

    def ac(self) -> bool:
        """Mini sayacı açar (zaten açıksa dokunmaz). Açık durumunu döndürür."""
        with self._kilit:
            if self._acik:
                return True
            self._kapat_istendi = False
            self._acik = True
            self._thread = threading.Thread(target=self._pencere_dongusu, name="mini-sayac", daemon=True)
            self._thread.start()
            return True

    def kapat(self) -> bool:
        """Mini sayacı kapatır (Heatmap çalışmaya devam eder)."""
        with self._kilit:
            self._kapat_istendi = True
            thread = self._thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.5)
        return self.acik

    def degistir(self) -> bool:
        """Açıksa kapatır, kapalıysa açar; yeni durumu döndürür."""
        return self.kapat() if self.acik else self.ac()

    def _pencere_dongusu(self) -> None:
        try:
            import tkinter as tk
        except Exception as hata:
            print(f"UYARI: Mini sayaç açılamadı ({hata}).", flush=True)
            with self._kilit:
                self._acik = False
            return

        genislik, yukseklik = 248, 86
        kok = tk.Tk()
        kok.title(MINI_SAYAC_BASLIK)
        kok.overrideredirect(True)           # Başlık çubuğusuz sade kart
        kok.attributes("-topmost", True)     # Her zaman üstte
        try:
            kok.attributes("-alpha", 0.93)   # Hafif yarı saydam
        except tk.TclError:
            pass
        kok.configure(bg=RENK_KENAR)

        # Konum: daha önce sürüklendiyse orası, yoksa ekranın sağ alt köşesi (görev çubuğunun üstü)
        if self._konum is not None:
            x, y = self._konum
        else:
            x = max(20, kok.winfo_screenwidth() - genislik - 24)
            y = max(20, kok.winfo_screenheight() - yukseklik - 64)
        kok.geometry(f"{genislik}x{yukseklik}+{x}+{y}")

        # 1px kenarlık etkisi için iç çerçeve
        ic = tk.Frame(kok, bg=RENK_ZEMIN, padx=12, pady=9)
        ic.pack(fill="both", expand=True, padx=1, pady=1)

        # Üst satır: durum noktası + sayaç + yüzde + küçük düğmeler
        ust = tk.Frame(ic, bg=RENK_ZEMIN)
        ust.pack(fill="x")

        nokta_tuval = tk.Canvas(ust, width=12, height=12, bg=RENK_ZEMIN, highlightthickness=0)
        nokta_daire = nokta_tuval.create_oval(2, 2, 10, 10, fill=RENK_SOLUK, outline="")
        nokta_tuval.pack(side="left", padx=(0, 7))

        sayac_etiket = tk.Label(ust, text="00:00:00", bg=RENK_ZEMIN, fg=RENK_YAZI,
                                font=("Segoe UI", 17, "bold"))
        sayac_etiket.pack(side="left")

        yuzde_etiket = tk.Label(ust, text="", bg=RENK_ZEMIN, fg=RENK_YESIL,
                                font=("Segoe UI", 10, "bold"))
        yuzde_etiket.pack(side="left", padx=(6, 0), pady=(4, 0))

        # İsteğe bağlı dahili odak kronometresi (tıkla başlat / durdur / sıfırla)
        odak = {"aktif": False, "baslangic": 0.0}

        def odak_degistir():
            if not odak["aktif"]:
                odak["aktif"] = True
                odak["baslangic"] = time.monotonic()
                odak_dugme.configure(fg=RENK_MAVI)
            else:
                odak["aktif"] = False
                odak_dugme.configure(fg=RENK_SOLUK)

        def duraklat_degistir():
            self.takipci.duraklat(not self.takipci.duraklatildi)

        def pencereyi_kapat():
            with self._kilit:
                self._kapat_istendi = True

        dugme_stili = {"bg": RENK_ZEMIN, "fg": RENK_SOLUK, "activebackground": RENK_RAY,
                       "activeforeground": RENK_YAZI, "bd": 0, "highlightthickness": 0,
                       "cursor": "hand2", "font": ("Segoe UI", 10)}

        kapat_dugme = tk.Button(ust, text="✕", command=pencereyi_kapat, **dugme_stili)
        kapat_dugme.pack(side="right", padx=(2, 0))

        duraklat_dugme = tk.Button(ust, text="⏸", command=duraklat_degistir, **dugme_stili)
        duraklat_dugme.pack(side="right", padx=(2, 0))

        odak_dugme = tk.Button(ust, text="⏱", command=odak_degistir, **dugme_stili)
        odak_dugme.pack(side="right", padx=(2, 0))

        # Orta: ince günlük hedef ilerleme çubuğu
        cubuk_genislik = genislik - 26
        cubuk = tk.Canvas(ic, width=cubuk_genislik, height=5, bg=RENK_RAY, highlightthickness=0)
        cubuk_dolgu = cubuk.create_rectangle(0, 0, 0, 5, fill=RENK_YESIL, outline="")
        cubuk.pack(fill="x", pady=(7, 5))

        # Alt satır: durum (veya odak kronometresi) + kalan hedef
        alt = tk.Frame(ic, bg=RENK_ZEMIN)
        alt.pack(fill="x")
        alt_sol = tk.Label(alt, text="bağlanıyor…", bg=RENK_ZEMIN, fg=RENK_SOLUK, font=("Segoe UI", 8.5))
        alt_sol.pack(side="left")
        alt_sag = tk.Label(alt, text="", bg=RENK_ZEMIN, fg=RENK_SOLUK, font=("Segoe UI", 8.5))
        alt_sag.pack(side="right")

        # Sürükle-taşı ve çift tıkla arayüzü aç
        surukle = {"x": 0, "y": 0}

        def basla(olay):
            surukle["x"], surukle["y"] = olay.x, olay.y

        def tasi(olay):
            nx = kok.winfo_x() + (olay.x - surukle["x"])
            ny = kok.winfo_y() + (olay.y - surukle["y"])
            kok.geometry(f"+{nx}+{ny}")
            self._konum = (nx, ny)

        def arayuzu_ac(_olay=None):
            webbrowser.open(self.adres)

        for eleman in (ic, ust, alt, nokta_tuval, sayac_etiket, yuzde_etiket, cubuk, alt_sol, alt_sag):
            eleman.bind("<ButtonPress-1>", basla)
            eleman.bind("<B1-Motion>", tasi)
            eleman.bind("<Double-Button-1>", arayuzu_ac)

        def guncelle():
            if self._kapat_istendi:
                kok.destroy()
                return
            try:
                odak_sn = int(time.monotonic() - odak["baslangic"]) if odak["aktif"] else None
                v = mini_gorunum_verisi(self.takipci.durum(), self.hedef_kaynagi(), odak_sn)
                nokta_tuval.itemconfig(nokta_daire, fill=v["nokta_renk"])
                sayac_etiket.configure(text=v["zaman"])
                yuzde_etiket.configure(text=v["yuzde"], fg=v["cubuk_renk"])
                cubuk.coords(cubuk_dolgu, 0, 0, round(cubuk_genislik * v["cubuk_oran"]), 5)
                cubuk.itemconfig(cubuk_dolgu, fill=v["cubuk_renk"])
                alt_sol.configure(text=v["alt_sol"], fg=RENK_MAVI if odak["aktif"] else RENK_SOLUK)
                alt_sag.configure(text=v["alt_sag"])
                duraklat_dugme.configure(text="▶" if v["duraklatildi"] else "⏸")
            except Exception:
                pass
            kok.after(400, guncelle)

        kok.after(50, guncelle)
        try:
            kok.mainloop()
        finally:
            with self._kilit:
                self._acik = False
                self._kapat_istendi = False
