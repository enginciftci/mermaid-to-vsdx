"""
Visio 2013+ ShapeSheet XML generator.
Builds parametric 2D shapes, subgraph containers, 1D dynamic connectors, and <Connects> topologies.
"""

import html
import re
from typing import Dict, List, Optional, Tuple
from ..visio.palettes import is_dark_color


def rgb_to_hex(color_str: str) -> str:
    """Converts 'RGB(r, g, b)' or '#RRGGBB' to standard hex '#RRGGBB' for Visio ShapeSheet."""
    if not color_str:
        return "#000000"
    if color_str.startswith("#"):
        return color_str
    m = re.search(r"RGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_str, re.IGNORECASE)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return color_str


def escape_xml(text: str) -> str:
    """Escapes string content for Visio XML elements."""
    if not text:
        return ""
    # Visio XML text requires standard XML escaping
    return html.escape(text, quote=True).replace("\n", "\n")


def build_cell(name: str, val: str, formula: Optional[str] = None, unit: Optional[str] = None) -> str:
    """Renders a single ShapeSheet <Cell> element."""
    escaped_val = escape_xml(val)
    attrs = [f"N='{name}'", f"V='{escaped_val}'"]
    if formula:
        escaped_formula = escape_xml(formula)
        attrs.append(f"F='{escaped_formula}'")
    if unit:
        attrs.append(f"U='{unit}'")
    return f"<Cell {' '.join(attrs)}/>"


def calculate_connector_endpoints_and_ports(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    dst_x: float,
    dst_y: float,
    dst_w: float,
    dst_h: float,
    direction: str = "TD",
) -> Tuple[float, float, float, float, str, str, int, int]:
    """
    Computes connector begin/end coordinates clamped to the bounding perimeters
    of the source and destination shapes, along with the corresponding connection
    port names ("Top", "Bottom", "Left", "Right") and Visio part indices (100, 101, 102, 103).

    Returns:
        (begin_x, begin_y, end_x, end_y, src_port, dst_port, src_part, dst_part)
    """
    dx = dst_x - src_x
    dy = dst_y - src_y
    d = (direction or "TD").upper()

    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        # Self-loop fallback
        return (
            round(src_x + src_w * 0.5, 4),
            round(src_y, 4),
            round(src_x + src_w * 0.5 + 0.5, 4),
            round(src_y + 0.5, 4),
            "Right",
            "Top",
            103,
            100,
        )

    if d in ("LR", "RL"):
        # Horizontal layout
        if d == "LR":
            if dx > 0.1:
                # Forward: Right of source -> Left of destination
                return (
                    round(src_x + src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x - dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Right",
                    "Left",
                    103,
                    102,
                )
            elif dx < -0.1:
                # Feedback loop to earlier column: Bottom -> Bottom
                return (
                    round(src_x, 4),
                    round(src_y - src_h * 0.5, 4),
                    round(dst_x, 4),
                    round(dst_y - dst_h * 0.5, 4),
                    "Bottom",
                    "Bottom",
                    101,
                    101,
                )
            else:
                # Same column in horizontal diagram (vertical branch)
                if dy < 0:
                    return (
                        round(src_x, 4),
                        round(src_y - src_h * 0.5, 4),
                        round(dst_x, 4),
                        round(dst_y + dst_h * 0.5, 4),
                        "Bottom",
                        "Top",
                        101,
                        100,
                    )
                else:
                    return (
                        round(src_x, 4),
                        round(src_y + src_h * 0.5, 4),
                        round(dst_x, 4),
                        round(dst_y - dst_h * 0.5, 4),
                        "Top",
                        "Bottom",
                        100,
                        101,
                    )
        else:  # RL
            if dx < -0.1:
                # Forward: Left of source -> Right of destination
                return (
                    round(src_x - src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x + dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Left",
                    "Right",
                    102,
                    103,
                )
            elif dx > 0.1:
                # Feedback loop: Bottom -> Bottom
                return (
                    round(src_x, 4),
                    round(src_y - src_h * 0.5, 4),
                    round(dst_x, 4),
                    round(dst_y - dst_h * 0.5, 4),
                    "Bottom",
                    "Bottom",
                    101,
                    101,
                )
            else:
                if dy < 0:
                    return (
                        round(src_x, 4),
                        round(src_y - src_h * 0.5, 4),
                        round(dst_x, 4),
                        round(dst_y + dst_h * 0.5, 4),
                        "Bottom",
                        "Top",
                        101,
                        100,
                    )
                else:
                    return (
                        round(src_x, 4),
                        round(src_y + src_h * 0.5, 4),
                        round(dst_x, 4),
                        round(dst_y - dst_h * 0.5, 4),
                        "Top",
                        "Bottom",
                        100,
                        101,
                    )

    elif d == "BT":
        # Bottom-to-Top vertical layout
        if dy > 0.1:
            # Forward: Top of source -> Bottom of destination
            return (
                round(src_x, 4),
                round(src_y + src_h * 0.5, 4),
                round(dst_x, 4),
                round(dst_y - dst_h * 0.5, 4),
                "Top",
                "Bottom",
                100,
                101,
            )
        elif dy < -0.1:
            # Feedback: Right -> Right
            return (
                round(src_x + src_w * 0.5, 4),
                round(src_y, 4),
                round(dst_x + dst_w * 0.5, 4),
                round(dst_y, 4),
                "Right",
                "Right",
                103,
                103,
            )
        else:
            if dx > 0:
                return (
                    round(src_x + src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x - dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Right",
                    "Left",
                    103,
                    102,
                )
            else:
                return (
                    round(src_x - src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x + dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Left",
                    "Right",
                    102,
                    103,
                )

    else:
        # Default: TD / TB (Top-to-Bottom vertical layout)
        if dy < -0.1:
            # Forward downward: Bottom of source -> Top of destination
            return (
                round(src_x, 4),
                round(src_y - src_h * 0.5, 4),
                round(dst_x, 4),
                round(dst_y + dst_h * 0.5, 4),
                "Bottom",
                "Top",
                101,
                100,
            )
        elif dy > 0.1:
            # Upward feedback loop: Right of source -> Right of destination
            return (
                round(src_x + src_w * 0.5, 4),
                round(src_y, 4),
                round(dst_x + dst_w * 0.5, 4),
                round(dst_y, 4),
                "Right",
                "Right",
                103,
                103,
            )
        else:
            # Same rank (horizontal connection)
            if dx > 0:
                return (
                    round(src_x + src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x - dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Right",
                    "Left",
                    103,
                    102,
                )
            else:
                return (
                    round(src_x - src_w * 0.5, 4),
                    round(src_y, 4),
                    round(dst_x + dst_w * 0.5, 4),
                    round(dst_y, 4),
                    "Left",
                    "Right",
                    102,
                    103,
                )


def calculate_connector_endpoints(
    src_x: float,
    src_y: float,
    src_w: float,
    src_h: float,
    dst_x: float,
    dst_y: float,
    dst_w: float,
    dst_h: float,
) -> Tuple[float, float, float, float]:
    """
    Computes connector begin/end coordinates clamped to the bounding perimeters
    of the source and destination shapes.
    """
    bx, by, ex, ey, _, _, _, _ = calculate_connector_endpoints_and_ports(
        src_x, src_y, src_w, src_h, dst_x, dst_y, dst_w, dst_h
    )
    return bx, by, ex, ey


def get_shape_geometry_xml(shape_type: str, width: float, height: float, rounding_in: float = 0.0) -> str:
    """
    Returns parametric ShapeSheet <Section N='Geometry' IX='0'> XML for 14 standard node primitives.
    All vertices compute evaluated numeric V values so shapes render immediately upon opening
    without requiring external stencils, and retain F formulas so they scale dynamically when resized.
    """
    st = shape_type.lower()
    w1 = round(width, 4)
    w05 = round(width * 0.5, 4)
    h1 = round(height, 4)
    h05 = round(height * 0.5, 4)

    if st in ("diamond", "rhombus"):
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w05}' F='Width*0.5'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h05}' F='Height*0.5'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w05}' F='Width*0.5'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h05}' F='Height*0.5'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='{w05}' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("circle", "double_circle"):
        sec0 = f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='Ellipse' IX='1'>
    <Cell N='X' V='{w05}' F='Width*0.5'/><Cell N='Y' V='{h05}' F='Height*0.5'/>
    <Cell N='A' V='{w1}' F='Width*1'/><Cell N='B' V='{h05}' F='Height*0.5'/>
    <Cell N='C' V='{w05}' F='Width*0.5'/><Cell N='D' V='{h1}' F='Height*1'/>
  </Row>
</Section>"""
        if st == "double_circle":
            w08 = round(width * 0.8, 4)
            h08 = round(height * 0.8, 4)
            sec1 = f"""<Section N='Geometry' IX='1'>
  <Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='Ellipse' IX='1'>
    <Cell N='X' V='{w05}' F='Width*0.5'/><Cell N='Y' V='{h05}' F='Height*0.5'/>
    <Cell N='A' V='{w08}' F='Width*0.8'/><Cell N='B' V='{h05}' F='Height*0.5'/>
    <Cell N='C' V='{w05}' F='Width*0.5'/><Cell N='D' V='{h08}' F='Height*0.8'/>
  </Row>
</Section>"""
            return sec0 + "\n" + sec1
        return sec0

    elif st in ("cylinder", "database"):
        h_base = round(height * 0.14, 4)
        h_top = round(height * 0.86, 4)
        h_top_apex = round(height * 1.0, 4)
        h_top_lower = round(height * 0.72, 4)
        h_bot_curve = round(height * 0.0, 4)
        w05 = round(width * 0.5, 4)
        d_val = round((height * 0.14) / max(0.001, (width * 0.5)), 4)
        d_formula = "(Height*0.14)/(Width*0.5)"
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h_base}' F='Height*0.14'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h_top}' F='Height*0.86'/></Row>
  <Row T='EllipticalArcTo' IX='3'>
    <Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h_top}' F='Height*0.86'/>
    <Cell N='A' V='{w05}' F='Width*0.5'/><Cell N='B' V='{h_top_apex}' F='Height*1'/>
    <Cell N='C' V='0'/><Cell N='D' V='{d_val}' F='{d_formula}'/>
  </Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h_base}' F='Height*0.14'/></Row>
  <Row T='EllipticalArcTo' IX='5'>
    <Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h_base}' F='Height*0.14'/>
    <Cell N='A' V='{w05}' F='Width*0.5'/><Cell N='B' V='{h_bot_curve}' F='Height*0'/>
    <Cell N='C' V='0'/><Cell N='D' V='{d_val}' F='{d_formula}'/>
  </Row>
</Section>
<Section N='Geometry' IX='1'>
  <Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h_top}' F='Height*0.86'/></Row>
  <Row T='EllipticalArcTo' IX='2'>
    <Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h_top}' F='Height*0.86'/>
    <Cell N='A' V='{w05}' F='Width*0.5'/><Cell N='B' V='{h_top_lower}' F='Height*0.72'/>
    <Cell N='C' V='0'/><Cell N='D' V='{d_val}' F='{d_formula}'/>
  </Row>
</Section>"""

    elif st in ("subroutine",):
        w01 = round(width * 0.1, 4)
        w09 = round(width * 0.9, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>
<Section N='Geometry' IX='1'>
  <Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w01}' F='Width*0.1'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w01}' F='Width*0.1'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
</Section>
<Section N='Geometry' IX='2'>
  <Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w09}' F='Width*0.9'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w09}' F='Width*0.9'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
</Section>"""

    elif st in ("hexagon",):
        w02 = round(width * 0.2, 4)
        w08 = round(width * 0.8, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w02}' F='Width*0.2'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w08}' F='Width*0.8'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h05}' F='Height*0.5'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='{w08}' F='Width*0.8'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='{w02}' F='Width*0.2'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='6'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h05}' F='Height*0.5'/></Row>
  <Row T='LineTo' IX='7'><Cell N='X' V='{w02}' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("parallelogram_right", "parallelogram"):
        w022 = round(width * 0.22, 4)
        w078 = round(width * 0.78, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w022}' F='Width*0.22'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w078}' F='Width*0.78'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='{w022}' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("parallelogram_left",):
        w022 = round(width * 0.22, 4)
        w078 = round(width * 0.78, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w078}' F='Width*0.78'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='{w022}' F='Width*0.22'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("trapezoid",):
        w02 = round(width * 0.2, 4)
        w08 = round(width * 0.8, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w08}' F='Width*0.8'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='{w02}' F='Width*0.2'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("trapezoid_inverted",):
        w02 = round(width * 0.2, 4)
        w08 = round(width * 0.8, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='{w02}' F='Width*0.2'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w08}' F='Width*0.8'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='{w02}' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    elif st in ("asymmetric",):
        w085 = round(width * 0.85, 4)
        return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w085}' F='Width*0.85'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h05}' F='Height*0.5'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='{w085}' F='Width*0.85'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='6'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""

    # Default: Rectangle / Rounded / Stadium
    return f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  <Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='2'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='0' F='Height*0'/></Row>
  <Row T='LineTo' IX='3'><Cell N='X' V='{w1}' F='Width*1'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h1}' F='Height*1'/></Row>
  <Row T='LineTo' IX='5'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>
</Section>"""


def build_2d_shape_xml(
    shape_id: int,
    name: str,
    pin_x: float,
    pin_y: float,
    width: float,
    height: float,
    text: str,
    shape_type: str = "rectangle",
    fill_color: str = "#ecfdf5",
    line_color: str = "#10b981",
    text_color: str = "#1e293b",
    line_weight_in: float = 0.0208,
    line_pattern: int = 1,
    fill_pattern: int = 1,
    rounding_in: float = 0.0,
    font_name: str = "Segoe UI",
    font_size_pt: float = 10.0,
    align_left: bool = False,
    bold: bool = False,
    is_container: bool = False,
    has_connections: bool = True,
    extra_connections: Optional[List[Tuple[str, float, float, str, str]]] = None,
) -> str:
    """
    Renders a complete Visio 2D <Shape> XML element with parametric ShapeSheet cells.
    """
    escaped_text = escape_xml(text)
    horz_align = 0 if align_left else 1
    ind_first = 0.1 if align_left else 0.0

    fill_hex = rgb_to_hex(fill_color)
    line_hex = rgb_to_hex(line_color)
    text_hex = rgb_to_hex(text_color)
    st = shape_type.lower() if shape_type else "rectangle"
    txt_px = str(round(width * 0.44, 4)) if st in ("asymmetric",) else str(round(width * 0.5, 4))
    txt_px_f = "Width*0.44" if st in ("asymmetric",) else "Width*0.5"
    txt_py = str(round(height * 0.48, 4)) if st in ("cylinder", "database") else str(round(height * 0.5, 4))
    txt_py_f = "Height*0.48" if st in ("cylinder", "database") else "Height*0.5"

    cells = [
        build_cell("PinX", str(pin_x)),
        build_cell("PinY", str(pin_y)),
        build_cell("Width", str(width)),
        build_cell("Height", str(height)),
        build_cell("LocPinX", str(round(width * 0.5, 4)), "Width*0.5"),
        build_cell("LocPinY", str(round(height * 0.5, 4)), "Height*0.5"),
        build_cell("Angle", "0"),
        build_cell("FillPattern", str(fill_pattern)),
        build_cell("FillForegnd", fill_hex),
        build_cell("FillBkgnd", "#ffffff"),
        build_cell("LineWeight", str(line_weight_in), unit="PT"),
        build_cell("LineColor", line_hex),
        build_cell("LinePattern", str(line_pattern), f"GUARD({line_pattern})" if line_pattern != 1 else None),
        build_cell("Rounding", str(rounding_in), unit="IN"),
        build_cell("TextBkgnd", "0"),
        build_cell("TxtWidth", str(width), "Width*1"),
        build_cell("TxtHeight", str(height), "Height*1"),
        build_cell("TxtLocPinX", str(round(width * 0.5, 4)), "TxtWidth*0.5"),
        build_cell("TxtLocPinY", str(round(height * 0.5, 4)), "TxtHeight*0.5"),
        build_cell("TxtPinX", txt_px, txt_px_f),
        build_cell("TxtPinY", txt_py, txt_py_f),
        build_cell("TxtAngle", "0"),
        build_cell("ObjType", "1"),
    ]

    user_section = ""
    if is_container:
        user_section = """<Section N='User'><Row N='msvStructureType'><Cell N='Value' V='Container'/></Row></Section>"""

    font_style = "1" if bold else "0"
    char_section = f"""<Section N='Character'><Row IX='0'>
  <Cell N='Color' V='{text_hex}'/>
  <Cell N='Font' V='{font_name}'/>
  <Cell N='Size' V='{font_size_pt / 72.0}' U='IN'/>
  <Cell N='Style' V='{font_style}'/>
</Row></Section>"""

    para_section = f"""<Section N='Paragraph'><Row IX='0'>
  <Cell N='IndFirst' V='{ind_first}' U='IN'/>
  <Cell N='IndLeft' V='0' U='IN'/>
  <Cell N='IndRight' V='0' U='IN'/>
  <Cell N='HorzAlign' V='{horz_align}'/>
</Row></Section>"""

    conn_section = ""
    if has_connections:
        w_rnd = round(width, 4)
        w05_rnd = round(width * 0.5, 4)
        h_rnd = round(height, 4)
        h05_rnd = round(height * 0.5, 4)
        conn_rows = [
            f"<Row T='Connection' N='Top'><Cell N='X' V='{w05_rnd}' F='Width*0.5'/><Cell N='Y' V='{h_rnd}' F='Height*1'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Bottom'><Cell N='X' V='{w05_rnd}' F='Width*0.5'/><Cell N='Y' V='0' F='Height*0'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Left'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h05_rnd}' F='Height*0.5'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Right'><Cell N='X' V='{w_rnd}' F='Width*1'/><Cell N='Y' V='{h05_rnd}' F='Height*0.5'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
        ]
        if extra_connections:
            for c_name, c_x, c_y, c_xf, c_yf in extra_connections:
                conn_rows.append(
                    f"<Row T='Connection' N='{c_name}'><Cell N='X' V='{round(c_x, 4)}' F='{c_xf}'/><Cell N='Y' V='{round(c_y, 4)}' F='{c_yf}'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>"
                )
        conn_rows_str = "\n  ".join(conn_rows)
        conn_section = f"""<Section N='Connection'>
  {conn_rows_str}
</Section>"""

    geom_section = get_shape_geometry_xml(shape_type, width, height, rounding_in)

    text_element = f"<Text><cp IX='0'/><pp IX='0'/>{escaped_text}</Text>" if text else ""

    escaped_name = escape_xml(name)
    xml_lines = [
        f"<Shape ID='{shape_id}' NameU='{escaped_name}' Name='{escaped_name}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>",
        "\n".join(cells),
        user_section,
        conn_section,
        char_section,
        para_section,
        geom_section,
        text_element,
        "</Shape>"
    ]
    return "\n".join(x for x in xml_lines if x)


def build_group_shape_xml(
    group_id: int,
    name: str,
    pin_x: float,
    pin_y: float,
    width: float,
    height: float,
    child_shapes_xml: List[str],
    has_connections: bool = True,
    extra_connections: Optional[List[Tuple[str, float, float, str, str]]] = None,
) -> str:
    """
    Renders a Visio Group <Shape Type='Group'> XML element that encapsulates
    multiple child shapes (compartments, dividers, text) into a single movable,
    selectable unit with perimeter connection points.
    """
    w_rnd = round(width, 4)
    w05_rnd = round(width * 0.5, 4)
    h_rnd = round(height, 4)
    h05_rnd = round(height * 0.5, 4)

    cells = [
        build_cell("PinX", str(pin_x)),
        build_cell("PinY", str(pin_y)),
        build_cell("Width", str(width)),
        build_cell("Height", str(height)),
        build_cell("LocPinX", str(w05_rnd), "Width*0.5"),
        build_cell("LocPinY", str(h05_rnd), "Height*0.5"),
        build_cell("Angle", "0"),
        build_cell("FlipX", "0"),
        build_cell("FlipY", "0"),
        build_cell("LinePattern", "0"),
        build_cell("FillPattern", "0"),
    ]

    conn_section = ""
    if has_connections:
        conn_rows = [
            f"<Row T='Connection' N='Top'><Cell N='X' V='{w05_rnd}' F='Width*0.5'/><Cell N='Y' V='{h_rnd}' F='Height*1'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Bottom'><Cell N='X' V='{w05_rnd}' F='Width*0.5'/><Cell N='Y' V='0' F='Height*0'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Left'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h05_rnd}' F='Height*0.5'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
            f"<Row T='Connection' N='Right'><Cell N='X' V='{w_rnd}' F='Width*1'/><Cell N='Y' V='{h05_rnd}' F='Height*0.5'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>",
        ]
        if extra_connections:
            for c_name, c_x, c_y, c_xf, c_yf in extra_connections:
                conn_rows.append(
                    f"<Row T='Connection' N='{c_name}'><Cell N='X' V='{round(c_x, 4)}' F='{c_xf}'/><Cell N='Y' V='{round(c_y, 4)}' F='{c_yf}'/><Cell N='DirX' V='0'/><Cell N='DirY' V='0'/><Cell N='Type' V='0'/><Cell N='AutoGen' V='0'/><Cell N='Prompt' V='' F='No Formula'/></Row>"
                )
        conn_rows_str = "\n  ".join(conn_rows)
        conn_section = f"""<Section N='Connection'>
  {conn_rows_str}
</Section>"""

    children_str = "\n".join(child_shapes_xml)
    escaped_name = escape_xml(name)
    return f"""<Shape ID='{group_id}' NameU='{escaped_name}' Name='{escaped_name}' Type='Group' LineStyle='3' FillStyle='3' TextStyle='3'>
{chr(10).join(cells)}
{conn_section}
<Shapes>
{children_str}
</Shapes>
</Shape>"""


def build_1d_connector_xml(
    connector_id: int,
    begin_x: float,
    begin_y: float,
    end_x: float,
    end_y: float,
    label: str = "",
    line_color: str = "#475569",
    line_weight_in: float = 0.018,
    line_pattern: int = 1,
    begin_arrow: int = 0,
    end_arrow: int = 13,
    end_arrow_size: int = 2,
    font_name: str = "Segoe UI",
    font_size_pt: float = 9.0,
    text_color: str = "#1e293b",
    text_bkgnd: str = "#ffffff",
    is_dynamic: bool = True,
    source_shape_id: Optional[int] = None,
    target_shape_id: Optional[int] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    routing_direction: Optional[str] = None,
    intermediate_waypoints: Optional[List[Tuple[float, float]]] = None,
) -> str:
    """
    Renders a Visio 1D Connector <Shape> XML element.
    If is_dynamic is True and endpoints are provided, configures dynamic orthogonal connector
    cells with PAR(PNT(...)) or _WALKGLUE and _XFTRIGGER formulas for automatic glue binding in Visio.
    Generates initial orthogonal right-angle geometry so connectors appear clean and orthogonal
    immediately upon opening in Microsoft Visio without requiring shapes to be moved first.
    If is_dynamic is False, creates a straight geometric 1D line (for lifelines and sequence messages).
    """
    dx = end_x - begin_x
    dy = end_y - begin_y
    pin_x = (begin_x + end_x) / 2.0
    pin_y = (begin_y + end_y) / 2.0

    w = max(0.001, abs(dx))
    h = max(0.001, abs(dy))
    if not is_dynamic:
        if abs(dy) < 0.005:
            h = 0.0
        if abs(dx) < 0.005:
            w = 0.0

    # If connector label background is dark or black, font face MUST be white
    if is_dark_color(text_bkgnd):
        text_color = "#ffffff"

    line_hex = rgb_to_hex(line_color)
    text_hex = rgb_to_hex(text_color)
    text_bkgnd_hex = rgb_to_hex(text_bkgnd)

    if is_dynamic and source_shape_id is not None and target_shape_id is not None:
        if src_port and dst_port:
            bx_formula = f"PAR(PNT(Sheet.{source_shape_id}!Connections.{src_port}.X,Sheet.{source_shape_id}!Connections.{src_port}.Y))"
            by_formula = f"PAR(PNT(Sheet.{source_shape_id}!Connections.{src_port}.X,Sheet.{source_shape_id}!Connections.{src_port}.Y))"
            ex_formula = f"PAR(PNT(Sheet.{target_shape_id}!Connections.{dst_port}.X,Sheet.{target_shape_id}!Connections.{dst_port}.Y))"
            ey_formula = f"PAR(PNT(Sheet.{target_shape_id}!Connections.{dst_port}.X,Sheet.{target_shape_id}!Connections.{dst_port}.Y))"
        else:
            bx_formula = "_WALKGLUE(BegTrigger,EndTrigger,WalkPreference)"
            by_formula = "_WALKGLUE(BegTrigger,EndTrigger,WalkPreference)"
            ex_formula = "_WALKGLUE(EndTrigger,BegTrigger,WalkPreference)"
            ey_formula = "_WALKGLUE(EndTrigger,BegTrigger,WalkPreference)"

        cells = [
            build_cell("BeginX", str(begin_x), formula=bx_formula),
            build_cell("BeginY", str(begin_y), formula=by_formula),
            build_cell("EndX", str(end_x), formula=ex_formula),
            build_cell("EndY", str(end_y), formula=ey_formula),
            build_cell("BegTrigger", "2", formula=f"_XFTRIGGER(Sheet.{source_shape_id}!EventXFMod)"),
            build_cell("EndTrigger", "2", formula=f"_XFTRIGGER(Sheet.{target_shape_id}!EventXFMod)"),
            build_cell("GlueType", "2"),
            build_cell("WalkPreference", "1"),
            build_cell("ShapeRouteStyle", "1"),
            build_cell("RouteStyle", "1"),
            build_cell("ConLineRouteExt", "1"),
            build_cell("ConFixedCode", "1"),
            build_cell("PinX", str(pin_x), "GUARD((BeginX+EndX)/2)"),
            build_cell("PinY", str(pin_y), "GUARD((BeginY+EndY)/2)"),
            build_cell("Width", str(round(w, 4)), "GUARD(ABS(EndX-BeginX))"),
            build_cell("Height", str(round(h, 4)), "GUARD(ABS(EndY-BeginY))"),
            build_cell("LocPinX", str(round(w * 0.5, 4))),
            build_cell("LocPinY", str(round(h * 0.5, 4))),
            build_cell("Angle", "0"),
        ]
    else:
        cells = [
            build_cell("BeginX", str(begin_x)),
            build_cell("BeginY", str(begin_y)),
            build_cell("EndX", str(end_x)),
            build_cell("EndY", str(end_y)),
            build_cell("PinX", str(pin_x), "GUARD((BeginX+EndX)/2)"),
            build_cell("PinY", str(pin_y), "GUARD((BeginY+EndY)/2)"),
            build_cell("Width", str(round(w, 4)), "GUARD(ABS(EndX-BeginX))"),
            build_cell("Height", str(round(h, 4)), "GUARD(ABS(EndY-BeginY))"),
            build_cell("LocPinX", str(round(w * 0.5, 4))),
            build_cell("LocPinY", str(round(h * 0.5, 4))),
            build_cell("Angle", "0"),
        ]
        if is_dynamic:
            cells.extend([
                build_cell("ShapeRouteStyle", "1"),
                build_cell("RouteStyle", "1"),
                build_cell("ConLineRouteExt", "1"),
                build_cell("ConFixedCode", "1"),
                build_cell("GlueType", "2"),
                build_cell("WalkPreference", "1"),
            ])

    # Position label text offset from line
    if is_dynamic:
        if w < 0.1:  # Predominantly vertical line
            txt_px = str(round(w * 0.5 + 0.35, 4))
            txt_py = str(round(h * 0.5, 4))
            txt_px_f = "Width*0.5+24 pt"
            txt_py_f = "Height*0.5"
        elif h < 0.1:  # Predominantly horizontal line
            txt_px = str(round(w * 0.5, 4))
            txt_py = str(round(h * 0.5 + 0.22, 4))
            txt_px_f = "Width*0.5"
            txt_py_f = "Height*0.5+16 pt"
        else:
            txt_px = str(round(w * 0.5 + 0.2, 4))
            txt_py = str(round(h * 0.5 + 0.18, 4))
            txt_px_f = "Width*0.5+14 pt"
            txt_py_f = "Height*0.5+13 pt"
    else:
        txt_px = str(round(w * 0.5, 4))
        txt_py = str(round(h * 0.5 + 0.15, 4))
        txt_px_f = "Width*0.5"
        txt_py_f = "Height*0.5+11 pt"

    jump_code = "1" if is_dynamic else "0"

    cells.extend([
        build_cell("ConRouteJumpCode", jump_code),
        build_cell("ConRouteJumpStyle", "0"),
        build_cell("ConRouteJumpDirX", "0"),
        build_cell("ConRouteJumpDirY", "0"),
        build_cell("FillPattern", "0"),
        build_cell("FillForegnd", "0"),
        build_cell("FillBkgnd", "0"),
        build_cell("LineWeight", str(line_weight_in), unit="PT"),
        build_cell("LineColor", line_hex),
        build_cell("LinePattern", str(line_pattern), f"GUARD({line_pattern})" if line_pattern != 1 else None),
        build_cell("BeginArrow", str(begin_arrow)),
        build_cell("EndArrow", str(end_arrow)),
        build_cell("EndArrowSize", str(end_arrow_size)),
        build_cell("TextBkgnd", text_bkgnd_hex),
        build_cell("TxtWidth", "1.6", "TEXTWIDTH(TheText)+16 pt"),
        build_cell("TxtHeight", "0.35", "TEXTHEIGHT(TheText, TxtWidth)"),
        build_cell("TxtLocPinX", "0.8", "TxtWidth*0.5"),
        build_cell("TxtLocPinY", "0.175", "TxtHeight*0.5"),
        build_cell("TxtPinX", txt_px, txt_px_f),
        build_cell("TxtPinY", txt_py, txt_py_f),
        build_cell("TxtAngle", "0"),
        build_cell("ObjType", "2" if is_dynamic else "1"),
    ])

    char_section = f"""<Section N='Character'><Row IX='0'>
  <Cell N='Color' V='{text_hex}'/>
  <Cell N='Font' V='{font_name}'/>
  <Cell N='Size' V='{font_size_pt / 72.0}' U='IN'/>
</Row></Section>"""

    para_section = """<Section N='Paragraph'><Row IX='0'>
  <Cell N='IndFirst' V='0' U='IN'/><Cell N='IndLeft' V='0' U='IN'/><Cell N='IndRight' V='0' U='IN'/>
  <Cell N='HorzAlign' V='1'/>
</Row></Section>"""

    x_begin = 0.0 if dx >= 0 else round(w, 4)
    y_begin = 0.0 if dy >= 0 else round(h, 4)
    x_end = round(w, 4) if dx >= 0 else 0.0
    y_end = round(h, 4) if dy >= 0 else 0.0

    if intermediate_waypoints:
        # Route through intermediate dummy waypoints
        points = [("MoveTo", x_begin, y_begin)]
        cur_x, cur_y = x_begin, y_begin
        for wx, wy in intermediate_waypoints:
            lx = min(w, max(0.0, (wx - begin_x) if dx >= 0 else (begin_x - wx)))
            ly = min(h, max(0.0, (wy - begin_y) if dy >= 0 else (begin_y - wy)))
            # Orthogonal step
            points.append(("LineTo", cur_x, ly))
            points.append(("LineTo", lx, ly))
            cur_x, cur_y = lx, ly
        points.append(("LineTo", cur_x, y_end))
        points.append(("LineTo", x_end, y_end))
    elif not is_dynamic or (w < 0.05 and h < 0.05) or w < 0.05 or h < 0.05:
        points = [
            ("MoveTo", x_begin, y_begin),
            ("LineTo", x_end, y_end),
        ]
    elif w < 0.05:
        # Collinear vertical line
        points = [
            ("MoveTo", x_begin, y_begin),
            ("LineTo", x_end, y_end),
        ]
    elif h < 0.05:
        # Collinear horizontal line
        points = [
            ("MoveTo", x_begin, y_begin),
            ("LineTo", x_end, y_end),
        ]
    else:
        # Compute orthogonal right-angle bend points
        if src_port in ("Top", "Bottom") and dst_port in ("Left", "Right"):
            # L-bend: vertical exit, horizontal entry
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_begin, y_end),
                ("LineTo", x_end, y_end),
            ]
        elif src_port in ("Left", "Right") and dst_port in ("Top", "Bottom"):
            # L-bend: horizontal exit, vertical entry
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_end, y_begin),
                ("LineTo", x_end, y_end),
            ]
        elif src_port in ("Left", "Right") and dst_port in ("Left", "Right"):
            # Horizontal S/Z-bend
            x_mid = round(w * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_mid, y_begin),
                ("LineTo", x_mid, y_end),
                ("LineTo", x_end, y_end),
            ]
        elif src_port in ("Top", "Bottom") and dst_port in ("Top", "Bottom"):
            # Vertical S/Z-bend
            y_mid = round(h * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_begin, y_mid),
                ("LineTo", x_end, y_mid),
                ("LineTo", x_end, y_end),
            ]
        elif routing_direction in ("LR", "RL"):
            x_mid = round(w * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_mid, y_begin),
                ("LineTo", x_mid, y_end),
                ("LineTo", x_end, y_end),
            ]
        elif routing_direction in ("TD", "TB", "BT"):
            y_mid = round(h * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_begin, y_mid),
                ("LineTo", x_end, y_mid),
                ("LineTo", x_end, y_end),
            ]
        elif abs(dx) > abs(dy):
            x_mid = round(w * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_mid, y_begin),
                ("LineTo", x_mid, y_end),
                ("LineTo", x_end, y_end),
            ]
        else:
            y_mid = round(h * 0.5, 4)
            points = [
                ("MoveTo", x_begin, y_begin),
                ("LineTo", x_begin, y_mid),
                ("LineTo", x_end, y_mid),
                ("LineTo", x_end, y_end),
            ]

    geom_rows = [
        f"<Row T='{t}' IX='{idx}'><Cell N='X' V='{round(rx, 4)}'/><Cell N='Y' V='{round(ry, 4)}'/></Row>"
        for idx, (t, rx, ry) in enumerate(points, start=1)
    ]
    geom_rows_str = "\n  ".join(geom_rows)

    geom_section = f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='1'/>
  <Cell N='NoLine' V='0'/>
  <Cell N='NoShow' V='0'/>
  <Cell N='NoSnap' V='0'/>
  <Cell N='NoQuickDrag' V='0'/>
  {geom_rows_str}
