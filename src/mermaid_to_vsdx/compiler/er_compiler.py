"""
Native headless compiler for Mermaid Entity-Relationship Diagrams (erDiagram).
Transforms ERDiagram AST into Open Packaging Conventions Visio XML.
"""

from typing import Dict, List, Tuple
from ..parser.ast_nodes import ERDiagram
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions, estimate_line_width_pt
from .layout_engine import SugiyamaLayoutEngine
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_group_shape_xml,
    build_connect_records,
    calculate_connector_endpoints_and_ports,
)
from .opc_package import package_vsdx


def compile_er_diagram_to_vsdx(
    diagram: ERDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles an ERDiagram AST into a native Visio (.vsdx) archive.
    Renders entities as multi-compartment tables with PK/FK attribute markers
    and live point-to-point connector glue.
    """
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    # 1. Text sizing heuristics
    node_dims: Dict[str, Tuple[float, float, str]] = {}
    for ename, entity in diagram.entities.items():
        title_w_pt = estimate_line_width_pt(ename, font_size_pt=10.0, bold=True)
        max_attr_pt = 0.0
        for a in entity.attributes:
            pk_str = " (PK)" if a.is_pk else (" (FK)" if a.is_fk else "")
            line = f"{a.attr_type} {a.name}{pk_str}"
            lw = estimate_line_width_pt(line, font_size_pt=9.0)
            if lw > max_attr_pt:
                max_attr_pt = lw

        content_w_in = max(title_w_pt, max_attr_pt) / 72.0 + 0.6
        w = max(2.2, min(5.0, round(content_w_in, 2)))

        header_h = 0.4
        attr_h = max(0.4, len(entity.attributes) * 0.22 + 0.1)
        total_h = round(header_h + attr_h, 2)
        node_dims[ename] = (w, total_h, None)

    # 2. Extract edge pairs
    edge_pairs = [(r.entity1, r.entity2) for r in diagram.relationships]

    # 3. Sugiyama layout
    layout_engine = SugiyamaLayoutEngine(
        direction="TD",
        rank_gap=1.2,
        node_gap=0.8,
        page_margin=1.0,
    )
    layout_res = layout_engine.layout(node_dims, edge_pairs)

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    entity_to_shape_id: Dict[str, int] = {}

    # 4. Render 2D Entity Shapes (Multi-compartment wrapped in Group Shape)
    for ename, entity in diagram.entities.items():
        main_id = shape_id_counter
        shape_id_counter += 1
        entity_to_shape_id[ename] = main_id

        l_node = layout_res.nodes[ename]
        cx, cy, w, h = l_node.pin_x, l_node.pin_y, l_node.width, l_node.height

        header_h = 0.4
        attr_h = round(h - header_h, 4)

        child_shapes: List[str] = []

        # Child 1: Base outer container box (local coords)
        bg_id = shape_id_counter
        shape_id_counter += 1
        child_shapes.append(build_2d_shape_xml(
            shape_id=bg_id,
            name=f"EntityBg_{ename}",
            pin_x=round(w * 0.5, 4),
            pin_y=round(h * 0.5, 4),
            width=w,
            height=h,
            text="",
            shape_type="rectangle",
            fill_color=palette.default_fill,
            line_color=palette.default_border,
            line_weight_in=0.02,
            rounding_in=0.03,
            has_connections=False,
        ))

        # Child 2: Title header compartment (top, local coords)
        title_pin_y = round(h - header_h * 0.5, 4)
        title_id = shape_id_counter
        shape_id_counter += 1
        child_shapes.append(build_2d_shape_xml(
            shape_id=title_id,
            name=f"Header_{ename}",
            pin_x=round(w * 0.5, 4),
            pin_y=title_pin_y,
            width=w,
            height=header_h,
            text=ename,
            shape_type="rectangle",
            fill_color=palette.subgraph_border,
            line_color=palette.subgraph_border,
            text_color="#ffffff" if is_dark_color(palette.subgraph_border) else palette.subgraph_text,
            font_name=font_name,
            font_size_pt=10.0,
            has_connections=False,
        ))

        # Child 3: Attributes compartment (bottom, local coords, transparent)
        attr_lines = []
        for a in entity.attributes:
            key_tag = " PK" if a.is_pk else (" FK" if a.is_fk else "")
            attr_lines.append(f"{a.attr_type} {a.name}{key_tag}")
        attr_text = "\n".join(attr_lines) if attr_lines else " "

        attr_pin_y = round(attr_h * 0.5, 4)
        attr_id = shape_id_counter
        shape_id_counter += 1
        child_shapes.append(build_2d_shape_xml(
            shape_id=attr_id,
            name=f"Attrs_{ename}",
            pin_x=round(w * 0.5, 4),
            pin_y=attr_pin_y,
            width=w,
            height=attr_h,
            text=attr_text,
            shape_type="rectangle",
            fill_color=palette.default_fill,
            line_color=palette.default_fill,
            text_color=palette.default_text,
            fill_pattern=0,
            line_pattern=0,
            font_name=font_name,
            font_size_pt=9.0,
            align_left=True,
            has_connections=False,
        ))

        # Child 4: Divider line below header (drawn on top)
        div_y = round(h - header_h, 4)
        div_id = shape_id_counter
        shape_id_counter += 1
        child_shapes.append(build_1d_connector_xml(
            connector_id=div_id,
            begin_x=0.0,
            begin_y=div_y,
            end_x=w,
            end_y=div_y,
            line_color=palette.default_border,
            line_weight_in=0.015,
            end_arrow=0,
            is_dynamic=False,
        ))

        # Enclosing Group Shape
        shapes_xml_list.append(build_group_shape_xml(
            group_id=main_id,
            name=f"Entity_{ename}",
            pin_x=cx,
            pin_y=cy,
            width=w,
            height=h,
            child_shapes_xml=child_shapes,
            has_connections=True,
        ))

    # 5. Render 1D Relationships & <Connects>
    for rel in diagram.relationships:
        if rel.entity1 not in entity_to_shape_id or rel.entity2 not in entity_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = entity_to_shape_id[rel.entity1]
        dst_s_id = entity_to_shape_id[rel.entity2]
        src_node = layout_res.nodes[rel.entity1]
        dst_node = layout_res.nodes[rel.entity2]

        line_pat = 2 if ".." in rel.cardinality else 1
        label = f"{rel.cardinality} {rel.role}".strip() if rel.role else rel.cardinality

        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = calculate_connector_endpoints_and_ports(
            src_x=src_node.pin_x,
            src_y=src_node.pin_y,
            src_w=src_node.width,
            src_h=src_node.height,
            dst_x=dst_node.pin_x,
            dst_y=dst_node.pin_y,
            dst_w=dst_node.width,
            dst_h=dst_node.height,
            direction="TD",
        )

        conn_xml = build_1d_connector_xml(
            connector_id=c_id,
            begin_x=bx,
            begin_y=by,
            end_x=ex,
            end_y=ey,
            label=label,
            line_color=palette.connector_line,
            line_weight_in=0.018,
            line_pattern=line_pat,
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
            routing_direction="TD",
            intermediate_waypoints=layout_res.edge_routes.get((rel.entity1, rel.entity2), []),
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
