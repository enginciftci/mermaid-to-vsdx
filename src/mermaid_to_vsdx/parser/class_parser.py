"""
Parser for Mermaid Class Diagrams (classDiagram).
Parses classes, attributes, methods, annotations (<<interface>>), and UML relationships.
"""

import re
from typing import List, Optional, Tuple
from .ast_nodes import (
    ClassDiagram, ClassNode, ClassMember, ClassRelationship, RelationshipType
)
from .base_parser import MermaidParseError, preprocess_lines
from ..utils.unicode_helper import clean_label_text


RELATIONSHIP_MAP = [
    ("<|--", RelationshipType.INHERITANCE, True),
    ("--|>", RelationshipType.INHERITANCE, False),
    ("<|..", RelationshipType.REALIZATION, True),
    ("..|>", RelationshipType.REALIZATION, False),
    ("*--", RelationshipType.COMPOSITION, False),
    ("--*", RelationshipType.COMPOSITION, True),
    ("o--", RelationshipType.AGGREGATION, False),
    ("--o", RelationshipType.AGGREGATION, True),
    ("-->", RelationshipType.ASSOCIATION, False),
    ("<--", RelationshipType.ASSOCIATION, True),
    ("..>", RelationshipType.DEPENDENCY, False),
    ("<..", RelationshipType.DEPENDENCY, True),
    ("--", RelationshipType.SOLID_LINK, False),
    ("..", RelationshipType.DASHED_LINK, False),
]


