"""
Tests for documentation syntax fixes and missing cases:
1. Sequence diagram dashed line (-->>), loop container, and self-pointing messages
2. Class diagram arrow directions (<|-- and --|>)
3. State diagram terminal bullseye ([*])
4. Block diagram (columns, composite blocks, space, edges)
"""

import os
import unittest
import zipfile
import xml.etree.ElementTree as ET

from mermaid_to_vsdx.parser import parse_mermaid, DiagramType
from mermaid_to_vsdx.compiler import compile_mermaid_to_vsdx
from mermaid_to_vsdx.compiler.sequence_compiler import compile_sequence_to_vsdx
from mermaid_to_vsdx.compiler.class_compiler import compile_class_diagram_to_vsdx
from mermaid_to_vsdx.compiler.state_compiler import compile_state_diagram_to_vsdx
from mermaid_to_vsdx.compiler.block_compiler import compile_block_to_vsdx
from mermaid_to_vsdx.parser.sequence_parser import SequenceParser
from mermaid_to_vsdx.parser.class_parser import ClassParser
from mermaid_to_vsdx.parser.state_parser import StateParser
from mermaid_to_vsdx.parser.block_parser import BlockParser
from mermaid_to_vsdx.verifier.native_renderer import render_vsdx_to_png


class TestDocSyntaxFixes(unittest.TestCase):

    def setUp(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_page_xml(self, vsdx_path: str) -> str:
        with zipfile.ZipFile(vsdx_path, "r") as z:
            return z.read("visio/pages/page1.xml").decode("utf-8")

    def test_sequence_dashed_line_and_loop_and_self_message(self):
        mmd = """sequenceDiagram
Alice->>John: Hello John, how are you?
loop HealthCheck
    John->>John: Fight against hypochondria
end
Note right of John: Rational thoughts!
John-->>Alice: Great!
John->>Bob: How about you?
Bob-->>John: Jolly good!
"""
        dtype, diag = parse_mermaid(mmd)
        self.assertEqual(dtype, DiagramType.SEQUENCE)

        vsdx_path = os.path.join(self.output_dir, "test_user_sequence.vsdx")
        compile_sequence_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        page_xml = self._get_page_xml(vsdx_path)

        # 1. Dashed line (-->>) must have LinePattern = 2 guarded
        self.assertIn("<Cell N='LinePattern' V='2' F='GUARD(2)'/>", page_xml)

        # 2. Loop container must exist
        self.assertIn("Container_Loop_", page_xml)
        self.assertIn("Badge_Loop_", page_xml)
        self.assertIn("loop [HealthCheck]", page_xml)

        # 3. Self-pointing loop connector must exist
        self.assertIn("Line.SelfLoop.", page_xml)
        self.assertIn("Fight against hypochondria", page_xml)

        # 4. Preview rendering succeeds without error
        png_path = os.path.join(self.output_dir, "test_user_sequence.png")
        render_res = render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(render_res["success"])
        self.assertTrue(os.path.exists(png_path))

    def test_class_diagram_arrow_direction(self):
        mmd = """classDiagram
Class01 <|-- AveryLongClass : Cool
<<Interface>> Class01
Class09 --> C2 : Where am I?
Class09 --* C3
Class09 --|> Class07
Class07 : equals()
Class07 : Object[] elementData
Class01 : size()
Class01 : int chimp
Class01 : int gorilla
class Class10 {
  <<service>>
  int id
  size()
}
"""
        dtype, diag = parse_mermaid(mmd)
        self.assertEqual(dtype, DiagramType.CLASS_DIAGRAM)

        # Check parsed relationships:
        # Class01 <|-- AveryLongClass: target should be Class01 (the superclass)
        # Class09 --|> Class07: target should be Class07 (the superclass)
        rel_cool = next(r for r in diag.relationships if r.label == "Cool")
        self.assertEqual(rel_cool.target_name, "Class01")
        self.assertEqual(rel_cool.source_name, "AveryLongClass")

        rel_c07 = next(r for r in diag.relationships if r.source_name == "Class09" and r.target_name == "Class07")
        self.assertEqual(rel_c07.target_name, "Class07")

        vsdx_path = os.path.join(self.output_dir, "test_user_class.vsdx")
        compile_class_diagram_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        png_path = os.path.join(self.output_dir, "test_user_class.png")
        render_res = render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(render_res["success"])
        self.assertTrue(os.path.exists(png_path))

    def test_state_diagram_terminal_bullseye(self):
        mmd = """stateDiagram-v2
[*] --> Still
Still --> [*]
Still --> Crash
Crash --> [*]
"""
        dtype, diag = parse_mermaid(mmd)
        self.assertEqual(dtype, DiagramType.STATE_DIAGRAM)

        vsdx_path = os.path.join(self.output_dir, "test_user_state.vsdx")
        compile_state_diagram_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        page_xml = self._get_page_xml(vsdx_path)
        # Both outer white ring and inner solid dark disc
        self.assertIn("EndOuter_", page_xml)
        self.assertIn("EndInner_", page_xml)

        png_path = os.path.join(self.output_dir, "test_user_state.png")
        render_res = render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(render_res["success"])
        self.assertTrue(os.path.exists(png_path))

    def test_block_diagram_compilation(self):
        mmd = """block
columns 3
  db[("Database")]
  service["Auth Service"]
  cache(("Redis Cache"))
  block:workerGroup:2
    columns 2
    w1["Worker 1"]
    w2["Worker 2"]
  end
  space
  metrics["Prometheus"]
  service --> db
  service --> cache
"""
        dtype, diag = parse_mermaid(mmd)
        self.assertEqual(dtype, DiagramType.BLOCK)
        self.assertEqual(diag.columns, 3)

        vsdx_path = os.path.join(self.output_dir, "test_user_block.vsdx")
        compile_block_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        page_xml = self._get_page_xml(vsdx_path)
        self.assertIn("Block_db", page_xml)
        self.assertIn("Block_service", page_xml)
        self.assertIn("Block_cache", page_xml)
        self.assertIn("Container_workerGroup", page_xml)
        self.assertIn("Block_w1", page_xml)
        self.assertIn("Block_w2", page_xml)

        png_path = os.path.join(self.output_dir, "test_user_block.png")
        render_res = render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(render_res["success"])
        self.assertTrue(os.path.exists(png_path))


if __name__ == "__main__":
    unittest.main()
