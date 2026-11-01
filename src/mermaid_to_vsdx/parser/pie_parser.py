"""
Mermaid Pie Chart Parser.
Parses `pie [showData] [title ...]` and `"Label" : value` slice declarations into PieDiagram AST.
"""

import re
from .ast_nodes import PieDiagram, PieSlice
from .base_parser import MermaidParseError, preprocess_lines


_HEADER_RE = re.compile(
    r"^pie(?:\s+(?P<show>showdata))?(?:\s+title\s+(?P<title>.+))?$",
    re.IGNORECASE,
)
_SLICE_RE = re.compile(
    r'^(?:"(?P<qlabel>[^"]+)"|\'(?P<slabel>[^\']+)\'|(?P<ulabel>[^:]+?))\s*:\s*(?P<val>-?\d+(?:\.\d+)?)\s*$'
)


class PieParser:
    """Parser for Mermaid `pie` diagrams."""

    def parse(self, mermaid_code: str) -> PieDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty pie diagram.")

        diagram = PieDiagram()
        header_seen = False

        for line_num, line in lines:
            if not header_seen:
                m_hdr = _HEADER_RE.match(line)
                if m_hdr:
                    header_seen = True
                    if m_hdr.group("show"):
                        diagram.show_data = True
                    if m_hdr.group("title"):
                        diagram.title = m_hdr.group("title").strip().strip('"')
                    continue
                elif line.lower().startswith("pie"):
                    header_seen = True
                    rem = line[3:].strip()
                    if rem.lower().startswith("showdata"):
                        diagram.show_data = True
                        rem = rem[8:].strip()
                    if rem.lower().startswith("title "):
                        diagram.title = rem[6:].strip().strip('"')
                    elif rem:
                        diagram.title = rem.strip('"')
                    continue
                else:
                    raise MermaidParseError("Expected 'pie' header.", line_num, line)

            low = line.lower()
            if low == "showdata":
                diagram.show_data = True
                continue
            if low.startswith("title "):
                diagram.title = line[6:].strip().strip('"')
                continue

            m_slice = _SLICE_RE.match(line)
            if m_slice:
                lbl = (
                    m_slice.group("qlabel")
                    or m_slice.group("slabel")
                    or m_slice.group("ulabel")
                    or ""
                ).strip()
                val = float(m_slice.group("val"))
                if val > 0:
                    diagram.slices.append(PieSlice(label=lbl, value=val))
                continue

        return diagram
