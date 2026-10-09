"""The one place that talks to D&D Beyond.

It uses the character service behind the public character sheet. That service is not
documented or promised, so everything that knows its address, its envelope or its failures
lives here, and the rest of the package only sees a `Character`.

Only characters a visitor can already open without logging in are available. This module has no
login, no cookie and no way to get one.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from lorenzo_beyond import __version__
from lorenzo_beyond.errors import BadReference, ChangedShape, NotAvailable, Unreachable
from lorenzo_beyond.models import Character, Envelope

SERVICE = "https://character-service.dndbeyond.com/character/v5/character/{id}"
USER_AGENT = f"lorenzo-beyond/{__version__} (+https://github.com/ramsesoriginal/lorenzo-beyond)"

_ID = re.compile(r"^\d{1,12}$")
_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?dndbeyond\.com/(?:profile/[^/]+/)?characters/(?P<id>\d{1,12})(?:[/?#].*)?$",
    re.IGNORECASE,
)
_SERVICE_URL = re.compile(
    r"^(?:https?://)?character-service\.dndbeyond\.com/character/v\d+/character/(?P<id>\d{1,12})"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)


def parse_reference(text: str) -> int:
    """A character id, or a link to its sheet (`dndbeyond.com/characters/12345678/AbC123`)."""
    text = text.strip()
    if _ID.match(text):
        return int(text)
    for pattern in (_URL, _SERVICE_URL):
        found = pattern.match(text)
        if found:
            return int(found["id"])
    raise BadReference(
        f"“{text}” is not a D&D Beyond character.",
        "Paste the link of the character sheet, such as "
        "https://www.dndbeyond.com/characters/12345678, or just its number.",
    )


def read_document(raw: str | bytes) -> Character:
    """The character in a saved or fetched JSON document, or a `ChangedShape` saying where."""
    try:
        envelope = Envelope.model_validate_json(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "the document"
        raise ChangedShape(
            f"D&D Beyond's character document is not in the shape expected (at {where}).",
            "D&D Beyond may have changed it. Please report this, with that location, at "
            "https://github.com/ramsesoriginal/lorenzo-beyond/issues (not the character's data).",
        ) from exc
    if not envelope.success or envelope.data is None:
        raise NotAvailable(
            "D&D Beyond would not show this character"
            + (f" (“{envelope.message}”)." if envelope.message else "."),
            "Only public characters can be read. In D&D Beyond, open the character, then "
            "Settings → Character Privacy, and choose Public.",
        )
    return envelope.data


def fetch(
    character_id: int,
    *,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 20.0,
    attempts: int = 2,
) -> Character:
    """Read a public character. Retries once on a dropped connection or a server error."""
    params: dict[str, Any] = {"includeCustomItems": "true"}
    last: Exception | None = None
    with httpx.Client(
        transport=transport,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        for attempt in range(attempts):
            try:
                response = client.get(SERVICE.format(id=character_id), params=params)
            except httpx.TransportError as exc:
                last = exc
            else:
                if response.status_code in (401, 403, 404):
                    raise NotAvailable(
                        f"D&D Beyond has no public character {character_id}.",
                        "Check the link. A private character cannot be read: in D&D Beyond, "
                        "open it, then Settings → Character Privacy, and choose Public.",
                    )
                if response.status_code >= 500:
                    last = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )
                elif response.status_code >= 400:
                    raise Unreachable(
                        f"D&D Beyond answered {response.status_code}.",
                        "Try again in a moment. If it keeps happening, please report it.",
                    )
                else:
                    return read_document(response.content)
            if attempt + 1 < attempts:
                time.sleep(0.5)
    advice = (
        "A proxy or firewall refused the connection to character-service.dndbeyond.com."
        if isinstance(last, httpx.ProxyError)
        else "Check your connection and try again."
    )
    raise Unreachable(
        "Could not reach D&D Beyond.", f"{advice} ({type(last).__name__ if last else 'no answer'})"
    )
