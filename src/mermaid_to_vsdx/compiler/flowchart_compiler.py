"""
Native headless compiler for Mermaid Flowcharts.
Transforms FlowchartDiagram AST into Open Packaging Conventions Visio XML.
"""

from collections import defaultdict
from typing import Dict, List, Tuple
from ..parser.ast_nodes import FlowchartDiagram, ShapeType, EdgeStyle, ArrowType, Subgraph
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .text_metrics import estimate_text_dimensions
from .layout_engine import SugiyamaLayoutEngine
from .shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_connect_records,
    calculate_connector_endpoints,
    calculate_connector_endpoints_and_ports,
)
from .opc_package import package_vsdx


# Shape mapping from AST ShapeType to geometry types
SHAPE_MAP = {
    ShapeType.RECTANGLE: "rectangle",
    ShapeType.ROUNDED: "rounded",
    ShapeType.STADIUM: "stadium",
    ShapeType.SUBROUTINE: "subroutine",
    ShapeType.CYLINDER: "cylinder",
    ShapeType.CIRCLE: "circle",
    ShapeType.ASYMMETRIC: "asymmetric",
    ShapeType.DIAMOND: "diamond",
    ShapeType.HEXAGON: "hexagon",
    ShapeType.PARALLELOGRAM: "parallelogram_right",
    ShapeType.TRAPEZOID: "trapezoid",
}


def _get_all_subgraphs_dict(subgraphs: List[Subgraph]) -> Dict[str, Subgraph]:
    result = {}
    for s in subgraphs:
        result[s.id] = s
        result.update(_get_all_subgraphs_dict(s.children))
    return result


def _get_subgraph_all_nodes(sub: Subgraph) -> List[str]:
    nodes = list(sub.node_ids)
    for c in sub.children:
        nodes.extend(_get_subgraph_all_nodes(c))
    return nodes


def _get_all_subgraphs_ordered(subgraphs: List[Subgraph]) -> List[Subgraph]:
    result = []
    for s in subgraphs:
        result.append(s)
        result.extend(_get_all_subgraphs_ordered(s.children))
    return result


def _is_in_subgraph_hierarchy(parent_sub: Subgraph, target_id: str) -> bool:
    if parent_sub.id == target_id or target_id in parent_sub.node_ids:
        return True
    return any(_is_in_subgraph_hierarchy(c, target_id) for c in parent_sub.children)