</Section>"""

    text_element = f"<Text><cp IX='0'/><pp IX='0'/>{escape_xml(label)}</Text>" if label else ""

    shape_name_u = f"Dynamic connector.{connector_id}" if is_dynamic else f"Line.{connector_id}"
    shape_name = "Dynamic connector" if is_dynamic else "Line"
    line_style = "3" if is_dynamic else "0"
    text_style = "3" if is_dynamic else "0"

    xml_lines = [
        f"<Shape ID='{connector_id}' NameU='{shape_name_u}' Name='{shape_name}' Type='Shape' LineStyle='{line_style}' FillStyle='0' TextStyle='{text_style}'>",
        "\n".join(cells),
        char_section,
        para_section,
        geom_section,
        text_element,
        "</Shape>"
    ]
    return "\n".join(x for x in xml_lines if x)


def build_connect_records(
    connector_id: int,
    source_shape_id: int,
    target_shape_id: int,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    src_part: Optional[int] = None,
    dst_part: Optional[int] = None,
) -> str:
    """
    Renders the dynamic glue <Connect> records in the page-level <Connects> table.
    If src_port and dst_port are provided, binds to named Connection points (e.g. Connections.Bottom.X).
    Otherwise binds to PinX (whole-shape glue).
    """
    if src_port and dst_port:
        port_to_part = {"Top": 100, "Bottom": 101, "Left": 102, "Right": 103}
        base_src = src_port.split("_")[0] if src_port else ""
        base_dst = dst_port.split("_")[0] if dst_port else ""
        sp = src_part if src_part is not None else port_to_part.get(base_src, 101)
        dp = dst_part if dst_part is not None else port_to_part.get(base_dst, 100)
        return f"""<Connect FromSheet='{connector_id}' FromCell='BeginX' FromPart='9' ToSheet='{source_shape_id}' ToCell='Connections.{src_port}.X' ToPart='{sp}'/>
