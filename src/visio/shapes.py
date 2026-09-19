"""
Visio Shape geometries, styling, font assignment, and connector utilities.
"""

from typing import Tuple, List, Optional
import win32com.client
from .palettes import PaletteTheme, is_dark_color
from ..parser.ast_nodes import ShapeType, EdgeStyle, ArrowType
from ..utils.unicode_helper import clean_label_text, sanitize_visio_formula_string

# Visio Section and Row Constants
visSectionObject = 1
visSectionCharacter = 3
visCharacterFont = 0
visCharacterColor = 1
visCharacterStyle = 2
visCharacterSize = 7


def format_shape_text(
    shape,
    text: str,
    font_name: str = "Segoe UI",
    font_size_pt: int = 10,
    font_color_rgb: str = "RGB(15, 23, 42)",
    bold: bool = False,
    visio_app=None
):
    """
    Applies text and explicit Unicode font styling to a Visio shape.
    Guarantees Turkish characters (ç, ğ, ı, ö, ş, ü, etc.) are rendered with TrueType fonts.
    """
    cleaned_text = clean_label_text(text)
    shape.Text = cleaned_text

    # If font background (shape fill) is black or dark, font face should be white
    try:
        fill_val = str(shape.CellsU("FillForegnd").FormulaU).strip()
        if is_dark_color(fill_val):
            font_color_rgb = "RGB(255, 255, 255)"
    except Exception:
        pass

    # Try applying font ID from Visio application fonts if available
    if visio_app is not None:
        try:
            font_obj = visio_app.Fonts.Item(font_name)
            shape.Characters.CharProps(visCharacterFont, font_obj.ID)
        except Exception:
            try:
                # Fallback to Font() formula
                shape.CellsSRC(visSectionCharacter, 0, visCharacterFont).FormulaU = f'INDEX(0,Fonts("{font_name}"))'
            except Exception:
                pass
    else:
        try:
            shape.CellsSRC(visSectionCharacter, 0, visCharacterFont).FormulaU = f'INDEX(0,Fonts("{font_name}"))'
        except Exception:
            pass

    # Character formatting
    try:
        shape.CellsSRC(visSectionCharacter, 0, visCharacterSize).FormulaU = f"{font_size_pt} pt"
    except Exception:
        pass

    try:
        shape.CellsSRC(visSectionCharacter, 0, visCharacterColor).FormulaU = font_color_rgb
    except Exception:
        pass

    try:
        shape.CellsSRC(visSectionCharacter, 0, visCharacterStyle).FormulaU = "1" if bold else "0"
    except Exception:
        pass

    # Alignment & margins
    try:
        shape.CellsU("VerticalAlign").FormulaU = "1"  # Middle
    except Exception:
        pass

    try:
        shape.CellsU("Para.HorzAlign").FormulaU = "1"  # Center
        shape.CellsU("Para.IndFirst").FormulaU = "0 in"
        shape.CellsU("Para.IndLeft").FormulaU = "0 in"
        shape.CellsU("Para.IndRight").FormulaU = "0 in"
    except Exception:
        pass

    try:
        is_1d = bool(shape.OneD)
        if is_1d:
            shape.CellsU("TxtWidth").FormulaU = "TEXTWIDTH(TheText) + 16 pt"
            shape.CellsU("TxtHeight").FormulaU = "TEXTHEIGHT(TheText, TxtWidth)"
            shape.CellsU("TxtAngle").FormulaU = "0 deg"
        else:
            shape.CellsU("TxtPinX").FormulaU = "Width*0.5"
            shape.CellsU("TxtPinY").FormulaU = "Height*0.5"
            shape.CellsU("TxtLocPinX").FormulaU = "TxtWidth*0.5"
            shape.CellsU("TxtLocPinY").FormulaU = "TxtHeight*0.5"
            shape.CellsU("TxtWidth").FormulaU = "Width"
            shape.CellsU("TxtHeight").FormulaU = "Height"
    except Exception:
        pass

    try:
        shape.CellsU("LeftMargin").FormulaU = "4 pt"
        shape.CellsU("RightMargin").FormulaU = "4 pt"
        shape.CellsU("TopMargin").FormulaU = "4 pt"
        shape.CellsU("BottomMargin").FormulaU = "4 pt"
    except Exception:
        pass


