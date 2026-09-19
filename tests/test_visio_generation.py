"""
Integration tests for Visio generation and verification screenshot capture.
"""

import os
import unittest
from PIL import Image
from src.visio import convert_mermaid_to_visio, is_visio_installed
from src.verifier import verify_and_capture_visio


class TestVisioGeneration(unittest.TestCase):

    @unittest.skipUnless(is_visio_installed(), "Microsoft Visio is not installed on this system")
    def test_flowchart_generation_and_verification(self):
        code = """graph TD
            A([Türkçe Başlangıç]) --> B[İşlem: Çağdaş Yazılım]
            B --> C{Şart: Onaylandı mı?}
            C -->|Evet: çğıöşü| D[(Güvenli Veritabanı)]
            C -->|Hayır: ÇĞİÖŞÜ| E([İşlemi Sonlandır])
        """
        out_vsdx = os.path.abspath("output/test_flowchart.vsdx")
        out_img = os.path.abspath("verification_output/test_flowchart_verified.png")

        # 1. Convert to Visio vsdx
        diag_type, path = convert_mermaid_to_visio(
            mermaid_code=code,
            output_vsdx_path=out_vsdx,
            palette_name="Modern Corporate (Blue & Slate)"
        )

        self.assertTrue(os.path.exists(path), f"Output .vsdx does not exist at {path}")
        self.assertGreater(os.path.getsize(path), 1000, "Generated .vsdx file is too small.")

        # 2. Visual Verification and Screenshot Capture
        ver_res = verify_and_capture_visio(
            vsdx_path=path,
            output_image_path=out_img
        )

        self.assertTrue(ver_res["success"])
        self.assertTrue(os.path.exists(out_img))
        self.assertGreater(os.path.getsize(out_img), 1000, "Verification image file is empty.")

        with Image.open(out_img) as img:
            self.assertGreater(img.width, 100)
            self.assertGreater(img.height, 100)

    @unittest.skipUnless(is_visio_installed(), "Microsoft Visio is not installed on this system")
    def test_sequence_generation_and_verification(self):
        code = """sequenceDiagram
            title Türkçe Yetkilendirme Protokolü
            actor K as Kullanıcı
            participant S as Kimlik Sunucusu
            K->>S: Şifreli Giriş Talebi (çğıöşü)
            S-->>K: Onay Jetonu İletildi (ÇĞİÖŞÜ)
            Note over K,S: 256-Bit SSL Bağlantısı
        """
        out_vsdx = os.path.abspath("output/test_sequence.vsdx")
        out_img = os.path.abspath("verification_output/test_sequence_verified.png")

        diag_type, path = convert_mermaid_to_visio(
            mermaid_code=code,
            output_vsdx_path=out_vsdx,
            palette_name="Emerald Tech (Mint & Teal)"
        )

        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)

        ver_res = verify_and_capture_visio(
            vsdx_path=path,
            output_image_path=out_img
        )

        self.assertTrue(ver_res["success"])
        self.assertTrue(os.path.exists(out_img))

        with Image.open(out_img) as img:
            self.assertGreater(img.width, 100)
            self.assertGreater(img.height, 100)

    @unittest.skipUnless(is_visio_installed(), "Microsoft Visio is not installed on this system")
    def test_grayscale_palette_conversion(self):
        code = """graph LR
            A[Girdi Verisi] --> B{Doğrulama}
            B -->|Başarılı| C[(Kalıcı Depo)]
            B -->|Hata| D([Geri Bildirim])
        """
        out_vsdx = os.path.abspath("output/test_grayscale.vsdx")
        out_img = os.path.abspath("verification_output/test_grayscale_verified.png")

        diag_type, path = convert_mermaid_to_visio(
            mermaid_code=code,
            output_vsdx_path=out_vsdx,
            palette_name="Grayscale Clean (Black & White)"
        )

        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)

        ver_res = verify_and_capture_visio(
            vsdx_path=path,
            output_image_path=out_img
        )

        self.assertTrue(ver_res["success"])
        self.assertTrue(os.path.exists(out_img))

    @unittest.skipUnless(is_visio_installed(), "Microsoft Visio is not installed on this system")
    def test_class_diagram_generation_and_verification(self):
        code = """classDiagram
            class PaymentProcessor {
                <<interface>>
                +String apiKey
                +processPayment(amount: float) bool
            }
            class StripeService {
                -String secretKey
                +processPayment(amount: float) bool
            }
            class BankTransferService {
                -String iban
                +processPayment(amount: float) bool
            }
            PaymentProcessor <|.. StripeService : Implements
            PaymentProcessor <|.. BankTransferService : Implements
        """
        out_vsdx = os.path.abspath("output/test_class_diag.vsdx")
        out_img = os.path.abspath("verification_output/test_class_diag_verified.png")

        diag_type, path = convert_mermaid_to_visio(
            mermaid_code=code,
            output_vsdx_path=out_vsdx,
            palette_name="Modern Corporate (Blue & Slate)"
        )

        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 1000)

        ver_res = verify_and_capture_visio(
            vsdx_path=path,
            output_image_path=out_img
        )

        self.assertTrue(ver_res["success"])
        self.assertTrue(os.path.exists(out_img))

        with Image.open(out_img) as img:
            self.assertGreater(img.width, 100)
            self.assertGreater(img.height, 100)


if __name__ == "__main__":
    unittest.main()
