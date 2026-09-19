---
name: mermaid-to-visio
description: Convert Mermaid diagrams (flowcharts, sequence diagrams, UML class diagrams, subgraphs) into professional Microsoft Visio (.vsdx) drawings using a 100% headless pure-Python native compiler (zero Visio needed) or Windows COM automation, with 100% Turkish character fidelity and automated verification.
---

# Mermaid to Microsoft Visio (.vsdx) Converter Skill

This skill enables AI agents to automatically generate professional, beautifully styled **Microsoft Visio (`.vsdx`) drawings** from Mermaid diagram source code, with **100% Turkish character support** (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`), proper connector routing, and an **agentic visual verification loop** (capturing and inspecting high-resolution screenshots).

---

## Dual-Engine Architecture

1. **Native Headless OPC Compiler (`--engine native`, Default)**:
   - **Zero Visio Dependency**: Pure Python implementation that compiles directly into standard Open Packaging Conventions (OPC) `.vsdx` ZIP archives without requiring Microsoft Visio or Windows COM Interop.
   - **Cross-Platform**: Runs anywhere Python runs — Windows, Linux Docker containers, macOS, serverless functions, and CI/CD pipelines.
   - **Sugiyama Hierarchical Layout**: Multi-pass alternating downward and upward barycentric sweeps, cycle removal via DFS back-edge reversal, longest-path ranking, and cluster-preserving crossing reduction.
   - **Parametric ShapeSheet Geometry**: Generates native Visio vector shape primitives with mathematically evaluated coordinates and dynamic formulas.
   - **Dynamic Point-to-Point Glue & Line Jump Bridges**: Emits directional connection points (`Top`, `Bottom`, `Left`, `Right`) with `NoFill` connectors and automatic semicircular line jump bridges (`ConRouteJumpCode=1`, `ConRouteJumpStyle=0`) for intersecting lines.

2. **Visio COM Automation Engine (`--engine com`)**:
   - Direct automation of local Microsoft Visio Desktop on Windows via `win32com.client`.
   - Utilizes desktop Visio's internal layout engines and native stencils.

---

## When to Use This Skill

- User wants to convert Mermaid diagram code (flowcharts, sequence diagrams, architecture trees, class diagrams, state diagrams, ER diagrams) into Microsoft Visio (`.vsdx`).
- Generating native Visio drawing files (`.vsdx`) on headless environments, Linux servers, or machines without Microsoft Office installed.
- Generating diagrams containing Turkish characters without glyph corruption or font distortion.
- User requests visual verification screenshots of generated Visio drawings.

---

## Capabilities & Diagram Support

1. **Markdown Document Ingestion (`.md`, `.markdown`)**:
   - Automatically extracts ```` ```mermaid ```` code blocks from full Markdown documents or raw text files.
   - Preserves all surrounding document context when ingesting.
2. **UML Class Diagrams (`classDiagram`)**:
   - Multi-compartment class rendering (class header, stereotype `<<interface>>`, left-aligned attributes, left-aligned methods).
   - Visibility markers: `+` public, `-` private, `#` protected, `~` package/internal.
   - UML relationship connectors:
     - Inheritance / Generalization (`<|--`): closed solid arrow.
     - Realization / Interface Implementation (`<|..`): dashed line with closed hollow arrow.
     - Composition (`*--`): solid line with filled diamond.
     - Aggregation (`o--`): solid line with hollow diamond.
     - Association (`-->`): directional open arrow.
     - Dependency (`..>`): dashed line with open arrow.
     - Multiplicity labels (`"1"`, `"*"` / `"0..*"`) and relationship descriptions.
3. **State Diagrams (`stateDiagram`, `stateDiagram-v2`)**:
   - Initial state start disc (`[*]`) and terminal bullseye state (`[*]`).
   - Rounded state boxes with custom radius and distinct state names.
   - Glued state transition connectors with action/event labels.
4. **Entity-Relationship Diagrams (`erDiagram`)**:
   - Multi-compartment entity tables with distinct header and attribute sections.
   - Explicit primary key (`PK`) and foreign key (`FK`) badges.
   - Relationship cardinalities (`||--o{`, `||--|{`, `}|..|{`, `||--||`) with descriptive verbs.
5. **Flowcharts (`graph TD`, `flowchart LR`, `BT`, `RL`)**:
   - Shapes: `[Rectangle]`, `(Rounded)`, `([Stadium / Pill])`, `[[Subroutine]]`, `[(Cylinder / Database)]`, `((Circle))`, `{Diamond / Decision}`, `{{Hexagon}}`, `[/Parallelogram/]`.
   - Edges: `-->` (arrow), `---` (open), `-.->` (dotted), `==>` (thick).
   - Edge Labels: `-->|text|`, `-- text -->`, `-. text .->`, `== text ==>`.
   - Subgraphs: `subgraph ID ["Turkish Title"] ... end` rendered as independent, collision-free container blocks with header banners.
6. **Sequence Diagrams (`sequenceDiagram`)**:
   - Actors and participants (`participant A`, `actor B as Ali`).
   - Messages: `->>`, `-->>`, `->`, `-->`, `-x`, `--x` with upright text orientation (`TxtAngle = 0 deg`).
   - Notes: `Note over A`, `Note left of A`, `Note right of B: Turkish text`.
7. **Visual Verification (`--verify`)**:
   - When running on Windows with Visio installed, automatically opens the generated `.vsdx`, performs a layout pass, and exports a 300-DPI high-res PNG into `verification_output/`.
   - Allows the agent to inspect the visual rendering using `view_file`.

---

## Execution Methods for AI Agents

### Method 1: CLI Execution (Recommended for Agents)

The fastest and most reliable way for an AI agent to convert diagrams:

```powershell
# 1. Native Headless Mode (Default, works without Visio or on Linux/macOS)
python main.py <input.mmd> -o <output.vsdx> --engine native --palette "<Palette Name>" --font "<Font Name>"

# 2. With Visual Verification (requires Windows with Visio installed)
python main.py <input.mmd> -o <output.vsdx> --verify
```

#### Example:
```powershell
# 1. Write the Mermaid syntax to a file
@'
graph TD
    A([Müşteri Siparişi]) --> B{Ödeme Onaylandı mı?}
    B -->|Evet| C[(Veritabanına Kaydet)]
    B -->|Hayır| D[Bildirim Gönder: Yetersiz Bakiye]
'@ | Set-Content -Encoding UTF8 "order_process.mmd"

# 2. Run conversion with automated visual verification
python main.py order_process.mmd -o "output/order_process.vsdx" --palette "Modern Corporate (Blue & Slate)" --verify
```

---

### Method 2: Python Programmatic API

#### Headless Native Compilation (Zero Dependencies):
```python
import sys
sys.path.insert(0, ".")

from src.compiler import compile_mermaid_to_vsdx

mermaid_code = """
graph TD
    A([Başlangıç: Talep Alındı]) --> B{Onaylandı mı?}
    B -->|Evet| C[(Veritabanı)]
    B -->|Hayır| D[Reddedildi]
"""

# Pure Python OPC package generation
vsdx_path = compile_mermaid_to_vsdx(
    mermaid_code=mermaid_code,
    output_vsdx_path="output/workflow.vsdx",
    palette_name="Modern Corporate (Blue & Slate)",
    font_name="Segoe UI"
)
print(f"Generated headless .vsdx: {vsdx_path}")
```

#### Windows COM Generation with Verification:
```python
import sys
sys.path.insert(0, ".")

from src.visio import convert_mermaid_to_visio
from src.verifier import verify_and_capture_visio

# 1. Convert via COM
diag_type, vsdx_path = convert_mermaid_to_visio(
    mermaid_code=mermaid_code,
    output_vsdx_path="output/auth_flow.vsdx",
    palette_name="Emerald Tech (Mint & Teal)",
    font_name="Segoe UI"
)

# 2. Capture high-res verification screenshot
verification = verify_and_capture_visio(
    vsdx_path=vsdx_path,
    output_image_path="verification_output/auth_flow_verified.png"
)

print(f"Generated: {vsdx_path}")
print(f"Screenshot: {verification['image_path']} ({verification['width']}x{verification['height']})")
```

---

## Agentic Visual Verification Loop (Best Practice)

When generating diagrams for a user on a system with Visio installed:

1. **Synthesize Mermaid**:
   Write clean Mermaid syntax. If the diagram contains multiple systems or layers, group them using `subgraph ID ["Title"] ... end`.
2. **Convert with `--verify`**:
   Run `main.py <file.mmd> -o <file.vsdx> --verify`.
3. **Inspect the Visual Rendering**:
   Use `view_file` on the exported screenshot in `verification_output/`.
   - Verify that all shape texts are centered.
   - Verify that subgraphs cleanly enclose their respective nodes.
   - Verify that all Turkish characters (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`) render without boxes or corruption.
4. **Deliver to User**:
   - Provide clickable GitHub markdown links to both the `.vsdx` file and the verification PNG screenshot.

---

## Styling Options Reference

### Available Color Palettes (`--palette`):
- `Modern Corporate (Blue & Slate)` *(Default)*: Clean enterprise theme with sky blue fills, slate text, amber decision diamonds, and soft purple database cylinders.
- `Emerald Tech (Mint & Teal)`: Modern tech aesthetic with mint fills, teal borders, and dark emerald connectors.
- `Sunset Coral & Violet`: Vibrant theme with soft rose/coral fills, red/rose borders, and violet container accents.
- `Minimalist Slate (Dark / Steel)`: High-contrast monochrome theme with clean slate tones and dark borders.
- `Grayscale Clean (Black & White)`: Publication and patent-ready black-and-white theme with solid black borders, pure white node fills, subtle 5-10% gray semantic accents, and true black text.

### Available Unicode Fonts (`--font`):
- `Segoe UI` *(Recommended)*: Windows 11 native Fluent typography with full Turkish glyph coverage.
- `Calibri`: Professional Microsoft Office corporate standard.
- `Arial`: High-compatibility universal sans-serif.
