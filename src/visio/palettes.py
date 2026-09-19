"""
Professional Color Palettes for Microsoft Visio Diagrams.
Provides harmonious fills, borders, text colors, and connector styles.
"""

import re
from dataclasses import dataclass
from typing import Dict, Tuple


def parse_color_rgb(color_str: str) -> Tuple[int, int, int]:
    """Extracts (r, g, b) tuple from 'RGB(r, g, b)', '#RRGGBB', or named colors."""
    if not color_str:
        return 255, 255, 255
    color_str = color_str.strip()
    m = re.search(r"RGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    if color_str.startswith("#"):
        c = color_str.lstrip("#")
        if len(c) == 3:
            return int(c[0] * 2, 16), int(c[1] * 2, 16), int(c[2] * 2, 16)
        if len(c) >= 6:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    named = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "charcoal": (80, 80, 80),
        "darkgray": (60, 60, 60),
        "dimgray": (105, 105, 105),
        "gray": (128, 128, 128),
    }
    return named.get(color_str.lower(), (0, 0, 0))


def is_dark_color(color_str: str) -> bool:
    """
    Returns True if the color has low perceived luminance (< 135), meaning it is black or dark.
    Perceived brightness = 0.299*R + 0.587*G + 0.114*B (ITU-R BT.601 standard).
    """
    if not color_str:
        return False
    r, g, b = parse_color_rgb(color_str)
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    return brightness < 135


def get_contrasting_text_color(background_color: str, default_text_color: str = "#000000") -> str:
    """
    Returns '#ffffff' if background is black or dark, otherwise returns default_text_color.
    """
    if is_dark_color(background_color):
        return "#ffffff"
    return default_text_color


@dataclass
class PaletteTheme:
    name: str
    background: str           # Page background / canvas
    default_fill: str         # Standard node fill
    default_border: str       # Standard node border
    default_text: str         # Standard text color
    decision_fill: str        # Diamond / decision fill
    decision_border: str      # Diamond / decision border
    terminal_fill: str        # Start / End / Stadium fill
    terminal_border: str      # Start / End border
    database_fill: str        # Cylinder / database fill
    database_border: str      # Cylinder border
    subgraph_fill: str        # Container fill
    subgraph_border: str      # Container border
    subgraph_text: str        # Container title color
    connector_line: str       # Arrow line color
    connector_text: str       # Edge label color
    note_fill: str            # Sequence note fill
    note_border: str          # Sequence note border
    note_text: str            # Sequence note text


