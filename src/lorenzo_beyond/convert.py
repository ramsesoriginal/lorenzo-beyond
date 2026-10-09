"""A D&D Beyond character's inventory, as a ledger.

D&D Beyond keeps every item in one flat list. An item is in a container when its
`containerEntityId` is that container's id, and at the top of the sheet when it is the
character's own. Items on the sheet's top level are either equipped or just *on the character*;
the ledger only has *Equipped* and *Not carried*, so which of the unequipped ones are carried is
a choice, made by the caller (see `default_carried`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lorenzo_beyond import units
from lorenzo_beyond.errors import TooBig
from lorenzo_beyond.html import to_lorenzoscript
from lorenzo_beyond.ledger import (
    MAX_DEPTH,
    MAX_DESCRIPTION,
    MAX_LINES,
    MAX_QUANTITY,
    Ledger,
    Line,
)
from lorenzo_beyond.models import Character, CustomItem, InventoryItem, ItemDefinition

HEAVY_POUNDS = 50.0  # what a person does not walk around with
MOUNT_CAPACITY = 250.0  # a plain container that holds more than this is a cart, a horse, a barrel
LOOSE = "Loose items"
PURSE = "Coin purse"


@dataclass
class Entry:
    item: InventoryItem
    children: list[Entry] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.item.definition.name

    def count(self) -> int:
        return 1 + sum(child.count() for child in self.children)


@dataclass(frozen=True)
class Options:
    descriptions: bool = True
    coins: bool = True
    owner: str | None = None


@dataclass
class Conversion:
    ledger: Ledger
    warnings: list[str] = field(default_factory=list)

    @property
    def lines(self) -> int:
        return len(self.ledger.walk())

    @property
    def descriptions(self) -> int:
        return sum(1 for line, _ in self.ledger.walk() if line.description)


# ---- the tree --------------------------------------------------------------------------------


def build_tree(character: Character) -> tuple[list[Entry], list[str]]:
    """The sheet's top level, each entry holding what is in it."""
    entries = {item.id: Entry(item) for item in character.inventory}
    parents: dict[int, Entry] = {}
    roots: list[Entry] = []
    warnings: list[str] = []
    for item in character.inventory:
        parent = item.container_entity_id
        if parent in entries and parent != item.id:
            entries[parent].children.append(entries[item.id])
            parents[item.id] = entries[parent]
        else:
            if parent not in (None, character.id):
                warnings.append(f"{item.definition.name}: its container is not on the sheet")
            roots.append(entries[item.id])
    reached = _reach(roots)
    for entry in entries.values():  # containers that hold each other are never reached from the top
        if id(entry) in reached:
            continue
        warnings.append(f"{entry.name}: sits in a loop of containers, and is put at the top")
        parents[entry.item.id].children.remove(entry)
        roots.append(entry)
        reached |= _reach([entry])
    return roots, warnings


def _reach(starts: list[Entry]) -> set[int]:
    """Every entry under these, as `id()`s (a loop is walked once, never forever)."""
    seen: set[int] = set()
    pending = list(starts)
    while pending:
        entry = pending.pop()
        if id(entry) not in seen:
            seen.add(id(entry))
            pending.extend(entry.children)
    return seen


def own_pounds(entry: Entry) -> float:
    """What the entry itself weighs, without what is in it."""
    d = entry.item.definition
    return (units.weight_per_piece(d.weight, d.bundle_size) or 0.0) * entry.item.quantity


def pounds(entry: Entry) -> float:
    """What it weighs with its contents, as the sheet counts them (a Bag of Holding's weigh 0)."""
    inside = sum(pounds(child) for child in entry.children)
    return own_pounds(entry) + inside * entry.item.definition.weight_multiplier


# ---- on the character, or not ------------------------------------------------------------------


def unequipped_roots(roots: list[Entry]) -> list[Entry]:
    return [e for e in roots if not e.item.equipped]


def default_carried(roots: list[Entry], character: Character) -> set[int]:
    """The unequipped top-level items a person is likely to have on them.

    Left behind: anything named like one of the sheet's creatures (a mount listed as gear), and
    anything too heavy to walk with or too large to be a bag.
    """
    creatures = {c.name.casefold() for c in character.creatures}
    carried: set[int] = set()
    for entry in unequipped_roots(roots):
        d = entry.item.definition
        cart = d.is_container and not d.magic and (d.capacity_weight or 0) >= MOUNT_CAPACITY
        if entry.name.casefold() in creatures or cart or own_pounds(entry) >= HEAVY_POUNDS:
            continue
        carried.add(entry.item.id)
    return carried


# ---- one entry, one line -------------------------------------------------------------------------


def _kind(d: ItemDefinition) -> str | None:
    filter_type, kind, sub = (
        (d.filter_type or "").strip(),
        (d.type or "").strip(),
        (d.sub_type or ""),
    )
    text = (
        (sub.strip() or kind or "gear")
        if filter_type.lower() == "other gear"
        else (filter_type or kind)
    )
    return text.lower() or None


def _attunement(by: str) -> str:
    """`requires attunement`, in the words the sheet gives (“by a spellcaster”, “Spellcaster”)."""
    lowered = by.lower()
    if not by:
        return "requires attunement"
    if lowered.startswith("requires"):
        return lowered
    if lowered.startswith("by "):
        return f"requires attunement {lowered}"
    return f"requires attunement ({lowered})"


