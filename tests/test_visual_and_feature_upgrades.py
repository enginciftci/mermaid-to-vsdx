"""
Comprehensive test suite for all visual quality upgrades, syntax extensions,
multi-page Markdown compilation, and the 5 new diagram types (Mindmap, Timeline, Quadrant, Pie, Gantt).
"""

import os
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mermaid_to_vsdx.parser import (
    parse_mermaid,
    DiagramType,
    ShapeType,
    EdgeStyle,
    ArrowType,
    extract_all_mermaid_from_markdown,
)
from mermaid_to_vsdx.compiler import compile_mermaid_to_vsdx
from mermaid_to_vsdx.verifier.native_renderer import render_vsdx_to_png


class TestVisualAndFeatureUpgrades(unittest.TestCase):
    def setUp(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_page_xml(self, vsdx_path: str, page_idx: int = 1) -> str:
        with zipfile.ZipFile(vsdx_path, "r") as zf:
            return zf.read(f"visio/pages/page{page_idx}.xml").decode("utf-8")

    def test_01_flowchart_rounding_double_circle_v11_shapes_and_styling(self):
        mmd = """flowchart TD
    classDef highlight fill:#fef08a,stroke:#ca8a04,color:#713f12
    A([Start Terminal]):::highlight --> B(Rounded Step)
    B <--> C(((Double Circle)))
    C --o D@{ shape: cyl, label: "Primary DB" }
    D --x E{Is Ready for<br/><b>Deployment</b>?}
    E ~~~ F[Hidden Rank Link]
    style B fill:#dcfce7,stroke:#16a34a
    linkStyle 0 stroke:#dc2626
"""
        dtype, diag = parse_mermaid(mmd)
        self.assertEqual(dtype, DiagramType.FLOWCHART)
        self.assertEqual(diag.nodes["A"].shape, ShapeType.STADIUM)
        self.assertIn("highlight", diag.nodes["A"].classes)
        self.assertEqual(diag.nodes["B"].shape, ShapeType.ROUNDED)
        self.assertEqual(diag.nodes["C"].shape, ShapeType.DOUBLE_CIRCLE)
        self.assertEqual(diag.nodes["C"].label, "Double Circle")
        self.assertEqual(diag.nodes["D"].shape, ShapeType.CYLINDER)
        self.assertEqual(diag.nodes["D"].label, "Primary DB")
        self.assertTrue(diag.nodes["E"].bold)

        # Bidirectional arrow B <--> C
        bi_edge = diag.edges[1]
        self.assertEqual(bi_edge.arrow_start, ArrowType.ARROW)
        self.assertEqual(bi_edge.arrow_end, ArrowType.ARROW)

        # Invisible edge E ~~~ F
        inv_edge = diag.edges[4]
        self.assertEqual(inv_edge.style, EdgeStyle.INVISIBLE)

        vsdx_path = os.path.join(self.output_dir, "test_fc_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)

        # Verify custom classDef fill on A and inline style on B
        self.assertIn("#fef08a", page_xml.lower())
        self.assertIn("#dcfce7", page_xml.lower())
        # Verify stadium rounding > 0 on Node_A
        root = ET.fromstring(page_xml)
        node_a = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Node_A")
        rnd_a = next(float(c.attrib["V"]) for c in node_a.findall("{*}Cell") if c.attrib.get("N") == "Rounding")
        self.assertGreater(rnd_a, 0.3)

        # Verify double circle is 1:1 square bounding box
        node_c = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Node_C")
        w_c = next(float(c.attrib["V"]) for c in node_c.findall("{*}Cell") if c.attrib.get("N") == "Width")
        h_c = next(float(c.attrib["V"]) for c in node_c.findall("{*}Cell") if c.attrib.get("N") == "Height")
        self.assertAlmostEqual(w_c, h_c, places=2)

    def test_02_class_diagram_stereotype_and_inheritance_hierarchy(self):
        mmd = """classDiagram
    Animal <|-- Duck : extends
    <<Interface>> Animal
    class Animal {
        +int age
        +isMammal()
    }
    class Duck {
        +String beakColor
        +swim()
    }
"""
        vsdx_path = os.path.join(self.output_dir, "test_class_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)

        # Must NOT contain quadruple brackets <<<<Interface>>>>
        self.assertNotIn("&lt;&lt;&lt;&lt;", page_xml)
        self.assertIn("&lt;&lt;Interface&gt;&gt;", page_xml)

        # Animal (superclass) must have higher PinY (placed above) than Duck (subclass)
        root = ET.fromstring(page_xml)
        s_animal = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Class_Animal")
        s_duck = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Class_Duck")
        y_animal = next(float(c.attrib["V"]) for c in s_animal.findall("{*}Cell") if c.attrib.get("N") == "PinY")
        y_duck = next(float(c.attrib["V"]) for c in s_duck.findall("{*}Cell") if c.attrib.get("N") == "PinY")
        self.assertGreater(y_animal, y_duck)

    def test_03_er_diagram_crows_foot_and_clean_labels(self):
        mmd = """erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
"""
        vsdx_path = os.path.join(self.output_dir, "test_er_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)

        # Raw ASCII cardinality must NOT appear in connector text
        self.assertNotIn("||--o{", page_xml)
        self.assertNotIn("||--|{", page_xml)
        self.assertIn("places", page_xml)
        self.assertIn("contains", page_xml)
        # Crow's foot arrow codes (28 for ||, 29 for o{, 27 for |{)
        self.assertIn("<Cell N='BeginArrow' V='28'/>", page_xml)
        self.assertIn("<Cell N='EndArrow' V='29'/>", page_xml)

    def test_04_sequence_else_branches_notes_autonumber_and_transparency(self):
        mmd = """sequenceDiagram
    autonumber
    actor User
    participant API
    User->>+API: Request Resource
    alt Authorized
        API-->>User: 200 OK
    else Unauthorized
        API-->>-User: 403 Forbidden
    end
    Note left of User: Client side note
    Note right of API: Server side note
"""
        vsdx_path = os.path.join(self.output_dir, "test_seq_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)

        self.assertIn("[1] Request Resource", page_xml)
        self.assertIn("else", page_xml.lower())
        self.assertIn("Unauthorized", page_xml)
        # Loop/alt container must have FillPattern = 0 so it never whites out lifelines/activations
        root = ET.fromstring(page_xml)
        loop_cont = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU", "").startswith("Container_Loop"))
        fp = next(c.attrib["V"] for c in loop_cont.findall("{*}Cell") if c.attrib.get("N") == "FillPattern")
        self.assertEqual(fp, "0")

    def test_05_state_composite_notes_and_u_channel_feedback(self):
        mmd = """stateDiagram-v2
    [*] --> Active
    state Active {
        Idle --> Running : start
        Running --> Idle : stop
    }
    Active --> [*]
    note right of Active : Composite state note
"""
        vsdx_path = os.path.join(self.output_dir, "test_state_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)
        self.assertIn("Container_Active", page_xml)
        self.assertIn("Composite state note", page_xml)

    def test_06_block_diagram_connects_and_nested_composites(self):
        mmd = """block-beta
    columns 2
    classDef custom fill:#fde68a,stroke:#d97706
    a["Service A"]
    b[("Database B")]
    a --> b
    class a custom
"""
        vsdx_path = os.path.join(self.output_dir, "test_block_upgrades.vsdx")
        compile_mermaid_to_vsdx(mmd, vsdx_path)
        page_xml = self._get_page_xml(vsdx_path)
        self.assertIn("<Connects>", page_xml)
        self.assertIn("#fde68a", page_xml.lower())

    def test_07_new_diagram_types_mindmap_timeline_quadrant_pie_gantt(self):
        diagrams = {
            "mindmap": """mindmap
  root((Strategy))
    Product
      Roadmap
      Design
    Engineering
      Compiler
      Layout
""",
            "timeline": """timeline
    title Platform Evolution
    section Phase 1
      2025 : Initial Prototype : Core Parser
    section Phase 2
      2026 : Headless VSDX Engine : 11 Diagram Types
""",
            "quadrant": """quadrantChart
    title Priority Matrix
    x-axis Low Effort --> High Effort
    y-axis Low Impact --> High Impact
    quadrant-1 Strategic
    quadrant-2 Quick Wins
    quadrant-3 Defer
    quadrant-4 Re-evaluate
    Feature A: [0.25, 0.85]
    Feature B: [0.75, 0.80]
""",
            "pie": """pie showData
    title Revenue Share
    "Enterprise" : 60
    "SMB" : 25
    "Self-Serve" : 15
""",
            "gantt": """gantt
    title Release Plan
    dateFormat YYYY-MM-DD
    section Core
        Parser Upgrade :done, p1, 2026-01-01, 5d
        Layout Engine  :active, p2, after p1, 4d
        Launch         :milestone, m1, after p2, 1d
""",
        }

        for name, code in diagrams.items():
            vsdx_path = os.path.join(self.output_dir, f"test_new_{name}.vsdx")
            png_path = os.path.join(self.output_dir, f"test_new_{name}.png")
            dtype, out = compile_mermaid_to_vsdx(code, vsdx_path)
            self.assertTrue(os.path.exists(out), f"{name} vsdx not created")
            # Validate XML well-formedness
            with zipfile.ZipFile(out, "r") as zf:
                for member in zf.namelist():
                    if member.endswith(".xml"):
                        ET.fromstring(zf.read(member))
            # Validate native PNG preview
            res = render_vsdx_to_png(out, png_path)
            self.assertTrue(res["success"], f"{name} native preview failed")

    def test_08_multipage_markdown_compilation(self):
        md = """# System Architecture
```mermaid
flowchart LR
    Client([Web Client]) --> API[API Gateway] --> DB[(Database)]
```

# Deployment Timeline
```mermaid
timeline
    title Rollout Schedule
    Q1 : Alpha Release
    Q2 : Production GA
```
"""
        blocks = extract_all_mermaid_from_markdown(md)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][0], "System Architecture")
        self.assertEqual(blocks[1][0], "Deployment Timeline")

        vsdx_path = os.path.join(self.output_dir, "test_multipage_doc.vsdx")
        compile_mermaid_to_vsdx(md, vsdx_path)
        with zipfile.ZipFile(vsdx_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("visio/pages/page1.xml", names)
            self.assertIn("visio/pages/page2.xml", names)
            pages_xml = zf.read("visio/pages/pages.xml").decode("utf-8")
            self.assertIn("System Architecture", pages_xml)
            self.assertIn("Deployment Timeline", pages_xml)


if __name__ == "__main__":
    unittest.main()
