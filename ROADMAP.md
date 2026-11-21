# Yol haritası: ağır işler

Bu dosya, büyük ve uzun sürecek işlerin sırasını ve durumunu tutar. Her adım bitince bu dosya
güncellenir, commit'lenir ve GitHub'a gönderilir; bir oturum yarıda kesilirse sıradaki adımdan
devam edilir. Ayrıntılı tasarım notları ve tuzaklar için [SONRAKI_ADIMLAR.md](SONRAKI_ADIMLAR.md).

Durum işaretleri: ✅ bitti · 🟡 sürüyor · 🔲 sırada

Kurallar (her adım için):

- Kod yorumlu ve Türkçe; mevcut kod adlarına (`DERS`, `ders_sn`...) dokunulmaz.
- Kullanıcının gerçek verisine (`data/`) ve gerçek ayarına (`config/config.toml`) testlerde dokunulmaz.
- Adım bitmeden önce: `ruff check .` temiz, bütün testler geçiyor, gerekiyorsa önizlemede denendi.
- Her adım ayrı commit(ler); GitHub Actions yeşil olmadan sonraki adıma geçilmez.

---

## 1. Veritabanı şema sürümleme ✅

**Neden:** Şu an yeni sütunlar `ALTER TABLE` ile tek tek, elle ekleniyor. İleride her değişiklik
kullanıcının gerçek verisini riske atar. Numaralı taşıma (migration) düzeni olursa her değişiklik
bir kez, sırayla ve öncesinde yedek alınarak uygulanır.

**Yapılacak:** `PRAGMA user_version` ile sürüm; `depo.py` içinde sıralı taşıma listesi (mevcut
şema = sürüm 1, `alan_adi` sütunu = sürüm 2, sağlık tablosu = sürüm 3); taşıma öncesi otomatik
yedek (`data/yedek/heatmap-gocmeden-once-vN.db`); bugüne kadarki her şema durumundan (en eski
"Ders Takip" veritabanı dahil) güncel şemaya geçişi deneyen testler.

**Bitti sayılır:** Eski şemalı veritabanları veri kaybı olmadan güncelleniyor, aynı veritabanı
ikinci kez açıldığında hiçbir taşıma çalışmıyor, testler geçiyor.

**Sonuç:** `heatmap/sema.py` (taşımalar 1–4; 4 = yeni `oturumlar(bitis)` dizini), `Depo(yol,
yedek_klasoru=)`, `tests/test_sema.py`. Kullanıcının gerçek veritabanının salt okunur kopyasında
denendi: aşama 1 olarak tanındı, 2-3-4 uygulandı, 350 oturum ve 2 kural korundu, önce yedek alındı.

## 2. Ayarlar sayfası ✅

**Neden:** Bugün her ayar değişikliği Not Defteri'nde TOML düzenlemek ve programı yeniden
başlatmak demek. Yeni başlayan biri için en büyük sürtünme bu.

**Yapılacak:** Arayüzde "Ayarlar" bölümü: günlük hedef, tolerans süreleri, boşta eşikleri,
çalışma / çalışma dışı uygulama listeleri, site listeleri, kart üst metni... Kaydetme `tomlkit`
ile yapılır; böylece `config.toml`'daki yorumlar ve düzen korunur. Kaydedince ayarlar yeniden
başlatmadan uygulanır (karar motoru, dedektörler, adlandırıcı yeniden kurulur). Kaydetmeden önce
eski dosya yedeklenir.

**Bitti sayılır:** Arayüzden yapılan değişiklik dosyada yorumları bozmadan görünüyor, program
yeniden başlatılmadan yeni ayarla çalışıyor, yanlış değer (örn. eksi süre) kaydedilmiyor.

