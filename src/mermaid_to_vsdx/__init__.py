"""
Mermaid to Microsoft Visio (.vsdx) Converter.
Provides high-level diagram compilation and verification APIs.
"""

from .visio import convert_mermaid_to_visio, DEFAULT_PALETTE_NAME, PALETTES
from .compiler import compile_mermaid_to_vsdx
from .parser import parse_mermaid, extract_mermaid_from_markdown, DiagramType

__version__ = "1.0.0"

__all__ = [
    "convert_mermaid_to_visio",
    "compile_mermaid_to_vsdx",
    "parse_mermaid",
    "extract_mermaid_from_markdown",
    "DiagramType",
    "DEFAULT_PALETTE_NAME",
    "PALETTES",
    "__version__",
]
