"""Windows açılışında otomatik başlatma.

Windows, oturum açılınca şu kayıt defteri anahtarındaki komutları çalıştırır:
    HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

Buraya "Heatmap" adında bir değer ekleyince program her açılışta kendiliğinden
başlar; değeri silince başlamaz. HKEY_CURRENT_USER yalnızca SENİN kullanıcı
hesabını etkiler ve yönetici izni gerektirmez. (Görev Yöneticisi > Başlangıç
uygulamaları sekmesinde de "Heatmap" olarak görünür ve oradan da kapatılabilir.)

Komut, konsol penceresi açmayan pythonw.exe ile proje klasöründeki
baslat.pyw dosyasını çalıştırır. --sessiz bayrağı, açılışta tarayıcının
açılmasını engeller.
"""

import sys
import winreg  # Python'un standart kütüphanesi; kayıt defterine erişim
from pathlib import Path

from heatmap.ayarlar import KOK

CALISTIR_ANAHTARI = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEGER_ADI = "Heatmap"
BASLATICI = KOK / "baslat.pyw"


def baslatma_komutu() -> str:
    """Kayıt defterine yazılacak komut. Örn:
    "C:\\...\\.venv\\Scripts\\pythonw.exe" "C:\\...\\baslat.pyw" --sessiz
    """
    # Program python.exe ile (terminalden) çalışıyor olsa bile açılışta
    # konsol penceresi çıkmasın diye yanındaki pythonw.exe'yi tercih ediyoruz.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    return f'"{pythonw}" "{BASLATICI}" --sessiz'


def _kayitli_komut(anahtar: str) -> str | None:
    """Kayıt defterindeki Heatmap değerini okur; yoksa None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, anahtar, 0, winreg.KEY_READ) as k:
            deger, _tur = winreg.QueryValueEx(k, DEGER_ADI)
            return deger
    except FileNotFoundError:  # Anahtar ya da değer yok
        return None


def acik_mi(anahtar: str = CALISTIR_ANAHTARI) -> bool:
    """Otomatik başlatma açık mı?"""
    return _kayitli_komut(anahtar) is not None


def ac(anahtar: str = CALISTIR_ANAHTARI) -> None:
    """Otomatik başlatmayı açar (zaten açıksa komutu günceller)."""
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, anahtar, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, DEGER_ADI, 0, winreg.REG_SZ, baslatma_komutu())


def kapat(anahtar: str = CALISTIR_ANAHTARI) -> None:
    """Otomatik başlatmayı kapatır (zaten kapalıysa bir şey yapmaz)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, anahtar, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, DEGER_ADI)
    except FileNotFoundError:
        pass


def ayarla(deger: bool, anahtar: str = CALISTIR_ANAHTARI) -> bool:
    """Açar ya da kapatır; yeni durumu döndürür."""
    ac(anahtar) if deger else kapat(anahtar)
    return acik_mi(anahtar)


def guncel_tut(anahtar: str = CALISTIR_ANAHTARI) -> bool:
    """Açıksa ama kayıtlı komut eskiyse (örn. proje klasörü taşındıysa) düzeltir.

    Program her açılışta bunu çağırır. Düzeltme yapıldıysa True döndürür.
    """
    kayitli = _kayitli_komut(anahtar)
    if kayitli is not None and kayitli != baslatma_komutu():
        ac(anahtar)
        return True
    return False
