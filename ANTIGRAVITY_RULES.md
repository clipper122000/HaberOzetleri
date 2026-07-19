# 📜 Proje1 Kodlama ve Mimari Kuralları Anayasası

## 1. Genel Prensipler
- Projede yazılacak tüm kodlar temiz, okunabilir ve kendi kendini açıklayan yapıda olmalıdır.
- Sadece Python 3.10+ ve FastAPI/Flask gibi hafif, güvenilir yapılar tercih edilmelidir.

## 2. Backend & Veritabanı Kuralları
- Tüm SQL sorguları kesinlikle parametrik yazılacaktır. Ham string birleştirme (SQL Injection riski) kesinlikle yasaktır.
- Fonksiyonlarda hata yönetimi için asla boş `except:` bloğu bırakılamaz. Her hata loglanmalıdır.