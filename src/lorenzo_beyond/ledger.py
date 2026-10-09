"""A LorenzoLedger (format `lorenzo-ledger/1`), written.

The format is specified in Lorenzo's repository
(https://github.com/ramsesoriginal/lorenzo/blob/main/docs/guides/inventory-file-format.md and
ADR 0226). This writes it and nothing else: there is no reader here, since reading is
`lorenzo inventory import`'s job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from lorenzo_beyond.units import weight_text

FORMAT = "lorenzo-ledger/1"
MAX_LINES = 1024
MAX_DEPTH = 6
MAX_QUANTITY = 1000
MAX_DESCRIPTION = 20_000


@dataclass
class Line:
    """One thing, or a container when `contents` is not empty."""

    name: str
    quantity: int = 1
    weight: float | None = None  # pounds, one piece
    value: str | None = None
    kind: str | None = None
    note: str | None = None
    description: str | None = None
    contents: list[Line] = field(default_factory=list)

    @property
    def is_container(self) -> bool:
        return bool(self.contents)

    def same_as(self, other: Line) -> bool:
        """Alike in every way but how many, and neither holds anything."""
        return (
            not self.contents
            and not other.contents
            and (self.name, self.weight, self.value, self.kind, self.note, self.description)
            == (other.name, other.weight, other.value, other.kind, other.note, other.description)
        )


@dataclass
class Ledger:
    owner: str
    equipped: list[Line] = field(default_factory=list)
    not_carried: list[Line] = field(default_factory=list)

    def walk(self) -> list[tuple[Line, int]]:
        """Every line with its depth, a container before what is in it."""
        out: list[tuple[Line, int]] = []

        def visit(lines: list[Line], depth: int) -> None:
            for line in lines:
                out.append((line, depth))
                visit(line.contents, depth + 1)

        visit(self.equipped, 0)
        visit(self.not_carried, 0)
        return out


def _text(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _lines(line: Line, depth: int) -> list[str]:
    head = f"{line.quantity} x " if line.quantity != 1 else ""
    parts = [f"{head}{_text(line.name)}"]
    if line.weight is not None:
        parts.append(f"weight: {weight_text(line.weight)}")
    for key in ("value", "kind", "note"):
        value = getattr(line, key)
        if value:
            parts.append(f"{key}: {_text(value)}")
    pad = "  " * depth
    rows = [f"{pad}- " + " | ".join(parts)]
    if line.description:
        rows += [f"{pad}  > {row}".rstrip() for row in line.description.split("\n")]
    for child in line.contents:
        rows.extend(_lines(child, depth + 1))
    return rows


def render_markdown(ledger: Ledger) -> str:
    rows = [f"format: {FORMAT}", f"owner: {_text(ledger.owner)}"]
    for heading, lines in (("Equipped", ledger.equipped), ("Not carried", ledger.not_carried)):
        rows += ["", f"## {heading}"]
        for line in lines:
            rows.extend(_lines(line, 0))
    return "\n".join(rows) + "\n"


def _json_line(line: Line) -> dict[str, Any]:
    out: dict[str, Any] = {"name": line.name}
    if line.quantity != 1:
        out["quantity"] = line.quantity
    if line.weight is not None:
        out["weight"] = round(line.weight, 4)
    for key in ("value", "kind", "note", "description"):
        value = getattr(line, key)
        if value:
            out[key] = value
    if line.contents:
        out["contents"] = [_json_line(child) for child in line.contents]
    return out


def render_json(ledger: Ledger) -> str:
    document = {
        "format": FORMAT,
        "owner": ledger.owner,
        "equipped": [_json_line(line) for line in ledger.equipped],
        "not_carried": [_json_line(line) for line in ledger.not_carried],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
