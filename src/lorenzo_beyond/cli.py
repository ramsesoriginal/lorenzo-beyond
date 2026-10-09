"""`lorenzo-beyond`: a public D&D Beyond character's inventory, as a LorenzoLedger."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from lorenzo_beyond import __version__, client, convert, ledger, prompts, ui
from lorenzo_beyond.errors import BadReference, BeyondError
from lorenzo_beyond.models import Character

app = typer.Typer(
    name="lorenzo-beyond",
    help="Bring a public D&D Beyond character's inventory into Lorenzo, as a LorenzoLedger file.",
    no_args_is_help=False,
    add_completion=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode="markdown",
)


def _version(show: bool) -> None:
    if show:
        typer.echo(f"lorenzo-beyond {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Show the version.", callback=_version, is_eager=True),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if _can_ask():
        ctx.invoke(inventory)
    else:
        typer.echo(ctx.get_help())


def _can_ask() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "character"


def _choose(roots: list[convert.Entry], names: list[str], what: str) -> set[int]:
    """The ids of the unequipped top-level items called `names` (any case)."""
    by_name: dict[str, list[int]] = {}
    for entry in convert.unequipped_roots(roots):
        by_name.setdefault(entry.name.casefold(), []).append(entry.item.id)
    ids: set[int] = set()
    for name in names:
        found = by_name.get(name.strip().casefold())
        if not found:
            options = ", ".join(sorted({e.name for e in convert.unequipped_roots(roots)})) or "none"
            raise BadReference(
                f"“{name}” is not one of the things on the sheet's top level that {what}.",
                f"These are: {options}.",
            )
        ids.update(found)
    return ids


@app.command(
    help="Write a character's inventory as a ledger, ready for `lorenzo inventory import`.",
    epilog="Only public characters can be read. Run with no arguments to be asked.",
)
def inventory(
    character: Annotated[
        str | None,
        typer.Argument(
            help="The character sheet's link, or its number.",
            show_default=False,
            metavar="CHARACTER",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Where to write. `-` is standard output.",
            show_default="NAME.ledger.md",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Write the JSON form.")] = False,
    from_file: Annotated[
        Path | None,
        typer.Option(
            "--from-file", help="Read a saved character document instead of asking D&D Beyond."
        ),
    ] = None,
    carry: Annotated[
        list[str] | None,
        typer.Option(
            "--carry", help="A top-level item to count as with the character. Repeatable."
        ),
    ] = None,
    leave_behind: Annotated[
        list[str] | None,
        typer.Option(
            "--leave-behind", help="A top-level item to put under Not carried. Repeatable."
        ),
    ] = None,
    no_descriptions: Annotated[
        bool, typer.Option("--no-descriptions", help="Leave out item text.")
    ] = False,
    no_coins: Annotated[bool, typer.Option("--no-coins", help="Leave out the coin purse.")] = False,
    owner: Annotated[
        str | None,
        typer.Option("--owner", help="The ledger's owner.", show_default="the character's name"),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Replace a file that exists.")
    ] = False,
    no_input: Annotated[bool, typer.Option("--no-input", help="Never ask a question.")] = False,
) -> None:
    console = ui.make_console()
    asking = _can_ask() and not no_input
    try:
        if console.is_terminal:
            ui.header(console)
        sheet = _read(console, character, from_file, asking)
        roots, tree_warnings = convert.build_tree(sheet)
        carried = _carried(sheet, roots, carry, leave_behind, asking)
        result = convert.convert(
            sheet,
            carried=carried,
            options=convert.Options(
                descriptions=not no_descriptions, coins=not no_coins, owner=owner
            ),
        )
        result.warnings[:0] = tree_warnings
        text = (
            ledger.render_json(result.ledger) if as_json else ledger.render_markdown(result.ledger)
        )
        target = _target(output, sheet.name, as_json, force, asking)
        _write(target, text)
        _report(console, sheet, result, target)
    except BeyondError as error:
        ui.problem(console, error)
        raise typer.Exit(error.code) from error
    except prompts.Cancelled:
        console.print("Cancelled. Nothing was written.", style="quiet")
        raise typer.Exit(130) from None


def _read(console: Console, reference: str | None, saved: Path | None, asking: bool) -> Character:
    if saved is not None:
        try:
            return client.read_document(saved.read_bytes())
        except OSError as error:
            raise BeyondError(f"Could not read {saved}: {error.strerror or error}.") from error
    if reference is None:
        if not asking:
            raise BadReference(
                "Which character?",
                "Give the sheet's link or number: lorenzo-beyond inventory 12345678",
            )
        reference = prompts.ask_character()
    number = client.parse_reference(reference)
    with console.status("Asking D&D Beyond…", spinner="dots"):
        return client.fetch(number)


def _carried(
    sheet: Character,
    roots: list[convert.Entry],
    carry: list[str] | None,
    leave: list[str] | None,
    asking: bool,
) -> set[int]:
    carried = convert.default_carried(roots, sheet)
    if carry or leave:
        return (carried - _choose(roots, leave or [], "can be left behind")) | _choose(
            roots, carry or [], "can be carried"
        )
    unequipped = convert.unequipped_roots(roots)
    if asking and unequipped:
        return prompts.ask_carried(sheet.name, unequipped, carried)
    return carried


def _target(
    output: Path | None, name: str, as_json: bool, force: bool, asking: bool
) -> Path | None:
    """Where to write: a path, or `None` for standard output."""
    if output is not None and str(output) == "-":
        return None
    path = output or Path(f"{_slug(name)}.ledger.{'json' if as_json else 'md'}")
    if path.exists() and not force:
        if asking:
            if not prompts.confirm_overwrite(path.name):
                raise prompts.Cancelled
        else:
            raise BeyondError(
                f"{path} already exists.",
                "Use --force to replace it, or -o to choose another file.",
            )
    return path


def _write(target: Path | None, text: str) -> None:
    if target is None:
        sys.stdout.write(text)
        return
    try:
        target.write_text(text, encoding="utf-8", newline="\n")
    except OSError as error:
        raise BeyondError(f"Could not write {target}: {error.strerror or error}.") from error


def _report(
    console: Console, sheet: Character, result: convert.Conversion, target: Path | None
) -> None:
    containers = sum(1 for line, _ in result.ledger.walk() if line.is_container)
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="quiet")
    grid.add_column()
    grid.add_row("Character", sheet.name)
    grid.add_row("Equipped", f"{len(result.ledger.equipped)} at the top")
    grid.add_row("Not carried", f"{len(result.ledger.not_carried)} at the top")
    grid.add_row(
        "In all",
        f"{result.lines} things, {containers} containers, {result.descriptions} descriptions",
    )
    console.print()
    console.print(grid)
    ui.bullets(console, "Worth a look", result.warnings)
    where = "standard output" if target is None else str(target)
    console.print(f"\nWrote {where}.", style="good")
    if target is not None:
        console.print(
            f"Next: lorenzo inventory import {target} --tenant <library>",
            style="quiet",
            soft_wrap=True,
        )


def main() -> None:
    app()
