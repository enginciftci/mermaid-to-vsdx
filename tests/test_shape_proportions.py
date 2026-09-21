"""
Tests verifying shape proportions, aspect ratios, and geometric fidelity
for cylinder, asymmetric, parallelogram, and trapezoid flowchart shapes.
"""

import os
import unittest
import zipfile
import xml.etree.ElementTree as ET

from mermaid_to_vsdx.parser.ast_nodes import ShapeType
from mermaid_to_vsdx.parser.flowchart_parser import FlowchartParser
from mermaid_to_vsdx.compiler.flowchart_compiler import compile_flowchart_to_vsdx
from mermaid_to_vsdx.verifier.native_renderer import render_vsdx_to_png


class TestShapeProportionsAndGeometry(unittest.TestCase):
    def setUp(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_page_xml(self, vsdx_path: str) -> str:
        with zipfile.ZipFile(vsdx_path, "r") as zf:
            for name in zf.namelist():
                if "page1.xml" in name:
                    return zf.read(name).decode("utf-8")
        return ""

    def test_cylinder_proportions_and_geometry(self):
        code = """flowchart TD
    cache[(Local cache)]"""
        diag = FlowchartParser().parse(code)
        self.assertIn("cache", diag.nodes)
        self.assertEqual(diag.nodes["cache"].shape, ShapeType.CYLINDER)

        vsdx_path = os.path.join(self.output_dir, "test_cylinder_proportions.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        xml_str = self._get_page_xml(vsdx_path)
        root = ET.fromstring(xml_str)
        shape_elem = None
        for s in root.findall(".//{*}Shape"):
            if s.attrib.get("NameU") == "Node_cache":
                shape_elem = s
                break

        self.assertIsNotNone(shape_elem, "Node_cache shape not found in XML")
        cells = {c.attrib.get("N"): (c.attrib.get("V"), c.attrib.get("F")) for c in shape_elem.findall("{*}Cell")}

        width = float(cells["Width"][0])
        height = float(cells["Height"][0])

        # Height must be at least 1.05 inches and aspect ratio should be <= 1.8
        self.assertGreaterEqual(height, 1.05, f"Cylinder height too small: {height}")
        aspect_ratio = width / height
        self.assertLessEqual(aspect_ratio, 1.80, f"Cylinder aspect ratio too flat: {aspect_ratio}")

        # TxtPinY should center inside the straight barrel
        txt_piny_cell = cells.get("TxtPinY")
        self.assertIsNotNone(txt_piny_cell)
        self.assertEqual(txt_piny_cell[1], "Height*0.48")

        # EllipticalArcTo row must have dynamic D formula
        geom_sec = shape_elem.find(".//{*}Section[@N='Geometry']")
        self.assertIsNotNone(geom_sec)
        d_found = False
        for r in geom_sec.findall("{*}Row"):
            if r.attrib.get("T") == "EllipticalArcTo":
                for c in r.findall("{*}Cell"):
                    if c.attrib.get("N") == "D" and c.attrib.get("F") == "(Height*0.14)/(Width*0.5)":
                        d_found = True
        self.assertTrue(d_found, "Dynamic eccentricity formula not found on cylinder EllipticalArcTo row")

        # Verify headless native rendering works for cylinder
        png_path = os.path.join(self.output_dir, "test_cylinder_preview.png")
        render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(os.path.exists(png_path))
        self.assertGreater(os.path.getsize(png_path), 500)

    def test_asymmetric_shape_geometry(self):
        code = """flowchart LR
    id1>This is the text in the box]"""
        diag = FlowchartParser().parse(code)
        self.assertIn("id1", diag.nodes)
        self.assertEqual(diag.nodes["id1"].shape, ShapeType.ASYMMETRIC)

        vsdx_path = os.path.join(self.output_dir, "test_asymmetric_shape.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        xml_str = self._get_page_xml(vsdx_path)
        root = ET.fromstring(xml_str)
        shape_elem = None
        for s in root.findall(".//{*}Shape"):
            if s.attrib.get("NameU") == "Node_id1":
                shape_elem = s
                break

        self.assertIsNotNone(shape_elem)
        cells = {c.attrib.get("N"): (c.attrib.get("V"), c.attrib.get("F")) for c in shape_elem.findall("{*}Cell")}
        height = float(cells["Height"][0])
        self.assertGreaterEqual(height, 0.90, f"Asymmetric shape height too squashed: {height}")

        # TxtPinX should be centered in the rectangular body
        self.assertEqual(cells["TxtPinX"][1], "Width*0.44")

        # Check vertex coordinates: apex must be on the right (Width*1, Height*0.5)
        geom_sec = shape_elem.find(".//{*}Section[@N='Geometry']")
        rows = geom_sec.findall("{*}Row")
        # Row 3 is LineTo Width*1, Height*0.5
        row3_cells = {c.attrib.get("N"): c.attrib.get("F") for c in rows[2].findall("{*}Cell")}
        self.assertEqual(row3_cells.get("X"), "Width*1")
        self.assertEqual(row3_cells.get("Y"), "Height*0.5")

        # Row 1 is MoveTo (0, 0), Row 5 is LineTo (0, Height*1), Row 6 is back to (0, 0) -> Left is flat vertical
        row1_cells = {c.attrib.get("N"): c.attrib.get("F") for c in rows[0].findall("{*}Cell")}
        row5_cells = {c.attrib.get("N"): c.attrib.get("F") for c in rows[4].findall("{*}Cell")}
        self.assertEqual(row1_cells.get("X"), "Width*0")
        self.assertEqual(row5_cells.get("X"), "Width*0")

        # Verify headless native rendering
        png_path = os.path.join(self.output_dir, "test_asymmetric_preview.png")
        render_vsdx_to_png(vsdx_path, png_path)
        self.assertTrue(os.path.exists(png_path))
        self.assertGreater(os.path.getsize(png_path), 500)

    def test_parallelogram_and_parallelogram_alt(self):
        code = """flowchart TD
    p1[/Forward slant/]
    p2[\\Backward slant\\]"""
        diag = FlowchartParser().parse(code)
        self.assertEqual(diag.nodes["p1"].shape, ShapeType.PARALLELOGRAM)
        self.assertEqual(diag.nodes["p2"].shape, ShapeType.PARALLELOGRAM_ALT)

        vsdx_path = os.path.join(self.output_dir, "test_parallelograms.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))

        xml_str = self._get_page_xml(vsdx_path)
        root = ET.fromstring(xml_str)

        # Check p1: [/ /] -> top shifted left (0, Height*1), bottom shifted right (Width*0.22, 0)
        s1 = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Node_p1")
        g1_rows = s1.find(".//{*}Section[@N='Geometry']").findall("{*}Row")
        r1_cells = {c.attrib.get("N"): c.attrib.get("F") for c in g1_rows[0].findall("{*}Cell")}
        r4_cells = {c.attrib.get("N"): c.attrib.get("F") for c in g1_rows[3].findall("{*}Cell")}
        self.assertEqual(r1_cells.get("X"), "Width*0.22")  # bottom-left shifted right
        self.assertEqual(r4_cells.get("X"), "Width*0")     # top-left at 0

        # Check p2: [\ \] -> top shifted right (Width*0.22, Height*1), bottom-left at 0
        s2 = next(s for s in root.findall(".//{*}Shape") if s.attrib.get("NameU") == "Node_p2")
        g2_rows = s2.find(".//{*}Section[@N='Geometry']").findall("{*}Row")
        r1_cells = {c.attrib.get("N"): c.attrib.get("F") for c in g2_rows[0].findall("{*}Cell")}
        r4_cells = {c.attrib.get("N"): c.attrib.get("F") for c in g2_rows[3].findall("{*}Cell")}
        self.assertEqual(r1_cells.get("X"), "Width*0")     # bottom-left at 0
        self.assertEqual(r4_cells.get("X"), "Width*0.22")  # top-left shifted right

    def test_trapezoid_and_trapezoid_alt(self):
        code = """flowchart TD
    t1[/Standard trapezoid\\]
    t2[\\Inverted trapezoid/]"""
        diag = FlowchartParser().parse(code)
        self.assertEqual(diag.nodes["t1"].shape, ShapeType.TRAPEZOID)
        self.assertEqual(diag.nodes["t2"].shape, ShapeType.TRAPEZOID_ALT)

        vsdx_path = os.path.join(self.output_dir, "test_trapezoids.vsdx")
        compile_flowchart_to_vsdx(diag, vsdx_path)
        self.assertTrue(os.path.exists(vsdx_path))


if __name__ == "__main__":
    unittest.main()
