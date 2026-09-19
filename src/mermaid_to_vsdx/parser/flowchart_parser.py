"""
Mermaid Flowchart Parser.
Parses Flowchart and Graph Mermaid diagrams into AST FlowchartDiagram models.
"""

import re
from typing import Dict, List, Optional, Tuple
from .ast_nodes import (
    FlowchartDiagram, Node, Edge, Subgraph, ShapeType, EdgeStyle, ArrowType
)
from .base_parser import MermaidParseError, preprocess_lines
from ..utils.unicode_helper import clean_label_text, ensure_utf8


# Shape delimiter pairs ordered from most specific to least specific
SHAPE_DELIMITERS = [
    ("[[", "]]", ShapeType.SUBROUTINE),
    ("[(", ")]", ShapeType.CYLINDER),
    ("((", "))", ShapeType.CIRCLE),
    ("{{", "}}", ShapeType.HEXAGON),
    ("([", "])", ShapeType.STADIUM),
    ("[/", "/]", ShapeType.PARALLELOGRAM),
    ("[\\", "\\]", ShapeType.PARALLELOGRAM),
    ("[/", "\\]", ShapeType.TRAPEZOID),
    ("[\\", "/]", ShapeType.TRAPEZOID),
    ("[", "]", ShapeType.RECTANGLE),
    ("(", ")", ShapeType.ROUNDED),
    (">", "]", ShapeType.ASYMMETRIC),
    ("{", "}", ShapeType.DIAMOND),
]


