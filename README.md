# ✧ lorenzo-beyond

Bring a public [D&D Beyond](https://www.dndbeyond.com) character's inventory into
[Lorenzo](https://github.com/ramsesoriginal/lorenzo), as a **LorenzoLedger** file.

```console
$ uvx lorenzo-beyond
✧ Lorenzo  Beyond

✧ Which character? (paste the sheet's link, or its number)
✧ What is Mira carrying, besides what is equipped?
 » ● Bag of Holding  (15 lb, 16 inside)
   ● Backpack  (48 lb, 12 inside)
   ○ Barrel  (70 lb)
   ○ Riding Horse  (25 lb, 1 inside)

Character    Mira
Equipped     11 at the top
Not carried  3 at the top
In all       41 things, 3 containers, 36 descriptions

Wrote mira.ledger.md.
Next: lorenzo inventory import mira.ledger.md --tenant <library>
```

## Install

```sh
uvx lorenzo-beyond          # run without installing
pipx install lorenzo-beyond # or install it
```

Python 3.12 or newer. The command is `lorenzo-beyond`, also `lrnzo-ddb`.

## Use

Run it with nothing to be asked, or give it the sheet's link or number:

```sh
lorenzo-beyond inventory https://www.dndbeyond.com/characters/12345678
lorenzo-beyond inventory 12345678 -o mira.ledger.md --no-input
lorenzo-beyond inventory 12345678 -o - | lorenzo inventory import - --tenant my-library
```

| Option | |
| --- | --- |
| `-o, --output FILE` | Where to write. Default `NAME.ledger.md`; `-` is standard output, which carries the ledger and nothing else. |
| `--json` | Write the JSON form instead of Markdown. |
| `--carry NAME` / `--leave-behind NAME` | Decide where a top-level item goes, without being asked. Repeatable. |
| `--no-descriptions` / `--no-coins` | Leave out item text, or the coin purse. |
| `--owner NAME` | The ledger's owner, if not the character's name. |
| `--from-file FILE` | Read a saved character document instead of asking D&D Beyond. |
| `-f, --force` / `--no-input` | Replace a file that exists / never ask a question. |

Exit status: `0` done, `1` something to fix in what you asked, `2` D&D Beyond would not show the
character or could not be reached, `3` D&D Beyond's document is not in a shape this version knows.

## What you get

A [LorenzoLedger](https://github.com/ramsesoriginal/lorenzo/blob/main/docs/guides/inventory-file-format.md):
a plain-text list of what the character owns, where it is, and what is known about it.

```markdown
format: lorenzo-ledger/1
owner: Mira

## Equipped
- Pearl of Power | kind: wondrous item | note: Attuned
  > *Wondrous item, uncommon, requires attunement (spellcaster)*
  >
  > While this pearl is on your person, you can take a Magic action to regain one expended spell slot…
- Backpack | weight: 5 | value: 2 gp | kind: adventuring gear
  > *Adventuring Gear*
  >
  > holds up to 30 lb
  - 7 x Rations (1 day) | weight: 2 | value: 5 sp | kind: adventuring gear
```

- **Equipped** is what the character holds or wears, plus the bags and things they have on them.
  D&D Beyond has a third state, *on the character but not equipped*; Lorenzo has two. You choose
  which of those are with the character. By default heavy things (50 lb or more), mounts and carts
  are left under **Not carried**.
- **Containers** keep their contents. Separate rows of the same thing inside a container become one
  stack (three daggers are `3 x Dagger`). A stack at the top of a section has nowhere to be, so it goes
  into a container named *Loose items*, and you are told.
- **Weight** is per piece, in pounds (a bundle's weight is shared among its pieces). **Value** is in
  the largest exact coin. **Descriptions** are the item's text, with its type, rarity, attunement,
  damage and properties above it, as Markdown. Homebrew and custom items come along with their notes.
- **Coins** are one line, *Coin purse*, with the coins in its note.
- Attunement is the character's, so it goes in the item's note.

Then, in Lorenzo, `lorenzo inventory import mira.ledger.md --tenant <library>` makes it.

## Private characters, and the API

Only characters anyone can open without logging in can be read: in D&D Beyond open the character,
then *Settings → Character Privacy*, and choose *Public*. This tool has no login and stores no
credentials.

It reads the character service behind the public character sheet. That service is **unofficial**:
not documented, not promised, and it may change or be closed. Everything that knows about it is in
one small module (`client.py`); when the shape changes, the tool says where (exit status `3`) rather
than writing something wrong. Please be considerate: it makes one request per run.

lorenzo-beyond is not affiliated with or endorsed by Wizards of the Coast or D&D Beyond. D&D Beyond
is a trademark of its owner. Item text belongs to its publishers; use it for your own table.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

`tests/fixtures/character.json` is a real character sheet reduced to what the tool reads, with the
item text replaced by synthetic text. `tests/conformance.py` is an independent reader of the
ledger rules that every file the tool writes is held to.

Releases: bump `version` in `pyproject.toml`, push a `vX.Y.Z` tag; the release workflow publishes to
PyPI by trusted publishing.

## License

MIT
