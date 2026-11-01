"""
Headless Native VSDX Vector-to-Raster Preview Renderer.
Renders Open Packaging Conventions (.vsdx) diagrams into high-resolution PNG images
using pure Python and Pillow without requiring Microsoft Visio or COM automation.
"""

import os
import math
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


def draw_dashed_line(draw: ImageDraw.ImageDraw, p1, p2, fill, width, dash_len=8, gap_len=5):
    if not fill:
        return
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return
    vx = dx / dist
    vy = dy / dist
    cur = 0.0
    while cur < dist:
        seg_end = min(cur + dash_len, dist)
        sp1 = (x1 + vx * cur, y1 + vy * cur)
        sp2 = (x1 + vx * seg_end, y1 + vy * seg_end)
        draw.line([sp1, sp2], fill=fill, width=width)
        cur += dash_len + gap_len


def draw_dashed_rect(draw: ImageDraw.ImageDraw, tl, br, fill, outline, width, dash_len=8, gap_len=5):
    x1, y1 = tl
    x2, y2 = br
    if fill:
        draw.rectangle([tl, br], fill=fill)
    if outline:
        draw_dashed_line(draw, (x1, y1), (x2, y1), fill=outline, width=width, dash_len=dash_len, gap_len=gap_len)
        draw_dashed_line(draw, (x2, y1), (x2, y2), fill=outline, width=width, dash_len=dash_len, gap_len=gap_len)
        draw_dashed_line(draw, (x2, y2), (x1, y2), fill=outline, width=width, dash_len=dash_len, gap_len=gap_len)
        draw_dashed_line(draw, (x1, y2), (x1, y1), fill=outline, width=width, dash_len=dash_len, gap_len=gap_len)


def _is_axis_aligned_rect(raw_local_pts, w: float, h: float) -> bool:
    """
    Returns True if the geometry points represent a 4- or 5-point axis-aligned rectangle
    matching the bounding box [0, w] x [0, h].
    """
    if len(raw_local_pts) not in (4, 5) or w <= 0 or h <= 0:
        return False
    tol_x = max(0.02, w * 0.04)
    tol_y = max(0.02, h * 0.04)
    for rx, ry in raw_local_pts:
        on_left_or_right = abs(rx) <= tol_x or abs(rx - w) <= tol_x
        on_bottom_or_top = abs(ry) <= tol_y or abs(ry - h) <= tol_y
        if not (on_left_or_right and on_bottom_or_top):
            return False
    xs = [p[0] for p in raw_local_pts]
    ys = [p[1] for p in raw_local_pts]
    if (max(xs) - min(xs)) < w * 0.8 or (max(ys) - min(ys)) < h * 0.8:
        return False
    return True


