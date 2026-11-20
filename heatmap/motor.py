"""Karar motoru: bütün sinyalleri birleştirip sayacın durumuna karar verir.

İki aşama var:

1. anlik_karar(sinyaller)  -> "TAM ŞU AN" için hüküm (tolerans yok).
2. KararMotoru.guncelle()  -> anlık hükmü tolerans süzgecinden geçirir.
   Sayacın gerçek durumu ancak yeni hüküm yeterince uzun sürerse değişir.

Motor saatin kaç olduğunu kendisi okumaz; zaman dışarıdan `simdi`
parametresiyle verilir. Böylece testlerde "15 saniye geçti" durumunu
beklemeden deneyebiliyoruz.
"""

from dataclasses import dataclass

from heatmap.sinyal import BELIRSIZ, DERS, DERS_DEGIL, DEVAM, FIKRIM_YOK, Sinyal


@dataclass(frozen=True)
class Durum:
    """Motorun bir an için vardığı sonuç. Veritabanındaki bir oturum = bir Durum'un sürdüğü zaman dilimi."""

    hukum: str          # DERS / DERS_DEGIL / BELIRSIZ (anlık kararda ayrıca DEVAM olabilir)
    baglam: str         # Oturumları birbirinden ayıran anahtar (uygulama ya da sekme)
    kaynak: str = ""    # Kararı hangi modül verdi
    aciklama: str = ""  # Neden bu karar verildi
    uygulama: str = ""  # Süreç adı, örn. "chrome.exe"
    baslik: str = ""    # Pencere / sekme başlığı
    alan_adi: str = ""  # Tarayıcıdaysa sitenin adı (eklenti kuruluysa), örn. "youtube.com"


@dataclass
class Gecis:
    """Sayacın durumu değişti: `zaman` anından itibaren geçerli durum `durum`."""

    durum: Durum
    zaman: float


# =====================================================================
#  1. AŞAMA - Anlık karar
# =====================================================================
def anlik_karar(sinyaller: dict[str, Sinyal]) -> Durum:
    """Dedektör sinyallerini birleştirip şu anki (toleranssız) durumu döndürür.

    Kural sırası:
      1. Kamera vetosu (telefon / masada değil)
      2. Boşta kalma (kamera "masada" diyorsa ya da video oynuyorsa muaf)
      3. Ekrandaki içerik (sekme başlığı ya da uygulama)
      4. Kamera düzeltmesi: uzun süre aşağı bakılıyorsa "çalışma" -> "belirsiz"
    """
    pencere = sinyaller.get("pencere")
    baslik = sinyaller.get("baslik")
    bosta = sinyaller.get("bosta")
    kamera = sinyaller.get("kamera")

    surec = pencere.detay.get("surec", "") if pencere else ""
    ham_baslik = pencere.detay.get("baslik", "") if pencere else ""

    # Video izleniyor mu? (Boşta kalma kuralını yumuşatmak için lazım.)
    video = bool(baslik and baslik.detay.get("video"))
    girdi_aktif = not (bosta and bosta.hukum == DERS_DEGIL)   # Klavye/fare yakın zamanda kullanıldı mı
    kamera_durumu = kamera.detay.get("kamera_durumu") if kamera else None
    masada = kamera.detay.get("masada") if kamera else None   # True / False / None (bilinmiyor)

    # --- Kural 1: Kamera vetosu ---------------------------------------------
    # Telefon her zaman veto eder. "Yüz yok" ise klavye/fare kullanılıyorsa uygulanmaz:
    # kamera kapatılmış, ışık kötü ya da yandan oturuyor olabilirsin; girdi yalan söylemez.
    if kamera and kamera.hukum == DERS_DEGIL and not (kamera_durumu == "yok" and girdi_aktif):
        return Durum(DERS_DEGIL, baglam="kamera", kaynak="kamera",
                     aciklama=kamera.aciklama, uygulama=surec, baslik=ham_baslik)

    # --- Kural 2: Bilgisayar başında değilse gerisinin önemi yok ---------
    if not girdi_aktif and masada is not True:
        # İstisna: video izlerken klavye/fareye dokunmamak normaldir.
        # Ancak videonun kendi (daha uzun) eşiği de aşıldıysa istisna biter.
        # (Kamera "masada" diyorsa bu kurala hiç girilmez: okuyor/izliyor/not alıyorsundur.)
        video_muafiyeti = video and not bosta.detay.get("video_esigi_asildi")
        if not video_muafiyeti:
            return Durum(DERS_DEGIL, baglam="bosta", kaynak="bosta",
                         aciklama=bosta.aciklama, uygulama="", baslik="Bilgisayar başında değil")

    # --- Kural 3: Ekrandaki içerik ----------------------------------------
    durum = _icerik_karari(pencere, baslik, surec, ham_baslik)

    # --- Kural 4: Uzun süre aşağı bakmak ----------------------------------
    # Klavye/fare boştayken kafa uzun süredir aşağıdaysa not alıyor da olabilirsin, masa altında
    # telefona bakıyor da. Kamera ayırt edemez: "çalışma" kararını "belirsiz"e çevir, sen karar ver.
    if (durum.hukum == DERS and not girdi_aktif and kamera_durumu == "asagi_bakiyor"
            and kamera.detay.get("not_alma_doldu")):
        return Durum(BELIRSIZ, baglam=durum.baglam + "|asagi", kaynak="kamera",
                     aciklama="Uzun süredir aşağı bakıyor: not mu alıyor, telefona mı bakıyor?",
                     uygulama=durum.uygulama, baslik=durum.baslik, alan_adi=durum.alan_adi)
    return durum


