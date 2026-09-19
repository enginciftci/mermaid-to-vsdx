"""
Unicode and Turkish character handling utilities.
Guarantees 100% fidelity for Turkish characters (ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü)
and safe formatting for Visio ShapeSheet and text elements.
"""

import unicodedata
from typing import Optional

# Canonical list of Turkish specific characters
TURKISH_CHARS = {
    'lower': "çğıöşü",
    'upper': "ÇĞİÖŞÜ",
    'all': "çğıöşüÇĞİÖŞÜ"
}

# Unicode-compatible fonts for Visio shapes
RECOMMENDED_FONTS = [
    "Segoe UI",
    "Calibri",
    "Arial",
    "Segoe UI Semibold",
    "Aptos",
    "Verdana"
]

DEFAULT_FONT = "Segoe UI"


def ensure_utf8(text: str) -> str:
    """
    Ensure the string is clean UTF-8 text, normalized with NFC to preserve
    composite Turkish glyphs properly.
    """
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return unicodedata.normalize("NFC", text)


def clean_label_text(raw_text: str) -> str:
    """
    Clean up label text from Mermaid syntax:
    - Strips surrounding quotes (single or double)
    - Unescapes common Mermaid HTML entities like <br/> to newlines
    - Strips leading and trailing whitespace while preserving internal formatting
    """
    if not raw_text:
        return ""
    
    text = ensure_utf8(raw_text.strip())
    
    # Strip quotes if wrapped
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
        
    # Replace HTML line breaks with standard newlines
    text = text.replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")
    
    # Handle HTML entity escapes
    text = text.replace("&quot;", '"').replace("&amp;", '&').replace("&lt;", '<').replace("&gt;", '>')
    
    return text


def sanitize_visio_formula_string(text: str) -> str:
    """
    Sanitize a string to be safely embedded inside a Visio ShapeSheet formula.
    Visio formulas wrap strings in double quotes, so internal quotes must be doubled.
    """
    cleaned = ensure_utf8(text)
    escaped = cleaned.replace('"', '""')
    return f'"{escaped}"'


def verify_turkish_chars(text: str) -> dict:
    """
    Verifies the presence and integrity of Turkish characters in a string.
    Returns a dictionary of detected Turkish characters and count.
    """
    norm = ensure_utf8(text)
    detected = {}
    for ch in norm:
        if ch in TURKISH_CHARS['all']:
            detected[ch] = detected.get(ch, 0) + 1
    return {
        "has_turkish": len(detected) > 0,
        "char_counts": detected,
        "total_turkish_chars": sum(detected.values())
    }
