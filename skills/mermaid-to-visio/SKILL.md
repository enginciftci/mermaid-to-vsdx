---
name: mermaid-to-visio
description: Convert Mermaid diagrams (flowcharts, sequence diagrams, UML class diagrams, state diagrams, ER diagrams, subgraphs) into professional Microsoft Visio (.vsdx) drawings using a 100% headless pure-Python native compiler (zero Visio needed) or Windows COM automation, with 100% Turkish character fidelity and automated verification.
---

# Mermaid to Microsoft Visio (.vsdx) Converter Skill

This skill equips AI coding agents (Antigravity, Claude Code, Cursor, Copilot, AutoGPT) with the capability to autonomously convert Mermaid diagram source code into professional, beautifully styled **Microsoft Visio (`.vsdx`) vector drawings**, with **100% Turkish character fidelity** (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`), dynamic orthogonal routing, and an **agentic visual verification loop**.

---

## 🧠 Instructions for AI Agents

When a user asks you to:
- Convert a flowchart, architecture diagram, sequence diagram, UML class diagram, ER diagram, or state machine into Microsoft Visio (`.vsdx`).
- Create Visio drawings from text descriptions or Markdown documents.
- Generate diagrams in headless environments (Linux servers, macOS, CI/CD pipelines, Docker containers) where Microsoft Office is not installed.
- Ensure Turkish characters render flawlessly without glyph corruption or broken question marks (`?`).

### The 5-Step Autonomous Agent Workflow

```
[1. Synthesize Mermaid] ──> [2. Save to .mmd] ──> [3. Run CLI Compiler] ──> [4. Verify Output] ──> [5. Deliver Links to User]
```

#### Step 1: Synthesize High-Quality Mermaid Code
- Write clean, standard Mermaid syntax (`graph TD`, `flowchart LR`, `sequenceDiagram`, `classDiagram`, `erDiagram`, or `stateDiagram-v2`).
- Group multi-tiered or microservice architectures using `subgraph ID ["Container Title"] ... end`.
- Ensure labels with special characters (parentheses, commas, colons) are enclosed in quotes: `nodeId["Label (Extra Details)"]`.

#### Step 2: Choose the Optimal Theme & Font
Select the color palette matching the user's intent:
- **`Modern Corporate (Blue & Slate)`** *(Default)*: Best for business workflows, enterprise IT systems, executive presentations.
- **`Emerald Tech (Mint & Teal)`**: Best for modern software architectures, microservices, DevOps pipelines.
- **`Sunset Coral & Violet`**: Best for customer-facing flows, e-commerce, frontend applications.
- **`Minimalist Slate (Dark / Steel)`**: Best for developer documentation, technical system specs.
- **`Grayscale Clean (Black & White)`**: Best for academic papers, patent submissions, print publications.

Recommended Unicode Fonts:
- **`Segoe UI`** *(Default)*: Clean Windows 11 Fluent typography with full Turkish glyph coverage.
- **`Calibri`**: Classic corporate Microsoft Office aesthetic.
- **`Arial`**: Universal cross-platform sans-serif.

#### Step 3: Execute Headless Compilation (CLI)
Run the converter from your terminal:
```powershell
# Pure Python headless compilation (Zero Visio required, runs everywhere)
python main.py input_diagram.mmd -o output/diagram.vsdx --engine native --palette "Modern Corporate (Blue & Slate)" --font "Segoe UI"
```

#### Step 4: Visual Verification (When Visio is Available)
If running on Windows with Microsoft Visio installed, add `--verify` to capture a high-resolution PNG screenshot of the Visio canvas:
```powershell
python main.py input_diagram.mmd -o output/diagram.vsdx --verify
```
The screenshot will be saved in `verification_output/`. Use your file viewing tool (`view_file`) to inspect the exported PNG:
- Confirm that labels are centered and fully legible.
- Confirm all Turkish characters (`ç, ğ, ı, ö, ş, ü, İ, Ç, Ğ, Ö, Ş, Ü`) render without square boxes.
- Confirm subgraph boundary boxes cleanly enclose their child nodes.

#### Step 5: Deliver to User
Provide clickable links in your markdown response:
- Link to the generated Visio file: `[Download diagram.vsdx](file:///path/to/output/diagram.vsdx)`
- Link to the preview image if captured: `![Diagram Preview](file:///path/to/verification_output/screenshot.png)`

---

## 🛠️ CLI Reference for Agents

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

## 💻 Programmatic Python API for Agents

Agents can also invoke the converter directly within Python scripts:

### Headless Native Compilation (Zero Dependencies):
```python
import sys
sys.path.insert(0, ".")

from src.compiler import compile_mermaid_to_vsdx

mermaid_code = """
graph TD
    A([Customer Request]) --> B{Approved?}
    B -->|Yes| C[(Database)]
    B -->|No| D[Send Notification: Rejected]
"""

vsdx_path = compile_mermaid_to_vsdx(
    mermaid_code=mermaid_code,
    output_vsdx_path="output/workflow.vsdx",
    palette_name="Modern Corporate (Blue & Slate)",
    font_name="Segoe UI"
)
print(f"Generated: {vsdx_path}")
```

### Markdown Ingestion:
```python
from src.parser import extract_mermaid_from_markdown, parse_mermaid

# Automatically extracts ```mermaid code blocks from markdown documentation
clean_mermaid = extract_mermaid_from_markdown(full_markdown_text)
ast = parse_mermaid(clean_mermaid)
```

---

## 📋 Supported Diagram Types & Ast Reference

1. **Flowcharts (`graph TD`, `flowchart LR`, `BT`, `RL`)**:
   - Shapes: `[Rectangle]`, `(Rounded)`, `([Stadium / Pill])`, `[[Subroutine]]`, `[(Cylinder / Database)]`, `((Circle))`, `{Diamond / Decision}`, `{{Hexagon}}`, `[/Parallelogram/]`.
   - Connectors: `-->` (arrow), `---` (open), `-.->` (dotted), `==>` (thick).
   - Dynamic orthogonal line jump bridges (`ConRouteJumpCode=1`, `ConRouteJumpStyle=0`).
   - Collision-free independent subgraphs with title banners.
2. **UML Class Diagrams (`classDiagram`)**:
   - Multi-compartment class shapes (class header, stereotypes like `<<interface>>`, attributes, and methods).
   - Visibility markers: `+` public, `-` private, `#` protected, `~` package.
   - UML relationship connectors: `<|--` (Inheritance), `<|..` (Realization), `*--` (Composition), `o--` (Aggregation), `-->` (Association), `..>` (Dependency).
3. **Entity-Relationship Diagrams (`erDiagram`)**:
   - Multi-compartment tables with attributes and explicit `PK` / `FK` markers.
   - Cardinality notations: `||--o{`, `||--|{`, `}|..|{`, `||--||`.
4. **State Machine Diagrams (`stateDiagram`, `stateDiagram-v2`)**:
   - Initial state disc `[*]`, terminal bullseye `[*]`.
   - Rounded state boxes and transition event labels.
5. **Sequence Diagrams (`sequenceDiagram`)**:
   - Participants & actors (`participant A`, `actor B as User`).
   - Messages: `->>`, `-->>`, `->`, `-->`, `-x`, `--x` with horizontal text alignment.
   - Notes: `Note over A`, `Note left of A`, `Note right of B`.
