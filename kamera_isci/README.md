# Kamera işçisi (isteğe bağlı modül)

Heatmap'in kamera modülü, kameradan yalnızca **"masada mısın, kafan aşağıda mı"** sonucunu çıkarır.
Görüntü hiçbir zaman diske yazılmaz ya da gönderilmez; analizden sonra hemen silinir. Ana uygulamaya
giden tek şey her 2 saniyede bir tek satırlık bir sonuçtur (`yuz_var`, `pitch`...).

> **Durum:** Ana uygulama tarafı (dedektör, karar kuralları) ve sahte modla alt süreç hattı test edildi.
> Gerçek kamera + MediaPipe kısmı **henüz gerçek bir kamerayla denenmedi.**

## Ne işe yarar?

Kamera açıkken:

- **Masadaysan** klavye/fareye dokunmasan da (kitap okurken, video izlerken) sayaç durmaz.
- **Kafan uzun süre aşağıdaysa** (not alıyorsun ya da telefona bakıyorsun) 10 dakikaya kadar çalışma
  sayılır, sonra o süre "belirsiz" olur ve düzeltme ekranından sen karar verirsin.
- **Masada değilsen** (30 sn yüz görünmüyorsa) ve klavye/fare de kullanılmıyorsa sayaç durur.
- Kamera hiçbir zaman tek başına "çalışma" demez: ekranda oyun varken masada olmak çalışma değildir.

## Kurulum

1. (Önerilir) [Python 3.12](https://www.python.org/downloads/) kur. MediaPipe Python 3.14'ü henüz
   desteklemiyor olabilir.
2. Proje klasöründeki `kamera_kur.bat`'a çift tıkla. `.venv-kamera` adlı ayrı bir ortam kurar.
3. MediaPipe'ın **Face Landmarker** model dosyasını (`face_landmarker.task`) indirip proje
   klasöründe `modeller/` klasörüne koy. Dosya MediaPipe'ın resmî "Face Landmarker" belgelerindeki
   model bağlantısından indirilir. `modeller/` klasörü Git'e girmez.
4. `config/config.toml` içinde `[kamera]` bölümüne `etkin = true` yaz ve Heatmap'i yeniden başlat.
5. Arayüzdeki "Modül sinyalleri" listesinde **Kamera** satırı "masada" gibi bir durum göstermeli.

## Deneme (kamera olmadan)

```bat
.venv\Scripts\python kamera_isci\isci.py --sahte masada --aralik 1
```

Her saniye bir JSON satırı yazar; `Ctrl+C` ile durur. Senaryolar: `masada`, `yok`, `not_aliyor`,
`telefon`, `hata`.

## Kalibrasyon

Dizüstü kamerası ekranın üstünde olduğu için ekrana bakarken bile kafa biraz aşağı görünür.
Ekrana normal bakarken arayüzdeki Kamera satırında görünen açıyı `config.toml` içinde
`[kamera] ekran_pitch` olarak yaz. Bundan `asagi_fark_derece` (varsayılan 18) kadar aşağısı
"kafa aşağıda" sayılır.
