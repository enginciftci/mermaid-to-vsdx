"""
Mermaid Quadrant Chart Parser.
Parses `quadrantChart` definitions with axis labels, 4 quadrant titles, and [x, y] data points.
"""

import re
from .ast_nodes import QuadrantDiagram, QuadrantPoint
from .base_parser import MermaidParseError, preprocess_lines


_AXIS_RE = re.compile(r"^(?P<axis>[xy]-axis)\s+(?P<left>.+?)(?:\s*-+>\s*(?P<right>.+))?$", re.IGNORECASE)
_QUAD_RE = re.compile(r"^quadrant-(?P<num>[1-4])\s+(?P<label>.+)$", re.IGNORECASE)
_POINT_RE = re.compile(
    r"^(?P<label>.+?)\s*:\s*\[\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*\]",
    re.IGNORECASE,
)


def _strip_quotes(text: str) -> str:
    t = text.strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        t = t[1:-1]
    return t.strip()


class QuadrantParser:
    """Parser for Mermaid `quadrantChart` diagrams."""

    def parse(self, mermaid_code: str) -> QuadrantDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty quadrantChart diagram.")

        diagram = QuadrantDiagram()
        header_seen = False

        for line_num, line in lines:
            if not header_seen:
                if line.lower().startswith("quadrantchart"):
                    header_seen = True
                    continue
                else:
                    raise MermaidParseError("Expected 'quadrantChart' header.", line_num, line)

            low = line.lower()
            if low.startswith("title "):
                diagram.title = _strip_quotes(line[6:])
                continue

            m_axis = _AXIS_RE.match(line)
            if m_axis:
                axis_name = m_axis.group("axis").lower()
                left_val = _strip_quotes(m_axis.group("left") or "")
                right_val = _strip_quotes(m_axis.group("right") or "")
                if axis_name == "x-axis":
                    diagram.x_axis_left = left_val
                    if right_val:
                        diagram.x_axis_right = right_val
                else:
                    diagram.y_axis_bottom = left_val
                    if right_val:
                        diagram.y_axis_top = right_val
                continue

            m_quad = _QUAD_RE.match(line)
            if m_quad:
                q_num = m_quad.group("num")
                q_label = _strip_quotes(m_quad.group("label"))
                setattr(diagram, f"quadrant_{q_num}", q_label)
                continue

            m_pt = _POINT_RE.match(line)
            if m_pt:
                raw_label = m_pt.group("label").split(":::")[0]
                pt_label = _strip_quotes(raw_label)
                x_val = max(0.0, min(1.0, float(m_pt.group("x"))))
                y_val = max(0.0, min(1.0, float(m_pt.group("y"))))
                diagram.points.append(QuadrantPoint(label=pt_label, x=x_val, y=y_val))
                continue

            if low.startswith("classdef "):
                continue

        return diagram
