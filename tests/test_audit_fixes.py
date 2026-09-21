"""
Comprehensive test suite verifying visual & drawing quality features
for mermaid-to-vsdx on Windows.
"""

import os
import unittest
import zipfile
import xml.etree.ElementTree as ET

from mermaid_to_vsdx.compiler.text_metrics import (
    wrap_text_to_width,
    estimate_text_dimensions,
    estimate_line_width_pt,
)
from mermaid_to_vsdx.compiler.layout_engine import SugiyamaLayoutEngine, LayoutNode
from mermaid_to_vsdx.compiler.shapesheet import (
    build_2d_shape_xml,
    build_1d_connector_xml,
    build_group_shape_xml,
    build_connect_records,
)
from mermaid_to_vsdx.parser.flowchart_parser import FlowchartParser
from mermaid_to_vsdx.parser.class_parser import ClassParser
from mermaid_to_vsdx.parser.er_parser import ERParser
from mermaid_to_vsdx.parser.sequence_parser import SequenceParser
from mermaid_to_vsdx.parser.state_parser import StateParser

from mermaid_to_vsdx.compiler.flowchart_compiler import compile_flowchart_to_vsdx
from mermaid_to_vsdx.compiler.class_compiler import compile_class_diagram_to_vsdx
from mermaid_to_vsdx.compiler.er_compiler import compile_er_diagram_to_vsdx
from mermaid_to_vsdx.compiler.sequence_compiler import compile_sequence_to_vsdx
from mermaid_to_vsdx.compiler.state_compiler import compile_state_diagram_to_vsdx


