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

  // Günlerin altında sağlık verisi (yalnızca hafta içinde en az bir kayıt varsa)
  const saglikVar = h.gunler.some((g) => g.adim != null || g.egzersiz_dk != null || g.uyku_dk != null);
  $("hafta-saglik").replaceChildren(...(saglikVar ? h.gunler.map(saglikHucresi) : []));

  // Seri: günlük hedefe üst üste kaç gündür ulaşıldı
  const s = await api("/api/seri");
  $("seri").textContent = s.hedef_sn
    ? `Seri: ${s.seri_gun} gün · Günlük hedef: ${sureBicimi(s.hedef_sn)} · `
    : "";
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
  olay.preventDefault();  // Formun sayfayı yeniden yüklemesini engelle
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

// ---------- Isı haritası (son 12 ay) ----------

const AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

async function isiHaritasiniYenile() {
  const v = await api("/api/isi-haritasi");
  const bugun = tarihMetni(new Date());

  // Kareler: API günleri Pazartesi'den başlayarak sırayla verir; CSS ızgarası
  // (grid-auto-flow: column) her 7 kareyi bir sütuna (haftaya) dizer.
  const izgara = $("isi-izgara");
  izgara.replaceChildren();
  for (const g of v.gunler) {
    const kare = el("i", `isi-kare s${g.seviye}`);
    if (g.gelecek) kare.classList.add("gelecek");
    if (g.tarih === bugun) kare.classList.add("bugun");
    if (!g.gelecek) {
      const [yil, ay, gun] = g.tarih.split("-").map(Number);
      kare.title = `${gun} ${AY_KISA[ay - 1]} ${yil}: ${g.ders_sn ? sureBicimi(g.ders_sn) : "kayıt yok"}`;
    }
    izgara.append(kare);
  }

  // Ay etiketleri: bir ayın ilk günü hangi haftadaysa etiket o sütunun üstüne yazılır.
  const haftaSayisi = v.gunler.length / 7;
  const etiketler = [];
  let oncekiAy = -1;
  for (let hafta = 0; hafta < haftaSayisi; hafta++) {
    const ay = Number(v.gunler[hafta * 7].tarih.slice(5, 7)) - 1;
    etiketler.push(ay !== oncekiAy && hafta < haftaSayisi - 2 ? AY_KISA[ay] : "");
    oncekiAy = ay;
  }
  // İlk sütundaki ay birkaç hafta sonra bitiyorsa iki etiket üst üste biner; ilkini at.
  const ikinci = etiketler.findIndex((e, i) => i > 0 && e);
  if (ikinci > 0 && ikinci < 3) etiketler[0] = "";
  $("isi-aylar").replaceChildren(...etiketler.map((e) => el("span", "", e)));

  // Dar ekranda harita yatay kayar; en yeni haftalar (sağ uç) görünsün.
  const kaydirma = document.querySelector(".isi-kaydirma");
  kaydirma.scrollLeft = kaydirma.scrollWidth;

  $("isi-ozet").textContent =
    `${v.aktif_gun} aktif gün · toplam ${sureBicimi(v.toplam_sn)}` +
    (v.aktif_gun ? ` · aktif gün ortalaması ${sureBicimi(v.aktif_gun_ortalamasi_sn)}` : "");
  $("isi-seri").textContent = v.hedef_sn
    ? `Hedef tutan gün: ${v.hedef_gunu} · Şu anki seri: ${v.simdiki_seri} gün · En uzun seri: ${v.en_uzun_seri} gün`
    : "";
}

// ---------- Paylaşım kartı ----------

function kartiOlustur() {
  const tur = $("kart-tur").value;
  const tarih = $("kart-tarih").value || tarihMetni(new Date());
  // Sondaki zaman damgası, tarayıcının eski resmi önbellekten göstermesini engeller.
  $("kart-resim").src = `/api/kart?tur=${tur}&tarih=${tarih}&t=${Date.now()}`;
  $("kart-indir").href = `/api/kart?tur=${tur}&tarih=${tarih}&indir=true`;
  $("kart-onizleme").hidden = false;
}

// ---------- Süre nereden geldi? (uygulama dökümü) ----------

