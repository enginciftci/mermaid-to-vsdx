"""
Mermaid Sequence Diagram Parser.
Parses sequence diagrams into SequenceDiagram AST models.
"""

import re
from typing import List, Optional
from .ast_nodes import (
    SequenceDiagram,
    Participant,
    ParticipantBox,
    Message,
    Note,
    MessageArrow,
    Activation,
    LoopBlock,
    ElseBranch,
)
from .base_parser import MermaidParseError, preprocess_lines
from ..utils.unicode_helper import clean_label_text, ensure_utf8


class SequenceParser:
    """
    Parses Mermaid sequence diagram code into a SequenceDiagram AST.
    """

    ARROW_MAPPING = [
        ("-->>", MessageArrow.DOTTED_ARROW),
        ("->>", MessageArrow.SOLID_ARROW),
        ("--x", MessageArrow.DOTTED_CROSS),
        ("-x", MessageArrow.SOLID_CROSS),
        ("--)", MessageArrow.DOTTED_OPEN),
        ("-)", MessageArrow.SOLID_OPEN),
        ("-->", MessageArrow.DOTTED_LINE),
        ("->", MessageArrow.SOLID_LINE),
    ]

    def __init__(self):
        self.diagram = SequenceDiagram()
        self.participant_order: List[str] = []
        self.block_stack: List[LoopBlock] = []
        self.active_box: Optional[ParticipantBox] = None

    def parse(self, text: str) -> SequenceDiagram:
        text = ensure_utf8(text)
        raw_lines = preprocess_lines(text)
        if not raw_lines:
            raise MermaidParseError("Empty sequence diagram input", 1, "")

        first_line_num, first_line = raw_lines[0]
        if not re.match(r'^sequenceDiagram\b', first_line, re.IGNORECASE):
            raise MermaidParseError(f"Expected 'sequenceDiagram' header, got '{first_line}'", first_line_num, first_line)

        self.diagram = SequenceDiagram()
        self.participant_order = []
        self.block_stack = []
        self.active_box = None

        for line_num, line in raw_lines[1:]:
            self._parse_line(line, line_num)

        return self.diagram

    def _parse_line(self, line: str, line_num: int):
        line = line.strip()

        # Check title
        if line.lower().startswith("title"):
            title_text = line[len("title"):].lstrip(":").strip()
            self.diagram.title = clean_label_text(title_text)
            return

        # Check autonumber
        if re.match(r'^autonumber\b', line, re.IGNORECASE):
            self.diagram.autonumber = True
            return

        # Check box start: box [color] [title]
        m_box = re.match(r'^box\b(?:\s+(.*))?$', line, re.IGNORECASE)
        if m_box:
            rest = (m_box.group(1) or "").strip()
            box_color = ""
            box_title = ""
            if rest:
                m_rgb = re.match(r'^(rgba?\s*\([^)]+\)|#[0-9a-fA-F]{3,8}|transparent)\b\s*(.*)$', rest, re.IGNORECASE)
                if m_rgb:
                    box_color = m_rgb.group(1).strip()
                    box_title = clean_label_text(m_rgb.group(2).strip())
                else:
                    parts = rest.split(None, 1)
                    known_colors = {
                        "aqua", "black", "blue", "fuchsia", "gray", "grey", "green",
                        "lime", "maroon", "navy", "olive", "orange", "purple", "red",
                        "silver", "teal", "white", "yellow", "lightblue", "lightgreen",
                        "lightgray", "lightgrey", "pink", "cyan", "magenta"
                    }
                    if parts[0].lower() in known_colors:
                        box_color = parts[0]
                        box_title = clean_label_text(parts[1]) if len(parts) > 1 else ""
                    else:
                        box_title = clean_label_text(rest)
            box_obj = ParticipantBox(title=box_title, color=box_color)
            self.diagram.boxes.append(box_obj)
            self.active_box = box_obj
            return

        if re.match(r'^destroy\s+', line, re.IGNORECASE):
            return

        # Check participant or actor
        # participant A as Alice [Turkish Text]
        # actor B as Bob
        m_part = re.match(r'^(?:create\s+)?(participant|actor)\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)(\s+as\s+(.+))?$', line, re.IGNORECASE)
        if m_part:
            is_actor = m_part.group(1).lower() == "actor"
            part_id = m_part.group(2)
            label_raw = m_part.group(4)
            label = clean_label_text(label_raw) if label_raw else part_id
            self._add_participant(part_id, label, is_actor)
            return

        # Check activate / deactivate standalone
        m_act = re.match(r'^(activate|deactivate)\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)$', line, re.IGNORECASE)
        if m_act:
            action = m_act.group(1).lower()
            part_id = m_act.group(2)
            self._ensure_participant_exists(part_id)
            self._add_item(Activation(
                participant_id=part_id,
                is_activate=(action == "activate")
            ))
            return

        # Check Note
        # Note [left of|right of|over] Actor[,Actor2]: Text
        m_note = re.match(r'^note\s+(left\s+of|right\s+of|over)\s+([^:]+):(.*)$', line, re.IGNORECASE)
        if m_note:
            placement = m_note.group(1).lower().strip()
            actors = [a.strip() for a in m_note.group(2).split(",")]
            note_text = clean_label_text(m_note.group(3))

            for a in actors:
                self._ensure_participant_exists(a)

            self._add_item(Note(
                placement=placement,
                participant_ids=actors,
                text=note_text
            ))
            return

        # Check Block start (loop, alt, opt, par, critical, break, rect)
        m_block = re.match(r'^(loop|alt|opt|par|critical|break|rect)\b(?:\s+(.*))?$', line, re.IGNORECASE)
        if m_block:
            b_type = m_block.group(1).lower()
            b_title = clean_label_text(m_block.group(2) or "")
            blk = LoopBlock(title=b_title, block_type=b_type)
            self._add_item(blk)
            self.block_stack.append(blk)
            return

        # Check Block or Box end
        if re.match(r'^end\b', line, re.IGNORECASE):
            if self.block_stack:
                self.block_stack.pop()
            elif self.active_box is not None:
                self.active_box = None
            return

        # Check divider / else / and / option inside block
        m_else = re.match(r'^(else|and|option)\b(?:\s+(.*))?$', line, re.IGNORECASE)
        if m_else:
            if self.block_stack:
                br_type = m_else.group(1).lower()
                br_title = clean_label_text(m_else.group(2) or "")
                self.block_stack[-1].else_branches.append(
                    ElseBranch(title=br_title, branch_type=br_type)
                )
            return

        # Check Message
        # Sender ->> Receiver: Message Text
        # Also handles activate/deactivate modifiers: + / -
        if ":" in line:
            for arrow_str, arrow_enum in self.ARROW_MAPPING:
                if arrow_str in line:
                    idx_arrow = line.find(arrow_str)
                    idx_colon = line.find(":", idx_arrow)
                    if idx_colon != -1:
                        sender_raw = line[:idx_arrow].strip()
                        receiver_raw = line[idx_arrow + len(arrow_str):idx_colon].strip()
                        text_raw = line[idx_colon + 1:].strip()

                        activate = False
                        deactivate = False

                        if receiver_raw.startswith("+"):
                            activate = True
                            receiver_raw = receiver_raw[1:].strip()
                        elif receiver_raw.startswith("-"):
                            deactivate = True
                            receiver_raw = receiver_raw[1:].strip()

                        if receiver_raw.endswith("+"):
                            activate = True
                            receiver_raw = receiver_raw[:-1].strip()
                        elif receiver_raw.endswith("-"):
                            deactivate = True
                            receiver_raw = receiver_raw[:-1].strip()

                        self._ensure_participant_exists(sender_raw)
                        self._ensure_participant_exists(receiver_raw)

                        self._add_item(Message(
                            sender_id=sender_raw,
                            receiver_id=receiver_raw,
                            text=clean_label_text(text_raw),
                            arrow_type=arrow_enum,
                            activate=activate,
                            deactivate=deactivate
                        ))
                        return

        raise MermaidParseError(f"Unrecognized sequence diagram statement: '{line}'", line_num, line)

    def _add_item(self, item):
        if self.block_stack:
            active_loop = self.block_stack[-1]
            if active_loop.else_branches:
                active_loop.else_branches[-1].items.append(item)
            else:
                active_loop.items.append(item)
        else:
            self.diagram.items.append(item)

    def _add_participant(self, part_id: str, label: str, is_actor: bool = False):
        if self.active_box is not None and part_id not in self.active_box.participant_ids:
            self.active_box.participant_ids.append(part_id)
        for p in self.diagram.participants:
            if p.id == part_id:
                p.label = label
                p.is_actor = is_actor
                return
        self.diagram.participants.append(Participant(id=part_id, label=label, is_actor=is_actor))
        self.participant_order.append(part_id)

    def _ensure_participant_exists(self, part_id: str):
        for p in self.diagram.participants:
            if p.id == part_id:
                return
        self._add_participant(part_id, part_id)
