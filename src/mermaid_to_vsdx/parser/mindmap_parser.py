"""
Mermaid Mindmap Diagram Parser.
Parses indentation-based `mindmap` diagrams into a hierarchical MindmapDiagram AST.
"""

import re
from typing import List, Tuple
from .ast_nodes import MindmapDiagram, MindmapNode, ShapeType
from .base_parser import MermaidParseError, preprocess_lines_raw


_SHAPE_PATTERNS: List[Tuple[re.Pattern, ShapeType]] = [
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\(\(\((?P<label>.+)\)\)\)$"), ShapeType.DOUBLE_CIRCLE),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\(\((?P<label>.+)\)\)$"), ShapeType.CIRCLE),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\)\)(?P<label>.+)\(\($"), ShapeType.STADIUM),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\(\[(?P<label>.+)\]\)$"), ShapeType.STADIUM),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\(-(?P<label>.+)-\)$"), ShapeType.STADIUM),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\{\{(?P<label>.+)\}\}$"), ShapeType.HEXAGON),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\[\[(?P<label>.+)\]\]$"), ShapeType.SUBROUTINE),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\[(?P<label>.+)\]$"), ShapeType.RECTANGLE),
    (re.compile(r"^(?:(?P<id>[A-Za-z0-9_.-]+))?\((?P<label>.+)\)$"), ShapeType.ROUNDED),
]


def _parse_mindmap_node_text(raw_text: str, fallback_id: str) -> Tuple[str, str, ShapeType]:
    """
    Extracts (node_id, clean_label, shape_type) from a single mindmap line.
    """
    text = raw_text.strip()
    # Strip inline ::icon(...) or :::class annotations
    text = re.sub(r"::icon\([^)]*\)", "", text).strip()
    text = re.sub(r":::[A-Za-z0-9_-]+", "", text).strip()

    for pattern, shape_type in _SHAPE_PATTERNS:
        m = pattern.match(text)
        if m:
            node_id = m.group("id") or fallback_id
            label = m.group("label").strip()
            if len(label) >= 2 and label[0] == '"' and label[-1] == '"':
                label = label[1:-1]
            label = re.sub(r"<br\s*/?>", "\n", label, flags=re.IGNORECASE)
            return node_id, label, shape_type

    label = text
    if len(label) >= 2 and label[0] == '"' and label[-1] == '"':
        label = label[1:-1]
    label = re.sub(r"<br\s*/?>", "\n", label, flags=re.IGNORECASE)
    return fallback_id, label, ShapeType.ROUNDED


class MindmapParser:
    """Parser for Mermaid `mindmap` diagrams."""

    def parse(self, mermaid_code: str) -> MindmapDiagram:
        lines = preprocess_lines_raw(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty mindmap diagram.")

        diagram = MindmapDiagram()
        header_seen = False
        stack: List[Tuple[int, MindmapNode]] = []
        node_counter = 0

        for line_num, raw_line in lines:
            expanded = raw_line.expandtabs(4)
            stripped = expanded.strip()
            if not stripped:
                continue

            if not header_seen:
                if stripped.lower().startswith("mindmap"):
                    header_seen = True
                    continue
                else:
                    raise MermaidParseError("Expected 'mindmap' header.", line_num, raw_line)

            # Ignore ::icon(...) and :::class lines
            if stripped.startswith("::icon(") or stripped.startswith(":::"):
                continue

            if stripped.lower().startswith("title "):
                diagram.title = stripped[6:].strip().strip('"')
                continue

            indent = len(expanded) - len(stripped)
            node_counter += 1
            fallback_id = f"mm_{node_counter}"
            node_id, label, shape = _parse_mindmap_node_text(stripped, fallback_id)
            if not label:
                continue

            while stack and stack[-1][0] >= indent:
                stack.pop()

            if not stack:
                if diagram.root is None:
                    node = MindmapNode(id=node_id, label=label, shape=shape, level=0)
                    diagram.root = node
                    stack.append((indent, node))
                else:
                    # Fallback if multiple unindented roots appear: attach under first root
                    node = MindmapNode(id=node_id, label=label, shape=shape, level=1)
                    diagram.root.children.append(node)
                    stack.append((indent, node))
            else:
                parent = stack[-1][1]
                node = MindmapNode(
                    id=node_id,
                    label=label,
                    shape=shape,
                    level=parent.level + 1,
                )
                parent.children.append(node)
                stack.append((indent, node))

        if diagram.root is None:
            diagram.root = MindmapNode(id="mm_root", label="Mindmap", shape=ShapeType.CIRCLE, level=0)

        return diagram
