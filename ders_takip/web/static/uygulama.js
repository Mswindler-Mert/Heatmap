// Arayüz mantığı: API'den JSON çeker ve sayfaya yazar. Kütüphane yok, düz JavaScript.
//
// ÖNEMLİ GÜVENLİK NOTU: Pencere/sekme başlıkları dışarıdan gelen metinlerdir
// (bir web sitesi başlığına istediğini yazabilir). Bu yüzden sayfaya metin
// koyarken HER ZAMAN textContent kullanıyoruz, asla innerHTML değil.

const HUKUM_ADI = {
  ders: "DERS",
  ders_degil: "DERS DEĞİL",
  belirsiz: "BELİRSİZ",
  fikrim_yok: "fikri yok",
};
const KAYNAK_ADI = { pencere: "Pencere", baslik: "Başlık", bosta: "Boşta", kamera: "Kamera", motor: "Motor" };
const KURAL_TURU = { surec: "Uygulama", baslik: "Tam başlık", kelime: "Kelime" };

const $ = (id) => document.getElementById(id);

// ---------- Küçük yardımcılar ----------

// Yeni bir HTML elemanı üretir: el("div", "sinif", "metin")
function el(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined) e.textContent = metin;
  return e;
}

async function api(yol, secenekler) {
  const yanit = await fetch(yol, secenekler);
  if (!yanit.ok) throw new Error(`${yol} -> ${yanit.status}`);
  return yanit.json();
}

function apiGonder(yol, yontem, govde) {
  return api(yol, {
    method: yontem,
    headers: { "Content-Type": "application/json" },
    body: govde ? JSON.stringify(govde) : undefined,
  });
}

const ikiHane = (n) => String(n).padStart(2, "0");

// 3725 -> "01:02:05"
function saatBicimi(sn) {
  return `${ikiHane(Math.floor(sn / 3600))}:${ikiHane(Math.floor((sn % 3600) / 60))}:${ikiHane(sn % 60)}`;
}

// 3725 -> "1 sa 2 dk"
function sureBicimi(sn) {
  if (sn < 60) return `${sn} sn`;
  const saat = Math.floor(sn / 3600);
  const dakika = Math.floor((sn % 3600) / 60);
  return saat ? `${saat} sa ${dakika} dk` : `${dakika} dk`;
}

// Date -> "2026-11-16" (yerel saatle)
function tarihMetni(d) {
  return `${d.getFullYear()}-${ikiHane(d.getMonth() + 1)}-${ikiHane(d.getDate())}`;
}

function rozet(hukum) {
  return el("span", `rozet ${hukum}`, HUKUM_ADI[hukum] || hukum);
}

// ---------- 1) Şu an ----------

let duraklatildi = false;

async function durumuYenile() {
  let d;
  try {
    d = await api("/api/durum");
  } catch {
    $("baglanti").textContent = "bağlantı yok (uygulama kapalı olabilir)";
    return;
  }
  $("baglanti").textContent = "";
  duraklatildi = d.duraklatildi;
  $("duraklat-dugme").textContent = duraklatildi ? "Takibe devam et" : "Takibi duraklat";

  $("sayac").textContent = saatBicimi(d.bugun_ders_sn);

  const r = $("durum-rozet");
  if (duraklatildi) {
    r.className = "rozet";
    r.textContent = "DURAKLATILDI";
  } else if (d.calisiyor) {
    r.className = "rozet ders";
    r.textContent = "● SAYAÇ ÇALIŞIYOR";
  } else if (d.hukum === "belirsiz") {
    r.className = "rozet belirsiz";
    r.textContent = "BELİRSİZ · sayılmıyor";
  } else {
    r.className = "rozet ders_degil";
    r.textContent = "SAYAÇ DURDU";
  }

  // Tolerans süresi dolmayı bekleyen değişiklik
  const b = d.bekleyen_gecis;
  $("bekleyen").textContent = b
    ? `${b.kalan_sn} sn daha böyle sürerse → ${HUKUM_ADI[b.hukum]}`
    : "";

  const anlik = d.anlik || {};
  $("algilanan-uygulama").textContent = anlik.uygulama || (duraklatildi ? "Takip duraklatıldı" : "—");
  $("algilanan-baslik").textContent = anlik.baslik || "";
  $("algilanan-aciklama").textContent = anlik.aciklama || "";

  const liste = $("sinyaller");
  liste.replaceChildren();
  for (const s of d.sinyaller || []) {
    const satir = el("li");
    satir.append(el("span", "", KAYNAK_ADI[s.kaynak] || s.kaynak), rozet(s.hukum), el("span", "soluk", s.aciklama));
    liste.append(satir);
  }
}

