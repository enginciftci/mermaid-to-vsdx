"""
Topological Graph Layout Engine (Sugiyama Framework).
Calculates collision-free coordinate positions, ranks, parent-child chain alignment,
corridor-aligned skip-level waypoints, and Cartesian coordinate inversions for Visio.
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
    decl_order: int = 0
    is_dummy: bool = False
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
    edge_routes: Dict[Tuple[str, str], List[Tuple[float, float]]] = field(default_factory=dict)


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
        2. Layer/Rank assignment (Longest path + leaf-subgraph peer unification + source tightening)
        3. Crossing reduction & vertex ordering (preserving declaration order within subgraphs)
        4. Coordinate assignment in screen space with parent-child alignment & corridor waypoints
        5. Subgraph container bounding box synthesis & collision resolution
        6. Cartesian coordinate inversion to Visio physical coordinates
        """
        layout_nodes: Dict[str, LayoutNode] = {}
        for decl_idx, (nid, (w, h, sub_id)) in enumerate(nodes.items()):
            layout_nodes[nid] = LayoutNode(
                id=nid, width=w, height=h, subgraph_id=sub_id, decl_order=decl_idx
            )

        adj: Dict[str, List[str]] = defaultdict(list)
        rev_adj: Dict[str, List[str]] = defaultdict(list)
        valid_edges = []
        for src, dst in edges:
            if src in layout_nodes and dst in layout_nodes and src != dst:
                adj[src].append(dst)
                rev_adj[dst].append(src)
                valid_edges.append((src, dst))

        # 1. Cycle removal via DFS
        acyclic_edges = self._remove_cycles(list(layout_nodes.keys()), adj)

        # 2. Rank assignment (Longest Path + Subgraph Peer Unification + Source Tightening)
        self._assign_ranks(layout_nodes, acyclic_edges, subgraphs)

        # 2b. Insert dummy nodes ONLY for forward skip-level edges (diff > 1).
        # Back-edges (diff < 0) route around the exterior via U-channels and should not
        # pollute intermediate ranks with dummy obstacles.
        dummy_edges: Dict[Tuple[str, str], List[str]] = {}
        augmented_adj: Dict[str, List[str]] = defaultdict(list)
        augmented_rev_adj: Dict[str, List[str]] = defaultdict(list)

        dummy_order_counter = len(layout_nodes)
        for src, dst in valid_edges:
            src_node = layout_nodes[src]
            dst_node = layout_nodes[dst]
            diff = dst_node.rank - src_node.rank
            if diff > 1:
                dummies = []
                prev = src
                for r in range(src_node.rank + 1, dst_node.rank):
                    d_id = f"__dummy_{src}_{dst}_{r}__"
                    if d_id not in layout_nodes:
                        d_node = LayoutNode(
                            id=d_id,
                            width=0.2,
                            height=0.2,
                            subgraph_id=src_node.subgraph_id if src_node.subgraph_id == dst_node.subgraph_id else None,
                            rank=r,
                            decl_order=dummy_order_counter,
                            is_dummy=True,
                        )
                        dummy_order_counter += 1
                        layout_nodes[d_id] = d_node
                    dummies.append(d_id)
                    augmented_adj[prev].append(d_id)
                    augmented_rev_adj[d_id].append(prev)
                    prev = d_id
                augmented_adj[prev].append(dst)
                augmented_rev_adj[dst].append(prev)
                dummy_edges[(src, dst)] = dummies
            elif diff == 1:
                augmented_adj[src].append(dst)
                augmented_rev_adj[dst].append(src)

        # Group nodes by rank (including dummy nodes)
        ranks: Dict[int, List[str]] = defaultdict(list)
        for nid, node in layout_nodes.items():
            ranks[node.rank].append(nid)

        # 3. Crossing reduction: sort within rank by barycenter and subgraph affinity
        self._order_vertices(ranks, layout_nodes, augmented_adj, augmented_rev_adj)

        # 4. Coordinate assignment in screen space
        is_horizontal = self.direction in ("LR", "RL")
        rank_keys = sorted(ranks.keys())
        if self.direction in ("BT", "RL"):
            rank_keys = sorted(ranks.keys(), reverse=True)

        current_rank_pos = 0.0
        for idx_rk, rk in enumerate(rank_keys):
            r_nodes = ranks[rk]
            real_r_nodes = [nid for nid in r_nodes if not layout_nodes[nid].is_dummy]
            ref_nodes = real_r_nodes if real_r_nodes else r_nodes

            # Calculate maximum thickness of this rank
            if is_horizontal:
                rank_thickness = max(layout_nodes[nid].width for nid in ref_nodes) if ref_nodes else 1.0
            else:
                rank_thickness = max(layout_nodes[nid].height for nid in ref_nodes) if ref_nodes else 1.0

            cross_pos = 0.0
            for idx_n, nid in enumerate(r_nodes):
                node = layout_nodes[nid]
                eff_node_gap = self.node_gap
                if idx_n + 1 < len(r_nodes):
                    nxt_n = layout_nodes[r_nodes[idx_n + 1]]
                    if node.subgraph_id != nxt_n.subgraph_id and (node.subgraph_id or nxt_n.subgraph_id):
                        eff_node_gap = max(self.node_gap, 1.5)

                if is_horizontal:
                    node.screen_x = current_rank_pos + rank_thickness / 2.0
                    node.screen_y = cross_pos + node.height / 2.0
                    cross_pos += node.height + eff_node_gap
                else:
                    node.screen_x = cross_pos + node.width / 2.0
                    node.screen_y = current_rank_pos + rank_thickness / 2.0
                    cross_pos += node.width + eff_node_gap

            eff_gap = self.rank_gap
            if idx_rk + 1 < len(rank_keys):
                nxt_rk = rank_keys[idx_rk + 1]
                nxt_nodes = ranks[nxt_rk]
                curr_subs = {layout_nodes[n].subgraph_id for n in r_nodes if not layout_nodes[n].is_dummy and layout_nodes[n].subgraph_id}
                nxt_subs = {layout_nodes[n].subgraph_id for n in nxt_nodes if not layout_nodes[n].is_dummy and layout_nodes[n].subgraph_id}
                if curr_subs != nxt_subs and (curr_subs or nxt_subs):
                    eff_gap = max(self.rank_gap, 1.6)

            current_rank_pos += rank_thickness + eff_gap

        # 5. Center alignment across ranks (based on real nodes so dummy nodes don't skew centering)
        real_all = [n for n in layout_nodes.values() if not n.is_dummy]
        if is_horizontal:
            max_y = max(n.screen_y + n.height / 2.0 for n in real_all) if real_all else 0.0
            for rk, r_nodes in ranks.items():
                real_in_rk = [n for n in r_nodes if not layout_nodes[n].is_dummy]
                ref = real_in_rk if real_in_rk else r_nodes
                if not ref:
                    continue
                min_n_y = min(layout_nodes[n].screen_y - layout_nodes[n].height / 2.0 for n in ref)
                max_n_y = max(layout_nodes[n].screen_y + layout_nodes[n].height / 2.0 for n in ref)
                rank_h = max_n_y - min_n_y
                offset_y = (max_y - rank_h) / 2.0 - min_n_y
                for n in r_nodes:
                    layout_nodes[n].screen_y += offset_y
        else:
            max_x = max(n.screen_x + n.width / 2.0 for n in real_all) if real_all else 0.0
            for rk, r_nodes in ranks.items():
                real_in_rk = [n for n in r_nodes if not layout_nodes[n].is_dummy]
                ref = real_in_rk if real_in_rk else r_nodes
                if not ref:
                    continue
                min_n_x = min(layout_nodes[n].screen_x - layout_nodes[n].width / 2.0 for n in ref)
                max_n_x = max(layout_nodes[n].screen_x + layout_nodes[n].width / 2.0 for n in ref)
                rank_w = max_n_x - min_n_x
                offset_x = (max_x - rank_w) / 2.0 - min_n_x
                for n in r_nodes:
                    layout_nodes[n].screen_x += offset_x

        # 5b. Parent-child chain alignment relaxation (eliminates unnecessary dog-leg Z-bends)
        self._align_parent_child_chains(rank_keys, ranks, layout_nodes, adj, rev_adj, is_horizontal)

        # 5c. Straighten skip-level dummy corridors so multi-rank waypoints form a straight vertical/horizontal line
        self._align_dummy_corridors(dummy_edges, ranks, layout_nodes, is_horizontal)

        # 6. Subgraphs bounding box synthesis with cross-axis collision resolution
        layout_subgraphs: Dict[str, LayoutSubgraph] = {}
        if subgraphs:
            def _calc_sub_bounds(sub_id: str, sub_title: str, sub_nids: List[str]) -> Optional[LayoutSubgraph]:
                member_nodes = [layout_nodes[n] for n in sub_nids if n in layout_nodes and not layout_nodes[n].is_dummy]
                if not member_nodes:
                    return None
                is_parent = any(layout_nodes[n].subgraph_id != sub_id for n in sub_nids if n in layout_nodes)
                pad = 0.85 if is_parent else 0.45
                header_h = 0.55 if is_parent else 0.45
                s_min_x = min(n.screen_x - n.width / 2.0 for n in member_nodes) - pad
                s_max_x = max(n.screen_x + n.width / 2.0 for n in member_nodes) + pad
                s_min_y = min(n.screen_y - n.height / 2.0 for n in member_nodes) - pad - header_h
                s_max_y = max(n.screen_y + n.height / 2.0 for n in member_nodes) + pad
                return LayoutSubgraph(
                    id=sub_id,
                    title=sub_title,
                    node_ids=[n for n in sub_nids if n in layout_nodes and not layout_nodes[n].is_dummy],
                    min_x=s_min_x,
                    max_x=s_max_x,
                    min_y=s_min_y,
                    max_y=s_max_y,
                    width=s_max_x - s_min_x,
                    height=s_max_y - s_min_y,
                )

            for sub_id, (sub_title, sub_nids) in subgraphs.items():
                ls = _calc_sub_bounds(sub_id, sub_title, sub_nids)
                if ls:
                    layout_subgraphs[sub_id] = ls

            # Identify leaf subgraphs
            leaf_sub_ids = [
                sub_id for sub_id, (sub_title, sub_nids) in subgraphs.items()
                if not any(layout_nodes[n].subgraph_id != sub_id for n in sub_nids if n in layout_nodes)
            ]

            # Cross-axis collision resolution between sibling leaf subgraphs
            if is_horizontal:
                leaf_sub_ids.sort(key=lambda sid: layout_subgraphs[sid].min_y if sid in layout_subgraphs else 0)
            else:
                leaf_sub_ids.sort(key=lambda sid: layout_subgraphs[sid].min_x if sid in layout_subgraphs else 0)

            shifted_any = False
            for i in range(len(leaf_sub_ids)):
                for j in range(i + 1, len(leaf_sub_ids)):
                    sid_a = leaf_sub_ids[i]
                    sid_b = leaf_sub_ids[j]
                    if sid_a not in layout_subgraphs or sid_b not in layout_subgraphs:
                        continue
                    sub_a = layout_subgraphs[sid_a]
                    sub_b = layout_subgraphs[sid_b]

                    if is_horizontal:
                        overlap_x = not (sub_a.max_x < sub_b.min_x or sub_b.max_x < sub_a.min_x)
                        if overlap_x:
                            overlap_y = (sub_a.max_y + 0.45) - sub_b.min_y
                            if overlap_y > 0:
                                for nid in subgraphs[sid_b][1]:
                                    if nid in layout_nodes:
                                        layout_nodes[nid].screen_y += overlap_y
                                sub_b.min_y += overlap_y
                                sub_b.max_y += overlap_y
                                shifted_any = True
                    else:
                        overlap_y = not (sub_a.max_y < sub_b.min_y or sub_b.max_y < sub_a.min_y)
                        if overlap_y:
                            overlap_x = (sub_a.max_x + 0.45) - sub_b.min_x
                            if overlap_x > 0:
                                for nid in subgraphs[sid_b][1]:
                                    if nid in layout_nodes:
                                        layout_nodes[nid].screen_x += overlap_x
                                sub_b.min_x += overlap_x
                                sub_b.max_x += overlap_x
                                shifted_any = True

            if shifted_any:
                for sub_id, (sub_title, sub_nids) in subgraphs.items():
                    ls = _calc_sub_bounds(sub_id, sub_title, sub_nids)
                    if ls:
                        layout_subgraphs[sub_id] = ls

            # Clear cross-subgraph corridors: if a leaf subgraph sits directly across the straight
            # corridor between two other subgraphs connected by an edge, shift it above the corridor
            corridor_shifted = False
            for obs_sid in leaf_sub_ids:
                if obs_sid not in layout_subgraphs:
                    continue
                obs_sub = layout_subgraphs[obs_sid]
                for u_id, v_id in valid_edges:
                    u_sub_id = layout_nodes[u_id].subgraph_id
                    v_sub_id = layout_nodes[v_id].subgraph_id
                    if not u_sub_id or not v_sub_id or u_sub_id == v_sub_id:
                        continue
                    if obs_sid in (u_sub_id, v_sub_id):
                        continue
                    if u_sub_id not in layout_subgraphs or v_sub_id not in layout_subgraphs:
                        continue
                    u_sub = layout_subgraphs[u_sub_id]
                    v_sub = layout_subgraphs[v_sub_id]
                    if is_horizontal:
                        if u_sub.max_x <= obs_sub.min_x + 0.5 and obs_sub.max_x - 0.5 <= v_sub.min_x:
                            u_cy = (u_sub.min_y + u_sub.max_y) * 0.5
                            v_cy = (v_sub.min_y + v_sub.max_y) * 0.5
                            corridor_y = (u_cy + v_cy) * 0.5
                            if obs_sub.min_y - 0.35 <= corridor_y <= obs_sub.max_y + 0.35:
                                delta_y = (corridor_y - 0.65) - obs_sub.max_y
                                for nid in subgraphs[obs_sid][1]:
                                    if nid in layout_nodes:
                                        layout_nodes[nid].screen_y += delta_y
                                obs_sub.min_y += delta_y
                                obs_sub.max_y += delta_y
                                # Also lift dummy waypoints for edges originating inside obs_sid above obs_sub
                                for idx_e, ((esrc, edst), d_list) in enumerate(dummy_edges.items()):
                                    if layout_nodes[esrc].subgraph_id == obs_sid and d_list:
                                        lane_y = obs_sub.min_y - 0.35 - 0.38 * (idx_e % 3)
                                        for d_id in d_list:
                                            layout_nodes[d_id].screen_y = lane_y
                                corridor_shifted = True
                                break

            if corridor_shifted:
                for sub_id, (sub_title, sub_nids) in subgraphs.items():
                    ls = _calc_sub_bounds(sub_id, sub_title, sub_nids)
                    if ls:
                        layout_subgraphs[sub_id] = ls

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

        # Adapt page orientation: landscape for LR/RL or wide diagrams
        if is_horizontal or total_w > total_h:
            min_page_w, min_page_h = 11.0, 8.5
        else:
            min_page_w, min_page_h = 8.5, 11.0

        page_w = max(min_page_w, round(total_w + self.page_margin * 2, 2))
        page_h = max(min_page_h, round(total_h + self.page_margin * 2, 2))

        # Center diagram content within page margins
        extra_x = max(0.0, round((page_w - (total_w + self.page_margin * 2)) / 2.0, 3))
        extra_y = max(0.0, round((page_h - (total_h + self.page_margin * 2)) / 2.0, 3))

        # 7. Cartesian coordinate inversion:
        # Visio (0,0) is bottom-left, Y points UP
        for n in layout_nodes.values():
            n.pin_x = round(n.screen_x + self.page_margin + extra_x, 3)
            n.pin_y = round(page_h - (n.screen_y + self.page_margin + extra_y), 3)

        for s in layout_subgraphs.values():
            center_x = (s.min_x + s.max_x) / 2.0
            center_y = (s.min_y + s.max_y) / 2.0
            s.pin_x = round(center_x + self.page_margin + extra_x, 3)
            s.pin_y = round(page_h - (center_y + self.page_margin + extra_y), 3)

        # Collect edge routes for dummy waypoints
        edge_routes: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}
        for (src, dst), dummies in dummy_edges.items():
            if dummies:
                edge_routes[(src, dst)] = [(layout_nodes[d].pin_x, layout_nodes[d].pin_y) for d in dummies]

        real_nodes = {nid: n for nid, n in layout_nodes.items() if not n.is_dummy}

        return LayoutResult(
            nodes=real_nodes,
            subgraphs=layout_subgraphs,
            page_width=page_w,
            page_height=page_h,
            edge_routes=edge_routes,
        )

    def _align_parent_child_chains(
        self,
        rank_keys: List[int],
        ranks: Dict[int, List[str]],
        nodes: Dict[str, LayoutNode],
        adj: Dict[str, List[str]],
        rev_adj: Dict[str, List[str]],
        is_horizontal: bool,
    ):
        """
        Aligns child nodes directly beneath/beside their parent when each node in a rank
        has a single parent in the preceding rank and doing so preserves minimum node spacing.
        Eliminates unnecessary dog-leg Z-bends on parallel or sequential chains.
        """
        for idx_rk in range(1, len(rank_keys)):
            rk = rank_keys[idx_rk]
            prev_rk = rank_keys[idx_rk - 1]
            real_r_nodes = [n for n in ranks[rk] if not nodes[n].is_dummy]
            if not real_r_nodes:
                continue

            real_prev_nodes = [n for n in ranks[prev_rk] if not nodes[n].is_dummy]
            # If sole parent in prev_rk branches into 2 nodes in rk, ensure the second branch clears parent's right/bottom tip
            if len(real_prev_nodes) == 1 and len(real_r_nodes) == 2:
                p_node = nodes[real_prev_nodes[0]]
                c0, c1 = nodes[real_r_nodes[0]], nodes[real_r_nodes[1]]
                if not is_horizontal:
                    min_c1_x = p_node.screen_x + p_node.width * 0.5 + 0.45
                    if c1.screen_x < min_c1_x:
                        c1.screen_x = min_c1_x
                else:
                    min_c1_y = p_node.screen_y + p_node.height * 0.5 + 0.45
                    if c1.screen_y < min_c1_y:
                        c1.screen_y = min_c1_y

            # Case 1: Multiple nodes in rank where each node has a clear parent column
            desired_coords = {}
            exclusive_parent = {}
            all_have_target_coord = True
            for nid in real_r_nodes:
                preds = [p for p in rev_adj.get(nid, []) if p in nodes and not nodes[p].is_dummy and nodes[p].rank == prev_rk]
                all_preds = [p for p in rev_adj.get(nid, []) if p in nodes and not nodes[p].is_dummy and nodes[p].rank < rk]
                if len(preds) == 1 and len(all_preds) == 1:
                    p_node = nodes[preds[0]]
                    desired_coords[nid] = p_node.screen_y if is_horizontal else p_node.screen_x
                elif all_preds:
                    p_coords = [nodes[p].screen_y if is_horizontal else nodes[p].screen_x for p in all_preds]
                    if max(p_coords) - min(p_coords) < 0.05:
                        desired_coords[nid] = p_coords[0]
                    else:
                        excl = [
                            p for p in all_preds
                            if [s for s in adj.get(p, []) if s in nodes and not nodes[s].is_dummy] == [nid]
                        ]
                        if len(excl) == 1:
                            ep = nodes[excl[0]]
                            desired_coords[nid] = ep.screen_y if is_horizontal else ep.screen_x
                            exclusive_parent[nid] = excl[0]
                        else:
                            all_have_target_coord = False
                else:
                    all_have_target_coord = False

            if len(real_r_nodes) >= 2 and all_have_target_coord:
                # Verify that desired coordinates are strictly ordered and non-overlapping
                valid_alignment = True
                for i in range(len(real_r_nodes) - 1):
                    n_a = nodes[real_r_nodes[i]]
                    n_b = nodes[real_r_nodes[i + 1]]
                    dim_a = n_a.height if is_horizontal else n_a.width
                    dim_b = n_b.height if is_horizontal else n_b.width
                    min_sep = (dim_a + dim_b) * 0.5 + self.node_gap * 0.85
                    if desired_coords[n_b.id] - desired_coords[n_a.id] < min_sep:
                        if n_b.id in exclusive_parent:
                            new_c = desired_coords[n_a.id] + min_sep
                            desired_coords[n_b.id] = new_c
                            ep_id = exclusive_parent[n_b.id]
                            if is_horizontal:
                                nodes[ep_id].screen_y = new_c
                            else:
                                nodes[ep_id].screen_x = new_c
                        else:
                            valid_alignment = False
                            break
                if valid_alignment:
                    for nid in real_r_nodes:
                        if is_horizontal:
                            nodes[nid].screen_y = desired_coords[nid]
                        else:
                            nodes[nid].screen_x = desired_coords[nid]
            elif len(real_r_nodes) == 1:
                nid = real_r_nodes[0]
                preds = [p for p in rev_adj.get(nid, []) if p in nodes and not nodes[p].is_dummy and nodes[p].rank == prev_rk]
                # If sole real node in rank has 1 parent in preceding rank, align directly with parent
                if len(preds) == 1:
                    p_node = nodes[preds[0]]
                    if is_horizontal:
                        nodes[nid].screen_y = p_node.screen_y
                    else:
                        nodes[nid].screen_x = p_node.screen_x

    def _align_dummy_corridors(
        self,
        dummy_edges: Dict[Tuple[str, str], List[str]],
        ranks: Dict[int, List[str]],
        nodes: Dict[str, LayoutNode],
        is_horizontal: bool,
    ):
        """
        Ensures all dummy waypoints belonging to a single skip-level edge (src, dst)
        share a single straight corridor coordinate (screen_x in vertical mode, screen_y in horizontal mode)
        that avoids colliding with any real node in intermediate ranks.
        """
        for (src, dst), dummies in dummy_edges.items():
            if not dummies:
                continue
            src_node = nodes[src]
            dst_node = nodes[dst]
            inter_ranks = [nodes[d].rank for d in dummies]

            # Collect obstacle intervals [low, high] of real nodes in intermediate ranks
            obstacles: List[Tuple[float, float]] = []
            for r in inter_ranks:
                for nid in ranks.get(r, []):
                    if not nodes[nid].is_dummy:
                        rn = nodes[nid]
                        if is_horizontal:
                            obstacles.append((rn.screen_y - rn.height * 0.5 - 0.35, rn.screen_y + rn.height * 0.5 + 0.35))
                        else:
                            obstacles.append((rn.screen_x - rn.width * 0.5 - 0.35, rn.screen_x + rn.width * 0.5 + 0.35))

            def _is_clear(coord: float) -> bool:
                return all(coord < low or coord > high for low, high in obstacles)

            src_c = src_node.screen_y if is_horizontal else src_node.screen_x
            dst_c = dst_node.screen_y if is_horizontal else dst_node.screen_x
            mean_d = sum((nodes[d].screen_y if is_horizontal else nodes[d].screen_x) for d in dummies) / len(dummies)

            if _is_clear(src_c):
                corridor = src_c
            elif _is_clear(dst_c):
                corridor = dst_c
            elif _is_clear(mean_d):
                corridor = mean_d
            elif obstacles:
                # Include source node bounds when bypassing so side-port exits step outward, never inward
                bypass_obs = list(obstacles)
                if is_horizontal:
                    bypass_obs.append((src_node.screen_y - src_node.height * 0.5 - 0.35, src_node.screen_y + src_node.height * 0.5 + 0.35))
                else:
                    bypass_obs.append((src_node.screen_x - src_node.width * 0.5 - 0.35, src_node.screen_x + src_node.width * 0.5 + 0.35))
                min_obs = min(low for low, _ in bypass_obs)
                max_obs = max(high for _, high in bypass_obs)
                corridor = min_obs - 0.25 if abs(src_c - min_obs) <= abs(src_c - max_obs) else max_obs + 0.25
            else:
                corridor = src_c

            for d in dummies:
                if is_horizontal:
                    nodes[d].screen_y = corridor
                else:
                    nodes[d].screen_x = corridor

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
                    # Cycle detected: ignore back-edge for rank assignment so forward hierarchy stays intact
                    continue
                else:
                    acyclic_edges.append((u, v))
            on_stack.remove(u)

        for n in node_ids:
            if n not in visited:
                dfs(n)
        return acyclic_edges

    def _assign_ranks(
        self,
        nodes: Dict[str, LayoutNode],
        edges: List[Tuple[str, str]],
        subgraphs: Optional[Dict[str, Tuple[str, List[str]]]] = None,
    ):
        """
        Assigns ranks using longest path layering, unifies peer nodes in leaf subgraphs
        that have no internal edges between each other, and pulls floating source nodes
        closer to their immediate consumers.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in nodes}
        graph: Dict[str, List[str]] = defaultdict(list)
        rev_graph: Dict[str, List[str]] = defaultdict(list)
        for u, v in edges:
            if u in nodes and v in nodes and u != v:
                graph[u].append(v)
                rev_graph[v].append(u)
                in_degree[v] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        if not queue:
            queue = deque(list(nodes.keys()))

        ranks: Dict[str, int] = {nid: 0 for nid in nodes}
        while queue:
            curr = queue.popleft()
            curr_rank = ranks[curr]
            for nxt in graph[curr]:
                if ranks[nxt] < curr_rank + 1:
                    ranks[nxt] = curr_rank + 1
                    queue.append(nxt)

        # Unify ranks for leaf subgraphs whose member nodes have no internal edges between each other
        if subgraphs:
            for sub_id, (sub_title, sub_nids) in subgraphs.items():
                member_ids = [n for n in sub_nids if n in nodes and nodes[n].subgraph_id == sub_id]
                if len(member_ids) <= 1:
                    continue
                member_set = set(member_ids)
                has_internal_edge = any(
                    v in member_set for u in member_ids for v in graph.get(u, [])
                )
                if not has_internal_edge:
                    target_rk = max(ranks[m] for m in member_ids)
                    for m in member_ids:
                        if ranks[m] < target_rk:
                            ranks[m] = target_rk
                    # Propagate updated ranks downstream
                    prop_q = deque(member_ids)
                    while prop_q:
                        curr = prop_q.popleft()
                        for nxt in graph[curr]:
                            if ranks[nxt] < ranks[curr] + 1:
                                ranks[nxt] = ranks[curr] + 1
                                prop_q.append(nxt)

        # Pull root nodes (in_degree == 0) down to min(child.rank) - 1 so they don't float at rank 0
        for nid, deg in in_degree.items():
            if deg == 0 and graph.get(nid):
                min_child_rk = min(ranks[c] for c in graph[nid])
                if min_child_rk > ranks[nid] + 1:
                    ranks[nid] = min_child_rk - 1

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
        to minimize edge crossings while preserving subgraph clustering and declaration order.
        """
        if not ranks:
            return

        sorted_ranks = sorted(ranks.keys())
        min_rank = sorted_ranks[0]
        max_rank = sorted_ranks[-1]

        # Initial ordering within ranks: group by subgraph_id and preserve declaration order
        for rk in sorted_ranks:
            r_nodes = ranks[rk]
            r_nodes.sort(key=lambda n: (nodes[n].subgraph_id or "", nodes[n].decl_order))
            for idx, nid in enumerate(r_nodes):
                nodes[nid].order = idx

        # Multi-pass alternating barycentric heuristic
        for iteration in range(max_iterations):
            if iteration % 2 == 0:
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
                        return (sub_val, bary, nodes[nid].decl_order)

                    sorted_nodes = sorted(r_nodes, key=down_key)
                    for idx, nid in enumerate(sorted_nodes):
                        nodes[nid].order = idx
                    ranks[rk] = sorted_nodes
            else:
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
                        return (sub_val, bary, nodes[nid].decl_order)

                    sorted_nodes = sorted(r_nodes, key=up_key)
                    for idx, nid in enumerate(sorted_nodes):
                        nodes[nid].order = idx
                    ranks[rk] = sorted_nodes