**Sonuç:** `heatmap/ayar_duzenleyici.py` (alanlar, doğrulama, `tomlkit` ile yazma), `/api/ayarlar`,
`api.Ortam` (ayara bağlı nesneler canlı yenilenir), `Takipci.ayarlari_uygula`, `main.ayarlari_yeniden_yukle`,
arayüzde "Ayarlar" bölümü. Kullanıcının gerçek `config.toml`'unun kopyasında denendi: fark yalnızca
değişen satırlar, yorumlar yerinde, önce yedek. `baslat.bat` artık `requirements.txt` değişince paket kurar.
Kalan (ileride): okunabilir adlar / siteler / kategoriler tablolarını da arayüzden düzenlemek.

## 3. Günlük zaman çizelgesi ✅

**Neden:** Döküm "ne kadar" sorusunu cevaplıyor, "ne zaman" sorusunu değil. Günün saat saat
renkli bir şeridi, odağın nerede bölündüğünü tek bakışta gösterir.

**Yapılacak:** `/api/zaman-cizelgesi?tarih=` (oturumların başlangıç-bitiş ve hükmü, okunabilir
adlarla); arayüzde 00:00–24:00 şerit, renk = çalışma / çalışma değil / belirsiz, üzerine gelince
uygulama ve süre; dokunmatik ve dar ekranda da çalışır.

**Bitti sayılır:** Seçilen günün şeridi doğru, dar ekranda taşma yok, pencere başlığı yalnızca
gerektiğinde ve yalnızca yerel arayüzde görünüyor.

**Sonuç:** `ozet.zaman_cizelgesi` (günle kırpma, okunabilir adlar, başlık YOK), `/api/zaman-cizelgesi`,
"Oturumlar" kartının üstünde şerit (görünen aralık kullanılan saatlere göre, en az 6 saat;
üzerine gelince/dokununca ayrıntı). Pencere başlığı hiç döndürülmediği için gizlilik kuralı daha da sıkı.

## 4. Düzeltmelerden öğrenen yerel sınıflandırıcı ✅

**Neden:** Bugün öğrenme yalnızca "aynı başlık" ya da "elle girilen anahtar kelime". Kullanıcı
yüzlerce oturumu düzelttikçe, benzer başlıklar da kendiliğinden tanınabilir.

**Yapılacak:** Ek paket olmadan, saf Python ile küçük bir Naive Bayes sınıflandırıcı: düzeltilmiş
tarayıcı oturumlarının başlıklarından öğrenir. Önce yalnızca **öneri** olarak düzeltme ekranında
görünür ("%87 çalışma olabilir"); `[tahmin]` ayarıyla, güven eşiğini geçen tahminlerin otomatik
karar vermesi açılabilir (varsayılan kapalı). Model her açılışta yeniden eğitilir, ayrı dosya yok.

**Bitti sayılır:** Ayrı tutulan test verisinde doğruluk ölçülüyor, öneriler arayüzde görünüyor,
otomatik karar kapalıyken davranış değişmiyor.

**Sonuç:** `heatmap/tahmin.py` (çok terimli Naive Bayes, 5 katlı çapraz doğrulama: doğruluk + kapsam),
`Tahminci` her düzeltmeden sonra yeniden eğitilir; `[tahmin]` ayarı (öneriler açık, otomatik karar
kapalı, eşik %90); düzeltme listesinde öneri rozeti; yeni "Karar bekleyenler" bölümü (bütün günler,
toplam süreye göre, tek tıkla toplu karar: `GET/POST /api/karar-bekleyenler`). Kullanıcının gerçek
verisinin kopyasında: 9 etiketli başlıkla model hazır, çapraz doğrulama %78, bekleyen 61 başlığın 8'ine
öneri. Kurallar her zaman tahminden önce gelir.

## 5. Tek dosya .exe ve GitHub Releases ✅

**Neden:** Şu an kullanmak için Python kurmak, sanal ortam oluşturmak gerekiyor. GitHub'dan bir
`.exe` indirip çift tıklamak, projeyi başkaları için gerçekten kullanılabilir kılar.

**Yapılacak:** PyInstaller ile paketleme; paketlenmiş hâlde `config/` ve `data/` klasörlerinin
`.exe`'nin yanında oluşması; otomatik başlatmanın `.exe`'yi göstermesi; GitHub Actions'ta
`v*` etiketiyle tetiklenen derleme ve Releases'e yükleme iş akışı. (Etiketi kullanıcı atar.)

