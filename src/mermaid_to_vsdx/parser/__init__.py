"""
Mermaid Parser Package.
"""

from .ast_nodes import (
    DiagramType, ShapeType, EdgeStyle, ArrowType, MessageArrow,
    Node, Edge, Subgraph, FlowchartDiagram,
    Participant, ParticipantBox, Message, Note, Activation, ElseBranch, LoopBlock, SequenceDiagram,
    RelationshipType, ClassMember, ClassNode, ClassNote, ClassRelationship, ClassDiagram,
    StateNodeType, StateNode, StateNote, StateTransition, StateDiagram,
    ERAttribute, EREntity, ERRelationship, ERDiagram,
    BlockNode, BlockEdge, BlockDiagram,
    MindmapNode, MindmapDiagram,
    TimelinePeriod, TimelineDiagram,
    QuadrantPoint, QuadrantDiagram,
    PieSlice, PieDiagram,
    GanttTask, GanttDiagram,
)
from .base_parser import (
    MermaidParseError,
    detect_diagram_type,
    extract_mermaid_from_markdown,
    extract_all_mermaid_from_markdown,
)
from .flowchart_parser import FlowchartParser
from .sequence_parser import SequenceParser
from .class_parser import ClassParser
from .state_parser import StateParser
from .er_parser import ERParser
from .block_parser import BlockParser
from .mindmap_parser import MindmapParser
from .timeline_parser import TimelineParser
from .quadrant_parser import QuadrantParser
from .pie_parser import PieParser
from .gantt_parser import GanttParser


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
    elif dtype == DiagramType.BLOCK:
        return dtype, BlockParser().parse(clean_code)
    elif dtype == DiagramType.MINDMAP:
        return dtype, MindmapParser().parse(clean_code)
    elif dtype == DiagramType.TIMELINE:
        return dtype, TimelineParser().parse(clean_code)
    elif dtype == DiagramType.QUADRANT:
        return dtype, QuadrantParser().parse(clean_code)
    elif dtype == DiagramType.PIE:
        return dtype, PieParser().parse(clean_code)
    elif dtype == DiagramType.GANTT:
        return dtype, GanttParser().parse(clean_code)
    else:
        raise MermaidParseError(
            "Could not detect supported diagram type. Start with 'graph TD', 'flowchart LR', "
            "'sequenceDiagram', 'classDiagram', 'stateDiagram-v2', 'erDiagram', 'block', "
            "'mindmap', 'timeline', 'quadrantChart', 'pie', or 'gantt'."
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
    "ParticipantBox",
    "Message",
    "Note",
    "Activation",
    "ElseBranch",
    "LoopBlock",
    "SequenceDiagram",
    "RelationshipType",
    "ClassMember",
    "ClassNode",
    "ClassNote",
    "ClassRelationship",
    "ClassDiagram",
    "StateNodeType",
    "StateNode",
    "StateNote",
    "StateTransition",
    "StateDiagram",
    "ERAttribute",
    "EREntity",
    "ERRelationship",
    "ERDiagram",
    "BlockNode",
    "BlockEdge",
    "BlockDiagram",
    "MindmapNode",
    "MindmapDiagram",
    "TimelinePeriod",
    "TimelineDiagram",
    "QuadrantPoint",
    "QuadrantDiagram",
    "PieSlice",
    "PieDiagram",
    "GanttTask",
    "GanttDiagram",
    "MermaidParseError",
    "detect_diagram_type",
    "extract_mermaid_from_markdown",
    "extract_all_mermaid_from_markdown",
    "FlowchartParser",
    "SequenceParser",
    "ClassParser",
    "StateParser",
    "ERParser",
    "BlockParser",
    "MindmapParser",
    "TimelineParser",
    "QuadrantParser",
    "PieParser",
    "GanttParser",
    "parse_mermaid",
]
