"""
Mermaid Block Diagram Parser.
Parses grid-based block diagram syntax into BlockDiagram AST models.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from .ast_nodes import (
    BlockDiagram, BlockNode, BlockEdge, ShapeType, EdgeStyle
)
from .base_parser import MermaidParseError, preprocess_lines
from ..utils.unicode_helper import clean_label_text, ensure_utf8


class BlockParser:
    """
    Parses Mermaid block diagrams (block, block-beta) into a BlockDiagram AST.
    """

    SHAPE_PATTERNS = [
        ("DOUBLE_CIRCLE", r'^([A-Za-z0-9_\-]+)\(\(\((.*?)\)\)\)(?::(\d+))?$'),
        ("CIRCLE", r'^([A-Za-z0-9_\-]+)\(\((.*?)\)\)(?::(\d+))?$'),
        ("CYLINDER", r'^([A-Za-z0-9_\-]+)\[\((.*?)\)\](?::(\d+))?$'),
        ("SUBROUTINE", r'^([A-Za-z0-9_\-]+)\[\[(.*?)\]\](?::(\d+))?$'),
        ("HEXAGON", r'^([A-Za-z0-9_\-]+)\{\{(.*?)\}\}(?::(\d+))?$'),
        ("DIAMOND", r'^([A-Za-z0-9_\-]+)\{(.*?)\}(?::(\d+))?$'),
        ("ROUNDED", r'^([A-Za-z0-9_\-]+)\(\[(.*?)\]\)(?::(\d+))?$'),
        ("ROUNDED_RECT", r'^([A-Za-z0-9_\-]+)\((.*?)\)(?::(\d+))?$'),
        ("PARALLELOGRAM", r'^([A-Za-z0-9_\-]+)\[\/(.*?)\/\](?::(\d+))?$'),
        ("PARALLELOGRAM_ALT", r'^([A-Za-z0-9_\-]+)\[\\(.*?)\\\](?::(\d+))?$'),
        ("TRAPEZOID", r'^([A-Za-z0-9_\-]+)\[\/(.*?)\\\](?::(\d+))?$'),
        ("TRAPEZOID_ALT", r'^([A-Za-z0-9_\-]+)\[\\(.*?)\/\](?::(\d+))?$'),
        ("RECTANGLE", r'^([A-Za-z0-9_\-]+)\[(.*?)\](?::(\d+))?$'),
        ("BLOCK_ARROW", r'^([A-Za-z0-9_\-]+)<\[(.*?)\]>\((.*?)\)(?::(\d+))?$'),
        ("SIMPLE", r'^([A-Za-z0-9_\-]+)(?::(\d+))?$'),
    ]

    SHAPE_MAP = {
        "DOUBLE_CIRCLE": ShapeType.DOUBLE_CIRCLE,
        "CIRCLE": ShapeType.CIRCLE,
        "CYLINDER": ShapeType.CYLINDER,
        "SUBROUTINE": ShapeType.SUBROUTINE,
        "HEXAGON": ShapeType.HEXAGON,
        "DIAMOND": ShapeType.DIAMOND,
        "ROUNDED": ShapeType.ROUNDED_RECT,
        "ROUNDED_RECT": ShapeType.ROUNDED_RECT,
        "PARALLELOGRAM": ShapeType.PARALLELOGRAM,
        "PARALLELOGRAM_ALT": ShapeType.PARALLELOGRAM_ALT,
        "TRAPEZOID": ShapeType.TRAPEZOID,
        "TRAPEZOID_ALT": ShapeType.TRAPEZOID_ALT,
        "RECTANGLE": ShapeType.RECTANGLE,
        "BLOCK_ARROW": ShapeType.RECTANGLE,
        "SIMPLE": ShapeType.RECTANGLE,
    }

    def __init__(self):
        self.diagram = BlockDiagram()
        self.container_stack: List[BlockNode] = []
        self.space_counter = 0

    def parse(self, text: str) -> BlockDiagram:
        text = ensure_utf8(text)
        raw_lines = preprocess_lines(text)
        if not raw_lines:
            raise MermaidParseError("Empty block diagram input", 1, "")

        first_line_num, first_line = raw_lines[0]
        if not re.match(r'^block(-beta)?\b', first_line, re.IGNORECASE):
            raise MermaidParseError(f"Expected 'block' or 'block-beta' header, got '{first_line}'", first_line_num, first_line)

        self.diagram = BlockDiagram()
        self.container_stack = []
        self.space_counter = 0

        for line_num, line in raw_lines[1:]:
            self._parse_line(line, line_num)

        return self.diagram

    def _parse_line(self, line: str, line_num: int):
        line = line.strip()
        if not line or line.startswith("%%"):
            return

        # Check columns directive: columns <num>
        m_col = re.match(r'^columns\s+(\d+)$', line, re.IGNORECASE)
        if m_col:
            num = int(m_col.group(1))
            if self.container_stack:
                self.container_stack[-1].columns = num
            else:
                self.diagram.columns = num
            return

        # Check block composite start: block:ID[:width]
        m_blk_start = re.match(r'^block:([A-Za-z0-9_\-]+)(?::(\d+))?$', line, re.IGNORECASE)
        if m_blk_start:
            blk_id = m_blk_start.group(1)
            width = int(m_blk_start.group(2)) if m_blk_start.group(2) else 1
            node = BlockNode(id=blk_id, label=blk_id, width_cols=width, children=[])
            self._add_node(node)
            self.container_stack.append(node)
            return

        # Check block composite end
        if line.lower() == "end":
            if self.container_stack:
                self.container_stack.pop()
            return

        # Check style / classDef / class
        if line.startswith("style "):
            self._parse_style(line)
            return
        if line.startswith("classDef "):
            self._parse_class_def(line)
            return
        if line.startswith("class "):
            self._parse_class_assign(line)
            return

        # Check edge / connection
        # A --> B, A --- B, A -- text --> B, A -->|text| B
        edge_match = self._try_parse_edge(line)
        if edge_match:
            self.diagram.edges.append(edge_match)
            return

        # Otherwise, parse one or more block node tokens on this line
        tokens = self._tokenize_line(line)
        for tok in tokens:
            node = self._parse_node_token(tok, line_num)
            if node:
                self._add_node(node)

    def _add_node(self, node: BlockNode):
        if self.container_stack:
            self.container_stack[-1].children.append(node)
        else:
            self.diagram.blocks.append(node)

    def _tokenize_line(self, line: str) -> List[str]:
        tokens = []
        cur = []
        in_quote = False
        depth = 0

        for char in line:
            if char == '"':
                in_quote = not in_quote
                cur.append(char)
            elif in_quote:
                cur.append(char)
            elif char in ('[', '(', '{', '<'):
                depth += 1
                cur.append(char)
            elif char in (']', ')', '}', '>'):
                depth = max(0, depth - 1)
                cur.append(char)
            elif char.isspace() and depth == 0:
                if cur:
                    tokens.append("".join(cur))
                    cur = []
            else:
                cur.append(char)

        if cur:
            tokens.append("".join(cur))

        return tokens

    def _parse_node_token(self, token: str, line_num: int) -> Optional[BlockNode]:
        token = token.strip()
        if not token:
            return None

        # Check space[:width]
        m_space = re.match(r'^space(?::(\d+))?$', token, re.IGNORECASE)
        if m_space:
            self.space_counter += 1
            w = int(m_space.group(1)) if m_space.group(1) else 1
            return BlockNode(id=f"space_{self.space_counter}", is_space=True, width_cols=w)

        # Match shapes
        for shape_key, pattern in self.SHAPE_PATTERNS:
            m = re.match(pattern, token)
            if m:
                node_id = m.group(1)
                label = ""
                width = 1

                if shape_key == "SIMPLE":
                    label = node_id
                    if m.group(2):
                        width = int(m.group(2))
                elif shape_key == "BLOCK_ARROW":
                    label = clean_label_text(m.group(2))
                    # arrow direction is in m.group(3)
                else:
                    label = clean_label_text(m.group(2))
                    if m.group(3):
                        width = int(m.group(3))

                return BlockNode(
                    id=node_id,
                    label=label if label else node_id,
                    shape=self.SHAPE_MAP.get(shape_key, ShapeType.RECTANGLE),
                    width_cols=width,
                )

        # Fallback simple token
        return BlockNode(id=token, label=token, shape=ShapeType.RECTANGLE, width_cols=1)

    def _try_parse_edge(self, line: str) -> Optional[BlockEdge]:
        # Edge patterns:
        # A --> B
        # A --- B
        # A -->|label| B
        # A -- label --> B
        # A -- label --- B
        m1 = re.match(r'^([A-Za-z0-9_\-]+)\s*-->\|(.*?)\|\s*([A-Za-z0-9_\-]+)$', line)
        if m1:
            return BlockEdge(source_id=m1.group(1), target_id=m1.group(3), label=clean_label_text(m1.group(2)), has_arrow=True)

        m2 = re.match(r'^([A-Za-z0-9_\-]+)\s*--\s*(.*?)\s*-->\s*([A-Za-z0-9_\-]+)$', line)
        if m2:
            return BlockEdge(source_id=m2.group(1), target_id=m2.group(3), label=clean_label_text(m2.group(2)), has_arrow=True)

        m3 = re.match(r'^([A-Za-z0-9_\-]+)\s*--\s*(.*?)\s*---\s*([A-Za-z0-9_\-]+)$', line)
        if m3:
            return BlockEdge(source_id=m3.group(1), target_id=m3.group(3), label=clean_label_text(m3.group(2)), has_arrow=False)

        m4 = re.match(r'^([A-Za-z0-9_\-]+)\s*-->\s*([A-Za-z0-9_\-]+)$', line)
        if m4:
            return BlockEdge(source_id=m4.group(1), target_id=m4.group(2), has_arrow=True)

        m5 = re.match(r'^([A-Za-z0-9_\-]+)\s*---\s*([A-Za-z0-9_\-]+)$', line)
        if m5:
            return BlockEdge(source_id=m5.group(1), target_id=m5.group(2), has_arrow=False)

        return None

    def _parse_style(self, line: str):
        # style ID fill:#...,stroke:#...
        parts = line.split(maxsplit=2)
        if len(parts) >= 3:
            node_id = parts[1]
            style_str = parts[2]
            props = {}
            for item in style_str.split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    props[k.strip()] = v.strip()
            # Assign to node if found
            self._apply_style_recursive(self.diagram.blocks, node_id, props)

    def _apply_style_recursive(self, nodes: List[BlockNode], node_id: str, props: Dict[str, str]):
        for n in nodes:
            if n.id == node_id:
                n.style.update(props)
                return
            if n.children:
                self._apply_style_recursive(n.children, node_id, props)

    def _parse_class_def(self, line: str):
        # classDef className fill:#...,stroke:#...
        parts = line.split(maxsplit=2)
        if len(parts) >= 3:
            class_name = parts[1]
            style_str = parts[2]
            props = {}
            for item in style_str.split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    props[k.strip()] = v.strip()
            self.diagram.class_defs[class_name] = props

    def _parse_class_assign(self, line: str):
        # class A,B className
        parts = line.split(maxsplit=2)
        if len(parts) >= 3:
            targets = [t.strip() for t in parts[1].split(",")]
            class_name = parts[2].strip()
            for t in targets:
                self._apply_class_recursive(self.diagram.blocks, t, class_name)

    def _apply_class_recursive(self, nodes: List[BlockNode], node_id: str, class_name: str):
        for n in nodes:
            if n.id == node_id:
                if class_name not in n.classes:
                    n.classes.append(class_name)
                return
            if n.children:
                self._apply_class_recursive(n.children, node_id, class_name)
