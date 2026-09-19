"""
Parser for Mermaid Entity-Relationship Diagrams (erDiagram).
Converts Mermaid text into an ERDiagram AST.
"""

import re
from typing import Dict, List, Optional
from .ast_nodes import ERDiagram, EREntity, ERAttribute, ERRelationship
from .base_parser import preprocess_lines, MermaidParseError
from ..utils.unicode_helper import clean_label_text


class ERParser:
    """
    Parses Mermaid ER diagrams into a structured ERDiagram AST.
    Supports entity definitions with typed attributes (PK, FK) and cardinalities.
    """

    def parse(self, mermaid_code: str) -> ERDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty ER diagram input.")

        first_line_num, first_line = lines[0]
        if not first_line.strip().lower().startswith("erdiagram"):
            raise MermaidParseError("ER diagram must begin with 'erDiagram'", first_line_num, first_line)

        entities: Dict[str, EREntity] = {}
        relationships: List[ERRelationship] = []

        in_entity: Optional[str] = None
        title = ""

        # Relationship regex: ENTITY1 cardinality ENTITY2 : "role"
        # Cardinalities: ||--o{, ||--|{, }|..|{, |o--o|, etc.
        rel_pattern = re.compile(
            r'^([A-Za-z0-9_\-]+)\s+([|o}{]+[-.]+[|o}{]+)\s+([A-Za-z0-9_\-]+)(?:\s*:\s*"?([^"]*)"?)?$',
            re.IGNORECASE
        )

        for line_num, line in lines[1:]:
            line_str = line.strip()
            if not line_str or line_str.startswith("%%"):
                continue

            if in_entity:
                if line_str == "}":
                    in_entity = None
                    continue
                # Attribute line inside entity: type name [PK|FK] ["comment"]
                # e.g., string customerNumber PK "Unique ID"
                attr_parts = line_str.split()
                if len(attr_parts) >= 2:
                    a_type = attr_parts[0]
                    a_name = attr_parts[1]
                    is_pk = "PK" in [p.upper() for p in attr_parts[2:]]
                    is_fk = "FK" in [p.upper() for p in attr_parts[2:]]
                    entities[in_entity].attributes.append(ERAttribute(
                        name=clean_label_text(a_name),
                        attr_type=clean_label_text(a_type),
                        is_pk=is_pk,
                        is_fk=is_fk,
                    ))
                continue

            # Check entity start: ENTITY_NAME {
            ent_start_match = re.match(r'^([A-Za-z0-9_\-]+)\s*\{$', line_str)
            if ent_start_match:
                ename = ent_start_match.group(1)
                in_entity = ename
                if ename not in entities:
                    entities[ename] = EREntity(name=ename)
                continue

            # Check relationship
            rel_match = rel_pattern.match(line_str)
            if rel_match:
                e1 = rel_match.group(1).strip()
                card = rel_match.group(2).strip()
                e2 = rel_match.group(3).strip()
                role = rel_match.group(4) or ""

                if e1 not in entities:
                    entities[e1] = EREntity(name=e1)
                if e2 not in entities:
                    entities[e2] = EREntity(name=e2)

                relationships.append(ERRelationship(
                    entity1=e1,
                    entity2=e2,
                    cardinality=card,
                    role=clean_label_text(role.strip())
                ))
                continue

            # Standalone entity declaration: ENTITY_NAME
            if re.match(r'^[A-Za-z0-9_\-]+$', line_str):
                if line_str not in entities:
                    entities[line_str] = EREntity(name=line_str)
                continue

        return ERDiagram(title=title, entities=entities, relationships=relationships)
