"""
Native headless compiler for Mermaid UML Class Diagrams.
Transforms ClassDiagram AST into Open Packaging Conventions Visio XML with multi-compartments.
"""

from typing import Dict, List, Tuple
from src.parser.ast_nodes import ClassDiagram, RelationshipType
from src.visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from src.compiler.text_metrics import estimate_text_dimensions, estimate_line_width_pt
from src.compiler.layout_engine import SugiyamaLayoutEngine
from src.compiler.shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_connect_records,
    calculate_connector_endpoints,
    calculate_connector_endpoints_and_ports,
)
from src.compiler.opc_package import package_vsdx


def compile_class_diagram_to_vsdx(
    diagram: ClassDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    # 1. Text sizing heuristics for each class
    class_dims: Dict[str, Tuple[float, float, None]] = {}
    class_members_split: Dict[str, Tuple[List, List]] = {}

    for cid, cls in diagram.classes.items():
        attrs = [m for m in cls.members if not m.is_method]
        meths = [m for m in cls.members if m.is_method]
        class_members_split[cid] = (attrs, meths)

        all_lines = [cls.name]
        if cls.annotation:
            all_lines.insert(0, f"<<{cls.annotation}>>")
        for a in attrs:
            prefix = a.visibility if a.visibility else "+"
            all_lines.append(f"{prefix} {a.return_type} {a.name}" if a.return_type else f"{prefix} {a.name}")
        for m in meths:
            prefix = m.visibility if m.visibility else "+"
            sig = f"{m.name}({m.parameters})" if m.parameters else f"{m.name}()"
            all_lines.append(f"{prefix} {sig}: {m.return_type}" if m.return_type else f"{prefix} {sig}")

        max_pt = max(estimate_line_width_pt(l, 9.5) for l in all_lines)
        w_in = max(2.4, round(max_pt / 72.0 + 0.6, 2))

        # Heights
        title_h = 0.55 if cls.annotation else 0.4
        attr_h = max(0.3, len(attrs) * 0.22 + 0.1)
        meth_h = max(0.3, len(meths) * 0.22 + 0.1)
        total_h = round(title_h + attr_h + meth_h, 2)

        class_dims[cid] = (w_in, total_h, None)

    # 2. Extract relationships
    edges = [(rel.source_name, rel.target_name) for rel in diagram.relationships]

    # 3. Layout engine (Class diagrams typically flow Top-Down)
    layout_engine = SugiyamaLayoutEngine(
        direction="TD",
        rank_gap=1.2,
        node_gap=0.8,
        page_margin=1.0,
    )
    layout_res = layout_engine.layout(class_dims, edges)

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    class_to_shape_id: Dict[str, int] = {}

    # 4. Render Classes (Multi-compartment)
    for cid, cls in diagram.classes.items():
        main_id = shape_id_counter
        shape_id_counter += 1
        class_to_shape_id[cid] = main_id

        attrs, meths = class_members_split[cid]
        l_node = layout_res.nodes[cid]
        w = l_node.width
        h = l_node.height
        cx = l_node.pin_x
        cy = l_node.pin_y

        is_interface = bool(cls.annotation and "interface" in cls.annotation.lower())
        fill_col = palette.decision_fill if is_interface else palette.default_fill
        border_col = palette.decision_border if is_interface else palette.default_border
        text_col = "#ffffff" if is_dark_color(fill_col) else palette.default_text

        # Base class box
        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=main_id,
            name=f"Class_{cid}",
            pin_x=cx,
            pin_y=cy,
            width=w,
            height=h,
            text="",
            shape_type="rectangle",
            fill_color=fill_col,
            line_color=border_col,
            line_weight_in=0.0208,
            rounding_in=0.04,
        ))

        # Title compartment at top
        title_lines = [f"<<{cls.annotation}>>", cls.name] if cls.annotation else [cls.name]
        title_text = "\n".join(title_lines)
        title_h = 0.55 if cls.annotation else 0.4
        title_pin_y = cy + h / 2.0 - title_h / 2.0

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=shape_id_counter,
            name=f"Title_{cid}",
            pin_x=cx,
            pin_y=title_pin_y,
            width=w,
            height=title_h,
            text=title_text,
            shape_type="rectangle",
            fill_color=fill_col,
            line_color=fill_col,
            text_color=text_col,
            font_name=font_name,
            font_size_pt=10.0,
            has_connections=False,
        ))
        shape_id_counter += 1

        # Divider 1 (below title)
        div1_y = cy + h / 2.0 - title_h
        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=cx - w / 2.0,
            begin_y=div1_y,
            end_x=cx + w / 2.0,
            end_y=div1_y,
            line_color=border_col,
            line_weight_in=0.015,
            end_arrow=0,
            is_dynamic=False,
        ))
        shape_id_counter += 1

        # Attributes compartment
        attr_lines = []
        for a in attrs:
            pfx = a.visibility if a.visibility else "+"
            attr_lines.append(f"{pfx} {a.return_type} {a.name}" if a.return_type else f"{pfx} {a.name}")
        attr_text = "\n".join(attr_lines) if attr_lines else " "
        attr_h = max(0.3, len(attrs) * 0.22 + 0.1)
        attr_pin_y = div1_y - attr_h / 2.0

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=shape_id_counter,
            name=f"Attrs_{cid}",
            pin_x=cx,
            pin_y=attr_pin_y,
            width=w,
            height=attr_h,
            text=attr_text,
            shape_type="rectangle",
            fill_color=fill_col,
            line_color=fill_col,
            text_color=text_col,
            font_name=font_name,
            font_size_pt=9.0,
            align_left=True,
            has_connections=False,
        ))
        shape_id_counter += 1

        # Divider 2 (below attributes)
        div2_y = div1_y - attr_h
        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=shape_id_counter,
            begin_x=cx - w / 2.0,
            begin_y=div2_y,
            end_x=cx + w / 2.0,
            end_y=div2_y,
            line_color=border_col,
            line_weight_in=0.015,
            end_arrow=0,
            is_dynamic=False,
        ))
        shape_id_counter += 1

        # Methods compartment
        meth_lines = []
        for m in meths:
            pfx = m.visibility if m.visibility else "+"
            sig = f"{m.name}({m.parameters})" if m.parameters else f"{m.name}()"
            meth_lines.append(f"{pfx} {sig}: {m.return_type}" if m.return_type else f"{pfx} {sig}")
        meth_text = "\n".join(meth_lines) if meth_lines else " "
        meth_h = max(0.3, len(meths) * 0.22 + 0.1)
        meth_pin_y = div2_y - meth_h / 2.0

        shapes_xml_list.append(build_2d_shape_xml(
            shape_id=shape_id_counter,
            name=f"Methods_{cid}",
            pin_x=cx,
            pin_y=meth_pin_y,
            width=w,
            height=meth_h,
            text=meth_text,
            shape_type="rectangle",
            fill_color=fill_col,
            line_color=fill_col,
            text_color=text_col,
            font_name=font_name,
            font_size_pt=9.0,
            align_left=True,
            has_connections=False,
        ))
        shape_id_counter += 1

    # 5. Render UML Relationship Connectors
    for rel in diagram.relationships:
        if rel.source_name not in class_to_shape_id or rel.target_name not in class_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = class_to_shape_id[rel.source_name]
        dst_s_id = class_to_shape_id[rel.target_name]
        src_pos = layout_res.nodes[rel.source_name]
        dst_pos = layout_res.nodes[rel.target_name]

        line_pat = 1
        begin_arr = 0
        end_arr = 0
        arr_sz = 2

        rt = rel.rel_type
        if rt == RelationshipType.INHERITANCE:
            end_arr = 14  # Closed hollow triangle for UML inheritance
        elif rt == RelationshipType.REALIZATION:
            line_pat = 2  # Dashed line
            end_arr = 14
        elif rt == RelationshipType.COMPOSITION:
            begin_arr = 20  # Filled diamond
        elif rt == RelationshipType.AGGREGATION:
            begin_arr = 21  # Hollow diamond
        elif rt == RelationshipType.ASSOCIATION:
            end_arr = 13
        elif rt == RelationshipType.DEPENDENCY:
            line_pat = 2
            end_arr = 13
        elif rt == RelationshipType.DASHED_LINK:
            line_pat = 2

        # Label assembly (multiplicities + text)
        label_parts = []
        if rel.multiplicity_source:
            label_parts.append(rel.multiplicity_source)
        if rel.label:
            label_parts.append(rel.label)
        if rel.multiplicity_target:
            label_parts.append(rel.multiplicity_target)
        full_label = " ".join(label_parts)

        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = calculate_connector_endpoints_and_ports(
            src_x=src_pos.pin_x,
            src_y=src_pos.pin_y,
            src_w=src_pos.width,
            src_h=src_pos.height,
            dst_x=dst_pos.pin_x,
            dst_y=dst_pos.pin_y,
            dst_w=dst_pos.width,
            dst_h=dst_pos.height,
            direction="TD",
        )

        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=c_id,
            begin_x=bx,
            begin_y=by,
            end_x=ex,
            end_y=ey,
            label=full_label,
            line_color=palette.connector_line,
            line_weight_in=0.018,
            line_pattern=line_pat,
            begin_arrow=begin_arr,
            end_arrow=end_arr,
            end_arrow_size=arr_sz,
            font_name=font_name,
            font_size_pt=8.5,
            text_color=palette.connector_text,
            is_dynamic=True,
            source_shape_id=src_s_id,
            target_shape_id=dst_s_id,
            src_port=src_port,
            dst_port=dst_port,
            routing_direction="TD",
        ))

        connects_xml_list.append(build_connect_records(
            connector_id=c_id,
            source_shape_id=src_s_id,
            target_shape_id=dst_s_id,
            src_port=src_port,
            dst_port=dst_port,
            src_part=src_part,
            dst_part=dst_part,
        ))

    # 6. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=layout_res.page_width,
        page_height=layout_res.page_height,
    )
