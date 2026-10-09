"""How the tool looks and sounds: Lorenzo's CLI identity (docs/brand/identity.md §12.6, §14).

`✧ Lorenzo` with the spark in Medici Gold, the descriptor quiet beside it, no banner art, no
colour that is the only carrier of meaning, and words for every state. Everything for a person
goes to standard error, so standard output stays free for the ledger itself.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

from lorenzo_beyond import __version__
from lorenzo_beyond.errors import BeyondError

GOLD = "#B88A3B"  # Medici Gold

THEME = Theme(
    {
        "spark": f"bold {GOLD}",
        "quiet": "dim",
        "problem": "bold red",
        "caution": "yellow",
        "good": "bold",
    }
)


def make_console() -> Console:
    return Console(stderr=True, theme=THEME, highlight=False)


def spark(console: Console) -> str:
    """`✧`, or `*` where the terminal cannot show it."""
    encoding = (console.encoding or "").lower()
    return "✧" if encoding.startswith("utf") else "*"


def header(console: Console) -> None:
    line = Text.assemble((spark(console), "spark"), " Lorenzo", ("  Beyond", "quiet"))
    console.print(line)
    console.print(Text(f"  {__version__}", "quiet"))


def problem(console: Console, error: BeyondError) -> None:
    console.print(Text.assemble(("Couldn't do that. ", "problem"), str(error)))
    if error.hint:
        console.print(Text(f"  {error.hint}", "quiet"))


def bullets(console: Console, title: str, rows: list[str]) -> None:
    if not rows:
        return
    console.print(Text(f"\n{title} ({len(rows)})", "caution"))
    for row in rows:
        console.print(Text(f"  · {row}"))
