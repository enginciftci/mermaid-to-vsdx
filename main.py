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
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        raw_code = f.read()

    mermaid_code = extract_mermaid_from_markdown(raw_code)
    if mermaid_code != raw_code.strip():
        print(f"✓ Markdown Document: Code block successfully extracted ({len(mermaid_code.splitlines())} lines).")

    # Turkish / Unicode character analysis
    tr_info = verify_turkish_chars(mermaid_code)
    if tr_info["has_turkish"]:
        print(f"✓ Unicode/Turkish Character Check: {tr_info['total_turkish_chars']} characters verified.")

    output_path = args.output or os.path.splitext(input_file)[0] + ".vsdx"
    output_path = os.path.abspath(output_path)

    engine_desc = "Headless OPC Compiler (Native)" if args.engine == "native" else "Visio COM Automation"
    print(f"Parsing Mermaid diagram and compiling to Visio ({engine_desc})...")
    diag_type, vsdx_path = convert_mermaid_to_visio(
        mermaid_code=mermaid_code,
        output_vsdx_path=output_path,
        palette_name=args.palette,
        font_name=args.font,
        engine=args.engine,
    )
    print(f"✓ Visio diagram successfully created: {vsdx_path}")

    if args.verify or args.screenshot:
        screenshot_target = args.screenshot if args.screenshot else None
        print("Running visual verification (capturing Visio canvas)...")
        try:
            res = verify_and_capture_visio(
                vsdx_path=vsdx_path,
                output_image_path=screenshot_target,
                verification_dir=args.verification_dir
            )
            print(f"✓ Visual Verification Successful:")
            print(f"   Screenshot   : {res['image_path']}")
            print(f"   Resolution   : {res['width']}x{res['height']} pixels")
            print(f"   File Size    : {res['file_size_kb']} KB")
            print(f"   Render Time  : {res['render_time_sec']} seconds")
        except Exception as ver_err:
            print(f"ℹ Visual verification skipped: {ver_err}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Mermaid to Microsoft Visio (.vsdx) Converter - Professional Edition"
    )
    parser.add_argument("input_pos", nargs="?", metavar="input", help="Path to input Mermaid (.mmd, .txt, .md) file. If omitted, desktop GUI opens.")
    parser.add_argument("-i", "--input", dest="input_opt", help="Path to input Mermaid (.mmd, .txt, .md) file.")
    parser.add_argument("-o", "--output", help="Path to destination .vsdx file.")
    parser.add_argument("-p", "--palette", default=DEFAULT_PALETTE_NAME, choices=list(PALETTES.keys()), help="Color palette theme.")
    parser.add_argument("-f", "--font", default=DEFAULT_FONT, help="Unicode font family (Segoe UI, Calibri, Arial).")
    parser.add_argument("--engine", default="native", choices=["native", "com"], help="Conversion engine: 'native' (100% headless, zero Visio required) or 'com' (Visio COM automation).")
    parser.add_argument("--verify", action="store_true", help="Opens drawing in Visio to verify layout and export high-resolution PNG screenshot.")
    parser.add_argument("-s", "--screenshot", help="Custom output path for the verification screenshot PNG.")
    parser.add_argument("--verification-dir", default="verification_output", help="Directory where verification screenshots will be saved.")

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
