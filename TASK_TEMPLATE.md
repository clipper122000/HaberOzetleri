# Task: Morning Press Summary & PDF Email Reporter - v2

## 1. Objective & Scope
Her sabah TSİ 07:30'da otomatik olarak tetiklenecek; Türkiye yerel basınındaki gelişmeleri (Genel, Savunma Sanayii, Spor) ve dünya basınındaki Türkiye odaklı içerikleri tarayıp, yapay zeka ile özet çıkartarak kullanıcıya şık bir PDF dokümanı halinde Gmail üzerinden raporlayacak otonom bir sistem kurulması.

## 2. System Architecture (Design Guidance)
Sistem modüler yapıda olup şu bileşenlerden oluşacaktır:
- `scraper.py`: Belirlenen ulusal haber kaynaklarından ve global ağlardan günlük verileri toplar.
- `analyzer.py`: Toplanan metinleri temizler, mükerrer kayıtları eler ve LLM API kullanarak kategorize edilmiş kısa özetler üretir. Global kaynaklardan gelen tüm yabancı dildeki içerikleri akıcı bir Türkçe diline çevirerek özetler. Haberlerin orijinal kaynak adını ve web linkini çıktı modelinde muhafaza eder.
- `pdf_generator.py`: Analiz edilen verileri HTML/CSS şablonuna yerleştirir. Haber özetlerinin yanına veya altına, kaynağın adını içeren ve tıklandığında orijinal habere yönlendiren aktif web linkleri (`<a href="...">`) yerleştirerek `weasyprint` ile PDF üretir.
- `mailer.py`: Üretilen PDF dokümanını ek (attachment) olarak ekleyip kullanıcının Gmail adresine güvenli SMTP oturumu ile gönderir.
- `.github/workflows/daily_report.yml`: GitHub Actions otomasyon akışı.

## 3. Tech Stack
- **Language:** Python 3.10+
- **Libraries:** `feedparser`, `requests`, `beautifulsoup4`, `pydantic`, `weasyprint`
- **Automation:** GitHub Actions (Cron Trigger: `30 4 * * *` UTC)
- **Secrets:** `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `LLM_API_KEY`

## 4. Input Data & Sources
- **Yerel Basın:** TRT Haber, Anadolu Ajansı, Hürriyet, Milliyet, Cumhuriyet, Yeni Şafak, Yeni Akit, Sözcü, Habertürk, Bloomberg HT RSS kanalları. Tarama esnasında savunma sanayii ve spor odaklı alt kategoriler/kelimeler de önceliklendirilir.
- **Dünya Basını:** Google News Global RSS ("Turkey", "Turkiye" sorguları) + Reuters ve BBC World ana akışları.

## 5. Expected Output (PDF Structure)
Oluşturulacak PDF dokümanı şu kurumsal sayfa yapısına sahip olmalıdır:
- **Kapak/Başlık:** 📅 [Tarih] Günlük Türkiye ve Dünya Gündemi Raporu
- **Bölüm 1:** 🇹🇷 Türkiye Genel Gündemi (En kritik 5 gelişme)
- **Bölüm 2:** 🛡️ Savunma Sanayii Gelişmeleri (Yerel ve global basındaki yansımalar)
- **Bölüm 3:** 🏆 Spor Faaliyetleri ve Başarılar (Günün öne çıkan spor gelişmeleri)
- **Bölüm 4:** 🌍 Dünya Basınında Türkiye (Global medyanın analizi)
- **Naming Convention:** Üretilen ve mail ile gönderilen PDF dosyasının adı dinamik olarak o günün tarihiyle oluşturulmalıdır. Format: `Haber Ozeti YYYY.MM.DD.pdf` (Örn: `Haber Ozeti 2026.07.19.pdf`). Dosya isminde Türkçe karakter sorunları yaşanmaması için "Özeti" yerine "Ozeti" kullanılması tercih edilmelidir.
- **İçerik Detayı ve İzlenebilirlik:** Her haber maddesinin sonunda veya başında hangi kaynaktan alındığı açıkça belirtilmeli (Örn: "Kaynak: Reuters") ve bu kaynak ismi veya yanındaki bir buton/ikon, haberin detayına ulaşmayı sağlayan tıklanabilir bir web linki barındırmalıdır.
- **Dil:** Rapordaki tüm içerik, başlıklar ve özetler tamamen Türkçe olmalıdır.

## 6. Constraints & Rules
- **SECURITY:** Kimlik bilgileri kesinlikle kod içinde yer alamaz (`os.environ`).
- **PDF Design:** PDF tasarlanırken modern tipografi, kurumsal renk paleti (örneğin lacivert/gri tonları) ve temiz sayfa boşlukları kullanılmalıdır. `weasyprint` standartlarına uygun olarak `display: flex/grid` yerine tablo ve blok yerleşimleri tercih edilmelidir.