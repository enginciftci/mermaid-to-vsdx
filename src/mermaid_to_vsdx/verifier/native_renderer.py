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
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont


def draw_dashed_line(draw: ImageDraw.ImageDraw, p1, p2, fill, width, dash_len=8, gap_len=5):
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
    font_main = None
    font_bold = None
    font_sm = None
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                font_main = ImageFont.truetype(fp, max(11, int(9.5 * dpi / 72)))
                bold_fp = fp.replace("segoeui", "segoeuib").replace("arial", "arialbd")
                font_bold = ImageFont.truetype(bold_fp if os.path.exists(bold_fp) else fp, max(12, int(10.0 * dpi / 72)))
                font_sm = ImageFont.truetype(fp, max(9, int(8.0 * dpi / 72)))
                break
            except Exception:
                continue

    if not font_main:
        font_main = ImageFont.load_default()
        font_bold = font_main
        font_sm = font_main

    def to_img(x_in: float, y_in: float):
        return (x_in * dpi, (ph_in - y_in) * dpi)

    shapes_to_render = []

    def collect_shapes(shape_elem, parent_ox=0.0, parent_oy=0.0):
        name_u = shape_elem.attrib.get('NameU', '')
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

    # Layering order: Containers first, 2D shapes next, Connectors on top
    def shape_sort_key(s_info):
        nu = s_info['name_u'].lower()
        if 'container' in nu or 'subgraph' in nu or 'loop' in nu or 'block' in nu:
            return 0
        elif 'connector' in nu or 'line' in nu or 'message' in nu:
            return 2
        return 1

    shapes_to_render.sort(key=shape_sort_key)

    for s_info in shapes_to_render:
        shape = s_info['elem']
        name_u = s_info['name_u']
        cells = s_info['cells']
        pin_x = s_info['pin_x']
        pin_y = s_info['pin_y']
        w = s_info['w']
        h = s_info['h']

        fill_col = cells.get('FillForegnd', '#ffffff')
        line_col = cells.get('LineColor', '#334155')
        fill_pat = int(cells.get('FillPattern', '1') or '1')
        line_pat = cells.get('LinePattern', '1')
        is_conn = 'connector' in name_u.lower() or 'line' in name_u.lower() or 'message' in name_u.lower()
        is_container = 'container' in name_u.lower() or 'subgraph' in name_u.lower() or 'loop' in name_u.lower() or 'block' in name_u.lower()

        # Extract Geometry points
        geom_sec = shape.find(".//{*}Section[@N='Geometry']")
        geom_pts = []
        if geom_sec is not None:
            for r in geom_sec.findall('{*}Row'):
                rcells = {c.attrib.get('N'): float(c.attrib.get('V', 0)) for c in r.findall('{*}Cell') if c.attrib.get('N') in ('X', 'Y')}
                if 'X' in rcells and 'Y' in rcells:
                    rx = rcells['X']
                    ry = rcells['Y']
                    gx = pin_x - w / 2.0 + rx
                    gy = pin_y - h / 2.0 + ry
                    geom_pts.append(to_img(gx, gy))

        # 1. Connectors (1D)
        if is_conn:
            line_w = max(2, int(0.018 * dpi))
            if len(geom_pts) >= 2:
                for i in range(len(geom_pts) - 1):
                    if line_pat in ('2', '3'):
                        draw_dashed_line(draw, geom_pts[i], geom_pts[i+1], fill=line_col, width=line_w)
                    else:
                        draw.line([geom_pts[i], geom_pts[i+1]], fill=line_col, width=line_w)

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

            if is_container:
                tl = to_img(pin_x - w/2.0, pin_y + h/2.0)
                br = to_img(pin_x + w/2.0, pin_y - h/2.0)
                if line_pat in ('2', '3'):
                    draw_dashed_rect(draw, tl, br, fill=f_col, outline=line_col, width=border_w)
                else:
                    draw.rounded_rectangle([tl, br], radius=8, fill=f_col, outline=line_col, width=border_w)
            elif geom_pts and len(geom_pts) >= 3:
                # Polygon or custom shape (diamond, hexagon, cylinder, etc.)
                draw.polygon(geom_pts, fill=f_col, outline=line_col)
            elif w > 0 and h > 0:
                tl = to_img(pin_x - w/2.0, pin_y + h/2.0)
                br = to_img(pin_x + w/2.0, pin_y - h/2.0)
                if line_pat in ('2', '3'):
                    draw_dashed_rect(draw, tl, br, fill=f_col, outline=line_col, width=border_w)
                else:
                    draw.rounded_rectangle([tl, br], radius=6, fill=f_col, outline=line_col, width=border_w)

        # 3. Text Label
        text_elem = shape.find('{*}Text')
        if text_elem is not None:
            raw_text = ''.join(text_elem.itertext()).strip()
            if raw_text:
                char_col = '#0f172a'
                char_sec = shape.find(".//{*}Section[@N='Character']")
                if char_sec is not None:
                    c_cell = char_sec.find(".//{*}Cell[@N='Color']")
                    if c_cell is not None and c_cell.attrib.get('V'):
                        char_col = c_cell.attrib.get('V')

                chosen_font = font_sm if is_conn else (font_bold if is_container else font_main)
                
                try:
                    txt_px = float(cells.get('TxtPinX', w * 0.5))
                    txt_py = float(cells.get('TxtPinY', h * 0.5))
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
                    line_heights.append(bb[3] - bb[1])

                total_th = sum(line_heights) + (len(lines) - 1) * 4
                max_tw = max(line_widths) if line_widths else 0

                if is_conn:
                    pad = 4
                    draw.rectangle(
                        [center_pt[0] - max_tw/2 - pad, center_pt[1] - total_th/2 - pad,
                         center_pt[0] + max_tw/2 + pad, center_pt[1] + total_th/2 + pad],
                        fill='#ffffff', outline='#cbd5e1'
                    )

                curr_y = center_pt[1] - total_th / 2.0
                for idx_ln, ln in enumerate(lines):
                    tw = line_widths[idx_ln]
                    th = line_heights[idx_ln]
                    draw.text((center_pt[0] - tw / 2.0, curr_y), ln, fill=char_col, font=chosen_font)
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