def style_shape(
    shape,
    fill_rgb: str,
    border_rgb: str,
    line_weight_pt: float = 1.5,
    rounding_in: float = 0.1,
    line_pattern: int = 1
):
    """
    Applies fill, border color, line weight, and corner rounding to a shape.
    """
    try:
        shape.CellsU("FillForegnd").FormulaU = fill_rgb
        shape.CellsU("FillPattern").FormulaU = "1"  # Solid fill
    except Exception:
        pass

    try:
        shape.CellsU("LineColor").FormulaU = border_rgb
        shape.CellsU("LineWeight").FormulaU = f"{line_weight_pt} pt"
        shape.CellsU("LinePattern").FormulaU = str(line_pattern)  # 1=solid, 2=dashed
    except Exception:
        pass

    if rounding_in > 0:
        try:
            shape.CellsU("Rounding").FormulaU = f"{rounding_in:.2f} in"
        except Exception:
            pass


def draw_node_shape(
    page,
    shape_type: ShapeType,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    palette: PaletteTheme
):
    """
    Draws the corresponding geometry on the page based on the ShapeType.
    Returns the created Visio Shape object.
    """
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    width = x2 - x1
    height = y2 - y1

    if shape_type in (ShapeType.CIRCLE, ShapeType.ROUNDED):
        if shape_type == ShapeType.CIRCLE:
            # Equal aspect ratio circle
            dim = max(width, height)
            shape = page.DrawOval(cx - dim / 2.0, cy - dim / 2.0, cx + dim / 2.0, cy + dim / 2.0)
            style_shape(shape, palette.terminal_fill, palette.terminal_border, line_weight_pt=1.5, rounding_in=0)
        else:
            # Rounded rectangle
            shape = page.DrawRectangle(x1, y1, x2, y2)
            style_shape(shape, palette.default_fill, palette.default_border, line_weight_pt=1.5, rounding_in=0.15)

    elif shape_type == ShapeType.STADIUM:
        # Pill shape with full radius rounding
        shape = page.DrawRectangle(x1, y1, x2, y2)
        style_shape(shape, palette.terminal_fill, palette.terminal_border, line_weight_pt=1.5, rounding_in=height / 2.0)

    elif shape_type == ShapeType.DIAMOND:
        # 4-point Diamond (Rhombus)
        # Coordinates: top, right, bottom, left, top
        pts = [cx, y2, x2, cy, cx, y1, x1, cy, cx, y2]
        shape = page.DrawPolyline(pts, 0)
        style_shape(shape, palette.decision_fill, palette.decision_border, line_weight_pt=1.5, rounding_in=0.05)

    elif shape_type == ShapeType.CYLINDER:
        # Database cylinder
        shape = page.DrawRectangle(x1, y1, x2, y2)
        style_shape(shape, palette.database_fill, palette.database_border, line_weight_pt=1.5, rounding_in=0.1)

    elif shape_type == ShapeType.HEXAGON:
        # 6-point Hexagon
        dx = width * 0.2
        pts = [x1 + dx, y2, x2 - dx, y2, x2, cy, x2 - dx, y1, x1 + dx, y1, x1, cy, x1 + dx, y2]
        shape = page.DrawPolyline(pts, 0)
        style_shape(shape, palette.default_fill, palette.default_border, line_weight_pt=1.5, rounding_in=0)

    elif shape_type == ShapeType.PARALLELOGRAM:
        # Angled parallelogram
        dx = width * 0.18
        pts = [x1 + dx, y2, x2, y2, x2 - dx, y1, x1, y1, x1 + dx, y2]
        shape = page.DrawPolyline(pts, 0)
        style_shape(shape, palette.default_fill, palette.default_border, line_weight_pt=1.5, rounding_in=0)

    elif shape_type == ShapeType.SUBROUTINE:
        # Subroutine (Rectangle with inner vertical markers or clean border)
        shape = page.DrawRectangle(x1, y1, x2, y2)
        style_shape(shape, palette.default_fill, palette.default_border, line_weight_pt=2.0, rounding_in=0.05)

    else:
        # Standard Rectangle
        shape = page.DrawRectangle(x1, y1, x2, y2)
        style_shape(shape, palette.default_fill, palette.default_border, line_weight_pt=1.5, rounding_in=0.08)

    return shape


def draw_subgraph_container(
    page,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    title: str,
    palette: PaletteTheme,
    font_name: str = "Segoe UI",
    visio_app=None
):
    """
    Draws a container boundary for a Subgraph with a distinct header and dashed border.
    """
    container = page.DrawRectangle(x1, y1, x2, y2)
    style_shape(
        container,
        fill_rgb=palette.subgraph_fill,
        border_rgb=palette.subgraph_border,
        line_weight_pt=1.5,
        rounding_in=0.15,
        line_pattern=2  # Dashed line
    )

    # Title label at the top-left of the subgraph container
    if title:
        header_height = 0.42
        header_width = min(max(len(title) * 0.11 + 0.5, 2.2), (x2 - x1) - 0.2)
        header = page.DrawRectangle(
            x1 + 0.1,
            y2 - header_height - 0.05,
            x1 + 0.1 + header_width,
            y2 - 0.05
        )
        style_shape(
            header,
            fill_rgb=palette.subgraph_border,
            border_rgb=palette.subgraph_border,
            line_weight_pt=0.5,
            rounding_in=0.08
        )
        format_shape_text(
            header,
            title,
            font_name=font_name,
            font_size_pt=9,
            font_color_rgb="RGB(255, 255, 255)",
            bold=True,
            visio_app=visio_app
        )

    # Push container to back
    try:
        container.SendToBack()
    except Exception:
        pass

    return container


