"""
Standards-compliant Open Packaging Conventions (OPC) packager.
Constructs and serializes a native Microsoft Visio (.vsdx) ZIP archive without external tools.
Supports both single-page and multi-page .vsdx documents as well as custom page background colors.
"""

import html
import os
import zipfile
from typing import Dict, List, Optional


def build_content_types_xml(num_pages: int = 1) -> str:
    page_overrides = "\n".join(
        f'  <Override PartName="/visio/pages/page{i}.xml" ContentType="application/vnd.ms-visio.page+xml"/>'
        for i in range(1, num_pages + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>
{page_overrides}
  <Override PartName="/visio/windows.xml" ContentType="application/vnd.ms-visio.windows+xml"/>
</Types>"""


def build_root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def build_core_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Diagram</dc:title>
  <dc:creator></dc:creator>
  <cp:lastModifiedBy></cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-09-19T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-19T00:00:00Z</dcterms:modified>
  <dc:language>en-US</dc:language>
</cp:coreProperties>"""


def build_app_props_xml(page_names: Optional[List[str]] = None) -> str:
    names = page_names or ["Page-1"]
    count = len(names)
    lpstrs = "".join(f"<vt:lpstr>{html.escape(n)}</vt:lpstr>" for n in names)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Visio</Application>
  <AppVersion>16.0000</AppVersion>
  <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Pages</vt:lpstr></vt:variant><vt:variant><vt:i4>{count}</vt:i4></vt:variant></vt:vector></HeadingPairs>
  <TitlesOfParts><vt:vector size="{count}" baseType="lpstr">{lpstrs}</vt:vector></TitlesOfParts>
</Properties>"""


def build_document_xml() -> str:
    std_doc_path = os.path.join(os.path.dirname(__file__), "standard_document.xml")
    if os.path.exists(std_doc_path):
        with open(std_doc_path, "r", encoding="utf-8") as f:
            return f.read()
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<VisioDocument xmlns="http://schemas.microsoft.com/office/visio/2012/main"
               xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <DocumentSettings TopPage="0" DefaultTextStyle="3" DefaultLineStyle="3" DefaultFillStyle="3">
    <GlueSettings>9</GlueSettings>
    <SnapSettings>65847</SnapSettings>
  </DocumentSettings>
  <Colors/>
  <FaceNames>
    <FaceName ID="1" NameU="Segoe UI" Name="Segoe UI"/>
    <FaceName ID="2" NameU="Calibri" Name="Calibri"/>
    <FaceName ID="3" NameU="Arial" Name="Arial"/>
  </FaceNames>
  <DocumentSheet NameU="TheDoc" Name="TheDoc" LineStyle="0" FillStyle="0" TextStyle="0"/>
</VisioDocument>"""


def build_document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/visio/2010/relationships/windows" Target="windows.xml"/>
</Relationships>"""


def build_windows_xml(page_width: float, page_height: float) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Windows xmlns="http://schemas.microsoft.com/office/visio/2012/main">
  <Window ID="0" WindowType="Drawing" WindowState="1073741824" ContainerType="Page" Page="0"
          ViewCenterX="{round(page_width / 2.0, 3)}" ViewCenterY="{round(page_height / 2.0, 3)}">
    <ShowRulers>1</ShowRulers>
    <ShowGrid>0</ShowGrid>
    <ShowPageBreaks>0</ShowPageBreaks>
    <GlueSettings>9</GlueSettings>
    <SnapSettings>65847</SnapSettings>
  </Window>
</Windows>"""


def build_pages_xml(page_width: float, page_height: float, pages_meta: Optional[List[Dict]] = None) -> str:
    if not pages_meta:
        pages_meta = [{
            "id": 0,
            "name_u": "Page-1",
            "name": "Sayfa-1",
            "width": page_width,
            "height": page_height,
            "rel_id": "rId1",
        }]
    page_elements = []
    for idx, pm in enumerate(pages_meta):
        pid = pm.get("id", idx)
        pw = pm.get("width", page_width)
        ph = pm.get("height", page_height)
        name_u = html.escape(pm.get("name_u", f"Page-{idx + 1}"))
        name = html.escape(pm.get("name", f"Sayfa-{idx + 1}"))
        rel_id = pm.get("rel_id", f"rId{idx + 1}")
        page_elements.append(f"""  <Page ID="{pid}" NameU="{name_u}" Name="{name}" ViewScale="1"
        ViewCenterX="{round(pw / 2.0, 3)}" ViewCenterY="{round(ph / 2.0, 3)}">
    <PageSheet LineStyle="0" FillStyle="0" TextStyle="0">
      <Cell N="PageWidth" V="{pw}" U="IN"/>
      <Cell N="PageHeight" V="{ph}" U="IN"/>
      <Cell N="ShdwOffsetX" V="0.125"/>
      <Cell N="ShdwOffsetY" V="-0.125"/>
      <Cell N="PageScale" V="1" U="IN_F"/>
      <Cell N="DrawingScale" V="1" U="IN_F"/>
      <Cell N="DrawingResizeType" V="2"/>
      <Cell N="RouteStyle" V="1"/>
    </PageSheet>
    <Rel r:id="{rel_id}"/>
  </Page>""")
    pages_str = "\n".join(page_elements)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
{pages_str}
</Pages>"""


def build_pages_rels_xml(num_pages: int = 1) -> str:
    rels = "\n".join(
        f'  <Relationship Id="rId{i}" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page{i}.xml"/>'
        for i in range(1, num_pages + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
</Relationships>"""


def build_page1_xml(shapes_xml: str, connects_xml: str) -> str:
    connects_block = ""
    if connects_xml and connects_xml.strip():
        connects_block = f"""  <Connects>
{connects_xml}
  </Connects>"""

    parts = [
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>""",
        """<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main" """,
        """              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">""",
        """  <Shapes>""",
        shapes_xml,
        """  </Shapes>""",
    ]
    if connects_block:
        parts.append(connects_block)
    parts.append("""</PageContents>""")
    return "\n".join(parts)


def package_vsdx(
    output_path: str,
    shapes_xml: str,
    connects_xml: str,
    page_width: float,
    page_height: float,
    page_bg_color: Optional[str] = None,
) -> str:
    """
    Serializes a complete, ISO/IEC 29500-2 compliant .vsdx ZIP package to output_path.
    If page_bg_color is provided and not white (#ffffff), prepends a full-bleed background canvas shape.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    final_shapes_xml = shapes_xml
    if page_bg_color and page_bg_color.lower() not in ("#ffffff", "#fff", "white", "rgb(255, 255, 255)", "rgb(255,255,255)"):
        from .shapesheet import build_2d_shape_xml
        bg_shape = build_2d_shape_xml(
            shape_id=99999,
            name="PageBackgroundCanvas",
            pin_x=round(page_width / 2.0, 4),
            pin_y=round(page_height / 2.0, 4),
            width=page_width,
            height=page_height,
            text="",
            shape_type="rectangle",
            fill_color=page_bg_color,
            line_color=page_bg_color,
            line_pattern=0,
            fill_pattern=1,
            has_connections=False,
        )
        final_shapes_xml = bg_shape + "\n" + shapes_xml

    parts = {
        "[Content_Types].xml": build_content_types_xml(1),
        "_rels/.rels": build_root_rels_xml(),
        "docProps/core.xml": build_core_props_xml(),
        "docProps/app.xml": build_app_props_xml(["Page-1"]),
        "visio/document.xml": build_document_xml(),
        "visio/_rels/document.xml.rels": build_document_rels_xml(),
        "visio/windows.xml": build_windows_xml(page_width, page_height),
        "visio/pages/pages.xml": build_pages_xml(page_width, page_height),
        "visio/pages/_rels/pages.xml.rels": build_pages_rels_xml(1),
        "visio/pages/page1.xml": build_page1_xml(final_shapes_xml, connects_xml),
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for part_name, content in parts.items():
            zf.writestr(part_name, content.encode("utf-8"))

    return os.path.abspath(output_path)


def package_multipage_vsdx(
    output_path: str,
    pages_data: List[Dict],
) -> str:
    """
    Packages multiple compiled Visio pages into a single multi-page .vsdx document.
    Each item in pages_data must be a dict with:
        - "title": str (optional page name)
        - "shapes_xml": str
        - "connects_xml": str
        - "page_width": float
        - "page_height": float
    """
    if not pages_data:
        raise ValueError("pages_data cannot be empty")
    if len(pages_data) == 1:
        p0 = pages_data[0]
        return package_vsdx(
            output_path=output_path,
            shapes_xml=p0["shapes_xml"],
            connects_xml=p0.get("connects_xml", ""),
            page_width=p0.get("page_width", 11.0),
            page_height=p0.get("page_height", 8.5),
            page_bg_color=p0.get("page_bg_color"),
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    num_pages = len(pages_data)
    pages_meta = []
    page_names = []
    used_names = set()

    for idx, pd in enumerate(pages_data):
        raw_title = (pd.get("title") or f"Page-{idx + 1}").strip()
        # Sanitize Visio page tab name (disallow []:*?/\ and truncate to 31 chars)
        clean_title = "".join(c for c in raw_title if c not in '[]:*?/\\')[:28].strip() or f"Page-{idx + 1}"
        if clean_title in used_names:
            clean_title = f"{clean_title}-{idx + 1}"
        used_names.add(clean_title)
        page_names.append(clean_title)
        pages_meta.append({
            "id": idx,
            "name_u": f"Page-{idx + 1}",
            "name": clean_title,
            "width": pd.get("page_width", 11.0),
            "height": pd.get("page_height", 8.5),
            "rel_id": f"rId{idx + 1}",
        })

    first_w = pages_meta[0]["width"]
    first_h = pages_meta[0]["height"]

    parts = {
        "[Content_Types].xml": build_content_types_xml(num_pages),
        "_rels/.rels": build_root_rels_xml(),
        "docProps/core.xml": build_core_props_xml(),
        "docProps/app.xml": build_app_props_xml(page_names),
        "visio/document.xml": build_document_xml(),
        "visio/_rels/document.xml.rels": build_document_rels_xml(),
        "visio/windows.xml": build_windows_xml(first_w, first_h),
        "visio/pages/pages.xml": build_pages_xml(first_w, first_h, pages_meta),
        "visio/pages/_rels/pages.xml.rels": build_pages_rels_xml(num_pages),
    }

    for idx, pd in enumerate(pages_data, start=1):
        parts[f"visio/pages/page{idx}.xml"] = build_page1_xml(
            pd["shapes_xml"], pd.get("connects_xml", "")
        )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for part_name, content in parts.items():
            zf.writestr(part_name, content.encode("utf-8"))

    return os.path.abspath(output_path)
