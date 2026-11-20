# Heatmap

Windows'ta arka planda çalışıp **bilgisayar başında aktif geçen çalışma sürenizi kendiliğinden ölçen**,
bu sürenin hangi uygulama ve sitelerden geldiğini gösteren ve paylaşılabilir bir özet kartına çeviren yerel bir uygulama.
Kronometre değildir: başlat/durdur düğmesine basmazsınız. Uygulama öndeki pencereye, tarayıcı
sekmesinin başlığına ve klavye/fare hareketine bakar; sayacı kendisi başlatır ve durdurur.

- **Tamamen yerel:** hiçbir veri bilgisayarınızdan çıkmaz, hesap ya da internet gerekmez.
- **Takılıp çıkarılabilir modüller:** her tespit kaynağı ayrı bir dosyadır ve ayardan kapatılabilir.
- **Öğrenir:** karar veremediği oturumları siz işaretlersiniz, bir dahaki sefere kendisi tanır.
- **Paylaşım kartı:** günlük/haftalık özeti hikâye boyutunda bir görsele çevirir; kartta pencere
  başlıkları yer almaz, yalnızca uygulama ve site adları görünür.
- **JSON API:** veriyi başka araçlardan (masaüstü dashboard'u, sağlık verisi birleştirme) okuyabilirsiniz.

## Nasıl çalışır?

```
 Dedektörler (saniyede bir okunur)
 ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────────┐
 │ Aktif pencere│ │ Sekme başlığı│ │ Boşta    │ │ Kamera           │
 │ / süreç      │ │ / YouTube    │ │ kalma    │ │ (iskelet, kapalı)│
 └──────┬───────┘ └──────┬───────┘ └────┬─────┘ └────────┬─────────┘
        └────────────────┴── sinyaller ─┴────────────────┘
                              ▼
                      ┌───────────────┐
                      │  Karar motoru │  birleştir + tolerans süreleri
                      └───────┬───────┘
                              ▼
                      ┌───────────────┐      ┌─────────────────────────┐
                      │ SQLite        │◄────►│ FastAPI: JSON API +     │
                      │ (oturumlar)   │      │ koyu temalı web arayüzü │
                      └───────────────┘      └─────────────────────────┘
```

Her dedektör `ders`, `ders_degil`, `belirsiz` ya da `fikrim_yok` diyen bir sinyal üretir.
Karar motoru bunları şu kurallarla birleştirir:

| Durum | Sonuç |
|---|---|
| Önde ders uygulaması var (VS Code, PDF okuyucu…) | Sayaç çalışır |
| Önde ders dışı uygulama var (Steam, Discord…) | Sayaç durur |
| Önde tarayıcı var | Karar sekme başlığındaki anahtar kelimelere göre verilir |
| Başlıkta tanıdık kelime yok ya da çelişki var | **Belirsiz**: sayılmaz, sonradan düzeltilebilir |
| Klavye/fare uzun süredir kullanılmıyor | Sayaç durur |
| …ama video izleniyor | Durmaz (video için ayrı, daha uzun bir eşik vardır) |

**Tolerans:** anlık değişiklikler sayacı hemen etkilemez. Varsayılan ayarlarla dersten 15 saniyeden
kısa ayrılmalar yok sayılır; sayacın başlaması için 5 saniye kesintisiz ders durumu gerekir.

## Kurulum

Gerekenler: Windows 10/11 ve [Python](https://www.python.org/downloads/) 3.11 veya üstü.

```bat
git clone https://github.com/Mswindler-Mert/Heatmap.git
cd Heatmap
baslat.bat
```

`baslat.bat` dosyasına çift tıklamak da yeterlidir. İlk çalıştırmada sanal ortamı (`.venv`) kurar
ve paketleri yükler; sonraki açılışlarda doğrudan başlatır.

## Kullanım

- Uygulama açılınca saatin yanında (sistem tepsisinde) bir ikon belirir ve tarayıcıda arayüz açılır:
  <http://127.0.0.1:8765>
- İkon rengi: **yeşil** = sayaç çalışıyor, **sarı** = belirsiz, **gri** = sayaç durdu.
- İkona sağ tıklayınca: arayüzü aç, takibi duraklat, ayar dosyasını aç, Windows açılışında başlat, çıkış.
- **Windows açılışında başlat:** arayüzün sağ üstündeki kutudan ya da tepsi menüsünden açılır.
  Açıkken bilgisayarı her açtığında Heatmap tarayıcı açmadan arka planda başlar, böylece takibi
  başlatmayı unuttuğun günler kaybolmaz. Ayar, kullanıcı hesabının kayıt defterine (`Run` anahtarı)
  yazılır ve Görev Yöneticisi > Başlangıç uygulamaları altında da görünür.

Arayüzde yedi bölüm vardır:

1. **Şu an:** bugünkü toplam süre, sayacın durumu, algılanan uygulama ve her modülün sinyali.
2. **Bu hafta:** gün gün çalışma süresi.
3. **Son 12 ay (ısı haritası):** GitHub katkı grafiği gibi her gün bir kare; ne kadar uzun
   çalıştıysan o kadar koyu yeşil, günlük hedefi tutan günler en koyu. Altında seri ve en uzun seri.
4. **Süre nereden geldi?:** bugünkü ya da bu haftaki sürenin uygulamalara ve sitelere dağılımı.
5. **Paylaşım kartı:** günlük ya da haftalık özeti 1080×1920 PNG olarak üretir ve indirir.
6. **Oturumlar:** kayıtlı zaman dilimleri. Her birini “Dersti” / “Ders değildi” diye düzeltebilirsiniz.
   “Bundan sonra da böyle say” seçiliyse aynı uygulama ya da başlık artık otomatik tanınır.
   Tarayıcı oturumlarında isterseniz bir anahtar kelime (örn. kanal adı) de öğretebilirsiniz.
7. **Öğrenilen kurallar:** düzeltmelerden oluşan kurallar; buradan silinebilir.

## Ayarlar

İlk açılışta `config/config.ornek.toml` dosyası `config/config.toml` adıyla kopyalanır.
Kendi listelerinizi **`config/config.toml`** içinde düzenleyin (tepsi menüsünden de açılır),
sonra uygulamayı yeniden başlatın.

| Bölüm | Ne ayarlanır |
|---|---|
| `[tolerans]` | Sayacın başlama ve durma tolerans süreleri |
| `[pencere]` | Ders / ders dışı / tarayıcı süreç adları, bilinmeyen uygulamaların hükmü |
| `[baslik]` | Ders ve ders dışı anahtar kelimeler, video sitesi işaretleri, sayacı hiç etkilemeyen sekmeler |
| `[bosta]` | Boşta kalma eşiği ve video izlerken geçerli eşik |
| `[adlar]` | Süreç adı → dökümde görünen ad (`"Code.exe" = "VS Code"`) |
| `[siteler]` | Site adı → sekme başlığında aranan kelimeler; tanınmayanlar "Diğer web" olur |
| `[hedef]` | Günlük hedef (dakika); seri hesabında kullanılır |
| `[kamera]` | Kamera modülü (henüz geliştirilmedi) |

Her modül `etkin = false` ile kapatılabilir.

## JSON API

Sunucu yalnızca `127.0.0.1` üzerinde dinler. Etkileşimli dokümantasyon:
<http://127.0.0.1:8765/api/docs>

| Uç | Açıklama |
|---|---|
| `GET /api/durum` | Şu an algılanan durum, sayaç, bugünkü toplam |
| `GET /api/ozet/bugun` | Bugünkü ders süresi |
| `GET /api/ozet/hafta` | Bu haftanın gün gün süreleri |
| `GET /api/gunluk?baslangic=2026-11-01&bitis=2026-11-30` | Tarih aralığı için gün gün süre |
| `GET /api/dokum?baslangic=2026-11-16&bitis=2026-11-22` | Sürenin uygulamalara ve sitelere dağılımı (tarih verilmezse bugün) |
| `GET /api/seri` | Günlük hedef ve üst üste hedefe ulaşılan gün sayısı |
| `GET /api/isi-haritasi?bitis=2026-11-21&hafta=53` | Isı haritası: her gün için süre ve 0-4 seviye, seri istatistikleri |
| `GET /api/otomatik-baslatma` · `POST` (`{"acik": true}`) | Windows açılışında başlatma durumu |
| `GET /api/kart?tur=gunluk` | Paylaşım kartı (PNG); `tur=haftalik`, `indir=true` seçenekleri |
| `GET /api/oturumlar?tarih=2026-11-16` | Bir günün oturumları |
| `POST /api/oturumlar/{id}/duzelt` | Oturumu düzelt (`{"hukum": "ders", "ogren": true, "kelime": null}`) |
| `GET /api/kurallar` · `DELETE /api/kurallar/{id}` | Öğrenilen kurallar |
| `POST /api/duraklat` | Takibi duraklat / sürdür (`{"duraklat": true}`) |

Süreler saniye cinsindendir (`ders_sn`).

## Gizlilik

- Web sunucusu yalnızca bu bilgisayardan erişilebilir; uygulama internete hiçbir şey göndermez.
- Pencere başlıkları ve uygulama adları yalnızca `data/heatmap.db` dosyasında saklanır.
- `data/` klasörü ve `config/config.toml` `.gitignore` içindedir; depoya girmez.
- Kamera modülü geliştirildiğinde de görüntü kaydedilmeyecek ve gönderilmeyecek; yalnızca
  “yüz var / yok” gibi sonuçlar tutulacak. Kurallar `heatmap/dedektorler/kamera.py` başında yazılıdır.

## Proje yapısı

```
Heatmap/
├── baslat.bat                # çift tıkla başlat
├── config/config.ornek.toml  # varsayılan ayarlar (kişisel kopya: config.toml)
├── data/                     # veritabanı ve günlük dosyası (git dışı)
├── heatmap/
│   ├── main.py               # parçaları kurar ve başlatır
│   ├── ayarlar.py            # ayar dosyasını okur
│   ├── sinyal.py             # Sinyal ve Dedektor: modüllerin ortak dili
│   ├── windows_api.py        # aktif pencere ve boşta süresini Windows'tan okur
│   ├── dedektorler/          # pencere.py, baslik.py, bosta.py, kamera.py
│   ├── motor.py              # karar motoru
│   ├── takipci.py            # saniyelik takip döngüsü
│   ├── depo.py               # SQLite
│   ├── ozet.py               # okunabilir adlar, site ayırma, seri hesabı
│   ├── kart.py               # paylaşım kartı (PNG) çizimi
│   ├── tepsi.py              # sistem tepsisi ikonu
│   └── web/                  # api.py + static/ (HTML, CSS, JS)
└── tests/                    # motor, sınıflandırıcı ve uçtan uca testler
```

Kodu okumaya `sinyal.py` → `dedektorler/` → `motor.py` → `takipci.py` sırasıyla başlamak en kolayıdır.

## Geliştirme

```bat
.venv\Scripts\python -m unittest -v
.venv\Scripts\python -m heatmap --tepsisiz
```

İkinci komut uygulamayı tepsi ikonu olmadan terminalde çalıştırır; `Ctrl+C` ile kapanır.

Yeni bir tespit modülü eklemek için `heatmap/sinyal.py` içindeki `Dedektor` sınıfından türetin,
`oku()` metodunu yazın ve `main.py` içindeki `dedektorleri_kur()` fonksiyonuna ekleyin.

## Bilinen sınırlar

- Tarayıcıda site ayrımı sekme başlığına dayanır; başlığında site adı geçmeyen sayfalar
  "Diğer web" olarak toplanır.

- Sekme başlığından videonun oynayıp oynamadığı anlaşılamaz; duraklatılmış bir ders videosu,
  video eşiği dolana kadar ders sayılır.
- YouTube başlığında kanal adı yer almaz; kanala göre kural yazılamaz.
- Bazı Microsoft Store uygulamaları süreç adı olarak `ApplicationFrameHost.exe` gösterir.

Planlanan işler için [SONRAKI_ADIMLAR.md](SONRAKI_ADIMLAR.md) dosyasına bakın.
