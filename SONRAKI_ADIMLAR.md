# Sonraki adımlar

Bu dosya, projeye başka bir oturumda ya da başka bir modelle devam edebilmek için yazıldı.
Önce "Şu anki durum"u oku, sonra listeden bir iş seç.

## Şu anki durum (v0.1)

Çalışan ve test edilen kısımlar:

- Modül 1, 2, 3 (aktif pencere, sekme başlığı, boşta kalma) ve karar motoru.
- SQLite kaydı, düzeltme ve kural öğrenme (tam başlık, süreç, anahtar kelime).
- FastAPI JSON API, koyu temalı arayüz, sistem tepsisi ikonu, `baslat.bat`.
- 32 birim/uçtan uca test (`.venv\Scripts\python -m unittest -v`).

Henüz yapılmayanlar:

- Kamera modülü yalnızca iskelettir (`ders_takip/dedektorler/kamera.py`), kameraya dokunmaz.
- Tepsi ikonu ve menüsü elle denenmedi; yalnızca programın tepsi modunda açılıp API'ye yanıt
  verdiği doğrulandı.

## Mimari hatırlatma

- Her dedektör `sinyal.Dedektor` sınıfından türer ve `oku(onceki) -> Sinyal` döndürür.
- `motor.anlik_karar()` sinyalleri birleştirir; `motor.KararMotoru` toleransı uygular.
- `takipci.Takipci.tik()` saniyede bir çalışır ve geçişleri `depo.Depo` ile kaydeder.
- Zaman motorlara parametre olarak verilir (`simdi`), bu yüzden testler beklemeden çalışır.
- Geliştirme ortamı: Windows 11, Python 3.14, komut `py` (`python` komutu yok).

## Asıl hedef (proje sahibinin notu)

