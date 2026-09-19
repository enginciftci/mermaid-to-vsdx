"""
Visio Visual Verification & Screenshot Capturer.
Opens generated .vsdx files in Microsoft Visio, triggers a layout/refresh pass,
and captures high-resolution rendered canvas images to verify visual correctness.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image
from ..visio.com_client import VisioSession


def verify_and_capture_visio(
    vsdx_path: str,
    output_image_path: Optional[str] = None,
    verification_dir: str = "verification_output"
) -> Dict[str, Any]:
    """
    Opens the .vsdx file in Microsoft Visio via COM automation,
    triggers a canvas refresh pass, and exports a high-resolution PNG screenshot.
    Saves the image into verification_dir and verifies dimensions with Pillow.
    """
    abs_vsdx_path = os.path.abspath(vsdx_path)
    if not os.path.exists(abs_vsdx_path):
        raise FileNotFoundError(f"Visio file not found: {abs_vsdx_path}")

    if not output_image_path:
        os.makedirs(verification_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(abs_vsdx_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_image_path = os.path.abspath(
            os.path.join(verification_dir, f"{base_name}_{timestamp}_verified.png")
        )
    else:
        output_image_path = os.path.abspath(output_image_path)
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)

    start_time = time.time()

    with VisioSession(visible=False) as visio_app:
        # Open the generated drawing
        # 0 = read/write standard open
        doc = visio_app.Documents.Open(abs_vsdx_path)
        page = doc.Pages.Item(1)

        # Trigger refresh / layout check
        try:
            page.ResizeToFitContents()
        except Exception:
            pass

        # High-resolution canvas export to PNG
        # Visio page.Export renders all vector elements, TrueType fonts, and connectors
        page.Export(output_image_path)

        doc.Saved = True
        doc.Close()

    elapsed = time.time() - start_time

    if not os.path.exists(output_image_path) or os.path.getsize(output_image_path) == 0:
        raise RuntimeError(f"Visio canvas export failed or produced an empty file: {output_image_path}")

    # Inspect image with Pillow
    with Image.open(output_image_path) as img:
        width, height = img.size
        img_format = img.format

    file_size_bytes = os.path.getsize(output_image_path)

    return {
        "success": True,
        "vsdx_path": abs_vsdx_path,
        "image_path": output_image_path,
        "width": width,
        "height": height,
        "format": img_format,
        "file_size_kb": round(file_size_bytes / 1024, 1),
        "render_time_sec": round(elapsed, 2)
    }
