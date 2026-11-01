"""
Visio Compiler for Mermaid Timeline Diagrams (`timeline`).
Renders an executive horizontal timeline backbone arrow, section banner headers,
milestone nodes on the axis, and vertically stacked event cards with dynamic connectors.
"""

from typing import Dict, List, Tuple
from ..parser.ast_nodes import TimelineDiagram, TimelinePeriod
from ..visio.palettes import (
    DEFAULT_PALETTE_NAME,
    get_contrasting_text_color,
    get_palette,
    is_dark_color,
)
from .opc_package import package_vsdx
from .shapesheet import (
    build_1d_connector_xml,
    build_2d_shape_xml,
    build_connect_records,
)


_LIGHT_SECTION_THEMES = [
    # (period_fill, event_fill, border, text, banner_fill)
    ("#dbeafe", "#eff6ff", "#2563eb", "#1e3a8a", "#bfdbfe"),
    ("#d1fae5", "#ecfdf5", "#059669", "#064e3b", "#a7f3d0"),
    ("#fef3c7", "#fffbeb", "#d97706", "#78350f", "#fde68a"),
    ("#f3e8ff", "#faf5ff", "#9333ea", "#581c87", "#e9d5ff"),
    ("#ffe4e6", "#fff1f2", "#e11d48", "#881337", "#fecdd3"),
    ("#ccfbf1", "#f0fdfa", "#0d9488", "#134e4a", "#99f6e4"),
]

_DARK_SECTION_THEMES = [
    ("#1e3a8a", "#172554", "#38bdf8", "#f8fafc", "#1e40af"),
    ("#064e3b", "#022c22", "#34d399", "#f8fafc", "#065f46"),
    ("#78350f", "#451a03", "#fbbf24", "#f8fafc", "#92400e"),
    ("#581c87", "#3b0764", "#c084fc", "#f8fafc", "#6b21a8"),
    ("#881337", "#4c0519", "#fb7185", "#f8fafc", "#9f1239"),
    ("#134e4a", "#042f2e", "#2dd4bf", "#f8fafc", "#115e59"),
]


