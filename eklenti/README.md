# Heatmap Bağlantısı (tarayıcı eklentisi)

Heatmap'e tarayıcıda **hangi sitede** olduğunu ve **sekmenin ses çalıp çalmadığını** bildirir.
Eklenti olmadan da Heatmap çalışır, ama yalnızca sekme başlığına bakabilir. Eklentiyle:

- **Siteler doğru tanınır.** Başlığında site adı geçmeyen sayfalar artık "Diğer web" olmaz;
  dökümde ve paylaşım kartında gerçek site adı görünür (örn. `geeksforgeeks.org`).
- **Site listeleriyle sınıflandırma:** ayar dosyasındaki `ders_alanlari` / `ders_degil_alanlari`
  listeleri kullanılır (örn. `claude.ai` her zaman çalışma, `instagram.com` hiçbir zaman).
- **Duraklatılmış video sayılmaz.** Eklenti yokken klavye/fareye dokunmadan bir video sekmesinde
  30 dakikaya kadar "izliyor" sayılırsın. Eklentiyle yalnızca sekme gerçekten ses çalıyorsa sayılır;
  video duraklatılınca normal boşta kalma süresi (2 dk) geçerli olur.

## Gizlilik

Gönderilen tek şey: site adı (`youtube.com`), sekmenin ses çalıp çalmadığı ve tarayıcının önde olup
olmadığı. **Adresin tamamı, sayfa başlığı, sayfa içeriği ve geçmiş gönderilmez.** Bilgi yalnızca bu
bilgisayardaki Heatmap'e (`127.0.0.1:8765`) gider; internete hiçbir şey çıkmaz.

## Kurulum (Brave, Chrome, Edge)

1. Adres çubuğuna `brave://extensions` yaz (Chrome'da `chrome://extensions`, Edge'de `edge://extensions`).
2. Sağ üstteki **Geliştirici modu**'nu aç.
3. **Paketlenmemiş öğe yükle**'ye tıkla ve bu `eklenti` klasörünü seç.
4. Heatmap arayüzündeki "Modül sinyalleri" listesinde **Tarayıcı** satırı, tarayıcıya geçtiğinde
   site adını göstermeye başlar.

Eklenti dosyalarını değiştirirsen eklentiler sayfasında eklentinin yenile düğmesine bas.
Heatmap'in portunu ayardan değiştirdiysen `manifest.json` ve `arkaplan.js` içindeki `8765`'i de değiştir.

## Sınırlar

- Sekme sesi kapalıyken (YouTube'un kendi ses düğmesiyle sessize alınmış video) "ses yok" sayılır.
- Eklenti tek tarayıcıya kurulur; başka bir tarayıcı öne geçerse Heatmap eski yönteme (başlık) döner.
