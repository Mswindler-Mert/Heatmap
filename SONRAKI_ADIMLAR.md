# Sonraki adımlar: devralma planı

Bu dosya, projeyi başka bir modelin (ya da insanın) devralıp uygulayabilmesi için yazıldı.
Kod yazmadan önce "0. Devralan için" bölümünü oku. Bölüm 2 ve 3 **uygulandı**; orada nasıl
çalıştığı ve kalan işler yazıyor. Bölüm 1 ve 4 **henüz uygulanmadı**; tasarım kararları verildi.

İşaretler: ✅ yapıldı · 🔲 yapılacak · ⚠️ tuzak · ❓ uygulamadan önce doğrulanmalı (emin değilim)

---

## 0. Devralan için

### Projenin amacı

Windows'ta arka planda çalışıp **bilgisayar başında aktif/verimli geçen süreyi kendiliğinden**
ölçmek, sürenin **hangi uygulama ve sitelerden geldiğini** göstermek ve sonucu **paylaşılabilir**
(Strava tarzı kart) hale getirmek. Proje "Ders Takip" adıyla başladı, sonra "Heatmap" oldu (paket: `heatmap`); iç kod adları hâlâ `ders`
diyor ama anlamı "çalışma / aktif süre".

### Kullanıcı ve çalışma biçimi

- Kullanıcı bilgisayar mühendisliği öğrencisi, ilk projesi. **Kod yorumlu ve okunabilir olmalı**;
  akıllıca ama anlaşılmaz çözümlerden kaçın.
- Dosya, değişken, yorum ve arayüz **Türkçe**. Kod adlarını (`DERS`, `ders_sn`, `ders_surecleri`,
  API alan adları) kullanıcı istemeden değiştirme.
- **Her anlamlı adımda commit** at (Türkçe, ASCII mesaj). Önce tasarımı anlat, onay al, sonra kodla.
- Ortam: Windows 11, **Python 3.14.3**, komut **`py`** (`python` komutu yok), Git kurulu.
- Çalıştırma: `baslat.bat` (tepsi ikonuyla) ya da `.venv\Scripts\python -m heatmap --tepsisiz --sessiz`.
- Testler: `.venv\Scripts\python -m unittest` (şu an 49 test, hepsi geçiyor). pytest yok, ekleme.

### Mimari (tek süreç, üç thread)

```
dedektorler/*.py  --Sinyal-->  motor.anlik_karar()  -->  motor.KararMotoru (tolerans)
                                                              |
takipci.Takipci.tik()  (saniyede bir)  <----------------------+
        |
     depo.Depo (SQLite: oturumlar, ogrenilen_kurallar)
        |
web/api.py (FastAPI, yalnızca 127.0.0.1)  -->  web/static/ (HTML/CSS/JS)
tepsi.py (pystray, ana thread)
```

| Dosya | Görev |
|---|---|
| `sinyal.py` | `Sinyal`, `Dedektor` ve hüküm sabitleri: `DERS`, `DERS_DEGIL`, `BELIRSIZ`, `FIKRIM_YOK`, `DEVAM` |
| `windows_api.py` | ctypes ile aktif pencere ve boşta süresi |
| `dedektorler/pencere.py`, `baslik.py`, `bosta.py`, `kamera.py` | Tespit modülleri (kamera yalnızca iskelet) |
| `motor.py` | `anlik_karar()` sinyalleri birleştirir; `KararMotoru` toleransı uygular, geçişler geriye dönük |
| `takipci.py` | Saniyelik döngü, oturum aç/kapat, uyku tespiti, arayüz için durum özeti |
| `depo.py` | Tüm SQL. Her işlemde bağlantı açılıp kapanır (thread güvenliği için) |
| `ozet.py` | `Adlandirici` (okunabilir ad, site ayırma), `seri_hesapla` |
| `kart.py` | Paylaşım kartı: `kart_verisi()` + `kart_ciz()` |
| `web/api.py` | `uygulama_olustur(takipci, depo, ayarlar)` |
| `main.py` | Parçaları kurar; `dedektorleri_kur()` modül sırasını belirler |

### Genel tuzaklar (hepsi yaşandı ya da bilinçli karar)

- ⚠️ **Zaman parametredir.** Motor ve `Takipci.tik(simdi)` saati kendisi okumaz; testler bu sayede
  beklemeden çalışır. Yeni kodda da `time.time()`'ı mantığın içine gömme, dışarıdan ver.
- ⚠️ **Çalışan kopya eski kodu tutar.** Kullanıcı uygulamayı `baslat.bat` ile açık bırakıyor
  (port 8765). Kod/ayar değişince yeniden başlatması gerekir; bunu her seferinde söyle. Doğrulama
  için kullanıcının verisine dokunmadan, geçici veritabanıyla başka bir portta (8766) çalıştır.
- ⚠️ **Ayar birleştirme:** `ayarlar._ustune_yaz` sözlükleri iç içe birleştirir ama **listeleri
  değiştirir**. Yani `config.toml`'daki `ders_surecleri` örnek dosyadakinin yerine geçer;
  `[adlar]` ve `[siteler]` ise (sözlük oldukları için) birleşir. Yeni ayar eklerken hangisini
  istediğine göre liste ya da tablo seç ve **her yeni ayarı `config.ornek.toml`'a da ekle**.
- ⚠️ **`config/config.toml` ve `data/` Git dışıdır** (kişisel uygulama listesi, pencere başlıkları).
  Commit'ten önce `git status` ile kontrol et; örnek dosyaya kişisel bilgi yazma.
- ⚠️ **Pencere başlıkları saldırgan kontrollü metindir** (bir web sitesi başlığına istediğini
  yazar). Arayüzde yalnızca `textContent` kullan, `innerHTML` kullanma.
- ⚠️ **Sunucu yalnızca 127.0.0.1'i dinler** ve `TrustedHostMiddleware` var. Bunu gevşetmeden önce
  kullanıcıya sor (bkz. Bölüm 4).
- ⚠️ **`pythonw.exe` ile `sys.stdout` None olur**; `main._ciktiyi_dosyaya_yonlendir` bunu
  `data/heatmap.log`'a çevirir. Alt süreç başlatırken de konsolsuz çalıştığını unutma.
