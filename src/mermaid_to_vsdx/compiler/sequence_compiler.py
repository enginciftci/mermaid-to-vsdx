"""
Native headless compiler for Mermaid Sequence Diagrams.
Transforms SequenceDiagram AST into Open Packaging Conventions Visio XML.
"""

from typing import Dict, List, Tuple
from ..parser.ast_nodes import SequenceDiagram, Participant, Message, Note, MessageArrow
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
)
from .opc_package import package_vsdx


def compile_sequence_to_vsdx(
    diagram: SequenceDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    participants = diagram.participants
    num_p = max(1, len(participants))

    # Spacing parameters
    part_spacing = 2.4
    start_x = 1.2
    margin_top = 1.0 if not diagram.title else 1.6
    step_y = 0.8
    part_w = 1.6
    part_h = 0.6

    total_events = len(diagram.items)
    content_w = start_x + (num_p - 1) * part_spacing + part_w / 2.0 + 1.0
    content_h = margin_top + (total_events + 2) * step_y + part_h + 1.0

    page_width = max(8.5, round(content_w, 2))
    page_height = max(11.0, round(content_h, 2))

    shapes_xml_list: List[str] = []
    shape_id_counter = 1

    # Title shape (if present)
    if diagram.title:
        t_id = shape_id_counter
        shape_id_counter += 1
        t_w = max(3.0, len(diagram.title) * 0.12)
        t_h = 0.45
        t_pin_x = page_width / 2.0
        t_pin_y = page_height - 0.6
        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=t_id,
            name="DiagramTitle",
            pin_x=t_pin_x,
            pin_y=t_pin_y,
            width=t_w,
            height=t_h,
            text=diagram.title,
            shape_type="rectangle",
            fill_color=palette.subgraph_border,
            line_color=palette.subgraph_border,
            text_color=palette.subgraph_text,
            line_weight_in=0.01,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=11.0,
        ))

    # Participant X positions
    part_x: Dict[str, float] = {}
    for idx, p_obj in enumerate(participants):
        part_x[p_obj.id] = start_x + idx * part_spacing

    top_y = page_height - margin_top
    bottom_y = page_height - (margin_top + (total_events + 1) * step_y)

    # 1. Render Lifeline Dashed Connectors
    for p_obj in participants:
        line_id = shape_id_counter
        shape_id_counter += 1
        px = part_x[p_obj.id]
        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=line_id,
            begin_x=px,
            begin_y=top_y - part_h / 2.0,
            end_x=px,
            end_y=bottom_y + part_h / 2.0,
            line_color="#94a3b8",
            line_weight_in=0.015,
            line_pattern=2,  # Dashed lifeline
            begin_arrow=0,
            end_arrow=0,
            is_dynamic=False,
        ))

    # 2. Render Participant Boxes (Top and Bottom)
    for p_obj in participants:
        px = part_x[p_obj.id]

        # Top Box
        top_id = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=top_id,
            name=f"Participant_Top_{p_obj.id}",
            pin_x=px,
            pin_y=top_y,
            width=part_w,
            height=part_h,
            text=p_obj.label,
            shape_type="rounded",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
            line_weight_in=0.0208,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=10.0,
        ))

        # Bottom Box
        bot_id = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=bot_id,
            name=f"Participant_Bottom_{p_obj.id}",
            pin_x=px,
            pin_y=bottom_y,
            width=part_w,
            height=part_h,
            text=p_obj.label,
            shape_type="rounded",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
            line_weight_in=0.0208,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=10.0,
        ))

    # 3. Render Items (Messages and Notes) in order
    curr_y = top_y - step_y
    for item_idx, item in enumerate(diagram.items):
        if isinstance(item, Note):
            n_id = shape_id_counter
            shape_id_counter += 1

            if len(item.participant_ids) >= 2:
                p1 = item.participant_ids[0]
                p2 = item.participant_ids[1]
                x1 = part_x.get(p1, start_x)
                x2 = part_x.get(p2, start_x + part_spacing)
                n_x = (x1 + x2) / 2.0
                n_w = abs(x2 - x1) + 0.6
            elif len(item.participant_ids) == 1:
                p1 = item.participant_ids[0]
                n_x = part_x.get(p1, start_x)
                n_w = 1.8
            else:
                n_x = page_width / 2.0
                n_w = 2.0

            n_w, n_h, _ = estimate_text_dimensions(item.text, font_size_pt=9.0, min_width_in=n_w, min_height_in=0.5)

            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=n_id,
                name=f"Note_{item_idx}",
                pin_x=n_x,
                pin_y=curr_y,
                width=n_w,
                height=n_h,
                text=item.text,
                shape_type="rectangle",
                fill_color=palette.note_fill,
                line_color=palette.note_border,
                text_color="#ffffff" if is_dark_color(palette.note_fill) else palette.note_text,
                line_weight_in=0.015,
                font_name=font_name,
                font_size_pt=9.0,
            ))
            curr_y -= step_y

        elif isinstance(item, Message):
            m_id = shape_id_counter
            shape_id_counter += 1

            src_x = part_x.get(item.sender_id, start_x)
            dst_x = part_x.get(item.receiver_id, start_x + part_spacing)

            if item.sender_id == item.receiver_id:
                dst_x = src_x + 1.0

            line_pat = 1
            end_arr = 13
            if item.arrow_type in (MessageArrow.DOTTED_ARROW, MessageArrow.DOTTED_LINE, MessageArrow.DOTTED_CROSS):
                line_pat = 2
            if item.arrow_type in (MessageArrow.SOLID_CROSS, MessageArrow.DOTTED_CROSS):
                end_arr = 20
            elif item.arrow_type in (MessageArrow.SOLID_LINE, MessageArrow.DOTTED_LINE):
                end_arr = 0

            shapes_xml_list.append(build_1d_connector_xml(
                connector_id=m_id,
                begin_x=src_x,
                begin_y=curr_y,
                end_x=dst_x,
                end_y=curr_y,
                label=item.text,
                line_color=palette.connector_line,
                line_weight_in=0.018,
                line_pattern=line_pat,
                end_arrow=end_arr,
                font_name=font_name,
                font_size_pt=9.0,
                text_color=palette.connector_text,
                is_dynamic=False,
            ))
            curr_y -= step_y

    # 4. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="",
        page_width=page_width,
        page_height=page_height,
    )
