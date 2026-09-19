"""
Main entry point for Mermaid to Microsoft Visio Converter.
Supports both Desktop GUI mode and Headless CLI mode.
"""

import sys
import os
import argparse

# Ensure UTF-8 output across Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure src is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser import extract_mermaid_from_markdown
from src.visio import convert_mermaid_to_visio, DEFAULT_PALETTE_NAME, PALETTES
from src.verifier import verify_and_capture_visio
from src.utils.unicode_helper import DEFAULT_FONT, verify_turkish_chars


def run_cli(args):
    """
    Headless command-line conversion and verification mode.
    """
    input_file = os.path.abspath(args.input)
    if not os.path.exists(input_file):
        print(f"Hata: Girdi dosyası bulunamadı: {input_file}", file=sys.stderr)
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        raw_code = f.read()

    mermaid_code = extract_mermaid_from_markdown(raw_code)
    if mermaid_code != raw_code.strip():
        print(f"✓ Markdown Belgesi: Kod bloğu başarıyla ayıklandı ({len(mermaid_code.splitlines())} satır).")

    # Turkish character analysis
    tr_info = verify_turkish_chars(mermaid_code)
    if tr_info["has_turkish"]:
        print(f"✓ Türkçe Karakter Tespiti: {tr_info['total_turkish_chars']} adet Türkçe karakter doğrulandı.")

    output_path = args.output or os.path.splitext(input_file)[0] + ".vsdx"
    output_path = os.path.abspath(output_path)

    engine_desc = "Headless OPC Derleyici (Native)" if args.engine == "native" else "Visio COM Otomasyonu"
    print(f"Mermaid şeması ayrıştırılıyor ve Visio'ya aktarılıyor ({engine_desc})...")
    diag_type, vsdx_path = convert_mermaid_to_visio(
        mermaid_code=mermaid_code,
        output_vsdx_path=output_path,
        palette_name=args.palette,
        font_name=args.font,
        engine=args.engine,
    )
    print(f"✓ Visio dosyası başarıyla oluşturuldu: {vsdx_path}")

    if args.verify or args.screenshot:
        screenshot_target = args.screenshot if args.screenshot else None
        print(f"Görsel doğrulama çalıştırılıyor (Visio tuval görüntüsü alınıyor)...")
        try:
            res = verify_and_capture_visio(
                vsdx_path=vsdx_path,
                output_image_path=screenshot_target,
                verification_dir=args.verification_dir
            )
            print(f"✓ Görsel Doğrulama Başarılı:")
            print(f"   Ekran Görüntüsü : {res['image_path']}")
            print(f"   Çözünürlük      : {res['width']}x{res['height']} piksel")
            print(f"   Dosya Boyutu    : {res['file_size_kb']} KB")
            print(f"   İşlem Süresi    : {res['render_time_sec']} saniye")
        except Exception as ver_err:
            print(f"ℹ Görsel doğrulama atlandı: {ver_err}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Mermaid to Microsoft Visio (.vsdx) Converter - Professional Edition"
    )
    parser.add_argument("input_pos", nargs="?", metavar="input", help="Girdi Mermaid (.mmd, .txt) dosyası yolu. Boş bırakılırsa grafik arayüz (GUI) açılır.")
    parser.add_argument("-i", "--input", dest="input_opt", help="Girdi Mermaid (.mmd, .txt) dosyası yolu.")
    parser.add_argument("-o", "--output", help="Çıktı .vsdx dosya yolu.")
    parser.add_argument("-p", "--palette", default=DEFAULT_PALETTE_NAME, choices=list(PALETTES.keys()), help="Renk paleti teması.")
    parser.add_argument("-f", "--font", default=DEFAULT_FONT, help="Kullanılacak Unicode yazı tipi (Segoe UI, Calibri, Arial).")
    parser.add_argument("--engine", default="native", choices=["native", "com"], help="Dönüştürme motoru: 'native' (100%% headless, Visio gerektirmez) veya 'com' (Visio COM otomasyonu).")
    parser.add_argument("--verify", action="store_true", help="Oluşturulan çizimi Visio'da açıp yüksek çözünürlüklü doğrulama ekran görüntüsü alır.")
    parser.add_argument("-s", "--screenshot", help="Doğrulama ekran görüntüsünün kaydedileceği özel dosya yolu.")
    parser.add_argument("--verification-dir", default="verification_output", help="Doğrulama ekran görüntülerinin kaydedileceği klasör.")

    args = parser.parse_args()
    args.input = args.input_opt or args.input_pos

    if args.input:
        run_cli(args)
    else:
        # Launch GUI
        from src.gui import MermaidVisioApp
        app = MermaidVisioApp()
        app.mainloop()


if __name__ == "__main__":
    main()
