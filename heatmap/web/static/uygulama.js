// Arayüz mantığı: API'den JSON çeker ve sayfaya yazar. Kütüphane yok, düz JavaScript.
//
// ÖNEMLİ GÜVENLİK NOTU: Pencere/sekme başlıkları dışarıdan gelen metinlerdir
// (bir web sitesi başlığına istediğini yazabilir). Bu yüzden sayfaya metin
// koyarken HER ZAMAN textContent kullanıyoruz, asla innerHTML değil.

const HUKUM_ADI = {
  ders: "ÇALIŞMA",
  ders_degil: "ÇALIŞMA DEĞİL",
  belirsiz: "BELİRSİZ",
  fikrim_yok: "fikri yok",
  devam: "yok sayılıyor",
};
const KAYNAK_ADI = { pencere: "Pencere", tarayici: "Tarayıcı", baslik: "Başlık", bosta: "Boşta", kamera: "Kamera", motor: "Motor" };
const KURAL_TURU = { surec: "Uygulama", baslik: "Tam başlık", kelime: "Kelime", alan: "Site" };
const HALKA_CEVRE = 2 * Math.PI * 64;  // SVG r=64 çember çevresi (~402.12)
const SVG_NS = "http://www.w3.org/2000/svg";

const $ = (id) => document.getElementById(id);

// ---------- Tema (Kâğıt & Mürekkep <-> Gece Mürekkebi) ----------
function temaUygula(geceMi) {
  document.body.classList.toggle("gece", geceMi);
  $("tema-dugme").textContent = geceMi ? "☀" : "☾";
  try {
    localStorage.setItem("heatmap_tema", geceMi ? "gece" : "kagit");
  } catch { /* özel pencerede localStorage kapalı olabilir */ }
}
try {
  temaUygula(localStorage.getItem("heatmap_tema") === "gece");
} catch {
  temaUygula(false);
}
$("tema-dugme").addEventListener("click", () => temaUygula(!document.body.classList.contains("gece")));

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
    // X-Heatmap: sunucu, veri değiştiren isteklerde bu başlığı arar (başka sitelerden
    // gelen sahte istekleri ayırt etmek için; bkz. api.py).
    headers: { "Content-Type": "application/json", "X-Heatmap": "1" },
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

// ---------- Sol menü sekme yönetimi ----------

let aktifSayfa = "ozet";
let kartIlkAcildi = false;

function sayfaAc(ad) {
  aktifSayfa = ad;
  for (const s of document.querySelectorAll(".sayfa")) {
    s.classList.toggle("aktif", s.id === `sayfa-${ad}`);
  }
  for (const m of document.querySelectorAll(".menu-oge")) {
    m.classList.toggle("aktif", m.dataset.sayfa === ad);
  }
  if (ad === "bekleyenler") {
    bekleyenleriYenile().catch(() => {});
  } else if (ad === "ayarlar" && !Object.keys(ayarOkuyucular).length) {
    ayarlariYukle().catch(() => {});
  } else if (ad === "kart" && !kartIlkAcildi) {
    kartIlkAcildi = true;
    kartiOlustur();
  } else if (ad === "oturumlar") {
    oturumlariYenile(true).catch(() => {});
  }
}

for (const dugme of document.querySelectorAll(".menu-oge")) {
  dugme.addEventListener("click", () => sayfaAc(dugme.dataset.sayfa));
}
$("kpi-bekleyen-kart").addEventListener("click", () => sayfaAc("bekleyenler"));

// Isı haritası, haftalık grafik ya da zincirden bir güne tıklayınca Oturumlar sekmesini o günle açar.
function gunuIncele(tarih) {
  $("tarih").value = tarih;
  sayfaAc("oturumlar");
}

// ---------- 1) Şu an ve hedef halkası ----------

let duraklatildi = false;
let sonBugunSn = 0;
let gunlukHedefSn = 0;

function hedefHalkasiniGuncelle() {
  const dolgu = $("halka-dolgu");
  const kutu = $("hedef-halka-kutu");
  const hap = $("motivasyon-hap");
  if (!gunlukHedefSn) {
    dolgu.style.strokeDashoffset = String(HALKA_CEVRE);
    $("halka-yuzde").textContent = "—";
    $("halka-hedef").textContent = "hedef kapalı";
    $("hedef-mesaj").textContent = "";
    hap.hidden = true;
    return;
  }
  const oran = sonBugunSn / gunlukHedefSn;
  const yuzde = Math.round(oran * 100);
  const sinirli = Math.min(1, Math.max(0, oran));
  dolgu.style.strokeDashoffset = String(HALKA_CEVRE * (1 - sinirli));
  kutu.classList.toggle("tamam", oran >= 1);
  $("halka-yuzde").textContent = `%${yuzde}`;
  $("halka-hedef").textContent = `hedef ${sureBicimi(gunlukHedefSn)}`;

  if (sonBugunSn === 0) {
    $("hedef-mesaj").textContent = "Başlamaya hazırsın — çalışma uygulamanı açınca sayaç otomatik başlar.";
    hap.hidden = true;
  } else if (oran < 0.5) {
    const kalan = Math.max(0, gunlukHedefSn - sonBugunSn);
    $("hedef-mesaj").textContent = `İyi başlangıç · Günlük hedefe ${sureBicimi(kalan)} kaldı.`;
    hap.hidden = true;
  } else if (oran < 1) {
    const kalan = Math.max(0, gunlukHedefSn - sonBugunSn);
    $("hedef-mesaj").textContent = `Harika gidiyorsun! Günlük hedefe sadece ${sureBicimi(kalan)} kaldı.`;
    hap.textContent = `Hedefe %${yuzde} yaklaştın`;
    hap.hidden = false;
  } else {
    const ekstra = sonBugunSn - gunlukHedefSn;
    $("hedef-mesaj").textContent = ekstra >= 60
      ? `Günlük hedef tamamlandı! (+${sureBicimi(ekstra)} ekstra)`
      : "Günlük hedef tamamlandı!";
    hap.textContent = "Günlük hedef tamamlandı";
    hap.hidden = false;
  }
}

