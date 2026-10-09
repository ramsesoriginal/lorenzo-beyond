"""D&D Beyond's item text is HTML. A ledger's descriptions are LorenzoScript, which is Markdown.

This reads the small set of tags the character sheet uses (paragraphs, emphasis, lists, tables,
headings, links) and writes Markdown. Anything it does not know is read through, so its text
survives even when its tag does not.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_BREAK = "\u0000"
_TAGS = re.compile(r"</?[a-zA-Z][^>]*>")
_HEADINGS = {f"h{n}": "#" * n for n in range(1, 7)}
_BLOCKS = {"p", "div", "section", "blockquote", "tr", "ul", "ol", "li", "table", *_HEADINGS}
_SKIP = {"script", "style"}


class _Markdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []  # (kind, text); kind is "li" or "block"
        self._inline: list[str] = []
        self._lists: list[list[str | int]] = []  # [kind, counter]
        self._marker = ""  # the bullet or number the next paragraph starts with
        self._fresh = False  # the next item opens a list at the top level
        self._heading = ""
        self._links: list[str | None] = []
        self._table: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._saved: list[str] = []  # the paragraph being written while a table cell is
        self._skipping = 0

    # -- output ------------------------------------------------------------------------------

    def _text(self) -> str:
        raw = "".join(self._inline)
        self._inline = []
        lines = [re.sub(r"[ \t\r\n]+", " ", part).strip() for part in raw.split(_BREAK)]
        return "  \n".join(line for line in lines if line) if any(lines) else ""

    def _flush(self) -> None:
        if self._cell is not None:
            return
        text = self._text()
        if not text:
            self._marker = ""
            return
        if self._heading:
            self.blocks.append(("block", f"{self._heading} {text}"))
        elif self._lists:
            depth = "  " * (len(self._lists) - 1)
            if self._marker:
                kind = "lifirst" if self._fresh and len(self._lists) == 1 else "li"
                self._fresh = False
                self.blocks.append((kind, f"{depth}{self._marker} {text}"))
            else:  # a second paragraph in the same item
                self.blocks.append(("li", f"{depth}  {text}"))
        else:
            self.blocks.append(("block", text))
        self._marker = ""

    # -- tags --------------------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skipping += 1
            return
        if tag == "br":
            self._inline.append(_BREAK)
        elif tag in ("strong", "b"):
            self._inline.append("**")
        elif tag in ("em", "i"):
            self._inline.append("*")
        elif tag == "sup":
            self._inline.append("^")
        elif tag == "sub":
            self._inline.append("~")
        elif tag == "code":
            self._inline.append("`")
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            absolute = href if href.startswith(("http://", "https://")) else None
            self._links.append(absolute)
            if absolute:
                self._inline.append("[")
        elif tag == "hr":
            self._flush()
            self.blocks.append(("block", "---"))
        elif tag in ("ul", "ol"):
            self._flush()
            self._fresh = not self._lists
            self._lists.append([tag, 0])
        elif tag == "li":
            self._flush()
            if self._lists:
                top = self._lists[-1]
                top[1] = int(top[1]) + 1
                self._marker = "-" if top[0] == "ul" else f"{top[1]}."
        elif tag in _HEADINGS:
            self._flush()
            self._heading = _HEADINGS[tag]
        elif tag == "table":
            self._flush()
            self._table = []
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
            self._saved, self._inline = self._inline, []
        elif tag in _BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skipping = max(0, self._skipping - 1)
            return
        if tag in ("strong", "b"):
            self._inline.append("**")
        elif tag in ("em", "i"):
            self._inline.append("*")
        elif tag == "sup":
            self._inline.append("^")
        elif tag == "sub":
            self._inline.append("~")
        elif tag == "code":
            self._inline.append("`")
        elif tag == "a":
            href = self._links.pop() if self._links else None
            if href:
                self._inline.append(f"]({href})")
        elif tag in ("ul", "ol"):
            self._flush()
            if self._lists:
                self._lists.pop()
        elif tag in _HEADINGS:
            self._flush()
            self._heading = ""
        elif tag in ("td", "th"):
            text = self._text().replace("|", "\\|").replace("  \n", " ")
            self._inline = self._saved
            self._cell = None
            if self._row is not None:
                self._row.append(text)
        elif tag == "tr":
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table":
            self._write_table()
        elif tag in _BLOCKS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._inline.append(data)

    def _write_table(self) -> None:
        rows = [row for row in self._table if any(row)]
        self._table = []
        if not rows:
            return
        width = max(len(row) for row in rows)
        padded = [row + [""] * (width - len(row)) for row in rows]
        lines = ["| " + " | ".join(padded[0]) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(row) + " |" for row in padded[1:]]
        self.blocks.append(("block", "\n".join(lines)))

    def result(self) -> str:
        self._flush()
        out: list[str] = []
        previous = ""
        for kind, text in self.blocks:
            if out and not (kind == "li" and previous in ("li", "lifirst")):
                out.append("")
            out.append(text)
            previous = kind
        return "\n".join(out).strip()


def to_lorenzoscript(source: str | None) -> str:
    """D&D Beyond HTML (or plain text) as Markdown; empty when there is no text."""
    if not source or not source.strip():
        return ""
    if not _TAGS.search(source):  # plain text, as a homebrew item's description often is
        return "\n".join(line.rstrip() for line in source.strip().splitlines())
    parser = _Markdown()
    parser.feed(source)
    parser.close()
    return parser.result()
