"""
Native Headless Mermaid to Visio (.vsdx) Compiler Package.
Translates Mermaid text directly into Open Packaging Conventions (OPC) XML ZIP packages
without requiring Microsoft Visio or Windows COM Interop.
Supports 11 Mermaid diagram types and multi-page Markdown compilation.
"""

import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple
from ..parser import parse_mermaid, DiagramType, extract_all_mermaid_from_markdown
from ..visio.palettes import DEFAULT_PALETTE_NAME
from .flowchart_compiler import compile_flowchart_to_vsdx
from .sequence_compiler import compile_sequence_to_vsdx
from .class_compiler import compile_class_diagram_to_vsdx
from .state_compiler import compile_state_diagram_to_vsdx
from .er_compiler import compile_er_diagram_to_vsdx
from .block_compiler import compile_block_to_vsdx
from .mindmap_compiler import compile_mindmap_to_vsdx
from .timeline_compiler import compile_timeline_to_vsdx
from .quadrant_compiler import compile_quadrant_to_vsdx
from .pie_compiler import compile_pie_to_vsdx
from .gantt_compiler import compile_gantt_to_vsdx
from .opc_package import package_multipage_vsdx


def _compile_single_mermaid_to_vsdx(
    mermaid_code: str,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> Tuple[DiagramType, str]:
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
    elif dtype == DiagramType.BLOCK:
        path = compile_block_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.MINDMAP:
        path = compile_mindmap_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.TIMELINE:
        path = compile_timeline_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.QUADRANT:
        path = compile_quadrant_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.PIE:
        path = compile_pie_to_vsdx(ast, output_path, palette_name, font_name)
    elif dtype == DiagramType.GANTT:
        path = compile_gantt_to_vsdx(ast, output_path, palette_name, font_name)
    else:
        raise ValueError(f"Unsupported diagram type for native compilation: {dtype}")

    return dtype, path


def _extract_page_payload(vsdx_path: str) -> Dict:
    """Extracts shapes_xml, connects_xml, page_width, and page_height from a single-page .vsdx."""
    with zipfile.ZipFile(vsdx_path, "r") as zf:
        page1_xml = zf.read("visio/pages/page1.xml").decode("utf-8")
        pages_xml = zf.read("visio/pages/pages.xml").decode("utf-8")

    m_shapes = re.search(r"<Shapes>(.*)</Shapes>", page1_xml, re.DOTALL)
    shapes_xml = m_shapes.group(1).strip() if m_shapes else ""

    m_conns = re.search(r"<Connects>(.*)</Connects>", page1_xml, re.DOTALL)
    connects_xml = m_conns.group(1).strip() if m_conns else ""

    ns = {"v": "http://schemas.microsoft.com/office/visio/2012/main"}
    root = ET.fromstring(pages_xml)
    w_cell = root.find(".//v:Cell[@N='PageWidth']", ns)
    h_cell = root.find(".//v:Cell[@N='PageHeight']", ns)
    page_w = float(w_cell.attrib["V"]) if w_cell is not None else 11.0
    page_h = float(h_cell.attrib["V"]) if h_cell is not None else 8.5

    return {
        "shapes_xml": shapes_xml,
        "connects_xml": connects_xml,
        "page_width": page_w,
        "page_height": page_h,
    }


def compile_mermaid_to_vsdx(
    mermaid_code: str,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> Tuple[DiagramType, str]:
    """
    Directly compiles Mermaid diagram text (or a Markdown document with one or more ```mermaid blocks)
    into a native Microsoft Visio (.vsdx) file.
    If multiple ```mermaid blocks exist in a Markdown document, compiles all of them into a multi-page .vsdx!
    """
    blocks = extract_all_mermaid_from_markdown(mermaid_code)
    if len(blocks) <= 1:
        return _compile_single_mermaid_to_vsdx(mermaid_code, output_path, palette_name, font_name)

    pages_data: List[Dict] = []
    first_dtype = DiagramType.UNKNOWN
    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, (title, block_code) in enumerate(blocks):
            tmp_vsdx = os.path.join(tmp_dir, f"page_{idx + 1}.vsdx")
            dtype, _ = _compile_single_mermaid_to_vsdx(block_code, tmp_vsdx, palette_name, font_name)
            if idx == 0:
                first_dtype = dtype
            payload = _extract_page_payload(tmp_vsdx)
            payload["title"] = title
            pages_data.append(payload)

    final_path = package_multipage_vsdx(output_path, pages_data)
    return first_dtype, final_path


__all__ = [
    "compile_mermaid_to_vsdx",
    "compile_flowchart_to_vsdx",
    "compile_sequence_to_vsdx",
    "compile_class_diagram_to_vsdx",
    "compile_state_diagram_to_vsdx",
    "compile_er_diagram_to_vsdx",
    "compile_block_to_vsdx",
    "compile_mindmap_to_vsdx",
    "compile_timeline_to_vsdx",
    "compile_quadrant_to_vsdx",
    "compile_pie_to_vsdx",
    "compile_gantt_to_vsdx",
]
