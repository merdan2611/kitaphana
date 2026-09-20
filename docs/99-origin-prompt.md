# Kitaphana — Opus 5 Roadmap Promptu

Claude subscription aldığında, bu dosyanın tamamını Opus 5'e (Claude Platform / claude.ai üzerinde) verip aşağıdaki isteği ekleyebilirsin.

---

## Proje Bağlamı (Opus'a kopyala-yapıştır)

**Proje:** Kitaphana — Türkmen dilinde kitap indirebilecek, PDF yükleyebilecek, "yıldız" kredi sistemiyle limitlenen ücretsiz/ücretli indirme yapılabilen, kitap talep edebilen bir dijital kütüphane web sitesi.

**Geliştirici profili:**
- Tek geliştirici, bilgisayar mühendisliği öğrencisi, gece 19:00-07:00 vardiyalı çalışıyor
- Haftada ~5-10 saat gerçekçi zaman bütçesi
- Linux'a aşina (Pop!_OS/Ubuntu, Fedora), ama sunucu deploy'una (systemd/nginx) yeni
- Türkmenistan içinde yaşıyor ve hedef kitlesi de büyük ihtimalle Türkmenistan içi
- Claude Code kullanarak tek başına geliştirecek (çoklu-ajan / paralel sprint koordinasyonu YOK)

**Teknik kararlar (bunlar sabit, değiştirilmemeli):**

| Alan | Karar |
|---|---|
| Barındırma | Turkmentelecom VDS Storage M (2 core, 2GB RAM, 120GB SSD, 403,20 TMT/ay) |
| PDF depolama | VPS'in yerel diski (harici cloud/CDN yok, dış bağımlılık istenmiyor) |
| Backend / DB | FastAPI + SQLite |
| Frontend | Düz HTML/CSS/JS (framework yok) |
| Deployment | Manuel: systemd + nginx (Docker YOK — 2GB RAM'de overhead istenmiyor) |
| Deployment workflow | Git/GitHub tabanlı — repo bir kez klonlanır, geliştirme local'de yapılır, VPS'te ayrı bir klon `git pull` ile güncellenir |
| Ödeme | "Yıldız" kredi sistemi, mobil operatör transferi ile satın alınır |
| Ödeme algılama | Ayrı bir Android telefon + SMS forwarding app → backend webhook (gelen SMS'ten gönderen numara çıkarılır, o numaraya kayıtlı hesaba yıldız eklenir) |
| Hesaplar | Telefon numarası + SMS OTP (email/username yok) |
| Kitap istekleri | Anonim yayınlanır, herkese açık upvote var; ileride yıldızla öncelikli istek eklenecek |
| Toplu içe aktarma | Mevcut ~30GB+ PDF koleksiyonu için yarı-otomatik: script Open Library'den eşleşme dener, eşleşmeyenler (çoğu Türkmence kitap) elle giriş kuyruğuna düşer |
| Yedekleme | Otomatik yok — orijinal PDF'ler zaten geliştiricinin kendi bilgisayarında/harici diskinde duruyor, felaket durumunda elle tekrar yüklenecek |
| Domain | Dışarıdan (yabancı registrar) alınacak, TM VPS'e yönlendirilecek |
| Admin paneli | Baştan var olacak (web arayüzü — kitap ekleme, istek onaylama, kullanıcı yönetimi) |
| Test/Demo modu | Erken bir fazda site uçtan uca canlı ve test edilebilir olmalı; bu aşamada OTP gerçek SMS yerine ekranda gösterilecek ("dev demo" modu) |

## İstenen Doküman Yapısı (repo içinde)

Tek bir dev karışık roadmap dosyası yerine, aşağıdaki gibi **yapılandırılmış bir `docs/` klasörü** isteniyor (bir arkadaşın projesinden ilham alındı, ama tek-geliştirici ölçeğine sadeleştirilmiş hali):

```
docs/
  00-vision.md                # Kitaphana neden var, kime hizmet ediyor
  01-glossary.md              # yıldız, istek, upvote gibi terimler sözlüğü
  02-phases.md                # Faz özetleri: Faz 1 (dev-demo MVP) → Faz 2 (gerçek SMS) → Faz 3 (yıldız-öncelikli istek) → ...
  03-roadmap.md               # "Neredeyiz?" dosyası — en üstte basit bir "Current Sprint" tablosu
                               # (Sprint adı, Status, Phase, Sprint doc linki, Milestone), altında faz/sprint trajectory
  adr/
    0001-<karar-adi>.md       # Her büyük teknik karar için kısa, numaralı, gerekçeli bir ADR
    0002-...
  sprints/
    sprint-01-<isim>.md       # Her sprint'in detay dosyası: task listesi, definition of done, testler
    sprint-02-...
```

**Bilinçli olarak İSTENMEYEN şeyler** (arkadaşın projesinde vardı ama bu ölçekte gereksiz):
- PR/issue numarasıyla çapraz referans sistemi (GitHub Issues'a yoğun bağımlı, çok-sprint'li süreç gerektirir)
- "Agents: bu bloğu her sprint başında güncelle" gibi çoklu-ajan koordinasyon talimatları (tek başına, tek Claude Code oturumunda çalışılacak)

## İstek (Opus'a verilecek asıl komut)

Yukarıdaki bağlamı ve doküman yapısını kullanarak bana **çok detaylı bir roadmap** hazırla:

1. **Yukarıdaki `docs/` yapısını doldur.** Her dosyayı ayrı ayrı üret (00-vision.md'den başlayarak).
2. **Fazlara (Phase) böl** (`02-phases.md`). Her fazın sonunda elle test edebileceğim, çalışan bir şey olsun. İlk faz, dev-OTP modlu, uçtan uca test edilebilir canlı bir MVP ile bitmeli.
3. **Her faz içinde sprint'lere böl** (`sprints/sprint-NN-*.md`). Haftada 5-10 saatlik bütçeme göre sprint'leri ~1 haftalık tut.
4. **Her sprint dosyasında somut task'lar olsun**, her task için net bir "bitti" kriteri (definition of done) yazılsın.
5. **Her büyük teknik kararı bir ADR olarak yaz** (`adr/000N-*.md`) — yukarıdaki tablo satırlarının her biri birer ADR adayı (ör. "0001-local-disk-pdf-storage.md", "0002-sqlite-over-postgres.md", "0003-manual-deploy-no-docker.md", "0004-sms-forwarding-android-phone.md" vb.), kısa gerekçesiyle birlikte.
6. **Bilmediğim/araştırmam gereken şeyleri ayrı işaretle** — örneğin "Turkmentelecom VDS panelinde snapshot/backup seçeneği var mı, kontrol et" gibi research task'ları, normal geliştirme task'larının içine gizlenmesin.
7. Riskleri ve bağımlılıkları belirt (örn. SMS forwarding app'in güvenilirliği, tek VPS'in tek nokta arıza riski gibi).

---

## Workflow Notu (kendine hatırlatma)

- Repo bir kez `git clone` edilir, geliştirme boyunca local makinende kalır — Claude Code her session'da bu klasörü açar, `docs/03-roadmap.md`'yi okuyarak "neredeyiz" bilgisini alır (bu dosya, oturumlar arası hafızanın yerini tutuyor).
- VPS'te ayrı bir klon durur; deploy = VPS'te `git pull` + servisi yeniden başlatma.
- Roadmap taşa kazınmış değil — her sprint sonunda gerçek ilerlemeye göre güncellenir.

*Not: Bu doküman [[kitaphana]] projesi için Claude ile yapılan bir "grilling" (fikir netleştirme) oturumunun çıktısıdır.*
