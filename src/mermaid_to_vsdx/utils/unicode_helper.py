"""
Unicode and Turkish character handling utilities.
Guarantees 100% fidelity for Turkish characters (ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü)
and safe formatting for Visio ShapeSheet and text elements.
"""

import re
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


def has_bold_markup(raw_text: str) -> bool:
    """Returns True if raw_text contains <b>, <strong>, or **bold** markup."""
    if not raw_text:
        return False
    if re.search(r"<\s*(b|strong)\b[^>]*>", raw_text, re.IGNORECASE):
        return True
    if re.search(r"\*\*[^*]+\*\*", raw_text):
        return True
    return False


def clean_label_text(raw_text: str) -> str:
    """
    Clean up label text from Mermaid syntax:
    - Strips surrounding quotes (single or double) and Markdown string backticks ("`...`")
    - Unescapes common Mermaid HTML entities like <br/> to newlines
    - Strips inline HTML formatting tags (<b>, <i>, <u>, <small>, <span>, etc.)
    - Strips Markdown **bold** and *italic* markers
    - Strips leading and trailing whitespace while preserving internal formatting
    """
    if not raw_text:
        return ""

    text = ensure_utf8(raw_text.strip())

    # Strip quotes if wrapped
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    # Strip Markdown string backticks (`...`)
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        text = text[1:-1].strip()

    # Replace HTML line breaks (<br>, <br/>, <br />) case-insensitively with standard newlines
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)

    # Strip common inline HTML formatting tags (<b>, </b>, <i>, </i>, <u>, <strong>, <em>, <small>, <sub/>, <sup/>)
    text = re.sub(r"</?\s*(b|i|u|strong|em|small|sub|sup|span|font)\b[^>]*>", "", text, flags=re.IGNORECASE)

    # Strip Markdown bold/italic (**text** or __text__)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)

    # Handle HTML entity escapes
    text = (
        text.replace("&quot;", '"')
        .replace("&#34;", '"')
        .replace("&apos;", "'")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
    )

    return text.strip()


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
