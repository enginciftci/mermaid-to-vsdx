"""
UML Class Diagram Drawing Engine for Microsoft Visio.
Translates ClassDiagram AST into native .vsdx drawings with multi-compartment
UML class shapes, attributes, methods, annotations, and UML relationship connectors.
"""

import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from .com_client import VisioSession
from .palettes import PaletteTheme, get_palette
from .shapes import style_shape, format_shape_text
from ..parser.ast_nodes import (
    ClassDiagram, ClassNode, ClassRelationship, RelationshipType
)
from ..utils.unicode_helper import DEFAULT_FONT


class ClassBuilder:
    """
    Builds a Microsoft Visio UML Class Diagram from a ClassDiagram AST.
    """

    def __init__(
        self,
        diagram: ClassDiagram,
        palette: Optional[PaletteTheme] = None,
        font_name: str = DEFAULT_FONT
    ):
        self.diagram = diagram
        self.palette = palette or get_palette()
        self.font_name = font_name
        self.class_positions: Dict[str, Tuple[float, float, float, float]] = {}
        self.visio_shapes: Dict[str, object] = {}

    def build_and_save(self, output_vsdx_path: str) -> str:
        """
        Builds the UML class diagram in Visio and saves to .vsdx.
        """
        abs_output_path = os.path.abspath(output_vsdx_path)
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)

        with VisioSession(visible=False) as visio_app:
            doc = visio_app.Documents.Add("")
            page = doc.Pages.Item(1)

            classes = self.diagram.classes
            if not classes:
                doc.SaveAs(abs_output_path)
                doc.Close()
                return abs_output_path

            # 1. Compute layout positions
            self._compute_layout()

            # 2. Draw Class Shapes
            self._draw_classes(page, visio_app)

            # 3. Draw Relationships
            self._draw_relationships(page, visio_app)

            # 4. Fit page to diagram
            try:
                page.ResizeToFitContents()
            except Exception:
                pass

            doc.SaveAs(abs_output_path)
            doc.Close()

        return abs_output_path

    def _compute_layout(self):
        """
        Arranges classes into hierarchical layers based on relationships
        (Generalization / Composition hierarchy).
        """
        classes = self.diagram.classes
        relationships = self.diagram.relationships

        # Build adjacency
        in_degree = {name: 0 for name in classes}
        adj = defaultdict(list)

        for rel in relationships:
            if rel.source_name in classes and rel.target_name in classes:
                # In UML, subclass points to superclass (Generalization)
                # We place superclass at higher rank (smaller Y) or vice-versa
                if rel.rel_type in (RelationshipType.INHERITANCE, RelationshipType.REALIZATION):
                    # Target is parent (top)
                    adj[rel.target_name].append(rel.source_name)
                    in_degree[rel.source_name] += 1
                else:
                    adj[rel.source_name].append(rel.target_name)
                    in_degree[rel.target_name] += 1

        # Ranks assignment via topological/BFS
        ranks: Dict[str, int] = {}
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        if not queue:
            queue.append(next(iter(classes.keys())))

        for name in queue:
            ranks[name] = 0

        visited = set(queue)
        while queue:
            curr = queue.popleft()
            curr_rank = ranks[curr]
            for neighbor in adj[curr]:
                ranks[neighbor] = max(ranks.get(neighbor, 0), curr_rank + 1)
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        for name in classes:
            if name not in ranks:
                ranks[name] = 0

        rank_groups = defaultdict(list)
        for name, r in sorted(ranks.items(), key=lambda x: (x[1], x[0])):
            rank_groups[r].append(name)

        # Calculate coordinates
        start_x = 1.5
        start_y = 10.0
        gap_x = 0.8
        gap_y = 0.9

        self.class_positions = {}

        for r, group in sorted(rank_groups.items()):
            # Determine maximum height in this row
            row_heights = []
            for name in group:
                node = classes[name]
                w, h = self._calculate_class_dimension(node)
                row_heights.append(h)
            max_row_h = max(row_heights) if row_heights else 1.5

            total_row_w = 0.0
            node_widths = {}
            for name in group:
                node = classes[name]
                w, h = self._calculate_class_dimension(node)
                node_widths[name] = (w, h)
                total_row_w += w
            total_row_w += max(0, len(group) - 1) * gap_x

            curr_x = start_x
            for name in group:
                w, h = node_widths[name]
                x1 = curr_x
                x2 = x1 + w
                y2 = start_y
                y1 = y2 - h
                self.class_positions[name] = (x1, y1, x2, y2)
                curr_x += w + gap_x

            start_y -= (max_row_h + gap_y)

    def _calculate_class_dimension(self, node: ClassNode) -> Tuple[float, float]:
        """
        Calculates width and height for a class shape based on text lines.
        """
        lines = [node.name]
        if node.annotation:
            lines.append(node.annotation)

        attrs = [m for m in node.members if not m.is_method]
        methods = [m for m in node.members if m.is_method]

        if attrs:
            lines.append("──────────────────────")
            for a in attrs:
                line_str = f"{a.visibility} {a.return_type + ' ' if a.return_type else ''}{a.name}".strip()
                lines.append(line_str)

        if methods:
            lines.append("──────────────────────")
            for m in methods:
                line_str = f"{m.visibility} {m.name}({m.parameters}){': ' + m.return_type if m.return_type else ''}".strip()
                lines.append(line_str)

        max_len = max(len(l) for l in lines) if lines else 10
        width = max(2.6, min(4.8, 0.11 * max_len + 0.6))
        height = max(1.2, 0.4 + 0.22 * len(lines))
        return width, height

    def _build_class_text(self, node: ClassNode) -> str:
        """
        Constructs the multi-compartment text for the Visio shape.
        """
        parts = []
        if node.annotation:
            parts.append(node.annotation)
        parts.append(node.name)

        attrs = [m for m in node.members if not m.is_method]
        methods = [m for m in node.members if m.is_method]

        if attrs or methods:
            parts.append("──────────────────────")
            for a in attrs:
                type_part = f"{a.return_type} " if a.return_type else ""
                parts.append(f"{a.visibility} {type_part}{a.name}")

        if methods:
            parts.append("──────────────────────")
            for m in methods:
                ret_part = f": {m.return_type}" if m.return_type else ""
                parts.append(f"{m.visibility} {m.name}({m.parameters}){ret_part}")

        return "\n".join(parts)

    def _draw_classes(self, page, visio_app):
        """
        Draws the UML class box shapes on the Visio page.
        """
        for name, node in self.diagram.classes.items():
            coords = self.class_positions.get(name, (1.0, 1.0, 3.6, 2.5))
            x1, y1, x2, y2 = coords

            shape = page.DrawRectangle(x1, y1, x2, y2)

            # Style with palette
            is_interface = "interface" in node.annotation.lower()
            fill_rgb = self.palette.decision_fill if is_interface else self.palette.default_fill
            border_rgb = self.palette.default_border

            style_shape(
                shape=shape,
                fill_rgb=fill_rgb,
                border_rgb=border_rgb,
                line_weight_pt=1.5,
                rounding_in=0.04
            )

            # Text formatting
            text = self._build_class_text(node)
            format_shape_text(
                shape=shape,
                text=text,
                font_name=self.font_name,
                font_size_pt=9,
                font_color_rgb=self.palette.default_text,
                bold=False,
                visio_app=visio_app
            )

            # Left align attributes/methods while keeping neat padding
            try:
                shape.CellsSRC(1, 0, 0).FormulaU = "0.08 in"  # Left Margin
                shape.CellsSRC(1, 0, 2).FormulaU = "0.08 in"  # Right Margin
                shape.CellsSRC(1, 0, 1).FormulaU = "0.08 in"  # Top Margin
                shape.CellsSRC(1, 0, 3).FormulaU = "0.08 in"  # Bottom Margin
            except Exception:
                pass

            self.visio_shapes[name] = shape

    def _draw_relationships(self, page, visio_app):
        """
        Draws connectors for UML class relationships.
        """
        for rel in self.diagram.relationships:
            shape_from = self.visio_shapes.get(rel.source_name)
            shape_to = self.visio_shapes.get(rel.target_name)
            if not (shape_from and shape_to):
                continue

            try:
                connector = page.Drop(visio_app.ConnectorToolDataObject, 0, 0)
            except Exception:
                connector = page.DrawLine(0, 0, 1, 1)

            try:
                connector.CellsU("BeginX").GlueTo(shape_from.CellsU("PinX"))
                connector.CellsU("EndX").GlueTo(shape_to.CellsU("PinX"))
            except Exception:
                pass

            # Connector styling based on UML relationship type
            self._apply_uml_connector_style(connector, rel.rel_type)

            # Label / Multiplicity
            label_text = rel.label
            if rel.multiplicity_source or rel.multiplicity_target:
                m_parts = []
                if rel.multiplicity_source:
                    m_parts.append(rel.multiplicity_source)
                if rel.label:
                    m_parts.append(rel.label)
                if rel.multiplicity_target:
                    m_parts.append(rel.multiplicity_target)
                label_text = "  ".join(m_parts)

            if label_text:
                format_shape_text(
                    connector,
                    label_text,
                    font_name=self.font_name,
                    font_size_pt=8,
                    font_color_rgb=self.palette.connector_text,
                    bold=False,
                    visio_app=visio_app
                )

    def _apply_uml_connector_style(self, connector, rel_type: RelationshipType):
        """
        Applies proper UML line patterns and arrowheads to a connector.
        """
        palette = self.palette

        try:
            connector.CellsU("LineColor").FormulaU = palette.connector_line
            connector.CellsU("LineWeight").FormulaU = "1.4 pt"
        except Exception:
            pass

        try:
            if rel_type == RelationshipType.INHERITANCE:
                # Solid line, hollow/closed triangle at end (target)
                connector.CellsU("LinePattern").FormulaU = "1"
                connector.CellsU("EndArrow").FormulaU = "13"
                connector.CellsU("EndArrowSize").FormulaU = "2"
                connector.CellsU("BeginArrow").FormulaU = "0"

            elif rel_type == RelationshipType.REALIZATION:
                # Dashed line, hollow triangle at end
                connector.CellsU("LinePattern").FormulaU = "2"
                connector.CellsU("EndArrow").FormulaU = "13"
                connector.CellsU("EndArrowSize").FormulaU = "2"
                connector.CellsU("BeginArrow").FormulaU = "0"

            elif rel_type == RelationshipType.COMPOSITION:
                # Solid line, filled diamond at begin (source)
                connector.CellsU("LinePattern").FormulaU = "1"
                connector.CellsU("BeginArrow").FormulaU = "20"
                connector.CellsU("BeginArrowSize").FormulaU = "2"
                connector.CellsU("EndArrow").FormulaU = "0"

            elif rel_type == RelationshipType.AGGREGATION:
                # Solid line, hollow diamond at begin (source)
                connector.CellsU("LinePattern").FormulaU = "1"
                connector.CellsU("BeginArrow").FormulaU = "21"
                connector.CellsU("BeginArrowSize").FormulaU = "2"
                connector.CellsU("EndArrow").FormulaU = "0"

            elif rel_type == RelationshipType.DEPENDENCY:
                # Dashed line with open arrow at end
                connector.CellsU("LinePattern").FormulaU = "2"
                connector.CellsU("EndArrow").FormulaU = "1"
                connector.CellsU("EndArrowSize").FormulaU = "2"
                connector.CellsU("BeginArrow").FormulaU = "0"

            elif rel_type == RelationshipType.DASHED_LINK:
                connector.CellsU("LinePattern").FormulaU = "2"
                connector.CellsU("EndArrow").FormulaU = "0"
                connector.CellsU("BeginArrow").FormulaU = "0"

            elif rel_type == RelationshipType.SOLID_LINK:
                connector.CellsU("LinePattern").FormulaU = "1"
                connector.CellsU("EndArrow").FormulaU = "0"
                connector.CellsU("BeginArrow").FormulaU = "0"

            else:  # ASSOCIATION (default)
                connector.CellsU("LinePattern").FormulaU = "1"
                connector.CellsU("EndArrow").FormulaU = "1"
                connector.CellsU("EndArrowSize").FormulaU = "2"
                connector.CellsU("BeginArrow").FormulaU = "0"

        except Exception:
            pass