def connect_shapes(
    page,
    visio_app,
    shape_from,
    shape_to,
    label: str = "",
    style: EdgeStyle = EdgeStyle.SOLID,
    arrow_start: ArrowType = ArrowType.NONE,
    arrow_end: ArrowType = ArrowType.ARROW,
    palette: Optional[PaletteTheme] = None,
    font_name: str = "Segoe UI"
):
    """
    Connects shape_from and shape_to using a dynamically routed Visio connector.
    Applies custom line styling, arrowheads, and label formatting.
    """
    if palette is None:
        from .palettes import get_palette
        palette = get_palette()

    try:
        connector = page.Drop(visio_app.ConnectorToolDataObject, 0, 0)
    except Exception:
        # Fallback: draw 2-point line
        connector = page.DrawLine(0, 0, 1, 1)

    try:
        # Determine connection points based on relative positions
        src_py = float(shape_from.CellsU("PinY").ResultStr(0))
        dst_py = float(shape_to.CellsU("PinY").ResultStr(0))
        if dst_py < src_py - 0.1:
            connector.CellsU("BeginX").GlueTo(shape_from.CellsU("Connections.Bottom.X"))
            connector.CellsU("EndX").GlueTo(shape_to.CellsU("Connections.Top.X"))
        elif dst_py > src_py + 0.1:
            connector.CellsU("BeginX").GlueTo(shape_from.CellsU("Connections.Right.X"))
            connector.CellsU("EndX").GlueTo(shape_to.CellsU("Connections.Right.X"))
        else:
            connector.CellsU("BeginX").GlueTo(shape_from.CellsU("PinX"))
            connector.CellsU("EndX").GlueTo(shape_to.CellsU("PinX"))
    except Exception:
        try:
            connector.CellsU("BeginX").GlueTo(shape_from.CellsU("PinX"))
            connector.CellsU("EndX").GlueTo(shape_to.CellsU("PinX"))
        except Exception:
            pass

    # Line and fill styling (connectors are strictly NoFill)
    try:
        connector.CellsU("FillPattern").FormulaU = "0"
    except Exception:
        pass
    try:
        connector.CellsU("Geometry1.NoFill").FormulaU = "1"
    except Exception:
        pass
    try:
        connector.CellsU("LineColor").FormulaU = palette.connector_line
    except Exception:
        pass

    line_weight = "2.2 pt" if style == EdgeStyle.THICK else "1.3 pt"
    try:
        connector.CellsU("LineWeight").FormulaU = line_weight
    except Exception:
        pass

    line_pattern = "2" if style == EdgeStyle.DOTTED else "1"
    try:
        connector.CellsU("LinePattern").FormulaU = line_pattern
    except Exception:
        pass

    # Arrowheads (13 is standard clean arrowhead in Visio)
    try:
        if arrow_end == ArrowType.ARROW:
            connector.CellsU("EndArrow").FormulaU = "13"
            connector.CellsU("EndArrowSize").FormulaU = "2"
        else:
            connector.CellsU("EndArrow").FormulaU = "0"

        if arrow_start == ArrowType.ARROW:
            connector.CellsU("BeginArrow").FormulaU = "13"
            connector.CellsU("BeginArrowSize").FormulaU = "2"
        else:
            connector.CellsU("BeginArrow").FormulaU = "0"
    except Exception:
        pass

    # Edge label
    if label:
        format_shape_text(
            connector,
            label,
            font_name=font_name,
            font_size_pt=8,
            font_color_rgb=palette.connector_text,
            bold=False,
            visio_app=visio_app
        )
        # Clean white background for label readability over crossing lines without filling connector shape
        try:
            connector.CellsU("TextBkgnd").FormulaU = "RGB(255, 255, 255)"
        except Exception:
            try:
                connector.CellsU("TextBkgnd").FormulaU = "1"
            except Exception:
                pass
        try:
            connector.CellsU("FillPattern").FormulaU = "0"
            connector.CellsU("Geometry1.NoFill").FormulaU = "1"
        except Exception:
            pass

    return connector
