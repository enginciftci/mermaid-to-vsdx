"""
Mermaid Timeline Diagram Parser.
Parses `timeline` diagrams with optional sections, periods, and multi-event chains into TimelineDiagram AST.
"""

import re
from .ast_nodes import TimelineDiagram, TimelinePeriod
from .base_parser import MermaidParseError, preprocess_lines


def _clean_text(text: str) -> str:
    t = text.strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    return re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE).strip()


class TimelineParser:
    """Parser for Mermaid `timeline` diagrams."""

    def parse(self, mermaid_code: str) -> TimelineDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty timeline diagram.")

        diagram = TimelineDiagram()
        header_seen = False
        current_section = ""

        for line_num, line in lines:
            if not header_seen:
                if line.lower().startswith("timeline"):
                    header_seen = True
                    rem = line[8:].strip()
                    if rem.lower().startswith("title "):
                        diagram.title = _clean_text(rem[6:])
                    elif rem:
                        diagram.title = _clean_text(rem)
                    continue
                else:
                    raise MermaidParseError("Expected 'timeline' header.", line_num, line)

            low = line.lower()
            if low.startswith("title "):
                diagram.title = _clean_text(line[6:])
                continue
            elif low.startswith("title:"):
                diagram.title = _clean_text(line[6:])
                continue

            if low.startswith("section "):
                current_section = _clean_text(line[8:])
                continue
            elif low.startswith("section:"):
                current_section = _clean_text(line[8:])
                continue

            if line.startswith(":"):
                raw_events = [_clean_text(p) for p in line[1:].split(":") if _clean_text(p)]
                if diagram.periods:
                    diagram.periods[-1].events.extend(raw_events)
                elif raw_events:
                    diagram.periods.append(
                        TimelinePeriod(period="Milestone", events=raw_events, section=current_section)
                    )
            elif ":" in line:
                parts = line.split(":")
                period_label = _clean_text(parts[0])
                events = [_clean_text(p) for p in parts[1:] if _clean_text(p)]
                diagram.periods.append(
                    TimelinePeriod(period=period_label, events=events, section=current_section)
                )
            else:
                period_label = _clean_text(line)
                if period_label:
                    diagram.periods.append(
                        TimelinePeriod(period=period_label, events=[], section=current_section)
                    )

        return diagram
