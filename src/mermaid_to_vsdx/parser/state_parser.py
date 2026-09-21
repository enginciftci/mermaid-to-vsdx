"""
Parser for Mermaid State Diagrams (stateDiagram and stateDiagram-v2).
Converts Mermaid text into a StateDiagram AST.
"""

import re
from typing import Dict, List, Optional
from .ast_nodes import StateDiagram, StateNode, StateTransition, StateNodeType
from .base_parser import preprocess_lines, MermaidParseError
from ..utils.unicode_helper import clean_label_text


class StateParser:
    """
    Parses Mermaid state diagrams into a structured StateDiagram AST.
    Supports [*] initial/terminal states, state descriptions, aliases,
    <<choice>>, <<fork>>, <<join>>, and labeled transitions.
    """

    def parse(self, mermaid_code: str) -> StateDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty state diagram input.")

        # Validate header
        first_line_num, first_line = lines[0]
        first_clean = first_line.strip().lower()
        if not (first_clean.startswith("statediagram") or first_clean.startswith("statediagram-v2")):
            raise MermaidParseError(
                "State diagram must begin with 'stateDiagram' or 'stateDiagram-v2'",
                first_line_num,
                first_line
            )

        direction = "TD"
        states: Dict[str, StateNode] = {}
        transitions: List[StateTransition] = []

        current_composite = None
        notes: List[Any] = []
        initial_counter = 1
        terminal_counter = 1

        for line_num, line in lines[1:]:
            line_str = line.strip()
            if not line_str or line_str.startswith("%%"):
                continue

            # Composite state closing: }
            if line_str == "}":
                current_composite = None
                continue

            # Direction directive
            dir_match = re.match(r"^direction\s+(TB|TD|LR|RL|BT)$", line_str, re.IGNORECASE)
            if dir_match:
                d = dir_match.group(1).upper()
                direction = "TD" if d == "TB" else d
                continue

            # Note line: note [left of|right of] StateId : text
            note_match = re.match(r'^note\s+(left\s+of|right\s+of)\s+([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_str, re.IGNORECASE)
            if note_match:
                from .ast_nodes import StateNote
                notes.append(StateNote(
                    placement=note_match.group(1).lower().strip(),
                    state_id=note_match.group(2).strip(),
                    text=clean_label_text(note_match.group(3))
                ))
                continue

            # Note blocks
            if line_str.lower().startswith("note ") or line_str.lower() == "end note":
                continue

            # Composite state opening: state StateName {
            comp_match = re.match(r'^state\s+([A-Za-z0-9_\-]+)\s*\{$', line_str, re.IGNORECASE)
            if comp_match:
                cid = comp_match.group(1).strip()
                if cid not in states:
                    states[cid] = StateNode(id=cid, label=clean_label_text(cid), node_type=StateNodeType.STATE)
                current_composite = cid
                continue

            # State definition with alias: state "Label Here" as s1
            alias_match = re.match(r'^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_\-]+)', line_str, re.IGNORECASE)
            if alias_match:
                lbl, sid = alias_match.group(1), alias_match.group(2)
                states[sid] = StateNode(id=sid, label=clean_label_text(lbl), node_type=StateNodeType.STATE)
                continue

            # Special states: state s1 <<choice>>, <<fork>>, <<join>>
            special_match = re.match(r'^state\s+([A-Za-z0-9_\-]+)\s+<<(choice|fork|join)>>', line_str, re.IGNORECASE)
            if special_match:
                sid, stype_str = special_match.group(1), special_match.group(2).lower()
                stype = (
                    StateNodeType.CHOICE
                    if stype_str == "choice"
                    else (StateNodeType.FORK if stype_str == "fork" else StateNodeType.JOIN)
                )
                states[sid] = StateNode(id=sid, label=clean_label_text(sid), node_type=stype)
                continue

            # State description: StateName : Description
            desc_match = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_str)
            if desc_match and "-->" not in line_str:
                sid, desc = desc_match.group(1), desc_match.group(2).strip()
                if sid in states:
                    states[sid].description = clean_label_text(desc)
                else:
                    states[sid] = StateNode(id=sid, label=clean_label_text(sid), description=clean_label_text(desc))
                continue

            # Transition: Source --> Target [: Event]
            trans_match = re.match(
                r'^(\[\*\]|[A-Za-z0-9_\-]+)\s*-->\s*(\[\*\]|[A-Za-z0-9_\-]+)(?:\s*:\s*(.*))?$',
                line_str
            )
            if trans_match:
                src_raw = trans_match.group(1).strip()
                dst_raw = trans_match.group(2).strip()
                event_raw = trans_match.group(3) or ""
                event_text = clean_label_text(event_raw.strip())

                # Resolve source
                if src_raw == "[*]":
                    src_id = f"__start_{initial_counter}__"
                    initial_counter += 1
                    states[src_id] = StateNode(id=src_id, label="", node_type=StateNodeType.INITIAL)
                else:
                    src_id = src_raw
                    if src_id not in states:
                        states[src_id] = StateNode(id=src_id, label=clean_label_text(src_id))

                # Resolve target
                if dst_raw == "[*]":
                    dst_id = f"__end_{terminal_counter}__"
                    terminal_counter += 1
                    states[dst_id] = StateNode(id=dst_id, label="", node_type=StateNodeType.TERMINAL)
                else:
                    dst_id = dst_raw
                    if dst_id not in states:
                        states[dst_id] = StateNode(id=dst_id, label=clean_label_text(dst_id))

                transitions.append(StateTransition(
                    source_id=src_id,
                    target_id=dst_id,
                    event=event_text
                ))
                continue

        return StateDiagram(direction=direction, states=states, transitions=transitions, notes=notes)