async function durumuYenile() {
  let d;
  try {
    d = await api("/api/durum");
  } catch {
    $("baglanti").textContent = "Bağlantı yok (uygulama kapalı olabilir)";
    $("mini-etiket").textContent = "Bağlantı yok";
    $("mini-nokta").className = "canli-nokta";
    return;
  }
  $("baglanti").textContent = "";
  duraklatildi = d.duraklatildi;
  $("duraklat-dugme").textContent = duraklatildi ? "Takibe devam et" : "Takibi duraklat";

  sonBugunSn = d.bugun_ders_sn;
  const saat = saatBicimi(d.bugun_ders_sn);
  $("sayac").textContent = saat;
  $("mini-sayac").textContent = saat;
  hedefHalkasiniGuncelle();

  const r = $("durum-rozet");
  const nokta = $("mini-nokta");
  if (duraklatildi) {
    r.className = "rozet";
    r.textContent = "DURAKLATILDI";
    nokta.className = "canli-nokta";
    $("mini-etiket").textContent = "Takip duraklatıldı";
  } else if (d.calisiyor) {
    r.className = "rozet ders";
    r.textContent = "● SAYAÇ ÇALIŞIYOR";
    nokta.className = "canli-nokta ders";
    $("mini-etiket").textContent = (d.anlik && d.anlik.uygulama) || "Çalışma sayılıyor";
  } else if (d.hukum === "belirsiz") {
    r.className = "rozet belirsiz";
    r.textContent = "BELİRSİZ · sayılmıyor";
    nokta.className = "canli-nokta belirsiz";
    $("mini-etiket").textContent = "Belirsiz · sayılmıyor";
  } else {
    r.className = "rozet ders_degil";
    r.textContent = "SAYAÇ DURDU";
    nokta.className = "canli-nokta ders_degil";
    $("mini-etiket").textContent = "Sayaç durdu";
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

// ---------- 2) Bu hafta ve seri ----------

async function haftayiYenile() {
  const [h, s] = await Promise.all([api("/api/ozet/hafta"), api("/api/seri")]);
  gunlukHedefSn = s.hedef_sn || 0;
  hedefHalkasiniGuncelle();

  // Çubuk yükseklikleri haftanın en uzun gününe veya günlük hedefe göre oranlanır (en az 1 saat).
  const enUzun = Math.max(3600, gunlukHedefSn, ...h.gunler.map((g) => g.ders_sn));
  const kutu = $("hafta");
  kutu.replaceChildren();
  for (const g of h.gunler) {
    const siniflar = ["gun"];
    if (g.bugun) siniflar.push("bugun");
    if (gunlukHedefSn && g.ders_sn >= gunlukHedefSn) siniflar.push("hedef-tamam");
    const gun = el("div", siniflar.join(" "));
    const cubuk = el("div", "cubuk");
    // Üstte ve altta etiket boşluğu olduğu için çubuk yüksekliğini %78 içine ölçekle
    cubuk.style.height = `${Math.max(2, (g.ders_sn / enUzun) * 78)}%`;
    cubuk.title = `${g.tarih}: ${sureBicimi(g.ders_sn)} (oturumları incelemek için tıkla)`;
    gun.addEventListener("click", () => gunuIncele(g.tarih));
    gun.append(el("div", "deger", g.ders_sn ? sureBicimi(g.ders_sn) : "–"), cubuk, el("div", "ad", g.gun_adi));
    kutu.append(gun);
  }

  // Haftalık grafikte yatay kesikli hedef çizgisi
  const hedefCizgi = $("hafta-hedef-cizgi");
  if (gunlukHedefSn > 0) {
    const oran = (gunlukHedefSn / enUzun) * 78;
    // Alttaki gün adı (~24px) üstüne konumlandır
    hedefCizgi.style.bottom = `calc(24px + ${oran}%)`;
    $("hafta-hedef-etiket").textContent = `Hedef ${sureBicimi(gunlukHedefSn)}`;
    hedefCizgi.hidden = false;
  } else {
    hedefCizgi.hidden = true;
  }

  $("hafta-toplam").textContent = `Toplam: ${sureBicimi(h.toplam_sn)}`;
  $("kpi-hafta").textContent = sureBicimi(h.toplam_sn);
  const gecenGun = h.gunler.findIndex((g) => g.bugun) + 1 || 7;
  $("kpi-hafta-ort").textContent = `Günlük ort: ${sureBicimi(Math.round(h.toplam_sn / gecenGun))}`;

  // Günlerin altında sağlık verisi (yalnızca hafta içinde en az bir kayıt varsa)
  const saglikVar = h.gunler.some((g) => g.adim != null || g.egzersiz_dk != null || g.uyku_dk != null);
  $("hafta-saglik").replaceChildren(...(saglikVar ? h.gunler.map(saglikHucresi) : []));

  $("seri").textContent = s.hedef_sn ? `Hedef: ${sureBicimi(s.hedef_sn)}` : "";
  $("kpi-seri").textContent = `${s.seri_gun} gün`;
}

// ---------- Kamera (yalnızca modül etkinse) ----------

async function kamerayiYenile() {
  const k = await api("/api/kamera");
  $("kamera-ayar").hidden = !k.etkin;
  if (!k.etkin) return;
  $("kamera-acik").checked = k.acik;
  $("kamera-kalibre").disabled = !k.acik;
  const anlik = k.anlik_pitch != null ? `şu an ${k.anlik_pitch}°` : "ölçüm yok";
  $("kamera-aci").textContent = k.acik
    ? `Kafa açısı: ${anlik} · ekrana bakma ${k.ekran_pitch}° · aşağı sayılan < ${k.asagi_esigi}°`
    : "";
}

async function kameraAcKapat(olay) {
  const d = await apiGonder("/api/kamera", "POST", { acik: olay.target.checked });
  olay.target.checked = d.acik;
  $("kamera-mesaj").textContent = d.acik ? "" : "Kamera kapalı; ışığı birkaç saniye içinde söner.";
  await kamerayiYenile();
}

async function kameraKalibre() {
  const dugme = $("kamera-kalibre");
  dugme.disabled = true;
  $("kamera-mesaj").textContent = "6 saniye boyunca ekrana normal bak…";
  try {
    const d = await apiGonder("/api/kamera/kalibre", "POST");
    $("kamera-mesaj").textContent = `Kaydedildi: ekrana bakma açısı ${d.ekran_pitch}°`;
  } catch {
    $("kamera-mesaj").textContent = "Ölçülemedi: kamera açık olmalı ve yüzün görünmeli.";
  } finally {
    dugme.disabled = false;
    await kamerayiYenile();
  }
}

// ---------- Sağlık verisi ----------

// 8200 -> "8,2 bin", 950 -> "950"
function adimBicimi(adim) {
  return adim >= 1000 ? `${(adim / 1000).toFixed(1).replace(".", ",")} bin` : String(adim);
}

function saglikHucresi(g) {
  const hucre = el("div");
  const satirlar = [];
  if (g.adim != null) satirlar.push(`${adimBicimi(g.adim)} adım`);
  if (g.egzersiz_dk) satirlar.push(`${g.egzersiz_dk} dk spor`);
  if (g.uyku_dk) satirlar.push(`${(g.uyku_dk / 60).toFixed(1).replace(".", ",")} sa uyku`);
  for (const s of satirlar) hucre.append(el("div", "", s));
  return hucre;
}

// Seçili günün kayıtlı değerlerini forma doldurur (yoksa boşaltır).
async function saglikFormunuDoldur() {
  const tarih = $("saglik-tarih").value;
  const kayitlar = await api(`/api/saglik?baslangic=${tarih}&bitis=${tarih}`);
  const k = kayitlar[0] || {};
  $("saglik-adim").value = k.adim ?? "";
  $("saglik-egzersiz").value = k.egzersiz_dk ?? "";
  $("saglik-uyku").value = k.uyku_dk != null ? k.uyku_dk / 60 : "";
  $("saglik-mesaj").textContent = kayitlar.length ? "Bu gün için kayıt var; değiştirip kaydedebilirsin." : "";
}

function sayiVeyaNull(id, carpan = 1) {
  const deger = $(id).value.trim();
  return deger === "" ? null : Math.round(Number(deger) * carpan);
}

async function saglikKaydet(olay) {
  olay.preventDefault();
  try {
    await apiGonder("/api/saglik", "POST", {
      tarih: $("saglik-tarih").value,
      adim: sayiVeyaNull("saglik-adim"),
      egzersiz_dk: sayiVeyaNull("saglik-egzersiz"),
      uyku_dk: sayiVeyaNull("saglik-uyku", 60),  // Saat olarak girilir, dakika olarak saklanır
    });
    $("saglik-mesaj").textContent = "Kaydedildi.";
    await haftayiYenile();
  } catch {
    $("saglik-mesaj").textContent = "Kaydedilemedi: değerleri kontrol et (en az bir alan dolu olmalı).";
  }
}

async function saglikSil() {
  try {
    await apiGonder(`/api/saglik/${$("saglik-tarih").value}`, "DELETE");
    await saglikFormunuDoldur();
    $("saglik-mesaj").textContent = "Silindi.";
    await haftayiYenile();
  } catch {
    $("saglik-mesaj").textContent = "Bu gün için silinecek kayıt yok.";
  }
}

// ---------- Öğrenen tahmin ve karar bekleyenler ----------

function oneriRozeti(oneri) {
  const rozetEl = el("span", `oneri ${oneri.hukum}`,
    `Tahmin: ${oneri.hukum === "ders" ? "çalışma" : "çalışma değil"} %${Math.round(oneri.olasilik * 100)}`);
  rozetEl.title = oneri.kelimeler && oneri.kelimeler.length
    ? `Benzer başlıklardan öğrenildi; en etkili kelimeler: ${oneri.kelimeler.join(", ")}`
    : "Benzer başlıklardan öğrenildi";
  return rozetEl;
}

async function tahminBilgisiniYenile() {
  const b = await api("/api/tahmin");
  let yazi = "";
  if (b.etkin === false) yazi = "Tahmin önerileri ayarlardan kapalı.";
  else if (!b.hazir) yazi = `Tahmin modeli için daha fazla karar gerekiyor (${b.ornek_sayisi}/${b.en_az_ornek} farklı başlık).`;
  else {
    yazi = `Tahmin modeli ${b.ornek_sayisi} farklı başlıktan öğrendi`;
    if (b.dogruluk != null) yazi += `; çapraz doğrulamada tahminlerin %${Math.round(b.dogruluk * 100)}'i doğru`;
    yazi += ". Sen karar verdikçe gelişir.";
  }
  $("tahmin-bilgisi").textContent = yazi;
}

function bekleyenSatiri(k) {
  const satir = el("div", "bekleyen-satir");
  const sol = el("div");
  const ust = el("div", "ust-satir");
  ust.append(rozet("belirsiz"), el("span", "ad", k.ad));
  if (k.alan_adi) ust.append(el("span", "soluk", k.alan_adi));
  if (k.oneri) ust.append(oneriRozeti(k.oneri));
  sol.append(ust);
  if (k.tur === "baslik") sol.append(el("div", "deger", k.deger));
  sol.append(el("div", "soluk",
    `${k.oturum_sayisi} oturum · toplam ${sureBicimi(k.sure_sn)} · son: ${k.son_gorulme.slice(0, 16).replace("T", " ")}`));

  const islemler = el("div", "islemler");
  const dersti = el("button", "dugme ders", "Çalışmaydı");
  const degildi = el("button", "dugme degil", "Çalışma değildi");
  if (k.oneri) (k.oneri.hukum === "ders" ? dersti : degildi).classList.add("onerilen");
  const etiket = el("label");
  const ogren = el("input");
  ogren.type = "checkbox";
  ogren.checked = true;
  etiket.append(ogren, document.createTextNode("bundan sonra da"));
  islemler.append(dersti, degildi, etiket);

  const karar = async (hukum) => {
    dersti.disabled = degildi.disabled = true;
    await apiGonder("/api/karar-bekleyenler", "POST", { tur: k.tur, deger: k.deger, hukum, ogren: ogren.checked });
    satir.remove();
    await Promise.all([bekleyenleriYenile(), hepsiniYenile(true)]);
  };
  dersti.addEventListener("click", () => karar("ders"));
  degildi.addEventListener("click", () => karar("ders_degil"));
  satir.append(sol, islemler);
  return satir;
}

async function bekleyenleriYenile() {
  const liste = await api("/api/karar-bekleyenler");
  const sayi = liste.length;
  $("bekleyen-sayisi").textContent = sayi ? `(${sayi})` : "";
  $("kpi-bekleyen").textContent = String(sayi);
  const menuRozet = $("menu-bekleyen-rozet");
  menuRozet.textContent = String(sayi);
  menuRozet.hidden = sayi === 0;

  if (aktifSayfa === "bekleyenler") {
    $("bekleyenler").replaceChildren(...(sayi ? liste.map(bekleyenSatiri)
      : [el("div", "bos", "Harika! Karar bekleyen başlık ya da uygulama yok.")]));
    tahminBilgisiniYenile().catch(() => {});
  }
}

// ---------- Isı haritası (son 12 ay) ----------

const AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

async function isiHaritasiniYenile() {
  const v = await api("/api/isi-haritasi");
  const bugun = tarihMetni(new Date());

  const izgara = $("isi-izgara");
  izgara.replaceChildren();
  for (const g of v.gunler) {
    const kare = el("i", `isi-kare s${g.seviye}`);
    if (g.gelecek) kare.classList.add("gelecek");
    if (g.tarih === bugun) kare.classList.add("bugun");
    if (!g.gelecek) {
      const [yil, ay, gun] = g.tarih.split("-").map(Number);
      kare.title = `${gun} ${AY_KISA[ay - 1]} ${yil}: ${g.ders_sn ? sureBicimi(g.ders_sn) : "kayıt yok"} (incelemek için tıkla)`;
      kare.addEventListener("click", () => gunuIncele(g.tarih));
    }
    izgara.append(kare);
  }

  const haftaSayisi = v.gunler.length / 7;
  const etiketler = [];
  let oncekiAy = -1;
  for (let hafta = 0; hafta < haftaSayisi; hafta++) {
    const ay = Number(v.gunler[hafta * 7].tarih.slice(5, 7)) - 1;
    etiketler.push(ay !== oncekiAy && hafta < haftaSayisi - 2 ? AY_KISA[ay] : "");
    oncekiAy = ay;
  }
  const ikinci = etiketler.findIndex((e, i) => i > 0 && e);
  if (ikinci > 0 && ikinci < 3) etiketler[0] = "";
  $("isi-aylar").replaceChildren(...etiketler.map((e) => el("span", "", e)));

  const kaydirma = document.querySelector(".isi-kaydirma");
  kaydirma.scrollLeft = kaydirma.scrollWidth;

  $("isi-ozet").textContent =
    `${v.aktif_gun} aktif gün · toplam ${sureBicimi(v.toplam_sn)}` +
    (v.aktif_gun ? ` · aktif gün ortalaması ${sureBicimi(v.aktif_gun_ortalamasi_sn)}` : "");
  $("isi-seri").textContent = v.hedef_sn
    ? `Hedef tutan gün: ${v.hedef_gunu} · Şu anki seri: ${v.simdiki_seri} gün · En uzun seri: ${v.en_uzun_seri} gün`
    : "";

  // KPI kartlarını ısı haritası özetinden güncelle
  $("kpi-en-uzun-seri").textContent = `En uzun: ${v.en_uzun_seri} gün`;
  $("kpi-hedef-gunu").textContent = String(v.hedef_gunu);
  $("kpi-aktif-gun").textContent = `${v.aktif_gun} aktif gün (son 12 ay)`;
}

// ---------- Paylaşım kartı ----------

function kartAdresi() {
  const tur = $("kart-tur").value;
  const tarih = $("kart-tarih").value || tarihMetni(new Date());
  return `/api/kart?tur=${tur}&tarih=${tarih}&liste=${$("kart-liste").value}`;
}

function kartiOlustur() {
  $("kart-resim").src = `${kartAdresi()}&t=${Date.now()}`;
  $("kart-indir").href = `${kartAdresi()}&indir=true`;
  $("kart-mesaj").textContent = "";
}

async function kartiKopyala() {
  try {
    const yanit = await fetch(kartAdresi());
    const resim = await yanit.blob();
    await navigator.clipboard.write([new ClipboardItem({ "image/png": resim })]);
    $("kart-mesaj").textContent = "Panoya kopyalandı.";
  } catch {
    $("kart-mesaj").textContent = "Kopyalanamadı; tarayıcın izin vermiyor olabilir. PNG indir'i kullan.";
  }
}

// ---------- Süre nereden geldi? (renk kodlu uygulama dökümü) ----------

async function dokumuYenile() {
  const bugun = new Date();
  let ilk = bugun;
  if ($("dokum-aralik").value === "hafta") {
    ilk = new Date(bugun);
    ilk.setDate(bugun.getDate() - ((bugun.getDay() + 6) % 7));
  }
  const gruplama = $("dokum-gruplama").value;
  const d = await api(`/api/dokum?baslangic=${tarihMetni(ilk)}&bitis=${tarihMetni(bugun)}&gruplama=${gruplama}`);

  const kutu = $("dokum");
  kutu.replaceChildren();
  if (!d.uygulamalar.length) {
    kutu.append(el("div", "bos", "Bu aralıkta sayılan çalışma süresi henüz yok."));
    return;
  }
  const enUzun = d.uygulamalar[0].sure_sn || 1;
  d.uygulamalar.forEach((u, i) => {
    const satir = el("div", "dokum-satir");
    const ad = el("span", "ad", u.ad);
    ad.title = u.tur === "kategori" ? `${u.ad}: ${u.icerik.join(", ")}`
      : u.tur === "site" ? `${u.ad} (web sitesi)` : u.ad;
    const ray = el("div", "ray");
    const dolgu = el("div", `dolgu renk-${i % 6}`);
    dolgu.style.width = `${(u.sure_sn / enUzun) * 100}%`;
    ray.append(dolgu);
    satir.append(ad, ray, el("span", "deger soluk", `${sureBicimi(u.sure_sn)} · %${Math.round(u.oran * 100)}`));
    kutu.append(satir);
  });
}

// ---------- 3) Oturumlar ve zaman çizelgesi ----------

function kullaniciYaziyor() {
  const a = document.activeElement;
  return a && a.tagName === "INPUT" && a.type === "text";
}

const HUKUM_YAZI = { ders: "Çalışma", ders_degil: "Çalışma değil", belirsiz: "Belirsiz" };

function dakikaSaat(dk) {
  const toplam = Math.round(dk);
  return `${ikiHane(Math.floor(toplam / 60) % 24)}:${ikiHane(toplam % 60)}`;
}

async function cizelgeyiYenile() {
  const d = await api(`/api/zaman-cizelgesi?tarih=${$("tarih").value}`);
  const serit = $("cizelge");
  const saatler = $("cizelge-saatler");
  let bas = 0, son = 1440;
  if (d.parcalar.length) {
    bas = Math.max(0, Math.floor(d.parcalar[0].bas_dk / 60) * 60);
    son = Math.min(1440, Math.ceil(Math.max(...d.parcalar.map((p) => p.bit_dk)) / 60) * 60);
    if (son - bas < 360) {
      const eksik = 360 - (son - bas);
      bas = Math.max(0, bas - Math.floor(eksik / 120) * 60);
      son = Math.min(1440, bas + 360);
    }
  }
  const genislik = son - bas;
  const konum = (dk) => `${((dk - bas) / genislik) * 100}%`;

  serit.replaceChildren(...d.parcalar.map((p) => {
    const parca = el("div", `parca ${p.tur === "bosta" ? "bosta" : p.hukum}`);
    parca.style.left = konum(p.bas_dk);
    parca.style.width = `${((p.bit_dk - p.bas_dk) / genislik) * 100}%`;
    const yazi = `${dakikaSaat(p.bas_dk)}–${dakikaSaat(p.bit_dk)} · ${p.ad} · ` +
      `${p.tur === "bosta" ? "Başında değil" : HUKUM_YAZI[p.hukum] || p.hukum} (${sureBicimi(p.sure_sn)})` +
      (p.duzeltildi ? " · sen düzelttin" : "");
    parca.title = yazi;
    const sec = () => {
      for (const diger of serit.querySelectorAll(".parca.secili")) diger.classList.remove("secili");
      parca.classList.add("secili");
      $("cizelge-secili").textContent = yazi;
    };
    parca.addEventListener("mouseenter", sec);
    parca.addEventListener("click", sec);
    return parca;
  }));

  const adim = genislik <= 480 ? 60 : genislik <= 900 ? 120 : 180;
  const etiketler = [];
  for (let dk = bas; dk <= son; dk += adim) {
    const etiket = el("span", "", dk === 1440 ? "24:00" : dakikaSaat(dk));
    etiket.style.left = konum(dk);
    if (dk === bas) etiket.style.transform = "none";
    if (dk === son) etiket.style.transform = "translateX(-100%)";
    etiketler.push(etiket);
  }
  saatler.replaceChildren(...etiketler);
  $("cizelge-secili").textContent = d.parcalar.length
    ? `Çalışma ${sureBicimi(d.toplam_sn.ders || 0)} · belirsiz ${sureBicimi(d.toplam_sn.belirsiz || 0)} · ` +
      "ayrıntı için bir parçanın üzerine gel."
    : "Bu gün için kayıt yok.";
}

async function oturumlariYenile(zorla) {
  if (!zorla && kullaniciYaziyor()) return;
  const tarih = $("tarih").value;
  cizelgeyiYenile().catch(() => {});
  let oturumlar = await api(`/api/oturumlar?tarih=${tarih}`);
  if ($("filtre").value === "belirsiz") {
    oturumlar = oturumlar.filter((o) => o.etkin_hukum === "belirsiz");
  }
  const gizlenen = $("kisalari-gizle").checked
    ? oturumlar.filter((o) => o.sure_sn < 60 && !o.suruyor).length : 0;
  if (gizlenen) oturumlar = oturumlar.filter((o) => o.sure_sn >= 60 || o.suruyor);

  const kutu = $("oturumlar");
  kutu.replaceChildren();
  if (!oturumlar.length) {
    kutu.append(el("div", "bos", $("filtre").value === "belirsiz"
      ? "Bu gün için karar bekleyen oturum yok."
      : "Bu gün için kayıt yok."));
    if (gizlenen) kutu.append(el("div", "soluk", `${gizlenen} kısa oturum gizlendi.`));
    return;
  }
  for (const o of oturumlar) kutu.append(oturumSatiri(o));
  if (gizlenen) kutu.append(el("div", "soluk", `${gizlenen} kısa oturum gizlendi.`));
}

function oturumSatiri(o) {
  const satir = el("div", `oturum h-${o.etkin_hukum}`);

  const zaman = el("div", "zaman");
  const saat = (iso) => iso.slice(11, 16);
  zaman.append(
    el("div", "", `${saat(o.baslangic)} – ${o.suruyor ? "şimdi" : saat(o.bitis)}`),
    el("div", "soluk", sureBicimi(o.sure_sn)),
  );

  const bilgi = el("div");
  const ust = el("div", "ust-satir");
  ust.append(rozet(o.etkin_hukum), el("span", "ad", o.uygulama || KAYNAK_ADI[o.kaynak] || ""));
  if (o.alan_adi) ust.append(el("span", "soluk", o.alan_adi));
  if (o.duzeltme) {
    ust.append(el("span", "soluk", "(sen düzelttin)"));
    const geriAl = el("button", "dugme kucuk", "Geri al");
    geriAl.title = "Düzeltmeyi kaldırır; öğrenilen kurallar kalır (onları Karar Bekleyenler sekmesinden silebilirsin).";
    geriAl.addEventListener("click", async () => {
      await apiGonder(`/api/oturumlar/${o.id}/duzelt`, "DELETE");
      await hepsiniYenile(true);
    });
    ust.append(geriAl);
  }
  if (o.oneri) ust.append(oneriRozeti(o.oneri));
  bilgi.append(ust, el("div", "baslik-metin", o.baslik || ""), el("div", "soluk", o.aciklama || ""));

  const islemler = el("div", "islemler");
  const dersti = el("button", "dugme ders" + (o.duzeltme === "ders" ? " secili" : ""), "Çalışmaydı");
  const degildi = el("button", "dugme degil" + (o.duzeltme === "ders_degil" ? " secili" : ""), "Çalışma değildi");
  islemler.append(dersti, degildi);
  if (o.oneri) (o.oneri.hukum === "ders" ? dersti : degildi).classList.add("onerilen");

  let ogrenKutusu = null;
  let kelimeKutusu = null;
  let siteKutusu = null;
  if (o.kaynak === "pencere" || o.kaynak === "baslik") {
    const etiket = el("label");
    ogrenKutusu = el("input");
    ogrenKutusu.type = "checkbox";
    ogrenKutusu.checked = o.hukum === "belirsiz";
    etiket.append(ogrenKutusu, document.createTextNode("bundan sonra da böyle say"));
    islemler.append(etiket);
  }
  if (o.kaynak === "baslik" && o.alan_adi) {
    const etiket = el("label");
    siteKutusu = el("input");
    siteKutusu.type = "checkbox";
    etiket.append(siteKutusu, document.createTextNode(`${o.alan_adi} sitesini hep böyle say`));
    islemler.append(etiket);
  }
  if (o.kaynak === "baslik") {
    kelimeKutusu = el("input");
    kelimeKutusu.type = "text";
    kelimeKutusu.maxLength = 80;
    kelimeKutusu.placeholder = "anahtar kelime ekle (isteğe bağlı)";
    kelimeKutusu.title = "Örn. kanal ya da konu adı. Bu kelime geçen bütün başlıklar aynı şekilde sayılır.";
    islemler.append(kelimeKutusu);
  }

  const gonder = async (hukum) => {
    await apiGonder(`/api/oturumlar/${o.id}/duzelt`, "POST", {
      hukum,
      ogren: ogrenKutusu ? ogrenKutusu.checked : false,
      kelime: kelimeKutusu ? kelimeKutusu.value : null,
      site_ogren: siteKutusu ? siteKutusu.checked : false,
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

// ---------- 4b) Zinciri Kırma ----------

let sonTakilanTarih = "";

async function halkaTak(tarih, tur) {
  try {
    await apiGonder("/api/zincir/halka", "POST", { tarih, tur });
    sonTakilanTarih = tarih;
    await Promise.all([zinciriYenile(), haftayiYenile(), isiHaritasiniYenile()]);
  } catch (hata) {
    console.error(hata);
  }
}

function zincirTepsiJetoni(tarih, tur, yazi, sinif) {
  const jeton = el("button", `halka-jeton ${sinif || ""}`.trim());
  jeton.type = "button";
  jeton.draggable = true;
  jeton.append(el("span", "halka-jeton-daire"), el("span", "", yazi));
  jeton.title = "Zincirdeki yanıp sönen yuvaya sürükleyebilir ya da doğrudan tıklayabilirsin.";
  jeton.addEventListener("dragstart", (olay) => {
    olay.dataTransfer.setData("text/plain", JSON.stringify({ tarih, tur }));
    olay.dataTransfer.effectAllowed = "move";
  });
  jeton.addEventListener("click", () => halkaTak(tarih, tur));
  return jeton;
}

// Yatay, fiziksel olarak iç içe geçen metalik zincir halkası SVG'si (innerHTML kullanmadan).
function zincirHalkaSvg(doluMu) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 68 40");
  svg.setAttribute("class", "zincir-svg");
  svg.setAttribute("aria-hidden", "true");

  // Dış kalın mürekkep gölgesi (dolu halkaya fiziksel derinlik verir)
  if (doluMu) {
    const dis = document.createElementNS(SVG_NS, "rect");
    dis.setAttribute("x", "6");
    dis.setAttribute("y", "7");
    dis.setAttribute("width", "56");
    dis.setAttribute("height", "26");
    dis.setAttribute("rx", "13");
    dis.setAttribute("fill", "none");
    dis.setAttribute("stroke", "#18181b");
    dis.setAttribute("stroke-width", "10.5");
    svg.append(dis);
  }

  const yol = document.createElementNS(SVG_NS, "rect");
  yol.setAttribute("x", "6");
  yol.setAttribute("y", "7");
  yol.setAttribute("width", "56");
  yol.setAttribute("height", "26");
  yol.setAttribute("rx", "13");
  yol.setAttribute("class", "zincir-halka-yol");
  svg.append(yol);

  if (doluMu) {
    const ic = document.createElementNS(SVG_NS, "rect");
    ic.setAttribute("x", "8");
    ic.setAttribute("y", "9");
    ic.setAttribute("width", "52");
    ic.setAttribute("height", "22");
    ic.setAttribute("rx", "11");
    ic.setAttribute("class", "zincir-halka-ic");
    svg.append(ic);
  }
  return svg;
}

async function zinciriYenile() {
  const z = await api("/api/zincir");
  const kart = $("zincir-kart");
  kart.className = `kart zincir-kart kademe-${z.kilometre_tasi.kod}`;

  const kademe = $("zincir-kademe");
  kademe.className = `kademe-rozet ${z.kilometre_tasi.kod}`;
  kademe.textContent = `${z.kilometre_tasi.ad} · ${z.zincir_uzunlugu} halka`;

  $("zincir-kalkan-bilgi").textContent =
    `Kalkan: ${z.kalkan_hakki}/${z.en_fazla_kalkan} · sonraki kalkana ${z.sonraki_kalkana_kalan} tam gün`;
  $("zincir-otomatik").checked = Boolean(z.otomatik_tak);

  // KPI kartı güncel zinciri (kurtarma/kalkan dahil) göstersin
  $("kpi-seri").textContent = `${z.zincir_uzunlugu} gün`;
  $("kpi-en-uzun-seri").textContent = `En uzun: ${z.en_uzun_zincir} gün · hedef ${z.kilometre_tasi.sonraki}`;

  const serit = $("zincir-serit");
  serit.replaceChildren();
  const bugunTarih = z.halkalar.length ? z.halkalar[z.halkalar.length - 1].tarih : "";

  z.halkalar.forEach((h) => {
    const sutun = el("div", h.bugun ? "zincir-gun bugun" : "zincir-gun");
    const kutu = el("div", "zincir-svg-kutu");
    if (h.tur) kutu.classList.add(h.tur);
    if (h.tarih === sonTakilanTarih) kutu.classList.add("yeni-takildi");

    const dropHedefi = h.bekliyor || (h.kalkan_adayi ? "kalkan" : null);
    if (dropHedefi) {
      kutu.classList.add("hedef-yuva");
      if (dropHedefi === "kurtarma") kutu.classList.add("kurtarma-yuva");
      if (dropHedefi === "kalkan") kutu.classList.add("kalkan-yuva");
      kutu.addEventListener("dragover", (olay) => {
        olay.preventDefault();
        kutu.classList.add("surukleme-ustu");
      });
      kutu.addEventListener("dragleave", () => kutu.classList.remove("surukleme-ustu"));
      kutu.addEventListener("drop", (olay) => {
        olay.preventDefault();
        kutu.classList.remove("surukleme-ustu");
        try {
          const veri = JSON.parse(olay.dataTransfer.getData("text/plain"));
          if (veri.tarih === h.tarih) halkaTak(veri.tarih, veri.tur);
        } catch {
          halkaTak(h.tarih, dropHedefi);
        }
      });
    }

    const simge = h.tur === "tam" ? "✓"
      : h.tur === "kurtarma" ? "B"
      : h.tur === "kalkan" ? "K"
      : dropHedefi ? "+"
      : String(h.gun_no);
    kutu.append(zincirHalkaSvg(Boolean(h.tur)), el("span", "zincir-gun-simge", simge));

    const turAciklama = h.tur === "tam" ? "Tam halka (hedef tuttu)"
      : h.tur === "kurtarma" ? "Bronz kurtarma halkası"
      : h.tur === "kalkan" ? "Gümüş kalkan halkası"
      : dropHedefi === "tam" ? "Hedef tamam! Halkayı buraya sürükle veya tıkla"
      : dropHedefi === "kurtarma" ? "Bronz kurtarma halkası takılabilir"
      : dropHedefi === "kalkan" ? "Dünü kalkan halkasıyla kurtarabilirsin"
      : "Halka yok";
    sutun.title = `${h.tarih} (${h.gun_adi}): ${sureBicimi(h.ders_sn)} · ${turAciklama}`;
    sutun.addEventListener("click", () => {
      if (dropHedefi) halkaTak(h.tarih, dropHedefi);
      else gunuIncele(h.tarih);
    });

    sutun.append(kutu, el("span", "zincir-etiket", h.bugun ? "Bugün" : `${h.gun_no} ${h.gun_adi}`));
    serit.append(sutun);
  });

  // Sağ uç (bugün) görünsün
  const kaydirma = document.querySelector(".zincir-kaydirma");
  kaydirma.scrollLeft = kaydirma.scrollWidth;

  // Alt aksiyon tepsisi: sürüklenebilir/tıklanabilir halka jetonları veya rehber notu
  const tepsi = $("zincir-tepsi");
  tepsi.replaceChildren();
  let jetonVar = false;

  if (z.bekleyen_halka === "tam") {
    tepsi.append(zincirTepsiJetoni(bugunTarih, "tam", "Bugünün halkasını zincire tak (sürükle ya da tıkla)"));
    jetonVar = true;
  } else if (z.bekleyen_halka === "kurtarma") {
    tepsi.append(zincirTepsiJetoni(bugunTarih, "kurtarma", "Bronz kurtarma halkası tak (sürükle ya da tıkla)", "kurtarma"));
    jetonVar = true;
  }
  if (z.kalkan_kullanilabilir_tarih) {
    tepsi.append(zincirTepsiJetoni(z.kalkan_kullanilabilir_tarih, "kalkan", "Dünü Gümüş Kalkan ile kurtar", "kalkan"));
    jetonVar = true;
  }

  if (!jetonVar) {
    const mesaj = !z.hedef_sn
      ? "Zinciri Kırma için Ayarlar'dan günlük hedef belirleyebilirsin."
      : z.otomatik_tak
        ? "Otomatik tak açık: günlük hedefine ulaştığın an yeni halkan kendiliğinden zincire eklenir."
        : "Günlük hedefine ulaştığında parlak halkan burada açılacak; sürükleyip zincire takabilirsin.";
    tepsi.append(el("span", "soluk", mesaj));
  }
  sonTakilanTarih = "";
}

// ---------- 4c) En verimli saatlerin (24 saatlik dağılım) ----------

async function verimliSaatleriYenile() {
  const gun = Number($("saatler-aralik").value) || 30;
  const v = await api(`/api/verimli-saatler?gun=${gun}`);
  const kutu = $("verimli-saatler");
  kutu.replaceChildren();

  if (v.en_verimli_saat != null) {
    const s1 = ikiHane(v.en_verimli_saat);
    const s2 = ikiHane((v.en_verimli_saat + 1) % 24);
    $("saatler-ozet").textContent =
      `En verimli saatin: ${s1}:00–${s2}:00 · En güçlü dilim: ${v.en_verimli_dilim}`;
  } else {
    $("saatler-ozet").textContent = "Bu aralıkta henüz çalışma verisi yok.";
  }

  for (const s of v.saatler) {
    const zirve = s.oran >= 0.8 && s.ders_sn > 0;
    const sutun = el("div", zirve ? "saat-sutun zirve" : "saat-sutun");
    const cubuk = el("div", "saat-cubuk");
    cubuk.style.height = `${Math.max(3, Math.round(s.oran * 82))}%`;
    const saatBas = `${ikiHane(s.saat)}:00`;
    const saatSon = `${ikiHane((s.saat + 1) % 24)}:00`;
    sutun.title = `${saatBas}–${saatSon}: ${s.ders_sn ? sureBicimi(s.ders_sn) : "kayıt yok"}`;
    const etiket = el("span", "saat-etiket", s.saat % 2 === 0 ? ikiHane(s.saat) : "");
    sutun.append(cubuk, etiket);
    kutu.append(sutun);
  }
}

// ---------- Başlangıç ve olay bağlamaları ----------

async function hepsiniYenile(zorla) {
  try {
    await Promise.all([
      durumuYenile(),
      haftayiYenile(),
      zinciriYenile(),
      verimliSaatleriYenile(),
      isiHaritasiniYenile(),
      dokumuYenile(),
      oturumlariYenile(zorla),
      bekleyenleriYenile(),
      kurallariYenile(),
    ]);
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
$("kisalari-gizle").addEventListener("change", () => oturumlariYenile(true));
$("onceki-gun").addEventListener("click", () => gunKaydir(-1));
$("sonraki-gun").addEventListener("click", () => gunKaydir(1));
$("bugun-dugme").addEventListener("click", () => {
  $("tarih").value = tarihMetni(new Date());
  oturumlariYenile(true);
});

$("dokum-aralik").addEventListener("change", dokumuYenile);
$("dokum-gruplama").addEventListener("change", dokumuYenile);
$("saatler-aralik").addEventListener("change", verimliSaatleriYenile);
$("zincir-otomatik").addEventListener("change", async (olay) => {
  const istenen = olay.target.checked;
  try {
    await apiGonder("/api/ayarlar", "POST", { degisiklikler: { "zincir.otomatik_tak": istenen } });
    await zinciriYenile();
  } catch {
    olay.target.checked = !istenen;
  }
});

$("kart-olustur").addEventListener("click", kartiOlustur);
$("kart-kopyala").addEventListener("click", kartiKopyala);
$("kart-tur").addEventListener("change", kartiOlustur);
$("kart-tarih").addEventListener("change", kartiOlustur);
$("kart-liste").addEventListener("change", kartiOlustur);
$("kart-tarih").value = $("kart-tarih").max = tarihMetni(new Date());

$("kamera-acik").addEventListener("change", kameraAcKapat);
$("kamera-kalibre").addEventListener("click", kameraKalibre);
kamerayiYenile().catch(() => {});
setInterval(() => kamerayiYenile().catch(() => {}), 3000);

$("saglik-tarih").value = $("saglik-tarih").max = tarihMetni(new Date());
$("saglik-tarih").addEventListener("change", saglikFormunuDoldur);
$("saglik-form").addEventListener("submit", saglikKaydet);
$("saglik-sil").addEventListener("click", saglikSil);
saglikFormunuDoldur();

api("/api/otomatik-baslatma").then((d) => { $("otomatik-baslatma").checked = d.acik; }).catch(() => {});
$("otomatik-baslatma").addEventListener("change", async (olay) => {
  const d = await apiGonder("/api/otomatik-baslatma", "POST", { acik: olay.target.checked });
  olay.target.checked = d.acik;
});

$("duraklat-dugme").addEventListener("click", async () => {
  await apiGonder("/api/duraklat", "POST", { duraklat: !duraklatildi });
  await durumuYenile();
});

// Kayan masaüstü mini sayacı (her zaman üstte duran küçük pencere)
let miniSayacAcik = false;

async function miniSayaciYenile() {
  try {
    const m = await api("/api/mini-sayac");
    const dugme = $("mini-sayac-dugme");
    dugme.hidden = !m.etkin;
    miniSayacAcik = Boolean(m.acik);
    dugme.textContent = miniSayacAcik ? "Mini sayacı kapat" : "Mini sayacı aç";
    dugme.classList.toggle("ders", miniSayacAcik);
  } catch {
    $("mini-sayac-dugme").hidden = true;
  }
}

$("mini-sayac-dugme").addEventListener("click", async () => {
  const dugme = $("mini-sayac-dugme");
  dugme.disabled = true;
  try {
    const m = await apiGonder("/api/mini-sayac", "POST", { acik: !miniSayacAcik });
    miniSayacAcik = Boolean(m.acik);
    dugme.textContent = miniSayacAcik ? "Mini sayacı kapat" : "Mini sayacı aç";
    dugme.classList.toggle("ders", miniSayacAcik);
  } finally {
    dugme.disabled = false;
  }
});
miniSayaciYenile();
setInterval(miniSayaciYenile, 5000);

hepsiniYenile(true);
api("/api/surum").then((s) => { $("surum").textContent = `v${s.surum}`; }).catch(() => {});

// ---------- Ayarlar (form, /api/ayarlar'daki alan tanımlarından oluşturulur) ----------

let ayarOkuyucular = {};

function ayarAlani(alan) {
  const kutu = el("div", "ayar-alan");
  kutu.dataset.anahtar = alan.anahtar;
  const kimlik = `ayar-${alan.anahtar.replace(".", "-")}`;
  const etiket = el("label", "", alan.etiket);
  etiket.htmlFor = kimlik;
  const giris = el("div", "giris");
  let girdi;

  if (alan.tur === "liste") {
    girdi = el("textarea");
    girdi.value = (alan.deger || []).join("\n");
    girdi.rows = Math.min(10, Math.max(3, (alan.deger || []).length + 1));
    ayarOkuyucular[alan.anahtar] = () => girdi.value.split("\n");
  } else if (alan.tur === "secim") {
    girdi = el("select");
    for (const s of alan.secenekler) {
      const secenek = el("option", "", s.ad);
      secenek.value = s.deger;
      girdi.append(secenek);
    }
    girdi.value = alan.deger;
    ayarOkuyucular[alan.anahtar] = () => girdi.value;
  } else if (alan.tur === "evet_hayir") {
    girdi = el("input");
    girdi.type = "checkbox";
    girdi.checked = Boolean(alan.deger);
    ayarOkuyucular[alan.anahtar] = () => girdi.checked;
  } else if (alan.tur === "tamsayi") {
    girdi = el("input");
    girdi.type = "number";
    girdi.min = alan.en_az;
    girdi.max = alan.en_cok;
    girdi.step = 1;
    girdi.value = alan.deger;
    ayarOkuyucular[alan.anahtar] = () => (girdi.value.trim() === "" ? null : Number(girdi.value));
  } else {
    girdi = el("input");
    girdi.type = "text";
    if (alan.en_uzun) girdi.maxLength = alan.en_uzun;
    girdi.value = alan.deger ?? "";
    ayarOkuyucular[alan.anahtar] = () => girdi.value;
  }
  girdi.id = kimlik;

  const satir = el("div", "satir");
  satir.append(girdi);
  if (alan.birim) satir.append(el("span", "soluk", alan.birim));
  giris.append(satir, el("span", "aciklama", alan.aciklama || ""), el("span", "hata"));
  kutu.append(etiket, giris);
  return kutu;
}

async function ayarlariYukle() {
  const d = await api("/api/ayarlar");
  ayarOkuyucular = {};
  const form = $("ayar-formu");
  form.replaceChildren(...d.gruplar.map((grup) => {
    const kume = el("fieldset", "ayar-grup");
    kume.append(el("legend", "", grup.ad), ...grup.alanlar.map(ayarAlani));
    return kume;
  }));
  $("ayar-kaydet").disabled = !d.kaydedilebilir;
  if (!d.kaydedilebilir) $("ayar-mesaj").textContent = "Bu çalıştırmada ayarlar arayüzden kaydedilemez.";
}

function ayarHatalariniGoster(hatalar) {
  for (const kutu of document.querySelectorAll(".ayar-alan")) {
    const mesaj = hatalar[kutu.dataset.anahtar] || "";
    kutu.classList.toggle("hatali", Boolean(mesaj));
    kutu.querySelector(".hata").textContent = mesaj;
  }
}

async function ayarlariKaydet(olay) {
  olay.preventDefault();
  const degisiklikler = {};
  for (const [anahtar, oku] of Object.entries(ayarOkuyucular)) degisiklikler[anahtar] = oku();
  $("ayar-kaydet").disabled = true;
  $("ayar-mesaj").textContent = "Kaydediliyor…";
  try {
    const yanit = await fetch("/api/ayarlar", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Heatmap": "1" },
      body: JSON.stringify({ degisiklikler }),
    });
    const veri = await yanit.json();
    if (yanit.status === 400 && veri.detail && veri.detail.hatalar) {
      ayarHatalariniGoster(veri.detail.hatalar);
      $("ayar-mesaj").textContent = "Kaydedilmedi: işaretli alanları düzelt.";
      return;
    }
    if (!yanit.ok) {
      $("ayar-mesaj").textContent = `Kaydedilmedi: ${typeof veri.detail === "string" ? veri.detail : yanit.status}`;
      return;
    }
    ayarHatalariniGoster({});
    $("ayar-mesaj").textContent = veri.degisen.length
      ? `Kaydedildi ve uygulandı (${veri.degisen.length} ayar değişti).`
      : "Değişiklik yok.";
    await ayarlariYukle();
    await hepsiniYenile(true);
    ayarUyarilariniYenile(veri.uyarilar || []);
  } catch {
    $("ayar-mesaj").textContent = "Kaydedilemedi: Heatmap'e ulaşılamıyor.";
  } finally {
    $("ayar-kaydet").disabled = false;
  }
}

function ayarUyarilariniYenile(uyarilar) {
  $("ayar-uyarisi").hidden = !uyarilar.length;
  $("ayar-uyari-listesi").replaceChildren(...uyarilar.map((u) => el("li", "", u)));
}

$("ayar-formu").addEventListener("submit", ayarlariKaydet);
$("ayar-geri").addEventListener("click", () => {
  ayarHatalariniGoster({});
  $("ayar-mesaj").textContent = "";
  ayarlariYukle().catch(() => {});
});

api("/api/ayar-uyarilari").then((uyarilar) => {
  $("ayar-uyarisi").hidden = !uyarilar.length;
  $("ayar-uyari-listesi").replaceChildren(...uyarilar.map((u) => el("li", "", u)));
}).catch(() => {});

setInterval(durumuYenile, 1000);                 // Sayaç her saniye
setInterval(() => hepsiniYenile(false), 15000);  // Listeler 15 saniyede bir
