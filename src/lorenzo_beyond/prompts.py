"""The questions, asked with questionary. Every one can be answered with a flag instead, and none
is asked when there is nobody to ask (a pipe, a script, CI)."""

from __future__ import annotations

import questionary
from questionary import Choice, Style

from lorenzo_beyond import units
from lorenzo_beyond.client import parse_reference
from lorenzo_beyond.convert import Entry, pounds
from lorenzo_beyond.errors import BadReference
from lorenzo_beyond.ui import GOLD

STYLE = Style(
    [
        ("qmark", f"fg:{GOLD} bold"),
        ("question", "bold"),
        ("pointer", f"fg:{GOLD} bold"),
        ("highlighted", "bold"),
        ("selected", ""),
        ("answer", f"fg:{GOLD}"),
        ("instruction", "fg:#757B80"),
    ]
)


class Cancelled(Exception):
    """The person stopped (Ctrl-C or Esc) at a question."""


def _answer[T](value: T | None) -> T:
    if value is None:
        raise Cancelled
    return value


def _valid(text: str) -> bool | str:
    try:
        parse_reference(text)
    except BadReference as error:
        return str(error)
    return True


def ask_character() -> str:
    answer: str = _answer(
        questionary.text(
            "Which character?",
            instruction="(paste the sheet's link, or its number)",
            validate=_valid,
            qmark="✧",
            style=STYLE,
        ).ask()
    )
    return answer


def _title(entry: Entry) -> str:
    inside = entry.count() - 1
    facts = []
    weight = pounds(entry)
    if weight:
        facts.append(f"{units.weight_text(round(weight, 1))} lb")
    if inside:
        facts.append(f"{inside} inside")
    if entry.item.quantity > 1:
        facts.append(f"{entry.item.quantity} pieces")
    return entry.name + (f"  ({', '.join(facts)})" if facts else "")


def ask_carried(name: str, unequipped: list[Entry], default: set[int]) -> set[int]:
    """Which of the things that are on the character but not equipped are with them."""
    picked = _answer(
        questionary.checkbox(
            f"What is {name} carrying, besides what is equipped?",
            choices=[
                Choice(_title(entry), value=entry.item.id, checked=entry.item.id in default)
                for entry in unequipped
            ],
            instruction="(space toggles, enter confirms; the rest is Not carried)",
            qmark="✧",
            style=STYLE,
        ).ask()
    )
    return set(picked)


def confirm_overwrite(name: str) -> bool:
    answer: bool = _answer(
        questionary.confirm(
            f"{name} already exists. Replace it?", default=False, qmark="✧", style=STYLE
        ).ask()
    )
    return answer