- ⚠️ **`.bat` dosyaları CRLF ve ASCII olmalı** (`.gitattributes` bunu sağlar; Türkçe karakter koyma).
- ⚠️ **Türkçe büyük/küçük harf:** `"seri".upper()` → "SERI" (yanlış). Büyük harfli etiketleri elle
  yaz. Karşılaştırmada `baslik._kucult()` kullan (İ → i).
- ⚠️ **Geçişler geriye dönüktür:** `Gecis.zaman`, kararın verildiği an değil durumun değiştiği andır.
  Oturum sürelerini hesaplayan her yeni kod bunu bozmamalı.
- ⚠️ Tepsi ikonu ve menüsü hiç gözle denenmedi (yalnızca sürecin açılıp API'ye yanıt verdiği doğrulandı).

---

## 1. Kamera modülü 🟡 (yarısı yapıldı)

**Yapılanlar (1.8'deki 1. ve 2. adım + işçinin ilk sürümü):**

- `kamera_isci/isci.py`: sözleşmedeki JSON'u yazan işçi. `--sahte <senaryo>` modu kamera ve
  MediaPipe olmadan çalışır (testler bunu kullanır). Gerçek mod: OpenCV + MediaPipe Face Landmarker,
  yüz var/yok ve dönüşüm matrisinden pitch/yaw. ❓ **Gerçek kamerayla HİÇ çalıştırılmadı**: MediaPipe
  API adları, açı formülü (`_acilar`) ve işareti ilk denemede doğrulanmalı. Telefon nesne tespiti
  (1.4-B) yok; `telefon_var` gerçek modda hep `null`.
- `dedektorler/kamera.py`: `IsciSureci` (alt süreç, CREATE_NO_WINDOW, satır okuyan thread, 5→300 sn
  artan yeniden başlatma, kapanışta terminate + boru kapatma) ve `KameraDedektoru` (1.5'teki
  durumlar, eşikler, `masada`, `not_alma_doldu`, bayat veri 10 sn).
- `motor.anlik_karar()`: 1.5'teki kural sırası uygulandı (veto → boşta + masada muafiyeti →
  içerik → uzun aşağı bakma = BELIRSIZ). `_icerik_karari()` ayrı fonksiyona alındı.
- `tests/test_kamera.py`: dedektör eşikleri, karar tablosunun her satırı, gerçek alt süreçle hat
  (sahte mod), Türkçe hata mesajının borudan bozulmadan gelmesi, gizlilik taraması.
- `kamera_kur.bat`, `kamera_isci/requirements.txt`, `kamera_isci/README.md`, `.gitignore`
  (`.venv-kamera/`, `modeller/`), `[kamera]` ayarları (`sahte_senaryo` dahil).

**Kalanlar (kullanıcının katılımı gerekir):** 🔲 Python 3.12 kurulumu (makinede yalnızca 3.14 var),
🔲 model dosyasının indirilmesi, 🔲 gerçek kamerayla ilk çalıştırma ve açı doğrulaması,
🔲 telefon nesne tespiti. ✅ Arayüzde kalibrasyon düğmesi (`POST /api/kamera/kalibre`,
`KameraDedektoru.kalibre_et`: 6 sn ölçüm, ortanca, `data/kamera_kalibrasyon.json`) ve arayüz/tepside
geçici aç/kapat (`ayarla_acik`: işçi durur, kapatınca yeni `IsciSureci` hazırlanır) yapıldı; sahte
işçiyle uçtan uca denendi (kapalıyken işçi süreci kalmıyor). ⚠️ Testler kalibrasyon dosyası için
HER ZAMAN geçici yol vermeli (`kalibrasyon_dosyasi=`), yoksa kullanıcının gerçek kalibrasyonunu okur. ✅ 1.7'deki "ikili gecikme" tuzağı
çözüldü: `Durum.geriye_sn` (karşılaştırmaya girmez) kameranın `sure_sn` bilgisini taşır,
`KararMotoru` ayrılma anını o kadar geriye çeker (mevcut durumun başlangıcından öteye değil).
Ayrıca "yüz yok" vetosu artık "yüz kaybolduktan SONRA girdi var mı" (`bosta_sn < sure_sn`) ölçütüne
bakıyor; eskiden 120 sn'lik boşta eşiğine baktığı için pratikte hiç devreye girmiyordu.
Boşta kalma kuralına geriye çekme bilerek UYGULANMADI (girdisiz geçen süre okumak da olabilir).

Aşağıdaki tasarım metni bu kalanlar için hâlâ geçerli.

### 1.1 Gizlilik kuralları (pazarlık yok)

1. Kare **asla diske yazılmaz** (`cv2.imwrite`, `VideoWriter`, `PIL.save` yok).
2. Kare **asla ağa gönderilmez**; analiz tamamen yerelde.
3. Kare analiz biter bitmez atılır; kamera sürecinin **dışına çıkan tek şey** aşağıdaki küçük JSON'dur.
4. Veritabanına ve API'ye yalnızca evet/hayır türü sonuçlar gider. Açı gibi sayılar yalnızca
   canlı durumda (kalibrasyon ekranı) gösterilir, kaydedilmez.
5. Kamera varsayılan olarak **kapalı**; kullanıcı açar. Arayüzde ve tepside "kamera açık" göstergesi olmalı.

### 1.2 Kütüphaneler

- **OpenCV** (`opencv-python`): yalnızca kameradan kare almak için.
- **MediaPipe** (`mediapipe`), Tasks API:
  - **Face Landmarker**: yüz var mı + kafa yönü. `output_facial_transformation_matrixes=True`
    ile 4x4 dönüşüm matrisi gelir; ondan pitch (aşağı/yukarı) ve yaw (sağ/sol) açısı çıkarılır.
  - **Object Detector** (EfficientDet-Lite0, COCO sınıfları içinde "cell phone" var): telefon
    nesnesi tespiti için, ikinci aşamada.
  - ❓ Sınıf/parametre adlarını ve model dosyası adreslerini güncel MediaPipe belgelerinden doğrula;
    burada ezberden yazıldı.
- Model dosyaları (`face_landmarker.task`, `efficientdet_lite0.tflite`) ayrı indirilir.
  `modeller/` klasörüne koy, **`.gitignore`'a ekle**, depoya koyma. İndirme internetten dosya
  çekmek demektir: kullanıcıya adresi ve boyutu söyleyip onay al.

### 1.3 Python 3.14 sorunu: seçilen çözüm → ayrı kamera süreci

MediaPipe yeni Python sürümlerine geç tekerlek (wheel) çıkarır; 3.14'te kurulmayabilir.

**Karar:** Kamera analizi **ayrı bir süreçte, kendi sanal ortamında** çalışır; ana uygulama 3.14'te kalır.

```
ana uygulama (3.14, .venv)                      kamera işçisi (3.12, .venv-kamera)
dedektorler/kamera.py  <-- stdout'tan JSON satırları --  kamera_isci/isci.py
   (alt süreci başlatır,                                   (kare al -> analiz et -> kareyi at
    son gözlemi bellekte tutar)                             -> tek satır JSON yaz)
```

Neden bu yol (ve neden diğerleri değil):

- Ana uygulamayı 3.12'ye indirmek de çalışırdı ama kullanıcının kurulu Python'u 3.14; her şeyi
  kamera yüzünden eski sürüme bağlamak kötü bir takas.
- Ayrı süreç, ağır paketleri (yüzlerce MB) kamera kullanmayanlardan uzak tutar ve kamera
  çökerse takip devam eder.
- İletişim için **ağ portu açılmaz**: işçi stdout'a satır yazar, ana uygulama `subprocess.Popen`
  ile okur. Görüntü borudan geçmez, yalnızca JSON.
- MediaPipe 3.14'te kurulabiliyorsa bile tasarım aynı kalır; yalnızca `[kamera] python` ayarı
  ana venv'i gösterir.

İşçinin her gözlemde yazdığı satır (sözleşme):

```json
{"zaman": 1794860000.0, "yuz_var": true, "pitch": -28.5, "yaw": 3.1, "telefon_var": false, "hata": null}
```

Kurulum adımları:

1. `py -0` ile kurulu sürümlere bak. 3.12 yoksa kullanıcıdan kurmasını iste (kendin kurma).
2. `kamera_kur.bat`: `py -3.12 -m venv .venv-kamera` + `pip install -r kamera_isci/requirements.txt`.
3. `.gitignore`'a `.venv-kamera/` ve `modeller/` ekle.

### 1.4 Tespitler

**Yüz var mı:** Face Landmarker en az bir yüz döndürdüyse `yuz_var = true`. Birden çok yüz
varsa en büyüğünü al.

**Kafa yönü:** dönüşüm matrisinden pitch/yaw. İşaret (aşağı = negatif mi pozitif mi) kameraya
göre değişebilir; ❓ gerçek kamerayla dene ve `isci.py` içinde "aşağı = negatif" olacak şekilde sabitle.

**Kişisel kalibrasyon şart:** dizüstü kamerası ekranın üstündedir, ekrana bakan biri zaten hafif
aşağı bakar. Sabit eşik (örn. -20°) herkes için tutmaz. Arayüze "Kalibrasyon" düğmesi ekle:
kullanıcı 5 sn ekrana bakar → ortalama pitch `ekran_pitch` olarak `data/` altına kaydedilir.
"Aşağı bakıyor" = `pitch < ekran_pitch - asagi_fark_derece` (varsayılan 18).

**Telefona bakma** (iki aşamalı; önce A'yı bitir, B isteğe bağlı):

- **A. Duruş sezgisi:** kafa belirgin aşağıda **ve** klavye/fare boşta **ve** bu durum
  `telefon_esik_sn` (varsayılan 20) boyunca sürüyor. Tek başına "not alıyor" ile ayırt edilemez;
  bu yüzden A yalnızca *aday* üretir, kararı 1.5'teki tablo verir.
- **B. Nesne tespiti:** Object Detector karede "cell phone" görürse `telefon_var = true`.
  Telefon çoğu zaman kadraj dışında (masanın altında) kalır; yani B "var" derse güvenilir,
  "yok" derse hiçbir şey kanıtlamaz. B'yi yalnızca "kesin telefon" sinyali olarak kullan.

### 1.5 Karar motoruna bağlama

**Sinyal sözleşmesi** (`KameraDedektoru.oku()`), hüküm + `detay["kamera_durumu"]`:

| `kamera_durumu` | Anlamı | `hukum` |
|---|---|---|
| `ekrana_bakiyor` | Yüz var, kafa düz | `FIKRIM_YOK` |
| `asagi_bakiyor` | Yüz var, kafa aşağıda, telefon görülmedi | `FIKRIM_YOK` |
| `telefon` | Telefon nesnesi görüldü (B) ve eşik doldu | `DERS_DEGIL` |
| `yok` | Yüz `yuz_yok_esik_sn` (30) boyunca yok | `DERS_DEGIL` |
| `bilinmiyor` | İşçi çalışmıyor / veri bayat (>10 sn) / kamera meşgul | `FIKRIM_YOK` |

Ek olarak `detay["masada"] = True/False/None`: yüz görünüyor mu (eşiklerden bağımsız, anlık).

**`motor.anlik_karar()` içinde yeni kural sırası** (şimdiki sıra: boşta → kamera → içerik):

1. **Kamera vetosu:** `kamera.hukum == DERS_DEGIL` → `Durum(DERS_DEGIL, baglam="kamera", ...)`.
   Ama klavye/fare **aktifse** `yok` vetosunu uygulama (kamera kapalı/kapatılmış olabilir, girdi
   yalan söylemez); `telefon` vetosu ise girdi olsa da geçerli.
2. **Boşta kuralı, kamera muafiyetiyle:** boşta eşiği aşıldıysa →
   - kamera `masada is True` ise **boşta sayma** (kişi masada: okuyor, izliyor ya da not alıyor);
   - kamera bilgisi yoksa (`None`) bugünkü davranış: video ise video eşiğine kadar muaf, değilse `DERS_DEGIL`.
3. **İçerik kuralı:** değişmedi (başlık / pencere).

Kamera **hiçbir zaman içeriği yükseltmez**: ekranda oyun varken masada olmak çalışma değildir.
Kamera yalnızca (a) veto eder, (b) boşta kuralını askıya alır.

**"Duraklatılmış video + yüz görünüyor = not alıyor" mantığı**

Sorun: sekme başlığından videonun oynadığı anlaşılamıyor; bugün duraklatılmış video 30 dk
(`video_esik_sn`) boyunca çalışma sayılıyor, sonra kesiliyor. Kamera açıkken bunun yerine:

| Ekran | Klavye/fare | Kamera | Sonuç |
|---|---|---|---|
| Çalışma videosu | boşta | `ekrana_bakiyor` | **Çalışma** (izliyor). Süre sınırı yok. |
| Çalışma videosu | boşta | `asagi_bakiyor` | **Çalışma** (not alıyor), `not_alma_esik_sn` (varsayılan 600) boyunca. Sonra `BELIRSIZ`: kullanıcı düzeltme ekranından karar verir. |
| Çalışma videosu | boşta | `telefon` | Çalışma değil |
| Çalışma videosu | boşta | `yok` | Çalışma değil (video eşiği beklenmez) |
| Çalışma uygulaması (PDF, IDE) | boşta | `ekrana_bakiyor` / `asagi_bakiyor` | Yukarıdakiyle aynı (okuyor / not alıyor) |
| Çalışma dışı içerik | — | — | Çalışma değil (kamera karışmaz) |
| Belirsiz içerik | boşta | masada | `BELIRSIZ` kalır (düzeltilince geriye dönük sayılır) |

Yani kamera açıkken `video_esik_sn` devre dışı kalır; onun yerini "masada mı" bilgisi alır.
Videonun duraklatılmış mı oynuyor mu olduğunu bilmeye gerek kalmaz: masadaysa ikisi de çalışmadır.
`not_alma_esik_sn` sınırı, "kafa aşağıda" durumunun aslında masa altındaki telefon olabilmesi
yüzünden var; süreyi `BELIRSIZ`'e düşürmek en dürüst sonuç.

### 1.6 Dokunulacak dosyalar

| Dosya | Değişiklik |
|---|---|
| `kamera_isci/isci.py` (yeni) | Kamera aç, 2 sn'de bir kare al, analiz et, JSON satırı yaz, kareyi sil. Ana uygulamadan **hiçbir şey import etmez**. |
| `kamera_isci/requirements.txt` (yeni) | `opencv-python`, `mediapipe` |
| `kamera_kur.bat` (yeni) | 3.12 venv'i kurar (ASCII, CRLF) |
| `dedektorler/kamera.py` | Alt süreci başlat/izle, stdout'u okuyan thread, son gözlemi kilitle sakla, eşik sürelerini uygula, `oku()` sözleşmesi, `kapat()` ile süreci sonlandır |
| `motor.py` | `anlik_karar()` kural sırası ve muafiyetler (1.5) |
| `config/config.ornek.toml` | `[kamera]`: `etkin`, `python`, `kare_araligi_sn`, `yuz_yok_esik_sn`, `telefon_esik_sn`, `not_alma_esik_sn`, `asagi_fark_derece`, `telefon_nesne_tespiti` |
| `main.py` | `dedektorleri_kur()` içinde kamera **en sonda** kalmalı |
| `web/api.py`, `web/static/*` | `/api/durum` içinde kamera durumu, "kamera açık" göstergesi, aç/kapat, kalibrasyon ucu ve ekranı |
| `tepsi.py` | Menüye "Kamera" aç/kapat |
| `.gitignore` | `.venv-kamera/`, `modeller/` |
| `tests/test_kamera.py` (yeni), `tests/test_motor.py` | Aşağıdaki testler |
| `README.md` | Kurulum, gizlilik, kalibrasyon |

Testler (işçi ve kamera olmadan, sahte gözlem vererek):

- `KameraDedektoru`'na sahte gözlem kaynağı ve sahte saat ver: yüz 29 sn yok → veto yok; 31 sn → `yok`.
- Bayat veri (>10 sn) → `bilinmiyor`, `FIKRIM_YOK`.
- `anlik_karar`: 1.5'teki tablonun her satırı ayrı test.
- Girdi aktifken `yok` vetosu uygulanmıyor.
- Gizlilik testi: `kamera_isci/` kaynaklarında `imwrite`, `VideoWriter`, `.save(`, `socket`,
  `requests`, `urllib` geçmediğini tarayan test.

### 1.7 Tuzaklar

- ⚠️ **İkili gecikme:** dedektörün kendi eşikleri (30 sn) + motorun toleransı (15 sn) üst üste
  biner. Eşikleri dedektörde tut, ama geçişin geriye dönük olması için `Sinyal.detay` içine
  "durum ne zamandır böyle" bilgisini koymayı ve motorun bunu kullanmasını değerlendir; yoksa
  her kalkışta ~45 sn fazla sayılır.
- ⚠️ **Alt süreç yaşam döngüsü:** program kapanırken işçiyi mutlaka sonlandır (`kapat()`), yoksa
  kamera ışığı açık kalır. İşçi çökerse artan bekleme ile yeniden başlat; sonsuz döngüye girme.
  Windows'ta konsol penceresi açılmasın: `creationflags=subprocess.CREATE_NO_WINDOW`.
- ⚠️ **stdout tamponu:** işçide her satırdan sonra `flush=True`; yoksa ana uygulama veriyi dakikalarca göremez.
  MediaPipe/absl kendi günlüklerini stderr'e yazar; stderr'i stdout'la karıştırma, JSON olmayan satırı yok say.
- ⚠️ **Kamera meşgul/yok:** Teams/Zoom açıkken kamera alınamaz. Bu bir hata değil, `bilinmiyor`
  durumudur; takip kamerasız kurallarla sürmeli.
- ⚠️ **Açılış süresi:** `cv2.VideoCapture(0)` Windows'ta yavaş açılabilir; `cv2.CAP_DSHOW` dene.
  Kamerayı ana thread'de açma.
- ⚠️ **İşlemci/pil:** 640x480, 2–3 sn'de bir kare yeterli. Nesne tespiti (B) pahalıdır; yalnızca
  `asagi_bakiyor` adayı varken çalıştır.
- ⚠️ **Yanlış pozitifler:** gözlük, loş ışık, arkadan ışık, yandan oturma, ikinci monitöre bakma
  (yaw büyük, yüz kaybolabilir). `yok` eşiğini kısa tutma; ikinci monitör kullananlar için ayar gerekir.
- ⚠️ **Kamera hiçbir zaman tek başına "çalışma" demez.** Aksi halde boş ekrana bakmak süre kazandırır.

### 1.8 Uygulama sırası (her biri ayrı commit)

1. İşçi sözleşmesi + `KameraDedektoru` sahte kaynakla + testler (kamera yok).
2. `motor.anlik_karar()` yeni kuralları + tablo testleri.
3. Gerçek işçi: yalnızca yüz var/yok. Gerçek kamerayla dene.
4. Kafa yönü + kalibrasyon ekranı.
5. Arayüz/tepsi göstergeleri, README.
6. (İsteğe bağlı) telefon nesne tespiti.

---

## 2. Okunabilir uygulama adları ve siteye göre ayırma ✅

### Nasıl çalışıyor

- `ozet.Adlandirici.etiket(oturum) -> (ad, tur)`; `tur` "uygulama" ya da "site".
  - Oturumun `kaynak` sütunu `"baslik"` ise tarayıcı oturumudur → `site_adi(baslik)`.
  - Değilse → `uygulama_adi(surec)`: `[adlar]` tablosuna bakar, yoksa `.exe` atar, süreç boşsa "Bilgisayar dışı".
- `site_adi`: `[siteler]` içindeki kelimeleri başlıkta tam kelime olarak arar
  (`baslik.son_gecis_yeri`); birden çok site eşleşirse **başlıkta en sonda geçen** kazanır.
  Hiçbiri tutmazsa "Diğer web".
- `depo.uygulama_dokumu(bas, bit, etiketle)` oturumları bu etikete göre toplar.
- `GET /api/dokum` → `{toplam_sn, uygulamalar: [{ad, tur, sure_sn, oran}]}`; arayüzde "Süre nereden geldi?".
- Adlandırma **sorgu anında** yapılır; ayar değişince geçmiş veri de yeni adlarla görünür.

Dosyalar: `ozet.py`, `depo.py` (`uygulama_dokumu`), `dedektorler/baslik.py` (`son_gecis_yeri`),
`web/api.py` (`/api/dokum`), `web/static/uygulama.js` (`dokumuYenile`), `config/config.ornek.toml`
(`[adlar]`, `[siteler]`), `tests/test_ozet.py`, `tests/test_takipci.py::test_uygulama_dokumu`.

### Kalan işler 🔲

- ✅ **Tarayıcı eklentisi** (`eklenti/`, Manifest V3): öndeki sekmenin alan adını, `audible`
  (ses çalıyor mu) ve pencere odağını olaylarda + 30 sn'de bir `POST /api/tarayici`'ye yollar.
  `dedektorler/tarayici.py` son raporu tutar (75 sn tazelik); `baslik.py` alan adını
  `ders_alanlari`/`ders_degil_alanlari` ile sınıflandırır ve `video` bilgisini sesten alır;
  `oturumlar.alan_adi` sütununa kaydedilir (eski DB'lere `Depo._semayi_guncelle` ekler);
  `Adlandirici` alan adını `[siteler]`'deki noktalı öğelerle eşler, eşleşmezse alan adını gösterir.
  Eklenti `host_permissions` ile istek attığı için CORS gerekmez.
  Öğrenilen kural türü "alan" ✅: düzeltme ekranında "<site> sitesini hep böyle say" kutusu
  (varsayılan kapalı); `baslik.siniflandir` içinde ayar listelerinden önce uygulanır.
  Kalanlar: 🔲 YouTube kanal adı (içerik betiği gerekir; ⚠️ yeni izin ister, gizliliği düşün),
  🔲 eklentinin portu sabit (8765); ayardan değişirse eklentide de değişmeli,
  🔲 eklenti gerçek Brave'de kullanıcı tarafından denenmedi (yalnızca sunucu tarafı test edildi).
- ✅ **Sahte istek koruması:** `api.py` içindeki ara katman, `GET/HEAD/OPTIONS` dışındaki her
  istekte `X-Heatmap: 1` başlığı ister (özel başlık CORS ön kontrolünü tetikler; sunucu CORS
  izni vermediği için yabancı siteler bu isteği gönderemez). ⚠️ Yeni bir `POST` ucu ya da yeni
  bir istemci (dashboard, telefon) yazarken bu başlığı eklemeyi unutma.
- **Arayüzden düzenleme:** "Diğer web"deki başlıklardan site kuralı, bilinmeyen süreçten ad
  eşlemesi eklemek. ⚠️ Program `config.toml`'u yeniden yazarsa kullanıcının yorumları silinir
  (`tomllib` yalnızca okur). Programın yazdığı eşlemeleri veritabanında ayrı bir tabloda tut
  (öğrenilen kurallar gibi), ayar dosyasına dokunma.
- **Kategori:** uygulamaları gruplara ayırma (kod, not, toplantı, video, yapay zekâ). `[kategoriler]`
  tablosu + dökümde gruplama seçeneği.
- `explorer.exe` gibi belirsiz bırakılanlar dökümde yalnızca kullanıcı "çalışmaydı" derse görünür; bu bilinçli.

### Tuzaklar

- ⚠️ `etiket()` **asla başlığın kendisini döndürmemeli**; paylaşım kartının gizliliği buna dayanıyor.
  "Tanınmayan başlığı olduğu gibi göster" türü bir iyileştirme kartı sızdırır.
- ⚠️ Site kelimeleri fazla genel olursa yanlış eşleşir ("Google" her Google ürününü yutar).
  Çakışmada sondaki kazanır; test: `test_birden_cok_site_kelimesinde_sondaki_kazanir`.
- ⚠️ `[siteler]` yalnızca **adlandırır**; sürenin sayılıp sayılmayacağına `[baslik]` kelimeleri karar
  verir. İkisini birleştirmeye kalkma, kullanıcıya ayrı ayrı anlatıldı.
- ⚠️ Aynı görünen ad farklı türlerde olabilir ("Claude" uygulaması ve "claude.ai" sitesi); gruplama
  anahtarı `(ad, tur)` ikilisidir, yalnızca `ad` değil.
- ⚠️ `/api/dokum` alan adı `uygulama`'dan `ad`'a değişti; eski adı kullanan bir tüketici yok ama
  ileride dashboard yazarken `ad` kullan.

---

## 3. Paylaşım kartı (1080x1920) ✅

### Nasıl çalışıyor

- `kart.kart_verisi(depo, adlandirici, hedef_sn, tur, tarih, bugun=None) -> dict`: kartta görünecek her şey.
  `tur`: gunluk / haftalik / aylik / yillik; `tarih` kartın ait olduğu gün, `bugun` gerçek bugün
  (sonraki günler "gelecek" diye boş çizilir).
- `kart.kart_ciz(veri) -> bytes`: Pillow ile PNG. **Veritabanına erişmez.**
- `GET /api/kart?tur=gunluk|haftalik|aylik|yillik&tarih=YYYY-AA-GG&indir=true|false` → `image/png`.
- `GET /api/seri` → hedef ve seri. Hedef: `[hedef] gunluk_dk` (varsayılan 120).
- Arayüz: "Paylaşım kartı" bölümü, "Paylaşım kartı oluştur" düğmesi, önizleme + "PNG olarak indir".
- Kartta: toplam aktif süre, motivasyon cümlesi, üç kutucuk (türe göre değişir), orta bölüm
  (günlük/haftalık: 7 günlük çubuk grafik + hedef çizgisi; aylık: takvim ısı haritası; yıllık: her
  satırı bir ay olan ısı haritası), en çok zaman geçen 4 uygulama/site (süre ve yüzde).
- Yerleşim: bütün içerik `GUVENLI_UST..GUVENLI_ALT` (250..1670) arasında; y değerleri dosyanın
  başındaki `Y_*` sabitlerinde. Bu bantların dışında yalnızca zemin ve imza var.

Dosyalar: `kart.py`, `ozet.py` (`seri_hesapla`, `GUN_ADLARI`), `web/api.py` (`/api/kart`,
`/api/seri`), `web/static/index.html` + `uygulama.js` (`kartiOlustur`) + `stil.css`,
`tests/test_kart.py`.

### Gizlilik güvencesi (bozma)

- Karta giden veri yalnızca `Adlandirici.etiket()` çıktısındaki adları içerir; pencere başlığı,
  sekme başlığı, video adı **hiçbir alanda yoktur**.
- `tests/test_kart.py::test_gizlilik_veride_baslik_yok` başlıklara gizli bir kelime gömüp
  `kart_verisi()` çıktısında geçmediğini doğrular. Karta yeni alan eklersen bu testi genişlet.
- `kart_ciz()` içine `depo` parametresi ekleme; "veride olmayan çizilemez" kuralı bu ayrıma dayanıyor.

### Kalan işler 🔲

- ✅ Instagram güvenli alanı, geçmiş tarih, aylık ve yıllık kart yapıldı. ❓ 250 px'lik güvenli alan
  ölçüsü ezberden; gerçek bir hikâyede deneyip gerekirse `GUVENLI_*` ve `Y_*` sabitlerini kaydır.
- Seri, geçmiş tarihli kartta o tarihe göre hesaplanır ama "o gün henüz bitmedi" kuralı o güne de
  uygulanır (küçük bir tutarsızlık; önemli değil).
- **Seçenekler:** uygulama listesini gizle (yalnızca süre paylaş), renk teması, üstteki ad
  ("HEATMAP" yerine kullanıcının seçtiği metin; `[kart] baslik`).
- **Panoya kopyala** (`navigator.clipboard.write` + `ClipboardItem`) ve telefona aktarma kolaylığı.
- Uygulamanın adı kartta "HEATMAP" yazıyor (2026-11 ad değişikliği). Eski veritabanı `ders_takip.db` ilk açılışta `heatmap.db`ye taşınır (`main.eski_veritabanini_tasi`).

### Tuzaklar

- ⚠️ **Yazı tipi:** `C:\Windows\Fonts\segoeui*.ttf` kullanılıyor; bulunamazsa Pillow varsayılanına
  düşer ve Türkçe karakterler/ölçüler bozulur. Başka işletim sistemi desteği gerekirse depoya
  açık lisanslı bir yazı tipi ekle.
- ⚠️ **Sabit koordinatlar:** bölümler elle yerleştirildi (`Y_*` sabitleri). Bir bölümün yüksekliğini
  değiştirince alttakilerle çakışmayı gözle kontrol et: örnek veriyle dört türü de PNG olarak üretip
  250 ve 1670 çizgilerini işaretleyerek bak. 4. uygulama satırı y≈1635'te bitiyor.
- ⚠️ Aylık takvimde ay 6 haftaya yayılırsa satır yüksekliği küçülür (`_ay_takvimi` içindeki `adim_y`).
- ⚠️ **Uzun adlar** `_sigdir` ile kesilir; kutucuklardaki uzun değerler küçük yazı tipine düşer.
  Yeni metin eklerken en uzun olası değeri dene ("12 sa 48 dk", "%227").
- ⚠️ **Yarı saydam çizim** için `ImageDraw.Draw(resim, "RGBA")` kullanılıyor; RGB çizimde dördüncü
  değer yok sayılır.
- ⚠️ **Önbellek:** yanıt `Cache-Control: no-store`; arayüz ayrıca adrese zaman damgası ekliyor.
- ⚠️ Seri hesabı gün başına bir sorgu yapar (en fazla 366); çok uzun serilerde yavaşlarsa tek
  sorguya çevir.

---

## 4. Windows arka plan dashboard'u ve Health Connect 🔲

### 4.1 Windows arka plan dashboard'u

> ✅ **İlk sürüm yapıldı:** `GET /dashboard` (`web/static/dashboard.html`, tek dosya, kendi CSS/JS'i)
> ve başlıksız özet ucu `GET /api/dashboard` (`simdiki` alanı `Adlandirici.etiket` ile okunabilir
> ada çevrilir). Sayfa başlığı "Takip Paneli · Masaüstü" olduğu için `yok_sayilan_basliklar`
> kuralına takılır. 5 sn'de bir yeniler; Heatmap kapalıysa "Heatmap kapalı" yazar. `?saydam=1`.
> Kalanlar: 🔲 Lively Wallpaper ile gerçek masaüstünde denenmedi (❓ duvar kâğıdı sürecinin ön plan
> penceresi sayılıp sayılmadığı hâlâ doğrulanmalı), 🔲 Rainmeter görünümü, 🔲 çoklu monitörde konum
> ayarı. Aşağıdaki plan, bu kalanlar için hâlâ geçerli.

Hedef: masaüstü arka planında bugünkü süre, sayaç durumu, haftalık grafik ve seri.

**Seçilen yol:** dashboard'u **uygulamanın kendisi sunar** (`GET /dashboard`), masaüstüne bir
"web sayfası duvar kâğıdı" aracıyla (örn. Lively Wallpaper) `http://127.0.0.1:8765/dashboard`
adresi verilir. Seçenek olarak Rainmeter görünümü de yazılabilir.

Neden: sayfa aynı kökenden geldiği için **CORS açmaya gerek kalmaz**. Yerel bir `.html` dosyasından
(`file://`) API'yi çağırmak CORS'u `null` kökenine açmayı gerektirir; bu, bilgisayardaki herhangi
bir yerel sayfanın pencere başlıklarını okuyabilmesi demektir. Yapma.

Dokunulacak dosyalar:

| Dosya | Değişiklik |
|---|---|
| `web/static/dashboard.html`, `dashboard.css`, `dashboard.js` (yeni) | Tam ekran, saydam/koyu zemin, büyük yazı; `/api/durum`, `/api/ozet/hafta`, `/api/seri`, `/api/dokum` okur |
| `web/api.py` | `GET /dashboard` rotası |
| `config/config.ornek.toml` | `[baslik] yok_sayilan_basliklar` içine dashboard sayfa başlığı |
| `README.md` | Kurulum adımları |
| (isteğe bağlı) `dashboard/rainmeter/` | Rainmeter görünümü |

Tuzaklar:

- ⚠️ **Dashboard'da pencere başlığı gösterme.** Arka plan ekran paylaşımında ve ekran görüntülerinde
  görünür. Yalnızca süre, durum ve okunabilir uygulama adları. `/api/durum` başlık döndürüyor;
  dashboard için başlıksız ayrı bir uç (`/api/dashboard`) daha güvenli.
- ⚠️ **Sayfa başlığı** `yok_sayilan_basliklar` kuralına uymalı ("Takip Paneli" ile başlat); duvar
  kâğıdı aracı bazen ön plan penceresi sayılır ve sayacı etkileyebilir. ❓ Duvar kâğıdı sürecinin
  ön plan penceresi olarak görünüp görünmediğini dene; görünüyorsa süreci `[pencere]` altında yeni
  bir "yok sayılan süreçler" listesine al (`DEVAM` hükmü zaten var).
- ⚠️ **Uygulama kapalıyken** dashboard boş kalır: bağlantı yoksa sade bir "kapalı" durumu göster.
  Windows açılışında otomatik başlatma da bu işin parçası (`shell:startup` içine `baslat.bat`
  kısayolu, `--sessiz` ile; ⚠️ `baslat.bat` şu an bayrak geçirmiyor).
- ⚠️ **Sorgu sıklığı:** saniyede bir `/api/durum` yeter; diğerleri 30–60 sn. Duvar kâğıdı sürekli
  çalışır, pil tüketir.
- ⚠️ Rainmeter seçilirse JSON'u regex ile ayrıştırır; onun için düz, sabit sıralı bir uç hazırla.

### 4.2 Health Connect birleştirmesi

> ✅ **Veri modeli ve elle giriş (yol C) yapıldı:** `saglik_gunluk` tablosu (`depo.saglik_kaydet`
> boş alanı değiştirmez, aynı gün tekrar kaydedilince üzerine yazar), `GET/POST/DELETE /api/saglik`,
> `/api/gunluk` artık sağlık alanlarını da döndürür (`depo.gunluk_birlesik`), arayüzde form ve
> haftalık grafikte gün altı satırı. Kart ve dashboard'a bilerek eklenmedi.
> Kalan: 🔲 yol A (dışa aktarım dosyası içe aktarıcı, `saglik.py`): kullanıcıdan gerçek bir dışa
> aktarım dosyası gelmeden yazma; biçim bilinmiyor. İçe aktarıcı `depo.saglik_kaydet(..., kaynak="health_connect")`
> çağırmalı. Şema sürümleme hâlâ yok; yeni tablo eklemek için gerekmedi, ama mevcut tabloya sütun
> eklenecekse `Depo._semayi_guncelle` kalıbını kullan.

Hedef: telefondaki adım ve spor verisini günlük çalışma süresiyle aynı tabloda/kartta göstermek.

Temel kısıt: Health Connect verisi **telefonda** durur; bilgisayardan doğrudan okunacak bir bulut
API'si yoktur. Veri bir şekilde bilgisayara taşınmalı.

| Yol | Artı | Eksi |
|---|---|---|
| **A. Dosya dışa aktarımı** (Health Connect'in dışa aktarma özelliği → bulut klasörü → bilgisayarda eşitlenen klasör → içe aktarma betiği) | Sunucu ayarı değişmez, ek uygulama yazılmaz | Gecikmeli; biçim Google'a bağlı |
| B. Telefonda küçük bir Android uygulaması veriyi yerel ağdan bilgisayara gönderir | Güncel veri | Android uygulaması yazmak gerekir; sunucuyu yerel ağa açmak gerekir |
| C. Elle giriş (arayüzde adım sayısı yaz) | En basit | Otomatik değil |

**Seçilen yol: A**, yedek olarak C. ❓ Health Connect'in dışa aktarma özelliğinin kullanıcının
telefonunda bulunduğunu, dosya biçimini (zip içinde SQLite olduğunu sanıyorum) ve tablo adlarını
**uygulamadan önce gerçek bir dışa aktarım dosyasıyla doğrula**; burada kesin bilgi yok.
B'yi seçmek sunucuyu `127.0.0.1` dışına açmak demektir: kullanıcıya sormadan yapma, yapılırsa
kimlik doğrulama (paylaşılan anahtar) ve yalnızca tek bir yazma ucu ile sınırla.

Veri modeli (`depo.py`):

```sql
CREATE TABLE saglik_gunluk (
    tarih        TEXT PRIMARY KEY,   -- YYYY-AA-GG, yerel gün
    adim         INTEGER,
    egzersiz_dk  INTEGER,
    uyku_dk      INTEGER,
    kaynak       TEXT,               -- 'health_connect' | 'elle'
    guncelleme   REAL
);
```

Dokunulacak dosyalar:

| Dosya | Değişiklik |
|---|---|
| `depo.py` | **Önce şema sürümleme** (`PRAGMA user_version` + sıralı taşıma fonksiyonları), sonra `saglik_gunluk` ve okuma/yazma |
| `saglik.py` (yeni) | Dışa aktarım dosyasını okuyup günlük toplamları çıkaran içe aktarıcı; komut satırından ve API'den çağrılabilir |
| `web/api.py` | `GET /api/saglik?baslangic=&bitis=`, `POST /api/saglik/ice-aktar`, `/api/gunluk` çıktısına isteğe bağlı alanlar |
| `config/config.ornek.toml` | `[saglik] etkin`, `klasor` (eşitlenen klasör yolu) |
| `web/static/*` | Haftalık grafikte adım/egzersiz, elle giriş formu |
| `kart.py` | İsteğe bağlı sağlık kutucuğu (varsayılan **kapalı**) |
| `tests/test_saglik.py` (yeni) | Sahte dışa aktarım dosyasıyla içe aktarma, gün sınırı, yinelenen kayıt |

Tuzaklar:

- ⚠️ **Şema değişikliği:** şu an `CREATE TABLE IF NOT EXISTS` var, taşıma düzeni yok. Kullanıcının
  gerçek veritabanı var; sütun eklemeden önce sürümleme kur ve taşıma öncesi dosyayı yedekle.
- ⚠️ **Gün sınırı ve saat dilimi:** Health Connect kayıtları UTC anlık zaman + bölge farkı taşır;
  çalışma süreleri yerel güne göre toplanıyor (`depo.gun_araligi`). Adımları da **yerel güne** göre
  topla, yoksa gece yarısı civarı kayıtlar yanlış güne düşer.
- ⚠️ **Yinelenen veri:** aynı adımlar hem telefon hem saat tarafından yazılabilir. Ham kayıtları
  toplarsan çift sayarsın; Health Connect'in birleştirilmiş (aggregate) değerini ya da tek bir
  kaynağı kullan. İçe aktarma **tekrar çalıştırılabilir** olmalı (`INSERT ... ON CONFLICT DO UPDATE`).
- ⚠️ **Sağlık verisi hassastır.** `data/` altında kalır (Git dışı). Paylaşım kartına ve dashboard'a
  yalnızca kullanıcı açıkça isterse girer; `test_kart.py` gizlilik testini buna göre genişlet.
- ⚠️ **Eşitlenen klasördeki dosya yarım olabilir** (eşitleme sürerken). Dosya boyutu sabitlenene
  kadar bekle, bozuk dosyada sessizce atla ve günlüğe yaz.
- ⚠️ Dışa aktarım dosyası kullanıcının belirttiği klasörden okunur; yolu ayardan al, başka yere bakma.

---

## 5. Diğer işler (kısa)

- **API testleri:** `tests/test_api.py` FastAPI `TestClient` kullanır; `httpx` gerekir
  (`requirements-dev.txt`, CI bunu kurar). ⚠️ `TestClient(app, base_url="http://127.0.0.1")` şart:
  varsayılan "testserver" adı `TrustedHostMiddleware`'e takılır. ⚠️ Kurulu Starlette sürümü
  "httpx yerine httpx2 kullanın" diye kullanımdan kaldırma uyarısı basıyor; şimdilik zararsız,
  ileride `requirements-dev.txt` güncellenmeli (önce httpx2'nin uyumunu doğrula).
  ⚠️ `POST /api/otomatik-baslatma` bilerek test edilmez (gerçek kayıt defterini değiştirir).

- **Tespit doğruluğu:** tarayıcı eklentisi (Bölüm 2), `pycaw` ile ses oturumundan "video oynuyor
  mu", ✅ Store uygulamalarında `ApplicationFrameHost.exe` yerine gerçek süreç
  (`windows_api.pencerenin_sureci`: çerçevenin başka sürece ait ilk alt penceresi; küçültülmüş
  uygulamada bulunamazsa çerçeve adı kalır), boşta eşiğinin ilk
  120 saniyesini geriye dönük düşme.
- **Arayüz:** ayarları arayüzden düzenleme, düzeltmeyi geri alma, çok kısa oturumları gizleme,
  aylık görünüm, başlıktan anahtar kelime önerisi, README için ekran görüntüsü.
- **Proje sağlığı:** lisans dosyası (yoksa "tüm hakları saklı" sayılır; kullanıcıya sor),
  GitHub Actions ile test, `ruff`, iç kod adlarını (`DERS`, `ders_sn`...) "çalışma" anlamına taşıma.
- **GitHub:** depo https://github.com/Mswindler-Mert/Heatmap (uzak ad: `origin`, dal: `main`).
  Commit e-postası GitHub noreply adresi (`70340171+Mswindler-Mert@users.noreply.github.com`);
  kullanıcının kişisel e-postası geçmişten temizlendi, yeni commit'lerde de kullanılmamalı.
- **Proje klasörü** hâlâ `ders-takip` adında. Kullanıcı taşırsa `.venv` bozulur: silip
  `baslat.bat` ile yeniden kurmak gerekir.
- ✅ **Isı haritası** (projenin adı buradan): arayüzde "Son 12 ay" bölümü (`/api/isi-haritasi`,
  `ozet.isi_haritasi`, `ozet.seviye`), kartta aylık/yıllık türler. Seviye 0-4 günlük hedefe göre.
  `depo.gunluk_sureler` artık tek sorgu atıyor ve gece yarısını geçen oturumu günlere bölüyor.
- ✅ **Windows açılışında başlatma:** `heatmap/otomatik_baslatma.py` + `baslat.pyw`; HKCU `Run`
  anahtarına "Heatmap" değeri yazılır. Arayüzün sağ üstündeki kutu, tepsi menüsü ve
  `/api/otomatik-baslatma` ile açılıp kapanır; klasör taşınırsa açılışta komut kendini günceller.
  ⚠️ Testler gerçek `Run` anahtarına dokunmaz, geçici bir test anahtarı kullanır; öyle kalmalı.

## 6. Doğrulanmamış varsayımlar (ilk iş bunlara bak)

- `config/config.toml` içindeki `?` işaretli süreç adları: `Gemini.exe`, `Copilot.exe`,
  `Goodnotes.exe`, `iLovePDF.exe`, `AppleTV.exe`. Gerçek adlar düzeltme ekranında "belirsiz"
  oturum olarak görünür.
- Brave/Edge sekme başlığı temizleme düzenli ifadeleri (`baslik._TARAYICI_SONEKI`) yalnızca örnek
  başlıklarla test edildi; Brave'de profil adı ya da "ve N sekme daha" eki varsa `basligi_temizle`'ye ekle.
- Tepsi ikonu ve menüsü (yeni "Windows açılışında başlat" seçeneği dahil) gözle denenmedi.
- Paylaşım kartı, döküm ve ısı haritası arayüzü yalnızca örnek veriyle denendi; kullanıcının gerçek
  verisiyle bakılmadı. Eski veritabanının `heatmap.db`ye taşınması gerçek veride çalıştı.
- MediaPipe API adları, Health Connect dışa aktarım biçimi ve Instagram güvenli alan ölçüsü (yukarıda ❓).
