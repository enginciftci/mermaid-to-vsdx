"""
Main entry point for Mermaid to Microsoft Visio Converter.
Supports both Desktop GUI mode and Headless CLI mode.
"""

import sys
import os

# Add src to sys.path to enable running directly from cloned repo root
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from mermaid_to_vsdx.cli import main, run_cli

if __name__ == "__main__":
    main()
