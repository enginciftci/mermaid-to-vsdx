"""
AST Node definitions for Mermaid diagrams (Flowcharts & Sequence diagrams).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Union


class DiagramType(Enum):
    FLOWCHART = auto()
    SEQUENCE = auto()
    CLASS_DIAGRAM = auto()
    STATE_DIAGRAM = auto()
    ER_DIAGRAM = auto()
    BLOCK = auto()
    UNKNOWN = auto()


class ShapeType(Enum):
    RECTANGLE = "rectangle"          # [text]
    ROUNDED = "rounded"              # (text)
    STADIUM = "stadium"              # ([text])
    SUBROUTINE = "subroutine"        # [[text]]
    CYLINDER = "cylinder"            # [(text)]
    CIRCLE = "circle"                # ((text))
    ASYMMETRIC = "asymmetric"        # >text]
    DIAMOND = "diamond"              # {text}
    HEXAGON = "hexagon"              # {{text}}
    PARALLELOGRAM = "parallelogram"  # [/text/] or [\text\]
    PARALLELOGRAM_ALT = "parallelogram_left"
    TRAPEZOID = "trapezoid"          # [/text\]
    TRAPEZOID_ALT = "trapezoid_inverted"  # [\text/]
    DOUBLE_CIRCLE = "double_circle"
    ROUNDED_RECT = "rounded"


class EdgeStyle(Enum):
    SOLID = "solid"      # --- or -->
    DOTTED = "dotted"    # -.- or -.->
    THICK = "thick"      # === or ==>


class ArrowType(Enum):
    NONE = "none"
    ARROW = "arrow"
    CROSS = "cross"
    CIRCLE = "circle"


@dataclass
class Node:
    id: str
    label: str
    shape: ShapeType = ShapeType.RECTANGLE
    classes: List[str] = field(default_factory=list)
    style: Dict[str, str] = field(default_factory=dict)


@dataclass
class Edge:
    source_id: str
    target_id: str
    label: str = ""
    style: EdgeStyle = EdgeStyle.SOLID
    arrow_start: ArrowType = ArrowType.NONE
    arrow_end: ArrowType = ArrowType.ARROW


@dataclass
class Subgraph:
    id: str
    title: str
    node_ids: List[str] = field(default_factory=list)
    children: List["Subgraph"] = field(default_factory=list)
    direction: Optional[str] = None


@dataclass
class FlowchartDiagram:
    direction: str = "TD"  # TD, TB, LR, RL, BT
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    subgraphs: List[Subgraph] = field(default_factory=list)


class MessageArrow(Enum):
    SOLID_ARROW = "->>"       # Solid line with arrowhead
    DOTTED_ARROW = "-->>"     # Dotted line with arrowhead
    SOLID_LINE = "->"         # Solid line without arrowhead (or open)
    DOTTED_LINE = "-->"       # Dotted line without arrowhead
    SOLID_CROSS = "-x"        # Solid line with cross at end
    DOTTED_CROSS = "--x"      # Dotted line with cross at end
    SOLID_OPEN = "-)"         # Solid line with open arrow
    DOTTED_OPEN = "--)"       # Dotted line with open arrow


@dataclass
class Participant:
    id: str
    label: str
    is_actor: bool = False


@dataclass
class Message:
    sender_id: str
    receiver_id: str
    text: str
    arrow_type: MessageArrow = MessageArrow.SOLID_ARROW
    activate: bool = False
    deactivate: bool = False


@dataclass
class Note:
    placement: str  # "left of", "right of", "over"
    participant_ids: List[str] = field(default_factory=list)
    text: str = ""


@dataclass
class Activation:
    participant_id: str
    is_activate: bool = True


@dataclass
class LoopBlock:
    title: str = ""
    block_type: str = "loop"
    items: List[Union["Message", "Note", "Activation", "LoopBlock"]] = field(default_factory=list)


@dataclass
class SequenceDiagram:
    title: str = ""
    participants: List[Participant] = field(default_factory=list)
    items: List[Union[Message, Note, Activation, LoopBlock]] = field(default_factory=list)


# --- Class Diagram Models ---

class RelationshipType(Enum):
    INHERITANCE = "<|--"        # Inheritance (generalization): Solid with triangle
    REALIZATION = "<|.."        # Realization (implementation): Dashed with triangle
    COMPOSITION = "*--"         # Composition: Solid with filled diamond
    AGGREGATION = "o--"         # Aggregation: Solid with hollow diamond
    ASSOCIATION = "-->"         # Association: Solid with standard arrow
    DEPENDENCY = "..>"          # Dependency: Dashed with standard arrow
    SOLID_LINK = "--"           # Solid line without arrow
    DASHED_LINK = ".."          # Dashed line without arrow


@dataclass
class ClassMember:
    name: str
    visibility: str = "+"       # +, -, #, ~
    is_method: bool = False
    return_type: str = ""
    parameters: str = ""


@dataclass
class ClassNode:
    name: str
    annotation: str = ""        # <<interface>>, <<abstract>>, <<service>>, etc.
    display_label: str = ""     # class Name["Display Label"]
    members: List[ClassMember] = field(default_factory=list)


@dataclass
class ClassNote:
    text: str
    target_class: Optional[str] = None


@dataclass
class ClassRelationship:
    source_name: str
    target_name: str
    rel_type: RelationshipType = RelationshipType.ASSOCIATION
    label: str = ""
    multiplicity_source: str = ""
    multiplicity_target: str = ""


@dataclass
class ClassDiagram:
    title: str = ""
    direction: str = "TD"
    classes: Dict[str, ClassNode] = field(default_factory=dict)
    relationships: List[ClassRelationship] = field(default_factory=list)
    notes: List[ClassNote] = field(default_factory=list)


# --- State Diagram Models ---

class StateNodeType(Enum):
    INITIAL = "initial"        # [*]
    TERMINAL = "terminal"      # [*]
    STATE = "state"            # Normal state
    CHOICE = "choice"          # <<choice>>
    FORK = "fork"              # <<fork>>
    JOIN = "join"              # <<join>>


@dataclass
class StateNode:
    id: str
    label: str
    node_type: StateNodeType = StateNodeType.STATE
    description: str = ""
    children: List[str] = field(default_factory=list)


@dataclass
class StateNote:
    placement: str  # "left of", "right of"
    state_id: str
    text: str


@dataclass
class StateTransition:
    source_id: str
    target_id: str
    event: str = ""


@dataclass
class StateDiagram:
    direction: str = "TD"
    states: Dict[str, StateNode] = field(default_factory=dict)
    transitions: List[StateTransition] = field(default_factory=list)
    notes: List[StateNote] = field(default_factory=list)


# --- ER Diagram Models ---

@dataclass
class ERAttribute:
    name: str
    attr_type: str = ""
    is_pk: bool = False
    is_fk: bool = False
    comment: str = ""


@dataclass
class EREntity:
    name: str
    attributes: List[ERAttribute] = field(default_factory=list)


@dataclass
class ERRelationship:
    entity1: str
    entity2: str
    cardinality: str = "--"
    role: str = ""


@dataclass
class ERDiagram:
    title: str = ""
    entities: Dict[str, EREntity] = field(default_factory=dict)
    relationships: List[ERRelationship] = field(default_factory=list)


# --- Block Diagram Models ---

@dataclass
class BlockNode:
    id: str
    label: str = ""
    shape: ShapeType = ShapeType.RECTANGLE
    width_cols: int = 1
    is_space: bool = False
    children: List["BlockNode"] = field(default_factory=list)
    columns: Optional[int] = None
    style: Dict[str, str] = field(default_factory=dict)
    classes: List[str] = field(default_factory=list)


@dataclass
class BlockEdge:
    source_id: str
    target_id: str
    label: str = ""
    style: EdgeStyle = EdgeStyle.SOLID
    has_arrow: bool = True


@dataclass
class BlockDiagram:
    columns: int = 1
    blocks: List[BlockNode] = field(default_factory=list)
    edges: List[BlockEdge] = field(default_factory=list)
    class_defs: Dict[str, Dict[str, str]] = field(default_factory=dict)