class FlowchartParser:
    """
    Parses Mermaid flowchart code into a FlowchartDiagram AST.
    """

    def __init__(self):
        self.diagram = FlowchartDiagram()
        self.subgraph_stack: List[Subgraph] = []

    def parse(self, code: str) -> FlowchartDiagram:
        self.diagram = FlowchartDiagram()
        self.subgraph_stack = []

        raw_lines = preprocess_lines(code)
        if not raw_lines:
            raise MermaidParseError("Empty Mermaid diagram source code.")

        header_idx, header_line = raw_lines[0]
        self._parse_header(header_line, header_idx)

        for line_num, line in raw_lines[1:]:
            self._parse_line(line, line_num)

        return self.diagram

    def _parse_header(self, line: str, line_num: int):
        # Match 'graph TD' or 'flowchart LR'
        m = re.match(r'^(graph|flowchart)\s+([A-Za-z]{2})', line, re.IGNORECASE)
        if m:
            self.diagram.direction = m.group(2).upper()
        else:
            # Fallback if direction wasn't specified
            m_simple = re.match(r'^(graph|flowchart)', line, re.IGNORECASE)
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

        # Ignore classDef, style, click, linkStyle lines for AST structure
        if re.match(r'^(classDef|class|style|click|linkStyle)\b', line, re.IGNORECASE):
            return

        # Process node or edge line
        self._parse_statement(line, line_num)

    def _handle_subgraph_start(self, line: str, line_num: int):
        # Syntax:
        # subgraph id [title]
        # subgraph id ["Turkish Title"]
        # subgraph id
        # subgraph "Turkish Title"
        content = line[len("subgraph"):].strip()
        sub_id = ""
        sub_title = ""

        # Check for brackets id[title] or id["title"]
        m_bracket = re.match(r'^([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)\s*\[(.*?)\]$', content)
        if m_bracket:
            sub_id = m_bracket.group(1)
            sub_title = clean_label_text(m_bracket.group(2))
        else:
            # Quoted title only: subgraph "Title"
            m_quoted = re.match(r'^["\'](.*?)["\']$', content)
            if m_quoted:
                sub_title = clean_label_text(m_quoted.group(1))
                sub_id = re.sub(r'\W+', '_', sub_title).strip('_') or f"sub_{len(self.diagram.subgraphs) + 1}"
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
        # A statement can be a single node or a chain of connections
        # e.g., A[Node A] -->|Label| B(Node B) --> C
        # Let's split on edge operators while preserving labels
        # Edge operators:
        # --> , --- , -.-> , -.- , ==> , ==
        # With pipe labels: -->|text|
        # Or infix labels: -- text --> , -. text .-> , == text ==>

        tokens, edges_meta = self._split_edges(line)
        if not tokens:
            return

        parsed_nodes = []
        for token in tokens:
            node = self._parse_node_spec(token.strip())
            if node:
                self._register_node(node)
                parsed_nodes.append(node)

        # Connect consecutive nodes
        for i, edge_info in enumerate(edges_meta):
            if i < len(parsed_nodes) - 1:
                src = parsed_nodes[i]
                tgt = parsed_nodes[i + 1]
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
            # Update label/shape if current has more details than default
            existing = self.diagram.nodes[node.id]
            if existing.shape == ShapeType.RECTANGLE and node.shape != ShapeType.RECTANGLE:
                existing.shape = node.shape
            if existing.label == existing.id and node.label != node.id:
                existing.label = node.label

        # If inside a subgraph, record membership
        if self.subgraph_stack:
            curr_sub = self.subgraph_stack[-1]
            if node.id not in curr_sub.node_ids:
                curr_sub.node_ids.append(node.id)

    def _parse_node_spec(self, text: str) -> Optional[Node]:
        text = text.strip()
        if not text:
            return None

        # Check delimiters
        for open_d, close_d, shape_type in SHAPE_DELIMITERS:
            idx_open = text.find(open_d)
            if idx_open != -1 and text.endswith(close_d):
                node_id = text[:idx_open].strip()
                label_raw = text[idx_open + len(open_d):-len(close_d)]
                label = clean_label_text(label_raw)
                return Node(id=node_id, label=label or node_id, shape=shape_type)

        # Simple ID without brackets
        node_id = text.strip()
        # Clean ID of any trailing chars
        node_id = re.sub(r'[\s;]+$', '', node_id)
        if node_id:
            return Node(id=node_id, label=node_id, shape=ShapeType.RECTANGLE)
        return None

    def _split_edges(self, line: str) -> Tuple[List[str], List[dict]]:
        """
        Splits a line into node tokens and edge metadata list.
        Supports:
        A --> B
        A -->|label| B
        A -- label --> B
        A -. label .-> B
        A == label ==> B
        A --- B
        A -.- B
        A == B
        """
        # Regex matching all mermaid connectors
        # 1. Pipe labeled: (-->|label| | ---|label| | -.->|label| | ==>|label| )
        # 2. Infix labeled: (-- label --> | -. label .-> | == label ==>)
        # 3. Plain: (--> | --- | -.-> | -.- | ==> | ==)
        pattern = re.compile(
            r'(-->\|(?P<pipe_lbl1>[^|]*)\|)|'
            r'(==>\|(?P<pipe_lbl2>[^|]*)\|)|'
            r'(-\.->\|(?P<pipe_lbl3>[^|]*)\|)|'
            r'(---\|(?P<pipe_lbl4>[^|]*)\|)|'
            r'(--\s+(?P<infix_lbl1>.+?)\s+-->)|'
            r'(==\s+(?P<infix_lbl2>.+?)\s+==>)|'
            r'(-\.\s+(?P<infix_lbl3>.+?)\s+\.->)|'
            r'(==>)|(-->)|(-\.->)|(===)|(---)|(-\.-)|(==)'
        )

        tokens = []
        edges = []
        last_end = 0

        for match in pattern.finditer(line):
            node_part = line[last_end:match.start()].strip()
            tokens.append(node_part)
            last_end = match.end()

            matched_text = match.group(0)
            label = ""
            style = EdgeStyle.SOLID
            arrow_end = ArrowType.ARROW

            # Determine label
            for group_name in ["pipe_lbl1", "pipe_lbl2", "pipe_lbl3", "pipe_lbl4",
                               "infix_lbl1", "infix_lbl2", "infix_lbl3"]:
                val = match.group(group_name)
                if val is not None:
                    label = clean_label_text(val)
                    break

            # Determine style & arrow
            if "==" in matched_text:
                style = EdgeStyle.THICK
                arrow_end = ArrowType.ARROW if ">" in matched_text else ArrowType.NONE
            elif "-." in matched_text:
                style = EdgeStyle.DOTTED
                arrow_end = ArrowType.ARROW if ">" in matched_text else ArrowType.NONE
            else:
                style = EdgeStyle.SOLID
                arrow_end = ArrowType.ARROW if ">" in matched_text else ArrowType.NONE

            edges.append({
                "label": label,
                "style": style,
                "arrow_start": ArrowType.NONE,
                "arrow_end": arrow_end
            })

        remaining = line[last_end:].strip()
        if remaining:
            tokens.append(remaining)

        return tokens, edges
