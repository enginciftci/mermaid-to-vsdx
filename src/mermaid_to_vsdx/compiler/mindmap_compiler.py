"""
Visio Compiler for Mermaid Mindmap Diagrams (`mindmap`).
Implements a balanced Left-Right Horizontal Tree Layout with branch-coded accent palettes
and dynamic ShapeSheet connectors.
"""

import math
from typing import Dict, List, Tuple
from ..parser.ast_nodes import MindmapDiagram, MindmapNode, ShapeType
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
    distribute_shared_ports,
)


_LIGHT_BRANCH_THEMES = [
    # (level1_fill, leaf_fill, border, text)
    ("#dbeafe", "#eff6ff", "#2563eb", "#1e3a8a"),  # Royal Blue
    ("#d1fae5", "#ecfdf5", "#059669", "#064e3b"),  # Emerald
    ("#fef3c7", "#fffbeb", "#d97706", "#78350f"),  # Amber
    ("#f3e8ff", "#faf5ff", "#9333ea", "#581c87"),  # Purple
    ("#ffe4e6", "#fff1f2", "#e11d48", "#881337"),  # Rose
    ("#ccfbf1", "#f0fdfa", "#0d9488", "#134e4a"),  # Teal
]

_DARK_BRANCH_THEMES = [
    ("#1e3a8a", "#172554", "#38bdf8", "#f8fafc"),
    ("#064e3b", "#022c22", "#34d399", "#f8fafc"),
    ("#78350f", "#451a03", "#fbbf24", "#f8fafc"),
    ("#581c87", "#3b0764", "#c084fc", "#f8fafc"),
    ("#881337", "#4c0519", "#fb7185", "#f8fafc"),
    ("#134e4a", "#042f2e", "#2dd4bf", "#f8fafc"),
]


def _measure_mindmap_node(node: MindmapNode) -> Tuple[float, float]:
    lines = (node.label or "Node").split("\n")
    max_chars = max(len(ln) for ln in lines) if lines else 4
    num_lines = len(lines)

    if node.level == 0:
        w = max(2.10, min(3.40, max_chars * 0.115 + 0.65))
        h = max(0.88, num_lines * 0.28 + 0.48)
        if node.shape in (ShapeType.CIRCLE, ShapeType.DOUBLE_CIRCLE):
            w = max(w, 2.15)
            h = max(h, 1.15)
    elif node.level == 1:
        w = max(1.65, min(2.85, max_chars * 0.098 + 0.50))
        h = max(0.58, num_lines * 0.24 + 0.32)
    else:
        w = max(1.45, min(2.60, max_chars * 0.088 + 0.42))
        h = max(0.46, num_lines * 0.22 + 0.24)

    return round(w, 4), round(h, 4)