// ---------- 2) Bu hafta ----------

async function haftayiYenile() {
  const h = await api("/api/ozet/hafta");
  // Çubuk yükseklikleri haftanın en uzun gününe göre oranlanır (en az 1 saatlik ölçek).
  const enUzun = Math.max(3600, ...h.gunler.map((g) => g.ders_sn));
  const kutu = $("hafta");
  kutu.replaceChildren();
  for (const g of h.gunler) {
    const gun = el("div", g.bugun ? "gun bugun" : "gun");
    const cubuk = el("div", "cubuk");
    cubuk.style.height = `${(g.ders_sn / enUzun) * 100}%`;
    cubuk.title = `${g.tarih}: ${sureBicimi(g.ders_sn)}`;
    gun.append(el("div", "deger", g.ders_sn ? sureBicimi(g.ders_sn) : "–"), cubuk, el("div", "ad", g.gun_adi));
    kutu.append(gun);
  }
  $("hafta-toplam").textContent = `Toplam: ${sureBicimi(h.toplam_sn)}`;
}

// ---------- 3) Oturumlar ve düzeltme ----------

// Kullanıcı bir kutuya yazı yazarken liste yenilenip yazdığını silmesin.
function kullaniciYaziyor() {
  const a = document.activeElement;
  return a && a.tagName === "INPUT" && a.type === "text";
}

async function oturumlariYenile(zorla) {
  if (!zorla && kullaniciYaziyor()) return;
  const tarih = $("tarih").value;
  let oturumlar = await api(`/api/oturumlar?tarih=${tarih}`);
  if ($("filtre").value === "belirsiz") {
    oturumlar = oturumlar.filter((o) => o.etkin_hukum === "belirsiz");
  }

  const kutu = $("oturumlar");
  kutu.replaceChildren();
  if (!oturumlar.length) {
    kutu.append(el("div", "bos", $("filtre").value === "belirsiz"
      ? "Karar bekleyen oturum yok."
      : "Bu gün için kayıt yok."));
    return;
  }
  for (const o of oturumlar) kutu.append(oturumSatiri(o));
}

