"""Düzeltmelerden öğrenen yerel sınıflandırıcı (Naive Bayes, ek paket yok).

Ne işe yarar? Kurallar yalnızca "aynı başlık" ya da "listedeki kelime"yi tanır. Bu model,
daha önce çalışma / çalışma değil diye bilinen tarayıcı oturumlarının başlıklarındaki
KELİMELERDEN öğrenir; böylece hiç görülmemiş ama benzer başlıklara (aynı kanal, aynı ders
adı, aynı site) tahmin yürütebilir.

Nasıl çalışır? (Çok terimli Naive Bayes)
  * Her başlık kelimelere bölünür; site adı varsa "@youtube.com" gibi ayrı bir kelime eklenir.
  * Her sınıf (çalışma / çalışma değil) için hangi kelimenin kaç kez geçtiği sayılır.
  * Yeni bir başlık için: "bu kelimeler çalışma başlıklarında mı, diğerlerinde mi daha sık?"
    olasılıkları çarpılır (taşma olmasın diye logaritmaları toplanır) ve en olası sınıf seçilir.
  * Hiç görülmemiş kelimeler için Laplace düzeltmesi (+1) kullanılır, sıfır olasılık olmaz.

Eğitim verisi: geçerli hükmü çalışma ya da çalışma değil olan tarayıcı oturumları. Senin
düzelttiklerin daha güçlü örnektir (3 kat ağırlık). Aynı başlık bir kez sayılır.

Model dosyaya kaydedilmez; açılışta ve her düzeltmeden sonra veritabanından yeniden eğitilir
(binlerce başlık için bile bir saniyeden kısa sürer).
"""

import math
import random
import re
import threading
import time
from collections import Counter

from heatmap.dedektorler.baslik import _kucult
from heatmap.sinyal import DERS, DERS_DEGIL

SINIFLAR = (DERS, DERS_DEGIL)
DUZELTME_AGIRLIGI = 3        # Kullanıcının düzelttiği örnek, kuralın karar verdiğinden bu kadar güçlü
EN_AZ_ORNEK = 8              # Toplam en az bu kadar farklı başlık olmadan tahmin yapılmaz
SINIF_BASINA_EN_AZ = 2       # Her sınıftan en az bu kadar örnek gerekir
_KELIME = re.compile(r"\w+", re.UNICODE)
# Neredeyse her başlıkta geçen, bir şey anlatmayan kelimeler
_ANLAMSIZ = {"ve", "ile", "bir", "bu", "the", "and", "of", "to", "in", "a", "for", "on", "with",
             "youtube", "google", "chrome", "brave", "edge", "firefox", "new", "tab", "yeni", "sekme"}


def kelimelere_bol(baslik: str, alan_adi: str = "") -> list[str]:
    """'(3) ML Lecture 5 - YouTube' -> ['ml', 'lecture', '5'] (+ '@youtube.com' site varsa)."""
    kelimeler = [k for k in _KELIME.findall(_kucult(baslik or "")) if k not in _ANLAMSIZ and len(k) > 1]
    if alan_adi:
        kelimeler.append("@" + alan_adi.lower())
    return kelimeler


class NaiveBayes:
    """İki sınıflı çok terimli Naive Bayes. ornekler: [(kelimeler, sınıf, ağırlık), ...]"""

    def __init__(self, ornekler: list[tuple[list[str], str, float]]):
        self.sayimlar = {s: Counter() for s in SINIFLAR}
        self.belge = Counter()
        for kelimeler, sinif, agirlik in ornekler:
            self.belge[sinif] += agirlik
            for kelime in kelimeler:
                self.sayimlar[sinif][kelime] += agirlik
        self.kelime_dagarcigi = set().union(*(set(c) for c in self.sayimlar.values()))
        self.toplam = {s: sum(c.values()) for s, c in self.sayimlar.items()}
        self.ornek_sayisi = len(ornekler)

    def _log_olasiliklar(self, kelimeler: list[str]) -> dict[str, float]:
        v = len(self.kelime_dagarcigi) or 1
        toplam_belge = sum(self.belge.values())
        sonuc = {}
        for s in SINIFLAR:
            log_p = math.log((self.belge[s] + 1) / (toplam_belge + len(SINIFLAR)))  # önsel olasılık
            for k in kelimeler:
                log_p += math.log((self.sayimlar[s][k] + 1) / (self.toplam[s] + v))
            sonuc[s] = log_p
        return sonuc

    def tahmin(self, kelimeler: list[str]) -> tuple[str, float, list[str]]:
        """(sınıf, olasılık 0-1, kararı en çok etkileyen kelimeler) döndürür."""
        bilinen = [k for k in kelimeler if k in self.kelime_dagarcigi]
        log = self._log_olasiliklar(bilinen)
        en_buyuk = max(log.values())
        ustel = {s: math.exp(v - en_buyuk) for s, v in log.items()}  # softmax: log -> olasılık
        toplam = sum(ustel.values())
        sinif = max(ustel, key=ustel.get)
        diger = DERS_DEGIL if sinif == DERS else DERS
        # Hangi kelimeler bu sınıfı en çok destekledi? (kelime başına olasılık oranı)
        etki = sorted(set(bilinen), reverse=True, key=lambda k: (
            math.log((self.sayimlar[sinif][k] + 1) / (self.toplam[sinif] + 1))
            - math.log((self.sayimlar[diger][k] + 1) / (self.toplam[diger] + 1))))
        return sinif, ustel[sinif] / toplam, etki[:3]