<Connect FromSheet='{connector_id}' FromCell='EndX' FromPart='12' ToSheet='{target_shape_id}' ToCell='Connections.{dst_port}.X' ToPart='{dp}'/>"""
    return f"""<Connect FromSheet='{connector_id}' FromCell='BeginX' FromPart='9' ToSheet='{source_shape_id}' ToCell='PinX' ToPart='3'/>
<Connect FromSheet='{connector_id}' FromCell='EndX' FromPart='12' ToSheet='{target_shape_id}' ToCell='PinX' ToPart='3'/>"""


def build_self_loop_xml(
    connector_id: int,
    px: float,
    start_y: float,
    label: str = "",
    loop_w: float = 0.75,
    loop_h: float = 0.40,
    line_color: str = "#475569",
    line_weight_in: float = 0.018,
    line_pattern: int = 1,
    end_arrow: int = 13,
    end_arrow_size: int = 2,
    font_name: str = "Segoe UI",
    font_size_pt: float = 9.0,
    text_color: str = "#1e293b",
    text_bkgnd: str = "#ffffff",
) -> str:
    """
    Renders a 3-segment orthogonal loopback connector for self-calling messages in sequence diagrams.
    Starts at (px, start_y), goes right to px + loop_w, drops down to start_y - loop_h,
    and returns left to px with an arrowhead pointing left.
    """
    pin_x = round(px + loop_w / 2.0, 4)
    pin_y = round(start_y - loop_h / 2.0, 4)
    w = round(loop_w, 4)
    h = round(loop_h, 4)
    line_hex = rgb_to_hex(line_color)
    text_hex = rgb_to_hex(text_color)
    text_bkgnd_hex = rgb_to_hex(text_bkgnd)
    escaped_label = escape_xml(label)
    shape_name = f"Line.SelfLoop.{connector_id}"

    text_element = f"<Text><cp IX='0'/><pp IX='0'/>{escaped_label}</Text>" if label else ""

    return f"""<Shape ID='{connector_id}' NameU='{shape_name}' Name='{shape_name}' Type='Shape' LineStyle='0' FillStyle='0' TextStyle='0'>
  <Cell N='PinX' V='{pin_x}'/>
  <Cell N='PinY' V='{pin_y}'/>
  <Cell N='Width' V='{w}'/>
  <Cell N='Height' V='{h}'/>
  <Cell N='LocPinX' V='{round(w * 0.5, 4)}' F='Width*0.5'/>
  <Cell N='LocPinY' V='{round(h * 0.5, 4)}' F='Height*0.5'/>
  <Cell N='Angle' V='0'/>
  <Cell N='LineWeight' V='{line_weight_in}' U='PT'/>
  <Cell N='LineColor' V='{line_hex}'/>
  <Cell N='LinePattern' V='{line_pattern}' F='GUARD({line_pattern})'/>
  <Cell N='BeginArrow' V='0'/>
  <Cell N='EndArrow' V='{end_arrow}'/>
  <Cell N='EndArrowSize' V='{end_arrow_size}'/>
  <Cell N='FillPattern' V='0'/>
  <Cell N='FillForegnd' V='0'/>
  <Cell N='FillBkgnd' V='0'/>
  <Cell N='ObjType' V='1'/>
  <Cell N='TextBkgnd' V='{text_bkgnd_hex}'/>
  <Cell N='TxtWidth' V='1.6' F='TEXTWIDTH(TheText)+8 pt'/>
  <Cell N='TxtHeight' V='0.35' F='TEXTHEIGHT(TheText, TxtWidth)'/>
  <Cell N='TxtLocPinX' V='0.8' F='TxtWidth*0.5'/>
  <Cell N='TxtLocPinY' V='0.175' F='TxtHeight*0.5'/>
  <Cell N='TxtPinX' V='{round(w * 0.5 + 0.1, 4)}' F='Width*0.5+8 pt'/>
  <Cell N='TxtPinY' V='{round(h + 0.18, 4)}' F='Height*1+12 pt'/>
  <Cell N='TxtAngle' V='0'/>
  <Section N='Character'><Row IX='0'>
    <Cell N='Color' V='{text_hex}'/>
    <Cell N='Font' V='{font_name}'/>
    <Cell N='Size' V='{font_size_pt / 72.0}' U='IN'/>
  </Row></Section>
  <Section N='Paragraph'><Row IX='0'>
    <Cell N='HorzAlign' V='0'/>
  </Row></Section>
  <Section N='Geometry' IX='0'>
    <Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
    <Row T='MoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='{h}' F='Height*1'/></Row>
    <Row T='LineTo' IX='2'><Cell N='X' V='{w}' F='Width*1'/><Cell N='Y' V='{h}' F='Height*1'/></Row>
    <Row T='LineTo' IX='3'><Cell N='X' V='{w}' F='Width*1'/><Cell N='Y' V='0'/></Row>
    <Row T='LineTo' IX='4'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>
  </Section>
  {text_element}
</Shape>"""