function oturumSatiri(o) {
  const satir = el("div", "oturum");

  // Sol sütun: saat aralığı ve süre
  const zaman = el("div", "zaman");
  const saat = (iso) => iso.slice(11, 16);
  zaman.append(
    el("div", "", `${saat(o.baslangic)} – ${o.suruyor ? "şimdi" : saat(o.bitis)}`),
    el("div", "soluk", sureBicimi(o.sure_sn)),
  );

  // Sağ sütun: ne olduğu
  const bilgi = el("div");
  const ust = el("div", "ust-satir");
  ust.append(rozet(o.etkin_hukum), el("span", "ad", o.uygulama || KAYNAK_ADI[o.kaynak] || ""));
  if (o.duzeltme) ust.append(el("span", "soluk", "(sen düzelttin)"));
  bilgi.append(ust, el("div", "baslik-metin", o.baslik || ""), el("div", "soluk", o.aciklama || ""));

  // Düzeltme araçları
  const islemler = el("div", "islemler");
  const dersti = el("button", "dugme ders" + (o.duzeltme === "ders" ? " secili" : ""), "Dersti");
  const degildi = el("button", "dugme degil" + (o.duzeltme === "ders_degil" ? " secili" : ""), "Ders değildi");
  islemler.append(dersti, degildi);

  // Kural öğrenme sadece uygulama ve tarayıcı oturumlarında anlamlı (boşta kalma için değil).
  let ogrenKutusu = null;
  let kelimeKutusu = null;
  if (o.kaynak === "pencere" || o.kaynak === "baslik") {
    const etiket = el("label");
    ogrenKutusu = el("input");
    ogrenKutusu.type = "checkbox";
    // Programın zaten bir fikri varsa (belirsiz değilse) kalıcı kuralı varsayılan yapma:
    // tek seferlik bir istisna olabilir.
    ogrenKutusu.checked = o.hukum === "belirsiz";
    etiket.append(ogrenKutusu, document.createTextNode("bundan sonra da böyle say"));
    islemler.append(etiket);
  }
  if (o.kaynak === "baslik") {
    kelimeKutusu = el("input");
    kelimeKutusu.type = "text";
    kelimeKutusu.maxLength = 80;
    kelimeKutusu.placeholder = "anahtar kelime ekle (isteğe bağlı)";
    kelimeKutusu.title = "Örn. kanal ya da ders adı. Bu kelime geçen bütün başlıklar aynı şekilde sayılır.";
    islemler.append(kelimeKutusu);
  }

  const gonder = async (hukum) => {
    await apiGonder(`/api/oturumlar/${o.id}/duzelt`, "POST", {
      hukum,
      ogren: ogrenKutusu ? ogrenKutusu.checked : false,
      kelime: kelimeKutusu ? kelimeKutusu.value : null,
    });
    await hepsiniYenile(true);
  };
  dersti.addEventListener("click", () => gonder("ders"));
  degildi.addEventListener("click", () => gonder("ders_degil"));

  satir.append(zaman, bilgi, islemler);
  return satir;
}

// ---------- 4) Öğrenilen kurallar ----------

async function kurallariYenile() {
  const kurallar = await api("/api/kurallar");
  const kutu = $("kurallar");
  kutu.replaceChildren();
  if (!kurallar.length) {
    kutu.append(el("div", "bos", "Henüz kural yok. Bir oturumu düzelttiğinde burada görünür."));
    return;
  }
  for (const k of kurallar) {
    const satir = el("div", "kural");
    const sil = el("button", "dugme kucuk", "Sil");
    sil.addEventListener("click", async () => {
      await apiGonder(`/api/kurallar/${k.id}`, "DELETE");
      await kurallariYenile();
    });
    satir.append(el("span", "soluk", KURAL_TURU[k.tur] || k.tur), el("span", "desen", k.desen), rozet(k.hukum), sil);
    kutu.append(satir);
  }
}

// ---------- Başlangıç ----------

async function hepsiniYenile(zorla) {
  try {
    await Promise.all([durumuYenile(), haftayiYenile(), oturumlariYenile(zorla), kurallariYenile()]);
  } catch (hata) {
    console.error(hata);
  }
}

function gunKaydir(fark) {
  const d = new Date($("tarih").value + "T12:00:00");
  d.setDate(d.getDate() + fark);
  $("tarih").value = tarihMetni(d);
  oturumlariYenile(true);
}

$("tarih").value = tarihMetni(new Date());
$("tarih").addEventListener("change", () => oturumlariYenile(true));
$("filtre").addEventListener("change", () => oturumlariYenile(true));
$("onceki-gun").addEventListener("click", () => gunKaydir(-1));
$("sonraki-gun").addEventListener("click", () => gunKaydir(1));
$("duraklat-dugme").addEventListener("click", async () => {
  await apiGonder("/api/duraklat", "POST", { duraklat: !duraklatildi });
  await durumuYenile();
});

hepsiniYenile(true);
setInterval(durumuYenile, 1000);                 // Sayaç her saniye
setInterval(() => hepsiniYenile(false), 15000);  // Listeler 15 saniyede bir
