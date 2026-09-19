"""
Headless unit and integration tests for Native Mermaid-to-Visio (.vsdx) OPC Compiler Engine.
Executes 100% headless without requiring Microsoft Visio or Windows COM Interop.
"""

import os
import zipfile
import xml.etree.ElementTree as ET
import unittest

from src.compiler import compile_mermaid_to_vsdx
from src.parser import DiagramType
from src.visio.palettes import PALETTES


class TestOpcCompiler(unittest.TestCase):
    """
    Test suite for headless OPC package creation, XML schema validity,
    and diagram AST compilation across Flowchart, Sequence, and Class diagrams.
    """

    def setUp(self):
        os.makedirs("output", exist_ok=True)

    def _assert_valid_vsdx_package(self, vsdx_path: str):
        """Validates that vsdx_path is a valid Open Packaging Conventions (OPC) archive."""
        self.assertTrue(os.path.exists(vsdx_path), f"File {vsdx_path} does not exist.")
        self.assertGreater(os.path.getsize(vsdx_path), 500, "VSDX package is too small.")

        required_parts = [
            "[Content_Types].xml",
            "_rels/.rels",
            "docProps/core.xml",
            "docProps/app.xml",
            "visio/document.xml",
            "visio/_rels/document.xml.rels",
            "visio/windows.xml",
            "visio/pages/pages.xml",
            "visio/pages/_rels/pages.xml.rels",
            "visio/pages/page1.xml",
        ]

        with zipfile.ZipFile(vsdx_path, "r") as z:
            names = z.namelist()
            for part in required_parts:
                self.assertIn(part, names, f"Required OPC part missing: {part}")

            # Validate that page1.xml is well-formed XML
            page_xml_bytes = z.read("visio/pages/page1.xml")
            root = ET.fromstring(page_xml_bytes)
            self.assertTrue(root.tag.endswith("PageContents"), f"Root tag was not PageContents: {root.tag}")

    def test_flowchart_native_compilation(self):
        """Tests pure headless compilation of Flowcharts with various node shapes and edge styles."""
        code = """graph TD
            A([Start: Müşteri Girişi]) --> B{Şart: Onaylandı mı?}
            B -->|Evet: çğıöşü| C[(Güvenli Veritabanı)]
            B -->|Hayır: ÇĞİÖŞÜ| D[[Hata Kaydı]]
            C --> E([İşlemi Sonlandır])
            D --> E
        """
        out_file = os.path.abspath("output/test_unit_flowchart.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Modern Corporate (Blue & Slate)")

        self.assertEqual(dtype, DiagramType.FLOWCHART)
        self.assertEqual(path, out_file)
        self._assert_valid_vsdx_package(out_file)

        # Inspect page1.xml contents
        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Müşteri Girişi", xml_str)
            self.assertIn("Onaylandı mı?", xml_str)
            self.assertIn("Güvenli Veritabanı", xml_str)
            self.assertIn("<Connects>", xml_str)
            self.assertIn("Dynamic connector", xml_str)
            self.assertIn("Connections.Bottom.X", xml_str)
            self.assertIn("Connections.Top.X", xml_str)
            self.assertIn("NoFill' V='1'", xml_str)

    def test_directional_connector_glue(self):
        """Verifies that connectors glue bottom-to-top in TD and right-to-left in LR with NoFill."""
        code_td = "graph TD\n  A([Source Box]) --> B([Target Box])"
        out_td = os.path.abspath("output/test_unit_glue_td.vsdx")
        compile_mermaid_to_vsdx(code_td, out_td)
        with zipfile.ZipFile(out_td, "r") as z:
            xml_td = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Connections.Bottom.X", xml_td)
            self.assertIn("Connections.Top.X", xml_td)
            self.assertIn("ToPart='101'", xml_td)
            self.assertIn("ToPart='100'", xml_td)
            self.assertIn("FillPattern' V='0'", xml_td)

        code_lr = "graph LR\n  A([Source Box]) --> B([Target Box])"
        out_lr = os.path.abspath("output/test_unit_glue_lr.vsdx")
        compile_mermaid_to_vsdx(code_lr, out_lr)
        with zipfile.ZipFile(out_lr, "r") as z:
            xml_lr = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Connections.Right.X", xml_lr)
            self.assertIn("Connections.Left.X", xml_lr)
            self.assertIn("ToPart='103'", xml_lr)
            self.assertIn("ToPart='102'", xml_lr)
            self.assertIn("FillPattern' V='0'", xml_lr)

    def test_subgraphs_native_compilation(self):
        """Tests compound subgraphs and container bounding boxes."""
        code = """flowchart TD
            subgraph Frontend [Ön Yüz Katmanı]
                A([React UI]) --> B([Next.js SSR])
            end
            subgraph Backend [Arka Yüz Katmanı]
                C{API Gateway} --> D[(PostgreSQL)]
            end
            A --> C
        """
        out_file = os.path.abspath("output/test_unit_subgraphs.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Oceanic Breeze (Teal & Cyan)")

        self.assertEqual(dtype, DiagramType.FLOWCHART)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Container_Frontend", xml_str)
            self.assertIn("Container_Backend", xml_str)
            self.assertIn("Container", xml_str)

    def test_sequence_native_compilation(self):
        """Tests sequence diagrams with participants, lifelines, messages, and notes."""
        code = """sequenceDiagram
            title Kimlik Doğrulama Süreci
            actor U as Kullanıcı
            participant S as Sunucu
            participant D as Veritabanı
            U->>S: Giriş Talebi (çğıöşü)
            S->>D: Bilgi Sorgusu
            D-->>S: Onay Sonucu
            Note over S,D: Güvenli Kanal
            S-->>U: Hoşgeldiniz (ÇĞİÖŞÜ)
        """
        out_file = os.path.abspath("output/test_unit_sequence.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Minimalist Pastel")

        self.assertEqual(dtype, DiagramType.SEQUENCE)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Kimlik Doğrulama Süreci", xml_str)
            self.assertIn("Giriş Talebi (çğıöşü)", xml_str)
            self.assertIn("Güvenli Kanal", xml_str)
            # Empty connects block must be omitted for sequence diagrams
            self.assertNotIn("<Connects>", xml_str)

    def test_class_diagram_native_compilation(self):
        """Tests UML class diagrams with multi-compartment classes and relationship connectors."""
        code = """classDiagram
            class Vehicle {
                +String brand
                +int year
                +start() void
                +stop() void
            }
            class Car {
                +int doors
                +openTrunk() void
            }
            Vehicle <|-- Car
        """
        out_file = os.path.abspath("output/test_unit_class.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="High Contrast Dark Mode")

        self.assertEqual(dtype, DiagramType.CLASS_DIAGRAM)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Vehicle", xml_str)
            self.assertIn("Car", xml_str)
            self.assertIn("<Connects>", xml_str)

    def test_state_diagram_native_compilation(self):
        """Tests native headless compilation of State Diagrams with initial/terminal states."""
        code = """stateDiagram-v2
            [*] --> Hazir: Sistem Açıldı (çğıöşü)
            Hazir --> Calisiyor: Görev Başlat
            Calisiyor --> Duraklatildi: Durdur
            Duraklatildi --> Calisiyor: Devam Et
            Calisiyor --> [*]: Kapat
        """
        out_file = os.path.abspath("output/test_unit_state.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Oceanic Breeze (Teal & Cyan)")

        self.assertEqual(dtype, DiagramType.STATE_DIAGRAM)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("Hazir", xml_str)
            self.assertIn("Calisiyor", xml_str)
            self.assertIn("Sistem Açıldı", xml_str)
            self.assertIn("<Connects>", xml_str)
            self.assertIn("Dynamic connector", xml_str)

    def test_er_diagram_native_compilation(self):
        """Tests native headless compilation of Entity-Relationship Diagrams."""
        code = """erDiagram
            MUSTERI ||--o{ SIPARIS : verir
            SIPARIS ||--|{ URUN : icerir

            MUSTERI {
                string musteriNo PK
                string adSoyad
                string email
            }
            SIPARIS {
                int siparisId PK
                string musteriNo FK
                date siparisTarihi
            }
            URUN {
                string urunKodu PK
                float fiyat
            }
        """
        out_file = os.path.abspath("output/test_unit_er.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Forest Emerald (Green & Mint)")

        self.assertEqual(dtype, DiagramType.ER_DIAGRAM)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            self.assertIn("MUSTERI", xml_str)
            self.assertIn("SIPARIS", xml_str)
            self.assertIn("URUN", xml_str)
            self.assertIn("musteriNo PK", xml_str)
            self.assertIn("siparisId PK", xml_str)
            self.assertIn("<Connects>", xml_str)
            self.assertIn("Dynamic connector", xml_str)

    def test_grayscale_dark_background_white_font(self):
        """
        Verifies that in Grayscale Clean style, if font background is black or dark,
        the font face is white (#ffffff), while on white/light backgrounds it is black (#000000).
        """
        code = """flowchart TD
            subgraph SISTEM ["Güvenlik Sistemi"]
                A[Kullanıcı Girişi] --> B[İşlem Onayı]
            end
        """
        out_file = os.path.abspath("output/test_unit_grayscale_contrast.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name="Grayscale Clean (Black & White)")
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            xml_str = z.read("visio/pages/page1.xml").decode("utf-8")
            # Subgraph header has dark fill (#505050) -> font face must be white (#ffffff)
            self.assertIn("Header_SISTEM", xml_str)
            self.assertIn("FillForegnd' V='#505050'", xml_str)
            self.assertIn("Color' V='#ffffff'", xml_str)
            # Regular node A has pure white fill (#ffffff) -> font face must be black (#000000)
            self.assertIn("Node_A", xml_str)
            self.assertIn("Color' V='#000000'", xml_str)

    def test_all_palettes_compile(self):
        """Verifies that all 5 color palettes compile cleanly."""
        code = "graph TD\n  A([Start]) --> B[Step] --> C([End])"
        for p_name in PALETTES.keys():
            out_file = os.path.abspath(f"output/test_palette_{p_name[:4]}.vsdx")
            dtype, path = compile_mermaid_to_vsdx(code, out_file, palette_name=p_name)
            self._assert_valid_vsdx_package(out_file)


    def test_orthogonal_connector_geometry_and_cells(self):
        """Verifies that connectors have ShapeRouteStyle=1, ConFixedCode=0, PageSheet RouteStyle=1, and multi-segment orthogonal geometry."""
        code = """graph TD
            A[Root] --> B[Left Step]
            A --> C[Right Step]
        """
        out_file = os.path.abspath("output/test_unit_orthogonal_connectors.vsdx")
        dtype, path = compile_mermaid_to_vsdx(code, out_file)
        self._assert_valid_vsdx_package(out_file)

        with zipfile.ZipFile(out_file, "r") as z:
            page1_xml = z.read("visio/pages/page1.xml").decode("utf-8")
            pages_xml = z.read("visio/pages/pages.xml").decode("utf-8")

            # Verify PageSheet has RouteStyle=1
            self.assertIn("<Cell N=\"RouteStyle\" V=\"1\"/>", pages_xml)

            # Verify connector Shape has ShapeRouteStyle=1 and ConFixedCode=0
            self.assertIn("Cell N='ShapeRouteStyle' V='1'", page1_xml)
            self.assertIn("Cell N='ConFixedCode' V='0'", page1_xml)

            # Verify that connectors have orthogonal bend points (IX='3' and IX='4')
            self.assertIn("<Row T='MoveTo' IX='1'>", page1_xml)
            self.assertIn("<Row T='LineTo' IX='2'>", page1_xml)
            self.assertIn("<Row T='LineTo' IX='3'>", page1_xml)
            self.assertIn("<Row T='LineTo' IX='4'>", page1_xml)

    def test_native_vsdx_preview_renderer(self):
        """Verifies that the headless native Pillow renderer creates a valid PNG preview from a vsdx file without Visio."""
        from src.verifier import render_vsdx_to_png
        vsdx_path = os.path.abspath("output/test_unit_orthogonal_connectors.vsdx")
        out_png = os.path.abspath("output/test_unit_native_render.png")
        
        res = render_vsdx_to_png(vsdx_path, out_png)
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(out_png))
        self.assertGreater(res["width"], 100)
        self.assertGreater(res["height"], 100)
        self.assertGreater(res["file_size_kb"], 1.0)
        self.assertEqual(res["engine"], "native_pillow")

    def test_gui_and_cli_entrypoints(self):
        """Verifies that GUI classes import cleanly and CLI help parser succeeds."""
        from src.gui import MermaidVisioApp, I18n, LANGUAGES
        self.assertTrue(issubclass(MermaidVisioApp, object))
        self.assertTrue(hasattr(MermaidVisioApp, "_export_vsdx_direct"))
        self.assertTrue(hasattr(MermaidVisioApp, "_export_png_direct"))
        self.assertFalse(hasattr(MermaidVisioApp, "_toggle_theme"), "Dark theme toggle should be removed.")

        import subprocess
        res = subprocess.run(["python", "main.py", "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"main.py --help failed: {res.stderr}")
        self.assertIn("Mermaid to Microsoft Visio", res.stdout)

    def test_i18n_and_language_switching(self):
        """Verifies Turkish (tr) and English US (en) dictionary completeness and dynamic switching."""
        from src.gui.i18n import I18n, LANGUAGES, TRANSLATIONS

        self.assertIn("tr", LANGUAGES)
        self.assertIn("en", LANGUAGES)

        # Check that both language dictionaries have all required keys
        tr_keys = set(TRANSLATIONS["tr"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())

        missing_in_en = tr_keys - en_keys
        missing_in_tr = en_keys - tr_keys
        self.assertEqual(missing_in_en, set(), f"Missing English translations: {missing_in_en}")
        self.assertEqual(missing_in_tr, set(), f"Missing Turkish translations: {missing_in_tr}")

        # Test I18n manager
        i18n = I18n("tr")
        self.assertEqual(i18n.current_lang, "tr")
        self.assertIn("Visio'ya Dönüştür", i18n("btn_convert"))

        # Switch to English
        i18n.set_language("en")
        self.assertEqual(i18n.current_lang, "en")
        self.assertIn("Convert to Visio", i18n("btn_convert"))

        # Formatted string interpolation test
        interpolated_tr = i18n.get("visio_ready", ver="16.0")
        self.assertIn("16.0", interpolated_tr)


if __name__ == "__main__":
    unittest.main()


