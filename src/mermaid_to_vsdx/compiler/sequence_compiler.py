"""
Native headless compiler for Mermaid Sequence Diagrams.
Transforms SequenceDiagram AST into Open Packaging Conventions Visio XML.
"""

from typing import Dict, List, Tuple, Union, Any, Optional
from ..parser.ast_nodes import (
    SequenceDiagram,
    Participant,
    Message,
    Note,
    MessageArrow,
    Activation,
    LoopBlock,
    ElseBranch,
)
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions, estimate_line_width_pt
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_self_loop_xml,
)
from .opc_package import package_vsdx


class LayoutEvent:
    def __init__(
        self,
        item: Any,
        y: float = 0.0,
        is_self: bool = False,
        top_y: float = 0.0,
        bottom_y: float = 0.0,
        left_x: float = 0.0,
        right_x: float = 0.0,
        children: Optional[List["LayoutEvent"]] = None,
        branch_events: Optional[List[Tuple[ElseBranch, float, List["LayoutEvent"]]]] = None,
    ):
        self.item = item
        self.y = y
        self.is_self = is_self
        self.top_y = top_y
        self.bottom_y = bottom_y
        self.left_x = left_x
        self.right_x = right_x
        self.children = children or []
        self.branch_events = branch_events or []


def _collect_pids(item: Any) -> List[str]:
    pids = []
    if isinstance(item, Message):
        pids.extend([item.sender_id, item.receiver_id])
    elif isinstance(item, Note):
        pids.extend(item.participant_ids)
    elif isinstance(item, Activation):
        pids.append(item.participant_id)
    elif isinstance(item, LoopBlock):
        for c in item.items:
            pids.extend(_collect_pids(c))
        for br in item.else_branches:
            for c in br.items:
                pids.extend(_collect_pids(c))
    return pids


def _has_self_message(item: LoopBlock) -> bool:
    for c in item.items:
        if isinstance(c, Message) and c.sender_id == c.receiver_id:
            return True
        if isinstance(c, LoopBlock) and _has_self_message(c):
            return True
    for br in item.else_branches:
        for c in br.items:
            if isinstance(c, Message) and c.sender_id == c.receiver_id:
                return True
            if isinstance(c, LoopBlock) and _has_self_message(c):
                return True
    return False


def _collect_all_messages_and_notes(items: List[Any], messages: List[Message], notes: List[Note]):
    for item in items:
        if isinstance(item, Message):
            messages.append(item)
        elif isinstance(item, Note):
            notes.append(item)
        elif isinstance(item, LoopBlock):
            _collect_all_messages_and_notes(item.items, messages, notes)
            for br in item.else_branches:
                _collect_all_messages_and_notes(br.items, messages, notes)


