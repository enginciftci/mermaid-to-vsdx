"""
Visio Compiler for Mermaid Pie Charts (`pie`).
Renders an executive Circular Sector Pie Chart (multi-wedge ShapeSheet geometry)
paired with a right-hand Legend & Proportional Bar Infographic table.
"""

import math
from typing import List, Tuple
from ..parser.ast_nodes import PieDiagram, PieSlice
from ..visio.palettes import (
    DEFAULT_PALETTE_NAME,
    get_contrasting_text_color,
    get_palette,
    is_dark_color,
)
from .opc_package import package_vsdx
from .shapesheet import build_2d_shape_xml, build_cell, escape_xml, rgb_to_hex


_SLICE_COLORS_LIGHT: List[Tuple[str, str]] = [
    # (fill_hex, border_hex)
    ("#3b82f6", "#1d4ed8"),  # Blue
    ("#10b981", "#047857"),  # Emerald
    ("#f59e0b", "#b45309"),  # Amber
    ("#8b5cf6", "#6d28d9"),  # Violet
    ("#f43f5e", "#be123c"),  # Rose
    ("#06b6d4", "#0e7490"),  # Cyan
    ("#f97316", "#c2410c"),  # Orange
    ("#6366f1", "#4338ca"),  # Indigo
]

_SLICE_COLORS_DARK: List[Tuple[str, str]] = [
    ("#2563eb", "#60a5fa"),
    ("#059669", "#34d399"),
    ("#d97706", "#fbbf24"),
    ("#7c3aed", "#c084fc"),
    ("#e11d48", "#fb7185"),
    ("#0891b2", "#22d3ee"),
    ("#ea580c", "#fb923c"),
    ("#4f46e5", "#818cf8"),
]


def _build_pie_wedge_shape_xml(
    shape_id: int,
    name: str,
    pie_cx: float,
    pie_cy: float,
    radius: float,
    theta_start_rad: float,
    theta_end_rad: float,
    fill_color: str,
    line_color: str,
    line_weight_in: float = 0.022,
) -> str:
    """
    Builds a 2D Visio <Shape> representing a circular pie wedge from theta_start_rad to theta_end_rad.
    Uses local bounding box [0, 2*R] x [0, 2*R] centered at (pie_cx, pie_cy).
    """
    diam = round(radius * 2.0, 4)
    r_val = round(radius, 4)
    fill_hex = rgb_to_hex(fill_color)
    line_hex = rgb_to_hex(line_color)

    span = abs(theta_end_rad - theta_start_rad)
    num_steps = max(12, min(48, int(math.ceil(span / (math.pi / 24.0)))))

    rows: List[str] = []
    ix = 1
    if span >= 2.0 * math.pi - 1e-4:
        # Full 360-degree circle
        for step in range(num_steps + 1):
            ang = theta_start_rad + (theta_end_rad - theta_start_rad) * (step / num_steps)
            vx = round(radius + radius * math.cos(ang), 4)
            vy = round(radius + radius * math.sin(ang), 4)
            r_type = "MoveTo" if step == 0 else "LineTo"
            rows.append(f"<Row T='{r_type}' IX='{ix}'><Cell N='X' V='{vx}'/><Cell N='Y' V='{vy}'/></Row>")
            ix += 1
    else:
        rows.append(f"<Row T='MoveTo' IX='{ix}'><Cell N='X' V='{r_val}'/><Cell N='Y' V='{r_val}'/></Row>")
        ix += 1
        for step in range(num_steps + 1):
            ang = theta_start_rad + (theta_end_rad - theta_start_rad) * (step / num_steps)
            vx = round(radius + radius * math.cos(ang), 4)
            vy = round(radius + radius * math.sin(ang), 4)
            rows.append(f"<Row T='LineTo' IX='{ix}'><Cell N='X' V='{vx}'/><Cell N='Y' V='{vy}'/></Row>")
            ix += 1
        rows.append(f"<Row T='LineTo' IX='{ix}'><Cell N='X' V='{r_val}'/><Cell N='Y' V='{r_val}'/></Row>")

    cells = [
        build_cell("PinX", str(round(pie_cx, 4))),
        build_cell("PinY", str(round(pie_cy, 4))),
        build_cell("Width", str(diam)),
        build_cell("Height", str(diam)),
        build_cell("LocPinX", str(r_val), "Width*0.5"),
        build_cell("LocPinY", str(r_val), "Height*0.5"),
        build_cell("Angle", "0"),
        build_cell("FillPattern", "1"),
        build_cell("FillForegnd", fill_hex),
        build_cell("FillBkgnd", "#ffffff"),
        build_cell("LineWeight", str(line_weight_in), unit="PT"),
        build_cell("LineColor", line_hex),
        build_cell("LinePattern", "1"),
        build_cell("ObjType", "1"),
    ]

    rows_str = "\n  ".join(rows)
    geom_section = f"""<Section N='Geometry' IX='0'>
  <Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>
  {rows_str}
</Section>"""

    escaped_name = escape_xml(name)
    return f"""<Shape ID='{shape_id}' NameU='{escaped_name}' Name='{escaped_name}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>
{chr(10).join(cells)}
{geom_section}
</Shape>"""


