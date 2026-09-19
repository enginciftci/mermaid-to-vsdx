"""
Unit tests for Mermaid Flowchart and Sequence Diagram AST Parsers.
"""

import unittest
from src.parser import (
    parse_mermaid, DiagramType, ShapeType, EdgeStyle, ArrowType,
    MessageArrow, MermaidParseError, FlowchartParser, SequenceParser
)


class TestFlowchartParser(unittest.TestCase):

    def test_basic_flowchart(self):
        code = """graph TD
            A[Başlangıç] --> B(İşlem)
            B --> C{Karar}
            C -->|Evet| D[(Veritabanı)]
            C -->|Hayır| E([Bitiş])
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(dtype, DiagramType.FLOWCHART)
        self.assertEqual(diagram.direction, "TD")
        self.assertEqual(len(diagram.nodes), 5)
        self.assertEqual(len(diagram.edges), 4)

        # Check shapes
        self.assertEqual(diagram.nodes["A"].shape, ShapeType.RECTANGLE)
        self.assertEqual(diagram.nodes["B"].shape, ShapeType.ROUNDED)
        self.assertEqual(diagram.nodes["C"].shape, ShapeType.DIAMOND)
        self.assertEqual(diagram.nodes["D"].shape, ShapeType.CYLINDER)
        self.assertEqual(diagram.nodes["E"].shape, ShapeType.STADIUM)

        # Check Turkish labels
        self.assertEqual(diagram.nodes["A"].label, "Başlangıç")
        self.assertEqual(diagram.nodes["B"].label, "İşlem")
        self.assertEqual(diagram.nodes["D"].label, "Veritabanı")

    def test_flowchart_edge_types(self):
        code = """flowchart LR
            A --> B
            B --- C
            C -.-> D
            D ==> E
            E -- Onaylandı --> F
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(diagram.direction, "LR")
        self.assertEqual(len(diagram.edges), 5)

        self.assertEqual(diagram.edges[0].style, EdgeStyle.SOLID)
        self.assertEqual(diagram.edges[0].arrow_end, ArrowType.ARROW)

        self.assertEqual(diagram.edges[1].style, EdgeStyle.SOLID)
        self.assertEqual(diagram.edges[1].arrow_end, ArrowType.NONE)

        self.assertEqual(diagram.edges[2].style, EdgeStyle.DOTTED)
        self.assertEqual(diagram.edges[2].arrow_end, ArrowType.ARROW)

        self.assertEqual(diagram.edges[3].style, EdgeStyle.THICK)
        self.assertEqual(diagram.edges[3].arrow_end, ArrowType.ARROW)

        self.assertEqual(diagram.edges[4].label, "Onaylandı")

    def test_subgraphs(self):
        code = """graph TD
            subgraph MUSTERI ["Müşteri İşlemleri"]
                A[Giriş Yap] --> B[Sepete Ekle]
            end
            subgraph ODEME ["Ödeme Sistemi"]
                C[Kredi Kartı] --> D[(Banka)]
            end
            B --> C
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(len(diagram.subgraphs), 2)
        self.assertEqual(diagram.subgraphs[0].title, "Müşteri İşlemleri")
        self.assertIn("A", diagram.subgraphs[0].node_ids)
        self.assertIn("B", diagram.subgraphs[0].node_ids)
        self.assertEqual(diagram.subgraphs[1].title, "Ödeme Sistemi")
        self.assertIn("C", diagram.subgraphs[1].node_ids)
        self.assertIn("D", diagram.subgraphs[1].node_ids)


class TestSequenceParser(unittest.TestCase):

    def test_sequence_diagram(self):
        code = """sequenceDiagram
            autonumber
            title Güvenli Giriş Akışı
            actor K as Kullanıcı
            participant S as Sunucu
            participant DB as Veritabanı

            K->>S: Giriş İsteği Gönder (ç, ğ, ı, ö, ş, ü)
            S->>DB: Şifre Sorgula
            DB-->>S: Onay Verildi
            Note over S,DB: Güvenlik Kontrolü
            S-->>K: Giriş Başarılı (JWT)
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(dtype, DiagramType.SEQUENCE)
        self.assertEqual(diagram.title, "Güvenli Giriş Akışı")
        self.assertEqual(len(diagram.participants), 3)

        # Check participants
        self.assertEqual(diagram.participants[0].id, "K")
        self.assertEqual(diagram.participants[0].label, "Kullanıcı")
        self.assertTrue(diagram.participants[0].is_actor)

        self.assertEqual(diagram.participants[1].id, "S")
        self.assertEqual(diagram.participants[1].label, "Sunucu")

        # Check items (messages + notes)
        self.assertEqual(len(diagram.items), 5)
        self.assertEqual(diagram.items[0].text, "Giriş İsteği Gönder (ç, ğ, ı, ö, ş, ü)")
        self.assertEqual(diagram.items[0].arrow_type, MessageArrow.SOLID_ARROW)
        self.assertEqual(diagram.items[2].arrow_type, MessageArrow.DOTTED_ARROW)


