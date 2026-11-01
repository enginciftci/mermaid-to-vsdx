"""
Mermaid Gantt Chart Parser.
Parses `gantt` schedules, sections, task statuses (`done`, `active`, `crit`, `milestone`),
dependencies (`after id`), dates, and durations into GanttDiagram AST.
"""

from datetime import datetime
import re
from typing import Dict, List, Optional
from .ast_nodes import GanttDiagram, GanttTask
from .base_parser import MermaidParseError, preprocess_lines


_DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$")
_DUR_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>ms|s|m|h|d|w|M|y)$")

_IGNORE_PREFIXES = (
    "axisformat ",
    "tickinterval ",
    "excludes ",
    "todaymarker ",
    "weekday ",
    "inclusiveenddates",
    "topaxis",
)


def _parse_date(token: str) -> Optional[datetime]:
    t = token.strip().replace("/", "-")
    if not _DATE_RE.match(t):
        return None
    try:
        parts = [int(p) for p in t.split("-")]
        return datetime(parts[0], parts[1], parts[2])
    except ValueError:
        return None


def _parse_duration_days(token: str) -> Optional[float]:
    m = _DUR_RE.match(token.strip())
    if not m:
        return None
    val = float(m.group("num"))
    unit = m.group("unit")
    if unit == "d":
        return max(0.2, val)
    elif unit == "w":
        return max(0.5, val * 7.0)
    elif unit == "h":
        return max(0.2, val / 24.0)
    elif unit in ("M", "y"):
        return val * (30.0 if unit == "M" else 365.0)
    else:
        return max(0.2, val)


def _is_start_token(token: str) -> bool:
    t = token.strip()
    if t.lower().startswith("after "):
        return True
    if _parse_date(t) is not None:
        return True
    return False


class GanttParser:
    """Parser for Mermaid `gantt` diagrams."""

    def parse(self, mermaid_code: str) -> GanttDiagram:
        lines = preprocess_lines(mermaid_code)
        if not lines:
            raise MermaidParseError("Empty gantt diagram.")

        diagram = GanttDiagram()
        header_seen = False
        current_section = ""
        task_counter = 0

        for line_num, line in lines:
            if not header_seen:
                if line.lower().startswith("gantt"):
                    header_seen = True
                    continue
                else:
                    raise MermaidParseError("Expected 'gantt' header.", line_num, line)

            low = line.lower()
            if low.startswith("title "):
                diagram.title = line[6:].strip().strip('"')
                continue
            if low.startswith("dateformat "):
                diagram.date_format = line[11:].strip()
                continue
            if low.startswith("section "):
                current_section = line[8:].strip().strip('"')
                continue
            if any(low.startswith(p) for p in _IGNORE_PREFIXES) or low.startswith("click "):
                continue

            if ":" not in line:
                continue

            name_part, meta_part = line.split(":", 1)
            task_name = name_part.strip().strip('"')
            raw_tokens = [t.strip() for t in meta_part.split(",") if t.strip()]

            status = ""
            is_milestone = False
            pos_tokens: List[str] = []

            for tok in raw_tokens:
                tl = tok.lower()
                if tl in ("done", "active", "crit"):
                    # Keep 'crit' if combined like 'crit, active'
                    if status != "crit":
                        status = tl
                elif tl == "milestone":
                    is_milestone = True
                else:
                    pos_tokens.append(tok)

            task_counter += 1
            task_id = f"task_{task_counter}"
            start_raw = ""
            end_raw = ""

            if len(pos_tokens) >= 3:
                task_id = pos_tokens[0]
                start_raw = pos_tokens[1]
                end_raw = pos_tokens[2]
            elif len(pos_tokens) == 2:
                if _is_start_token(pos_tokens[0]):
                    start_raw = pos_tokens[0]
                    end_raw = pos_tokens[1]
                else:
                    task_id = pos_tokens[0]
                    if is_milestone and _is_start_token(pos_tokens[1]):
                        start_raw = pos_tokens[1]
                        end_raw = "0d"
                    else:
                        end_raw = pos_tokens[1]
            elif len(pos_tokens) == 1:
                tok0 = pos_tokens[0]
                if _parse_duration_days(tok0) is not None:
                    end_raw = tok0
                elif _is_start_token(tok0):
                    start_raw = tok0
                    end_raw = "0d" if is_milestone else "1d"
                else:
                    task_id = tok0
                    end_raw = "0d" if is_milestone else "1d"

            diagram.tasks.append(
                GanttTask(
                    id=task_id,
                    name=task_name,
                    section=current_section,
                    status=status,
                    start_raw=start_raw,
                    end_raw=end_raw,
                    is_milestone=is_milestone,
                )
            )

        # Resolve start_idx and duration in days
        anchor_date: Optional[datetime] = None
        for t in diagram.tasks:
            dt = _parse_date(t.start_raw)
            if dt is not None and (anchor_date is None or dt < anchor_date):
                anchor_date = dt

        resolved_end: Dict[str, float] = {}
        prev_end = 0.0

        for t in diagram.tasks:
            # 1. Resolve start_idx
            s_raw = t.start_raw.strip()
            dt_start = _parse_date(s_raw)
            if dt_start is not None and anchor_date is not None:
                start_val = float((dt_start - anchor_date).days)
            elif s_raw.lower().startswith("after "):
                ref_ids = s_raw[6:].strip().split()
                ref_ends = [resolved_end[rid] for rid in ref_ids if rid in resolved_end]
                start_val = max(ref_ends) if ref_ends else prev_end
            else:
                start_val = prev_end

            # 2. Resolve duration
            e_raw = t.end_raw.strip()
            dur_days = _parse_duration_days(e_raw)
            dt_end = _parse_date(e_raw)
            if t.is_milestone:
                dur_val = 0.2
            elif dur_days is not None:
                dur_val = max(0.5, dur_days)
            elif dt_end is not None and anchor_date is not None:
                end_offset = float((dt_end - anchor_date).days)
                dur_val = max(1.0, end_offset - start_val)
            else:
                dur_val = 2.0

            t.start_idx = round(start_val, 3)
            t.duration = round(dur_val, 3)
            task_finish = start_val + (0.0 if t.is_milestone else dur_val)
            resolved_end[t.id] = task_finish
            prev_end = task_finish

        if diagram.tasks:
            min_start = min(t.start_idx for t in diagram.tasks)
            if min_start != 0.0:
                for t in diagram.tasks:
                    t.start_idx = round(t.start_idx - min_start, 3)

        return diagram
