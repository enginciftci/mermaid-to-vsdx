"""
Mermaid Sequence Diagram Parser.
Parses sequence diagrams into SequenceDiagram AST models.
"""

import re
from typing import List, Optional
from .ast_nodes import (
    SequenceDiagram, Participant, Message, Note, MessageArrow, Activation, LoopBlock
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
        if line.lower() == "autonumber":
            return

        # Check participant or actor
        # participant A as Alice [Turkish Text]
        # actor B as Bob
        m_part = re.match(r'^(participant|actor)\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)(\s+as\s+(.+))?$', line, re.IGNORECASE)
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

        # Check Block start (loop, alt, opt, par, critical, rect)
        m_block = re.match(r'^(loop|alt|opt|par|critical|rect)(\s+(.*))?$', line, re.IGNORECASE)
        if m_block:
            b_type = m_block.group(1).lower()
            b_title = clean_label_text(m_block.group(3) or "")
            blk = LoopBlock(title=b_title, block_type=b_type)
            self._add_item(blk)
            self.block_stack.append(blk)
            return

        # Check Block end
        if re.match(r'^end\b', line, re.IGNORECASE):
            if self.block_stack:
                self.block_stack.pop()
            return

        # Check divider / else
        if re.match(r'^else\b', line, re.IGNORECASE):
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
            self.block_stack[-1].items.append(item)
        else:
            self.diagram.items.append(item)

    def _add_participant(self, part_id: str, label: str, is_actor: bool = False):
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
