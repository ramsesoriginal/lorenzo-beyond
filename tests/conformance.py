"""A strict reader of the LorenzoLedger rules, to hold what this tool writes to the format.

Written from the specification (docs/guides/inventory-file-format.md in Lorenzo's repository),
not copied from its parser, so it is an independent check.
"""

from __future__ import annotations

import re

MAX_LINES, MAX_DEPTH, MAX_QUANTITY, MAX_DESCRIPTION = 1024, 6, 1000, 20_000
ITEM = re.compile(r"^(?P<indent> *)- (?P<rest>\S.*)$")
COUNT = re.compile(r"^(?P<n>\d+) x (?P<name>.+)$")
FIELDS = {"ref", "item", "weight", "value", "kind", "note", "place"}


def problems(text: str) -> list[str]:
    out: list[str] = []
    lines = text.split("\n")
    if lines[0] != "format: lorenzo-ledger/1":
        out.append("the first line is the format")
    if not lines[1].startswith("owner: "):
        out.append("the second line is the owner")
    section: str | None = None
    items = 0
    prev_level = -1
    prev_item: dict[str, int | bool] = {}
    descriptions: dict[int, list[str]] = {}
    for number, line in enumerate(lines[2:], start=3):
        if line.startswith("## "):
            if line[3:] not in ("Equipped", "Not carried"):
                out.append(f"{number}: unknown section")
            section, prev_level = line[3:], -1
            continue
        quote = re.match(r"^ *>( ?)(.*)$", line)
        if quote:
            if not prev_item:
                out.append(f"{number}: a quote with no item above it")
            else:
                descriptions.setdefault(int(prev_item["number"]), []).append(quote.group(2))
            continue
        match = ITEM.match(line)
        if not match:
            if line.strip():
                out.append(f"{number}: not an item or a quote: {line!r}")
            continue
        if section is None:
            out.append(f"{number}: an item before a section")
        indent = len(match["indent"])
        if indent % 2:
            out.append(f"{number}: indent by two spaces")
        level = indent // 2
        if level >= MAX_DEPTH:
            out.append(f"{number}: too deep")
        if level > prev_level + 1:
            out.append(f"{number}: indented too far")
        prev_level = level
        items += 1
        parts = re.split(r"(?<!\\) \| ", match["rest"])
        name = parts[0]
        counted = COUNT.match(name)
        quantity = int(counted["n"]) if counted else 1
        if quantity < 1 or quantity > MAX_QUANTITY:
            out.append(f"{number}: quantity out of range")
        for part in parts[1:]:
            key = part.split(":", 1)[0]
            if key not in FIELDS or ":" not in part:
                out.append(f"{number}: unknown field {key!r}")
        prev_item = {"number": number, "level": level, "quantity": quantity}
        if quantity > 1 and level == 0:
            out.append(f"{number}: a stack at the top of a section")
    if items > MAX_LINES:
        out.append("too many lines")
    for number, rows in descriptions.items():
        if len("\n".join(rows)) > MAX_DESCRIPTION:
            out.append(f"{number}: description too long")
    return out
