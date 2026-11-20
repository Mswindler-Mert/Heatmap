// Heatmap Bağlantısı: Brave/Chrome eklentisinin arka plan betiği.
//
// NE YAPAR: Öndeki pencerenin etkin sekmesine bakar ve bilgisayardaki Heatmap
// uygulamasına (yalnızca 127.0.0.1, yani bu bilgisayar) üç bilgi gönderir:
//   alan_adi : sitenin adı, örn. "youtube.com"  (adresin geri kalanı GÖNDERİLMEZ)
//   sesli    : sekme şu an ses çalıyor mu (video oynuyor mu anlamak için)
//   odakta   : tarayıcı penceresi şu an önde mi
//
// Sayfa başlığı, adresin tamamı, sayfa içeriği ya da geçmiş GÖNDERİLMEZ.
// Heatmap kapalıysa istek sessizce başarısız olur; eklenti hiçbir şey saklamaz.

const ADRES = "http://127.0.0.1:8765/api/tarayici";

// Adresten yalnızca site adını çıkarır: "https://www.youtube.com/watch?v=..." -> "youtube.com".
// http/https dışındaki sayfalar (brave://, dosyalar, yeni sekme) için boş döner.
function alanAdi(adres) {
  try {
    const url = new URL(adres);
    if (url.protocol !== "http:" && url.protocol !== "https:") return "";
    return url.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

async function bildir() {
  let rapor = { alan_adi: "", sesli: false, odakta: false };
  try {
    // Kullanıcının en son odaklandığı pencere ve onun etkin sekmesi
    const pencere = await chrome.windows.getLastFocused({ populate: true });
    const sekme = (pencere.tabs || []).find((s) => s.active);
    if (sekme) {
      rapor = { alan_adi: alanAdi(sekme.url || ""), sesli: Boolean(sekme.audible), odakta: pencere.focused };
    }
  } catch {
    // Açık pencere yoksa boş rapor gider
  }
  try {
    await fetch(ADRES, {
      method: "POST",
      // X-Heatmap başlığı: Heatmap, web sitelerinden gelen sahte istekleri bununla ayırt eder.
      headers: { "Content-Type": "application/json", "X-Heatmap": "1" },
      body: JSON.stringify(rapor),
    });
  } catch {
    // Heatmap kapalı: sorun değil, bir sonraki olayda yeniden denenir.
  }
}

// Sekme değişince çok sayıda olay arka arkaya gelir; 300 ms bekleyip tek rapor gönder.
let bekleyen = null;
function yakinda_bildir() {
  clearTimeout(bekleyen);
  bekleyen = setTimeout(bildir, 300);
}

chrome.tabs.onActivated.addListener(yakinda_bildir);
chrome.tabs.onUpdated.addListener((_id, degisen) => {
  // Yalnızca işimize yarayan değişikliklerde: adres, ses durumu, yükleme bitti
  if ("url" in degisen || "audible" in degisen || degisen.status === "complete") yakinda_bildir();
});
chrome.windows.onFocusChanged.addListener(yakinda_bildir);

// Hiç olay olmasa bile (örn. aynı videoyu izlerken) 30 saniyede bir "hâlâ buradayım" de.
chrome.alarms.create("nabiz", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(bildir);
chrome.runtime.onStartup.addListener(bildir);
chrome.runtime.onInstalled.addListener(bildir);
