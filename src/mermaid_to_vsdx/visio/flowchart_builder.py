"""
Flowchart Drawing Engine for Microsoft Visio.
Translates FlowchartDiagram AST into native .vsdx drawings with
topological layout, independent subgraph blocks/clusters, and dynamic connector routing.
"""

import os
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional
from .com_client import VisioSession
from .palettes import PaletteTheme, get_palette
from .shapes import (
    draw_node_shape,
    draw_subgraph_container,
    connect_shapes,
    format_shape_text
)
from ..parser.ast_nodes import FlowchartDiagram, Node, Edge, Subgraph, ShapeType
from ..utils.unicode_helper import DEFAULT_FONT


class FlowchartBuilder:
    """
    Builds a Visio flowchart from a FlowchartDiagram AST.
    Treats subgraphs as independent container blocks.
    """

    def __init__(
        self,
        diagram: FlowchartDiagram,
        palette: Optional[PaletteTheme] = None,
        font_name: str = DEFAULT_FONT
    ):
        self.diagram = diagram
        self.palette = palette or get_palette()
        self.font_name = font_name
        self.node_positions: Dict[str, Tuple[float, float, float, float]] = {}
        self.visio_shapes: Dict[str, object] = {}

    def build_and_save(self, output_vsdx_path: str) -> str:
        """
        Creates the Visio drawing document, lays out all elements, and saves to vsdx.
        """
        abs_output_path = os.path.abspath(output_vsdx_path)
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)

        with VisioSession(visible=False) as visio_app:
            doc = visio_app.Documents.Add("")
            page = doc.Pages.Item(1)

            # 1. Compute layout coordinates (subgraph-aware or standard)
            self._compute_layout()

            # 2. Draw subgraphs (containers) first so they sit in the background
            self._draw_subgraphs(page, visio_app)

            # 3. Draw nodes
            self._draw_nodes(page, visio_app)

            # 4. Draw connectors
            self._draw_edges(page, visio_app)

            # 5. Fit drawing to contents
            try:
                page.ResizeToFitContents()
            except Exception:
                pass

            # Save file
            doc.SaveAs(abs_output_path)
            doc.Saved = True
            doc.Close()

        return abs_output_path

    def _compute_layout(self):
        """
        Dispatches to subgraph cluster layout if subgraphs are present,
        or standard DAG topological layout otherwise.
        """
        if self.diagram.subgraphs:
            self._compute_subgraph_cluster_layout()
        else:
            self._compute_standard_layout()

    def _compute_subgraph_cluster_layout(self):
        """
        Lays out diagrams containing subgraphs as distinct, independent container blocks.
        """
        nodes = self.diagram.nodes
        direction = self.diagram.direction.upper()  # LR, RL, TD, TB, BT
        is_horizontal = direction in ("LR", "RL")

        # Map each node to its immediate subgraph
        node_to_sub = {}
        for sub in self.diagram.subgraphs:
            for nid in sub.node_ids:
                node_to_sub[nid] = sub.id

        # Unique cluster IDs: subgraphs + standalone nodes
        clusters: List[str] = []
        subgraph_map: Dict[str, Subgraph] = {}
        for sub in self.diagram.subgraphs:
            clusters.append(sub.id)
            subgraph_map[sub.id] = sub

        for nid in nodes:
            if nid not in node_to_sub:
                cid = f"standalone_{nid}"
                node_to_sub[nid] = cid
                clusters.append(cid)

        # Build inter-cluster adjacency
        cluster_adj = defaultdict(set)
        cluster_in_degree = {c: 0 for c in clusters}

        for edge in self.diagram.edges:
            c_src = node_to_sub.get(edge.source_id)
            c_tgt = node_to_sub.get(edge.target_id)
            if c_src and c_tgt and c_src != c_tgt:
                if c_tgt not in cluster_adj[c_src]:
                    cluster_adj[c_src].add(c_tgt)
                    cluster_in_degree[c_tgt] += 1

        # Compute cluster ranks via topological sort
        queue = deque([c for c, deg in cluster_in_degree.items() if deg == 0])
        if not queue and clusters:
            queue.append(clusters[0])

        cluster_ranks: Dict[str, int] = {}
        for c in queue:
            cluster_ranks[c] = 0

        visited = set(queue)
        while queue:
            curr = queue.popleft()
            cr = cluster_ranks[curr]
            for nxt in cluster_adj[curr]:
                cluster_ranks[nxt] = max(cluster_ranks.get(nxt, 0), cr + 1)
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)

        for c in clusters:
            if c not in cluster_ranks:
                cluster_ranks[c] = 0

        # Group clusters by rank
        rank_to_clusters = defaultdict(list)
        for c, r in sorted(cluster_ranks.items(), key=lambda x: (x[1], x[0])):
            rank_to_clusters[r].append(c)

        # Node and container sizing constants
        shape_w = 2.4
        shape_h = 0.9
        inner_gap_y = 0.5
        inner_gap_x = 0.6
        pad_x = 0.45
        pad_bottom = 0.45
        pad_top = 0.75  # Room for header badge
        cluster_gap_x = 1.3
        cluster_gap_y = 1.2

        self.node_positions = {}

        if is_horizontal:
            # LR / RL: Ranks advance along X; nodes within each cluster are stacked vertically along Y
            start_x = 1.5
            start_y = 10.0
            curr_x = start_x

            # Find maximum vertical span among all clusters to align centers
            max_cluster_h = 0.0
            cluster_member_map = {}
            cluster_dim_map = {}

            for c in clusters:
                if c in subgraph_map:
                    members = [nid for nid in subgraph_map[c].node_ids if nid in nodes]
                else:
                    members = [c.replace("standalone_", "")]
                cluster_member_map[c] = members

                n_count = max(len(members), 1)
                c_w = shape_w + (pad_x * 2 if c in subgraph_map else 0)
                c_h = n_count * shape_h + (n_count - 1) * inner_gap_y + (pad_top + pad_bottom if c in subgraph_map else 0)
                cluster_dim_map[c] = (c_w, c_h)
                if c_h > max_cluster_h:
                    max_cluster_h = c_h

            # Position clusters rank by rank
            max_rank = max(rank_to_clusters.keys()) if rank_to_clusters else 0
            for r in sorted(rank_to_clusters.keys()):
                effective_r = (max_rank - r) if direction == "RL" else r
                c_list = rank_to_clusters[effective_r]
                
                # Column width for this rank
                col_w = max(cluster_dim_map[c][0] for c in c_list)

                # Total height of all clusters in this rank column
                total_col_h = sum(cluster_dim_map[c][1] for c in c_list) + max(0, len(c_list) - 1) * cluster_gap_y
                top_y = start_y + (max_cluster_h / 2.0)

                running_y = top_y
                for c in c_list:
                    members = cluster_member_map[c]
                    c_w, c_h = cluster_dim_map[c]
                    is_sub = (c in subgraph_map)

                    # Cluster center X
                    c_cx = curr_x + col_w / 2.0

                    # Node X
                    node_x1 = c_cx - shape_w / 2.0
                    node_x2 = node_x1 + shape_w

                    # First node top Y inside cluster
                    node_top_y = running_y - (pad_top if is_sub else 0)

                    for idx, nid in enumerate(members):
                        ny2 = node_top_y - idx * (shape_h + inner_gap_y)
                        ny1 = ny2 - shape_h
                        self.node_positions[nid] = (node_x1, ny1, node_x2, ny2)

                    running_y -= (c_h + cluster_gap_y)

                curr_x += col_w + cluster_gap_x

        else:
            # TD / TB / BT: Ranks advance along Y (downwards); nodes in clusters are arranged horizontally or vertically
            start_x = 1.5
            start_y = 12.0
            curr_y = start_y

            cluster_member_map = {}
            cluster_dim_map = {}

            for c in clusters:
                if c in subgraph_map:
                    members = [nid for nid in subgraph_map[c].node_ids if nid in nodes]
                else:
                    members = [c.replace("standalone_", "")]
                cluster_member_map[c] = members

                n_count = max(len(members), 1)
                # In TD, place members horizontally or in 2-column grid inside subgraph
                c_w = n_count * shape_w + (n_count - 1) * inner_gap_x + (pad_x * 2 if c in subgraph_map else 0)
                c_h = shape_h + (pad_top + pad_bottom if c in subgraph_map else 0)
                cluster_dim_map[c] = (c_w, c_h)

            max_rank = max(rank_to_clusters.keys()) if rank_to_clusters else 0
            for r in sorted(rank_to_clusters.keys()):
                effective_r = (max_rank - r) if direction == "BT" else r
                c_list = rank_to_clusters[effective_r]

                row_h = max(cluster_dim_map[c][1] for c in c_list)
                total_row_w = sum(cluster_dim_map[c][0] for c in c_list) + max(0, len(c_list) - 1) * cluster_gap_x

                running_x = start_x
                for c in c_list:
                    members = cluster_member_map[c]
                    c_w, c_h = cluster_dim_map[c]
                    is_sub = (c in subgraph_map)

                    node_left_x = running_x + (pad_x if is_sub else 0)
                    node_top_y = curr_y - (pad_top if is_sub else 0)

                    for idx, nid in enumerate(members):
                        nx1 = node_left_x + idx * (shape_w + inner_gap_x)
                        nx2 = nx1 + shape_w
                        ny2 = node_top_y
                        ny1 = ny2 - shape_h
                        self.node_positions[nid] = (nx1, ny1, nx2, ny2)

                    running_x += (c_w + cluster_gap_x)

                curr_y -= (row_h + cluster_gap_y)

    def _compute_standard_layout(self):
        """
        Computes layer-based grid coordinates for standard diagrams without subgraphs.
        """
        nodes = self.diagram.nodes
        edges = self.diagram.edges
        direction = self.diagram.direction.upper()

        if not nodes:
            return

        adj = defaultdict(list)
        in_degree = {nid: 0 for nid in nodes}

        for edge in edges:
            if edge.source_id in in_degree and edge.target_id in in_degree:
                adj[edge.source_id].append(edge.target_id)
                in_degree[edge.target_id] += 1

        ranks: Dict[str, int] = {}
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])

        if not queue:
            queue.append(next(iter(nodes.keys())))

        for nid in queue:
            ranks[nid] = 0

        visited = set(queue)
        while queue:
            curr = queue.popleft()
            curr_rank = ranks[curr]
            for neighbor in adj[curr]:
                ranks[neighbor] = max(ranks.get(neighbor, 0), curr_rank + 1)
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        for nid in nodes:
            if nid not in ranks:
                ranks[nid] = 0

        rank_groups = defaultdict(list)
        for nid, r in sorted(ranks.items(), key=lambda x: (x[1], x[0])):
            rank_groups[r].append(nid)

        shape_w = 2.4
        shape_h = 1.0
        gap_x = 1.1
        gap_y = 1.2

        is_horizontal = direction in ("LR", "RL")
        max_rank = max(rank_groups.keys()) if rank_groups else 0

        self.node_positions = {}
        start_x = 1.5
        start_y = 10.0

        for r, group in sorted(rank_groups.items()):
            effective_rank = (max_rank - r) if direction in ("BT", "RL") else r
            group_count = len(group)

            for idx, nid in enumerate(group):
                if is_horizontal:
                    x1 = start_x + effective_rank * (shape_w + gap_x)
                    x2 = x1 + shape_w
                    total_height = group_count * shape_h + (group_count - 1) * gap_y
                    y_center = start_y - (total_height / 2.0)
                    y1 = y_center + (group_count - 1 - idx) * (shape_h + gap_y)
                    y2 = y1 + shape_h
                else:
                    y2 = start_y - effective_rank * (shape_h + gap_y)
                    y1 = y2 - shape_h
                    total_width = group_count * shape_w + (group_count - 1) * gap_x
                    x_center = start_x + 2.0
                    x1 = (x_center - total_width / 2.0) + idx * (shape_w + gap_x)
                    x2 = x1 + shape_w

                self.node_positions[nid] = (x1, y1, x2, y2)

    def _draw_subgraphs(self, page, visio_app):
        """
        Draws container rectangles for subgraphs around their member nodes.
        """
        for sub in self.diagram.subgraphs:
            self._draw_single_subgraph(page, sub, visio_app)

    def _draw_single_subgraph(self, page, sub: Subgraph, visio_app):
        for child in sub.children:
            self._draw_single_subgraph(page, child, visio_app)

        member_boxes = [self.node_positions[nid] for nid in sub.node_ids if nid in self.node_positions]
        if not member_boxes:
            return

        pad_x = 0.45
        pad_bottom = 0.45
        pad_top = 0.75  # Generous headroom for title badge

        min_x = min(b[0] for b in member_boxes) - pad_x
        min_y = min(b[1] for b in member_boxes) - pad_bottom
        max_x = max(b[2] for b in member_boxes) + pad_x
        max_y = max(b[3] for b in member_boxes) + pad_top

        draw_subgraph_container(
            page=page,
            x1=min_x,
            y1=min_y,
            x2=max_x,
            y2=max_y,
            title=sub.title,
            palette=self.palette,
            font_name=self.font_name,
            visio_app=visio_app
        )

    def _draw_nodes(self, page, visio_app):
        """
        Draws all nodes on the Visio page and applies styling and text.
        """
        for nid, node in self.diagram.nodes.items():
            coords = self.node_positions.get(nid, (1.0, 1.0, 3.4, 1.9))
            x1, y1, x2, y2 = coords

            shape = draw_node_shape(
                page=page,
                shape_type=node.shape,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                palette=self.palette
            )

            format_shape_text(
                shape=shape,
                text=node.label,
                font_name=self.font_name,
                font_size_pt=10,
                font_color_rgb=self.palette.default_text,
                bold=False,
                visio_app=visio_app
            )

            self.visio_shapes[nid] = shape

    def _draw_edges(self, page, visio_app):
        """
        Draws connectors for each edge between source and target shapes.
        """
        for edge in self.diagram.edges:
            shape_from = self.visio_shapes.get(edge.source_id)
            shape_to = self.visio_shapes.get(edge.target_id)
            if shape_from and shape_to:
                connect_shapes(
                    page=page,
                    visio_app=visio_app,
                    shape_from=shape_from,
                    shape_to=shape_to,
                    label=edge.label,
                    style=edge.style,
                    arrow_start=edge.arrow_start,
                    arrow_end=edge.arrow_end,
                    palette=self.palette,
                    font_name=self.font_name
                )
