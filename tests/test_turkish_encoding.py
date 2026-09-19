"""
Unit tests for Turkish character support, unicode preservation, and sanitization.
"""

import unittest
from src.utils.unicode_helper import (
    ensure_utf8, clean_label_text, sanitize_visio_formula_string,
    verify_turkish_chars, TURKISH_CHARS
)


class TestTurkishEncoding(unittest.TestCase):

    def test_all_turkish_characters_presence(self):
        sample = "Türkçe Karakter Seti: ç, ğ, ı, ö, ş, ü / Ç, Ğ, İ, Ö, Ş, Ü"
        result = verify_turkish_chars(sample)
        self.assertTrue(result["has_turkish"])
        # Ensure all 12 characters are recognized
        for ch in TURKISH_CHARS["all"]:
            self.assertIn(ch, result["char_counts"], f"Character '{ch}' not detected in result.")

    def test_utf8_normalization(self):
        raw = "Öğretmen İletişimi"
        norm = ensure_utf8(raw)
        self.assertEqual(norm, raw)

    def test_clean_label_text(self):
        self.assertEqual(clean_label_text('"Tırnak İçi Metin"'), "Tırnak İçi Metin")
        self.assertEqual(clean_label_text("'Tek Tırnak'"), "Tek Tırnak")
        self.assertEqual(clean_label_text("Satır 1<br/>Satır 2"), "Satır 1\nSatır 2")
        self.assertEqual(clean_label_text("Kullanıcı &amp; Şifre"), "Kullanıcı & Şifre")

    def test_visio_formula_sanitization(self):
        text = 'Özel "Kampanya" Şartları'
        formula_str = sanitize_visio_formula_string(text)
        self.assertEqual(formula_str, '"Özel ""Kampanya"" Şartları"')


if __name__ == "__main__":
    unittest.main()
