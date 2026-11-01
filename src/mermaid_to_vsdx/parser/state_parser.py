"""
Parser for Mermaid State Diagrams (stateDiagram and stateDiagram-v2).
Converts Mermaid text into a StateDiagram AST.
"""

import re
from typing import Dict, List, Optional, Set, Any
from .ast_nodes import StateDiagram, StateNode, StateTransition, StateNodeType, StateNote
from .base_parser import preprocess_lines, MermaidParseError
from ..utils.unicode_helper import clean_label_text


class StateParser:
    """
    Parses Mermaid state diagrams into a structured StateDiagram AST.
    Supports [*] initial/terminal states, state descriptions, aliases,
    composite states, <<choice>>, <<fork>>, <<join>>, notes, and labeled transitions.
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

        composite_stack: List[str] = []
        top_level_states: Set[str] = set()
        notes: List[StateNote] = []
        initial_counter = 1
        terminal_counter = 1

        in_multiline_note: Optional[Tuple[str, str, List[str]]] = None

        def _attach_to_composite(sid: str, force: bool = False):
            if not composite_stack:
                top_level_states.add(sid)
                return
            parent_cid = composite_stack[-1]
            if sid == parent_cid:
                return
            if not force and sid in top_level_states:
                return
            top_level_states.discard(sid)
            st_obj = states.get(sid)
            if st_obj is None:
                return
            if st_obj.parent_id is None or force:
                st_obj.parent_id = parent_cid
            if sid not in states[parent_cid].children:
                states[parent_cid].children.append(sid)

        for line_num, line in lines[1:]:
            line_str = line.strip()
            if not line_str or line_str.startswith("%%"):
                continue

            if in_multiline_note is not None:
                if line_str.lower() == "end note":
                    placement, st_id, buf = in_multiline_note
                    notes.append(StateNote(
                        placement=placement,
                        state_id=st_id,
                        text=clean_label_text(" ".join(buf)),
                    ))
                    in_multiline_note = None
                else:
                    in_multiline_note[2].append(line_str)
                continue

            # Composite state closing: }
            if line_str == "}":
                if composite_stack:
                    composite_stack.pop()
                continue

            # Direction directive
            dir_match = re.match(r"^direction\s+(TB|TD|LR|RL|BT)$", line_str, re.IGNORECASE)
            if dir_match:
                d = dir_match.group(1).upper()
                direction = "TD" if d == "TB" else d
                continue

            # Single-line Note: note [left of|right of] StateId : text
            note_match = re.match(r'^note\s+(left\s+of|right\s+of)\s+([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_str, re.IGNORECASE)
            if note_match:
                notes.append(StateNote(
                    placement=note_match.group(1).lower().strip(),
                    state_id=note_match.group(2).strip(),
                    text=clean_label_text(note_match.group(3))
                ))
                continue

            # Multi-line Note opening: note [left of|right of] StateId
            note_open_match = re.match(r'^note\s+(left\s+of|right\s+of)\s+([A-Za-z0-9_\-]+)$', line_str, re.IGNORECASE)
            if note_open_match:
                in_multiline_note = (
                    note_open_match.group(1).lower().strip(),
                    note_open_match.group(2).strip(),
                    [],
                )
                continue

            if line_str.lower().startswith("note ") or line_str.lower() == "end note":
                continue

            # Composite state opening with alias: state "Label Here" as StateName {
            comp_alias_match = re.match(r'^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_\-]+)\s*\{$', line_str, re.IGNORECASE)
            if comp_alias_match:
                lbl, cid = comp_alias_match.group(1), comp_alias_match.group(2).strip()
                if cid not in states:
                    states[cid] = StateNode(id=cid, label=clean_label_text(lbl), node_type=StateNodeType.STATE)
                else:
                    states[cid].label = clean_label_text(lbl)
                _attach_to_composite(cid, force=True)
                composite_stack.append(cid)
                continue

            # Composite state opening: state StateName {
            comp_match = re.match(r'^state\s+([A-Za-z0-9_\-]+)\s*\{$', line_str, re.IGNORECASE)
            if comp_match:
                cid = comp_match.group(1).strip()
                if cid not in states:
                    states[cid] = StateNode(id=cid, label=clean_label_text(cid), node_type=StateNodeType.STATE)
                _attach_to_composite(cid, force=True)
                composite_stack.append(cid)
                continue

            # State definition with alias: state "Label Here" as s1
            alias_match = re.match(r'^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_\-]+)$', line_str, re.IGNORECASE)
            if alias_match:
                lbl, sid = alias_match.group(1), alias_match.group(2)
                if sid not in states:
                    states[sid] = StateNode(id=sid, label=clean_label_text(lbl), node_type=StateNodeType.STATE)
                else:
                    states[sid].label = clean_label_text(lbl)
                _attach_to_composite(sid, force=True)
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
                _attach_to_composite(sid, force=True)
                continue

            # State description: StateName : Description
            desc_match = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_str)
            if desc_match and "-->" not in line_str:
                sid, desc = desc_match.group(1), desc_match.group(2).strip()
                if sid in states:
                    states[sid].description = clean_label_text(desc)
                else:
                    states[sid] = StateNode(id=sid, label=clean_label_text(sid), description=clean_label_text(desc))
                _attach_to_composite(sid, force=True)
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
                    _attach_to_composite(src_id, force=True)
                else:
                    src_id = src_raw
                    is_new_src = src_id not in states
                    if is_new_src:
                        states[src_id] = StateNode(id=src_id, label=clean_label_text(src_id))
                    _attach_to_composite(src_id, force=is_new_src)

                # Resolve target
                if dst_raw == "[*]":
                    dst_id = f"__end_{terminal_counter}__"
                    terminal_counter += 1
                    states[dst_id] = StateNode(id=dst_id, label="", node_type=StateNodeType.TERMINAL)
                    _attach_to_composite(dst_id, force=True)
                else:
                    dst_id = dst_raw
                    is_new_dst = dst_id not in states
                    if is_new_dst:
                        states[dst_id] = StateNode(id=dst_id, label=clean_label_text(dst_id))
                    _attach_to_composite(dst_id, force=is_new_dst)

                transitions.append(StateTransition(
                    source_id=src_id,
                    target_id=dst_id,
                    event=event_text
                ))
                continue

        return StateDiagram(direction=direction, states=states, transitions=transitions, notes=notes)