class TestClassParser(unittest.TestCase):

    def test_class_diagram_parsing(self):
        code = """classDiagram
            class OdemeServisi {
                <<interface>>
                +String ad
                +odemeYap(tutar) bool
            }
            class KrediKarti {
                -String kartNo
                +odemeYap(tutar) bool
            }
            class Musteri
            OdemeServisi <|.. KrediKarti : uygular
            Musteri "1" --> "*" KrediKarti : sahiptir
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(dtype, DiagramType.CLASS_DIAGRAM)
        self.assertEqual(len(diagram.classes), 3)
        self.assertIn("OdemeServisi", diagram.classes)
        self.assertIn("KrediKarti", diagram.classes)
        self.assertIn("Musteri", diagram.classes)

        # Check OdemeServisi interface
        cls_odeme = diagram.classes["OdemeServisi"]
        self.assertEqual(cls_odeme.annotation, "<<interface>>")
        self.assertEqual(len(cls_odeme.members), 2)
        self.assertFalse(cls_odeme.members[0].is_method)
        self.assertEqual(cls_odeme.members[0].name, "ad")
        self.assertEqual(cls_odeme.members[0].return_type, "String")
        self.assertTrue(cls_odeme.members[1].is_method)
        self.assertEqual(cls_odeme.members[1].name, "odemeYap")

        # Check relationships
        self.assertEqual(len(diagram.relationships), 2)
        rel1 = diagram.relationships[0]
        self.assertEqual(rel1.source_name, "OdemeServisi")
        self.assertEqual(rel1.target_name, "KrediKarti")
        self.assertEqual(rel1.label, "uygular")

        rel2 = diagram.relationships[1]
        self.assertEqual(rel2.source_name, "Musteri")
        self.assertEqual(rel2.target_name, "KrediKarti")
        self.assertEqual(rel2.multiplicity_source, "1")
        self.assertEqual(rel2.multiplicity_target, "*")


class TestMarkdownExtractor(unittest.TestCase):

    def test_markdown_code_fence_extraction(self):
        md_text = """# Sistem Mimarisi Raporu
        Aşağıda sistem akışı gösterilmektedir:

        ```mermaid
        flowchart TD
            A[Giriş] --> B[Çıkış]
        ```

        Raporun sonu.
        """
        dtype, diagram = parse_mermaid(md_text)
        self.assertEqual(dtype, DiagramType.FLOWCHART)
        self.assertEqual(len(diagram.nodes), 2)
        self.assertEqual(diagram.nodes["A"].label, "Giriş")
        self.assertEqual(diagram.nodes["B"].label, "Çıkış")


class TestStateParser(unittest.TestCase):

    def test_state_diagram_parsing(self):
        code = """stateDiagram-v2
            direction LR
            [*] --> Idle: Sistem Başlatıldı
            Idle --> Processing: İstek Geldi
            Processing --> Success: Onaylandı
            Processing --> Failed: Hata Oluştu
            Failed --> Idle: Tekrar Dene
            Success --> [*]: İşlem Tamam
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(dtype, DiagramType.STATE_DIAGRAM)
        self.assertEqual(diagram.direction, "LR")
        self.assertIn("Idle", diagram.states)
        self.assertIn("Processing", diagram.states)
        self.assertIn("Success", diagram.states)
        self.assertIn("Failed", diagram.states)
        self.assertEqual(len(diagram.transitions), 6)
        self.assertEqual(diagram.transitions[0].event, "Sistem Başlatıldı")
        self.assertEqual(diagram.transitions[1].event, "İstek Geldi")


class TestERParser(unittest.TestCase):

    def test_er_diagram_parsing(self):
        code = """erDiagram
            CUSTOMER ||--o{ ORDER : places
            ORDER ||--|{ LINE-ITEM : contains
            CUSTOMER }|..|{ DELIVERY-ADDRESS : uses

            CUSTOMER {
                string id PK
                string name
                string email
            }
            ORDER {
                int orderNumber PK
                string customerId FK
                datetime orderDate
            }
            LINE-ITEM {
                string itemId PK
                int quantity
                float price
            }
        """
        dtype, diagram = parse_mermaid(code)
        self.assertEqual(dtype, DiagramType.ER_DIAGRAM)
        self.assertEqual(len(diagram.entities), 4)
        self.assertIn("CUSTOMER", diagram.entities)
        self.assertIn("ORDER", diagram.entities)
        self.assertIn("LINE-ITEM", diagram.entities)
        self.assertIn("DELIVERY-ADDRESS", diagram.entities)

        cust = diagram.entities["CUSTOMER"]
        self.assertEqual(len(cust.attributes), 3)
        self.assertTrue(cust.attributes[0].is_pk)
        self.assertEqual(cust.attributes[0].name, "id")
        self.assertEqual(cust.attributes[0].attr_type, "string")

        order = diagram.entities["ORDER"]
        self.assertEqual(len(order.attributes), 3)
        self.assertTrue(order.attributes[0].is_pk)
        self.assertTrue(order.attributes[1].is_fk)

        self.assertEqual(len(diagram.relationships), 3)
        self.assertEqual(diagram.relationships[0].entity1, "CUSTOMER")
        self.assertEqual(diagram.relationships[0].entity2, "ORDER")
        self.assertEqual(diagram.relationships[0].role, "places")
        self.assertEqual(diagram.relationships[0].cardinality, "||--o{")


if __name__ == "__main__":
    unittest.main()
