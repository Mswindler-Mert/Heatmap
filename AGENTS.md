# Antigravity Çalışma Kuralları (Heatmap / ders-takip)

Bu proje daha önce Claude Code ile geliştirildi. Asıl ayrıntılı devralma belgesi ve tasarım kararları **`SONRAKI_ADIMLAR.md`** (41 KB) ve **`ROADMAP.md`** dosyalarındadır.

## Oturum Başında Zorunlu Okuma

Kod yazmadan veya değişiklik önermeden önce şu iki dosyayı mutlaka oku:

1. `ROADMAP.md` — tamamlanan ve sırada bekleyen büyük işler.
2. `SONRAKI_ADIMLAR.md` — özellikle **Bölüm 0 (Devralan için)**, ilgili özellik bölümü ve **Bölüm 6 (Doğrulanmamış varsayımlar)**.

## Temel Çalışma Kuralları

- **Dil ve okunabilirlik:** Kullanıcı bilgisayar mühendisliği öğrencisi. Kod yorumlu, sade ve okunabilir olmalı. Dosya, değişken, yorum ve arayüz metinleri **Türkçe**.
- **Mevcut iç adlara dokunma:** `DERS`, `ders_sn`, `ders_surecleri` ve mevcut API alan adlarını kullanıcı özellikle istemeden değiştirme.
- **Önce tasarım, sonra kod:** Büyük veya anlamlı bir değişiklikten önce tasarımı kısaca anlat, onay al, sonra kodla.
- **Commit ve GitHub:** Her anlamlı adımda Türkçe ve ASCII karakterli mesajla commit at. Commit e-postası GitHub noreply adresi olmalı (`70340171+Mswindler-Mert@users.noreply.github.com`); kişisel e-posta kullanma. GitHub Actions yeşil olmadan sıradaki ağır işe geçme.
- **Sürüm ve değişiklik günlüğü:** Kullanıcıya görünen değişiklikleri `CHANGELOG.md` dosyasına ekle (`heatmap/__init__.py` içindeki `__version__` ile uyumlu olmalı).

## Ortam ve Doğrulama

- **Sistem:** Windows 11, Python 3.14.3 (`py` komutu var, `python` yok).
- **Sanal ortam:** `.venv\Scripts\python`
- **Kod taraması:** `.venv\Scripts\python -m ruff check .`
- **Testler:** `.venv\Scripts\python -m unittest` (`pytest` yok, ekleme).
- **Gerçek veriye dokunma:** Testlerde ve önizlemelerde kullanıcının gerçek `data/` klasörüne, `config/config.toml` dosyasına, kalibrasyon dosyasına ve Windows `Run` kayıt defteri anahtarına **asla dokunma**. Önizleme için geçici veritabanı ve farklı port (örn. 8766) kullan.
- **Yeniden başlatma uyarısı:** Kullanıcı uygulamayı `baslat.bat` ile port 8765'te açık tutuyor olabilir. Kod veya ayar değiştiğinde yeniden başlatması gerektiğini hatırlat.

## Kritik Teknik Kurallar ve Tuzaklar

- **Zaman parametredir:** Karar motoru ve `Takipci.tik(simdi)` içine `time.time()` gömme; dışarıdan parametre olarak ver.
- **Gizlilik ve güvenlik:**
  - Pencere/sekme başlıkları saldırgan kontrollü metindir; arayüzde yalnızca `textContent` kullan (`innerHTML` kullanma).
  - Paylaşım kartı (`kart.py`) ve masaüstü paneli (`dashboard.html`) asla ham pencere başlığı içermez; yalnızca `Adlandirici.etiket()` çıktısını kullanır.
  - Veri değiştiren (`POST`/`DELETE` vb.) tüm API istekleri `X-Heatmap: 1` başlığı ister.
  - Sunucu yalnızca `127.0.0.1` dinler; kullanıcıya sormadan gevşetme.
  - Kamera kareleri asla diske yazılmaz ve ağa gönderilmez.
- **Ayarlar ve şema:**
  - `config/config.toml` ve `data/` Git dışıdır; commit öncesi `git status` kontrol et.
  - Yeni her ayarı `config/config.ornek.toml` dosyasına da ekle. `config.toml` yazarken yalnızca `tomlkit` tabanlı `ayar_duzenleyici.dosyaya_yaz` kullan.
  - Veritabanı şema değişiklikleri için `heatmap/sema.py` içindeki `GOCLER` listesinin sonuna yeni taşıma ekle; mevcut taşımaları değiştirme.
- **Paketleme (`.exe`) ve Windows:**
  - Salt okunur uygulama dosyaları için `KAYNAK_KOK`, kullanıcı verisi/ayarları için `KOK` kullan (`heatmap/ayarlar.py`).
  - `.bat` dosyaları **CRLF ve ASCII** olmalı (Türkçe karakter koyma).
  - Türkçe büyük/küçük harfte `.upper()` / `.lower()` tuzağına dikkat et (`baslik._kucult()` / `kart.buyuk_harf()` kullan).