def compile_pie_to_vsdx(
    diagram: PieDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a PieDiagram AST into a native Microsoft Visio (.vsdx) file.
    """
    palette = get_palette(palette_name)
    dark_mode = is_dark_color(palette.background)
    slice_palette = _SLICE_COLORS_DARK if dark_mode else _SLICE_COLORS_LIGHT

    slices = diagram.slices or [PieSlice(label="Total", value=100.0)]
    total_val = sum(max(0.0, s.value) for s in slices)
    if total_val <= 0:
        total_val = 1.0

    num_slices = len(slices)
    page_w = 11.5
    page_h = round(max(7.2, num_slices * 0.65 + 2.8), 2)

    pie_radius = 2.15
    pie_cx = 3.15
    pie_cy = round(page_h * 0.5 - (0.25 if diagram.title else 0.0), 4)

    shapes_xml_list: List[str] = []
    shape_id_counter = 1

    # 1. Optional Title Banner
    if diagram.title:
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name="Pie_Title",
                pin_x=round(page_w * 0.5, 4),
                pin_y=round(page_h - 0.55, 4),
                width=round(min(9.5, max(4.5, len(diagram.title) * 0.14 + 1.2)), 4),
                height=0.50,
                text=diagram.title,
                shape_type="rounded",
                fill_color=palette.subgraph_fill,
                line_color=palette.subgraph_border,
                text_color=palette.default_text,
                font_name=font_name,
                font_size_pt=14.0,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    # 2. Pie Chart Backdrop Card
    pie_card_w = 5.10
    pie_card_h = 5.10
    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Container_Pie_Card",
            pin_x=pie_cx,
            pin_y=pie_cy,
            width=pie_card_w,
            height=pie_card_h,
            text="",
            shape_type="rounded",
            fill_color=palette.subgraph_fill,
            line_color=palette.subgraph_border,
            rounding_in=0.16,
            is_container=True,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    # 3. Render Multi-Wedge Pie Sectors & Percentage Callout Badges
    cur_angle = math.pi / 2.0  # Start at 12 o'clock and sweep clockwise
    sep_border = "#0f172a" if dark_mode else "#ffffff"

    for idx_s, s_item in enumerate(slices):
        frac = max(0.0, s_item.value) / total_val
        sweep = frac * 2.0 * math.pi
        next_angle = cur_angle - sweep
        fill_col, border_col = slice_palette[idx_s % len(slice_palette)]

        shapes_xml_list.append(
            _build_pie_wedge_shape_xml(
                shape_id=shape_id_counter,
                name=f"Pie_Wedge_{idx_s}",
                pie_cx=pie_cx,
                pie_cy=pie_cy,
                radius=pie_radius,
                theta_start_rad=cur_angle,
                theta_end_rad=next_angle,
                fill_color=fill_col,
                line_color=sep_border,
                line_weight_in=0.024,
            )
        )
        shape_id_counter += 1

        # Percentage badge positioned along the slice bisector
        pct = frac * 100.0
        if pct >= 3.5:
            mid_angle = (cur_angle + next_angle) * 0.5
            lbl_r = pie_radius * (0.64 if pct >= 9.0 else 0.78)
            bx = round(pie_cx + lbl_r * math.cos(mid_angle), 4)
            by = round(pie_cy + lbl_r * math.sin(mid_angle), 4)
            pct_str = f"{pct:.1f}%" if abs(pct - round(pct)) >= 0.1 else f"{int(round(pct))}%"

            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Badge_PiePct_{idx_s}",
                    pin_x=bx,
                    pin_y=by,
                    width=0.68,
                    height=0.28,
                    text=pct_str,
                    shape_type="stadium",
                    fill_color="#0f172a" if dark_mode else "#ffffff",
                    line_color=border_col,
                    text_color="#f8fafc" if dark_mode else "#0f172a",
                    line_weight_in=0.015,
                    font_name=font_name,
                    font_size_pt=8.5,
                    bold=True,
                    has_connections=False,
                    shadow=True,
                )
            )
            shape_id_counter += 1

        cur_angle = next_angle

    # 4. Right-Hand Legend & Proportional Breakdown Table Card
    leg_cx = 8.45
    leg_w = 4.65
    row_h = 0.56
    header_h = 0.46
    leg_h = round(max(3.2, header_h + num_slices * row_h + 0.55), 4)
    leg_top = pie_cy + leg_h * 0.5

    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Container_Legend_Card",
            pin_x=leg_cx,
            pin_y=pie_cy,
            width=leg_w,
            height=leg_h,
            text="",
            shape_type="rounded",
            fill_color=palette.subgraph_fill,
            line_color=palette.subgraph_border,
            rounding_in=0.16,
            is_container=True,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    # Legend Header Bar
    hdr_y = round(leg_top - 0.34, 4)
    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Subgraph_Header_Legend",
            pin_x=leg_cx,
            pin_y=hdr_y,
            width=round(leg_w - 0.28, 4),
            height=0.38,
            text="Category Breakdown & Share",
            shape_type="rounded",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            text_color=palette.default_text,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=10.0,
            bold=True,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    leg_left = leg_cx - leg_w * 0.5
    for idx_s, s_item in enumerate(slices):
        frac = max(0.0, s_item.value) / total_val
        pct = frac * 100.0
        fill_col, border_col = slice_palette[idx_s % len(slice_palette)]
        ry = round(hdr_y - 0.46 - idx_s * row_h, 4)

        # Color Swatch
        swatch_x = round(leg_left + 0.36, 4)
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"LegendSwatch_{idx_s}",
                pin_x=swatch_x,
                pin_y=ry,
                width=0.28,
                height=0.28,
                text="",
                shape_type="rounded",
                fill_color=fill_col,
                line_color=border_col,
                rounding_in=0.06,
                has_connections=False,
            )
        )
        shape_id_counter += 1

        # Category Label + Proportional Bar
        val_str = f"{int(s_item.value)}" if abs(s_item.value - round(s_item.value)) < 1e-4 else f"{s_item.value:.1f}"
        lbl_str = f"{s_item.label} ({val_str})" if diagram.show_data else s_item.label
        lbl_w = 2.55
        lbl_x = round(leg_left + 0.62 + lbl_w * 0.5, 4)
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"LegendLabel_{idx_s}",
                pin_x=lbl_x,
                pin_y=round(ry + 0.08, 4),
                width=lbl_w,
                height=0.26,
                text=lbl_str,
                shape_type="rectangle",
                fill_pattern=0,
                line_pattern=0,
                text_color=palette.default_text,
                font_name=font_name,
                font_size_pt=9.5,
                align_left=True,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

        # Proportional Progress Bar Track & Fill under the label
        bar_max_w = 2.45
        bar_h = 0.10
        bar_y = round(ry - 0.11, 4)
        bar_left = leg_left + 0.66
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"LegendBarTrack_{idx_s}",
                pin_x=round(bar_left + bar_max_w * 0.5, 4),
                pin_y=bar_y,
                width=bar_max_w,
                height=bar_h,
                text="",
                shape_type="stadium",
                fill_color="#334155" if dark_mode else "#e2e8f0",
                line_pattern=0,
                has_connections=False,
            )
        )
        shape_id_counter += 1

        fill_bar_w = round(max(0.12, bar_max_w * frac), 4)
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"LegendBarFill_{idx_s}",
                pin_x=round(bar_left + fill_bar_w * 0.5, 4),
                pin_y=bar_y,
                width=fill_bar_w,
                height=bar_h,
                text="",
                shape_type="stadium",
                fill_color=fill_col,
                line_pattern=0,
                has_connections=False,
            )
        )
        shape_id_counter += 1

        # Right-aligned Percentage Pill
        pct_text = f"{pct:.1f}% ({val_str})"
        pill_w = 1.12
        pill_x = round(leg_left + leg_w - 0.22 - pill_w * 0.5, 4)
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"LegendPctPill_{idx_s}",
                pin_x=pill_x,
                pin_y=ry,
                width=pill_w,
                height=0.32,
                text=pct_text,
                shape_type="stadium",
                fill_color=palette.default_fill,
                line_color=border_col,
                text_color=get_contrasting_text_color(palette.default_fill, palette.default_text),
                line_weight_in=0.015,
                font_name=font_name,
                font_size_pt=8.5,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="",
        page_width=page_w,
        page_height=page_h,
        page_bg_color=palette.background,
    )
