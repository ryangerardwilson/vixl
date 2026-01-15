from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExpressionRegisterEntry:
    kind: str  # "expression" or "comment_only"
    expr: str
    comment: str
    match_text: str


def _split_expression_comment(text: str):
    if not text:
        return "", ""

    in_single = False
    in_double = False
    escape = False
    for idx, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "#" and not in_single and not in_double:
            return text[:idx], text[idx + 1 :]
    return text, ""


def parse_expression_register_entry(raw: str) -> Optional[ExpressionRegisterEntry]:
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    comment_only_prefix = "%fz#/"
    if text.startswith(comment_only_prefix):
        comment = text[len(comment_only_prefix) :].strip()
        if not comment:
            return None
        return ExpressionRegisterEntry(
            kind="comment_only",
            expr="",
            comment=comment,
            match_text=comment,
        )

    expr_part, comment_part = _split_expression_comment(text)
    expr = expr_part.strip()
    comment = comment_part.strip()
    if not expr:
        return None

    match_text = expr if not comment else f"{expr} {comment}"
    return ExpressionRegisterEntry(
        kind="expression",
        expr=expr,
        comment=comment,
        match_text=match_text,
    )


def parse_expression_register(entries) -> List[ExpressionRegisterEntry]:
    parsed: List[ExpressionRegisterEntry] = []
    for raw in entries or []:
        entry = parse_expression_register_entry(raw)
        if entry:
            parsed.append(entry)
    return parsed
