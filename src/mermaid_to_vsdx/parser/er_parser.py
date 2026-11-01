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
    Supports entity definitions with aliases, typed attributes (PK, FK, UK, comments), and cardinalities.
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

        # Relationship regex: ENTITY1["Alias1"] cardinality ENTITY2["Alias2"] : "role"
        # Cardinalities: ||--o{, ||--|{, }|..|{, |o--o|, etc.
        rel_pattern = re.compile(
            r'^([A-Za-z0-9_\-]+)(?:\[\s*["\']([^"\']+)["\']\s*\])?\s+([|o}{]+[-.]+[|o}{]+)\s+([A-Za-z0-9_\-]+)(?:\[\s*["\']([^"\']+)["\']\s*\])?(?:\s*:\s*"?([^"]*)"?)?$',
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
                # Attribute line inside entity: type name [PK|FK|UK] ["comment"]
                comment_str = ""
                m_comment = re.search(r'"([^"]*)"|\'([^\']*)\'', line_str)
                if m_comment:
                    comment_str = clean_label_text(m_comment.group(1) or m_comment.group(2) or "")
                    rest_attr = line_str[:m_comment.start()].strip()
                else:
                    rest_attr = line_str

                attr_parts = rest_attr.split()
                if len(attr_parts) >= 2:
                    a_type = attr_parts[0]
                    a_name = attr_parts[1]
                    tags = {t.strip().upper() for p in attr_parts[2:] for t in p.split(",") if t.strip()}
                    is_pk = "PK" in tags
                    is_fk = "FK" in tags
                    is_uk = "UK" in tags
                    entities[in_entity].attributes.append(ERAttribute(
                        name=clean_label_text(a_name),
                        attr_type=clean_label_text(a_type),
                        is_pk=is_pk,
                        is_fk=is_fk,
                        is_uk=is_uk,
                        comment=comment_str,
                    ))
                continue

            # Check entity start with optional alias: ENTITY_NAME["Display Name"] {
            ent_start_match = re.match(
                r'^([A-Za-z0-9_\-]+)(?:\[\s*["\']([^"\']+)["\']\s*\])?\s*\{$',
                line_str
            )
            if ent_start_match:
                ename = ent_start_match.group(1)
                ealias = ent_start_match.group(2) or ""
                in_entity = ename
                if ename not in entities:
                    entities[ename] = EREntity(name=ename, alias=clean_label_text(ealias) if ealias else "")
                elif ealias:
                    entities[ename].alias = clean_label_text(ealias)
                continue

            # Check relationship
            rel_match = rel_pattern.match(line_str)
            if rel_match:
                e1 = rel_match.group(1).strip()
                e1_alias = rel_match.group(2) or ""
                card = rel_match.group(3).strip()
                e2 = rel_match.group(4).strip()
                e2_alias = rel_match.group(5) or ""
                role = rel_match.group(6) or ""

                if e1 not in entities:
                    entities[e1] = EREntity(name=e1, alias=clean_label_text(e1_alias) if e1_alias else "")
                elif e1_alias:
                    entities[e1].alias = clean_label_text(e1_alias)

                if e2 not in entities:
                    entities[e2] = EREntity(name=e2, alias=clean_label_text(e2_alias) if e2_alias else "")
                elif e2_alias:
                    entities[e2].alias = clean_label_text(e2_alias)

                relationships.append(ERRelationship(
                    entity1=e1,
                    entity2=e2,
                    cardinality=card,
                    role=clean_label_text(role.strip())
                ))
                continue

            # Standalone entity declaration with optional alias: ENTITY_NAME["Display Name"]
            ent_standalone = re.match(
                r'^([A-Za-z0-9_\-]+)(?:\[\s*["\']([^"\']+)["\']\s*\])?$',
                line_str
            )
            if ent_standalone:
                ename = ent_standalone.group(1)
                ealias = ent_standalone.group(2) or ""
                if ename not in entities:
                    entities[ename] = EREntity(name=ename, alias=clean_label_text(ealias) if ealias else "")
                elif ealias:
                    entities[ename].alias = clean_label_text(ealias)
                continue

        return ERDiagram(title=title, entities=entities, relationships=relationships)