def _icerik_karari(pencere, baslik, surec: str, ham_baslik: str) -> Durum:
    """Ekranda ne var? Tarayıcıdaysak başlık dedektörü, değilsek pencere dedektörü konuşur."""
    if baslik and baslik.hukum != FIKRIM_YOK:
        temiz = baslik.detay.get("temiz_baslik", ham_baslik)
        # Bağlama başlığı da katıyoruz: farklı sekme = farklı oturum.
        return Durum(baslik.hukum, baglam=f"{surec}|{temiz}", kaynak="baslik",
                     aciklama=baslik.aciklama, uygulama=surec, baslik=temiz,
                     alan_adi=baslik.detay.get("alan_adi", ""))

    if pencere and pencere.hukum != FIKRIM_YOK:
        # Bağlam sadece uygulama: VS Code'da dosya değiştirmek oturumu bölmesin.
        return Durum(pencere.hukum, baglam=surec, kaynak="pencere",
                     aciklama=pencere.aciklama, uygulama=surec, baslik=ham_baslik)

    # Hiçbir modül fikir bildirmedi.
    return Durum(BELIRSIZ, baglam=surec, kaynak="motor",
                 aciklama="Hiçbir modül karar veremedi", uygulama=surec, baslik=ham_baslik)


# =====================================================================
#  2. AŞAMA - Tolerans (ani değişiklikleri süzme)
# =====================================================================
class KararMotoru:
    """Anlık kararları tolerans süresinden geçirip sayacın kalıcı durumunu tutar.

    Kurallar:
      * Sayaç ders SAYMIYORKEN, anlık hüküm `baslatma_sn` boyunca kesintisiz
        DERS olursa sayaç başlar.
      * Mevcut durumdan `durdurma_sn` boyunca ayrı kalınırsa (örn. dersten
        çıkıp Discord'a geçmek) durum değişir. Daha kısa kaçamaklar yok sayılır.
      * Geçişler GERİYE DÖNÜK işlenir: Discord'a 12:00:00'da geçtiysen ve
        15 sn sonra karar kesinleştiyse, ders oturumu 12:00:00'da bitmiş sayılır.
        Böylece tolerans süresi haksız yere derse eklenmez.
    """

    def __init__(self, baslatma_sn: float, durdurma_sn: float):
        self.baslatma_sn = baslatma_sn
        self.durdurma_sn = durdurma_sn
        self.sifirla()

    def sifirla(self) -> None:
        """Her şeyi unut (program açılışı, duraklatma ya da uykudan dönüş sonrası)."""
        self.mevcut: Durum | None = None   # Sayacın şu anki kalıcı durumu
        self._ayrilma_ani = None           # Anlık hüküm mevcut hükümden ne zaman ayrıldı
        self._aday_hukum = None            # Şu an gözlenen farklı hüküm
        self._aday_hukum_ani = None        # Bu aday hüküm ne zamandır kesintisiz sürüyor
        self._aday_baglam = None           # Hüküm aynı ama uygulama/sekme farklıysa: yeni bağlam
        self._aday_baglam_ani = None

    def _adaylari_temizle(self) -> None:
        self._ayrilma_ani = None
        self._aday_hukum = None
        self._aday_hukum_ani = None
        self._aday_baglam = None
        self._aday_baglam_ani = None

    def _gecis_yap(self, yeni: Durum, zaman: float) -> Gecis:
        self.mevcut = yeni
        self._adaylari_temizle()
        return Gecis(yeni, zaman)

    def guncelle(self, anlik: Durum, simdi: float) -> Gecis | None:
        """Her taramada çağrılır. Durum değiştiyse Gecis, değişmediyse None döndürür."""
        # Yok sayılan bir şeye bakılıyor (örn. takip paneli): hiçbir şey olmamış gibi
        # davran, yani "anlık durum = mevcut durum" kabul et. Henüz bir durum yoksa bekle.
        if anlik.hukum == DEVAM:
            if self.mevcut is None:
                return None
            anlik = self.mevcut

        # İlk çağrı: beklemeden mevcut durumu kabul et.
        if self.mevcut is None:
            return self._gecis_yap(anlik, simdi)

        # ---------- A) Hüküm mevcut durumdan farklı ----------------------
        if anlik.hukum != self.mevcut.hukum:
            self._aday_baglam = None  # Bağlam takibi sadece hüküm aynıyken anlamlı

            if self._ayrilma_ani is None:
                self._ayrilma_ani = simdi
            if anlik.hukum != self._aday_hukum:
                self._aday_hukum = anlik.hukum
                self._aday_hukum_ani = simdi

            if anlik.hukum == DERS:
                # Sayacı BAŞLATMAK için: ders hükmü kesintisiz sürmeli.
                if simdi - self._aday_hukum_ani >= self.baslatma_sn:
                    return self._gecis_yap(anlik, self._aday_hukum_ani)
            else:
                # Mevcut durumdan ÇIKMAK için: toplam ayrı kalma süresine bakılır.
                # (Belirsiz ve ders dışı arasında gidip gelmek sayacı açık tutmasın.)
                if simdi - self._ayrilma_ani >= self.durdurma_sn:
                    return self._gecis_yap(anlik, self._ayrilma_ani)
            return None

        # ---------- B) Hüküm aynı ----------------------------------------
        # Kısa kaçamak bitti, mevcut hükme geri dönüldü.
        self._ayrilma_ani = None
        self._aday_hukum = None
        self._aday_hukum_ani = None

        if anlik.baglam == self.mevcut.baglam:
            self._aday_baglam = None
            return None

        # Hüküm aynı ama uygulama/sekme değişti (örn. bir ders videosundan diğerine).
        # Yeni bağlam yeterince sürerse oturumu bölüyoruz ki düzeltme ekranında
        # her biri ayrı satır olarak görünsün.
        if anlik.baglam != self._aday_baglam:
            self._aday_baglam = anlik.baglam
            self._aday_baglam_ani = simdi
        if simdi - self._aday_baglam_ani >= self.durdurma_sn:
            return self._gecis_yap(anlik, self._aday_baglam_ani)
        return None

    def bekleyen(self, anlik: Durum, simdi: float) -> dict | None:
        """Arayüz için: tolerans süresi dolmayı bekleyen bir hüküm değişikliği var mı?"""
        if self.mevcut is None or self._aday_hukum is None or anlik.hukum == DEVAM:
            return None
        if anlik.hukum == DERS:
            kalan = self.baslatma_sn - (simdi - self._aday_hukum_ani)
        else:
            kalan = self.durdurma_sn - (simdi - self._ayrilma_ani)
        return {"hukum": anlik.hukum, "kalan_sn": max(0, round(kalan))}