PALETTES: Dict[str, PaletteTheme] = {
    "Modern Corporate (Blue & Slate)": PaletteTheme(
        name="Modern Corporate",
        background="RGB(255, 255, 255)",
        default_fill="RGB(239, 246, 255)",        # Soft Sky Blue
        default_border="RGB(59, 130, 246)",       # Tailwind Blue 500
        default_text="RGB(30, 41, 59)",           # Slate 800
        decision_fill="RGB(254, 243, 199)",       # Soft Amber
        decision_border="RGB(245, 158, 11)",      # Amber 500
        terminal_fill="RGB(236, 253, 245)",       # Soft Emerald
        terminal_border="RGB(16, 185, 129)",      # Emerald 500
        database_fill="RGB(243, 232, 255)",       # Soft Purple
        database_border="RGB(168, 85, 247)",      # Purple 500
        subgraph_fill="RGB(248, 250, 252)",       # Slate 50
        subgraph_border="RGB(203, 213, 225)",     # Slate 300
        subgraph_text="RGB(71, 85, 105)",         # Slate 600
        connector_line="RGB(71, 85, 105)",        # Slate 600
        connector_text="RGB(15, 23, 42)",         # Slate 900
        note_fill="RGB(254, 249, 195)",           # Pale Yellow
        note_border="RGB(234, 179, 8)",           # Yellow 500
        note_text="RGB(113, 63, 18)"              # Warm Brown
    ),
    "Emerald Tech (Mint & Teal)": PaletteTheme(
        name="Emerald Tech",
        background="RGB(255, 255, 255)",
        default_fill="RGB(240, 253, 250)",        # Mint 50
        default_border="RGB(20, 184, 166)",       # Teal 500
        default_text="RGB(19, 78, 74)",           # Teal 900
        decision_fill="RGB(255, 251, 235)",       # Warm Sand
        decision_border="RGB(217, 119, 6)",       # Amber 600
        terminal_fill="RGB(236, 253, 245)",       # Emerald 50
        terminal_border="RGB(5, 150, 105)",       # Emerald 600
        database_fill="RGB(240, 249, 255)",       # Sky 50
        database_border="RGB(2, 132, 199)",       # Sky 600
        subgraph_fill="RGB(248, 250, 252)",
        subgraph_border="RGB(148, 163, 184)",
        subgraph_text="RGB(51, 65, 85)",
        connector_line="RGB(15, 118, 110)",       # Deep Teal
        connector_text="RGB(19, 78, 74)",
        note_fill="RGB(254, 243, 199)",
        note_border="RGB(245, 158, 11)",
        note_text="RGB(120, 53, 15)"
    ),
    "Sunset Coral & Violet": PaletteTheme(
        name="Sunset Coral",
        background="RGB(255, 255, 255)",
        default_fill="RGB(255, 241, 242)",        # Rose 50
        default_border="RGB(244, 63, 94)",        # Rose 500
        default_text="RGB(76, 5, 25)",            # Rose 950
        decision_fill="RGB(254, 242, 242)",       # Red 50
        decision_border="RGB(239, 68, 68)",       # Red 500
        terminal_fill="RGB(255, 247, 237)",       # Orange 50
        terminal_border="RGB(249, 115, 22)",      # Orange 500
        database_fill="RGB(250, 245, 255)",       # Purple 50
        database_border="RGB(168, 85, 247)",      # Purple 500
        subgraph_fill="RGB(255, 251, 235)",
        subgraph_border="RGB(253, 186, 116)",
        subgraph_text="RGB(154, 52, 18)",
        connector_line="RGB(159, 18, 57)",        # Rose 800
        connector_text="RGB(76, 5, 25)",
        note_fill="RGB(254, 240, 138)",
        note_border="RGB(202, 138, 4)",
        note_text="RGB(113, 63, 18)"
    ),
    "Minimalist Slate (Dark / Steel)": PaletteTheme(
        name="Minimalist Slate",
        background="RGB(255, 255, 255)",
        default_fill="RGB(248, 250, 252)",        # Slate 50
        default_border="RGB(71, 85, 105)",        # Slate 600
        default_text="RGB(15, 23, 42)",           # Slate 900
        decision_fill="RGB(241, 245, 249)",       # Slate 100
        decision_border="RGB(51, 65, 85)",        # Slate 700
        terminal_fill="RGB(226, 232, 240)",       # Slate 200
        terminal_border="RGB(30, 41, 59)",        # Slate 800
        database_fill="RGB(241, 245, 249)",
        database_border="RGB(51, 65, 85)",
        subgraph_fill="RGB(255, 255, 255)",
        subgraph_border="RGB(148, 163, 184)",
        subgraph_text="RGB(71, 85, 105)",
        connector_line="RGB(30, 41, 59)",         # Slate 800
        connector_text="RGB(15, 23, 42)",
        note_fill="RGB(254, 249, 195)",
        note_border="RGB(161, 98, 7)",
        note_text="RGB(66, 32, 6)"
    ),
    "Grayscale Clean (Black & White)": PaletteTheme(
        name="Grayscale Clean",
        background="RGB(255, 255, 255)",
        default_fill="RGB(255, 255, 255)",        # Pure White
        default_border="RGB(0, 0, 0)",             # Solid Black
        default_text="RGB(0, 0, 0)",               # True Black
        decision_fill="RGB(245, 245, 245)",        # 5% Light Gray
        decision_border="RGB(0, 0, 0)",            # Crisp Black
        terminal_fill="RGB(230, 230, 230)",        # 10% Gray
        terminal_border="RGB(0, 0, 0)",            # Crisp Black
        database_fill="RGB(240, 240, 240)",        # Soft Gray
        database_border="RGB(0, 0, 0)",            # Crisp Black
        subgraph_fill="RGB(255, 255, 255)",        # Pure White Container
        subgraph_border="RGB(80, 80, 80)",         # Charcoal Border
        subgraph_text="RGB(255, 255, 255)",        # Pure White Title for Charcoal/Black Header
        connector_line="RGB(0, 0, 0)",             # Solid Black
        connector_text="RGB(0, 0, 0)",             # Crisp Black
        note_fill="RGB(245, 245, 245)",            # Very Light Gray
        note_border="RGB(0, 0, 0)",                # Solid Black
        note_text="RGB(0, 0, 0)"                   # Solid Black
    )
}

DEFAULT_PALETTE_NAME = "Modern Corporate (Blue & Slate)"


def get_palette(name: str = DEFAULT_PALETTE_NAME) -> PaletteTheme:
    return PALETTES.get(name, PALETTES[DEFAULT_PALETTE_NAME])


__all__ = [
    "PaletteTheme",
    "PALETTES",
    "DEFAULT_PALETTE_NAME",
    "get_palette",
    "parse_color_rgb",
    "is_dark_color",
    "get_contrasting_text_color",
]
