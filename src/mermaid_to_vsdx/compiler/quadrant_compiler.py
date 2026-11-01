"""
Visio Compiler for Mermaid Quadrant Charts (`quadrantChart`).
Renders an executive 2x2 Strategic Matrix (6.4" x 6.4" grid) with 4 tinted quadrant
background cards, corner header badges, directional X/Y axes, and data point pins + pill badges.
"""

from typing import List, Tuple
from ..parser.ast_nodes import QuadrantDiagram
from ..visio.palettes import (
    DEFAULT_PALETTE_NAME,
    get_contrasting_text_color,
    get_palette,
    is_dark_color,
)
from .opc_package import package_vsdx
from .shapesheet import build_1d_connector_xml, build_2d_shape_xml


def compile_quadrant_to_vsdx(
    diagram: QuadrantDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a QuadrantDiagram AST into a native Microsoft Visio (.vsdx) file.
    """
    palette = get_palette(palette_name)
    dark_mode = is_dark_color(palette.background)

    page_w = 10.0
    page_h = 9.0
    grid_size = 6.4
    half_q = grid_size * 0.5  # 3.2" per quadrant

    grid_cx = 5.2
    grid_cy = 4.4
    grid_left = round(grid_cx - half_q, 4)
    grid_right = round(grid_cx + half_q, 4)
    grid_bottom = round(grid_cy - half_q, 4)
    grid_top = round(grid_cy + half_q, 4)

    # Quadrant color themes: (bg_fill, border_col, header_fill, header_text, pin_fill)
    if dark_mode:
        q_themes = {
            1: ("#064e3b", "#34d399", "#065f46", "#f8fafc", "#10b981"),  # Q1 Top-Right (Emerald)
            2: ("#1e3a8a", "#38bdf8", "#1e40af", "#f8fafc", "#3b82f6"),  # Q2 Top-Left (Blue)
            3: ("#334155", "#94a3b8", "#475569", "#f8fafc", "#64748b"),  # Q3 Bottom-Left (Slate)
            4: ("#78350f", "#fbbf24", "#92400e", "#f8fafc", "#f59e0b"),  # Q4 Bottom-Right (Amber)
        }
    else:
        q_themes = {
            1: ("#ecfdf5", "#10b981", "#d1fae5", "#065f46", "#059669"),  # Q1 Top-Right (Emerald)
            2: ("#eff6ff", "#3b82f6", "#dbeafe", "#1e40af", "#2563eb"),  # Q2 Top-Left (Blue)
            3: ("#f8fafc", "#94a3b8", "#e2e8f0", "#334155", "#475569"),  # Q3 Bottom-Left (Slate)
            4: ("#fffbeb", "#f59e0b", "#fef3c7", "#92400e", "#d97706"),  # Q4 Bottom-Right (Amber)
        }

    shapes_xml_list: List[str] = []
    shape_id_counter = 1

    # 1. Title Banner
    if diagram.title:
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name="Quadrant_Title",
                pin_x=grid_cx,
                pin_y=round(page_h - 0.58, 4),
                width=round(min(8.2, max(4.2, len(diagram.title) * 0.14 + 1.0)), 4),
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

    # 2. Four Quadrant Background Cards + Header Watermark Pills
    # Mermaid Quadrant convention:
    # Q2: Top-Left     | Q1: Top-Right
    # Q3: Bottom-Left  | Q4: Bottom-Right
    quad_specs = [
        (2, diagram.quadrant_2, grid_cx - half_q * 0.5, grid_cy + half_q * 0.5, True),
        (1, diagram.quadrant_1, grid_cx + half_q * 0.5, grid_cy + half_q * 0.5, True),
        (3, diagram.quadrant_3, grid_cx - half_q * 0.5, grid_cy - half_q * 0.5, False),
        (4, diagram.quadrant_4, grid_cx + half_q * 0.5, grid_cy - half_q * 0.5, False),
    ]

    placed_obstacles: List[Tuple[float, float, float, float]] = []

    for q_num, q_title, qx, qy, is_top in quad_specs:
        bg_fill, q_border, hdr_fill, hdr_text, _ = q_themes[q_num]
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"Quadrant_Bg_Q{q_num}",
                pin_x=round(qx, 4),
                pin_y=round(qy, 4),
                width=round(half_q - 0.04, 4),
                height=round(half_q - 0.04, 4),
                text="",
                shape_type="rounded",
                fill_color=bg_fill,
                line_color=q_border,
                line_weight_in=0.018,
                rounding_in=0.10,
                is_container=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

        if q_title:
            hdr_y = round(qy + half_q * 0.5 - 0.28, 4) if is_top else round(qy + half_q * 0.5 - 0.28, 4)
            hdr_w = round(min(half_q - 0.36, max(1.5, len(q_title) * 0.095 + 0.45)), 4)
            placed_obstacles.append((round(qx, 4), hdr_y, hdr_w, 0.36))
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Subgraph_Header_Q{q_num}",
                    pin_x=round(qx, 4),
                    pin_y=hdr_y,
                    width=hdr_w,
                    height=0.34,
                    text=q_title,
                    shape_type="rounded",
                    fill_color=hdr_fill,
                    line_color=q_border,
                    text_color=hdr_text,
                    rounding_in=0.08,
                    font_name=font_name,
                    font_size_pt=9.5,
                    bold=True,
                    has_connections=False,
                )
            )
            shape_id_counter += 1

    # 3. Crosshair Dividers & Outer X/Y Directional Axes
    # Center vertical dashed divider (x = 0.5)
    shapes_xml_list.append(
        build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=grid_cx,
            begin_y=grid_bottom,
            end_x=grid_cx,
            end_y=grid_top,
            line_color=palette.connector_line,
            line_weight_in=0.020,
            line_pattern=2,
            begin_arrow=0,
            end_arrow=0,
            is_dynamic=False,
        )
    )
    shape_id_counter += 1

    # Center horizontal dashed divider (y = 0.5)
    shapes_xml_list.append(
        build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=grid_left,
            begin_y=grid_cy,
            end_x=grid_right,
            end_y=grid_cy,
            line_color=palette.connector_line,
            line_weight_in=0.020,
            line_pattern=2,
            begin_arrow=0,
            end_arrow=0,
            is_dynamic=False,
        )
    )
    shape_id_counter += 1

    # Bottom X-Axis Arrow
    axis_offset = 0.14
    shapes_xml_list.append(
        build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=grid_left,
            begin_y=round(grid_bottom - axis_offset, 4),
            end_x=round(grid_right + 0.18, 4),
            end_y=round(grid_bottom - axis_offset, 4),
            line_color=palette.default_text,
            line_weight_in=0.026,
            line_pattern=1,
            begin_arrow=0,
            end_arrow=13,
            end_arrow_size=2,
            is_dynamic=False,
        )
    )
    shape_id_counter += 1

    # Left Y-Axis Arrow
    shapes_xml_list.append(
        build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=round(grid_left - axis_offset, 4),
            begin_y=grid_bottom,
            end_x=round(grid_left - axis_offset, 4),
            end_y=round(grid_top + 0.18, 4),
            line_color=palette.default_text,
            line_weight_in=0.026,
            line_pattern=1,
            begin_arrow=0,
            end_arrow=13,
            end_arrow_size=2,
            is_dynamic=False,
        )
    )
    shape_id_counter += 1

    # 4. Axis Labels (X-left, X-right, Y-bottom, Y-top)
    axis_labels = [
        ("X_Left", diagram.x_axis_left, round(grid_left + 1.05, 4), round(grid_bottom - 0.44, 4), 2.1, 0.34),
        ("X_Right", diagram.x_axis_right, round(grid_right - 1.05, 4), round(grid_bottom - 0.44, 4), 2.1, 0.34),
        ("Y_Bottom", diagram.y_axis_bottom, round(grid_left - 0.92, 4), round(grid_bottom + 0.55, 4), 1.45, 0.42),
        ("Y_Top", diagram.y_axis_top, round(grid_left - 0.92, 4), round(grid_top - 0.55, 4), 1.45, 0.42),
    ]
    for lbl_key, lbl_text, lx, ly, lw, lh in axis_labels:
        if not lbl_text:
            continue
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"AxisLabel_{lbl_key}",
                pin_x=lx,
                pin_y=ly,
                width=lw,
                height=lh,
                text=lbl_text,
                shape_type="rounded",
                fill_color=palette.subgraph_fill,
                line_color=palette.subgraph_border,
                text_color=palette.default_text,
                rounding_in=0.08,
                font_name=font_name,
                font_size_pt=9.0,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    # 5. Data Points: Circular Marker Pin + Floating Pill Badge
    usable_pad = 0.25
    usable_span = grid_size - 2 * usable_pad

    point_coords: List[Tuple[float, float, int]] = []
    for idx_pt, pt in enumerate(diagram.points):
        px = round(grid_left + usable_pad + pt.x * usable_span, 4)
        py = round(grid_bottom + usable_pad + pt.y * usable_span, 4)

        if pt.x >= 0.5 and pt.y >= 0.5:
            q_num = 1
        elif pt.x < 0.5 and pt.y >= 0.5:
            q_num = 2
        elif pt.x < 0.5 and pt.y < 0.5:
            q_num = 3
        else:
            q_num = 4

        point_coords.append((px, py, q_num))
        placed_obstacles.append((px, py, 0.26, 0.26))

        _, q_border, _, _, pin_fill = q_themes[q_num]

        # Marker Pin Circle
        pin_sid = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=pin_sid,
                name=f"Marker_Pin_{idx_pt}",
                pin_x=px,
                pin_y=py,
                width=0.20,
                height=0.20,
                text="",
                shape_type="circle",
                fill_color=pin_fill,
                line_color="#ffffff" if not dark_mode else palette.default_text,
                line_weight_in=0.022,
                has_connections=False,
                shadow=True,
            )
        )

    for idx_pt, pt in enumerate(diagram.points):
        px, py, q_num = point_coords[idx_pt]
        _, q_border, _, _, _ = q_themes[q_num]

        # Floating Pill Badge with collision avoidance against headers, pins, and other badges
        badge_text = f"{pt.label}"
        bw = round(min(2.15, max(1.10, len(badge_text) * 0.088 + 0.34)), 4)
        bh = 0.32
        clamped_x = max(grid_left + bw * 0.5 + 0.06, min(grid_right - bw * 0.5 - 0.06, px))

        near_q_top = (0.35 <= pt.y < 0.50) or (pt.y >= 0.84)
        if near_q_top:
            candidates = [
                (clamped_x, round(py - 0.27, 4)),
                (clamped_x, round(py + 0.27, 4)),
                (max(grid_left + bw * 0.5 + 0.06, min(grid_right - bw * 0.5 - 0.06, round(px + bw * 0.5 + 0.18, 4))), py),
                (max(grid_left + bw * 0.5 + 0.06, min(grid_right - bw * 0.5 - 0.06, round(px - bw * 0.5 - 0.18, 4))), py),
            ]
        else:
            candidates = [
                (clamped_x, round(py + 0.27, 4)),
                (clamped_x, round(py - 0.27, 4)),
                (max(grid_left + bw * 0.5 + 0.06, min(grid_right - bw * 0.5 - 0.06, round(px + bw * 0.5 + 0.18, 4))), py),
                (max(grid_left + bw * 0.5 + 0.06, min(grid_right - bw * 0.5 - 0.06, round(px - bw * 0.5 - 0.18, 4))), py),
            ]

        bx, by = candidates[0]
        for cand_x, cand_y in candidates:
            collision = False
            for obx, oby, obw, obh in placed_obstacles:
                if abs(cand_x - obx) < (bw + obw) * 0.50 and abs(cand_y - oby) < (bh + obh) * 0.52:
                    collision = True
                    break
            if not collision:
                bx, by = cand_x, cand_y
                break

        placed_obstacles.append((bx, by, bw, bh))

        badge_fill = "#1e293b" if dark_mode else "#ffffff"
        badge_text_col = get_contrasting_text_color(badge_fill, palette.default_text)

        badge_sid = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=badge_sid,
                name=f"Badge_Point_{idx_pt}",
                pin_x=round(bx, 4),
                pin_y=round(by, 4),
                width=bw,
                height=bh,
                text=badge_text,
                shape_type="stadium",
                fill_color=badge_fill,
                line_color=q_border,
                text_color=badge_text_col,
                line_weight_in=0.018,
                font_name=font_name,
                font_size_pt=8.5,
                bold=True,
                has_connections=False,
                shadow=True,
            )
        )

    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="",
        page_width=page_w,
        page_height=page_h,
        page_bg_color=palette.background,
    )
