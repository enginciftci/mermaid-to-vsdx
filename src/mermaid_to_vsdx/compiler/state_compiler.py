"""
Native headless compiler for Mermaid State Diagrams (stateDiagram and stateDiagram-v2).
Transforms StateDiagram AST into Open Packaging Conventions Visio XML.
"""

from typing import Dict, List, Tuple
from ..parser.ast_nodes import StateDiagram, StateNodeType
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions
from .layout_engine import SugiyamaLayoutEngine
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_connect_records,
    calculate_connector_endpoints_and_ports,
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
    Renders initial states as filled discs, terminal states as bullseye circles,
    and states as rounded rectangular boxes with live point-to-point glue.
    """
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    # 1. Text sizing heuristics
    node_dims: Dict[str, Tuple[float, float, str]] = {}
    for sid, state in diagram.states.items():
        if state.node_type == StateNodeType.INITIAL:
            node_dims[sid] = (0.28, 0.28, None)
        elif state.node_type == StateNodeType.TERMINAL:
            node_dims[sid] = (0.34, 0.34, None)
        elif state.node_type == StateNodeType.CHOICE:
            node_dims[sid] = (0.6, 0.6, None)
        else:
            full_text = f"{state.label}\n{state.description}" if state.description else state.label
            w, h, _ = estimate_text_dimensions(
                text=full_text,
                font_size_pt=9.5,
                min_width_in=1.6,
                min_height_in=0.75,
            )
            node_dims[sid] = (w, h, None)

    # 2. Extract edge pairs
    edge_pairs = [(t.source_id, t.target_id) for t in diagram.transitions]

    # 3. Sugiyama layout
    layout_engine = SugiyamaLayoutEngine(
        direction=diagram.direction,
        rank_gap=1.2,
        node_gap=0.8,
        page_margin=1.0,
    )
    layout_res = layout_engine.layout(node_dims, edge_pairs)

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    state_to_shape_id: Dict[str, int] = {}

    # 4. Render 2D State Shapes
    for sid, state in diagram.states.items():
        s_id = shape_id_counter
        shape_id_counter += 1
        state_to_shape_id[sid] = s_id
        l_node = layout_res.nodes[sid]

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
            ))
        elif state.node_type == StateNodeType.TERMINAL:
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"End_{s_id}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text="",
                shape_type="double_circle",
                fill_color="#ffffff",
                line_color=palette.default_text,
                line_weight_in=0.02,
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
            ))
        else:
            full_text = f"{state.label}\n{state.description}" if state.description else state.label
            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=s_id,
                name=f"State_{sid}",
                pin_x=l_node.pin_x,
                pin_y=l_node.pin_y,
                width=l_node.width,
                height=l_node.height,
                text=full_text,
                shape_type="rounded",
                rounding_in=0.15,
                fill_color=palette.default_fill,
                line_color=palette.default_border,
                text_color="#ffffff" if is_dark_color(palette.default_fill) else palette.default_text,
                line_weight_in=0.02,
                font_name=font_name,
                font_size_pt=9.5,
            ))

    # 5. Render 1D Transition Connectors & <Connects>
    for trans in diagram.transitions:
        if trans.source_id not in state_to_shape_id or trans.target_id not in state_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = state_to_shape_id[trans.source_id]
        dst_s_id = state_to_shape_id[trans.target_id]
        src_node = layout_res.nodes[trans.source_id]
        dst_node = layout_res.nodes[trans.target_id]

        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = calculate_connector_endpoints_and_ports(
            src_x=src_node.pin_x,
            src_y=src_node.pin_y,
            src_w=src_node.width,
            src_h=src_node.height,
            dst_x=dst_node.pin_x,
            dst_y=dst_node.pin_y,
            dst_w=dst_node.width,
            dst_h=dst_node.height,
            direction=diagram.direction,
        )

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

    # 6. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=layout_res.page_width,
        page_height=layout_res.page_height,
    )
