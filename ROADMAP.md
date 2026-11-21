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

## 1. Veritabanı şema sürümleme 🔲

**Neden:** Şu an yeni sütunlar `ALTER TABLE` ile tek tek, elle ekleniyor. İleride her değişiklik
kullanıcının gerçek verisini riske atar. Numaralı taşıma (migration) düzeni olursa her değişiklik
bir kez, sırayla ve öncesinde yedek alınarak uygulanır.

**Yapılacak:** `PRAGMA user_version` ile sürüm; `depo.py` içinde sıralı taşıma listesi (mevcut
şema = sürüm 1, `alan_adi` sütunu = sürüm 2, sağlık tablosu = sürüm 3); taşıma öncesi otomatik
yedek (`data/yedek/heatmap-gocmeden-once-vN.db`); bugüne kadarki her şema durumundan (en eski
"Ders Takip" veritabanı dahil) güncel şemaya geçişi deneyen testler.

**Bitti sayılır:** Eski şemalı veritabanları veri kaybı olmadan güncelleniyor, aynı veritabanı
ikinci kez açıldığında hiçbir taşıma çalışmıyor, testler geçiyor.

## 2. Ayarlar sayfası 🔲

**Neden:** Bugün her ayar değişikliği Not Defteri'nde TOML düzenlemek ve programı yeniden
başlatmak demek. Yeni başlayan biri için en büyük sürtünme bu.

**Yapılacak:** Arayüzde "Ayarlar" bölümü: günlük hedef, tolerans süreleri, boşta eşikleri,
çalışma / çalışma dışı uygulama listeleri, site listeleri, kart üst metni... Kaydetme `tomlkit`
ile yapılır; böylece `config.toml`'daki yorumlar ve düzen korunur. Kaydedince ayarlar yeniden
başlatmadan uygulanır (karar motoru, dedektörler, adlandırıcı yeniden kurulur). Kaydetmeden önce
eski dosya yedeklenir.

**Bitti sayılır:** Arayüzden yapılan değişiklik dosyada yorumları bozmadan görünüyor, program
yeniden başlatılmadan yeni ayarla çalışıyor, yanlış değer (örn. eksi süre) kaydedilmiyor.

## 3. Günlük zaman çizelgesi 🔲

**Neden:** Döküm "ne kadar" sorusunu cevaplıyor, "ne zaman" sorusunu değil. Günün saat saat
renkli bir şeridi, odağın nerede bölündüğünü tek bakışta gösterir.

**Yapılacak:** `/api/zaman-cizelgesi?tarih=` (oturumların başlangıç-bitiş ve hükmü, okunabilir
adlarla); arayüzde 00:00–24:00 şerit, renk = çalışma / çalışma değil / belirsiz, üzerine gelince
uygulama ve süre; dokunmatik ve dar ekranda da çalışır.

**Bitti sayılır:** Seçilen günün şeridi doğru, dar ekranda taşma yok, pencere başlığı yalnızca
gerektiğinde ve yalnızca yerel arayüzde görünüyor.

## 4. Düzeltmelerden öğrenen yerel sınıflandırıcı 🔲

**Neden:** Bugün öğrenme yalnızca "aynı başlık" ya da "elle girilen anahtar kelime". Kullanıcı
yüzlerce oturumu düzelttikçe, benzer başlıklar da kendiliğinden tanınabilir.

**Yapılacak:** Ek paket olmadan, saf Python ile küçük bir Naive Bayes sınıflandırıcı: düzeltilmiş
tarayıcı oturumlarının başlıklarından öğrenir. Önce yalnızca **öneri** olarak düzeltme ekranında
görünür ("%87 çalışma olabilir"); `[tahmin]` ayarıyla, güven eşiğini geçen tahminlerin otomatik
karar vermesi açılabilir (varsayılan kapalı). Model her açılışta yeniden eğitilir, ayrı dosya yok.

**Bitti sayılır:** Ayrı tutulan test verisinde doğruluk ölçülüyor, öneriler arayüzde görünüyor,
otomatik karar kapalıyken davranış değişmiyor.

## 5. Tek dosya .exe ve GitHub Releases 🔲

**Neden:** Şu an kullanmak için Python kurmak, sanal ortam oluşturmak gerekiyor. GitHub'dan bir
`.exe` indirip çift tıklamak, projeyi başkaları için gerçekten kullanılabilir kılar.

**Yapılacak:** PyInstaller ile paketleme; paketlenmiş hâlde `config/` ve `data/` klasörlerinin
`.exe`'nin yanında oluşması; otomatik başlatmanın `.exe`'yi göstermesi; GitHub Actions'ta
`v*` etiketiyle tetiklenen derleme ve Releases'e yükleme iş akışı. (Etiketi kullanıcı atar.)

**Bitti sayılır:** Yerelde derlenen `.exe` temiz bir klasörde açılıyor, arayüz çalışıyor,
iş akışı dosyası hazır ve belgelenmiş.
