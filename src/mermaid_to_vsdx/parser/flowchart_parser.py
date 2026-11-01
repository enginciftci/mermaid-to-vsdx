"""
Mermaid Flowchart Parser.
Parses Flowchart and Graph Mermaid diagrams into AST FlowchartDiagram models.
"""

from collections import defaultdict
import re
from typing import Dict, List, Optional, Tuple
from .ast_nodes import (
    FlowchartDiagram, Node, Edge, Subgraph, ShapeType, EdgeStyle, ArrowType
)
from .base_parser import MermaidParseError, preprocess_lines
from ..utils.unicode_helper import clean_label_text, ensure_utf8, has_bold_markup


# Shape delimiter pairs ordered from most specific to least specific
SHAPE_DELIMITERS = [
    ("(((", ")))", ShapeType.DOUBLE_CIRCLE),
    ("[[", "]]", ShapeType.SUBROUTINE),
    ("[(", ")]", ShapeType.CYLINDER),
    ("((", "))", ShapeType.CIRCLE),
    ("{{", "}}", ShapeType.HEXAGON),
    ("([", "])", ShapeType.STADIUM),
    ("[/", "/]", ShapeType.PARALLELOGRAM),
    ("[\\", "\\]", ShapeType.PARALLELOGRAM_ALT),
    ("[/", "\\]", ShapeType.TRAPEZOID),
    ("[\\", "/]", ShapeType.TRAPEZOID_ALT),
    ("[", "]", ShapeType.RECTANGLE),
    ("(", ")", ShapeType.ROUNDED),
    (">", "]", ShapeType.ASYMMETRIC),
    ("{", "}", ShapeType.DIAMOND),
]

EXPANDED_SHAPE_MAP = {
    "rect": ShapeType.RECTANGLE,
    "proc": ShapeType.RECTANGLE,
    "process": ShapeType.RECTANGLE,
    "rectangle": ShapeType.RECTANGLE,
    "rounded": ShapeType.ROUNDED,
    "event": ShapeType.ROUNDED,
    "stadium": ShapeType.STADIUM,
    "pill": ShapeType.STADIUM,
    "terminal": ShapeType.STADIUM,
    "subproc": ShapeType.SUBROUTINE,
    "subroutine": ShapeType.SUBROUTINE,
    "fr-rect": ShapeType.SUBROUTINE,
    "framed-rectangle": ShapeType.SUBROUTINE,
    "cyl": ShapeType.CYLINDER,
    "db": ShapeType.CYLINDER,
    "database": ShapeType.CYLINDER,
    "cylinder": ShapeType.CYLINDER,
    "circle": ShapeType.CIRCLE,
    "circ": ShapeType.CIRCLE,
    "dbl-circ": ShapeType.DOUBLE_CIRCLE,
    "double-circle": ShapeType.DOUBLE_CIRCLE,
    "sm-circ": ShapeType.DOUBLE_CIRCLE,
    "framed-circle": ShapeType.DOUBLE_CIRCLE,
    "f-circ": ShapeType.DOUBLE_CIRCLE,
    "diam": ShapeType.DIAMOND,
    "diamond": ShapeType.DIAMOND,
    "decision": ShapeType.DIAMOND,
    "hex": ShapeType.HEXAGON,
    "hexagon": ShapeType.HEXAGON,
    "prepare": ShapeType.HEXAGON,
    "lean-r": ShapeType.PARALLELOGRAM,
    "in-out": ShapeType.PARALLELOGRAM,
    "parallelogram": ShapeType.PARALLELOGRAM,
    "lean-l": ShapeType.PARALLELOGRAM_ALT,
    "out-in": ShapeType.PARALLELOGRAM_ALT,
    "parallelogram-alt": ShapeType.PARALLELOGRAM_ALT,
    "trap-b": ShapeType.TRAPEZOID,
    "priority": ShapeType.TRAPEZOID,
    "trapezoid": ShapeType.TRAPEZOID,
    "trap-t": ShapeType.TRAPEZOID_ALT,
    "manual": ShapeType.TRAPEZOID_ALT,
    "trapezoid-alt": ShapeType.TRAPEZOID_ALT,
    "odd": ShapeType.ASYMMETRIC,
    "flag": ShapeType.ASYMMETRIC,
    "asymmetric": ShapeType.ASYMMETRIC,
}


