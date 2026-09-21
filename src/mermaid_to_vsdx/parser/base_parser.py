import re
from typing import List, Tuple
from .ast_nodes import DiagramType


def extract_mermaid_from_markdown(content: str) -> str:
    """
    If the content contains a Markdown code block like ```mermaid ... ``` or ~~~mermaid ... ~~~,
    extracts and returns the mermaid code. If no fences are found, returns content as-is.
    """
    if not content:
        return ""

    lines = content.splitlines()
    in_mermaid = False
    extracted_lines = []

    for line in lines:
        stripped = line.strip()
        if not in_mermaid:
            if (stripped.startswith("```") or stripped.startswith("~~~")) and "mermaid" in stripped.lower():
                in_mermaid = True
                continue
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_mermaid = False
                break
            extracted_lines.append(line)

    if extracted_lines:
        return "\n".join(extracted_lines).strip()
    return content.strip()


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
