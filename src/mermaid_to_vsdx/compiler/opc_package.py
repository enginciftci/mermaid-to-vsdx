"""
Standards-compliant Open Packaging Conventions (OPC) packager.
Constructs and serializes a native Microsoft Visio (.vsdx) ZIP archive without external tools.
"""

import os
import zipfile
from typing import List, Optional


def build_content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>
  <Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>
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


def build_app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Visio</Application>
  <AppVersion>16.0000</AppVersion>
  <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Pages</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant></vt:vector></HeadingPairs>
  <TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>Page-1</vt:lpstr></vt:vector></TitlesOfParts>
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
    <FaceName ID="1" Name="Segoe UI"/>
    <FaceName ID="2" Name="Calibri"/>
    <FaceName ID="3" Name="Arial"/>
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


def build_pages_xml(page_width: float, page_height: float) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <Page ID="0" NameU="Page-1" Name="Sayfa-1" ViewScale="1"
        ViewCenterX="{round(page_width / 2.0, 3)}" ViewCenterY="{round(page_height / 2.0, 3)}">
    <PageSheet LineStyle="0" FillStyle="0" TextStyle="0">
      <Cell N="PageWidth" V="{page_width}" U="IN"/>
      <Cell N="PageHeight" V="{page_height}" U="IN"/>
      <Cell N="ShdwOffsetX" V="0.125"/>
      <Cell N="ShdwOffsetY" V="-0.125"/>
      <Cell N="PageScale" V="1" U="IN_F"/>
      <Cell N="DrawingScale" V="1" U="IN_F"/>
      <Cell N="DrawingResizeType" V="2"/>
      <Cell N="RouteStyle" V="1"/>
    </PageSheet>
    <Rel r:id="rId1"/>
  </Page>
</Pages>"""


def build_pages_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page1.xml"/>
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
    page_height: float
) -> str:
    """
    Serializes a complete, ISO/IEC 29500-2 compliant .vsdx ZIP package to output_path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    parts = {
        "[Content_Types].xml": build_content_types_xml(),
        "_rels/.rels": build_root_rels_xml(),
        "docProps/core.xml": build_core_props_xml(),
        "docProps/app.xml": build_app_props_xml(),
        "visio/document.xml": build_document_xml(),
        "visio/_rels/document.xml.rels": build_document_rels_xml(),
        "visio/windows.xml": build_windows_xml(page_width, page_height),
        "visio/pages/pages.xml": build_pages_xml(page_width, page_height),
        "visio/pages/_rels/pages.xml.rels": build_pages_rels_xml(),
        "visio/pages/page1.xml": build_page1_xml(shapes_xml, connects_xml),
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for part_name, content in parts.items():
            zf.writestr(part_name, content.encode("utf-8"))

    return os.path.abspath(output_path)