def _plan_layout(
    items: List[Any],
    curr_y: float,
    step_y: float,
    part_x: Dict[str, float],
    default_x: float,
    open_activations: Dict[str, List[float]],
    active_intervals: Dict[str, List[Tuple[float, float]]],
) -> Tuple[List[LayoutEvent], float]:
    events: List[LayoutEvent] = []

    for item in items:
        if isinstance(item, Message):
            y = curr_y
            is_self = (item.sender_id == item.receiver_id)
            if is_self:
                curr_y -= (0.40 + step_y * 0.75)
            else:
                curr_y -= step_y

            if item.activate:
                open_activations[item.receiver_id].append(y)
            if item.deactivate:
                target_p = item.sender_id if open_activations.get(item.sender_id) else item.receiver_id
                if open_activations.get(target_p):
                    start_act = open_activations[target_p].pop()
                    active_intervals[target_p].append((start_act, y))

            events.append(LayoutEvent(item=item, y=y, is_self=is_self))

        elif isinstance(item, Note):
            y = curr_y
            curr_y -= step_y
            events.append(LayoutEvent(item=item, y=y))

        elif isinstance(item, Activation):
            act_y = curr_y + step_y if events else curr_y
            if item.is_activate:
                open_activations[item.participant_id].append(act_y)
            else:
                if open_activations.get(item.participant_id):
                    start_act = open_activations[item.participant_id].pop()
                    active_intervals[item.participant_id].append((start_act, act_y))

        elif isinstance(item, LoopBlock):
            loop_top = curr_y + 0.20
            curr_y -= 0.42  # Extra top clearance after LoopBlock header so first message/self-loop never touches Badge_Loop
            child_events, curr_y = _plan_layout(
                item.items, curr_y, step_y, part_x, default_x, open_activations, active_intervals
            )

            branch_events: List[Tuple[ElseBranch, float, List[LayoutEvent]]] = []
            for br in item.else_branches:
                div_y = curr_y + step_y * 0.45
                curr_y -= 0.35
                br_children, curr_y = _plan_layout(
                    br.items, curr_y, step_y, part_x, default_x, open_activations, active_intervals
                )
                branch_events.append((br, div_y, br_children))

            loop_bottom = curr_y + 0.15
            curr_y -= 0.25  # Space after loop container

            pids = _collect_pids(item)
            coords = [part_x[p] for p in pids if p in part_x]
            if not coords:
                coords = list(part_x.values()) if part_x else [default_x]

            has_self = _has_self_message(item)
            lx = min(coords) - 0.45
            rx = max(coords) + (1.1 if has_self else 0.45)

            events.append(LayoutEvent(
                item=item,
                top_y=loop_top,
                bottom_y=loop_bottom,
                left_x=lx,
                right_x=rx,
                children=child_events,
                branch_events=branch_events,
            ))

    return events, curr_y