def compile_mindmap_to_vsdx(
    diagram: MindmapDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    """
    Compiles a MindmapDiagram AST into a native Microsoft Visio (.vsdx) file.
    """
    palette = get_palette(palette_name)
    dark_mode = is_dark_color(palette.background)
    branch_themes = _DARK_BRANCH_THEMES if dark_mode else _LIGHT_BRANCH_THEMES

    root = diagram.root or MindmapNode(id="mm_root", label="Mindmap", shape=ShapeType.CIRCLE, level=0)

    # 1. Assign unique internal keys and measure every node
    node_dims: Dict[int, Tuple[float, float]] = {}
    node_branch_idx: Dict[int, int] = {}
    all_nodes: List[MindmapNode] = []

    def _index_nodes(n: MindmapNode, b_idx: int):
        all_nodes.append(n)
        node_dims[id(n)] = _measure_mindmap_node(n)
        node_branch_idx[id(n)] = b_idx
        for idx_c, child in enumerate(n.children):
            child_b = idx_c if n.level == 0 else b_idx
            _index_nodes(child, child_b)

    _index_nodes(root, 0)

    # 2. Split level-1 children into Right and Left balanced halves
    l1_children = root.children
    right_branches: List[MindmapNode] = []
    left_branches: List[MindmapNode] = []

    def _subtree_span(n: MindmapNode) -> float:
        _, nh = node_dims[id(n)]
        v_gap = 0.24 if n.level >= 1 else 0.32
        if not n.children:
            return nh + v_gap
        children_sum = sum(_subtree_span(c) for c in n.children)
        group_pad = 0.18 if n.level == 1 else 0.08
        return max(nh + v_gap, children_sum + group_pad)

    subtree_heights: Dict[int, float] = {}

    def _compute_all_spans(n: MindmapNode) -> float:
        sp = _subtree_span(n)
        subtree_heights[id(n)] = sp
        for c in n.children:
            _compute_all_spans(c)
        return sp

    _compute_all_spans(root)

    if len(l1_children) == 1:
        right_branches = [l1_children[0]]
    elif len(l1_children) > 1:
        total_span = sum(subtree_heights[id(c)] for c in l1_children)
        acc = 0.0
        for idx_c, c in enumerate(l1_children):
            if idx_c == 0 or (acc + subtree_heights[id(c)] * 0.5 <= total_span * 0.52 and len(right_branches) < len(l1_children) - 1):
                right_branches.append(c)
                acc += subtree_heights[id(c)]
            else:
                left_branches.append(c)

    # 3. Compute relative coordinates with root at (0.0, 0.0)
    rel_pos: Dict[int, Tuple[float, float]] = {}
    node_side: Dict[int, str] = {}  # "center", "right", "left"
    rel_pos[id(root)] = (0.0, 0.0)
    node_side[id(root)] = "center"
    h_gap = 0.88

    def _layout_subtree(n: MindmapNode, px: float, y_bottom: float, y_top: float, side: str):
        nw, nh = node_dims[id(n)]
        cy = (y_bottom + y_top) * 0.5
        node_side[id(n)] = side

        if not n.children:
            rel_pos[id(n)] = (px, cy)
            return

        total_child_h = sum(subtree_heights[id(c)] for c in n.children)
        cur_top = cy + total_child_h * 0.5
        child_ys = []
        for c in n.children:
            ch_span = subtree_heights[id(c)]
            cw, _ = node_dims[id(c)]
            if side == "right":
                cx = px + nw * 0.5 + h_gap + cw * 0.5
            else:
                cx = px - nw * 0.5 - h_gap - cw * 0.5
            c_bot = cur_top - ch_span
            _layout_subtree(c, cx, c_bot, cur_top, side)
            child_ys.append(rel_pos[id(c)][1])
            cur_top = c_bot

        # Center parent vertically between first and last child
        parent_y = (child_ys[0] + child_ys[-1]) * 0.5 if child_ys else cy
        rel_pos[id(n)] = (px, parent_y)

    root_w, root_h = node_dims[id(root)]

    if right_branches:
        r_total = sum(subtree_heights[id(c)] for c in right_branches)
        cur_top = r_total * 0.5
        for c in right_branches:
            ch_span = subtree_heights[id(c)]
            cw, _ = node_dims[id(c)]
            cx = root_w * 0.5 + h_gap + cw * 0.5
            _layout_subtree(c, cx, cur_top - ch_span, cur_top, "right")
            cur_top -= ch_span

    if left_branches:
        l_total = sum(subtree_heights[id(c)] for c in left_branches)
        cur_top = l_total * 0.5
        for c in left_branches:
            ch_span = subtree_heights[id(c)]
            cw, _ = node_dims[id(c)]
            cx = -(root_w * 0.5 + h_gap + cw * 0.5)
            _layout_subtree(c, cx, cur_top - ch_span, cur_top, "left")
            cur_top -= ch_span

    # 4. Compute bounding box and translate to positive Visio page coordinates
    min_x = min(rel_pos[id(n)][0] - node_dims[id(n)][0] * 0.5 for n in all_nodes)
    max_x = max(rel_pos[id(n)][0] + node_dims[id(n)][0] * 0.5 for n in all_nodes)
    min_y = min(rel_pos[id(n)][1] - node_dims[id(n)][1] * 0.5 for n in all_nodes)
    max_y = max(rel_pos[id(n)][1] + node_dims[id(n)][1] * 0.5 for n in all_nodes)

    margin_x = 0.85
    margin_y = 0.85
    title_space = 0.65 if diagram.title else 0.0

    content_w = max_x - min_x
    content_h = max_y - min_y
    page_w = round(max(11.0, content_w + 2 * margin_x), 2)
    page_h = round(max(8.5, content_h + 2 * margin_y + title_space), 2)

    offset_x = (page_w - content_w) * 0.5 - min_x
    offset_y = (page_h - title_space - content_h) * 0.5 - min_y

    abs_pos: Dict[int, Tuple[float, float]] = {}
    nodes_geom: Dict[str, Tuple[float, float, float, float]] = {}
    node_shape_id: Dict[int, int] = {}

    shape_id_counter = 1
    for n in all_nodes:
        rx, ry = rel_pos[id(n)]
        nw, nh = node_dims[id(n)]
        ax = round(rx + offset_x, 4)
        ay = round(ry + offset_y, 4)
        abs_pos[id(n)] = (ax, ay)
        sid = shape_id_counter
        shape_id_counter += 1
        node_shape_id[id(n)] = sid
        nodes_geom[str(id(n))] = (ax, ay, nw, nh)

    # 5. Collect parent->child edges and distribute ports
    edge_pairs: List[Tuple[str, str]] = []
    custom_ports: Dict[int, Tuple[float, float, float, float, str, str, int, int]] = {}
    edge_nodes: List[Tuple[MindmapNode, MindmapNode]] = []

    def _collect_edges(parent: MindmapNode):
        px, py = abs_pos[id(parent)]
        pw, ph = node_dims[id(parent)]
        for child in parent.children:
            cx, cy = abs_pos[id(child)]
            cw, ch = node_dims[id(child)]
            e_idx = len(edge_pairs)
            edge_pairs.append((str(id(parent)), str(id(child))))
            edge_nodes.append((parent, child))
            side = node_side[id(child)]
            if side == "right":
                custom_ports[e_idx] = (
                    round(px + pw * 0.5, 4),
                    round(py, 4),
                    round(cx - cw * 0.5, 4),
                    round(cy, 4),
                    "Right",
                    "Left",
                    103,
                    102,
                )
            else:
                custom_ports[e_idx] = (
                    round(px - pw * 0.5, 4),
                    round(py, 4),
                    round(cx + cw * 0.5, 4),
                    round(cy, 4),
                    "Left",
                    "Right",
                    102,
                    103,
                )
            _collect_edges(child)

    _collect_edges(root)

    routed_ports, node_extra_connections = distribute_shared_ports(
        nodes_geom=nodes_geom,
        edge_pairs=edge_pairs,
        direction="LR",
        custom_ports=custom_ports,
    )

    shapes_xml_list: List[str] = []
    connects_xml_list: List[str] = []

    # Optional title banner
    if diagram.title:
        title_sid = shape_id_counter
        shape_id_counter += 1
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=title_sid,
                name="Mindmap_Title",
                pin_x=round(page_w * 0.5, 4),
                pin_y=round(page_h - 0.52, 4),
                width=round(min(page_w - 1.2, max(4.2, len(diagram.title) * 0.14 + 1.0)), 4),
                height=0.48,
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

    # 6. Emit 2D node shapes
    for n in all_nodes:
        sid = node_shape_id[id(n)]
        ax, ay = abs_pos[id(n)]
        nw, nh = node_dims[id(n)]
        b_idx = node_branch_idx[id(n)]
        l1_fill, leaf_fill, br_border, br_text = branch_themes[b_idx % len(branch_themes)]

        if n.level == 0:
            fill_c = palette.decision_fill if n.shape == ShapeType.HEXAGON else palette.terminal_fill
            line_c = palette.decision_border if n.shape == ShapeType.HEXAGON else palette.terminal_border
            text_c = get_contrasting_text_color(fill_c, palette.default_text)
            f_size = 12.0
            is_bold = True
            lw = 0.028
        elif n.level == 1:
            fill_c = l1_fill
            line_c = br_border
            text_c = get_contrasting_text_color(fill_c, br_text)
            f_size = 10.5
            is_bold = True
            lw = 0.022
        else:
            fill_c = leaf_fill
            line_c = br_border
            text_c = get_contrasting_text_color(fill_c, br_text)
            f_size = 9.5
            is_bold = False
            lw = 0.018

        extra_conns = node_extra_connections.get(str(id(n)))
        shapes_xml_list.append(
            build_2d_shape_xml(
                shape_id=sid,
                name=f"MindmapNode_{n.id}_{sid}",
                pin_x=ax,
                pin_y=ay,
                width=nw,
                height=nh,
                text=n.label,
                shape_type=n.shape.value,
                fill_color=fill_c,
                line_color=line_c,
                text_color=text_c,
                line_weight_in=lw,
                font_name=font_name,
                font_size_pt=f_size,
                bold=is_bold,
                has_connections=True,
                extra_connections=extra_conns,
                shadow=(n.level <= 1),
            )
        )

    # 7. Emit 1D connectors and Connect records
    for e_idx, (parent, child) in enumerate(edge_nodes):
        conn_id = shape_id_counter
        shape_id_counter += 1
        src_sid = node_shape_id[id(parent)]
        dst_sid = node_shape_id[id(child)]
        bx, by, ex, ey, src_port, dst_port, src_part, dst_part = routed_ports[e_idx]
        b_idx = node_branch_idx[id(child)]
        _, _, br_border, _ = branch_themes[b_idx % len(branch_themes)]

        side = node_side[id(child)]
        r_dir = "LR" if side == "right" else "RL"

        shapes_xml_list.append(
            build_1d_connector_xml(
                connector_id=conn_id,
                begin_x=bx,
                begin_y=by,
                end_x=ex,
                end_y=ey,
                label="",
                line_color=br_border,
                line_weight_in=0.022 if parent.level == 0 else 0.016,
                line_pattern=1,
                begin_arrow=0,
                end_arrow=0,
                font_name=font_name,
                text_color=palette.connector_text,
                text_bkgnd=palette.background,
                is_dynamic=True,
                source_shape_id=src_sid,
                target_shape_id=dst_sid,
                src_port=src_port,
                dst_port=dst_port,
                routing_direction=r_dir,
            )
        )
        connects_xml_list.append(
            build_connect_records(
                connector_id=conn_id,
                source_shape_id=src_sid,
                target_shape_id=dst_sid,
                src_port=src_port,
                dst_port=dst_port,
                src_part=src_part,
                dst_part=dst_part,
            )
        )

    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="\n".join(connects_xml_list),
        page_width=page_w,
        page_height=page_h,
        page_bg_color=palette.background,
    )
