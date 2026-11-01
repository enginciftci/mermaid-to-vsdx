---
name: mermaid-to-visio
description: Convert 11 Mermaid diagram types (flowcharts, sequence diagrams, UML class diagrams, state diagrams, ER diagrams, block diagrams, mindmaps, timelines, quadrant charts, pie charts, and Gantt charts) plus multi-page Markdown documents into professional Microsoft Visio (.vsdx) drawings using a 100% headless pure-Python native compiler (zero Visio needed) or Windows COM automation, with 100% Turkish character fidelity and automated verification.
---

# Mermaid to Microsoft Visio (.vsdx) Converter Skill

This skill equips automated workflows and coding environments with the capability to autonomously convert Mermaid diagram source code into professional, executive-ready **Microsoft Visio (`.vsdx`) vector drawings**, with **100% Turkish character fidelity** (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`), dynamic orthogonal routing, and an **automated visual verification loop**.

---

## ⚡ Quick Setup (One-Line Global Installation)

**Prerequisite**: Python 3.10 or newer (`python --version >= 3.10`).

Install the CLI globally into your environment with:

```bash
pip install git+https://github.com/enginciftci/mermaid-to-vsdx.git
```

Once installed, the `mermaid-to-vsdx` command is available from **any directory** without needing to clone or locate repository paths:

```bash
mermaid-to-vsdx diagram.mmd -o output/diagram.vsdx
```

If working inside a cloned repository:
```bash
python main.py diagram.mmd -o output/diagram.vsdx
```

---

## 🧠 Automation Instructions

When asked to:
- Convert any of the 11 supported Mermaid diagram types (Flowchart, Sequence, UML Class, ER, State Machine, Block, Mindmap, Timeline, Quadrant Chart, Pie Chart, or Gantt Chart) into Microsoft Visio (`.vsdx`).
- Create single-page or multi-page Visio drawings from text descriptions or Markdown documents containing multiple ```` ```mermaid ```` code blocks.
- Generate diagrams in headless environments (Linux servers, macOS, CI/CD pipelines, Docker containers) where Microsoft Office is not installed.
- Ensure Turkish characters render flawlessly without glyph corruption or broken question marks (`?`).

### The 5-Step Workflow

```
[1. Synthesize Mermaid] ──> [2. Save to .mmd] ──> [3. Run CLI Compiler] ──> [4. Verify Output] ──> [5. Deliver Links to User]
```

#### Step 1: Synthesize High-Quality Mermaid Code
- Write clean, standard Mermaid syntax (`graph TD`, `flowchart LR`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `stateDiagram-v2`, `block-beta`, `mindmap`, `timeline`, `quadrantChart`, `pie`, or `gantt`).
- Group multi-tiered or microservice architectures using `subgraph ID ["Container Title"] ... end`.
- Ensure labels with special characters (parentheses, commas, colons) are enclosed in quotes: `nodeId["Label (Extra Details)"]`.

#### Step 2: Choose the Optimal Theme & Font
Select the color palette matching the user's intent:
- **`Modern Corporate (Blue & Slate)`** *(Default)*: Best for business workflows, enterprise IT systems, executive presentations.
- **`Emerald Tech (Mint & Teal)`**: Best for modern software architectures, microservices, DevOps pipelines.
- **`Sunset Coral & Violet`**: Best for customer-facing flows, e-commerce, frontend applications.
- **`Minimalist Slate (Dark / Steel)`**: Full dark-canvas theme (`#0f172a` background) for developer documentation and dark-mode presentations.
- **`Grayscale Clean (Black & White)`**: Best for academic papers, patent submissions, print publications.

Recommended Unicode Fonts:
- **`Segoe UI`** *(Default)*: Clean Windows 11 Fluent typography with full Turkish glyph coverage.
- **`Calibri`**: Classic corporate Microsoft Office aesthetic.
- **`Arial`**: Universal cross-platform sans-serif.

#### Step 3: Execute Headless Compilation (CLI)
Run the converter from your terminal:
```powershell
# Global CLI command (works from any directory)
mermaid-to-vsdx input_diagram.mmd -o output/diagram.vsdx --engine native --palette "Modern Corporate (Blue & Slate)" --font "Segoe UI"

# Or from cloned repository root
python main.py input_diagram.mmd -o output/diagram.vsdx --engine native --palette "Modern Corporate (Blue & Slate)" --font "Segoe UI"
```

#### Step 4: Visual Verification (When Visio is Available)
If running on Windows with Microsoft Visio installed, add `--verify` to capture a high-resolution PNG screenshot of the Visio canvas:
```powershell
mermaid-to-vsdx input_diagram.mmd -o output/diagram.vsdx --verify
```
The screenshot will be saved in `verification_output/`. Inspect the exported PNG to:
- Confirm that labels are centered and fully legible.
- Confirm all Turkish characters (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`) render without square boxes.
- Confirm subgraph boundary boxes cleanly enclose their child nodes.

#### Step 5: Deliver to User
Provide clickable links in your markdown response:
- Link to the generated Visio file: `[Download diagram.vsdx](file:///path/to/output/diagram.vsdx)`
- Link to the preview image if captured: `![Diagram Preview](file:///path/to/verification_output/screenshot.png)`

---

## 🛠️ CLI Reference

| Argument | Description | Default |
| :--- | :--- | :--- |
| `input` / `-i` | Path to the `.mmd`, `.txt`, `.md`, or `.markdown` file. | Required in CLI |
| `-o, --output` | Path to save the resulting `.vsdx` file. | `<input_basename>.vsdx` |
| `--engine` | `native` (pure Python OPC package builder) or `com` (desktop Visio automation). | `native` |
| `-p, --palette` | Theme: `Modern Corporate (Blue & Slate)`, `Emerald Tech (Mint & Teal)`, `Sunset Coral & Violet`, `Minimalist Slate (Dark / Steel)`, `Grayscale Clean (Black & White)`. | `Modern Corporate` |
| `-f, --font` | Font: `Segoe UI`, `Calibri`, `Arial`. | `Segoe UI` |
| `--verify` | Performs visual verification pass and exports PNG screenshot (requires Windows + Visio). | `False` |
| `-s, --screenshot` | Explicit file path for the verification screenshot PNG. | Auto timestamped |

---

## 💻 Programmatic Python API

You can also invoke the converter directly within Python scripts:

### Headless Native Compilation (Zero Visio Required):
```python
from mermaid_to_vsdx import convert_mermaid_to_visio

mermaid_code = """
graph TD
    A([Customer Request]) --> B{Approved?}
    B -->|Yes| C[(Database)]
    B -->|No| D[Send Notification: Rejected]
"""

diag_type, vsdx_path = convert_mermaid_to_visio(
    mermaid_code=mermaid_code,
    output_vsdx_path="output/workflow.vsdx",
    palette_name="Modern Corporate (Blue & Slate)",
    font_name="Segoe UI",
    engine="native"
)
print(f"Generated {diag_type}: {vsdx_path}")
```

### Multi-Block Markdown Ingestion:
```python
from mermaid_to_vsdx.parser import extract_all_mermaid_from_markdown
from mermaid_to_vsdx.compiler import compile_mermaid_to_vsdx

# Automatically extracts all ```mermaid code blocks (with section titles) and compiles
# a multi-page .vsdx archive when 2+ Mermaid blocks are present in the Markdown document
diag_type, vsdx_path = compile_mermaid_to_vsdx(full_markdown_text, "output/architecture_deck.vsdx")
```

---

## 📋 Supported Diagram Types (11 Types + Multi-Page Markdown)

1. **Flowcharts (`graph TD`, `flowchart LR`, `BT`, `RL`)**:
   - All 14 standard shapes (`[Rectangle]`, `(Rounded)`, `([Stadium])`, `[[Subroutine]]`, `[(Cylinder)]`, `((Circle))`, `(((Double Circle)))`, `>Asymmetric]`, `{Diamond}`, `{{Hexagon}}`, `[/Parallelogram/]`, `[\Parallelogram Alt\]`, `[/Trapezoid\]`, `[\Trapezoid Alt/]`) plus Mermaid v11 `@{ shape: ... }` syntax.
   - Custom styling: `classDef`, `class`, `:::className`, `style`, `linkStyle`.
   - Connectors: `-->`, `---`, `-.->`, `==>`, `<-->`, `--o`, `--x`, `--->`, `~~~`.
   - Collision-free nested subgraphs with title banners and corridor-aligned skip-level routing.
2. **Sequence Diagrams (`sequenceDiagram`)**:
   - `participant`, `actor` (stick-figure icon), `box` grouping, `autonumber`, activation bars (`+`/`-`).
   - Combined fragments (`loop`, `alt`, `opt`, `par`, `critical`, `break`) with `else`/`and` dividers.
   - Notes: `Note over`, `Note left of`, `Note right of`.
3. **UML Class Diagrams (`classDiagram`)**:
   - Multi-compartment class shapes (header, `<<interface>>`/`<<abstract>>`/`<<enumeration>>`/`<<service>>` stereotypes, attributes, methods).
   - Visibility markers (`+`, `-`, `#`, `~`) and 8 UML relationship connectors (`<|--`, `<|..`, `*--`, `o--`, `-->`, `..>`, `--`, `..`).
4. **Entity-Relationship Diagrams (`erDiagram`)**:
   - Multi-compartment entity tables with `PK`, `FK`, `UK` markers and entity aliases.
   - True Information Engineering Crow's Foot cardinality markers (`||--o{`, `||--|{`, `}|..|{`, `||--||`).
5. **State Machine Diagrams (`stateDiagram`, `stateDiagram-v2`)**:
   - Initial state disc `[*]`, terminal bullseye `[*]`, composite states (`state Active { ... }`), `<<choice>>`, `<<fork>>`, `<<join>>`, `note left/right of`, and exterior U-channel feedback loops.
6. **Block Diagrams (`block-beta`, `block`)**:
   - Multi-column grid (`columns N`), column spans (`:2`), nested composite blocks, `classDef`/`style`, and dynamic `<Connects>`.
7. **Mindmaps (`mindmap`)**:
   - Indentation-based hierarchy, central root node, color-coded radial branch families, and elbow branch connectors.
8. **Timelines (`timeline`)**:
   - Horizontal chronological spine, `section` bands, period badges, and stacked event cards.
9. **Quadrant Charts (`quadrantChart`)**:
   - 2x2 strategic matrix with 4 tinted quadrants, X/Y axis arrows, and collision-free data point pins + pill badges.
10. **Pie & Donut Charts (`pie`)**:
    - Parametric `EllipticalArcTo` circular sectors (`showData`), percentage badges, and category breakdown legend card.
11. **Gantt Charts (`gantt`)**:
    - Project schedule grid with date columns, section bands, status-styled task bars (`done`, `active`, `crit`), and diamond `milestone` markers.
12. **Multi-Page Markdown Documents (`.md`, `.markdown`)**:
    - Automatically extracts all ```` ```mermaid ```` blocks from a Markdown file and compiles each onto its own named Visio page tab (`Page-1`, `Page-2`, ...) in a single `.vsdx` archive.