def compile_sequence_to_vsdx(
    diagram: SequenceDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    participants = diagram.participants
    num_p = max(1, len(participants))
    p_index_map = {p.id: idx for idx, p in enumerate(participants)}

    all_messages: List[Message] = []
    all_notes: List[Note] = []
    _collect_all_messages_and_notes(diagram.items, all_messages, all_notes)

    # Dynamic participant box width & spacing
    max_p_label_w = 1.6
    for p_obj in participants:
        p_lines = [
            "«actor»",
            p_obj.label,
        ] if p_obj.is_actor else [p_obj.label]
        w_pt = max(estimate_line_width_pt(line, font_size_pt=10.0, bold=True) for line in p_lines)
        max_p_label_w = max(max_p_label_w, round(w_pt / 72.0 + 0.45, 2))
    part_w = min(2.4, max_p_label_w)
    part_h = 0.65 if any(p.is_actor for p in participants) else 0.6

    max_needed_spacing = max(2.4, part_w + 0.5)
    for m_idx, msg in enumerate(all_messages, start=1):
        if msg.sender_id != msg.receiver_id and msg.sender_id in p_index_map and msg.receiver_id in p_index_map:
            span = max(1, abs(p_index_map[msg.receiver_id] - p_index_map[msg.sender_id]))
            msg_text = f"[{m_idx}] {msg.text}" if diagram.autonumber else msg.text
            msg_w_in = estimate_line_width_pt(msg_text, font_size_pt=9.0) / 72.0 + 0.55
            needed_per_span = msg_w_in / span
            if needed_per_span > max_needed_spacing:
                max_needed_spacing = min(4.2, round(needed_per_span, 2))

    part_spacing = max(2.4, max_needed_spacing)
    start_x = max(1.2, part_w / 2.0 + 0.5)

    # Check if any Note is placed "left of" a participant and expand start_x so it never clips left margin
    page_margin = 0.8
    for note in all_notes:
        if len(note.participant_ids) == 1 and "left" in note.placement.lower():
            p1 = note.participant_ids[0]
            if p1 in p_index_map:
                idx = p_index_map[p1]
                n_w, _, _ = estimate_text_dimensions(note.text, font_size_pt=9.0, min_width_in=1.8, min_height_in=0.5)
                # Ensure (start_x + idx * part_spacing - 1.35) - n_w / 2.0 >= page_margin
                req_start_x = page_margin + 1.35 + n_w / 2.0 - idx * part_spacing
                if req_start_x > start_x:
                    start_x = round(req_start_x, 2)

    margin_top = 1.0 if not diagram.title else 1.6
    step_y = 0.8

    part_x: Dict[str, float] = {}
    for idx, p_obj in enumerate(participants):
        part_x[p_obj.id] = round(start_x + idx * part_spacing, 4)

    # Track right-most extent including right-of notes and self-loops on rightmost participant
    max_x_used = start_x + (num_p - 1) * part_spacing + part_w / 2.0
    for note in all_notes:
        if len(note.participant_ids) == 1 and "right" in note.placement.lower():
            p1 = note.participant_ids[0]
            if p1 in part_x:
                n_w, _, _ = estimate_text_dimensions(note.text, font_size_pt=9.0, min_width_in=1.8, min_height_in=0.5)
                right_edge = part_x[p1] + 1.35 + n_w / 2.0
                if right_edge > max_x_used:
                    max_x_used = right_edge
    for msg in all_messages:
        if msg.sender_id == msg.receiver_id and msg.sender_id in part_x:
            msg_w_in = estimate_line_width_pt(msg.text, font_size_pt=9.0) / 72.0
            self_right = part_x[msg.sender_id] + 0.9 + msg_w_in
            if self_right > max_x_used:
                max_x_used = self_right

    # First layout simulation to determine total page height
    dummy_open = {p.id: [] for p in participants}
    dummy_intervals = {p.id: [] for p in participants}
    _, end_calc_y = _plan_layout(
        diagram.items, 0.0, step_y, part_x, start_x, dummy_open, dummy_intervals
    )
    total_content_height = abs(end_calc_y)

    content_w = max_x_used + 1.0
    content_h = margin_top + total_content_height + part_h + 1.2

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
            text_color="#ffffff" if is_dark_color(palette.subgraph_border) else palette.subgraph_text,
            line_weight_in=0.01,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=11.0,
            bold=True,
        ))

    top_y = page_height - margin_top

    # Actual layout placement
    open_activations: Dict[str, List[float]] = {p.id: [] for p in participants}
    active_intervals: Dict[str, List[Tuple[float, float]]] = {p.id: [] for p in participants}
    layout_events, final_y = _plan_layout(
        diagram.items, top_y - step_y, step_y, part_x, start_x, open_activations, active_intervals
    )
    bottom_y = final_y - 0.45

    # Close any unclosed activations
    for p_id, starts in open_activations.items():
        for start_act in starts:
            active_intervals[p_id].append((start_act, bottom_y + part_h / 2.0 + 0.1))

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

    # 2. Render Activation Bars
    for p_obj in participants:
        px = part_x[p_obj.id]
        intervals = active_intervals.get(p_obj.id, [])
        for act_idx, (start_act, end_act) in enumerate(intervals):
            act_bar_id = shape_id_counter
            shape_id_counter += 1
            bar_w = 0.16
            bar_h = max(0.2, abs(start_act - end_act))
            bar_y = (start_act + end_act) / 2.0
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=act_bar_id,
                name=f"Activation_{p_obj.id}_{act_idx}",
                pin_x=px,
                pin_y=round(bar_y, 4),
                width=bar_w,
                height=round(bar_h, 4),
                text="",
                shape_type="rectangle",
                fill_color=palette.decision_fill,
                line_color=palette.default_border,
                line_weight_in=0.015,
                has_connections=False,
            ))

    # 3. Render Participant Boxes (Top and Bottom)
    for p_obj in participants:
        px = part_x[p_obj.id]
        p_text = f"«actor»\n{p_obj.label}" if p_obj.is_actor else p_obj.label

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
            text=p_text,
            shape_type="rounded",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
            line_weight_in=0.0208,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=10.0,
            bold=True,
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
            text=p_text,
            shape_type="rounded",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
            line_weight_in=0.0208,
            rounding_in=0.08,
            font_name=font_name,
            font_size_pt=10.0,
            bold=True,
        ))

    # 4. Helper to render layout events
    msg_counter = 1

    def render_events(event_list: List[LayoutEvent]):
        nonlocal shape_id_counter, msg_counter
        for ev in event_list:
            if isinstance(ev.item, LoopBlock):
                box_id = shape_id_counter
                shape_id_counter += 1
                badge_id = shape_id_counter
                shape_id_counter += 1

                bw = ev.right_x - ev.left_x
                bh = ev.top_y - ev.bottom_y
                bpx = (ev.left_x + ev.right_x) / 2.0
                bpy = (ev.top_y + ev.bottom_y) / 2.0

                # Dashed container box (transparent fill so it NEVER whites out lifelines or activation bars)
                shapes_xml_list.append(build_2d_shape_xml(
                    shape_id=box_id,
                    name=f"Container_Loop_{box_id}",
                    pin_x=round(bpx, 4),
                    pin_y=round(bpy, 4),
                    width=round(bw, 4),
                    height=round(bh, 4),
                    text="",
                    shape_type="rectangle",
                    fill_color="#ffffff",
                    line_color=palette.subgraph_border,
                    line_weight_in=0.015,
                    line_pattern=2,
                    fill_pattern=0,
                    has_connections=False,
                ))

                # Header badge at top left (opaque fill)
                b_type = ev.item.block_type
                b_title = ev.item.title
                b_text = f"{b_type} [{b_title}]" if b_title else b_type
                badge_w = max(1.1, len(b_text) * 0.085 + 0.35)
                badge_h = 0.26
                shapes_xml_list.append(build_2d_shape_xml(
                    shape_id=badge_id,
                    name=f"Badge_Loop_{badge_id}",
                    pin_x=round(ev.left_x + badge_w / 2.0, 4),
                    pin_y=round(ev.top_y - badge_h / 2.0, 4),
                    width=round(badge_w, 4),
                    height=round(badge_h, 4),
                    text=b_text,
                    shape_type="rectangle",
                    fill_color="#f1f5f9",
                    line_color=palette.subgraph_border,
                    text_color=palette.subgraph_text,
                    line_weight_in=0.012,
                    fill_pattern=1,
                    font_name=font_name,
                    font_size_pt=8.5,
                    bold=True,
                    has_connections=False,
                ))

                # Render primary items inside loop
                render_events(ev.children)

                # Render else / and / option branches if present
                for branch, div_y, br_children in ev.branch_events:
                    div_id = shape_id_counter
                    shape_id_counter += 1
                    shapes_xml_list.append(build_1d_connector_xml(
                        connector_id=div_id,
                        begin_x=round(ev.left_x, 4),
                        begin_y=round(div_y, 4),
                        end_x=round(ev.right_x, 4),
                        end_y=round(div_y, 4),
                        line_color=palette.subgraph_border,
                        line_weight_in=0.015,
                        line_pattern=2,
                        begin_arrow=0,
                        end_arrow=0,
                        is_dynamic=False,
                    ))

                    br_badge_id = shape_id_counter
                    shape_id_counter += 1
                    br_label = f"[{branch.branch_type}: {branch.title}]" if branch.title else f"[{branch.branch_type}]"
                    br_w = max(0.95, len(br_label) * 0.08 + 0.25)
                    br_h = 0.22
                    shapes_xml_list.append(build_2d_shape_xml(
                        shape_id=br_badge_id,
                        name=f"Badge_Branch_{br_badge_id}",
                        pin_x=round(ev.left_x + br_w / 2.0 + 0.06, 4),
                        pin_y=round(div_y - br_h / 2.0 - 0.03, 4),
                        width=round(br_w, 4),
                        height=round(br_h, 4),
                        text=br_label,
                        shape_type="rectangle",
                        fill_color="#f1f5f9",
                        line_color=palette.subgraph_border,
                        text_color=palette.subgraph_text,
                        line_weight_in=0.01,
                        fill_pattern=1,
                        font_name=font_name,
                        font_size_pt=8.0,
                        bold=True,
                        has_connections=False,
                    ))

                    render_events(br_children)

            elif isinstance(ev.item, Note):
                n_id = shape_id_counter
                shape_id_counter += 1

                item = ev.item
                if len(item.participant_ids) >= 2:
                    p1 = item.participant_ids[0]
                    p2 = item.participant_ids[1]
                    x1 = part_x.get(p1, start_x)
                    x2 = part_x.get(p2, start_x + part_spacing)
                    n_x = (x1 + x2) / 2.0
                    n_w = abs(x2 - x1) + 0.6
                elif len(item.participant_ids) == 1:
                    p1 = item.participant_ids[0]
                    base_px = part_x.get(p1, start_x)
                    placement_low = item.placement.lower()
                    if "left" in placement_low:
                        n_x = base_px - 1.35
                    elif "right" in placement_low:
                        n_x = base_px + 1.35
                    else:
                        n_x = base_px
                    n_w = 1.8
                else:
                    n_x = page_width / 2.0
                    n_w = 2.0

                n_w, n_h, _ = estimate_text_dimensions(item.text, font_size_pt=9.0, min_width_in=n_w, min_height_in=0.5)

                shapes_xml_list.append(build_2d_shape_xml(
                    shape_id=n_id,
                    name=f"Note_{n_id}",
                    pin_x=round(n_x, 4),
                    pin_y=round(ev.y, 4),
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

            elif isinstance(ev.item, Message):
                m_id = shape_id_counter
                shape_id_counter += 1
                item = ev.item

                src_x = part_x.get(item.sender_id, start_x)
                dst_x = part_x.get(item.receiver_id, start_x + part_spacing)

                msg_label = f"[{msg_counter}] {item.text}" if diagram.autonumber else item.text
                msg_counter += 1

                line_pat = 1
                end_arr = 13
                if item.arrow_type in (MessageArrow.DOTTED_ARROW, MessageArrow.DOTTED_LINE, MessageArrow.DOTTED_CROSS, MessageArrow.DOTTED_OPEN):
                    line_pat = 2
                if item.arrow_type in (MessageArrow.SOLID_CROSS, MessageArrow.DOTTED_CROSS):
                    end_arr = 20
                elif item.arrow_type in (MessageArrow.SOLID_LINE, MessageArrow.DOTTED_LINE):
                    end_arr = 0

                if ev.is_self:
                    shapes_xml_list.append(build_self_loop_xml(
                        connector_id=m_id,
                        px=src_x,
                        start_y=ev.y,
                        label=msg_label,
                        loop_w=0.75,
                        loop_h=0.40,
                        line_color=palette.connector_line,
                        line_weight_in=0.018,
                        line_pattern=line_pat,
                        end_arrow=end_arr,
                        font_name=font_name,
                        font_size_pt=9.0,
                        text_color=palette.connector_text,
                    ))
                else:
                    shapes_xml_list.append(build_1d_connector_xml(
                        connector_id=m_id,
                        begin_x=src_x,
                        begin_y=ev.y,
                        end_x=dst_x,
                        end_y=ev.y,
                        label=msg_label,
                        line_color=palette.connector_line,
                        line_weight_in=0.018,
                        line_pattern=line_pat,
                        end_arrow=end_arr,
                        font_name=font_name,
                        font_size_pt=9.0,
                        text_color=palette.connector_text,
                        is_dynamic=False,
                    ))

    render_events(layout_events)

    # 5. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="",
        page_width=page_width,
        page_height=page_height,
    )
