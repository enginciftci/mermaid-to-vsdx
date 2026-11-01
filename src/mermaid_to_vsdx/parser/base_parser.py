import re
from typing import List, Tuple
from .ast_nodes import DiagramType


def extract_mermaid_from_markdown(content: str) -> str:
    """
    If the content contains a Markdown code block like ```mermaid ... ``` or ~~~mermaid ... ~~~,
    extracts and returns the first mermaid code block. If no fences are found, returns content as-is.
    """
    if not content:
        return ""

    blocks = extract_all_mermaid_from_markdown(content)
    if blocks:
        return blocks[0][1]
    return content.strip()


def extract_all_mermaid_from_markdown(content: str) -> List[Tuple[str, str]]:
    """
    Extracts all ```mermaid ... ``` or ~~~mermaid ... ~~~ blocks from a Markdown document.
    Returns a list of (page_title, mermaid_code) tuples.
    If the input is raw Mermaid code (no fences), returns [("Page-1", content.strip())].
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    in_mermaid = False
    current_lines: List[str] = []
    blocks: List[Tuple[str, str]] = []
    last_heading = ""
    found_any_fence = False

    for line in lines:
        stripped = line.strip()
        if not in_mermaid:
            if stripped.startswith("#"):
                heading_text = stripped.lstrip("#").strip()
                if heading_text:
                    last_heading = heading_text
            elif (stripped.startswith("```") or stripped.startswith("~~~")) and "mermaid" in stripped.lower():
                in_mermaid = True
                found_any_fence = True
                current_lines = []
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_mermaid = False
                code_str = "\n".join(current_lines).strip()
                if code_str:
                    idx = len(blocks) + 1
                    title = last_heading if last_heading else f"Page-{idx}"
                    blocks.append((title, code_str))
                    last_heading = ""
            else:
                current_lines.append(line)

    if in_mermaid and current_lines:
        code_str = "\n".join(current_lines).strip()
        if code_str:
            idx = len(blocks) + 1
            title = last_heading if last_heading else f"Page-{idx}"
            blocks.append((title, code_str))

    if not found_any_fence:
        return [("Page-1", content.strip())]

    return blocks


class MermaidParseError(Exception):
    """Exception raised when Mermaid code fails parsing, including line number context."""
    def __init__(self, message: str, line_number: int = -1, line_content: str = ""):
        self.message = message
        self.line_number = line_number
        self.line_content = line_content
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.line_number > 0:
            return f"Line {self.line_number}: {self.message}\n  > {self.line_content.strip()}"
        return self.message


def detect_diagram_type(mermaid_code: str) -> DiagramType:
    """
    Detects whether the given Mermaid code represents a Flowchart, Sequence, Class Diagram, or other.
    Automatically un-fences Markdown code blocks if present.
    """
    code = extract_mermaid_from_markdown(mermaid_code)
    in_frontmatter = False
    for raw_line in code.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        line_lower = line.lower()
        if line_lower.startswith(("graph", "flowchart")):
            return DiagramType.FLOWCHART
        elif line_lower.startswith("sequencediagram"):
            return DiagramType.SEQUENCE
        elif line_lower.startswith("classdiagram"):
            return DiagramType.CLASS_DIAGRAM
        elif line_lower.startswith(("statediagram-v2", "statediagram")):
            return DiagramType.STATE_DIAGRAM
        elif line_lower.startswith("erdiagram"):
            return DiagramType.ER_DIAGRAM
        elif line_lower.startswith("block"):
            return DiagramType.BLOCK
        elif line_lower.startswith("mindmap"):
            return DiagramType.MINDMAP
        elif line_lower.startswith("timeline"):
            return DiagramType.TIMELINE
        elif line_lower.startswith("quadrantchart"):
            return DiagramType.QUADRANT
        elif line_lower.startswith("pie"):
            return DiagramType.PIE
        elif line_lower.startswith("gantt"):
            return DiagramType.GANTT
        else:
            return DiagramType.UNKNOWN
    return DiagramType.UNKNOWN


def preprocess_lines(mermaid_code: str) -> List[Tuple[int, str]]:
    """
    Returns a list of (1-indexed line_number, stripped_line),
    ignoring empty lines, comment lines (%%), and YAML frontmatter (---).
    Automatically extracts Mermaid block if Markdown input.
    """
    code = extract_mermaid_from_markdown(mermaid_code)
    lines = []
    in_frontmatter = False
    for idx, raw_line in enumerate(code.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        lines.append((idx, line))
    return lines


def preprocess_lines_raw(mermaid_code: str) -> List[Tuple[int, str]]:
    """
    Returns a list of (1-indexed line_number, raw_line_without_trailing_newline),
    preserving leading whitespace/indentation (needed for mindmap),
    while ignoring empty lines, comment lines (%%), and YAML frontmatter (---).
    """
    code = extract_mermaid_from_markdown(mermaid_code)
    lines = []
    in_frontmatter = False
    for idx, raw_line in enumerate(code.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        lines.append((idx, raw_line.rstrip()))
    return lines
