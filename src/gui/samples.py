"""
Mermaid diagram sample presets with rich Turkish character content and various diagram types.
"""

SAMPLES = {
    "1. Akış Şeması - E-Ticaret Sipariş & Kargo Süreci (Flowchart TD)": """graph TD
    A([Müşteri Siparişi Oluşturdu]) --> B[Ödeme Onayı Bekleniyor]
    B --> C{Ödeme Başarılı mı?}
    C -->|Evet: Kart Çekildi| D[(Sipariş Veritabanına Kaydet)]
    C -->|Hayır: Yetersiz Bakiye| E[Kullanıcıya SMS ve E-Posta Bildirimi]
    E --> F([İşlemi İptal Et])
    
    D --> G[Depo Hazırlık Birimine İlet]
    G --> H[Fatura ve İrsaliye Düzenle]
    H --> I[(Kargo Takip Sistemi)]
    I --> J[Kuryeye Teslim Edildi]
    J --> K([Müşteriye Teslim Edildi])
""",

    "2. Alt Sistemler - Mikroservis & Veritabanı Mimarisi (Subgraphs LR)": """flowchart LR
    subgraph MUSTERI_PANELI ["Müşteri Ön Yüzü & Kimlik Doğrulama"]
        A[Web Tarayıcı İstemcisi]
        B[Mobil Uygulama iOS/Android]
    end

    subgraph AG_GECIDI ["API Ağ Geçidi (API Gateway)"]
        GW[Tersine Dizin ve Güvenlik Duvarı]
    end

    subgraph MIKROSERVISLER ["İç İşlem Mikroservisleri"]
        S1[Kullanıcı Servisi]
        S2[Ödeme ve Provizyon Servisi]
        S3[Bildirim ve Mesajlaşma Servisi]
    end

    subgraph VERI_KATMANI ["Güvenli Veritabanı Deposu"]
        DB1[(PostgreSQL Müşteri Verisi)]
        DB2[(Redis Önbellek Kümesi)]
        DB3[(Kafka Olay Kuyruğu)]
    end

    A --> GW
    B --> GW
    GW --> S1
    GW --> S2
    GW --> S3
    S1 --> DB1
    S2 --> DB2
    S3 --> DB3
""",

    "3. Karar Ağacı - Kredi Başvuru Değerlendirme & Risk Analizi (Flowchart TD)": """graph TD
    BASLA([Kredi Başvurusu Alındı]) --> KONTROL[KKB ve Findeks Puanı Sorgula]
    KONTROL --> PUAN_KONTROL{Puan >= 1400 mü?}
    
    PUAN_KONTROL -->|Evet| GELIR_TESTI{Aylık Gelir Yeterli mi?}
    PUAN_KONTROL -->|Hayır| RED_SEBEP[Risk Seviyesi Yüksek Reddi]
    RED_SEBEP --> BITIS_RED([Başvuru Reddedildi])
    
    GELIR_TESTI -->|Evet| ONAY_LIMIT[Kredi Limiti ve Faiz Oranı Belirle]
    GELIR_TESTI -->|Hayır| KEFIL_SOR[Ek Teminat veya Kefil İste]
    
    KEFIL_SOR --> KEFIL_ONAY{Kefil Uygun mu?}
    KEFIL_ONAY -->|Evet| ONAY_LIMIT
    KEFIL_ONAY -->|Hayır| BITIS_RED
    
    ONAY_LIMIT --> SOZLESME[(Dijital Sözleşme İmzala)]
    SOZLESME --> HESABA_AKT([Hesaba Kredi Tutarı Aktarıldı])
""",

    "4. Sıralama Şeması - Kullanıcı Girişi & 2FA Doğrulama (Sequence Diagram)": """sequenceDiagram
    autonumber
    title Güvenli Kullanıcı Girişi ve İki Aşamalı Doğrulama (2FA) Protokolü
    actor K as Kullanıcı (Tarayıcı)
    participant S as Kimlik Sunucusu (Auth)
    participant SMS as SMS Gönderim Ağ Geçidi
    participant DB as Güvenli Veritabanı

    K->>S: Kullanıcı Adı ve Şifre Gönder
    S->>DB: Şifre Özetini Doğrula (Argon2id)
    DB-->>S: Şifre Doğrulandı (Kullanıcı Aktif)
    
    Note over S,SMS: 6 Haneli Tek Kullanımlık Güvenlik Kodu Üret
    S->>SMS: SMS Doğrulama Kodu İlet (+90 5XX XXX XX XX)
    SMS-->>K: SMS Kodu İletildi: 849201
    
    K->>S: SMS Kodunu Gir: 849201
    S->>S: Kodu ve Geçerlilik Süresini Kontrol Et
    Note over S: Güvenlik Kontrolü Başarılı
    S-->>K: Oturum Jetonu (JWT Bearer Token) Üretildi
""",

    "5. Sıralama Şeması - Banka Ödeme ve Provizyon Entegrasyonu (Sequence Diagram)": """sequenceDiagram
    autonumber
    title Banka Sanal POS Ödeme Provizyon Süreci
    actor M as Müşteri
    participant E as E-Ticaret Sunucusu
    participant POS as Banka Sanal POS Servisi
    participant B as Kart Sahibi Bankası

    M->>E: Siparişi Onayla ve Kart Bilgilerini Gönder
    E->>POS: 3D Secure Doğrulama İsteği Başlat
    POS->>B: 3D Secure Doğrulama Sayfası Yönlendirmesi
    B-->>M: Doğrulama Şifresi SMS ile Gönderildi
    M->>B: SMS Şifresini Gir ve Doğrula
    B-->>POS: 3D Secure Kimlik Doğrulama Başarılı
    POS->>POS: Provizyon / Bakiye Bloke İşlemi
    POS-->>E: Ödeme Onaylandı (İşlem No: TR-948291)
    E-->>M: Sipariş Başarıyla Tamamlandı Fişi
""",

    "6. Alfabe & Karakter Testi - 100% Türkçe Karakter Bütünlüğü (Flowchart TD)": """graph TD
    A[Başlangıç: çğıöşü ÇĞİÖŞÜ] -->|İğne İplik Testi| B(Küçük Harfler: ç, ğ, ı, ö, ş, ü)
    B -->|Şüpheli İşlem Bildirimi| C{Büyük Harfler: Ç, Ğ, İ, Ö, Ş, Ü}
    C -->|Doğru Kodlama: UTF-8| D[(Türkçe Veritabanı Tablosu: Öğrenci İşleri)]
    C -->|Hatalı Kodlama Algılandı| E[Hata Günlüğü: Çağdaş İletişim]
    D --> F([İşlem Başarıyla Tamamlandı: Teşekkürler!])
""",

    "7. Sınıf Şeması - E-Ticaret ve Ödeme Nesne Mimarisi (Class Diagram)": """classDiagram
    class OdemeYontemi {
        <<interface>>
        +String ad
        +odemeYap(tutar) bool
        +iadeEt(tutar) bool
    }
    class KrediKarti {
        -String kartNumarasi
        -String sonKullanmaTarihi
        -String cvv
        +odemeYap(tutar) bool
    }
    class HavaleEFT {
        -String iban
        -String bankaKodu
        +odemeYap(tutar) bool
    }
    class Siparis {
        +String siparisKodu
        +Date olusturmaTarihi
        +BigDecimal toplamTutar
        +siparisOnayla() bool
        +iptalEt() void
    }
    class Musteri {
        +String adSoyad
        +String ePosta
        +girisYap() bool
    }

    OdemeYontemi <|.. KrediKarti : uygular
    OdemeYontemi <|.. HavaleEFT : uygular
    Musteri "1" --> "*" Siparis : verir
    Siparis *-- "1" OdemeYontemi : icerir
""",

    "8. Durum Şeması - Kullanıcı Oturumu ve İşlem Döngüsü (State Diagram)": """stateDiagram-v2
    direction TD
    [*] --> Beklemede: Sistem Başlatıldı
    Beklemede --> KimlikDogrulama: Giriş Talebi
    KimlikDogrulama --> Aktif: Şifre Doğrulandı (çğıöşü)
    KimlikDogrulama --> Kilitli: Hatalı Giriş Denemesi (3x)
    Kilitli --> Beklemede: Yönetici Sıfırlama Yaptı
    Aktif --> IslemYapiliyor: Güvenli İşlem Seçildi
    IslemYapiliyor --> Aktif: İşlem Başarıyla Tamamlandı
    Aktif --> [*]: Güvenli Çıkış Yapıldı
""",

    "9. Varlık İlişki Şeması - E-Ticaret Veritabanı Mimarisi (ER Diagram)": """erDiagram
    MUSTERI ||--o{ SIPARIS : verir
    SIPARIS ||--|{ SIPARIS_DETAY : icerir
    URUN ||--o{ SIPARIS_DETAY : listelenir
    SIPARIS ||--|| ODEME : tamamlanir

    MUSTERI {
        string musteriId PK
        string adSoyad
        string eposta
        string telefon
    }

    SIPARIS {
        int siparisNo PK
        string musteriId FK
        datetime siparisTarihi
        float toplamTutar
        string durum
    }

    SIPARIS_DETAY {
        int detayId PK
        int siparisNo FK
        string urunKodu FK
        int adet
        float birimFiyat
    }

    URUN {
        string urunKodu PK
        string urunAdi
        float fiyat
        int stokAdedi
    }

    ODEME {
        string odemeId PK
        int siparisNo FK
        string odemeTuru
        float tutar
        datetime odemeZamani
    }
"""
}
