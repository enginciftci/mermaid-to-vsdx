"""
Topological Graph Layout Engine (Sugiyama Framework).
Calculates collision-free coordinate positions, ranks, and Cartesian coordinate inversions for Visio.
"""

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class LayoutNode:
    id: str
    width: float           # Width in inches
    height: float          # Height in inches
    subgraph_id: Optional[str] = None
    rank: int = 0
    order: int = 0
    # Screen coordinates (origin top-left, inches)
    screen_x: float = 0.0
    screen_y: float = 0.0
    # Visio physical coordinates (origin bottom-left, inches)
    pin_x: float = 0.0
    pin_y: float = 0.0


@dataclass
class LayoutSubgraph:
    id: str
    title: str
    node_ids: List[str] = field(default_factory=list)
    # Screen coordinates
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # Visio physical coordinates
    pin_x: float = 0.0
    pin_y: float = 0.0


@dataclass
class LayoutResult:
    nodes: Dict[str, LayoutNode]
    subgraphs: Dict[str, LayoutSubgraph]
    page_width: float
    page_height: float


class SugiyamaLayoutEngine:
    def __init__(
        self,
        direction: str = "TD",
        rank_gap: float = 1.0,
        node_gap: float = 0.6,
        page_margin: float = 1.0,
    ):
        self.direction = direction.upper() if direction else "TD"
        if self.direction == "TB":
            self.direction = "TD"
        self.rank_gap = rank_gap
        self.node_gap = node_gap
        self.page_margin = page_margin

    def layout(
        self,
        nodes: Dict[str, Tuple[float, float, Optional[str]]],  # id -> (width, height, subgraph_id)
        edges: List[Tuple[str, str]],                          # (source_id, target_id)
        subgraphs: Optional[Dict[str, Tuple[str, List[str]]]] = None  # id -> (title, node_ids)
    ) -> LayoutResult:
        """
        Executes the Sugiyama topological layout pipeline:
        1. Cycle detection & acyclic graph reduction
        2. Layer/Rank assignment (Longest path)
        3. Crossing reduction & vertex ordering
        4. Coordinate assignment in screen space
        5. Subgraph container bounding box synthesis
        6. Cartesian coordinate inversion to Visio physical coordinates
        """
        layout_nodes: Dict[str, LayoutNode] = {}
        for nid, (w, h, sub_id) in nodes.items():
            layout_nodes[nid] = LayoutNode(id=nid, width=w, height=h, subgraph_id=sub_id)

        adj: Dict[str, List[str]] = defaultdict(list)
        rev_adj: Dict[str, List[str]] = defaultdict(list)
        valid_edges = []
        for src, dst in edges:
            if src in layout_nodes and dst in layout_nodes:
                adj[src].append(dst)
                rev_adj[dst].append(src)
                valid_edges.append((src, dst))

        # 1. Cycle removal via DFS
        acyclic_edges = self._remove_cycles(list(layout_nodes.keys()), adj)

        # 2. Rank assignment (Longest Path)
        self._assign_ranks(layout_nodes, acyclic_edges)

        # Group nodes by rank
        ranks: Dict[int, List[str]] = defaultdict(list)
        for nid, node in layout_nodes.items():
            ranks[node.rank].append(nid)

        # 3. Crossing reduction: sort within rank by barycenter and subgraph affinity (multi-pass sweeps)
        self._order_vertices(ranks, layout_nodes, adj, rev_adj)

        # 4. Coordinate assignment in screen space
        is_horizontal = self.direction in ("LR", "RL")
        max_rank = max(ranks.keys()) if ranks else 0

        current_rank_pos = 0.0
        rank_keys = sorted(ranks.keys())
        if self.direction in ("BT", "RL"):
            rank_keys = sorted(ranks.keys(), reverse=True)

        for rk in rank_keys:
            r_nodes = ranks[rk]
            # Calculate maximum thickness of this rank
            if is_horizontal:
                rank_thickness = max(layout_nodes[nid].width for nid in r_nodes) if r_nodes else 1.0
            else:
                rank_thickness = max(layout_nodes[nid].height for nid in r_nodes) if r_nodes else 1.0

            # Calculate total width/length of nodes along cross axis
            total_cross_len = 0.0
            for idx, nid in enumerate(r_nodes):
                dim = layout_nodes[nid].height if is_horizontal else layout_nodes[nid].width
                total_cross_len += dim
                if idx > 0:
                    total_cross_len += self.node_gap

            cross_pos = 0.0
            for nid in r_nodes:
                node = layout_nodes[nid]
                if is_horizontal:
                    node.screen_x = current_rank_pos + rank_thickness / 2.0
                    node.screen_y = cross_pos + node.height / 2.0
                    cross_pos += node.height + self.node_gap
                else:
                    node.screen_x = cross_pos + node.width / 2.0
                    node.screen_y = current_rank_pos + rank_thickness / 2.0
                    cross_pos += node.width + self.node_gap

            current_rank_pos += rank_thickness + self.rank_gap

        # 5. Center alignment across ranks
        # Find maximum cross dimension
        if is_horizontal:
            max_y = max(n.screen_y + n.height / 2.0 for n in layout_nodes.values()) if layout_nodes else 0.0
            for rk, r_nodes in ranks.items():
                if not r_nodes:
                    continue
                min_n_y = min(layout_nodes[n].screen_y - layout_nodes[n].height / 2.0 for n in r_nodes)
                max_n_y = max(layout_nodes[n].screen_y + layout_nodes[n].height / 2.0 for n in r_nodes)
                rank_h = max_n_y - min_n_y
                offset_y = (max_y - rank_h) / 2.0 - min_n_y
                for n in r_nodes:
                    layout_nodes[n].screen_y += offset_y
        else:
            max_x = max(n.screen_x + n.width / 2.0 for n in layout_nodes.values()) if layout_nodes else 0.0
            for rk, r_nodes in ranks.items():
                if not r_nodes:
                    continue
                min_n_x = min(layout_nodes[n].screen_x - layout_nodes[n].width / 2.0 for n in r_nodes)
                max_n_x = max(layout_nodes[n].screen_x + layout_nodes[n].width / 2.0 for n in r_nodes)
                rank_w = max_n_x - min_n_x
                offset_x = (max_x - rank_w) / 2.0 - min_n_x
                for n in r_nodes:
                    layout_nodes[n].screen_x += offset_x

        # 6. Subgraphs bounding box synthesis
        layout_subgraphs: Dict[str, LayoutSubgraph] = {}
        if subgraphs:
            pad = 0.45
            header_h = 0.4
            for sub_id, (sub_title, sub_nids) in subgraphs.items():
                member_nodes = [layout_nodes[n] for n in sub_nids if n in layout_nodes]
                if not member_nodes:
                    continue
                s_min_x = min(n.screen_x - n.width / 2.0 for n in member_nodes) - pad
                s_max_x = max(n.screen_x + n.width / 2.0 for n in member_nodes) + pad
                s_min_y = min(n.screen_y - n.height / 2.0 for n in member_nodes) - pad - header_h
                s_max_y = max(n.screen_y + n.height / 2.0 for n in member_nodes) + pad

                sw = s_max_x - s_min_x
                sh = s_max_y - s_min_y
                layout_subgraphs[sub_id] = LayoutSubgraph(
                    id=sub_id,
                    title=sub_title,
                    node_ids=sub_nids,
                    min_x=s_min_x,
                    max_x=s_max_x,
                    min_y=s_min_y,
                    max_y=s_max_y,
                    width=sw,
                    height=sh,
                )

        # Calculate total diagram bounds
        all_min_x = min(n.screen_x - n.width / 2.0 for n in layout_nodes.values()) if layout_nodes else 0.0
        all_max_x = max(n.screen_x + n.width / 2.0 for n in layout_nodes.values()) if layout_nodes else 8.5
        all_min_y = min(n.screen_y - n.height / 2.0 for n in layout_nodes.values()) if layout_nodes else 0.0
        all_max_y = max(n.screen_y + n.height / 2.0 for n in layout_nodes.values()) if layout_nodes else 11.0

        if layout_subgraphs:
            all_min_x = min(all_min_x, min(s.min_x for s in layout_subgraphs.values()))
            all_max_x = max(all_max_x, max(s.max_x for s in layout_subgraphs.values()))
            all_min_y = min(all_min_y, min(s.min_y for s in layout_subgraphs.values()))
            all_max_y = max(all_max_y, max(s.max_y for s in layout_subgraphs.values()))

        # Normalize screen coordinates to start at 0
        norm_offset_x = -all_min_x
        norm_offset_y = -all_min_y
        for n in layout_nodes.values():
            n.screen_x += norm_offset_x
            n.screen_y += norm_offset_y
        for s in layout_subgraphs.values():
            s.min_x += norm_offset_x
            s.max_x += norm_offset_x
            s.min_y += norm_offset_y
            s.max_y += norm_offset_y

        total_w = all_max_x - all_min_x
        total_h = all_max_y - all_min_y

        page_w = max(8.5, round(total_w + self.page_margin * 2, 2))
        page_h = max(11.0, round(total_h + self.page_margin * 2, 2))

        # 7. Cartesian coordinate inversion:
        # Visio (0,0) is bottom-left, Y points UP
        # PinY = page_h - (screen_y + page_margin)
        for n in layout_nodes.values():
            n.pin_x = round(n.screen_x + self.page_margin, 3)
            n.pin_y = round(page_h - (n.screen_y + self.page_margin), 3)

        for s in layout_subgraphs.values():
            center_x = (s.min_x + s.max_x) / 2.0
            center_y = (s.min_y + s.max_y) / 2.0
            s.pin_x = round(center_x + self.page_margin, 3)
            s.pin_y = round(page_h - (center_y + self.page_margin), 3)

        return LayoutResult(
            nodes=layout_nodes,
            subgraphs=layout_subgraphs,
            page_width=page_w,
            page_height=page_h,
        )

    def _remove_cycles(self, node_ids: List[str], adj: Dict[str, List[str]]) -> List[Tuple[str, str]]:
        """Removes cycles by reversing back-edges found in DFS."""
        visited: Set[str] = set()
        on_stack: Set[str] = set()
        acyclic_edges: List[Tuple[str, str]] = []

        def dfs(u: str):
            visited.add(u)
            on_stack.add(u)
            for v in adj.get(u, []):
                if v not in visited:
                    acyclic_edges.append((u, v))
                    dfs(v)
                elif v in on_stack:
                    # Cycle detected: reverse edge for rank assignment
                    acyclic_edges.append((v, u))
                else:
                    acyclic_edges.append((u, v))
            on_stack.remove(u)

        for n in node_ids:
            if n not in visited:
                dfs(n)
        return acyclic_edges

    def _assign_ranks(self, nodes: Dict[str, LayoutNode], edges: List[Tuple[str, str]]):
        """Assigns ranks using longest path layering."""
        in_degree: Dict[str, int] = {nid: 0 for nid in nodes}
        graph: Dict[str, List[str]] = defaultdict(list)
        for u, v in edges:
            if u in nodes and v in nodes:
                graph[u].append(v)
                in_degree[v] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        if not queue:
            # Graph was disconnected or purely cyclic; fallback
            queue = deque(list(nodes.keys()))

        ranks: Dict[str, int] = {nid: 0 for nid in nodes}
        while queue:
            curr = queue.popleft()
            curr_rank = ranks[curr]
            for nxt in graph[curr]:
                if ranks[nxt] < curr_rank + 1:
                    ranks[nxt] = curr_rank + 1
                    queue.append(nxt)

        for nid, rk in ranks.items():
            nodes[nid].rank = rk

    def _order_vertices(
        self,
        ranks: Dict[int, List[str]],
        nodes: Dict[str, LayoutNode],
        adj: Dict[str, List[str]],
        rev_adj: Dict[str, List[str]],
        max_iterations: int = 4,
    ):
        """
        Orders vertices within ranks using multi-pass alternating barycentric sweeps
        (similar to ELK and Dagre) to minimize edge crossings while preserving
        subgraph clustering.
        """
        if not ranks:
            return

        sorted_ranks = sorted(ranks.keys())
        min_rank = sorted_ranks[0]
        max_rank = sorted_ranks[-1]

        # Initial ordering within ranks
        for rk in sorted_ranks:
            r_nodes = ranks[rk]
            # Initial sort by subgraph affinity
            r_nodes.sort(key=lambda n: (nodes[n].subgraph_id or "", n))
            for idx, nid in enumerate(r_nodes):
                nodes[nid].order = idx

        # Multi-pass alternating barycentric heuristic
        for iteration in range(max_iterations):
            if iteration % 2 == 0:
                # Downward sweep: rank min_rank + 1 to max_rank (use predecessors)
                for rk in range(min_rank + 1, max_rank + 1):
                    if rk not in ranks:
                        continue
                    r_nodes = ranks[rk]

                    def down_key(nid: str):
                        sub_val = nodes[nid].subgraph_id or ""
                        preds = [p for p in rev_adj.get(nid, []) if p in nodes and nodes[p].rank < rk]
                        if preds:
                            bary = sum(nodes[p].order for p in preds) / len(preds)
                        else:
                            bary = float(nodes[nid].order)
                        return (sub_val, bary, nodes[nid].order)

                    sorted_nodes = sorted(r_nodes, key=down_key)
                    for idx, nid in enumerate(sorted_nodes):
                        nodes[nid].order = idx
                    ranks[rk] = sorted_nodes
            else:
                # Upward sweep: rank max_rank - 1 down to min_rank (use successors)
                for rk in range(max_rank - 1, min_rank - 1, -1):
                    if rk not in ranks:
                        continue
                    r_nodes = ranks[rk]

                    def up_key(nid: str):
                        sub_val = nodes[nid].subgraph_id or ""
                        succs = [s for s in adj.get(nid, []) if s in nodes and nodes[s].rank > rk]
                        if succs:
                            bary = sum(nodes[s].order for s in succs) / len(succs)
                        else:
                            bary = float(nodes[nid].order)
                        return (sub_val, bary, nodes[nid].order)

                    sorted_nodes = sorted(r_nodes, key=up_key)
                    for idx, nid in enumerate(sorted_nodes):
                        nodes[nid].order = idx
                    ranks[rk] = sorted_nodes