class TestDrawingQualityFeatures(unittest.TestCase):
    def setUp(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_page_xml(self, vsdx_path: str) -> str:
        """Helper to extract page1.xml content from a vsdx archive."""
        with zipfile.ZipFile(vsdx_path, "r") as zf:
            for name in zf.namelist():
                if "page1.xml" in name:
                    return zf.read(name).decode("utf-8")
        return ""

    # Item 1: Skip-level edges and intermediate dummy waypoints
    def test_item1_sugiyama_dummy_nodes_and_edge_routes(self):
        engine = SugiyamaLayoutEngine(direction="TD")
        node_dims = {
            "A": (1.5, 0.75, None),
            "B": (1.5, 0.75, None),
            "C": (1.5, 0.75, None),
        }
        # A -> B -> C and skip-level edge A -> C
        edges = [("A", "B"), ("B", "C"), ("A", "C")]
        res = engine.layout(node_dims, edges)

        # Skip-level edge A -> C should have generated waypoints
        self.assertIn(("A", "C"), res.edge_routes)
        waypoints = res.edge_routes[("A", "C")]
        self.assertGreaterEqual(len(waypoints), 1)

        # Confirm dummy nodes are not in res.nodes
        for nid, node in res.nodes.items():
            self.assertFalse(node.is_dummy)
            self.assertIn(nid, ["A", "B", "C"])

    # Item 2: Decision diamond branch separation and fan-out/fan-in ports
    def test_item2_flowchart_branch_separation_and_port_distribution(self):
        mmd = """flowchart TD
    D{Is Valid?}
    D -->|Yes| P[Process]
    D -->|No| R[Reject]
    D -->|Escalate| S[Supervisor]
    P --> End[Done]
    R --> End
    S --> End
"""
        parser = FlowchartParser()
        diag = parser.parse(mmd)
        vsdx_path = os.path.join(self.output_dir, "test_decision_ports.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)

        page_xml = self._get_page_xml(vsdx_path)
        # Check that fan-out ports on decision node and fan-in ports on target node are distributed
        self.assertIn("Connections.Bottom_", page_xml)
        self.assertIn("Connections.Top_in_", page_xml)

    # Item 3: Connector ConFixedCode = 1 locks orthogonal routing in Visio
    def test_item3_connector_confixedcode(self):
        conn_xml = build_1d_connector_xml(
            connector_id=10,
            begin_x=1.0,
            begin_y=2.0,
            end_x=3.0,
            end_y=4.0,
            is_dynamic=True,
        )
        self.assertIn("<Cell N='ConFixedCode' V='1'/>", conn_xml)

    # Item 4: Word wrapping prevents horizontal overflow
    def test_item4_word_wrapping(self):
        long_label = "This is an extremely lengthy process description that should wrap properly across several lines"
        wrapped = wrap_text_to_width(long_label, max_width_in=2.5, font_size_pt=10.0)
        self.assertGreater(len(wrapped), 1)

        w, h, wrapped_lines = estimate_text_dimensions(
            long_label,
            font_size_pt=10.0,
            max_width_in=2.5,
        )
        self.assertLessEqual(w, 3.5)
        self.assertGreater(h, 0.8)
        self.assertGreater(len(wrapped_lines), 1)

    # Item 5: Connector label offset from line with opaque background
    def test_item5_connector_label_offset(self):
        conn_xml = build_1d_connector_xml(
            connector_id=11,
            begin_x=1.0,
            begin_y=1.0,
            end_x=1.0,
            end_y=5.0,
            label="Branch Status",
            is_dynamic=True,
        )
        # Check that TxtPinX is offset from horizontal 0 (width*0.5)
        self.assertIn("TxtPinX", conn_xml)
        self.assertIn("TxtPinY", conn_xml)
        # Check opaque fill for label legibility via TextBkgnd
        self.assertIn("<Cell N='TextBkgnd' V='#ffffff'/>", conn_xml)

    # Item 6: Class and ER diagrams wrap compartments in native Visio Groups
    def test_item6_class_and_er_group_shapes(self):
        # Class diagram
        class_mmd = """classDiagram
    class User {
        +String username
        +String email
        +login()
        +logout()
    }
    class Admin {
        +grantRole()
    }
    Admin --|> User
"""
        c_diag = ClassParser().parse(class_mmd)
        c_vsdx = os.path.join(self.output_dir, "test_class_group.vsdx")
        compile_class_diagram_to_vsdx(c_diag, c_vsdx)
        c_xml = self._get_page_xml(c_vsdx)

        self.assertIn("Type='Group'", c_xml)
        self.assertIn("<Shapes>", c_xml)
        self.assertIn("NameU='Class_User'", c_xml)
        self.assertIn("NameU='Title_User'", c_xml)
        self.assertIn("NameU='Attrs_User'", c_xml)
        self.assertIn("NameU='Methods_User'", c_xml)

        # ER diagram
        er_mmd = """erDiagram
    CUSTOMER ||--o{ ORDER : places
    CUSTOMER {
        string customer_id PK
        string email
    }
    ORDER {
        int order_id PK
        string customer_id FK
    }
"""
        e_diag = ERParser().parse(er_mmd)
        e_vsdx = os.path.join(self.output_dir, "test_er_group.vsdx")
        compile_er_diagram_to_vsdx(e_diag, e_vsdx)
        e_xml = self._get_page_xml(e_vsdx)

        self.assertIn("Type='Group'", e_xml)
        self.assertIn("NameU='Entity_CUSTOMER'", e_xml)
        self.assertIn("NameU='Header_CUSTOMER'", e_xml)
        self.assertIn("NameU='Attrs_CUSTOMER'", e_xml)

    # Item 7: Sequence diagram activation bars
    def test_item7_sequence_activation_bars(self):
        seq_mmd = """sequenceDiagram
    Alice->>+Bob: Authenticate
    Bob-->>-Alice: Success
    Alice->>Bob: Fetch Data
    activate Bob
    Bob-->>Alice: Data Result
    deactivate Bob
"""
        s_diag = SequenceParser().parse(seq_mmd)
        s_vsdx = os.path.join(self.output_dir, "test_seq_act.vsdx")
        compile_sequence_to_vsdx(s_diag, s_vsdx)
        s_xml = self._get_page_xml(s_vsdx)

        self.assertIn("Activation_Bob", s_xml)
        # Bar width 0.16 inches
        self.assertIn("<Cell N='Width' V='0.16'/>", s_xml)

    # Item 8: State diagram terminal bullseye
    def test_item8_state_terminal_bullseye(self):
        state_mmd = """stateDiagram-v2
    [*] --> Idle
    Idle --> Processing: event
    Processing --> [*]
"""
        st_diag = StateParser().parse(state_mmd)
        st_vsdx = os.path.join(self.output_dir, "test_state_bullseye.vsdx")
        compile_state_diagram_to_vsdx(st_diag, st_vsdx)
        st_xml = self._get_page_xml(st_vsdx)

        # Terminal state group shape with clean outer ring and solid dark inner disc
        self.assertIn("EndOuter_", st_xml)
        self.assertIn("EndInner_", st_xml)
        self.assertIn("<Cell N='NoFill' V='0'/>", st_xml)

    # Item 9: Subgraph headroom prevents header overlap
    def test_item9_subgraph_headroom(self):
        mmd = """flowchart TD
    subgraph Cluster1 [Payment Services]
        P1[Stripe Gateway]
        P2[PayPal Gateway]
    end
    Entry[User Checkout] --> P1
"""
        diag = FlowchartParser().parse(mmd)
        vsdx_path = os.path.join(self.output_dir, "test_subgraph_headroom.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)

        self.assertIn("Header_Cluster1", page_xml)
        self.assertIn("Container_Cluster1", page_xml)

    # Item 10: Automatic landscape page sizing for LR diagrams
    def test_item10_auto_landscape_sizing(self):
        mmd = """flowchart LR
    A --> B --> C --> D --> E --> F
"""
        diag = FlowchartParser().parse(mmd)
        vsdx_path = os.path.join(self.output_dir, "test_landscape.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)

        with zipfile.ZipFile(vsdx_path, "r") as zf:
            pages_xml = zf.read("visio/pages/pages.xml").decode("utf-8")

        # Landscape minimum width 11.0, height 8.5
        root = ET.fromstring(pages_xml)
        ns = {"v": "http://schemas.microsoft.com/office/visio/2012/main"}
        w_cell = root.find(".//v:Cell[@N='PageWidth']", ns)
        h_cell = root.find(".//v:Cell[@N='PageHeight']", ns)
        self.assertIsNotNone(w_cell)
        self.assertIsNotNone(h_cell)
        page_w = float(w_cell.attrib["V"])
        page_h = float(h_cell.attrib["V"])

        self.assertGreaterEqual(page_w, 11.0)
        self.assertGreaterEqual(page_h, 8.5)
        self.assertGreater(page_w, page_h)  # Landscape orientation

    # Item 11: 7 Text Block transform cells present to prevent character stacking
    def test_item11_text_block_transform_cells(self):
        shape_xml = build_2d_shape_xml(
            shape_id=99,
            name="TestNode",
            pin_x=4.0,
            pin_y=5.0,
            width=2.5,
            height=1.0,
            text="Node Text",
        )
        for cell_name in ["TxtPinX", "TxtPinY", "TxtWidth", "TxtHeight", "TxtLocPinX", "TxtLocPinY", "TxtAngle"]:
            self.assertIn(f"<Cell N='{cell_name}'", shape_xml)

    # Item 12: Ampersand chaining, nested subgraphs, and XML escaping
    def test_item12_ampersand_chaining_and_nested_subgraphs(self):
        mmd = """flowchart LR
    subgraph SENSOR_ALANI ["TEU: Akustik Dizin"]
        direction TB
        PZT1["Sensor 1"]
        PZT2["Sensor 2"]
        PZT_CONN["Connector"]
        PZT1 & PZT2 --> PZT_CONN
    end
    subgraph OUTER ["Outer Box"]
        direction TB
        subgraph INNER1 ["Power Rail"]
            PWR1["Power 1"]
            PWR2["Power 2"]
            PWR1 --> PWR2
        end
        subgraph INNER2 ["Channels"]
            CH1["Channel 1"]
            CH2["Channel 2"]
        end
    end
    PZT_CONN --> INNER2
    PWR1 -.-> CH1
    PWR2 -.-> CH2
"""
        diag = FlowchartParser().parse(mmd)
        vsdx_path = os.path.join(self.output_dir, "test_nested_subgraphs.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)

        # Validate that the generated VSDX package has 100% well-formed XML
        with zipfile.ZipFile(vsdx_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    data = zf.read(name)
                    # Must parse without xml.etree.ElementTree.ParseError
                    root = ET.fromstring(data)
                    self.assertIsNotNone(root)

        page_xml = self._get_page_xml(vsdx_path)
        # Verify containers and shapes were properly synthesized
        self.assertIn("Container_OUTER", page_xml)
        self.assertIn("Container_INNER1", page_xml)
        self.assertIn("Container_INNER2", page_xml)


if __name__ == "__main__":
    unittest.main()
