"""
Native headless compiler for Mermaid State Diagrams (stateDiagram and stateDiagram-v2).
Transforms StateDiagram AST into Open Packaging Conventions Visio XML.
"""

from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from ..parser.ast_nodes import StateDiagram, StateNodeType
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions
from .layout_engine import SugiyamaLayoutEngine
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_group_shape_xml,
    build_connect_records,
    calculate_connector_endpoints_and_ports,
    distribute_shared_ports,
)
from .opc_package import package_vsdx


def compile_state_diagram_to_vsdx(
    diagram: StateDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a StateDiagram AST into a native Visio (.vsdx) archive.
    Renders composite state containers, initial states as filled discs, terminal states
    as bullseye circles, normal states as rounded rectangular boxes with live point-to-point glue,
    staggered feedback channels, and state notes.
    """
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    composite_ids = {sid for sid, st in diagram.states.items() if st.children}

    # Helper to collect all leaf descendant state IDs of a composite state
    def _get_leaf_descendants(cid: str) -> List[str]:
        leaves: List[str] = []
        st = diagram.states.get(cid)
        if not st:
            return leaves
        for child_id in st.children:
            if child_id in composite_ids:
                leaves.extend(_get_leaf_descendants(child_id))
            elif child_id in diagram.states:
                leaves.append(child_id)
        return leaves

    # 1. Text sizing heuristics for leaf states
    node_dims: Dict[str, Tuple[float, float, Optional[str]]] = {}
    node_text_map: Dict[str, str] = {}

    for sid, state in diagram.states.items():
        if sid in composite_ids:
            continue
        parent_sub = state.parent_id if state.parent_id in composite_ids else None
        if state.node_type == StateNodeType.INITIAL:
            node_dims[sid] = (0.28, 0.28, parent_sub)
        elif state.node_type == StateNodeType.TERMINAL:
            node_dims[sid] = (0.34, 0.34, parent_sub)
        elif state.node_type == StateNodeType.CHOICE:
            node_dims[sid] = (0.6, 0.6, parent_sub)
        elif state.node_type in (StateNodeType.FORK, StateNodeType.JOIN):
            if diagram.direction in ("LR", "RL"):
                node_dims[sid] = (0.08, 1.2, parent_sub)
            else:
                node_dims[sid] = (1.2, 0.08, parent_sub)
        else:
            full_text = f"{state.label}\n{state.description}" if state.description else state.label
            w, h, wrapped = estimate_text_dimensions(
                text=full_text,
                font_size_pt=9.5,
                min_width_in=1.6,
                min_height_in=0.75,
                max_width_in=3.0,
            )
            node_dims[sid] = (w, h, parent_sub)
            node_text_map[sid] = "\n".join(wrapped) if isinstance(wrapped, list) else str(wrapped)

    subgraphs_input: Dict[str, Tuple[str, List[str]]] = {}
    for cid in composite_ids:
        leaves = _get_leaf_descendants(cid)
        if leaves:
            subgraphs_input[cid] = (diagram.states[cid].label, leaves)
        else:
            # Fallback if composite has no valid leaf states
            state = diagram.states[cid]
            w, h, wrapped = estimate_text_dimensions(
                text=state.label, font_size_pt=9.5, min_width_in=1.6, min_height_in=0.75, max_width_in=3.0
            )
            node_dims[cid] = (w, h, state.parent_id)
            node_text_map[cid] = "\n".join(wrapped) if isinstance(wrapped, list) else str(wrapped)

    # 2. Extract edge pairs for Sugiyama layout (mapping edges targeting composite states to entry/exit leaves)
    layout_edges: List[Tuple[str, str]] = []
    for t in diagram.transitions:
        u, v = t.source_id, t.target_id
        u_list = [u]
        v_list = [v]
        if u in subgraphs_input:
            leaves = subgraphs_input[u][1]
            if v not in leaves:
                u_list = [leaves[-1]]
            else:
                continue
        if v in subgraphs_input:
            leaves = subgraphs_input[v][1]
            if u not in leaves:
                v_list = [leaves[0]]
            else:
                continue
        for uu in u_list:
            for vv in v_list:
                if uu in node_dims and vv in node_dims and uu != vv:
                    layout_edges.append((uu, vv))

    # 3. Sugiyama layout
    layout_engine = SugiyamaLayoutEngine(
        direction=diagram.direction,
        rank_gap=1.2,
        node_gap=0.8,
        page_margin=1.0,
    )
    layout_res = layout_engine.layout(
        node_dims,
        layout_edges,
        subgraphs=subgraphs_input if subgraphs_input else None,
    )

    # 3b. Account for StateNotes horizontal space so left/right notes never go out of page bounds
    note_specs: List[Tuple[str, str, float, float, str]] = []
    shift_x = 0.0
    for note in diagram.notes:
        nw, nh, wrapped_n = estimate_text_dimensions(
            note.text, font_size_pt=9.0, min_width_in=1.5, min_height_in=0.5, max_width_in=2.3
        )
        ntext = "\n".join(wrapped_n) if isinstance(wrapped_n, list) else str(wrapped_n)
        note_specs.append((note.placement.lower(), note.state_id, nw, nh, ntext))
        if note.state_id in layout_res.nodes:
            tn = layout_res.nodes[note.state_id]
            if "left" in note.placement.lower():
                left_edge = tn.pin_x - tn.width * 0.5 - 0.55 - nw
                if left_edge < 0.6:
                    shift_x = max(shift_x, round(0.6 - left_edge, 3))
        elif note.state_id in layout_res.subgraphs:
            ts = layout_res.subgraphs[note.state_id]
            if "left" in note.placement.lower():
                left_edge = ts.pin_x - ts.width * 0.5 - 0.55 - nw
                if left_edge < 0.6:
                    shift_x = max(shift_x, round(0.6 - left_edge, 3))

    # Reserve left margin if any upward feedback loop routes via Left -> Left
    if diagram.direction in ("TD", "TB"):
        for t in diagram.transitions:
            sn = layout_res.nodes.get(t.source_id) or layout_res.subgraphs.get(t.source_id)
            dn = layout_res.nodes.get(t.target_id) or layout_res.subgraphs.get(t.target_id)
            if sn and dn and t.source_id != t.target_id and (dn.pin_y - sn.pin_y) > 0.1:
                y_low, y_high = min(sn.pin_y, dn.pin_y) - 0.15, max(sn.pin_y, dn.pin_y) + 0.15
                r_thresh = min(sn.pin_x + sn.width * 0.5, dn.pin_x + dn.width * 0.5) - 0.05
                l_thresh = max(sn.pin_x - sn.width * 0.5, dn.pin_x - dn.width * 0.5) + 0.05
                r_obs = sum(
                    1 for oid, on in layout_res.nodes.items()
                    if oid not in (t.source_id, t.target_id)
                    and not (on.pin_y + on.height * 0.5 < y_low or on.pin_y - on.height * 0.5 > y_high)
                    and (on.pin_x + on.width * 0.5 > r_thresh)
                )
                l_obs = sum(
                    1 for oid, on in layout_res.nodes.items()
                    if oid not in (t.source_id, t.target_id)
                    and not (on.pin_y + on.height * 0.5 < y_low or on.pin_y - on.height * 0.5 > y_high)
                    and (on.pin_x - on.width * 0.5 < l_thresh)
                )
                if r_obs > l_obs:
                    min_left = min(sn.pin_x - sn.width * 0.5, dn.pin_x - dn.width * 0.5) - 1.85
                    if min_left < 0.4:
                        shift_x = max(shift_x, round(0.4 - min_left, 3))

    if shift_x > 0:
        for n in layout_res.nodes.values():
            n.pin_x = round(n.pin_x + shift_x, 3)
        for s in layout_res.subgraphs.values():
            s.pin_x = round(s.pin_x + shift_x, 3)
        for k, wp_list in layout_res.edge_routes.items():
            layout_res.edge_routes[k] = [(round(wx + shift_x, 3), wy) for wx, wy in wp_list]
        layout_res.page_width = round(layout_res.page_width + shift_x, 2)

    # Build unified geometry map for both leaf states and composite state containers
    nodes_geom: Dict[str, Tuple[float, float, float, float]] = {}
    for sid, n in layout_res.nodes.items():
        nodes_geom[sid] = (n.pin_x, n.pin_y, n.width, n.height)
    for cid, sub in layout_res.subgraphs.items():
        nodes_geom[cid] = (sub.pin_x, sub.pin_y, sub.width, sub.height)

    edge_pairs = [(t.source_id, t.target_id) for t in diagram.transitions]
    distributed_routes, node_extra_connections = distribute_shared_ports(
        nodes_geom=nodes_geom,
        edge_pairs=edge_pairs,
        direction=diagram.direction,
    )

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    state_to_shape_id: Dict[str, int] = {}

    # 4a. Render Composite State Containers + Bold Header Pills FIRST (behind 2D state nodes)
    header_fill = getattr(palette, "subgraph_header_fill", palette.subgraph_border)
    header_text_col = "#ffffff" if is_dark_color(header_fill) else "#0f172a"

    for cid, sub in layout_res.subgraphs.items():
        cont_id = shape_id_counter
        shape_id_counter += 1
        state_to_shape_id[cid] = cont_id

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=cont_id,
            name=f"Container_{cid}",
            pin_x=sub.pin_x,
            pin_y=sub.pin_y,
            width=round(sub.width, 4),
            height=round(sub.height, 4),
            text="",
            shape_type="rounded",
            rounding_in=0.14,
            fill_color=palette.subgraph_fill,
            line_color=palette.subgraph_border,
            line_weight_in=0.02,
            line_pattern=2,
            fill_pattern=1,
            is_container=True,
            has_connections=True,
            extra_connections=node_extra_connections.get(cid),
        ))

        hdr_id = shape_id_counter
        shape_id_counter += 1
        hdr_h = 0.32
        hdr_w = min(round(sub.width - 0.2, 4), max(1.3, round(len(sub.title) * 0.095 + 0.45, 4)))
        hdr_x = sub.pin_x
        hdr_y = round(sub.pin_y + sub.height * 0.5 - hdr_h * 0.5 - 0.06, 4)

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=hdr_id,
            name=f"SubgraphHeader_{cid}",
            pin_x=hdr_x,
            pin_y=hdr_y,
            width=hdr_w,
            height=hdr_h,
            text=sub.title,
            shape_type="rounded",
            rounding_in=0.08,
            fill_color=header_fill,
            line_color=palette.subgraph_border,
            text_color=header_text_col,
            line_weight_in=0.015,
            font_name=font_name,
            font_size_pt=9.5,
            bold=True,
            has_connections=False,
        ))

    # 4b. Render 2D Leaf State Shapes
    for sid, state in diagram.states.items():
        if sid not in layout_res.nodes:
            continue
        s_id = shape_id_counter
        shape_id_counter += 1
        state_to_shape_id[sid] = s_id
        l_node = layout_res.nodes[sid]
        extra_conns = node_extra_connections.get(sid)

        if state.node_type == StateNodeType.INITIAL:
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"Start_{s_id}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text="",
                shape_type="circle",
                fill_color=palette.default_text,
                line_color=palette.default_text,
                line_weight_in=0.015,
                extra_connections=extra_conns,
            ))
        elif state.node_type == StateNodeType.TERMINAL:
            w = l_node.width
            h = l_node.height
            outer_id = shape_id_counter
            shape_id_counter += 1
            inner_id = shape_id_counter
            shape_id_counter += 1
            inner_w = round(w * 0.55, 4)
            inner_h = round(h * 0.55, 4)

            child_shapes = [
                build_2d_shape_xml(
                    shape_id=outer_id,
                    name=f"EndOuter_{s_id}",
                    pin_x=round(w * 0.5, 4),
                    pin_y=round(h * 0.5, 4),
                    width=w,
                    height=h,
                    text="",
                    shape_type="circle",
                    fill_color="#ffffff",
                    line_color=palette.default_text,
                    line_weight_in=0.018,
                    has_connections=False,
                ),
                build_2d_shape_xml(
                    shape_id=inner_id,
                    name=f"EndInner_{s_id}",
                    pin_x=round(w * 0.5, 4),
                    pin_y=round(h * 0.5, 4),
                    width=inner_w,
                    height=inner_h,
                    text="",
                    shape_type="circle",
                    fill_color=palette.default_text,
                    line_color=palette.default_text,
                    line_weight_in=0.01,
                    has_connections=False,
                ),
            ]
            shapes_xml_list.append(build_group_shape_xml(
                group_id=s_id,
                name=f"End_{s_id}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=w,
                height=h,
                child_shapes_xml=child_shapes,
                has_connections=True,
                extra_connections=extra_conns,
            ))
        elif state.node_type in (StateNodeType.FORK, StateNodeType.JOIN):
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"Sync_{s_id}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text="",
                shape_type="rectangle",
                fill_color=palette.default_text,
                line_color=palette.default_text,
                line_weight_in=0.015,
                extra_connections=extra_conns,
            ))
        elif state.node_type == StateNodeType.CHOICE:
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"Choice_{s_id}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text=state.label if state.label != sid else "",
                shape_type="diamond",
                fill_color=palette.decision_fill,
                line_color=palette.decision_border,
                line_weight_in=0.018,
                extra_connections=extra_conns,
            ))
        else:
            state_text = node_text_map.get(sid) or (f"{state.label}\n{state.description}" if state.description else state.label)
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"State_{sid}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text=state_text,
                shape_type="rounded",
                rounding_in=0.15,
                fill_color=palette.default_fill,
                line_color=palette.default_border,
                text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
                line_weight_in=0.02,
                font_name=font_name,
                font_size_pt=9.5,
                bold=True,
                extra_connections=extra_conns,
                shadow=True,
            ))

    page_w = layout_res.page_width
    page_h = layout_res.page_height

    # 5. Render 1D Transition Connectors & <Connects> with staggered feedback loop offsets
    fb_counts: Dict[str, int] = defaultdict(int)
    last_right_channel_x: float = 0.0

    for idx, trans in enumerate(diagram.transitions):
        if trans.source_id not in state_to_shape_id or trans.target_id not in state_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = state_to_shape_id[trans.source_id]
        dst_s_id = state_to_shape_id[trans.target_id]

        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = distributed_routes[idx]

        base_src = (src_port or "").split("_")[0]
        base_dst = (dst_port or "").split("_")[0]
        u_off = 0.55
        if base_src and base_src == base_dst and trans.source_id != trans.target_id:
            fb_idx = fb_counts[base_src]
            fb_counts[base_src] += 1
            u_off = round(0.55 + 0.40 * fb_idx, 4)
            if base_src == "Right":
                y_low, y_high = min(by, ey), max(by, ey)
                obs_right = max(bx, ex)
                for gx, gy, gw, gh in nodes_geom.values():
                    if not (gy + gh * 0.5 < y_low or gy - gh * 0.5 > y_high):
                        obs_right = max(obs_right, gx + gw * 0.5)
                desired_x = max(
                    max(bx, ex) + u_off,
                    obs_right + 0.45,
                    last_right_channel_x + 0.55 if last_right_channel_x > 0 else 0.0,
                )
                u_off = round(desired_x - max(bx, ex), 4)
                last_right_channel_x = desired_x
                page_w = max(page_w, round(desired_x + 1.3, 2))

        conn_xml = build_1d_connector_xml(
            connector_id=c_id,
            begin_x=bx,
            begin_y=by,
            end_x=ex,
            end_y=ey,
            label=trans.event or "",
            line_color=palette.connector_line,
            line_weight_in=0.018,
            line_pattern=1,
            begin_arrow=0,
            end_arrow=13,
            end_arrow_size=2,
            font_name=font_name,
            font_size_pt=8.5,
            text_color=palette.connector_text,
            is_dynamic=True,
            source_shape_id=src_s_id,
            target_shape_id=dst_s_id,
            src_port=src_port,
            dst_port=dst_port,
            routing_direction=diagram.direction,
            intermediate_waypoints=layout_res.edge_routes.get((trans.source_id, trans.target_id), []),
            u_channel_offset=u_off,
        )
        shapes_xml_list.append(conn_xml)

        conn_rec = build_connect_records(
            connector_id=c_id,
            source_shape_id=src_s_id,
            target_shape_id=dst_s_id,
            src_port=src_port,
            dst_port=dst_port,
            src_part=src_part,
            dst_part=dst_part,
        )
        connects_xml_list.append(conn_rec)

    # 6. Render StateNotes
    for placement, target_sid, nw, nh, ntext in note_specs:
        if target_sid not in nodes_geom:
            continue
        sx, sy, sw, sh = nodes_geom[target_sid]
        note_id = shape_id_counter
        shape_id_counter += 1

        if "left" in placement:
            nx = round(sx - sw * 0.5 - 0.55 - nw * 0.5, 4)
            ny = round(sy, 4)
            bx = round(nx + nw * 0.5, 4)
            ex = round(sx - sw * 0.5, 4)
        else:
            right_base = max(sx + sw * 0.5, last_right_channel_x + 0.35 if last_right_channel_x > sx else sx + sw * 0.5)
            nx = round(right_base + 0.55 + nw * 0.5, 4)
            ny = round(sy, 4)
            bx = round(nx - nw * 0.5, 4)
            ex = round(sx + sw * 0.5, 4)
            page_w = max(page_w, round(nx + nw * 0.5 + 0.8, 2))

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=note_id,
            name=f"StateNote_{note_id}",
            pin_x=nx,
            pin_y=ny,
            width=nw,
            height=nh,
            text=ntext,
            shape_type="rectangle",
            fill_color=palette.note_fill,
            line_color=palette.note_border,
            text_color="#ffffff" if is_dark_color(palette.note_fill) else palette.note_text,
            line_weight_in=0.015,
            font_name=font_name,
            font_size_pt=9.0,
            has_connections=False,
        ))

        link_id = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=link_id,
            begin_x=bx,
            begin_y=ny,
            end_x=ex,
            end_y=ny,
            line_color=palette.note_border,
            line_weight_in=0.015,
            line_pattern=2,
            begin_arrow=0,
            end_arrow=0,
            is_dynamic=False,
        ))

    # 7. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=page_w,
        page_height=page_h,
    )