def compile_flowchart_to_vsdx(
    diagram: FlowchartDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    all_subgraphs = _get_all_subgraphs_dict(diagram.subgraphs)

    # 1. Filter out phantom nodes that are actually subgraph references
    for sub_id in all_subgraphs:
        if sub_id in diagram.nodes and diagram.nodes[sub_id].label == sub_id:
            del diagram.nodes[sub_id]

    # 2. Text sizing heuristics for each node
    node_dims: Dict[str, Tuple[float, float, str]] = {}
    node_subgraph: Dict[str, str] = {}
    for sub in all_subgraphs.values():
        for nid in sub.node_ids:
            node_subgraph[nid] = sub.id

    node_wrapped_text: Dict[str, str] = {}
    for nid, node in diagram.nodes.items():
        w, h, lines = estimate_text_dimensions(
            text=node.label,
            font_size_pt=10.0,
            min_width_in=1.8 if node.shape == ShapeType.DIAMOND else 1.5,
            min_height_in=0.9 if node.shape == ShapeType.DIAMOND else 0.75,
            max_width_in=3.2,
        )
        node_dims[nid] = (w, h, node_subgraph.get(nid))
        node_wrapped_text[nid] = "\n".join(lines)

    # 3. Extract edge pairs for layout ranking, expanding subgraph endpoints to member nodes
    edge_pairs: List[Tuple[str, str]] = []
    for e in diagram.edges:
        src_nodes = [e.source_id]
        if e.source_id in all_subgraphs:
            src_nodes = _get_subgraph_all_nodes(all_subgraphs[e.source_id])
        dst_nodes = [e.target_id]
        if e.target_id in all_subgraphs:
            dst_nodes = _get_subgraph_all_nodes(all_subgraphs[e.target_id])
        for s_node in src_nodes:
            for d_node in dst_nodes:
                if s_node in diagram.nodes and d_node in diagram.nodes:
                    edge_pairs.append((s_node, d_node))

    # Add topological precedence for top-level subgraphs:
    # If an edge enters a top-level subgraph (directly or via any descendant),
    # all nodes in that top-level subgraph must follow the source nodes.
    for e in diagram.edges:
        target_top = None
        for top_s in diagram.subgraphs:
            if _is_in_subgraph_hierarchy(top_s, e.target_id):
                target_top = top_s
                break
        if target_top:
            if _is_in_subgraph_hierarchy(target_top, e.source_id):
                continue
            src_nodes = [e.source_id]
            if e.source_id in all_subgraphs:
                src_nodes = _get_subgraph_all_nodes(all_subgraphs[e.source_id])
            top_nodes = _get_subgraph_all_nodes(target_top)
            for s_n in src_nodes:
                if s_n in diagram.nodes:
                    for t_n in top_nodes:
                        if t_n in diagram.nodes and t_n != s_n:
                            edge_pairs.append((s_n, t_n))

    # 4. Extract subgraphs for layout synthesis
    subgraph_map = {
        s_id: (s.title, _get_subgraph_all_nodes(s))
        for s_id, s in all_subgraphs.items()
    }

    # 5. Run Sugiyama topological layout
    layout_engine = SugiyamaLayoutEngine(
        direction=diagram.direction,
        rank_gap=1.0,
        node_gap=0.6,
        page_margin=1.0,
    )
    layout_res = layout_engine.layout(node_dims, edge_pairs, subgraph_map)

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []
    shape_id_counter = 1
    node_to_shape_id: Dict[str, int] = {}
    node_extra_connections = defaultdict(list)

    # 5b. Pre-calculate connector endpoints and distribute connection ports
    diamond_outgoing = defaultdict(list)
    for idx, edge in enumerate(diagram.edges):
        if edge.source_id in diagram.nodes and diagram.nodes[edge.source_id].shape == ShapeType.DIAMOND:
            diamond_outgoing[edge.source_id].append(idx)

    edge_port_info = {}
    src_port_groups = defaultdict(list)
    dst_port_groups = defaultdict(list)

    for idx, edge in enumerate(diagram.edges):
        src_node = layout_res.nodes.get(edge.source_id) or layout_res.subgraphs.get(edge.source_id)
        dst_node = layout_res.nodes.get(edge.target_id) or layout_res.subgraphs.get(edge.target_id)
        if not src_node or not dst_node:
            continue

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

        # Decision diamond branch separation: if 2 branches, route one out side (Right)
        if edge.source_id in diamond_outgoing and len(diamond_outgoing[edge.source_id]) == 2:
            branches = diamond_outgoing[edge.source_id]
            is_second = (idx == branches[1])
            lbl = (edge.label or "").lower()
            is_negative = any(w in lbl for w in ("no", "false", "reject", "cancel", "fail", "hayır", "hata"))
            if is_negative or (is_second and not any(w in (diagram.edges[branches[0]].label or "").lower() for w in ("no", "false"))):
                src_port = "Right" if diagram.direction in ("TD", "TB") else "Bottom"
                bx = round(src_node.pin_x + src_node.width * 0.5, 4) if src_port == "Right" else round(src_node.pin_x, 4)
                by = round(src_node.pin_y, 4) if src_port == "Right" else round(src_node.pin_y - src_node.height * 0.5, 4)
                src_part = 103 if src_port == "Right" else 101

        edge_port_info[idx] = {
            "bx": bx, "by": by, "ex": ex, "ey": ey,
            "src_port": src_port, "dst_port": dst_port,
            "src_part": src_part, "dst_part": dst_part,
        }
        src_port_groups[(edge.source_id, src_port)].append(idx)
        dst_port_groups[(edge.target_id, dst_port)].append(idx)

    # Distribute connection points along sides with multiple edges
    for (nid, side), edge_indices in src_port_groups.items():
        if len(edge_indices) > 1:
            node = layout_res.nodes.get(nid) or layout_res.subgraphs.get(nid)
            if not node:
                continue
            k = len(edge_indices)
            def _get_dst_y(i):
                t = layout_res.nodes.get(diagram.edges[i].target_id) or layout_res.subgraphs.get(diagram.edges[i].target_id)
                return t.pin_y if t else 0.0
            def _get_dst_x(i):
                t = layout_res.nodes.get(diagram.edges[i].target_id) or layout_res.subgraphs.get(diagram.edges[i].target_id)
                return t.pin_x if t else 0.0

            if side in ("Left", "Right"):
                edge_indices.sort(key=_get_dst_y)
            else:
                edge_indices.sort(key=_get_dst_x)

            for order_idx, e_idx in enumerate(edge_indices):
                frac = (order_idx + 1.0) / (k + 1.0)
                port_name = f"{side}_{order_idx}"
                edge_port_info[e_idx]["src_port"] = port_name
                if side == "Right":
                    bx = node.pin_x + node.width * 0.5
                    by = node.pin_y + node.height * (frac - 0.5)
                    fx, fy = "Width*1", f"Height*{round(frac, 4)}"
                    node_extra_connections[nid].append((port_name, node.width, node.height * frac, fx, fy))
                elif side == "Left":
                    bx = node.pin_x - node.width * 0.5
                    by = node.pin_y + node.height * (frac - 0.5)
                    fx, fy = "Width*0", f"Height*{round(frac, 4)}"
                    node_extra_connections[nid].append((port_name, 0.0, node.height * frac, fx, fy))
                elif side == "Bottom":
                    bx = node.pin_x + node.width * (frac - 0.5)
                    by = node.pin_y - node.height * 0.5
                    fx, fy = f"Width*{round(frac, 4)}", "Height*0"
                    node_extra_connections[nid].append((port_name, node.width * frac, 0.0, fx, fy))
                else:  # Top
                    bx = node.pin_x + node.width * (frac - 0.5)
                    by = node.pin_y + node.height * 0.5
                    fx, fy = f"Width*{round(frac, 4)}", "Height*1"
                    node_extra_connections[nid].append((port_name, node.width * frac, node.height, fx, fy))
                edge_port_info[e_idx]["bx"] = round(bx, 4)
                edge_port_info[e_idx]["by"] = round(by, 4)

    for (nid, side), edge_indices in dst_port_groups.items():
        if len(edge_indices) > 1:
            node = layout_res.nodes.get(nid) or layout_res.subgraphs.get(nid)
            if not node:
                continue
            k = len(edge_indices)
            def _get_src_y(i):
                s = layout_res.nodes.get(diagram.edges[i].source_id) or layout_res.subgraphs.get(diagram.edges[i].source_id)
                return s.pin_y if s else 0.0
            def _get_src_x(i):
                s = layout_res.nodes.get(diagram.edges[i].source_id) or layout_res.subgraphs.get(diagram.edges[i].source_id)
                return s.pin_x if s else 0.0

            if side in ("Left", "Right"):
                edge_indices.sort(key=_get_src_y)
            else:
                edge_indices.sort(key=_get_src_x)

            for order_idx, e_idx in enumerate(edge_indices):
                frac = (order_idx + 1.0) / (k + 1.0)
                port_name = f"{side}_in_{order_idx}"
                edge_port_info[e_idx]["dst_port"] = port_name
                if side == "Right":
                    ex = node.pin_x + node.width * 0.5
                    ey = node.pin_y + node.height * (frac - 0.5)
                    fx, fy = "Width*1", f"Height*{round(frac, 4)}"
                    node_extra_connections[nid].append((port_name, node.width, node.height * frac, fx, fy))
                elif side == "Left":
                    ex = node.pin_x - node.width * 0.5
                    ey = node.pin_y + node.height * (frac - 0.5)
                    fx, fy = "Width*0", f"Height*{round(frac, 4)}"
                    node_extra_connections[nid].append((port_name, 0.0, node.height * frac, fx, fy))
                elif side == "Bottom":
                    ex = node.pin_x + node.width * (frac - 0.5)
                    ey = node.pin_y - node.height * 0.5
                    fx, fy = f"Width*{round(frac, 4)}", "Height*0"
                    node_extra_connections[nid].append((port_name, node.width * frac, 0.0, fx, fy))
                else:  # Top
                    ex = node.pin_x + node.width * (frac - 0.5)
                    ey = node.pin_y + node.height * 0.5
                    fx, fy = f"Width*{round(frac, 4)}", "Height*1"
                    node_extra_connections[nid].append((port_name, node.width * frac, node.height, fx, fy))
                edge_port_info[e_idx]["ex"] = round(ex, 4)
                edge_port_info[e_idx]["ey"] = round(ey, 4)

    # 5c. Render Subgraph Containers (rendered in topological order: parents then children)
    for sub in _get_all_subgraphs_ordered(diagram.subgraphs):
        sub_id = sub.id
        if sub_id not in layout_res.subgraphs:
            continue
        sub_info = layout_res.subgraphs[sub_id]
        cont_id = shape_id_counter
        shape_id_counter += 1
        node_to_shape_id[sub_id] = cont_id

        # Container bounding box
        cont_xml = build_2d_shape_xml(
            shape_id=cont_id,
            name=f"Container_{sub_id}",
            pin_x=sub_info.pin_x,
            pin_y=sub_info.pin_y,
            width=sub_info.width,
            height=sub_info.height,
            text="",
            shape_type="rectangle",
            fill_color=palette.subgraph_fill,
            line_color=palette.subgraph_border,
            line_weight_in=0.0208,
            line_pattern=2,  # Dashed boundary
            rounding_in=0.1,
            is_container=True,
            extra_connections=node_extra_connections.get(sub_id),
        )
        shapes_xml_list.append(cont_xml)

        # Header banner for title
        hdr_id = shape_id_counter
        shape_id_counter += 1
        hdr_w = max(2.2, min(sub_info.width - 0.4, 5.0))
        hdr_h = 0.35
        hdr_pin_x = sub_info.pin_x
        hdr_pin_y = sub_info.pin_y + sub_info.height / 2.0 - hdr_h / 2.0 - 0.05

        hdr_xml = build_2d_shape_xml(
            shape_id=hdr_id,
            name=f"Header_{sub_id}",
            pin_x=hdr_pin_x,
            pin_y=hdr_pin_y,
            width=hdr_w,
            height=hdr_h,
            text=sub_info.title,
            shape_type="rectangle",
            fill_color=palette.subgraph_border,
            line_color=palette.subgraph_border,
            text_color="#ffffff" if is_dark_color(palette.subgraph_border) else palette.subgraph_text,
            line_weight_in=0.01,
            rounding_in=0.05,
            font_name=font_name,
            font_size_pt=9.0,
            has_connections=False,
        )
        shapes_xml_list.append(hdr_xml)

    # 6. Render 2D Node Shapes
    for nid, node in diagram.nodes.items():
        s_id = shape_id_counter
        shape_id_counter += 1
        node_to_shape_id[nid] = s_id

        l_node = layout_res.nodes[nid]
        geom_type = SHAPE_MAP.get(node.shape, "rectangle")

        # Palette semantic color selection
        fill_col = palette.default_fill
        border_col = palette.default_border
        text_col = palette.default_text

        if node.shape == ShapeType.DIAMOND:
            fill_col = palette.decision_fill
            border_col = palette.decision_border
            text_col = palette.default_text
        elif node.shape == ShapeType.CYLINDER:
            fill_col = palette.database_fill
            border_col = palette.database_border
            text_col = palette.default_text
        elif node.shape == ShapeType.STADIUM:
            fill_col = palette.terminal_fill
            border_col = palette.terminal_border
            text_col = palette.default_text

        # If font background is black or dark, font face MUST be white
        if is_dark_color(fill_col):
            text_col = "#ffffff"

        shape_xml = build_2d_shape_xml(
            shape_id=s_id,
            name=f"Node_{nid}",
            pin_x=l_node.pin_x,
            pin_y=l_node.pin_y,
            width=l_node.width,
            height=l_node.height,
            text=node_wrapped_text.get(nid, node.label),
            shape_type=geom_type,
            fill_color=fill_col,
            line_color=border_col,
            text_color=text_col,
            line_weight_in=0.0208,
            font_name=font_name,
            font_size_pt=10.0,
            extra_connections=node_extra_connections.get(nid),
        )
        shapes_xml_list.append(shape_xml)

    # 7. Render 1D Connectors & <Connects>
    for idx, edge in enumerate(diagram.edges):
        if edge.source_id not in node_to_shape_id or edge.target_id not in node_to_shape_id:
            continue

        c_id = shape_id_counter
        shape_id_counter += 1

        src_s_id = node_to_shape_id[edge.source_id]
        dst_s_id = node_to_shape_id[edge.target_id]

        # Arrow markers and line pattern
        begin_arrow = 13 if edge.arrow_start != ArrowType.NONE else 0
        end_arrow = 13 if edge.arrow_end != ArrowType.NONE else 0
        line_pat = 2 if edge.style == EdgeStyle.DOTTED else 1
        line_wt = 0.032 if edge.style == EdgeStyle.THICK else 0.018
        arr_sz = 3 if edge.style == EdgeStyle.THICK else 2

        info = edge_port_info.get(idx, {})
        bx = info.get("bx", 0.0)
        by = info.get("by", 0.0)
        ex = info.get("ex", 0.0)
        ey = info.get("ey", 0.0)
        src_port = info.get("src_port", "Bottom")
        dst_port = info.get("dst_port", "Top")
        src_part = info.get("src_part", 101)
        dst_part = info.get("dst_part", 100)

        # Thread skip-level edges through intermediate dummy waypoints
        waypoints = layout_res.edge_routes.get((edge.source_id, edge.target_id))

        conn_xml = build_1d_connector_xml(
            connector_id=c_id,
            begin_x=bx,
            begin_y=by,
            end_x=ex,
            end_y=ey,
            label=edge.label or "",
            line_color=palette.connector_line,
            line_weight_in=line_wt,
            line_pattern=line_pat,
            begin_arrow=begin_arrow,
            end_arrow=end_arrow,
            end_arrow_size=arr_sz,
            font_name=font_name,
            font_size_pt=9.0,
            text_color=palette.connector_text,
            is_dynamic=True,
            source_shape_id=src_s_id,
            target_shape_id=dst_s_id,
            src_port=src_port,
            dst_port=dst_port,
            routing_direction=diagram.direction,
            intermediate_waypoints=waypoints,
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

    # 8. Serialize to vsdx
    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=layout_res.page_width,
        page_height=layout_res.page_height,
    )
