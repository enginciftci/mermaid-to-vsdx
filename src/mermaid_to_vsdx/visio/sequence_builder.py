"""
Sequence Diagram Drawing Engine for Microsoft Visio.
Translates SequenceDiagram AST into native .vsdx drawings with
lifelines, message connectors, activations, and note boxes.
"""

import os
from typing import Dict, List, Optional
from .com_client import VisioSession
from .palettes import PaletteTheme, get_palette
from .shapes import style_shape, format_shape_text
from ..parser.ast_nodes import SequenceDiagram, Participant, Message, Note, MessageArrow, LoopBlock
from ..utils.unicode_helper import DEFAULT_FONT


class SequenceBuilder:
    """
    Builds a Visio sequence diagram from a SequenceDiagram AST.
    """

    def __init__(
        self,
        diagram: SequenceDiagram,
        palette: Optional[PaletteTheme] = None,
        font_name: str = DEFAULT_FONT
    ):
        self.diagram = diagram
        self.palette = palette or get_palette()
        self.font_name = font_name
        self.participant_x: Dict[str, float] = {}

    def build_and_save(self, output_vsdx_path: str) -> str:
        """
        Creates the Visio sequence diagram and saves to .vsdx.
        """
        abs_output_path = os.path.abspath(output_vsdx_path)
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)

        with VisioSession(visible=False) as visio_app:
            doc = visio_app.Documents.Add("")
            page = doc.Pages.Item(1)

            participants = self.diagram.participants
            items = self.diagram.items

            if not participants:
                # Add default participant if none were registered
                participants = [Participant(id="actor", label="Aktör")]

            col_spacing = 2.6  # inches between lifelines
            start_x = 1.8
            y_top = 10.5
            box_w = 1.9
            box_h = 0.7
            row_spacing = 0.85

            # Calculate total vertical height
            total_items = max(len(items), 1)
            y_bottom = y_top - box_h - (total_items + 1) * row_spacing

            # 1. Draw Title if present
            if self.diagram.title:
                title_shape = page.DrawRectangle(start_x, y_top + 0.3, start_x + 6.0, y_top + 0.9)
                style_shape(
                    title_shape,
                    fill_rgb=self.palette.background,
                    border_rgb=self.palette.background,
                    line_weight_pt=0,
                    rounding_in=0
                )
                format_shape_text(
                    title_shape,
                    self.diagram.title,
                    font_name=self.font_name,
                    font_size_pt=14,
                    font_color_rgb=self.palette.default_text,
                    bold=True,
                    visio_app=visio_app
                )

            # 2. Draw Lifelines and Header/Footer boxes for participants
            for i, p in enumerate(participants):
                px = start_x + i * col_spacing
                self.participant_x[p.id] = px

                # Top participant box
                top_box = page.DrawRectangle(px - box_w / 2.0, y_top - box_h, px + box_w / 2.0, y_top)
                style_shape(
                    top_box,
                    fill_rgb=self.palette.default_fill,
                    border_rgb=self.palette.default_border,
                    line_weight_pt=1.5,
                    rounding_in=0.1
                )
                format_shape_text(
                    top_box,
                    p.label,
                    font_name=self.font_name,
                    font_size_pt=10,
                    font_color_rgb=self.palette.default_text,
                    bold=True,
                    visio_app=visio_app
                )

                # Vertical dashed lifeline
                lifeline = page.DrawLine(px, y_top - box_h, px, y_bottom + box_h)
                try:
                    lifeline.CellsU("LineColor").FormulaU = self.palette.subgraph_border
                    lifeline.CellsU("LineWeight").FormulaU = "1.0 pt"
                    lifeline.CellsU("LinePattern").FormulaU = "2"  # Dashed line
                    lifeline.SendToBack()
                except Exception:
                    pass

                # Bottom participant box
                bottom_box = page.DrawRectangle(px - box_w / 2.0, y_bottom, px + box_w / 2.0, y_bottom + box_h)
                style_shape(
                    bottom_box,
                    fill_rgb=self.palette.default_fill,
                    border_rgb=self.palette.default_border,
                    line_weight_pt=1.5,
                    rounding_in=0.1
                )
                format_shape_text(
                    bottom_box,
                    p.label,
                    font_name=self.font_name,
                    font_size_pt=10,
                    font_color_rgb=self.palette.default_text,
                    bold=True,
                    visio_app=visio_app
                )

            # 3. Draw Messages, Notes, and Loops recursively
            y_curr = y_top - box_h - 0.6

            def draw_items(item_list):
                nonlocal y_curr
                for item in item_list:
                    if isinstance(item, LoopBlock):
                        loop_top = y_curr + 0.15
                        y_curr -= 0.38

                        from ..compiler.sequence_compiler import _collect_pids
                        pids = _collect_pids(item)
                        coords = [self.participant_x[p] for p in pids if p in self.participant_x]
                        if not coords:
                            coords = list(self.participant_x.values()) if self.participant_x else [start_x]

                        has_self = any(isinstance(c, Message) and c.sender_id == c.receiver_id for c in item.items)
                        lx = min(coords) - 0.45
                        rx = max(coords) + (1.1 if has_self else 0.45)

                        draw_items(item.items)

                        loop_bottom = y_curr + 0.15
                        y_curr -= 0.25

                        # Draw dashed container frame
                        frame = page.DrawRectangle(lx, loop_bottom, rx, loop_top)
                        try:
                            frame.CellsU("FillPattern").FormulaU = "0"
                            frame.CellsU("LinePattern").FormulaU = "2"
                            frame.CellsU("LineColor").FormulaU = self.palette.subgraph_border
                            frame.CellsU("LineWeight").FormulaU = "1.2 pt"
                            frame.SendToBack()
                        except Exception:
                            pass

                        # Draw header badge
                        b_text = f"loop [{item.title}]" if item.title else item.block_type
                        badge_w = max(1.1, len(b_text) * 0.085 + 0.35)
                        badge_h = 0.26
                        badge = page.DrawRectangle(lx, loop_top - badge_h, lx + badge_w, loop_top)
                        style_shape(
                            badge,
                            fill_rgb="#f1f5f9",
                            border_rgb=self.palette.subgraph_border,
                            line_weight_pt=1.0,
                            rounding_in=0.04
                        )
                        format_shape_text(
                            badge, b_text,
                            font_name=self.font_name, font_size_pt=8.5,
                            font_color_rgb=self.palette.subgraph_text,
                            bold=True, visio_app=visio_app
                        )

                    elif isinstance(item, Message):
                        x_from = self.participant_x.get(item.sender_id, start_x)
                        x_to = self.participant_x.get(item.receiver_id, start_x + col_spacing)

                        # Check for self-message
                        if item.sender_id == item.receiver_id:
                            px = x_from
                            line_w = 0.75
                            line_h = 0.40
                            l1 = page.DrawLine(px, y_curr, px + line_w, y_curr)
                            l2 = page.DrawLine(px + line_w, y_curr, px + line_w, y_curr - line_h)
                            l3 = page.DrawLine(px + line_w, y_curr - line_h, px, y_curr - line_h)
                            for seg in (l1, l2, l3):
                                try:
                                    seg.CellsU("LineColor").FormulaU = self.palette.connector_line
                                    seg.CellsU("LineWeight").FormulaU = "1.4 pt"
                                    if item.arrow_type in (MessageArrow.DOTTED_ARROW, MessageArrow.DOTTED_LINE, MessageArrow.DOTTED_CROSS):
                                        seg.CellsU("LinePattern").FormulaU = "2"
                                    else:
                                        seg.CellsU("LinePattern").FormulaU = "1"
                                except Exception:
                                    pass
                            try:
                                l3.CellsU("EndArrow").FormulaU = "13"
                                l3.CellsU("EndArrowSize").FormulaU = "2"
                            except Exception:
                                pass

                            if item.text:
                                txt_box = page.DrawRectangle(px, y_curr + 0.05, px + 2.0, y_curr + 0.35)
                                try:
                                    txt_box.CellsU("LinePattern").FormulaU = "0"
                                    txt_box.CellsU("FillPattern").FormulaU = "0"
                                except Exception:
                                    pass
                                format_shape_text(
                                    txt_box, item.text,
                                    font_name=self.font_name, font_size_pt=9,
                                    font_color_rgb=self.palette.connector_text,
                                    bold=False, visio_app=visio_app
                                )

                            y_curr -= (line_h + row_spacing * 0.75)
                            continue

                        # Normal message between two lifelines
                        x_left = min(x_from, x_to)
                        x_right = max(x_from, x_to)
                        is_forward = (x_to >= x_from)

                        msg_line = page.DrawLine(x_left, y_curr, x_right, y_curr)
                        try:
                            msg_line.CellsU("LineColor").FormulaU = self.palette.connector_line
                            msg_line.CellsU("LineWeight").FormulaU = "1.4 pt"

                            # Ensure text is never inverted
                            msg_line.CellsU("TxtAngle").FormulaU = "0 deg"
                            msg_line.CellsU("TxtPinY").FormulaU = "Height*0.5 + 8 pt"

                            # Line style (solid vs dotted)
                            if item.arrow_type in (MessageArrow.DOTTED_ARROW, MessageArrow.DOTTED_LINE, MessageArrow.DOTTED_CROSS):
                                msg_line.CellsU("LinePattern").FormulaU = "2"  # Dashed
                            else:
                                msg_line.CellsU("LinePattern").FormulaU = "1"  # Solid

                            # Arrowhead placement based on flow direction
                            has_arrow = item.arrow_type in (
                                MessageArrow.SOLID_ARROW, MessageArrow.DOTTED_ARROW,
                                MessageArrow.SOLID_OPEN, MessageArrow.DOTTED_OPEN
                            )
                            if has_arrow:
                                if is_forward:
                                    msg_line.CellsU("EndArrow").FormulaU = "13"
                                    msg_line.CellsU("EndArrowSize").FormulaU = "2"
                                    msg_line.CellsU("BeginArrow").FormulaU = "0"
                                else:
                                    msg_line.CellsU("BeginArrow").FormulaU = "13"
                                    msg_line.CellsU("BeginArrowSize").FormulaU = "2"
                                    msg_line.CellsU("EndArrow").FormulaU = "0"
                            else:
                                msg_line.CellsU("EndArrow").FormulaU = "0"
                                msg_line.CellsU("BeginArrow").FormulaU = "0"
                        except Exception:
                            pass

                        # Label text
                        if item.text:
                            format_shape_text(
                                msg_line,
                                item.text,
                                font_name=self.font_name,
                                font_size_pt=9,
                                font_color_rgb=self.palette.connector_text,
                                bold=False,
                                visio_app=visio_app
                            )
                            try:
                                msg_line.CellsU("FillForegnd").FormulaU = "RGB(255, 255, 255)"
                                msg_line.CellsU("FillPattern").FormulaU = "1"
                            except Exception:
                                pass

                        y_curr -= row_spacing

                    elif isinstance(item, Note):
                        participant_coords = [self.participant_x[p] for p in item.participant_ids if p in self.participant_x]
                        if not participant_coords:
                            participant_coords = [start_x]

                        if len(participant_coords) == 1:
                            cx = participant_coords[0]
                            if "left" in item.placement:
                                cx -= (col_spacing * 0.4)
                            elif "right" in item.placement:
                                cx += (col_spacing * 0.4)
                            nw = 2.0
                            nh = 0.5
                            note_shape = page.DrawRectangle(cx - nw / 2.0, y_curr - nh / 2.0, cx + nw / 2.0, y_curr + nh / 2.0)
                        else:
                            min_px = min(participant_coords)
                            max_px = max(participant_coords)
                            nh = 0.55
                            note_shape = page.DrawRectangle(min_px - 0.4, y_curr - nh / 2.0, max_px + 0.4, y_curr + nh / 2.0)

                        style_shape(
                            note_shape,
                            fill_rgb=self.palette.note_fill,
                            border_rgb=self.palette.note_border,
                            line_weight_pt=1.0,
                            rounding_in=0.06
                        )
                        format_shape_text(
                            note_shape,
                            item.text,
                            font_name=self.font_name,
                            font_size_pt=9,
                            font_color_rgb=self.palette.note_text,
                            bold=False,
                            visio_app=visio_app
                        )
                        y_curr -= row_spacing

            draw_items(items)

            # Fit page to contents
            try:
                page.ResizeToFitContents()
            except Exception:
                pass

            doc.SaveAs(abs_output_path)
            doc.Saved = True
            doc.Close()

        return abs_output_path
