"""Windows'a sorulan iki soru burada: "Önde hangi pencere var?" ve
"Klavye/fare ne zamandır kullanılmıyor?".

Ek paket kurmamak için Python'un standart `ctypes` kütüphanesiyle doğrudan
Windows'un kendi fonksiyonlarını (user32.dll, kernel32.dll) çağırıyoruz.
ctypes'ta her fonksiyon için parametre ve dönüş tiplerini elle belirtmek
gerekir; aşağıdaki `argtypes` / `restype` satırları bunun için.
"""

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- Fonksiyon imzaları -------------------------------------------------
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

# EnumChildWindows bir pencerenin alt pencerelerini tek tek bu tipte bir fonksiyona verir.
ALT_PENCERE_FONKSIYONU = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows.argtypes = [wintypes.HWND, ALT_PENCERE_FONKSIYONU, wintypes.LPARAM]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetTickCount.restype = wintypes.DWORD

# Bir sürecin sadece adını öğrenmeye yeten en düşük yetki.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Microsoft Store (UWP) uygulamalarının penceresi bu "çerçeve" sürecine aittir;
# asıl uygulama (örn. Ayarlar, Hesap Makinesi) çerçevenin İÇİNDEKİ bir alt penceredir.
UWP_CERCEVE = "applicationframehost.exe"


class LASTINPUTINFO(ctypes.Structure):
    """GetLastInputInfo fonksiyonunun doldurduğu yapı."""

    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _surec_adi(pid: int) -> str:
    """Süreç numarasından (PID) exe adını bulur, örn. 'Code.exe'."""
    tutamac = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not tutamac:
        return ""  # Erişim izni yok (örn. bazı sistem süreçleri)
    try:
        tampon = ctypes.create_unicode_buffer(1024)
        boyut = wintypes.DWORD(len(tampon))
        if kernel32.QueryFullProcessImageNameW(tutamac, 0, tampon, ctypes.byref(boyut)):
            return os.path.basename(tampon.value)  # Tam yoldan sadece dosya adını al
        return ""
    finally:
        kernel32.CloseHandle(tutamac)


def _pencere_pid(pencere) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(pencere, ctypes.byref(pid))
    return pid.value


def _uwp_uygulama_pid(cerceve, cerceve_pid: int) -> int | None:
    """Store uygulaması çerçevesinin içindeki, BAŞKA bir sürece ait ilk alt pencerenin PID'i."""
    bulunan = []

    def alt_pencere(cocuk, _parametre):
        pid = _pencere_pid(cocuk)
        if pid and pid != cerceve_pid:
            bulunan.append(pid)
            return False  # Bulduk, aramayı durdur
        return True       # Devam et

    # Geri çağırma nesnesi, çağrı süresince bir değişkende tutulmalı (çöp toplanmasın).
    geri_cagirma = ALT_PENCERE_FONKSIYONU(alt_pencere)
    user32.EnumChildWindows(cerceve, geri_cagirma, 0)
    return bulunan[0] if bulunan else None


def pencerenin_sureci(pencere) -> str:
    """Pencerenin ait olduğu sürecin exe adı. Store uygulamalarında çerçeve yerine asıl uygulama."""
    pid = _pencere_pid(pencere)
    ad = _surec_adi(pid)
    if ad.lower() == UWP_CERCEVE:
        uygulama_pid = _uwp_uygulama_pid(pencere, pid)
        if uygulama_pid:
            ad = _surec_adi(uygulama_pid) or ad
    return ad


def aktif_pencereyi_oku() -> tuple[str, str]:
    """Öndeki pencerenin (süreç adı, pencere başlığı) ikilisini döndürür.

    Pencere yoksa ya da okunamazsa boş metinler döner.
    """
    pencere = user32.GetForegroundWindow()
    if not pencere:
        return "", ""

    uzunluk = user32.GetWindowTextLengthW(pencere)
    tampon = ctypes.create_unicode_buffer(uzunluk + 1)
    user32.GetWindowTextW(pencere, tampon, uzunluk + 1)
    baslik = tampon.value

    return pencerenin_sureci(pencere), baslik


def bosta_suresini_oku() -> float:
    """Son klavye/fare hareketinden beri geçen süreyi saniye olarak döndürür."""
    bilgi = LASTINPUTINFO()
    bilgi.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(bilgi)):
        return 0.0
    # İki değer de "bilgisayar açıldığından beri geçen milisaniye"dir ve
    # 32 bitlik sayaç ~49 günde başa döner; maskeleme bu durumu düzeltir.
    gecen_ms = (kernel32.GetTickCount() - bilgi.dwTime) & 0xFFFFFFFF
    return gecen_ms / 1000.0
