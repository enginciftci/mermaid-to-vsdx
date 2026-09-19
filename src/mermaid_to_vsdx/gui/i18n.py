"""
Internationalization (i18n) localization tables for Mermaid to Visio Converter.
Supports Turkish (tr_TR) and English (en_US).
"""

from typing import Dict, Any

LANGUAGES = {
    "tr": "🇹🇷 Türkçe",
    "en": "🇺🇸 English (US)",
}

DEFAULT_LANGUAGE = "tr"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "tr": {
        "app_title": "Mermaid ➔ Microsoft Visio (.vsdx) Dönüştürücü - Professional Edition",
        "header_title": "📐 Mermaid ➔ Microsoft Visio (.vsdx) Dönüştürücü",
        "visio_checking": "Visio Kontrol Ediliyor...",
        "visio_ready": "✓ Microsoft Visio Hazır (Sürüm {ver})",
        "visio_independent": "⚡ Bağımsız Motor Aktif (Visio Gerekmez)",
        "visio_not_found": "⚠ Microsoft Visio Bulunamadı",
        "language_label": "Dil / Language:",
        # Presets & Editor Toolbar
        "sample_templates": "Örnek Şablonlar:",
        "load_file": "Dosyadan Yükle",
        "save_file": "Kaydet",
        "clear_editor": "Temizle",
        "clear_confirm_title": "Temizle",
        "clear_confirm_msg": "Düzenleyicideki tüm metni temizlemek istediğinize emin misiniz?",
        "editor_cleared": "Düzenleyici temizlendi.",
        # Settings Bar
        "style_settings": " Çizim & Stil Ayarları ",
        "palette_label": "Renk Paleti:",
        "font_label": "Unicode Yazı Tipi:",
        # Action Buttons
        "btn_convert": "🚀 Visio'ya Dönüştür (.vsdx)",
        "btn_export_vsdx": "💾 .vsdx Dışa Aktar",
        "btn_export_png": "📷 PNG Kaydet",
        "btn_open_visio": "📂 Çizimi Visio'da Aç",
        "btn_open_general": "🌐 Çizimi Aç / Görüntüle",
        # Preview Toolbar
        "btn_fit": "🔍 Ekrana Sığdır",
        "btn_zoom_in": "➕ Yakınlaştır",
        "btn_zoom_out": "➖ Uzaklaştır",
        "btn_orig": "1:1 Orijinal",
        "scale_label": "Ölçek: {scale}%",
        "preview_placeholder": "🎨 Visio Görsel Doğrulama Önizlemesi\n\n'Visio'ya Dönüştür' butonuna basarak\nşemanızı oluşturabilir ve canlı önizleyebilirsiniz.",
        "preview_status_empty": "Görsel Doğrulama: Henüz şema oluşturulmadı.",
        "preview_status_loaded": "Görsel Doğrulama: {width}x{height} px ({size_kb} KB, {time_sec}s)",
        # Bottom Console
        "console_title": " İşlem Günlüğü ve Durum Bildirimleri ",
        "log_ready": "Uygulama başlatıldı. Hazır.",
        "log_sample_loaded": "Örnek şablon yüklendi: {name}",
        "log_markdown_extracted": "Markdown dosyasından Mermaid kod bloğu ayıklandı: {path}",
        "log_file_loaded": "Dosya yüklendi: {path}",
        "log_file_saved": "Mermaid kodu kaydedildi: {path}",
        "log_turkish_detected": "Türkçe Karakter Denetimi: {total} adet Türkçe karakter tespit edildi ({chars}).",
        "log_step_1": "1/3 Mermaid kodu çözümleniyor (AST oluşturuluyor)...",
        "log_step_2": "2/3 Visio çizimi oluşturuldu: {name}",
        "log_step_3": "3/3 Canlı görsel önizleme oluşturuluyor...",
        "log_success": "✓ BAŞARILI: Çizim kaydedildi ve önizlendi ({engine})! ({width}x{height} px, {size_kb} KB, {time_sec}s)",
        "log_export_vsdx": "Visio açılmadan doğrudan .vsdx dışa aktarılıyor: {name}...",
        "log_export_vsdx_success": "✓ Başarıyla kaydedildi (Visio açılmadı): {path}",
        "log_export_png_success": "✓ Görsel başarıyla kaydedildi: {path}",
        "log_visio_detected": "Microsoft Visio COM servisi algılandı: Sürüm {ver}",
        "log_visio_independent_info": "Bilgi: Microsoft Visio bulunamadı. Tüm .vsdx dosyaları dahili bağımsız motor ile %100 uyumlu olarak üretilmektedir.",
        "log_drawio_opened": "Draw.io Web tarayıcıda açıldı. Oluşturulan .vsdx dosyasını sürükleyip bırakarak ücretsiz görüntüleyebilirsiniz.",
        "log_lang_changed": "Arayüz dili Türkçe olarak ayarlandı.",
        # Messages & Dialogs
        "warn_title": "Uyarı",
        "error_title": "Hata",
        "success_title": "Başarılı",
        "warn_no_code": "Lütfen dönüştürülecek Mermaid kodunu giriniz.",
        "warn_no_preview": "Dışa aktarılacak görsel önizleme bulunamadı. Lütfen önce dönüştürün.",
        "vsdx_exported_msg": "Visio (.vsdx) dosyası başarıyla kaydedildi:\n\n{path}",
        "png_exported_msg": "Diyagram resmi başarıyla kaydedildi:\n\n{path}",
        "non_visio_dialog_title": "Visio Dosyasını Görüntüle",
        "non_visio_dialog_msg": (
            "Bu bilgisayarda Microsoft Visio bulunamadı.\n\n"
            "• [Evet]: Dosyayı sistemin varsayılan uygulamasıyla (Draw.io, LibreOffice vb.) aç\n"
            "• [Hayır]: Ücretsiz Draw.io Web görüntüleyicisini tarayıcıda aç (vsdx dosyasını sürükleyip bırakabilirsiniz)\n"
            "• [İptal]: Dosya konumunu klasörde göster"
        ),
    },
    "en": {
        "app_title": "Mermaid ➔ Microsoft Visio (.vsdx) Converter - Professional Edition",
        "header_title": "📐 Mermaid ➔ Microsoft Visio (.vsdx) Converter",
        "visio_checking": "Checking Visio...",
        "visio_ready": "✓ Microsoft Visio Ready (v{ver})",
        "visio_independent": "⚡ Native Engine Active (No Visio Needed)",
        "visio_not_found": "⚠ Microsoft Visio Not Found",
        "language_label": "Language / Dil:",
        # Presets & Editor Toolbar
        "sample_templates": "Sample Templates:",
        "load_file": "Load from File",
        "save_file": "Save",
        "clear_editor": "Clear",
        "clear_confirm_title": "Clear Editor",
        "clear_confirm_msg": "Are you sure you want to clear all text in the editor?",
        "editor_cleared": "Editor cleared.",
        # Settings Bar
        "style_settings": " Drawing & Style Settings ",
        "palette_label": "Color Palette:",
        "font_label": "Unicode Font:",
        # Action Buttons
        "btn_convert": "🚀 Convert to Visio (.vsdx)",
        "btn_export_vsdx": "💾 Export .vsdx",
        "btn_export_png": "📷 Save PNG",
        "btn_open_visio": "📂 Open in Visio",
        "btn_open_general": "🌐 Open / View Diagram",
        # Preview Toolbar
        "btn_fit": "🔍 Fit to View",
        "btn_zoom_in": "➕ Zoom In",
        "btn_zoom_out": "➖ Zoom Out",
        "btn_orig": "1:1 Original",
        "scale_label": "Scale: {scale}%",
        "preview_placeholder": "🎨 Visio Visual Verification Preview\n\nClick 'Convert to Visio' to generate\nyour diagram and see the live preview.",
        "preview_status_empty": "Visual Verification: No diagram generated yet.",
        "preview_status_loaded": "Visual Verification: {width}x{height} px ({size_kb} KB, {time_sec}s)",
        # Bottom Console
        "console_title": " Activity Log & Status Notifications ",
        "log_ready": "Application started. Ready.",
        "log_sample_loaded": "Sample template loaded: {name}",
        "log_markdown_extracted": "Extracted Mermaid code block from Markdown: {path}",
        "log_file_loaded": "File loaded: {path}",
        "log_file_saved": "Mermaid code saved: {path}",
        "log_turkish_detected": "Turkish Character Check: {total} Turkish characters detected ({chars}).",
        "log_step_1": "1/3 Parsing Mermaid code (building AST)...",
        "log_step_2": "2/3 Visio diagram generated: {name}",
        "log_step_3": "3/3 Rendering live visual preview...",
        "log_success": "✓ SUCCESS: Diagram saved and previewed ({engine})! ({width}x{height} px, {size_kb} KB, {time_sec}s)",
        "log_export_vsdx": "Exporting direct .vsdx without opening Visio: {name}...",
        "log_export_vsdx_success": "✓ Saved successfully (Visio not launched): {path}",
        "log_export_png_success": "✓ Image saved successfully: {path}",
        "log_visio_detected": "Microsoft Visio COM service detected: Version {ver}",
        "log_visio_independent_info": "Info: Microsoft Visio not found. All .vsdx files are generated 100% compliant using the built-in native engine.",
        "log_drawio_opened": "Draw.io Web opened in browser. Drag and drop the generated .vsdx file to view and edit for free.",
        "log_lang_changed": "Interface language set to English (USA).",
        # Messages & Dialogs
        "warn_title": "Warning",
        "error_title": "Error",
        "success_title": "Success",
        "warn_no_code": "Please enter the Mermaid code to convert.",
        "warn_no_preview": "No preview image found to export. Please convert first.",
        "vsdx_exported_msg": "Visio (.vsdx) file saved successfully:\n\n{path}",
        "png_exported_msg": "Diagram image saved successfully:\n\n{path}",
        "non_visio_dialog_title": "View Visio Diagram",
        "non_visio_dialog_msg": (
            "Microsoft Visio is not installed on this system.\n\n"
            "• [Yes]: Open file with system default application (Draw.io, LibreOffice, etc.)\n"
            "• [No]: Open free Draw.io Web viewer in browser (you can drag & drop the vsdx file)\n"
            "• [Cancel]: Show file location in Windows Explorer"
        ),
    }
}


class I18n:
    """
    Localization manager holding the current active locale.
    """
    def __init__(self, default_lang: str = DEFAULT_LANGUAGE):
        self.current_lang = default_lang if default_lang in TRANSLATIONS else DEFAULT_LANGUAGE

    def set_language(self, lang_code: str):
        if lang_code in TRANSLATIONS:
            self.current_lang = lang_code

    def get(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS.get(self.current_lang, {}).get(key)
        if text is None:
            text = TRANSLATIONS.get("en", {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def __call__(self, key: str, **kwargs) -> str:
        return self.get(key, **kwargs)
