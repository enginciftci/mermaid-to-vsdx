import xml.etree.ElementTree as ET
from mermaid_to_vsdx.parser.flowchart_parser import FlowchartParser
from mermaid_to_vsdx.compiler.flowchart_compiler import compile_flowchart_to_vsdx, PALETTES
import zipfile

content = """flowchart LR
    subgraph SENSOR_ALANI ["TEÜ: Akustik Dizin (YÇYFA)"]
        direction TB
        PZT1["PZT Sensör Ch 1"]
        PZT2["PZT Sensör Ch 2"]
        PZT_DOTS["..."]
        PZT8["PZT Sensör Ch 8"]
        PZT_CONN["PZT Dizin Konnektörü\\n(Glenair 805 / SEACON)"]
        PZT1 & PZT2 & PZT_DOTS & PZT8 --> PZT_CONN
    end

    subgraph GIRIS_KABLAJ ["TKBL-01: Özel RF Giriş Kablo Demeti"]
        direction TB
        CABLE_PREP["50 Ω RF Koaksiyel Kablo\\n(Soyulmuş / Ekranı Ayrılmış / Ferüllü)\\nUzunluk: 1.5 m"]
    end

    subgraph PREAMP_BOX ["Test Donanımı Kabini (Korumalı Alüminyum Şasi)"]
        direction TB
        subgraph POWER_DIST ["USB +5V Güç Dağıtım Rayı (Daisy-Chain AWG28)"]
            USB_IN["Micro-USB (P3)\\n+5VDC Harici Giriş"]
            CH1_PWR["Ch 1: PWR_3.6V & PGND1"]
            CH2_PWR["Ch 2: PWR_3.6V & PGND1"]
            CH8_PWR["Ch 8: PWR_3.6V & PGND1"]
            USB_IN --> CH1_PWR
            CH1_PWR -->|AWG28 Bükümlü Çift| CH2_PWR
            CH2_PWR -.->|AWG28 Bükümlü Çift| CH8_PWR
        end

        subgraph CHANNELS ["8x EVAL-INAMP-RMZ (AD8421BRMZ)"]
            direction TB
            AMP1["Kanal 1 Ön Yükselteç\\nGain: 40 dB (RG=100Ω)\\nRbias: 1MΩ (C1/C3)\\nBand: 260-460 kHz"]
            AMP2["Kanal 2 Ön Yükselteç\\nGain: 40 dB (RG=100Ω)\\nRbias: 1MΩ (C1/C3)\\nBand: 260-460 kHz"]
            AMP_DOTS["..."]
            AMP8["Kanal 8 Ön Yükselteç\\nGain: 40 dB (RG=100Ω)\\nRbias: 1MΩ (C1/C3)\\nBand: 260-460 kHz"]
        end
    end

    subgraph CIKIS_KABLAJ ["TKBL-02: Çıkış Kablo Demeti"]
        direction TB
        SMA_BNC["8x SMA-Erkek - BNC-Erkek\\n50 Ω Çift Ekranlı RF Kablo\\nUzunluk: 2.0 m"]
    end

    subgraph DAQ_SYSTEM ["Veri Toplama ve İşleme"]
        direction TB
        DAQ["Dewesoft SIRIUS XHS-ACC\\n(8x İzole BNC Giriş\\n15 MS/s @ 16-bit / 1 MS/s @ 24-bit)"]
        PC["Endüstriyel Test Bilgisayarı\\n(DewesoftX Sinyal Analiz Yazılımı)"]
        DAQ -->|USB 3.0 / PCIe Veri Yolu| PC
    end

    PZT_CONN ==> GIRIS_KABLAJ
    GIRIS_KABLAJ ==>|J1/J2 BNC/SMA| CHANNELS
    CHANNELS ==>|J3 SMA Dişi| CIKIS_KABLAJ
    CIKIS_KABLAJ ==>|BNC Erkek| DAQ
    CH1_PWR -.->|±15V Regüle| AMP1
    CH2_PWR -.->|±15V Regüle| AMP2
    CH8_PWR -.->|±15V Regüle| AMP8
"""

def main():
    parser = FlowchartParser()
    diagram = parser.parse(content)
    print("Top-level subgraphs:", [s.id for s in diagram.subgraphs])
    for s in diagram.subgraphs:
        print(f"  Subgraph {s.id}: node_ids={s.node_ids}, children={[c.id for c in s.children]}")
        for c in s.children:
            print(f"    Child {c.id}: node_ids={c.node_ids}")
    print("Nodes in diagram:", list(diagram.nodes.keys()))
    print("Edges count:", len(diagram.edges))
    for e in diagram.edges:
        safe_lbl = e.label.encode('ascii', errors='replace').decode('ascii')
        print(f"  Edge: {e.source_id} --[{safe_lbl}]--> {e.target_id}")

    out_path = "tests/output/error_repro.vsdx"
    compile_flowchart_to_vsdx(diagram, out_path, palette_name="Modern Corporate (Blue & Slate)")

    with zipfile.ZipFile(out_path, "r") as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                data = z.read(name)
                try:
                    ET.fromstring(data)
                except Exception as e:
                    print(f"Error in {name}: {e}")
                    lines = data.decode("utf-8", errors="replace").split("\n")
                    import re
                    m = re.search(r"line (\d+), column (\d+)", str(e))
                    if m:
                        line_no = int(m.group(1))
                        col_no = int(m.group(2))
                        print(f"Line {line_no}: {lines[line_no - 1]}")
                        print(f"Around col {col_no}: {lines[line_no - 1][max(0, col_no - 30):col_no + 30]}")


if __name__ == "__main__":
    main()
