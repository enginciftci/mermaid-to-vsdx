# Airgapped (Offline) Kurulum ve Kullanım Kılavuzu
### Mermaid to Microsoft Visio (.vsdx) Converter

Bu paket, **internet bağlantısı bulunmayan (airgapped)** kapalı devre Windows 10/11 bilgisayarlarda doğrudan çalıştırılmak üzere hazırlanmıştır.

---

## 📦 Paket İçeriği

- **`wheels/`**: Python 3.9, 3.10, 3.11 ve 3.12 (Windows 64-bit) için önceden indirilmiş tüm çevrimdışı tekerlek (wheel) paketleri:
  - `pywin32` (Visio COM otomasyonu için)
  - `pillow` (Doğrulama ve görsel önizleme için)
  - `sv_ttk` (Modern Windows 11 Fluent arayüz teması için)
- **`src/`**: Tam kaynak kodları (Ayrıştırıcı, Visio COM motoru, Türkçe karakter desteği, Grafik Arayüz).
- **`install_offline.bat`**: İnternet aramaksızın yerel `wheels/` klasöründen kurulum yapan tek tık betik.
- **`run.bat`**: Uygulamayı başlatan ana Windows başlatıcısı (bağımlılık eksikse otomatik çevrimdışı kurar).
- **`run.ps1`**: PowerShell üzerinden başlatma alternatifi.
- **`main.py`**: Hem Grafik Arayüz (GUI) hem de Komut Satırı (CLI) ana giriş noktası.
- **`tests/`**: Çevrimdışı çalıştırılabilen birim ve entegrasyon testleri.

---

## 💻 Önkoşullar (Hedef Bilgisayarda)

1. **Python 3.9, 3.10, 3.11 veya 3.12 (64-bit)**:
   - Bilgisayarda Python kurulu olmalı ve "Add Python to PATH" seçeneği etkinleştirilmiş olmalıdır.
2. **Microsoft Visio**:
   - Yerel olarak kurulu Microsoft Visio (Visio 2016, Visio 2019, Visio 2021 veya Microsoft 365).

---

## 🚀 Airgapped Bilgisayara Kurulum Adımları

1. **Paketi Taşıma**:
   - `Mermaid_to_Visio_Converter_Offline_Airgapped.zip` dosyasını USB bellek veya dahili ağ üzerinden hedef bilgisayara kopyalayınız.
   - Dosyayı istediğiniz bir klasöre çıkartınız (örneğin `C:\MermaidToVisio\`).

2. **Çevrimdışı Kurulum (Tek Tık)**:
   - Klasör içindeki **`install_offline.bat`** dosyasına çift tıklayınız.
   - Bu işlem, yerel `wheels/` klasöründeki paketleri yükleyecek ve harici internete **asla** bağlanmaya çalışmayacaktır.
   - Ekranda `[BASARILI] Tum bagimliliklar cevrimdisi olarak kuruldu!` mesajını göreceksiniz.

   *(Manuel olarak komut satırından kurmak isterseniz)*:
   ```cmd
   python -m pip install --no-index --find-links=wheels -r requirements.txt
   ```

3. **Uygulamayı Başlatma**:
   - **`run.bat`** dosyasına çift tıklayarak modern grafik arayüzü başlatabilirsiniz.
   - Veya komut satırından:
     ```cmd
     python main.py
     ```

---

## 🖥️ Kullanım

### Grafik Arayüz (GUI):
- Sol paneldeki açılır listeden Türkçe şablonları seçebilir veya kendi Mermaid kodunuzu yapıştırabilirsiniz.
- **"🚀 Visio'ya Dönüştür (.vsdx)"** butonuna basarak çizimin oluşturulmasını ve sağ panelde yüksek çözünürlüklü doğrulama ekran görüntüsünün açılmasını sağlayabilirsiniz.
- **"📂 Çizimi Visio'da Aç"** butonu ile oluşturulan `.vsdx` dosyasını doğrudan Microsoft Visio'da açıp düzenleyebilirsiniz.

### Komut Satırı (CLI - Otomasyon & Betikler İçin):
```cmd
python main.py ornek.mmd -o cikti.vsdx --verify
```

---

## 🧪 Çevrimdışı Testleri Çalıştırma

Hedef bilgisayarda sistemin sorunsuz çalıştığını teyit etmek için:
```cmd
python -m unittest discover -s tests -p "test_*.py" -v
```
Tüm 13 testin internet gerektirmeksizin başarıyla tamamlandığını göreceksiniz.