def _facts(d: ItemDefinition) -> list[str]:
    """What the sheet shows above an item's text: what it is, how rare, how it fights."""
    filter_type, kind = (d.filter_type or "").strip(), (d.type or "").strip()
    if filter_type.lower() == "other gear":
        label = (d.sub_type or kind or "gear").strip()
    elif filter_type and kind and kind.lower() != filter_type.lower():
        label = f"{filter_type} ({kind})"
    else:
        label = filter_type or kind
    head = [label] if label else []
    if d.rarity and d.rarity.lower() not in ("common", "unknown"):
        head.append(d.rarity.lower())
    if d.can_attune:
        head.append(_attunement((d.attunement_description or "").strip()))
    rows = [f"*{', '.join(head)}*"] if head else []
    stats: list[str] = []
    if d.damage and d.damage.dice_string:
        stats.append(
            " ".join(x for x in (d.damage.dice_string, (d.damage_type or "").lower()) if x)
        )
    stats += [p.name for p in d.properties or []]
    if d.armor_class:
        stats.append(f"AC {d.armor_class}")
    if d.is_container and d.capacity_weight:
        stats.append(f"holds up to {units.weight_text(d.capacity_weight)} lb")
    if stats:
        rows.append(" · ".join(stats))
    return rows


def _description(d: ItemDefinition, custom: CustomItem | None, warnings: list[str]) -> str | None:
    body = to_lorenzoscript(custom.description if custom and custom.description else d.description)
    text = "\n\n".join([*_facts(d), body] if body else _facts(d)).strip()
    if len(text) > MAX_DESCRIPTION:
        cut = text[: MAX_DESCRIPTION - 2].rsplit("\n\n", 1)[0].rstrip()
        warnings.append(f"{d.name}: its description was cut to fit the {MAX_DESCRIPTION:,} limit")
        text = cut + "\n\n…"
    return text or None


def _line(
    entry: Entry, customs: dict[int, CustomItem], options: Options, warnings: list[str]
) -> Line:
    item = entry.item
    d = item.definition
    custom = customs.get(d.id) if d.is_custom_item else None
    notes = ["Attuned" if item.is_attuned else "", (custom.notes or "").strip() if custom else ""]
    children = _merge([_line(c, customs, options, warnings) for c in entry.children])
    quantity = max(item.quantity, 1)
    if children and quantity > 1:
        warnings.append(f"{quantity} x {d.name} hold things, so one is written")
        quantity = 1
    return Line(
        name=d.name.strip(),
        quantity=quantity,
        weight=units.weight_per_piece(d.weight, d.bundle_size),
        value=units.price(d.cost),
        kind=_kind(d),
        note="; ".join(n for n in notes if n) or None,
        description=_description(d, custom, warnings) if options.descriptions else None,
        contents=children,
    )


def _merge(lines: list[Line]) -> list[Line]:
    """Rows that are the same thing become one stack (three separate daggers are `3 x Dagger`)."""
    merged: list[Line] = []
    for line in lines:
        twin = next((m for m in merged if m.same_as(line)), None)
        if twin is None:
            merged.append(line)
        else:
            twin.quantity += line.quantity
    return merged


def _split(lines: list[Line]) -> list[Line]:
    """A line holds at most MAX_QUANTITY; a larger stack is written as several."""
    out: list[Line] = []
    for line in lines:
        line.contents = _split(line.contents)
        left = line.quantity
        while left > MAX_QUANTITY:
            out.append(Line(**{**line.__dict__, "quantity": MAX_QUANTITY, "contents": []}))
            left -= MAX_QUANTITY
        line.quantity = left
        out.append(line)
    return out


def _gather_loose(lines: list[Line], warnings: list[str]) -> list[Line]:
    """A stack needs something to be in. Top-level stacks go into one container, said aloud."""
    loose = [line for line in lines if line.quantity > 1 and not line.is_container]
    if not loose:
        return lines
    names = ", ".join(line.name for line in loose[:3]) + (", …" if len(loose) > 3 else "")
    warnings.append(
        f"{len(loose)} loose stack(s) ({names}) went into “{LOOSE}”: "
        "a stack in a ledger needs a container"
    )
    kept = [line for line in lines if line not in loose]
    return [*kept, Line(name=LOOSE, contents=loose)]


# ---- the whole sheet ----------------------------------------------------------------------


def convert(
    character: Character, *, carried: set[int] | None = None, options: Options | None = None
) -> Conversion:
    """The character's inventory as a ledger. `carried` picks which unequipped top-level items
    are on the character (their ids); left out, `default_carried` decides."""
    options = options or Options()
    roots, warnings = build_tree(character)
    if carried is None:
        carried = default_carried(roots, character)
    customs = {c.id: c for c in character.custom_items}
    equipped: list[Line] = []
    not_carried: list[Line] = []
    for entry in roots:
        line = _line(entry, customs, options, warnings)
        on_person = entry.item.equipped or entry.item.id in carried
        (equipped if on_person else not_carried).append(line)

    if options.coins:
        note, worth = units.purse(character.currencies.as_dict())
        if note:
            equipped.append(Line(name=PURSE, value=worth, note=note))

    ledger = Ledger(
        owner=options.owner or character.name,
        equipped=_gather_loose(_split(equipped), warnings),
        not_carried=_gather_loose(_split(not_carried), warnings),
    )
    _check(ledger)
    return Conversion(ledger, warnings)


def _check(ledger: Ledger) -> None:
    walked = ledger.walk()
    if len(walked) > MAX_LINES:
        raise TooBig(
            f"This inventory has {len(walked)} lines, and a ledger holds at most {MAX_LINES}.",
            "Use --leave-behind for the containers you do not need, or split it into two files.",
        )
    deepest = max((depth for _, depth in walked), default=0)
    if deepest >= MAX_DEPTH:
        raise TooBig(
            f"Containers inside containers go {MAX_DEPTH} levels deep in a ledger, no more."
        )