Amaç yalnızca "ders" süresi değil: **bilgisayar başında aktif/verimli geçen süreyi** ölçmek,
bu sürenin **hangi uygulamalardan geldiğini** görmek ve sonucu **paylaşılabilir** hale getirmek
(Strava'nın etkinlik kartı gibi, Instagram hikâyesine atılabilecek bir görsel). Bu yüzden
kişisel ayarda Teams, Unity, Outlook, yapay zekâ asistanları da "ders" (= çalışma) sayılıyor.

Bu hedefe giden işler:

- **Uygulama bazında döküm:** `oturumlar` tablosunda `uygulama` sütunu zaten var. Gün/hafta için
  uygulamaya göre toplam süre veren bir uç (`/api/dokum?baslangic=&bitis=`) ve arayüzde bir
  "nereden geldi" bölümü eklenmeli. Tarayıcı oturumlarında site/başlık bazında gruplama da düşünülmeli.
- **Kategori:** tek bir "ders" hükmü yerine süreçlere kategori (kod, not, toplantı, video…) atamak.
- **Adlandırma:** kodda ve arayüzde "ders" yerine "çalışma/aktif süre" demek daha doğru olabilir.
- **Paylaşım kartı:** günlük/haftalık özeti dikey (1080×1920) bir PNG olarak üreten uç
  (Pillow zaten kurulu). Kartta pencere başlığı gibi kişisel ayrıntı OLMAMALI; yalnızca toplam
  süre, uygulama dökümü ve seri gibi özet bilgiler.

## 1. Kamera modülü

Hedef: yüz var mı, kafa uzun süre aşağı eğik mi, telefona mı bakılıyor.

1. **Python sürümünü kontrol et.** MediaPipe yeni Python sürümlerini geç destekler. `pip install
   mediapipe opencv-python` 3.14'te başarısız olursa iki seçenek var: projeyi 3.12 ile kurulmuş
   ayrı bir venv'e taşımak ya da kamerayı ayrı bir süreç olarak 3.12'de çalıştırıp sonucu ana
   programa iletmek.
2. Paketleri `requirements.txt` yerine ayrı bir `requirements-kamera.txt` dosyasına koy; kamera
   kullanmayanlar büyük paketleri indirmek zorunda kalmasın.
3. `KameraDedektoru._gozlemle()` içini doldur: tek kare al, MediaPipe Face Landmarker ile analiz
   et, `KameraGozlemi` döndür, kareyi sil.
4. Kafa eğimi için yüz işaret noktalarından pitch açısını hesapla (`cv2.solvePnP` ya da
   Face Landmarker'ın dönüşüm matrisi).
5. `oku()` içinde süre koşullarını ekle: "yüz N saniyedir yok", "kafa N saniyedir eğik".
   Eşikler `config.ornek.toml` içindeki `[kamera]` bölümüne eklenmeli.
6. Her saniye yerine 2–3 saniyede bir kare işle; işlemci kullanımını ölç.
7. Kamera başka uygulamada meşgulse ya da yoksa `FIKRIM_YOK` dön, programı çökertme.
8. Arayüze "kamera açık" göstergesi ve aç/kapat düğmesi ekle.
9. Gizlilik kuralları (dosyanın başında yazılı) için test yaz: modülde `imwrite`, `VideoWriter`
   ve ağ çağrısı bulunmadığını kontrol eden basit bir kaynak taraması yeterli.

Karar motoru tarafı hazır: kamera `DERS_DEGIL` derse `anlik_karar()` sayacı durdurur
(`tests/test_motor.py::test_kamera_vetosu`). "Kitaptan çalışıyorum, ekrana dokunmuyorum" durumunu
kamerayla ders saymak istersen `anlik_karar()` içine yeni bir kural gerekir.

## 2. Tespit doğruluğu

- **Tarayıcı eklentisi:** sekmenin adresini (URL), YouTube kanal adını ve videonun oynayıp
  oynamadığını yerel API'ye gönderen küçük bir eklenti. Başlığa bakmaktan çok daha güvenilir olur
  ve duraklatılmış videonun ders sayılması sorununu çözer.
- **Ses tespiti:** eklenti olmadan "video oynuyor mu" bilgisi için Windows ses oturumlarına bakmak
  (`pycaw`).
- **Site bazlı kurallar:** başlıkta site adı geçenler için ayrı bir liste (örn. üniversitenin LMS'i).
- **Boşta kalma düzeltmesi:** eşik aşıldığında, boşta geçen ilk 120 saniye de geriye dönük olarak
  dersten düşülebilir (şu an sayılıyor).
- **Store uygulamaları:** `ApplicationFrameHost.exe` görünen pencerelerde asıl süreci bulmak.
- **Başlıktan kelime önerisi:** düzeltme ekranında başlıktaki kelimeleri tıklanabilir öneri olarak
  göstermek.

## 3. Arayüz ve kullanım

- Ayarları arayüzden düzenleme; ayar dosyası değişince yeniden başlatmadan yükleme.
- Windows açılışında otomatik başlatma (Başlangıç klasörüne kısayol ya da Görev Zamanlayıcı).
- Düzeltmeyi geri alma düğmesi ve çok kısa oturumları gizleme/birleştirme.
- Ders bazında süre: anahtar kelimeleri derslere bağlayıp "ML: 3 sa, Database: 2 sa" dökümü.
- Aylık görünüm, günlük hedef ve seri (streak) takibi.
- README için arayüz ekran görüntüsü.

## 4. Veri birleştirme

- **Windows arka plan dashboard'u:** `/api/durum` ve `/api/ozet/hafta` uçlarını okuyan bir
  Rainmeter görünümü ya da küçük bir masaüstü penceresi.
- **Health Connect:** telefon verisi (adım, spor) için önce veriyi bilgisayara getirme yolu
  seçilmeli (dosya dışa aktarımı ya da telefonda küçük bir uygulama). Sonra `saglik_gunluk`
  gibi ayrı bir tablo ve `/api/gunluk` çıktısına tarih üzerinden birleştirme.
- Veriyi CSV olarak dışa aktarma ucu.

## 5. Proje sağlığı

- Lisans dosyası ekle (örn. MIT); lisanssız depo "tüm hakları saklı" sayılır.
- GitHub Actions ile her push'ta testleri çalıştır.
- Veritabanı şeması değişirse basit bir sürüm/taşıma (migration) düzeni.
- `ruff` ile kod biçimi denetimi.
- İstenirse dosya ve değişken adlarını İngilizceye çevirme.