**Bitti sayılır:** Yerelde derlenen `.exe` temiz bir klasörde açılıyor, arayüz çalışıyor,
iş akışı dosyası hazır ve belgelenmiş.

**Sonuç:** `paketle.py` (PyInstaller 6.22, tek dosya, konsolsuz, ikon), `requirements-build.txt`,
`ayarlar.kok_klasorleri` (paketliyken kaynaklar `sys._MEIPASS`, ayar/veri `.exe`'nin yanında),
otomatik başlatma `.exe`'yi gösterir, kamera işçisi `.exe`'yi yeniden çalıştırmaz.
`.github/workflows/surum.yml`: `v*` etiketiyle test + derleme + GitHub Sürümü; elle tetiklenirse
yalnızca derleme. Yerelde derlenen 23,5 MB'lık `.exe` boş bir klasörde 3 sn'de açıldı; arayüz,
dashboard, kart, ayarlar, takip döngüsü çalıştı. ❓ Sürüm iş akışı GitHub'da henüz hiç çalışmadı
(ilk etiketle çalışacak). `.exe` imzasız: Windows SmartScreen ilk açılışta uyarı gösterebilir.

---

## Faz 2: Arayüz, Motivasyon ve Kullanım Kolaylığı

1. ✅ **Yenilenen sol menülü arayüz:** 5 net sekme (Özet, Oturumlar, Karar Bekleyenler, Paylaşım Kartı, Ayarlar), dairesel günlük hedef halkası, 4'lü KPI özet kartları, haftalık hedef çizgisi, renk kodlu döküm.
2. 🔲 **Zinciri Kırma + Tıklanabilir Grafikler + En Verimli Saatler:**
   - Barış Özcan'ın *Zinciri Kırma* yaklaşımıyla görsel zincir: hedefe ulaşınca sürükle-tak veya otomatik takılan halkalar, hak edilen kalkan halkası (7 ardışık halkada 1), bronz kurtarma halkası, kilometre taşı renkleri.
   - Tıklanabilir ısı haritası ve haftalık çubuklar (tıklanan günün Oturumlar ekranını açar).
   - 24 saatlik "En verimli saatlerin" grafiği.
3. 🔲 **İsteğe Bağlı Kayan Mini Masaüstü Sayacı + Hedef Bildirimleri:**
   - Her zaman üstte duran, sürüklenebilir, yarı saydam mini sayaç penceresi (tepsi ve arayüzden istenilen zaman aç/kapat; isteğe bağlı odak zamanlayıcısı).
   - Günlük hedefe ulaşınca ve akşam zinciri kurtarmaya az kalınca sessiz Windows bildirimi.
4. 🔲 **Karar Bekleyenler Hızlı Temizlik & Ayarlar Tablo Düzenleyici:**
   - Tahminleri tek seferlik toplu uygulama düğmesi ve klavye kısayolları (`C`/`D`).
   - `[adlar]`, `[siteler]`, `[kategoriler]` tablolarını da Ayarlar sayfasından düzenlemek.
5. 🔲 **Ders / Proje Bazlı Takip:** VS Code proje adını yakalama + hızlı ders/proje etiketi ve dökümü.
6. 🔲 **Brave/Chrome eklentisi:** Gerçek tarayıcıda kurulum ve doğrulama (kullanıcının katılımıyla).
7. 🔲 **Kamera modülü:** Güvenlik/gizlilik doğrulamasıyla gerçek kamerayla ilk çalıştırma ve açı doğrulaması (kullanıcının katılımıyla).
8. 🔲 **Görsel bütünlük ve ilk sürüm (`v0.4.0`):** `/dashboard` yenilemesi, paylaşım kartı temaları, lisans, güncel `Heatmap.exe`, README ekran görüntüleri ve GitHub Release.
9. 🔲 **İleride:** Health Connect dışa aktarım içe aktarıcısı (gerçek dosya gelince) ve tahmin modeline ses/alan adı ağırlığı ekleme.
