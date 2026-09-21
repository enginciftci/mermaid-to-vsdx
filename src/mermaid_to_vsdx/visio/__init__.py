"""
Visio Generation Engine Package.
Provides high-level converter interface to turn Mermaid code into .vsdx drawings.
"""

from typing import Optional, Tuple
from ..parser import parse_mermaid, DiagramType, MermaidParseError
from .com_client import VisioSession, is_visio_installed, get_visio_version, open_in_visio
from .palettes import get_palette, PALETTES, DEFAULT_PALETTE_NAME, PaletteTheme
from .flowchart_builder import FlowchartBuilder
from .sequence_builder import SequenceBuilder
from .class_builder import ClassBuilder
from ..utils.unicode_helper import DEFAULT_FONT


def convert_mermaid_to_visio(
    mermaid_code: str,
    output_vsdx_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = DEFAULT_FONT,
    engine: str = "native"
) -> Tuple[DiagramType, str]:
    """
    Parses Mermaid code (or Markdown containing Mermaid blocks) and renders it into a Microsoft Visio (.vsdx) file.
    Supports:
    - engine='native' (default): Pure headless Open Packaging Conventions compiler. Zero external dependencies.
    - engine='com': Windows COM Interop automation via local Microsoft Visio desktop.
    """
    if engine == "native" or not is_visio_installed():
        from ..compiler import compile_mermaid_to_vsdx
        return compile_mermaid_to_vsdx(
            mermaid_code=mermaid_code,
            output_path=output_vsdx_path,
            palette_name=palette_name,
            font_name=font_name
        )

    if not is_visio_installed():
        raise RuntimeError("Microsoft Visio installation could not be detected on this system.")

    diag_type, ast = parse_mermaid(mermaid_code)
    palette = get_palette(palette_name)

    if diag_type == DiagramType.FLOWCHART:
        builder = FlowchartBuilder(ast, palette=palette, font_name=font_name)
        path = builder.build_and_save(output_vsdx_path)
        return diag_type, path
    elif diag_type == DiagramType.SEQUENCE:
        builder = SequenceBuilder(ast, palette=palette, font_name=font_name)
        path = builder.build_and_save(output_vsdx_path)
        return diag_type, path
    elif diag_type == DiagramType.CLASS_DIAGRAM:
        builder = ClassBuilder(ast, palette=palette, font_name=font_name)
        path = builder.build_and_save(output_vsdx_path)
        return diag_type, path
    elif diag_type in (DiagramType.STATE_DIAGRAM, DiagramType.ER_DIAGRAM, DiagramType.BLOCK):
        from ..compiler import compile_mermaid_to_vsdx
        return compile_mermaid_to_vsdx(
            mermaid_code=mermaid_code,
            output_path=output_vsdx_path,
            palette_name=palette_name,
            font_name=font_name
        )
    else:
        raise MermaidParseError("Unsupported diagram type for Visio conversion.")


__all__ = [
    "convert_mermaid_to_visio",
    "VisioSession",
    "is_visio_installed",
    "get_visio_version",
    "open_in_visio",
    "get_palette",
    "PALETTES",
    "DEFAULT_PALETTE_NAME",
    "FlowchartBuilder",
    "SequenceBuilder",
    "ClassBuilder",
]