def _parse_style_props(style_str: str) -> Dict[str, str]:
    """Parses comma-separated CSS-like Mermaid style properties into a dict."""
    style_str = style_str.strip().rstrip(";").strip()
    props: Dict[str, str] = {}
    for item in re.split(r",\s*(?=[A-Za-z_\-]+\s*:)", style_str):
        if ":" in item:
            k, v = item.split(":", 1)
            props[k.strip()] = v.strip().rstrip(";").strip()
    return props


def _parse_endpoint_marker(marker: Optional[str]) -> ArrowType:
    """Maps a connector endpoint string ('<', '>', 'o', 'x', '>o', '>x') to ArrowType."""
    if not marker:
        return ArrowType.NONE
    if "o" in marker:
        return ArrowType.CIRCLE
    if "x" in marker:
        return ArrowType.CROSS
    if ">" in marker or "<" in marker:
        return ArrowType.ARROW
    return ArrowType.NONE


def _mask_protected_regions(line: str) -> str:
    """
    Replaces characters inside quotes ("...", '...') and node brackets ([...], (...), {...}, >...])
    with '_' so connector regexes only match top-level connectors while preserving character offsets.
    """
    chars = list(line)
    n = len(chars)
    in_quote = False
    quote_char = ""
    bracket_depth = 0

    for i in range(n):
        ch = chars[i]
        if in_quote:
            if ch == quote_char and (i == 0 or line[i - 1] != "\\"):
                in_quote = False
            else:
                chars[i] = "_"
        else:
            if ch in ('"', "'"):
                in_quote = True
                quote_char = ch
                if bracket_depth > 0:
                    chars[i] = "_"
            elif ch in ("[", "(", "{"):
                if bracket_depth > 0:
                    chars[i] = "_"
                bracket_depth += 1
            elif ch in ("]", ")", "}"):
                if bracket_depth > 0:
                    bracket_depth -= 1
                    if bracket_depth > 0:
                        chars[i] = "_"
            elif ch == ">" and bracket_depth == 0:
                if i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
                    j = i - 1
                    while j >= 0 and (line[j].isalnum() or line[j] in ("_", "-")):
                        j -= 1
                    if j < 0 or line[j] != "<":
                        rest = line[i + 1:]
                        idx_close = rest.find("]")
                        idx_open = rest.find("[")
                        if idx_close != -1 and (idx_open == -1 or idx_close < idx_open):
                            bracket_depth += 1
            else:
                if bracket_depth > 0:
                    chars[i] = "_"
    return "".join(chars)


