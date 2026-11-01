"""
Visio Compiler for Mermaid Gantt Charts (`gantt`).
Renders an executive Project Schedule chart with a title banner, status legend,
left-hand section/task column, vertical timeline gridlines, rounded status-coded task bars,
and diamond milestone markers.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from ..parser.ast_nodes import GanttDiagram, GanttTask
from ..visio.palettes import (
    DEFAULT_PALETTE_NAME,
    get_contrasting_text_color,
    get_palette,
    is_dark_color,
)
from .opc_package import package_vsdx
from .shapesheet import build_1d_connector_xml, build_2d_shape_xml


def _try_anchor_date(tasks: List[GanttTask]) -> Optional[datetime]:
    for t in tasks:
        raw = (t.start_raw or "").strip().replace("/", "-")
        parts = raw.split("-")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            try:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass
    return None


def compile_gantt_to_vsdx(
    diagram: GanttDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a GanttDiagram AST into a native Microsoft Visio (.vsdx) file.
    """
    palette = get_palette(palette_name)
    dark_mode = is_dark_color(palette.background)

    tasks = diagram.tasks or [
        GanttTask(id="t1", name="Project Kickoff", section="Planning", status="done", start_idx=0.0, duration=3.0)
    ]

    # Build display rows: interleave section header rows when section changes
    display_rows: List[Tuple[str, Optional[GanttTask], str]] = []
    last_section = None
    for t in tasks:
        if t.section and t.section != last_section:
            display_rows.append(("section", None, t.section))
            last_section = t.section
        display_rows.append(("task", t, t.section))

    num_rows = len(display_rows)
    max_span = max((t.start_idx + (0.5 if t.is_milestone else t.duration) for t in tasks), default=10.0)
    max_span = max(4.0, max_span)

    margin_x = 0.70
    label_col_w = 2.65
    chart_w = 7.40
    row_h = 0.48
    header_bar_h = 0.44
    title_space = 0.72 if diagram.title else 0.15

    page_w = round(margin_x * 2 + label_col_w + chart_w, 2)
    table_h = header_bar_h + num_rows * row_h
    page_h = round(max(6.0, table_h + title_space + 1.35), 2)

    table_left = margin_x
    chart_left = round(table_left + label_col_w, 4)
    chart_right = round(chart_left + chart_w, 4)
    table_top = round(page_h - title_space - 0.65, 4)
    table_bottom = round(table_top - table_h, 4)

    # Status color mapping: (bar_fill, bar_border, bar_text)
    if dark_mode:
        status_colors: Dict[str, Tuple[str, str, str]] = {
            "done": ("#065f46", "#34d399", "#f8fafc"),       # Emerald
            "active": ("#1e40af", "#38bdf8", "#f8fafc"),     # Sky Blue
            "crit": ("#991b1b", "#f87171", "#f8fafc"),       # Crimson Red
            "milestone": ("#92400e", "#fbbf24", "#f8fafc"),  # Gold
            "": ("#334155", "#94a3b8", "#f8fafc"),           # Default Slate
        }
    else:
        status_colors = {
            "done": ("#d1fae5", "#059669", "#064e3b"),       # Emerald
            "active": ("#dbeafe", "#2563eb", "#1e3a8a"),     # Royal Blue
            "crit": ("#fee2e2", "#dc2626", "#7f1d1d"),       # Crimson Red
            "milestone": ("#fef3c7", "#d97706", "#78350f"),  # Amber Gold
            "": (palette.default_fill, palette.default_border, palette.default_text),
        }

    shapes_xml_list: List[str] = []
    shape_id_counter = 1

    # 1. Optional Title Banner & Status Legend Pills
    if diagram.title:
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name="Gantt_Title",
                pin_x=round(table_left + 3.2, 4),
                pin_y=round(page_h - 0.52, 4),
                width=round(min(6.2, max(3.6, len(diagram.title) * 0.13 + 0.9)), 4),
                height=0.46,
                text=diagram.title,
                shape_type="rounded",
                fill_color=palette.subgraph_fill,
                line_color=palette.subgraph_border,
                text_color=palette.default_text,
                font_name=font_name,
                font_size_pt=13.5,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    legend_items = [
        ("Done", "done"),
        ("Active", "active"),
        ("Critical", "crit"),
        ("Milestone", "milestone"),
    ]
    for l_idx, (l_name, l_key) in enumerate(legend_items):
        lf, lb, lt = status_colors[l_key]
        lx = round(chart_right - (len(legend_items) - 1 - l_idx) * 1.02 - 0.46, 4)
        ly = round(page_h - 0.52, 4)
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"Gantt_Legend_{l_key}",
                pin_x=lx,
                pin_y=ly,
                width=0.92,
                height=0.30,
                text=l_name,
                shape_type="stadium",
                fill_color=lf,
                line_color=lb,
                text_color=lt,
                line_weight_in=0.015,
                font_name=font_name,
                font_size_pt=8.0,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    # 2. Outer Schedule Container Card
    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Container_Gantt_Schedule",
            pin_x=round((table_left + chart_right) * 0.5, 4),
            pin_y=round((table_top + table_bottom) * 0.5, 4),
            width=round(label_col_w + chart_w, 4),
            height=round(table_h, 4),
            text="",
            shape_type="rounded",
            fill_color=palette.subgraph_fill,
            line_color=palette.subgraph_border,
            rounding_in=0.12,
            is_container=True,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    # 3. Top Header Bar (Task Column Header + Timeline Axis Ticks)
    hdr_y = round(table_top - header_bar_h * 0.5, 4)
    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Subgraph_Header_TaskCol",
            pin_x=round(table_left + label_col_w * 0.5, 4),
            pin_y=hdr_y,
            width=label_col_w,
            height=header_bar_h,
            text="Task / Phase",
            shape_type="rectangle",
            fill_color=palette.default_fill,
            line_color=palette.subgraph_border,
            text_color=palette.default_text,
            font_name=font_name,
            font_size_pt=9.5,
            bold=True,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    shapes_xml_list.append(
        build_2d_shape_xml(
            shape_id=shape_id_counter,
            name="Subgraph_Header_TimelineAxis",
            pin_x=round(chart_left + chart_w * 0.5, 4),
            pin_y=hdr_y,
            width=chart_w,
            height=header_bar_h,
            text="",
            shape_type="rectangle",
            fill_color=palette.default_fill,
            line_color=palette.subgraph_border,
            has_connections=False,
        )
    )
    shape_id_counter += 1

    # 4. Vertical Timeline Gridlines & Tick Labels
    num_ticks = 6
    anchor_dt = _try_anchor_date(tasks)
    usable_pad_left = 0.22
    usable_pad_right = 0.32
    usable_chart_w = chart_w - usable_pad_left - usable_pad_right

    for tick_i in range(num_ticks + 1):
        frac = tick_i / float(num_ticks)
        day_val = frac * max_span
        gx = round(chart_left + usable_pad_left + frac * usable_chart_w, 4)

        # Vertical dashed gridline
        shapes_xml_list.append(
            build_1d_connector_xml(
                connector_id=shape_id_counter,
                begin_x=gx,
                begin_y=round(table_top - header_bar_h, 4),
                end_x=gx,
                end_y=table_bottom,
                line_color=palette.subgraph_border,
                line_weight_in=0.012,
                line_pattern=2,
                begin_arrow=0,
                end_arrow=0,
                is_dynamic=False,
            )
        )
        shape_id_counter += 1

        if anchor_dt is not None:
            tick_dt = anchor_dt + timedelta(days=int(round(day_val)))
            tick_label = tick_dt.strftime("%b %d")
        else:
            tick_label = f"D+{int(round(day_val))}"

        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"Gantt_Tick_{tick_i}",
                pin_x=gx,
                pin_y=hdr_y,
                width=0.82,
                height=0.30,
                text=tick_label,
                shape_type="rectangle",
                fill_pattern=0,
                line_pattern=0,
                text_color=palette.default_text,
                font_name=font_name,
                font_size_pt=8.5,
                bold=True,
                has_connections=False,
            )
        )
        shape_id_counter += 1

    # 5. Render Section Bands, Task Labels, Task Bars & Milestones
    for r_idx, (r_kind, task_obj, sec_title) in enumerate(display_rows):
        ry = round(table_top - header_bar_h - (r_idx + 0.5) * row_h, 4)

        if r_kind == "section":
            sec_fill = "#1e293b" if dark_mode else "#e2e8f0"
            sec_text = get_contrasting_text_color(sec_fill, palette.default_text)
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Subgraph_Header_GanttSec_{r_idx}",
                    pin_x=round((table_left + chart_right) * 0.5, 4),
                    pin_y=ry,
                    width=round(label_col_w + chart_w - 0.04, 4),
                    height=round(row_h - 0.04, 4),
                    text=f"▸  {sec_title}",
                    shape_type="rectangle",
                    fill_color=sec_fill,
                    line_color=palette.subgraph_border,
                    text_color=sec_text,
                    font_name=font_name,
                    font_size_pt=9.5,
                    align_left=True,
                    bold=True,
                    has_connections=False,
                )
            )
            shape_id_counter += 1
            continue

        assert task_obj is not None
        # Left column task label cell
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=shape_id_counter,
                name=f"Gantt_TaskLabel_{r_idx}",
                pin_x=round(table_left + label_col_w * 0.5, 4),
                pin_y=ry,
                width=round(label_col_w - 0.08, 4),
                height=round(row_h - 0.04, 4),
                text=task_obj.name,
                shape_type="rectangle",
                fill_pattern=0,
                line_pattern=0,
                text_color=palette.default_text,
                font_name=font_name,
                font_size_pt=9.0,
                align_left=True,
                bold=(task_obj.status == "crit" or task_obj.is_milestone),
                has_connections=False,
            )
        )
        shape_id_counter += 1

        # Task Bar or Milestone Diamond
        x_start = chart_left + usable_pad_left + (task_obj.start_idx / max_span) * usable_chart_w

        if task_obj.is_milestone:
            mf, mb, mt = status_colors["milestone"]
            ms_size = 0.30
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Gantt_Milestone_{r_idx}",
                    pin_x=round(x_start, 4),
                    pin_y=ry,
                    width=ms_size,
                    height=ms_size,
                    text="",
                    shape_type="diamond",
                    fill_color=mf,
                    line_color=mb,
                    line_weight_in=0.022,
                    has_connections=False,
                    shadow=True,
                )
            )
            shape_id_counter += 1

            # Milestone badge label to the right of the diamond
            ms_lbl = f"★ {task_obj.name}"
            ms_bw = round(min(2.2, max(1.0, len(ms_lbl) * 0.08 + 0.25)), 4)
            ms_bx = round(min(chart_right - ms_bw * 0.5 - 0.08, x_start + ms_size * 0.5 + ms_bw * 0.5 + 0.10), 4)
            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Badge_Milestone_{r_idx}",
                    pin_x=ms_bx,
                    pin_y=ry,
                    width=ms_bw,
                    height=0.28,
                    text=ms_lbl,
                    shape_type="stadium",
                    fill_color=mf,
                    line_color=mb,
                    text_color=mt,
                    line_weight_in=0.014,
                    font_name=font_name,
                    font_size_pt=8.0,
                    bold=True,
                    has_connections=False,
                )
            )
            shape_id_counter += 1
        else:
            bf, bb, bt = status_colors.get(task_obj.status, status_colors[""])
            bar_w = max(0.42, (task_obj.duration / max_span) * usable_chart_w)
            bar_cx = round(x_start + bar_w * 0.5, 4)
            bar_h = round(row_h * 0.66, 4)

            dur_num = int(round(task_obj.duration)) if abs(task_obj.duration - round(task_obj.duration)) < 0.1 else round(task_obj.duration, 1)
            bar_text = f"{task_obj.name} ({dur_num}d)" if bar_w >= 1.45 else f"{dur_num}d"

            shapes_xml_list.append(
                build_2d_shape_xml(
                    shape_id=shape_id_counter,
                    name=f"Gantt_Bar_{r_idx}",
                    pin_x=bar_cx,
                    pin_y=ry,
                    width=round(bar_w, 4),
                    height=bar_h,
                    text=bar_text,
                    shape_type="rounded",
                    fill_color=bf,
                    line_color=bb,
                    text_color=get_contrasting_text_color(bf, bt),
                    line_weight_in=0.020,
                    rounding_in=0.08,
                    font_name=font_name,
                    font_size_pt=8.5,
                    bold=True,
                    has_connections=False,
                    shadow=True,
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