def capraz_dogrulama(ornekler: list[tuple[list[str], str, float]], katman: int = 5,
                     tohum: int = 7) -> tuple[float | None, float] | None:
    """k katlı çapraz doğrulama: (doğruluk, kapsam) döndürür; örnek azsa None.

    Veriyi k parçaya böler; her seferinde bir parçayı saklayıp diğerleriyle eğitir ve saklanan
    parçayı tahmin eder. Böylece model, ezberlediği değil hiç görmediği başlıklarla ölçülür.

    Gerçek kullanımdaki gibi, içinde HİÇ tanıdık kelime olmayan başlığa tahmin yapılmaz:
      doğruluk = tahmin yapılanların kaçı doğru (hiç tahmin yoksa None)
      kapsam   = başlıkların kaçına tahmin yapılabildi
    """
    if len(ornekler) < max(EN_AZ_ORNEK, katman):
        return None
    karisik = ornekler[:]
    random.Random(tohum).shuffle(karisik)
    dogru = tahmin_edilen = 0
    for i in range(katman):
        test = karisik[i::katman]
        egitim = [o for j, o in enumerate(karisik) if j % katman != i]
        model = NaiveBayes(egitim)
        for kelimeler, sinif, _ in test:
            if not any(k in model.kelime_dagarcigi for k in kelimeler):
                continue  # Tanıdık kelime yok: tahmin yapılmaz
            tahmin_edilen += 1
            dogru += model.tahmin(kelimeler)[0] == sinif
    dogruluk = dogru / tahmin_edilen if tahmin_edilen else None
    return dogruluk, tahmin_edilen / len(karisik)


class Tahminci:
    """Veritabanından eğitilen, iş parçacıkları arasında paylaşılan model."""

    def __init__(self, depo, saat=time.time):
        self.depo = depo
        self.saat = saat
        self._kilit = threading.Lock()
        self._model: NaiveBayes | None = None
        self.bilgi = {"ornek_sayisi": 0, "sinif_sayilari": {}, "dogruluk": None, "egitim_zamani": None,
                      "hazir": False}

    def egitim_ornekleri(self) -> list[tuple[list[str], str, float]]:
        """Her farklı (başlık, site) için tek örnek; düzeltilmişse ağırlığı fazla."""
        gorulen: dict[tuple[str, str], tuple[list[str], str, float]] = {}
        for o in self.depo.etiketli_tarayici_oturumlari():
            anahtar = (_kucult(o["baslik"] or ""), o["alan_adi"] or "")
            agirlik = DUZELTME_AGIRLIGI if o["duzeltme"] else 1
            onceki = gorulen.get(anahtar)
            if onceki is None or agirlik > onceki[2]:  # Düzeltilmiş olan kazanır
                gorulen[anahtar] = (kelimelere_bol(o["baslik"], o["alan_adi"] or ""), o["hukum"], agirlik)
        return [o for o in gorulen.values() if o[0]]

    def yeniden_egit(self) -> dict:
        ornekler = self.egitim_ornekleri()
        sayilar = Counter(sinif for _, sinif, _ in ornekler)
        hazir = len(ornekler) >= EN_AZ_ORNEK and all(sayilar[s] >= SINIF_BASINA_EN_AZ for s in SINIFLAR)
        model = NaiveBayes(ornekler) if hazir else None
        olcum = capraz_dogrulama(ornekler) if hazir else None
        dogruluk, kapsam = olcum if olcum else (None, None)
        bilgi = {
            "ornek_sayisi": len(ornekler),
            "sinif_sayilari": {s: sayilar[s] for s in SINIFLAR},
            "dogruluk": round(dogruluk, 3) if dogruluk is not None else None,
            "kapsam": round(kapsam, 3) if kapsam is not None else None,
            "egitim_zamani": self.saat(),
            "hazir": hazir,
            "en_az_ornek": EN_AZ_ORNEK,
        }
        with self._kilit:
            self._model, self.bilgi = model, bilgi
        return bilgi

    def tahmin_et(self, baslik: str, alan_adi: str = "") -> dict | None:
        """{"hukum", "olasilik", "kelimeler"} ya da (model hazır değilse / bilgi yoksa) None."""
        with self._kilit:
            model = self._model
        kelimeler = kelimelere_bol(baslik, alan_adi)
        if model is None or not any(k in model.kelime_dagarcigi for k in kelimeler):
            return None  # Hiç tanıdık kelime yok: tahmin, önsel olasılıktan ibaret olurdu
        sinif, olasilik, etkili = model.tahmin(kelimeler)
        return {"hukum": sinif, "olasilik": round(olasilik, 3), "kelimeler": etkili}