class ClassParser:
    """
    Parses Mermaid classDiagram syntax into a ClassDiagram AST.
    """

    def __init__(self):
        self.diagram = ClassDiagram()
        self.current_class: Optional[ClassNode] = None

    def parse(self, code: str) -> ClassDiagram:
        self.diagram = ClassDiagram()
        self.current_class = None

        lines = preprocess_lines(code)
        if not lines:
            raise MermaidParseError("Empty class diagram input.")

        # Validate header
        first_line_num, first_line = lines[0]
        if not first_line.lower().startswith("classdiagram"):
            raise MermaidParseError(
                f"Expected 'classDiagram' header, found '{first_line}'",
                line_number=first_line_num,
                line_content=first_line
            )

        in_class_block = False

        for line_num, line in lines[1:]:
            # Check for block closing
            if line == "}":
                if not in_class_block:
                    raise MermaidParseError("Unexpected '}' without open class block", line_num, line)
                in_class_block = False
                self.current_class = None
                continue

            if in_class_block:
                self._parse_class_member(line, self.current_class)
                continue

            # Check direction: direction RL / LR / TB / BT
            m_dir = re.match(r'^direction\s+(TB|TD|LR|RL|BT)$', line, re.IGNORECASE)
            if m_dir:
                d = m_dir.group(1).upper()
                self.diagram.direction = "TD" if d == "TB" else d
                continue

            # Check for notes: note "text" or note for ClassName "text"
            m_note = re.match(r'^note\s+(?:for\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)\s+)?["\'](.*)["\']$', line, re.IGNORECASE)
            if m_note:
                target_cls = m_note.group(1)
                note_text = clean_label_text(m_note.group(2))
                from .ast_nodes import ClassNote
                self.diagram.notes.append(ClassNote(text=note_text, target_class=target_cls))
                continue

            # Check for class declaration with block: class Name["Label"] {
            m_block = re.match(r'^class\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)(?:\[(.*?)\])?\s*\{$', line)
            if m_block:
                c_name = m_block.group(1).strip()
                c_lbl = m_block.group(2)
                self.current_class = self._get_or_create_class(c_name)
                if c_lbl:
                    self.current_class.display_label = clean_label_text(c_lbl.strip('"\''))
                in_class_block = True
                continue

            # Check for standalone class declaration: class Name["Label"]
            m_simple = re.match(r'^class\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)(?:\[(.*?)\])?$', line)
            if m_simple:
                c_name = m_simple.group(1).strip()
                c_lbl = m_simple.group(2)
                cls_node = self._get_or_create_class(c_name)
                if c_lbl:
                    cls_node.display_label = clean_label_text(c_lbl.strip('"\''))
                continue

            # Check for annotation line: <<interface>> ClassName or class ClassName:::style
            m_ann = re.match(r'^(?:class\s+)?([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)\s*:::.*$', line)
            if m_ann:
                self._get_or_create_class(m_ann.group(1))
                continue

            m_ann_prefix = re.match(r'^<<([A-Za-z0-9_]+)>>\s+([A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+)$', line)
            if m_ann_prefix:
                ann = m_ann_prefix.group(1)
                c_name = m_ann_prefix.group(2)
                cls_node = self._get_or_create_class(c_name)
                cls_node.annotation = f"<<{ann}>>"
                continue

            # Check for inline member: ClassName : +type member or ClassName : +method()
            if " : " in line or line.find(":") > 0:
                parts = line.split(":", 1)
                potential_name = parts[0].strip()
                if re.match(r'^[A-Za-z0-9_\-ğüşıöçĞÜŞİÖÇ]+$', potential_name) and not any(op in line for op, _, _ in RELATIONSHIP_MAP[:12]):
                    cls_node = self._get_or_create_class(potential_name)
                    self._parse_class_member(parts[1].strip(), cls_node)
                    continue

            # Check for relationships
            if self._try_parse_relationship(line):
                continue

        return self.diagram

    def _get_or_create_class(self, name: str) -> ClassNode:
        name = clean_label_text(name).strip()
        if name not in self.diagram.classes:
            self.diagram.classes[name] = ClassNode(name=name)
        return self.diagram.classes[name]

    def _parse_class_member(self, line: str, cls_node: ClassNode):
        line = line.strip()
        if not line:
            return

        # Annotation inside block: <<interface>>
        if line.startswith("<<") and line.endswith(">>"):
            cls_node.annotation = line
            return

        visibility = "+"
        if line[0] in ("+", "-", "#", "~"):
            visibility = line[0]
            member_def = line[1:].strip()
        else:
            member_def = line

        is_method = "(" in member_def and ")" in member_def
        ret_type = ""
        params = ""

        if is_method:
            # e.g. deposit(amount) bool or getBalance()
            m_method = re.match(r'^(.*?)\((.*?)\)(?:\s*(.*))?$', member_def)
            if m_method:
                name = m_method.group(1).strip()
                params = m_method.group(2).strip()
                ret_type = (m_method.group(3) or "").strip()
            else:
                name = member_def
        else:
            # Attribute: e.g. String owner or owner String
            parts = member_def.split(None, 1)
            if len(parts) == 2:
                # Could be Type Name or Name Type
                ret_type = parts[0].strip()
                name = parts[1].strip()
            else:
                name = member_def

        cls_node.members.append(ClassMember(
            name=clean_label_text(name),
            visibility=visibility,
            is_method=is_method,
            return_type=clean_label_text(ret_type),
            parameters=clean_label_text(params)
        ))

    def _try_parse_relationship(self, line: str) -> bool:
        """
        Attempts to parse UML relationship like:
        Animal <|-- Dog
        Car *-- Engine : contains
        Driver "1" --> "*" Car : drives
        """
        # Extract optional label after colon: ... : label
        rel_label = ""
        if " : " in line:
            line_part, rel_label = line.split(" : ", 1)
            rel_label = clean_label_text(rel_label)
        elif line.count(":") == 1 and not line.startswith("class"):
            # check if colon is preceded by relationship
            p = line.split(":", 1)
            line_part = p[0].strip()
            rel_label = clean_label_text(p[1])
        else:
            line_part = line.strip()

        for op, rel_type, is_reversed in RELATIONSHIP_MAP:
            if op in line_part:
                parts = line_part.split(op, 1)
                left_raw = parts[0].strip()
                right_raw = parts[1].strip()

                # Extract optional multiplicities: ClassA "1" op "*" ClassB
                left_name, mult_left = self._extract_multiplicity(left_raw)
                right_name, mult_right = self._extract_multiplicity(right_raw)

                if left_name and right_name:
                    self._get_or_create_class(left_name)
                    self._get_or_create_class(right_name)

                    if is_reversed:
                        src = right_name
                        tgt = left_name
                        m_src = mult_right
                        m_tgt = mult_left
                    else:
                        src = left_name
                        tgt = right_name
                        m_src = mult_left
                        m_tgt = mult_right

                    self.diagram.relationships.append(ClassRelationship(
                        source_name=src,
                        target_name=tgt,
                        rel_type=rel_type,
                        label=rel_label,
                        multiplicity_source=m_src,
                        multiplicity_target=m_tgt
                    ))
                    return True
        return False

    def _extract_multiplicity(self, token: str) -> Tuple[str, str]:
        token = token.strip()
        m_mult = re.search(r'["\'](.*?)["\']', token)
        if m_mult:
            mult = m_mult.group(1).strip()
            name = re.sub(r'["\'].*?["\']', '', token).strip()
            return name, mult
        return token, ""
