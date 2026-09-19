"""
Native Headless Mermaid to Visio (.vsdx) Compiler Package.
Translates Mermaid text directly into Open Packaging Conventions (OPC) XML ZIP packages
without requiring Microsoft Visio or Windows COM Interop.
"""

from typing import Tuple
from ..parser import parse_mermaid, DiagramType
from ..visio.palettes import DEFAULT_PALETTE_NAME
from .flowchart_compiler import compile_flowchart_to_vsdx
from .sequence_compiler import compile_sequence_to_vsdx
from .class_compiler import compile_class_diagram_to_vsdx
from .state_compiler import compile_state_diagram_to_vsdx
from .er_compiler import compile_er_diagram_to_vsdx


def compile_mermaid_to_vsdx(
    mermaid_code: str,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI"
) -> Tuple[DiagramType, str]:
    """
    Directly compiles Mermaid diagram text into a native Microsoft Visio (.vsdx) file.
    Runs 100% headless and cross-platform (Linux, macOS, Windows) with ZERO external dependencies.
    """
    dtype, ast = parse_mermaid(mermaid_code)

    if dtype == DiagramType.FLOWCHART:
        path = compile_flowchart_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.SEQUENCE:
        path = compile_sequence_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.CLASS_DIAGRAM:
        path = compile_class_diagram_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.STATE_DIAGRAM:
        path = compile_state_diagram_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.ER_DIAGRAM:
        path = compile_er_diagram_to_vsdx(ast, output_path, palette_name, font_name)
    else:
        raise ValueError(f"Unsupported diagram type for native compilation: {dtype}")

    return dtype, path


__all__ = [
    "compile_mermaid_to_vsdx",
    "compile_flowchart_to_vsdx",
    "compile_sequence_to_vsdx",
    "compile_class_diagram_to_vsdx",
    "compile_state_diagram_to_vsdx",
    "compile_er_diagram_to_vsdx",
]