class FlowchartParser:
    """
    Parses Mermaid flowchart code into a FlowchartDiagram AST.
    """

    def __init__(self):
        self.diagram = FlowchartDiagram()
        self.subgraph_stack: List[Subgraph] = []
        self._pending_classes: Dict[str, List[str]] = defaultdict(list)
        self._pending_styles: Dict[str, Dict[str, str]] = defaultdict(dict)

    def parse(self, code: str) -> FlowchartDiagram:
        self.diagram = FlowchartDiagram()
        self.subgraph_stack = []
        self._pending_classes = defaultdict(list)
        self._pending_styles = defaultdict(dict)

        raw_lines = preprocess_lines(code)
        if not raw_lines:
            raise MermaidParseError("Empty Mermaid diagram source code.")

        header_idx, header_line = raw_lines[0]
        self._parse_header(header_line, header_idx)

        for line_num, line in raw_lines[1:]:
            self._parse_line(line, line_num)

        self._apply_pending_styles_and_classes()
        return self.diagram

    def _find_subgraph(self, sub_id: str, subgraphs: Optional[List[Subgraph]] = None) -> Optional[Subgraph]:
        if subgraphs is None:
            subgraphs = self.diagram.subgraphs
        for s in subgraphs:
            if s.id == sub_id:
                return s
            found = self._find_subgraph(sub_id, s.children)
            if found:
                return found
        for s in self.subgraph_stack:
            if s.id == sub_id:
                return s
        return None

    def _apply_pending_styles_and_classes(self):
        for nid, cls_list in self._pending_classes.items():
            if nid in self.diagram.nodes:
                for c in cls_list:
                    if c not in self.diagram.nodes[nid].classes:
                        self.diagram.nodes[nid].classes.append(c)

        for tid, props in self._pending_styles.items():
            if tid in self.diagram.nodes:
                self.diagram.nodes[tid].style.update(props)
            else:
                sub = self._find_subgraph(tid)
                if sub:
                    sub.style.update(props)

        for idx, edge in enumerate(self.diagram.edges):
            if -1 in self.diagram.link_styles:
                for k, v in self.diagram.link_styles[-1].items():
                    edge.link_style.setdefault(k, v)
            if idx in self.diagram.link_styles:
                edge.link_style.update(self.diagram.link_styles[idx])

    def _parse_header(self, line: str, line_num: int):
        # Match 'graph TD' or 'flowchart LR'
        m = re.match(r"^(graph|flowchart)\s+([A-Za-z]{2})", line, re.IGNORECASE)
        if m:
            self.diagram.direction = m.group(2).upper()
        else:
            # Fallback if direction wasn't specified
            m_simple = re.match(r"^(graph|flowchart)", line, re.IGNORECASE)
            if m_simple:
                self.diagram.direction = "TD"
            else:
                raise MermaidParseError(
                    f"Invalid flowchart header '{line}'. Expected 'graph TD' or 'flowchart LR'.",
                    line_num, line
                )

    def _parse_line(self, line: str, line_num: int):
        line = line.strip()

        # Handle Subgraph start
        if line.lower().startswith("subgraph"):
            self._handle_subgraph_start(line, line_num)
            return

        # Handle Subgraph end
        if line.lower() == "end":
            self._handle_subgraph_end(line_num, line)
            return

        # Handle direction directive inside subgraph or diagram
        if re.match(r"^direction\s+(TB|TD|LR|RL|BT)\b", line, re.IGNORECASE):
            m_dir = re.match(r"^direction\s+([A-Za-z]{2})", line, re.IGNORECASE)
            if m_dir:
                dir_val = m_dir.group(1).upper()
                if dir_val == "TB":
                    dir_val = "TD"
                if self.subgraph_stack:
                    self.subgraph_stack[-1].direction = dir_val
                else:
                    self.diagram.direction = dir_val
            return

        # Styling directives
        if re.match(r"^classDef\b", line, re.IGNORECASE):
            self._parse_class_def(line)
            return

        if re.match(r"^class\b", line, re.IGNORECASE):
            self._parse_class_assign(line)
            return

        if re.match(r"^style\b", line, re.IGNORECASE):
            self._parse_style_directive(line)
            return

        if re.match(r"^linkStyle\b", line, re.IGNORECASE):
            self._parse_link_style(line)
            return

        if re.match(r"^click\b", line, re.IGNORECASE):
            return

        # Process node or edge line
        self._parse_statement(line, line_num)

    def _parse_class_def(self, line: str):
        m = re.match(r"^classDef\s+([^\s]+)\s+(.+)$", line, re.IGNORECASE)
        if m:
            class_names = [c.strip() for c in m.group(1).split(",") if c.strip()]
            props = _parse_style_props(m.group(2))
            for cname in class_names:
                self.diagram.class_defs.setdefault(cname, {}).update(props)

    def _parse_class_assign(self, line: str):
        clean_line = line.rstrip(";").strip()
        m = re.match(r"^class\s+(.+?)\s+([A-Za-z0-9_\-,]+)$", clean_line, re.IGNORECASE)
        if m:
            node_ids = [n.strip() for n in m.group(1).split(",") if n.strip()]
            class_names = [c.strip() for c in m.group(2).split(",") if c.strip()]
            for nid in node_ids:
                for cname in class_names:
                    if cname not in self._pending_classes[nid]:
                        self._pending_classes[nid].append(cname)
                    if nid in self.diagram.nodes and cname not in self.diagram.nodes[nid].classes:
                        self.diagram.nodes[nid].classes.append(cname)

    def _parse_style_directive(self, line: str):
        m = re.match(r"^style\s+([^\s]+)\s+(.+)$", line, re.IGNORECASE)
        if m:
            target_ids = [t.strip() for t in m.group(1).split(",") if t.strip()]
            props = _parse_style_props(m.group(2))
            for tid in target_ids:
                self._pending_styles[tid].update(props)
                if tid in self.diagram.nodes:
                    self.diagram.nodes[tid].style.update(props)
                else:
                    sub = self._find_subgraph(tid)
                    if sub:
                        sub.style.update(props)

    def _parse_link_style(self, line: str):
        m = re.match(r"^linkStyle\s+(default|[\d\s,]+)\s+(.+)$", line, re.IGNORECASE)
        if m:
            target_spec = m.group(1).strip()
            props = _parse_style_props(m.group(2))
            if target_spec.lower() == "default":
                self.diagram.link_styles.setdefault(-1, {}).update(props)
            else:
                for tok in target_spec.split(","):
                    tok = tok.strip()
                    if tok.isdigit():
                        idx = int(tok)
                        self.diagram.link_styles.setdefault(idx, {}).update(props)

    def _handle_subgraph_start(self, line: str, line_num: int):
        content = line[len("subgraph"):].strip()
        sub_id = ""
        sub_title = ""

        # Check for brackets id[title] or id["title"]
        m_bracket = re.match(r"^([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)\s*\[(.*?)\]$", content)
        if m_bracket:
            sub_id = m_bracket.group(1)
            sub_title = clean_label_text(m_bracket.group(2))
        else:
            # Quoted title only: subgraph "Title"
            m_quoted = re.match(r"^[\"'](.*?)[\"']$", content)
            if m_quoted:
                sub_title = clean_label_text(m_quoted.group(1))
                sub_id = re.sub(r"\W+", "_", sub_title).strip("_") or f"sub_{len(self.diagram.subgraphs) + 1}"
            else:
                parts = content.split(None, 1)
                if len(parts) == 2:
                    sub_id = parts[0]
                    sub_title = clean_label_text(parts[1])
                elif len(parts) == 1:
                    sub_id = parts[0]
                    sub_title = parts[0]
                else:
                    sub_id = f"sub_{len(self.diagram.subgraphs) + 1}"
                    sub_title = sub_id

        subgraph = Subgraph(id=sub_id, title=sub_title or sub_id)
        if self.subgraph_stack:
            self.subgraph_stack[-1].children.append(subgraph)
        else:
            self.diagram.subgraphs.append(subgraph)
        self.subgraph_stack.append(subgraph)

    def _handle_subgraph_end(self, line_num: int, line: str):
        if not self.subgraph_stack:
            raise MermaidParseError("Found 'end' without matching 'subgraph'", line_num, line)
        self.subgraph_stack.pop()

    def _parse_statement(self, line: str, line_num: int):
        tokens, edges_meta = self._split_edges(line)
        if not tokens:
            return

        parsed_groups: List[List[Node]] = []
        for token in tokens:
            specs = self._split_node_group(token.strip())
            group_nodes = []
            for spec in specs:
                node = self._parse_node_spec(spec.strip())
                if node:
                    self._register_node(node)
                    group_nodes.append(node)
            if group_nodes:
                parsed_groups.append(group_nodes)

        # Connect consecutive groups
        for i, edge_info in enumerate(edges_meta):
            if i < len(parsed_groups) - 1:
                src_group = parsed_groups[i]
                tgt_group = parsed_groups[i + 1]
                for src in src_group:
                    for tgt in tgt_group:
                        edge = Edge(
                            source_id=src.id,
                            target_id=tgt.id,
                            label=edge_info.get("label", ""),
                            style=edge_info.get("style", EdgeStyle.SOLID),
                            arrow_start=edge_info.get("arrow_start", ArrowType.NONE),
                            arrow_end=edge_info.get("arrow_end", ArrowType.ARROW)
                        )
                        self.diagram.edges.append(edge)

    def _register_node(self, node: Node):
        if node.id not in self.diagram.nodes:
            self.diagram.nodes[node.id] = node
        else:
            existing = self.diagram.nodes[node.id]
            if existing.shape == ShapeType.RECTANGLE and node.shape != ShapeType.RECTANGLE:
                existing.shape = node.shape
            if existing.label == existing.id and node.label != node.id:
                existing.label = node.label
            if node.bold:
                existing.bold = True
            for c in node.classes:
                if c not in existing.classes:
                    existing.classes.append(c)
            if node.style:
                existing.style.update(node.style)

        # If inside a subgraph, record membership
        if self.subgraph_stack:
            curr_sub = self.subgraph_stack[-1]
            if node.id not in curr_sub.node_ids:
                curr_sub.node_ids.append(node.id)

    def _parse_node_spec(self, text: str) -> Optional[Node]:
        # 1. Strip trailing semicolons and whitespace FIRST
        text = re.sub(r"[\s;]+$", "", text.strip())
        if not text:
            return None

        # 2. Extract inline class attachments :::className before checking shape delimiters
        inline_classes: List[str] = []
        while True:
            m_cls = re.search(r":::([A-Za-z0-9_\-]+)\s*$", text)
            if m_cls:
                inline_classes.insert(0, m_cls.group(1))
                text = re.sub(r"[\s;]+$", "", text[:m_cls.start()].strip())
            else:
                break

        if not text:
            return None

        # 3. Check Mermaid v10/v11 expanded shape syntax: nodeId@{ shape: ..., label: ... }
        m_expanded = re.match(r"^([^\s@\{\[\(\>]+)\s*@\{\s*(.*?)\s*\}$", text, re.DOTALL)
        if m_expanded:
            node_id = m_expanded.group(1).strip()
            body = m_expanded.group(2)
            shape_type = ShapeType.RECTANGLE
            m_shape = re.search(r"\bshape\s*:\s*[\"']?([A-Za-z0-9_\-]+)[\"']?", body, re.IGNORECASE)
            if m_shape:
                s_key = m_shape.group(1).lower()
                shape_type = EXPANDED_SHAPE_MAP.get(s_key, ShapeType.RECTANGLE)

            raw_label = ""
            m_lbl = re.search(r"\blabel\s*:\s*(\"[^\"]*\"|'[^']*'|[^,}]+)", body, re.IGNORECASE)
            if m_lbl:
                raw_label = m_lbl.group(1).strip()

            bold = has_bold_markup(raw_label) if raw_label else False
            label = clean_label_text(raw_label) if raw_label else node_id
            return Node(
                id=node_id,
                label=label or node_id,
                shape=shape_type,
                classes=inline_classes,
                bold=bold,
            )

        # 4. Check standard shape delimiters
        for open_d, close_d, shape_type in SHAPE_DELIMITERS:
            idx_open = text.find(open_d)
            if idx_open != -1 and text.endswith(close_d):
                node_id = text[:idx_open].strip()
                # Also check if node_id had inline :::class before the delimiter
                while ":::" in node_id:
                    m_id_cls = re.search(r":::([A-Za-z0-9_\-]+)$", node_id)
                    if m_id_cls:
                        inline_classes.insert(0, m_id_cls.group(1))
                        node_id = node_id[:m_id_cls.start()].strip()
                    else:
                        break
                label_raw = text[idx_open + len(open_d):-len(close_d)]
                bold = has_bold_markup(label_raw)
                label = clean_label_text(label_raw)
                return Node(
                    id=node_id,
                    label=label or node_id,
                    shape=shape_type,
                    classes=inline_classes,
                    bold=bold,
                )

        # 5. Simple ID without brackets
        node_id = re.sub(r"[\s;]+$", "", text.strip())
        if node_id:
            return Node(
                id=node_id,
                label=node_id,
                shape=ShapeType.RECTANGLE,
                classes=inline_classes,
            )
        return None

    def _split_node_group(self, group_str: str) -> List[str]:
        """
        Splits a node group string on '&' operators at the top level.
        """
        parts = []
        current = []
        in_quote = False
        quote_char = ""
        bracket_depth = 0

        for ch in group_str:
            if in_quote:
                current.append(ch)
                if ch == quote_char:
                    in_quote = False
            else:
                if ch in ('"', "'"):
                    in_quote = True
                    quote_char = ch
                    current.append(ch)
                elif ch in ("[", "(", "{"):
                    bracket_depth += 1
                    current.append(ch)
                elif ch in ("]", ")", "}"):
                    if bracket_depth > 0:
                        bracket_depth -= 1
                    current.append(ch)
                elif ch == "&" and bracket_depth == 0:
                    part = "".join(current).strip()
                    if part:
                        parts.append(part)
                    current = []
                else:
                    current.append(ch)

        part = "".join(current).strip()
        if part:
            parts.append(part)
        return parts

    def _split_edges(self, line: str) -> Tuple[List[str], List[dict]]:
        """
        Splits a line into node tokens and edge metadata list using quote/bracket-aware scanning.
        """
        masked_line = _mask_protected_regions(line)

        pattern = re.compile(
            # 1. Infix dotted: -. label .-> or -. label .-
            r"(?P<idot>(?P<idot_s><|(?<!\S)[ox])?-\.\s+(?P<idot_lbl>.+?)\s+\.+-(?P<idot_e>>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$))?)|"
            # 2. Infix thick: == label ==> or == label ===
            r"(?P<ithk>(?<!=)(?P<ithk_s><|(?<!\S)[ox])?==\s+(?P<ithk_lbl>.+?)\s+={2,}(?P<ithk_e>>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$))?)|"
            # 3. Infix solid: -- label --> or -- label --- or -- label --o / --x
            r"(?P<isol>(?<!-)(?P<isol_s><|(?<!\S)[ox])?--\s+(?!-)(?P<isol_lbl>.+?)\s+(?:(?P<isol_e1>-{2,}(?:>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$)))|(?P<isol_e2>-{3,})))|"
            # 4. Invisible links: ~~~
            r"(?P<inv>~{3,}(?:\|(?P<pipe_inv>[^|]*)\|)?)|"
            # 5. Dotted links (plain or pipe-labeled): -.->, -...->, <-.->, -.->o, -.->x, -.-
            r"(?P<dot>(?P<dot_s><|(?<!\S)[ox])?-\.+-(?P<dot_e>>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$))?(?:\|(?P<pipe_dot>[^|]*)\|)?)|"
            # 6. Thick links (plain or pipe-labeled): ==>, ===>, <==>, ===, ==
            r"(?P<thk>(?P<thk_s><|(?<!\S)[ox])?={2,}(?P<thk_e>>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$))?(?:\|(?P<pipe_thk>[^|]*)\|)?)|"
            # 7a. Solid links with end marker (>, o, x): -->, --->, <--> , --o, o--o, --x, x--x
            r"(?P<sol1>(?P<sol1_s><|(?<!\S)[ox])?-{2,}(?P<sol1_e>>[ox]?(?=\s|\||$)|>|[ox](?=\s|\||$))(?:\|(?P<pipe_sol1>[^|]*)\|)?)|"
            # 7b. Solid links with start marker only: <--, o--, x--
            r"(?P<sol2>(?P<sol2_s><|(?<!\S)[ox])-{2,}(?:\|(?P<pipe_sol2>[^|]*)\|)?)|"
            # 7c. Open solid links (3+ dashes, or 2 dashes with pipe label): ---, ----, ---|lbl|, --|lbl|
            r"(?P<sol3>-{3,}(?:\|(?P<pipe_sol3>[^|]*)\|)?|--\|(?P<pipe_sol4>[^|]*)\|)"
        )

        tokens: List[str] = []
        edges: List[dict] = []
        last_end = 0

        for match in pattern.finditer(masked_line):
            node_part = line[last_end:match.start()].strip()
            tokens.append(node_part)
            last_end = match.end()

            label = ""
            style = EdgeStyle.SOLID
            arrow_start = ArrowType.NONE
            arrow_end = ArrowType.NONE

            # Extract label from original unmasked line using group span
            for lbl_group in (
                "idot_lbl", "ithk_lbl", "isol_lbl",
                "pipe_inv", "pipe_dot", "pipe_thk",
                "pipe_sol1", "pipe_sol2", "pipe_sol3", "pipe_sol4",
            ):
                if match.group(lbl_group) is not None:
                    l_start, l_end = match.span(lbl_group)
                    label = clean_label_text(line[l_start:l_end])
                    break

            if match.group("inv") is not None:
                style = EdgeStyle.INVISIBLE
                arrow_start = ArrowType.NONE
                arrow_end = ArrowType.NONE
            elif match.group("idot") is not None:
                style = EdgeStyle.DOTTED
                arrow_start = _parse_endpoint_marker(match.group("idot_s"))
                arrow_end = _parse_endpoint_marker(match.group("idot_e"))
            elif match.group("dot") is not None:
                style = EdgeStyle.DOTTED
                arrow_start = _parse_endpoint_marker(match.group("dot_s"))
                arrow_end = _parse_endpoint_marker(match.group("dot_e"))
            elif match.group("ithk") is not None:
                style = EdgeStyle.THICK
                arrow_start = _parse_endpoint_marker(match.group("ithk_s"))
                arrow_end = _parse_endpoint_marker(match.group("ithk_e"))
            elif match.group("thk") is not None:
                style = EdgeStyle.THICK
                arrow_start = _parse_endpoint_marker(match.group("thk_s"))
                arrow_end = _parse_endpoint_marker(match.group("thk_e"))
            elif match.group("isol") is not None:
                style = EdgeStyle.SOLID
                arrow_start = _parse_endpoint_marker(match.group("isol_s"))
                arrow_end = _parse_endpoint_marker(match.group("isol_e1"))
            elif match.group("sol1") is not None:
                style = EdgeStyle.SOLID
                arrow_start = _parse_endpoint_marker(match.group("sol1_s"))
                arrow_end = _parse_endpoint_marker(match.group("sol1_e"))
            elif match.group("sol2") is not None:
                style = EdgeStyle.SOLID
                arrow_start = _parse_endpoint_marker(match.group("sol2_s"))
                arrow_end = ArrowType.NONE
            else:
                style = EdgeStyle.SOLID
                arrow_start = ArrowType.NONE
                arrow_end = ArrowType.NONE

            edges.append({
                "label": label,
                "style": style,
                "arrow_start": arrow_start,
                "arrow_end": arrow_end,
            })

        remaining = line[last_end:].strip()
        if remaining:
            tokens.append(remaining)

        return tokens, edges
