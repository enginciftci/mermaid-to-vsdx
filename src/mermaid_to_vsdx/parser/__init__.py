"""
Mermaid Parser Package.
"""

from .ast_nodes import (
    DiagramType, ShapeType, EdgeStyle, ArrowType, MessageArrow,
    Node, Edge, Subgraph, FlowchartDiagram,
    Participant, Message, Note, SequenceDiagram,
    RelationshipType, ClassMember, ClassNode, ClassRelationship, ClassDiagram,
    StateNodeType, StateNode, StateTransition, StateDiagram,
    ERAttribute, EREntity, ERRelationship, ERDiagram
)
from .base_parser import MermaidParseError, detect_diagram_type, extract_mermaid_from_markdown
from .flowchart_parser import FlowchartParser
from .sequence_parser import SequenceParser
from .class_parser import ClassParser
from .state_parser import StateParser
from .er_parser import ERParser


def parse_mermaid(code: str):
    """
    Auto-detects diagram type and parses Mermaid code into the corresponding AST.
    Accepts raw Mermaid code or Markdown documents containing ```mermaid code blocks.
    """
    clean_code = extract_mermaid_from_markdown(code)
    dtype = detect_diagram_type(clean_code)
    if dtype == DiagramType.FLOWCHART:
        return dtype, FlowchartParser().parse(clean_code)
    elif dtype == DiagramType.SEQUENCE:
        return dtype, SequenceParser().parse(clean_code)
    elif dtype == DiagramType.CLASS_DIAGRAM:
        return dtype, ClassParser().parse(clean_code)
    elif dtype == DiagramType.STATE_DIAGRAM:
        return dtype, StateParser().parse(clean_code)
    elif dtype == DiagramType.ER_DIAGRAM:
        return dtype, ERParser().parse(clean_code)
    else:
        raise MermaidParseError(
            "Could not detect supported diagram type. Start with 'graph TD', 'flowchart LR', 'sequenceDiagram', 'classDiagram', 'stateDiagram-v2', or 'erDiagram'."
        )


__all__ = [
    "DiagramType",
    "ShapeType",
    "EdgeStyle",
    "ArrowType",
    "MessageArrow",
    "Node",
    "Edge",
    "Subgraph",
    "FlowchartDiagram",
    "Participant",
    "Message",
    "Note",
    "SequenceDiagram",
    "RelationshipType",
    "ClassMember",
    "ClassNode",
    "ClassRelationship",
    "ClassDiagram",
    "MermaidParseError",
    "detect_diagram_type",
    "extract_mermaid_from_markdown",
    "FlowchartParser",
    "SequenceParser",
    "ClassParser",
    "parse_mermaid"
]
