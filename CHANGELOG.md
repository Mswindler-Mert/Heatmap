# Değişiklik günlüğü

Sürüm numarası `heatmap/__init__.py` içindeki `__version__` değeridir ve arayüzün en altında görünür.

## Yayımlanmamış

- Veritabanı şeması artık numaralı sürümlerle güncelleniyor; eski bir veritabanı açılınca eksik
  adımlar sırayla ve önce yedek alınarak uygulanıyor (`data/yedek/heatmap-gocmeden-once-*.db`).
- Tarih aralığı sorguları için yeni dizin.
- **Ayarlar sayfası:** günlük hedef, süreler, uygulama ve site listeleri, kart yazısı gibi ayarlar
  arayüzden değiştirilebiliyor; `config.toml`'daki yorumlar korunuyor, eski hâli yedekleniyor ve
  değişiklik yeniden başlatmadan uygulanıyor.
- `baslat.bat`, `requirements.txt` değiştiğinde paketleri kendiliğinden kuruyor.

## 0.3.0 (2026-11-21)

**Yeni**

- **Kamera modülü (deneysel, varsayılan kapalı):** ayrı süreçte çalışan kamera işçisi; masadaysan
  klavyeye dokunmasan da sayaç durmaz, kalkınca durur ve kalkış anına geri çekilir; uzun süre aşağı
  bakınca süre "belirsiz" olur. Arayüzde ve tepside aç/kapat, 6 saniyelik kalibrasyon. Görüntü
  kaydedilmez ve gönderilmez. Gerçek kamerayla henüz denenmedi.
- **Sağlık verisi:** adım, egzersiz ve uyku elle girilebilir; haftalık grafikte görünür,
  `/api/gunluk` çalışma süresiyle birlikte döndürür.
- **Kategoriler:** dökümde ve paylaşım kartında süre Kod, Yapay zekâ, Belge ve not, Video ve kurs,
  İletişim gibi gruplara göre gösterilebilir (`[kategoriler]`).
- **Paylaşım kartı:** panoya kopyala, alttaki listeyi uygulama/kategori/hiç seçme, sol üstteki
  yazıyı değiştirme (`[kart] ust_metin`).
- **CSV dışa aktarma:** günlük özet ve oturumlar, Türkçe Excel'de doğrudan açılır.
- **Günlük otomatik yedek:** `data/yedek/` altında son 7 gün.
- **Düzeltme ekranı:** düzeltmeyi geri alma, 1 dakikadan kısa oturumları gizleme.

**İyileştirme**

- Microsoft Store uygulamaları (Ayarlar, Hesap Makinesi...) gerçek adlarıyla tanınır.
- Ayar dosyasında yazım hatası ya da yanlış türde değer varsa program yine açılır, sorunu
  arayüzün üstünde gösterir.
- Açılışta ya da çalışırken çökme olursa hata günlüğe yazılır ve bir uyarı penceresi çıkar.
- Kod taraması (`ruff`) ve API testleri; GitHub'da her push'ta Windows üzerinde çalışır.

## 0.2.0 (2026-11-21)

**Yeni**

- Proje adı **Heatmap** oldu (paket `heatmap`); eski `ders_takip.db` ilk açılışta taşınır.
- **Son 12 ay ısı haritası** (GitHub katkı grafiği gibi) ve seri istatistikleri.
- **Paylaşım kartı:** Instagram güvenli alanı, geçmiş tarih, aylık (takvim) ve yıllık kartlar.
- **Windows açılışında otomatik başlatma** (arayüz ve tepsi menüsünden aç/kapat).
- **Brave/Chrome eklentisi:** site adı ve sekmenin ses durumu; duraklatılmış video artık
  izleniyor sayılmaz; siteye göre kurallar ve "bu siteyi hep böyle say".
- **Masaüstü dashboard'u** (`/dashboard`): duvar kâğıdı araçları için sade panel.

**Güvenlik**

- Veri değiştiren istekler `X-Heatmap` başlığı ister; başka web siteleri tarayıcın üzerinden
  Heatmap'e gizlice istek gönderemez.

## 0.1.0 (2026-11-16)

İlk sürüm ("Ders Takip" adıyla).

- Aktif pencere, sekme başlığı ve klavye/fare boşta kalma dedektörleri; tolerans süreli karar motoru.
- SQLite kaydı, düzeltme ekranı ve düzeltmelerden öğrenme.
- Okunabilir uygulama adları, siteye göre döküm, günlük hedef ve seri.
- 1080×1920 günlük/haftalık paylaşım kartı.
- Koyu temalı web arayüzü, sistem tepsisi, JSON API, `baslat.bat`.
