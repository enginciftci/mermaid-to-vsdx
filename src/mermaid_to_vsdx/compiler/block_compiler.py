"""
Native headless compiler for Mermaid Block Diagrams.
Transforms BlockDiagram AST into Open Packaging Conventions Visio XML.
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from ..parser.ast_nodes import BlockDiagram, BlockNode, BlockEdge, ShapeType
from ..visio.palettes import PALETTES, DEFAULT_PALETTE_NAME, is_dark_color
from .shapesheet import build_2d_shape_xml, build_1d_connector_xml
from .opc_package import package_vsdx


class BlockLayoutBox:
    def __init__(
        self,
        node: BlockNode,
        x: float,
        y: float,
        w: float,
        h: float,
        shape_id: int = 0
    ):
        self.node = node
        self.x = x  # Center X
        self.y = y  # Center Y
        self.w = w
        self.h = h
        self.shape_id = shape_id
        self.children: List["BlockLayoutBox"] = []


def _layout_grid(
    nodes: List[BlockNode],
    cols: int,
    start_x: float,
    start_y: float,
    cell_w: float = 2.0,
    cell_h: float = 1.0,
    gap_x: float = 0.4,
    gap_y: float = 0.4,
    counter: int = 1
) -> Tuple[List[BlockLayoutBox], float, float, int]:
    """
    Arranges blocks into a grid, placing items left-to-right, wrapping across rows.
    Returns (boxes, total_width, total_height, counter).
    """
    boxes: List[BlockLayoutBox] = []
    if not nodes:
        return boxes, 0.0, 0.0, counter

    cols = max(1, cols)

    # First pass: layout any composite blocks to get their dimensions
    node_sizes: List[Tuple[float, float, List[BlockLayoutBox]]] = []
    for n in nodes:
        if n.children:
            child_cols = n.columns if n.columns else max(1, len(n.children))
            c_boxes, c_w, c_h, counter = _layout_grid(
                n.children, child_cols, 0.0, 0.0, cell_w, cell_h, gap_x, gap_y, counter
            )
            # Add padding around composite container
            comp_w = max(n.width_cols * cell_w + (n.width_cols - 1) * gap_x, c_w + 0.6)
            comp_h = c_h + 0.7
            node_sizes.append((comp_w, comp_h, c_boxes))
        else:
            w = n.width_cols * cell_w + (n.width_cols - 1) * gap_x
            h = cell_h
            node_sizes.append((w, h, []))

    # Second pass: assign row and col positions
    cur_col = 0
    cur_row = 0
    row_heights: Dict[int, float] = {}
    row_assignments: List[Tuple[int, int, int]] = []  # (row, col_start, col_span)

    for idx, n in enumerate(nodes):
        span = min(cols, max(1, n.width_cols))
        if cur_col + span > cols and cur_col > 0:
            cur_row += 1
            cur_col = 0

        row_assignments.append((cur_row, cur_col, span))
        w, h, _ = node_sizes[idx]
        row_heights[cur_row] = max(row_heights.get(cur_row, cell_h), h)

        cur_col += span
        if cur_col >= cols:
            cur_row += 1
            cur_col = 0

    total_rows = cur_row + (1 if cur_col > 0 else 0)
    total_grid_w = cols * cell_w + (cols - 1) * gap_x

    # Calculate row Y offsets
    row_y_offsets: Dict[int, float] = {}
    accum_y = 0.0
    for r in range(total_rows):
        rh = row_heights.get(r, cell_h)
        row_y_offsets[r] = accum_y + rh / 2.0
        accum_y += rh + gap_y
    total_grid_h = max(cell_h, accum_y - gap_y)

    # Position each block
    for idx, n in enumerate(nodes):
        r, c_start, span = row_assignments[idx]
        w, h, child_boxes = node_sizes[idx]

        # Center of the cell span
        span_left = c_start * (cell_w + gap_x)
        span_w = span * cell_w + (span - 1) * gap_x
        center_x = start_x + span_left + span_w / 2.0
        center_y = start_y - row_y_offsets[r]

        box_id = counter
        counter += 1
        box = BlockLayoutBox(node=n, x=center_x, y=center_y, w=w, h=h, shape_id=box_id)

        # Shift child boxes into absolute coordinates
        if child_boxes:
            c_top = center_y + h / 2.0 - 0.45
            c_left = center_x - w / 2.0 + 0.3
            for cb in child_boxes:
                cb.x = c_left + cb.x
                cb.y = c_top + cb.y
                box.children.append(cb)

        boxes.append(box)

    return boxes, total_grid_w, total_grid_h, counter


def compile_block_to_vsdx(
    diagram: BlockDiagram,
    output_path: str,
    palette_name: str = DEFAULT_PALETTE_NAME,
    font_name: str = "Segoe UI",
) -> str:
    palette = PALETTES.get(palette_name, PALETTES[DEFAULT_PALETTE_NAME])

    cols = diagram.columns if diagram.columns > 0 else max(1, len(diagram.blocks))
    cell_w = 2.0
    cell_h = 0.9
    gap_x = 0.45
    gap_y = 0.45

    counter = 1
    boxes, grid_w, grid_h, counter = _layout_grid(
        diagram.blocks, cols, 1.2, 0.0, cell_w, cell_h, gap_x, gap_y, counter
    )

    page_width = max(8.5, round(grid_w + 2.4, 2))
    page_height = max(11.0, round(grid_h + 2.4, 2))

    # Shift boxes down so start_y corresponds to page top
    top_y = page_height - 1.2
    for b in boxes:
        b.y += top_y
        for cb in b.children:
            cb.y += top_y

    shapes_xml_list: List[str] = []
    shape_id_map: Dict[str, int] = {}
    box_coord_map: Dict[str, BlockLayoutBox] = {}

    def collect_boxes(b_list: List[BlockLayoutBox]):
        for b in b_list:
            if not b.node.is_space:
                shape_id_map[b.node.id] = b.shape_id
                box_coord_map[b.node.id] = b
            if b.children:
                collect_boxes(b.children)

    collect_boxes(boxes)

    # 1. Render Composite Containers
    def render_containers(b_list: List[BlockLayoutBox]):
        for b in b_list:
            if b.children:
                shapes_xml_list.append(build_2d_shape_xml(
                    shape_id=b.shape_id,
                    name=f"Container_{b.node.id}",
                    pin_x=round(b.x, 4),
                    pin_y=round(b.y, 4),
                    width=round(b.w, 4),
                    height=round(b.h, 4),
                    text="",
                    shape_type="rectangle",
                    fill_color=palette.subgraph_fill,
                    line_color=palette.subgraph_border,
                    line_weight_in=0.015,
                    line_pattern=2,
                    rounding_in=0.08,
                    has_connections=False,
                ))
                # Container title label
                t_h = 0.28
                t_w = max(1.2, len(b.node.label) * 0.10 + 0.3)
                t_y = b.y + b.h / 2.0 - t_h / 2.0 - 0.05
                t_x = b.x - b.w / 2.0 + t_w / 2.0 + 0.15
                shapes_xml_list.append(build_2d_shape_xml(
                    shape_id=b.shape_id + 10000,
                    name=f"Title_{b.node.id}",
                    pin_x=round(t_x, 4),
                    pin_y=round(t_y, 4),
                    width=round(t_w, 4),
                    height=round(t_h, 4),
                    text=b.node.label,
                    shape_type="rectangle",
                    fill_color="#f1f5f9",
                    line_color=palette.subgraph_border,
                    text_color=palette.subgraph_text,
                    line_weight_in=0.01,
                    font_name=font_name,
                    font_size_pt=8.5,
                    bold=True,
                    has_connections=False,
                ))
                render_containers(b.children)

    render_containers(boxes)

    # 2. Render Leaf Node Shapes
    def render_nodes(b_list: List[BlockLayoutBox]):
        for b in b_list:
            if b.node.is_space:
                continue
            if b.children:
                render_nodes(b.children)
                continue

            # Determine colors from style / class / palette
            fill_col = b.node.style.get("fill", palette.default_fill)
            stroke_col = b.node.style.get("stroke", palette.default_border)
            text_col = b.node.style.get("color", "#ffffff" if is_dark_color(fill_col) else palette.default_text)

            st = b.node.shape.value if hasattr(b.node.shape, 'value') else "rectangle"

            shapes_xml_list.append(build_2d_shape_xml(
                shape_id=b.shape_id,
                name=f"Block_{b.node.id}",
                pin_x=round(b.x, 4),
                pin_y=round(b.y, 4),
                width=round(b.w, 4),
                height=round(b.h, 4),
                text=b.node.label,
                shape_type=st,
                fill_color=fill_col,
                line_color=stroke_col,
                text_color=text_col,
                line_weight_in=0.018,
                font_name=font_name,
                font_size_pt=9.5,
            ))

    render_nodes(boxes)

    # 3. Render Edges
    edge_counter = counter + 20000
    for edge in diagram.edges:
        src_b = box_coord_map.get(edge.source_id)
        dst_b = box_coord_map.get(edge.target_id)
        if not src_b or not dst_b:
            continue

        e_id = edge_counter
        edge_counter += 1

        dx = dst_b.x - src_b.x
        dy = dst_b.y - src_b.y

        # Determine edge connection ports
        if abs(dx) > abs(dy):
            if dx > 0:
                bx = src_b.x + src_b.w / 2.0
                by = src_b.y
                ex = dst_b.x - dst_b.w / 2.0
                ey = dst_b.y
                src_port = "Right"
                dst_port = "Left"
            else:
                bx = src_b.x - src_b.w / 2.0
                by = src_b.y
                ex = dst_b.x + dst_b.w / 2.0
                ey = dst_b.y
                src_port = "Left"
                dst_port = "Right"
        else:
            if dy > 0:
                bx = src_b.x
                by = src_b.y + src_b.h / 2.0
                ex = dst_b.x
                ey = dst_b.y - dst_b.h / 2.0
                src_port = "Top"
                dst_port = "Bottom"
            else:
                bx = src_b.x
                by = src_b.y - src_b.h / 2.0
                ex = dst_b.x
                ey = dst_b.y + dst_b.h / 2.0
                src_port = "Bottom"
                dst_port = "Top"

        shapes_xml_list.append(build_1d_connector_xml(
            connector_id=e_id,
            begin_x=round(bx, 4),
            begin_y=round(by, 4),
            end_x=round(ex, 4),
            end_y=round(ey, 4),
            label=edge.label,
            line_color=palette.connector_line,
            line_weight_in=0.018,
            end_arrow=13 if edge.has_arrow else 0,
            font_name=font_name,
            font_size_pt=9.0,
            text_color=palette.connector_text,
            is_dynamic=True,
            source_shape_id=src_b.shape_id,
            target_shape_id=dst_b.shape_id,
            src_port=src_port,
            dst_port=dst_port,
        ))

    return package_vsdx(
        output_path=output_path,
        shapes_xml="\n".join(shapes_xml_list),
        connects_xml="",
        page_width=page_width,
        page_height=page_height,
    )