async function dokumuYenile() {
  const bugun = new Date();
  let ilk = bugun;
  if ($("dokum-aralik").value === "hafta") {
    // Haftanın pazartesisi. getDay(): Pazar=0, Pazartesi=1 ... olduğu için (gün+6)%7 = pazartesiden uzaklık.
    ilk = new Date(bugun);
    ilk.setDate(bugun.getDate() - ((bugun.getDay() + 6) % 7));
  }
  const d = await api(`/api/dokum?baslangic=${tarihMetni(ilk)}&bitis=${tarihMetni(bugun)}`);

  const kutu = $("dokum");
  kutu.replaceChildren();
  if (!d.uygulamalar.length) {
    kutu.append(el("div", "bos", "Bu aralıkta sayılan süre yok."));
    return;
  }
  // Çubuklar en çok kullanılan uygulamaya göre oranlanır; yüzde ise toplam içindeki paydır.
  const enUzun = d.uygulamalar[0].sure_sn || 1;
  for (const u of d.uygulamalar) {
    const satir = el("div", "dokum-satir");
    // u.ad: okunabilir ad (ayar dosyasındaki [adlar] ve [siteler] bölümlerinden gelir)
    const ad = el("span", "ad", u.ad);
    ad.title = u.tur === "site" ? `${u.ad} (web sitesi)` : u.ad;
    const ray = el("div", "ray");
    const dolgu = el("div", "dolgu");
    dolgu.style.width = `${(u.sure_sn / enUzun) * 100}%`;
    ray.append(dolgu);
    satir.append(ad, ray, el("span", "deger soluk", `${sureBicimi(u.sure_sn)} · %${Math.round(u.oran * 100)}`));
    kutu.append(satir);
  }
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
  if (o.alan_adi) ust.append(el("span", "soluk", o.alan_adi));  // eklentiden gelen site adı
  if (o.duzeltme) ust.append(el("span", "soluk", "(sen düzelttin)"));
  bilgi.append(ust, el("div", "baslik-metin", o.baslik || ""), el("div", "soluk", o.aciklama || ""));

  // Düzeltme araçları
  const islemler = el("div", "islemler");
  const dersti = el("button", "dugme ders" + (o.duzeltme === "ders" ? " secili" : ""), "Çalışmaydı");
  const degildi = el("button", "dugme degil" + (o.duzeltme === "ders_degil" ? " secili" : ""), "Çalışma değildi");
  islemler.append(dersti, degildi);

  // Kural öğrenme sadece uygulama ve tarayıcı oturumlarında anlamlı (boşta kalma için değil).
  let ogrenKutusu = null;
  let kelimeKutusu = null;
  let siteKutusu = null;
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
  if (o.kaynak === "baslik" && o.alan_adi) {
    // Eklenti site adını bildirdiyse: o sitedeki her şeyi aynı şekilde say (varsayılan kapalı;
    // YouTube gibi sitelerde içerik videoya göre değiştiği için dikkatli kullanılmalı).
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

// ---------- Başlangıç ----------

async function hepsiniYenile(zorla) {
  try {
    await Promise.all([durumuYenile(), haftayiYenile(), isiHaritasiniYenile(), dokumuYenile(), oturumlariYenile(zorla), kurallariYenile()]);
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
$("dokum-aralik").addEventListener("change", dokumuYenile);
$("kart-olustur").addEventListener("click", kartiOlustur);
$("kart-tarih").value = $("kart-tarih").max = tarihMetni(new Date());  // Gelecek seçilemesin

$("kamera-acik").addEventListener("change", kameraAcKapat);
$("kamera-kalibre").addEventListener("click", kameraKalibre);
kamerayiYenile().catch(() => {});
setInterval(() => kamerayiYenile().catch(() => {}), 3000);  // Canlı açı (yalnızca ekranda, kaydedilmez)

$("saglik-tarih").value = $("saglik-tarih").max = tarihMetni(new Date());
$("saglik-tarih").addEventListener("change", saglikFormunuDoldur);
$("saglik-form").addEventListener("submit", saglikKaydet);
$("saglik-sil").addEventListener("click", saglikSil);
saglikFormunuDoldur();

// Windows açılışında otomatik başlatma (gerçek durum kayıt defterinden okunur)
api("/api/otomatik-baslatma").then((d) => { $("otomatik-baslatma").checked = d.acik; }).catch(() => {});
$("otomatik-baslatma").addEventListener("change", async (olay) => {
  const d = await apiGonder("/api/otomatik-baslatma", "POST", { acik: olay.target.checked });
  olay.target.checked = d.acik;  // İşlem başarısız olduysa kutu gerçek durumu göstersin
});
$("onceki-gun").addEventListener("click", () => gunKaydir(-1));
$("sonraki-gun").addEventListener("click", () => gunKaydir(1));
$("duraklat-dugme").addEventListener("click", async () => {
  await apiGonder("/api/duraklat", "POST", { duraklat: !duraklatildi });
  await durumuYenile();
});

hepsiniYenile(true);
setInterval(durumuYenile, 1000);                 // Sayaç her saniye
setInterval(() => hepsiniYenile(false), 15000);  // Listeler 15 saniyede bir
