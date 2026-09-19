"""
Headless typographical sizing heuristics.
Estimates bounding box dimensions for text elements without browser DOM or native font engines.
"""

from typing import Tuple, List

# Character width weights (in points at 10pt base font)
CHAR_WIDTH_WEIGHTS = {
    # Narrow characters
    'i': 3.2, 'l': 3.2, 't': 4.0, 'j': 3.5, 'f': 4.0, 'r': 4.5,
    'I': 3.5, '!': 3.5, '.': 3.0, ',': 3.0, ':': 3.0, ';': 3.0,
    "'": 2.5, '"': 4.5, '|': 3.0, '/': 4.5, '\\': 4.5, '-': 4.5,
    '(': 4.0, ')': 4.0, '[': 4.0, ']': 4.0, '{': 4.0, '}': 4.0,
    'ı': 3.2, 'İ': 3.5,
    # Wide characters
    'm': 11.0, 'w': 10.5, 'M': 11.5, 'W': 12.0, '%': 11.0, '@': 12.0,
    '#': 8.0, '&': 9.0,
    # Uppercase & digits
    'A': 8.5, 'B': 8.0, 'C': 8.5, 'D': 8.5, 'E': 8.0, 'F': 7.5,
    'G': 9.0, 'H': 8.5, 'J': 6.0, 'K': 8.0, 'L': 7.0, 'N': 8.5,
    'O': 9.0, 'P': 8.0, 'Q': 9.0, 'R': 8.0, 'S': 7.5, 'T': 7.5,
    'U': 8.5, 'V': 8.0, 'X': 8.0, 'Y': 7.5, 'Z': 7.5,
    '0': 7.5, '1': 6.5, '2': 7.5, '3': 7.5, '4': 7.5, '5': 7.5,
    '6': 7.5, '7': 7.5, '8': 7.5, '9': 7.5,
    'Ç': 8.5, 'Ğ': 9.0, 'Ö': 9.0, 'Ş': 7.5, 'Ü': 8.5,
    # Turkish lowercase
    'ç': 7.2, 'ğ': 7.5, 'ö': 7.5, 'ş': 7.0, 'ü': 7.2,
    # Space
    ' ': 4.0,
}

DEFAULT_CHAR_WIDTH = 7.0


def estimate_line_width_pt(line: str, font_size_pt: float = 10.0, bold: bool = False) -> float:
    """Calculates width in points for a single line of text."""
    scale = font_size_pt / 10.0
    total_pt = 0.0
    for ch in line:
        total_pt += CHAR_WIDTH_WEIGHTS.get(ch, DEFAULT_CHAR_WIDTH) * scale
    if bold:
        total_pt *= 1.08
    return total_pt


def estimate_text_dimensions(
    text: str,
    font_size_pt: float = 10.0,
    padding_x_in: float = 0.35,
    padding_y_in: float = 0.25,
    min_width_in: float = 1.6,
    min_height_in: float = 0.75,
) -> Tuple[float, float, List[str]]:
    """
    Estimates physical bounding box dimensions (in inches) for a given text block.
    Supports newline and '<br>' line breaks.
    """
    normalized_text = text.replace("<br/>", "\n").replace("<br>", "\n").replace("\\n", "\n")
    lines = [line.strip() for line in normalized_text.split("\n")]
    if not lines or (len(lines) == 1 and not lines[0]):
        lines = [" "]

    max_line_width_pt = max(estimate_line_width_pt(l, font_size_pt) for l in lines)
    # 72 points = 1 inch
    text_width_in = max_line_width_pt / 72.0
    
    # Line height: 1.35x font size
    line_height_pt = font_size_pt * 1.35
    total_text_height_pt = len(lines) * line_height_pt
    text_height_in = total_text_height_pt / 72.0

    total_width_in = max(min_width_in, text_width_in + padding_x_in * 2)
    total_height_in = max(min_height_in, text_height_in + padding_y_in * 2)

    return (round(total_width_in, 3), round(total_height_in, 3), lines)
