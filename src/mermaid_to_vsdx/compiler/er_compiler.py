"""
Native headless compiler for Mermaid Entity-Relationship Diagrams (erDiagram).
Transforms ERDiagram AST into Open Packaging Conventions Visio XML.
"""

import re
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
    distribute_shared_ports,
)
from .opc_package import package_vsdx


def _parse_er_cardinality(card: str) -> Tuple[int, int, int]:
    """
    Maps Mermaid ER cardinality strings (e.g. '||--o{', '||--|{', '}|..|{', '|o--o|')
    to (line_pattern, begin_arrow, end_arrow) using Visio Crow's Foot arrow codes:
      - Exact one ('||'): 28
      - Zero or one ('|o', 'o|'): 24
      - One or many ('}|', '|{'): 27
      - Zero or many ('}o', 'o{'): 29
    """
    line_pat = 2 if ".." in card else 1
    parts = re.split(r"[-.]+", card.strip())
    left_c = parts[0] if len(parts) > 0 else ""
    right_c = parts[1] if len(parts) > 1 else ""

    def _marker_code(sym: str) -> int:
        if sym == "||":
            return 28
        if sym in ("|o", "o|"):
            return 24
        if sym in ("}|", "|{"):
            return 27
        if sym in ("}o", "o{"):
            return 29
        return 0

    return line_pat, _marker_code(left_c), _marker_code(right_c)


def compile_er_diagram_to_vsdx(
    diagram: ERDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles an ERDiagram AST into a native Visio (.vsdx) archive.
    Renders entities as multi-compartment tables with PK/FK/UK attribute markers,
    Visio Crow's Foot cardinality connectors, and distributed perimeter connection ports.
    """
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    # 1. Text sizing heuristics
    node_dims: Dict[str, Tuple[float, float, None]] = {}
    for ename, entity in diagram.entities.items():
        display_name = entity.alias if entity.alias else ename
        title_w_pt = estimate_line_width_pt(display_name, font_size_pt=10.0, bold=True)
        max_attr_pt = 0.0
        for a in entity.attributes:
            tags = [t for t, flag in (("PK", a.is_pk), ("FK", a.is_fk), ("UK", a.is_uk)) if flag]
            key_str = f" ({','.join(tags)})" if tags else ""
            line = f"{a.attr_type} {a.name}{key_str}"
            lw = estimate_line_width_pt(line, font_size_pt=9.0)
            if lw > max_attr_pt:
                max_attr_pt = lw

        content_w_in = max(title_w_pt, max_attr_pt) / 72.0 + 0.6
        w = max(2.2, min(5.0, round(content_w_in, 2)))

        if entity.attributes:
            header_h = 0.4
            attr_h = max(0.38, len(entity.attributes) * 0.22 + 0.12)
            total_h = round(header_h + attr_h, 2)
        else:
            total_h = 0.55

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

    # 3b. Distribute shared ports across all ER relationships
    nodes_geom: Dict[str, Tuple[float, float, float, float]] = {
        ename: (n.pin_x, n.pin_y, n.width, n.height)
        for ename, n in layout_res.nodes.items()
    }
    distributed_routes, node_extra_connections = distribute_shared_ports(
        nodes_geom=nodes_geom,
        edge_pairs=edge_pairs,
        direction="TD",
    )

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    entity_to_shape_id: Dict[str, int] = {}

    header_fill = getattr(palette, "subgraph_header_fill", palette.subgraph_border)
    header_text_col = "#ffffff" if is_dark_color(header_fill) else "#0f172a"

    # 4. Render 2D Entity Shapes
    for ename, entity in diagram.entities.items():
        main_id = shape_id_counter
        shape_id_counter += 1
        entity_to_shape_id[ename] = main_id

        l_node = layout_res.nodes[ename]
        cx, cy, w, h = l_node.pin_x, l_node.pin_y, l_node.width, l_node.height
        display_name = entity.alias if entity.alias else ename

        child_shapes: List[str] = []

        if not entity.attributes:
            # Compact single-box entity when no attributes are declared
            title_id = shape_id_counter
            shape_id_counter += 1
            child_shapes.append(build_2d_shape_xml(
                shape_id=title_id,
                name=f"Header_{ename}",
                pin_x=round(w * 0.5, 4),
                pin_y=round(h * 0.5, 4),
                width=w,
                height=h,
                text=display_name,
                shape_type="rectangle",
                fill_color=header_fill,
                line_color=palette.default_border,
                text_color=header_text_col,
                line_weight_in=0.02,
                rounding_in=0.05,
                font_name=font_name,
                font_size_pt=10.0,
                bold=True,
                has_connections=False,
            ))
        else:
            header_h = 0.4
            attr_h = round(h - header_h, 4)

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

            # Child 2: Title header compartment (top, local coords, bold)
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
                text=display_name,
                shape_type="rectangle",
                fill_color=header_fill,
                line_color=palette.default_border,
                text_color=header_text_col,
                font_name=font_name,
                font_size_pt=10.0,
                bold=True,
                has_connections=False,
            ))

            # Child 3: Attributes compartment (bottom, local coords, transparent)
            attr_lines = []
            for a in entity.attributes:
                tags = [t for t, flag in (("PK", a.is_pk), ("FK", a.is_fk), ("UK", a.is_uk)) if flag]
                key_tag = " " + ",".join(tags) if tags else ""
                attr_lines.append(f"{a.attr_type} {a.name}{key_tag}")
            attr_text = "\n".join(attr_lines)

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

        # Enclosing Group Shape with distributed perimeter connection points
        shapes_xml_list.append(build_group_shape_xml(
            group_id=main_id,
            name=f"Entity_{ename}",
            pin_x=cx,
            pin_y=cy,
            width=w,
            height=h,
            child_shapes_xml=child_shapes,
            has_connections=True,
            extra_connections=node_extra_connections.get(ename),
        ))

    # 5. Render 1D Relationships & <Connects>
    for idx, rel in enumerate(diagram.relationships):
        if rel.entity1 not in entity_to_shape_id or rel.entity2 not in entity_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = entity_to_shape_id[rel.entity1]
        dst_s_id = entity_to_shape_id[rel.entity2]

        line_pat, begin_arr, end_arr = _parse_er_cardinality(rel.cardinality)
        label_str = rel.role if rel.role else ""

        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = distributed_routes[idx]

        conn_xml = build_1d_connector_xml(
            connector_id=c_id,
            begin_x=bx,
            begin_y=by,
            end_x=ex,
            end_y=ey,
            label=label_str,
            line_color=palette.connector_line,
            line_weight_in=0.018,
            line_pattern=line_pat,
            begin_arrow=begin_arr,
            end_arrow=end_arr,
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