def render_vsdx_to_png(
    vsdx_path: str,
    output_image_path: Optional[str] = None,
    dpi: int = 120,
    verification_dir: str = "verification_output"
) -> Dict[str, Any]:
    """
    Renders the page1.xml inside a .vsdx archive into a high-resolution PNG preview.
    Returns metadata compatible with verification results.
    """
    start_time = time.time()
    abs_vsdx = os.path.abspath(vsdx_path)
    if not os.path.exists(abs_vsdx):
        raise FileNotFoundError(f"VSDX file not found: {abs_vsdx}")

    if not output_image_path:
        os.makedirs(verification_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(abs_vsdx))[0]
        output_image_path = os.path.abspath(os.path.join(verification_dir, f"{base}_preview.png"))
    else:
        output_image_path = os.path.abspath(output_image_path)
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)

    with zipfile.ZipFile(abs_vsdx, 'r') as z:
        page1_xml = z.read('visio/pages/page1.xml').decode('utf-8')
        pages_xml = z.read('visio/pages/pages.xml').decode('utf-8')

    root_pages = ET.fromstring(pages_xml)
    root_p1 = ET.fromstring(page1_xml)

    # 1. Page Dimensions
    pw_in = 8.5
    ph_in = 11.0
    for cell in root_pages.findall('.//{*}Cell'):
        if cell.attrib.get('N') == 'PageWidth':
            pw_in = float(cell.attrib.get('V', '8.5'))
        elif cell.attrib.get('N') == 'PageHeight':
            ph_in = float(cell.attrib.get('V', '11.0'))

    img_w = max(400, int(pw_in * dpi))
    img_h = max(300, int(ph_in * dpi))

    img = Image.new('RGBA', (img_w, img_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Load system font for crisp rendering
    font_candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "segoeui.ttf",
        "arial.ttf"
    ]
    base_font_path = None
    bold_font_path = None
    for fp in font_candidates:
        if os.path.exists(fp):
            base_font_path = fp
            cand_bold = fp.replace("segoeui", "segoeuib").replace("arial", "arialbd")
            bold_font_path = cand_bold if os.path.exists(cand_bold) else fp
            break

    font_cache: Dict[Tuple[int, bool], Any] = {}

    def get_font(pt_size: float, is_bold: bool = False):
        px_size = max(9, int(round(pt_size * dpi / 72.0)))
        key = (px_size, is_bold)
        if key in font_cache:
            return font_cache[key]
        if base_font_path:
            try:
                fp = bold_font_path if is_bold else base_font_path
                f_obj = ImageFont.truetype(fp, px_size)
                font_cache[key] = f_obj
                return f_obj
            except Exception:
                pass
        f_obj = ImageFont.load_default()
        font_cache[key] = f_obj
        return f_obj

    def to_img(x_in: float, y_in: float):
        return (x_in * dpi, (ph_in - y_in) * dpi)

    shapes_to_render = []

    def collect_shapes(shape_elem, parent_ox=0.0, parent_oy=0.0, order_idx=0):
        name_u = shape_elem.attrib.get('NameU', '') or shape_elem.attrib.get('Name', '')
        cells = {c.attrib.get('N'): c.attrib.get('V', '') for c in shape_elem.findall('{*}Cell')}
        try:
            pin_x = float(cells.get('PinX', 0))
            pin_y = float(cells.get('PinY', 0))
            w = float(cells.get('Width', 0))
            h = float(cells.get('Height', 0))
        except (ValueError, TypeError):
            return

        abs_pin_x = parent_ox + pin_x
        abs_pin_y = parent_oy + pin_y

        child_shapes_elem = shape_elem.find('{*}Shapes')
        has_children = child_shapes_elem is not None and len(child_shapes_elem.findall('{*}Shape')) > 0

        line_pat = cells.get('LinePattern', '1')
        fill_pat = int(cells.get('FillPattern', '1') or '1')
        is_transparent_group = has_children and line_pat == '0' and fill_pat == 0

        if not is_transparent_group:
            shapes_to_render.append({
                'elem': shape_elem,
                'name_u': name_u,
                'cells': cells,
                'pin_x': abs_pin_x,
                'pin_y': abs_pin_y,
                'w': w,
                'h': h,
                'idx': len(shapes_to_render),
            })

        if has_children:
            child_ox = abs_pin_x - w / 2.0
            child_oy = abs_pin_y - h / 2.0
            for child in child_shapes_elem.findall('{*}Shape'):
                collect_shapes(child, child_ox, child_oy)

    shapes_container = root_p1.find('{*}Shapes')
    if shapes_container is not None:
        for s in shapes_container.findall('{*}Shape'):
            collect_shapes(s, 0.0, 0.0)
    else:
        for s in root_p1.findall('{*}Shape'):
            collect_shapes(s, 0.0, 0.0)

    # Layering order:
    # -3: PageBackgroundCanvas
    # -2: Outer containers (Subgraph, ParticipantBox, Swimlane, Quadrant bg), largest area first
    # -1: Loop containers (Container_Loop), largest area first so they never paint over activation bars or text
    #  0: Lifelines & Gridlines
    #  1: Container tabs / headers / dividers (Loop_Tab, Loop_Div, SubgraphHeader)
    #  2: Standard 2D shapes (nodes, activation bars, notes, cards, pie wedges, gantt bars)
    #  3: 1D Connectors / Messages / SelfLoops
    #  4: Foreground markers / badges / callouts
    def shape_sort_key(s_info):
        nu = s_info['name_u'].lower()
        area = s_info['w'] * s_info['h']
        idx = s_info['idx']
        if 'pagebackgroundcanvas' in nu or 'canvas_bg' in nu:
            return (-3, -area, idx)
        if 'selfloop' in nu:
            return (3, 0, idx)
        if 'container_loop' in nu:
            return (-1, -area, idx)
        if 'loop_tab' in nu or 'loop_div' in nu or 'subgraph_header' in nu or 'subgraphheader' in nu or 'compositeheader' in nu:
            return (1, 0, idx)
        if 'container' in nu or 'subgraph' in nu or 'compositestate' in nu or 'participantbox' in nu or 'quadrant_bg' in nu:
            return (-2, -area, idx)
        if 'lifeline' in nu or 'gridline' in nu:
            return (0, 0, idx)
        if 'connector' in nu or 'line' in nu or 'message' in nu:
            return (3, 0, idx)
        if 'badge' in nu or 'callout' in nu or 'marker_pin' in nu:
            return (4, 0, idx)
        return (2, 0, idx)

    shapes_to_render.sort(key=shape_sort_key)

    for s_info in shapes_to_render:
        shape = s_info['elem']
        name_u = s_info['name_u']
        nu_low = name_u.lower()
        cells = s_info['cells']
        pin_x = s_info['pin_x']
        pin_y = s_info['pin_y']
        w = s_info['w']
        h = s_info['h']

        fill_col = cells.get('FillForegnd', '#ffffff')
        line_col = cells.get('LineColor', '#334155')
        fill_pat = int(cells.get('FillPattern', '1') or '1')
        line_pat = cells.get('LinePattern', '1')
        obj_type = cells.get('ObjType', '1')
        has_begin_x = 'BeginX' in cells and 'EndX' in cells

        is_conn = (
            obj_type == '2'
            or has_begin_x
            or 'connector' in nu_low
            or nu_low.startswith('line')
            or 'message' in nu_low
            or 'selfloop' in nu_low
        )
        is_container = (
            'container' in nu_low
            or 'subgraph' in nu_low
            or 'participantbox' in nu_low
        )

        # Extract all Geometry sections
        geom_sections = shape.findall(".//{*}Section[@N='Geometry']")
        geom_sec = geom_sections[0] if geom_sections else None
        geom_pts = []
        raw_local_pts = []
        has_ellipse = False

        if geom_sec is not None:
            for r in geom_sec.findall('{*}Row'):
                r_type = r.attrib.get('T', '')
                if r_type == 'Ellipse':
                    has_ellipse = True
                rcells = {
                    c.attrib.get('N'): float(c.attrib.get('V', 0))
                    for c in r.findall('{*}Cell')
                    if c.attrib.get('N') in ('X', 'Y')
                }
                if 'X' in rcells and 'Y' in rcells:
                    rx = rcells['X']
                    ry = rcells['Y']
                    raw_local_pts.append((rx, ry))
                    gx = pin_x - w / 2.0 + rx
                    gy = pin_y - h / 2.0 + ry
                    geom_pts.append(to_img(gx, gy))

        # 1. Connectors (1D)
        if is_conn:
            if line_pat == '0':
                continue
            line_w = max(2, int(0.018 * dpi))
            if len(geom_pts) >= 2:
                for i in range(len(geom_pts) - 1):
                    if line_pat in ('2', '3', '4', '16', '23'):
                        draw_dashed_line(draw, geom_pts[i], geom_pts[i + 1], fill=line_col, width=line_w)
                    else:
                        draw.line([geom_pts[i], geom_pts[i + 1]], fill=line_col, width=line_w)

                # Begin Arrow
                if cells.get('BeginArrow', '0') not in ('0', '') and len(geom_pts) >= 2:
                    p_first = geom_pts[0]
                    p_next = geom_pts[1]
                    ang = math.atan2(p_first[1] - p_next[1], p_first[0] - p_next[0])
                    arr_len = 9 * (dpi / 96)
                    a1 = (p_first[0] - arr_len * math.cos(ang - 0.40), p_first[1] - arr_len * math.sin(ang - 0.40))
                    a2 = (p_first[0] - arr_len * math.cos(ang + 0.40), p_first[1] - arr_len * math.sin(ang + 0.40))
                    draw.polygon([p_first, a1, a2], fill=line_col)

                # End Arrow
                if cells.get('EndArrow', '0') not in ('0', '') and len(geom_pts) >= 2:
                    p_last = geom_pts[-1]
                    p_prev = geom_pts[-2]
                    ang = math.atan2(p_last[1] - p_prev[1], p_last[0] - p_prev[0])
                    arr_len = 9 * (dpi / 96)
                    a1 = (p_last[0] - arr_len * math.cos(ang - 0.40), p_last[1] - arr_len * math.sin(ang - 0.40))
                    a2 = (p_last[0] - arr_len * math.cos(ang + 0.40), p_last[1] - arr_len * math.sin(ang + 0.40))
                    draw.polygon([p_last, a1, a2], fill=line_col)

        # 2. 2D Shapes & Containers
        else:
            border_w = max(1, int(0.016 * dpi))
            f_col = fill_col if fill_pat != 0 else None
            # For Container_Loop, never let an opaque fill obscure inner elements
            if 'container_loop' in nu_low:
                f_col = None
            outline_col = None if line_pat == '0' else line_col

            try:
                rounding_val = float(cells.get('Rounding', '0') or '0')
            except (ValueError, TypeError):
                rounding_val = 0.0

            is_cylinder = 'cylinder' in nu_low
            if not is_cylinder and geom_sec is not None:
                for r in geom_sec.findall('{*}Row'):
                    if r.attrib.get('T') == 'EllipticalArcTo' and 'pie_wedge' not in nu_low:
                        is_cylinder = True
                        break

            if has_ellipse:
                # Render all Geometry sections containing <Row T='Ellipse'> (supports circle and double_circle)
                for g_sec in geom_sections:
                    sec_cells = {c.attrib.get('N'): c.attrib.get('V', '0') for c in g_sec.findall('{*}Cell')}
                    sec_no_fill = sec_cells.get('NoFill', '0') == '1'
                    sec_no_line = sec_cells.get('NoLine', '0') == '1'
                    sec_f = None if sec_no_fill else f_col
                    sec_o = None if sec_no_line else outline_col
                    for r in g_sec.findall('{*}Row'):
                        if r.attrib.get('T') == 'Ellipse':
                            ec = {
                                c.attrib.get('N'): float(c.attrib.get('V', 0))
                                for c in r.findall('{*}Cell')
                                if c.attrib.get('N') in ('X', 'Y', 'A', 'B', 'C', 'D')
                            }
                            ex = ec.get('X', w * 0.5)
                            ey = ec.get('Y', h * 0.5)
                            ea = ec.get('A', w)
                            ed = ec.get('D', h)
                            rad_x = abs(ea - ex) if 'A' in ec else w * 0.5
                            rad_y = abs(ed - ey) if 'D' in ec else h * 0.5
                            cx_in = pin_x - w * 0.5 + ex
                            cy_in = pin_y - h * 0.5 + ey
                            tl_e = to_img(cx_in - rad_x, cy_in + rad_y)
                            br_e = to_img(cx_in + rad_x, cy_in - rad_y)
                            draw.ellipse([tl_e, br_e], fill=sec_f, outline=sec_o, width=border_w)
            elif is_container:
                tl = to_img(pin_x - w / 2.0, pin_y + h / 2.0)
                br = to_img(pin_x + w / 2.0, pin_y - h / 2.0)
                if line_pat in ('2', '3', '4', '16', '23'):
                    draw_dashed_rect(draw, tl, br, fill=f_col, outline=outline_col, width=border_w)
                else:
                    rad_px = max(6, int(rounding_val * dpi)) if rounding_val > 0 else 8
                    draw.rounded_rectangle([tl, br], radius=rad_px, fill=f_col, outline=outline_col, width=border_w)
            elif is_cylinder and w > 0 and h > 0:
                cap_h_in = h * 0.28
                cap_h_px = cap_h_in * dpi
                tl_b = to_img(pin_x - w / 2.0, pin_y + h / 2.0 - cap_h_in / 2.0)
                br_b = to_img(pin_x + w / 2.0, pin_y - h / 2.0 + cap_h_in / 2.0)
                tl_bot = (tl_b[0], br_b[1] - cap_h_px / 2.0)
                br_bot = (br_b[0], br_b[1] + cap_h_px / 2.0)
                if f_col:
                    draw.pieslice([tl_bot, br_bot], start=0, end=180, fill=f_col, outline=None)
                    draw.rectangle([tl_b, br_b], fill=f_col, outline=None)
                if outline_col:
                    draw.arc([tl_bot, br_bot], start=0, end=180, fill=outline_col, width=border_w)
                    draw.line([(tl_b[0], tl_b[1]), (tl_b[0], br_b[1])], fill=outline_col, width=border_w)
                    draw.line([(br_b[0], tl_b[1]), (br_b[0], br_b[1])], fill=outline_col, width=border_w)
                tl_top = (tl_b[0], tl_b[1] - cap_h_px / 2.0)
                br_top = (br_b[0], tl_b[1] + cap_h_px / 2.0)
                draw.ellipse([tl_top, br_top], fill=f_col, outline=outline_col, width=border_w)
            elif _is_axis_aligned_rect(raw_local_pts, w, h) or (not geom_pts and w > 0 and h > 0):
                tl = to_img(pin_x - w / 2.0, pin_y + h / 2.0)
                br = to_img(pin_x + w / 2.0, pin_y - h / 2.0)
                if line_pat in ('2', '3', '4', '16', '23'):
                    draw_dashed_rect(draw, tl, br, fill=f_col, outline=outline_col, width=border_w)
                elif rounding_val > 0:
                    max_r = int(min(w, h) * dpi * 0.5)
                    px_radius = max(2, min(int(rounding_val * dpi), max_r))
                    draw.rounded_rectangle([tl, br], radius=px_radius, fill=f_col, outline=outline_col, width=border_w)
                else:
                    draw.rectangle([tl, br], fill=f_col, outline=outline_col, width=border_w)
                # Render any secondary stroke sections (e.g. Subroutine vertical bars)
                if len(geom_sections) > 1 and outline_col:
                    for extra_sec in geom_sections[1:]:
                        pts_extra = []
                        for r in extra_sec.findall('{*}Row'):
                            rc = {
                                c.attrib.get('N'): float(c.attrib.get('V', 0))
                                for c in r.findall('{*}Cell')
                                if c.attrib.get('N') in ('X', 'Y')
                            }
                            if 'X' in rc and 'Y' in rc:
                                pts_extra.append(to_img(pin_x - w / 2.0 + rc['X'], pin_y - h / 2.0 + rc['Y']))
                        if len(pts_extra) >= 2:
                            draw.line(pts_extra, fill=outline_col, width=border_w)
            elif geom_pts and len(geom_pts) >= 3:
                # Polygon or custom shape (diamond, hexagon, asymmetric, parallelogram, pie wedge, etc.)
                draw.polygon(geom_pts, fill=f_col, outline=outline_col, width=border_w)
            elif len(geom_pts) == 2 and outline_col:
                if line_pat in ('2', '3', '4', '16', '23'):
                    draw_dashed_line(draw, geom_pts[0], geom_pts[1], fill=outline_col, width=border_w)
                else:
                    draw.line([geom_pts[0], geom_pts[1]], fill=outline_col, width=border_w)

        # 3. Text Label
        text_elem = shape.find('{*}Text')
        if text_elem is not None:
            raw_text = ''.join(text_elem.itertext()).strip()
            if raw_text:
                char_col = '#0f172a'
                pt_size = 8.5 if is_conn else 10.0
                is_bold = is_container
                char_sec = shape.find(".//{*}Section[@N='Character']")
                if char_sec is not None:
                    c_cell = char_sec.find(".//{*}Cell[@N='Color']")
                    if c_cell is not None and c_cell.attrib.get('V'):
                        char_col = c_cell.attrib.get('V')
                    s_cell = char_sec.find(".//{*}Cell[@N='Size']")
                    if s_cell is not None and s_cell.attrib.get('V'):
                        try:
                            pt_size = float(s_cell.attrib.get('V')) * 72.0
                        except (ValueError, TypeError):
                            pass
                    st_cell = char_sec.find(".//{*}Cell[@N='Style']")
                    if st_cell is not None and st_cell.attrib.get('V'):
                        try:
                            is_bold = (int(st_cell.attrib.get('V')) & 1) != 0
                        except (ValueError, TypeError):
                            pass

                horz_align = '1'
                para_sec = shape.find(".//{*}Section[@N='Paragraph']")
                if para_sec is not None:
                    ha_cell = para_sec.find(".//{*}Cell[@N='HorzAlign']")
                    if ha_cell is not None and ha_cell.attrib.get('V') is not None:
                        horz_align = ha_cell.attrib.get('V')

                chosen_font = get_font(pt_size, is_bold)

                try:
                    txt_px = float(cells.get('TxtPinX', w * 0.5))
                    txt_py = float(cells.get('TxtPinY', h * 0.5))
                    if is_conn:
                        bx = float(cells.get('BeginX', pin_x - w * 0.5))
                        by = float(cells.get('BeginY', pin_y - h * 0.5))
                        ex = float(cells.get('EndX', pin_x + w * 0.5))
                        ey = float(cells.get('EndY', pin_y + h * 0.5))
                        txt_gx = min(bx, ex) + txt_px
                        txt_gy = min(by, ey) + txt_py
                    else:
                        txt_gx = pin_x - w / 2.0 + txt_px
                        txt_gy = pin_y - h / 2.0 + txt_py
                    center_pt = to_img(txt_gx, txt_gy)
                except (ValueError, TypeError):
                    center_pt = to_img(pin_x, pin_y)

                lines = raw_text.split('\n')
                line_widths = []
                line_heights = []
                for ln in lines:
                    bb = draw.textbbox((0, 0), ln, font=chosen_font)
                    line_widths.append(bb[2] - bb[0])
                    line_heights.append(max(10, bb[3] - bb[1]))

                total_th = sum(line_heights) + (len(lines) - 1) * 4
                max_tw = max(line_widths) if line_widths else 0

                if is_conn:
                    pad = 4
                    txt_bg = cells.get('TextBkgnd', '#ffffff')
                    if not txt_bg or not txt_bg.startswith('#'):
                        txt_bg = '#ffffff'
                    draw.rectangle(
                        [center_pt[0] - max_tw / 2 - pad, center_pt[1] - total_th / 2 - pad,
                         center_pt[0] + max_tw / 2 + pad, center_pt[1] + total_th / 2 + pad],
                        fill=txt_bg, outline='#cbd5e1'
                    )

                curr_y = center_pt[1] - total_th / 2.0
                left_x_px = (pin_x - w / 2.0 + 0.10) * dpi
                for idx_ln, ln in enumerate(lines):
                    tw = line_widths[idx_ln]
                    th = line_heights[idx_ln]
                    if not is_conn and horz_align == '0' and w > 0.4:
                        tx = left_x_px
                    else:
                        tx = center_pt[0] - tw / 2.0
                    draw.text((tx, curr_y), ln, fill=char_col, font=chosen_font)
                    curr_y += th + 4

    img.save(output_image_path, "PNG")
    elapsed = time.time() - start_time
    file_size_kb = round(os.path.getsize(output_image_path) / 1024, 1)

    return {
        "success": True,
        "vsdx_path": abs_vsdx,
        "image_path": output_image_path,
        "width": img_w,
        "height": img_h,
        "file_size_kb": file_size_kb,
        "render_time_sec": round(elapsed, 3),
        "engine": "native_pillow"
    }