def compile_timeline_to_vsdx(
    diagram: TimelineDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a TimelineDiagram AST into a native Microsoft Visio (.vsdx) file.
    """
    palette = get_palette(palette_name)
    dark_mode = is_dark_color(palette.background)
    themes = _DARK_SECTION_THEMES if dark_mode else _LIGHT_SECTION_THEMES

    periods = diagram.periods or [TimelinePeriod(period="2026", events=["Milestone"])]
    num_periods = len(periods)
    has_sections = any(bool(p.section) for p in periods)
    max_events = max((len(p.events) for p in periods), default=1)

    col_w = 2.05
    col_gap = 0.48
    period_w = 1.85
    period_h = 0.62
    event_w = 1.88
    event_h = 0.66
    event_v_gap = 0.34
    margin_x = 0.95
    margin_bottom = 0.85

    total_cols_w = num_periods * col_w + max(0, num_periods - 1) * col_gap
    page_w = round(max(11.0, total_cols_w + 2 * margin_x), 2)

    events_stack_h = max_events * (event_h + event_v_gap) + 0.25
    section_space = 0.85 if has_sections else 0.0
    title_space = 0.75 if diagram.title else 0.0
    page_h = round(max(6.5, margin_bottom + events_stack_h + period_h + section_space + title_space + 0.9), 2)

    start_x = (page_w - total_cols_w) * 0.5 + col_w * 0.5
    axis_y = round(page_h - title_space - section_space - 1.05, 4)

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1

    # 1. Optional Title Banner
    if diagram.title:
        title_sid = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=title_sid,
                name="Timeline_Title",
                pin_x=round(page_w * 0.5, 4),
                pin_y=round(page_h - 0.52, 4),
                width=round(min(page_w - 1.2, max(4.5, len(diagram.title) * 0.14 + 1.2)), 4),
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

    # 2. Group contiguous section runs and render section headers & container backdrops
    section_runs: List[Tuple[str, int, int, int]] = []
    if has_sections:
        cur_sec = periods[0].section
        run_start = 0
        sec_idx = 0
        for i in range(1, num_periods):
            if periods[i].section != cur_sec:
                section_runs.append((cur_sec, run_start, i - 1, sec_idx))
                cur_sec = periods[i].section
                run_start = i
                sec_idx += 1
        section_runs.append((cur_sec, run_start, num_periods - 1, sec_idx))

        for sec_name, idx_start, idx_end, s_idx in section_runs:
            if not sec_name:
                continue
            _, _, s_border, s_text, s_banner = themes[s_idx % len(themes)]
            x_left = start_x + idx_start * (col_w + col_gap) - col_w * 0.5 - 0.12
            x_right = start_x + idx_end * (col_w + col_gap) + col_w * 0.5 + 0.12
            span_w = round(x_right - x_left, 4)
            span_cx = round((x_left + x_right) * 0.5, 4)

            # Section backdrop container
            lowest_y = axis_y - period_h * 0.5 - max(
                (len(periods[k].events) for k in range(idx_start, idx_end + 1)), default=0
            ) * (event_h + event_v_gap) - 0.22
            top_y = axis_y + period_h * 0.5 + 0.72
            box_h = round(top_y - lowest_y, 4)
            box_cy = round((top_y + lowest_y) * 0.5, 4)

            bg_sid = shape_id_counter
            shape_id_counter += 1
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=bg_sid,
                    name=f"Container_Section_{s_idx}",
                    pin_x=span_cx,
                    pin_y=box_cy,
                    width=span_w,
                    height=box_h,
                    text="",
                    shape_type="rounded",
                    fill_color=palette.subgraph_fill,
                    line_color=s_border,
                    line_pattern=2,
                    rounding_in=0.14,
                    is_container=True,
                    has_connections=False,
                )
            )

            hdr_sid = shape_id_counter
            shape_id_counter += 1
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=hdr_sid,
                    name=f"Subgraph_Header_Section_{s_idx}",
                    pin_x=span_cx,
                    pin_y=round(axis_y + period_h * 0.5 + 0.44, 4),
                    width=round(span_w - 0.16, 4),
                    height=0.38,
                    text=sec_name,
                    shape_type="rounded",
                    fill_color=s_banner,
                    line_color=s_border,
                    text_color=get_contrasting_text_color(s_banner, s_text),
                    rounding_in=0.10,
                    font_name=font_name,
                    font_size_pt=10.5,
                    bold=True,
                    has_connections=False,
                )
            )

    # Map each period index to a theme index
    period_theme_idx: Dict[int, int] = {}
    if has_sections:
        for _, idx_start, idx_end, s_idx in section_runs:
            for k in range(idx_start, idx_end + 1):
                period_theme_idx[k] = s_idx
    else:
        for k in range(num_periods):
            period_theme_idx[k] = k

    # 3. Horizontal Timeline Backbone Arrow
    backbone_id = shape_id_counter
    shape_id_counter += 1
    bb_start_x = round(start_x - col_w * 0.55, 4)
    bb_end_x = round(start_x + (num_periods - 1) * (col_w + col_gap) + col_w * 0.65, 4)
    shapes_xml_list.append(
        build_1d_connector_xml(
            connector_id=backbone_id,
            begin_x=bb_start_x,
            begin_y=axis_y,
            end_x=bb_end_x,
            end_y=axis_y,
            label="",
            line_color=palette.connector_line,
            line_weight_in=0.032,
            line_pattern=1,
            begin_arrow=0,
            end_arrow=13,
            end_arrow_size=3,
            font_name=font_name,
            is_dynamic=False,
        )
    )

    # 4. Period Milestone Nodes & Stacked Event Cards
    for p_idx, p_item in enumerate(periods):
        px = round(start_x + p_idx * (col_w + col_gap), 4)
        t_idx = period_theme_idx.get(p_idx, p_idx)
        p_fill, ev_fill, s_border, s_text, _ = themes[t_idx % len(themes)]

        period_sid = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=period_sid,
                name=f"TimelinePeriod_{p_idx}",
                pin_x=px,
                pin_y=axis_y,
                width=period_w,
                height=period_h,
                text=p_item.period,
                shape_type="stadium",
                fill_color=p_fill,
                line_color=s_border,
                text_color=get_contrasting_text_color(p_fill, s_text),
                line_weight_in=0.025,
                font_name=font_name,
                font_size_pt=10.5,
                bold=True,
                has_connections=True,
                shadow=True,
            )
        )

        prev_sid = period_sid
        prev_y = axis_y
        prev_h = period_h

        for ev_idx, ev_text in enumerate(p_item.events):
            ev_y = round(axis_y - (period_h * 0.5) - (ev_idx + 0.5) * event_h - (ev_idx + 1) * event_v_gap, 4)
            ev_sid = shape_id_counter
            shape_id_counter += 1
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=ev_sid,
                    name=f"TimelineEvent_{p_idx}_{ev_idx}",
                    pin_x=px,
                    pin_y=ev_y,
                    width=event_w,
                    height=event_h,
                    text=ev_text,
                    shape_type="rounded",
                    fill_color=ev_fill,
                    line_color=s_border,
                    text_color=get_contrasting_text_color(ev_fill, palette.default_text),
                    line_weight_in=0.018,
                    rounding_in=0.10,
                    font_name=font_name,
                    font_size_pt=9.5,
                    bold=False,
                    has_connections=True,
                    shadow=True,
                )
            )

            conn_sid = shape_id_counter
            shape_id_counter += 1
            bx = px
            by = round(prev_y - prev_h * 0.5, 4)
            ex = px
            ey = round(ev_y + event_h * 0.5, 4)

            shapes_xml_list.append(
                build_1d_connector_xml(
                    connector_id=conn_sid,
                    begin_x=bx,
                    begin_y=by,
                    end_x=ex,
                    end_y=ey,
                    label="",
                    line_color=s_border,
                    line_weight_in=0.018,
                    line_pattern=2 if ev_idx == 0 else 1,
                    begin_arrow=0,
                    end_arrow=13,
                    font_name=font_name,
                    is_dynamic=True,
                    source_shape_id=prev_sid,
                    target_shape_id=ev_sid,
                    src_port="Bottom",
                    dst_port="Top",
                    routing_direction="TD",
                )
            )
            connects_xml_list.append(
                build_connect_records(
                    connector_id=conn_sid,
                    source_shape_id=prev_sid,
                    target_shape_id=ev_sid,
                    src_port="Bottom",
                    dst_port="Top",
                    src_part=101,
                    dst_part=100,
                )
            )

            prev_sid = ev_sid
            prev_y = ev_y
            prev_h = event_h

    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=page_w,
        page_height=page_h,
        page_bg_color=palette.background,
    )
