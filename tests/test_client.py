import json
from pathlib import Path

import httpx
import pytest

from lorenzo_beyond import client
from lorenzo_beyond.errors import BadReference, ChangedShape, NotAvailable, Unreachable

FIXTURE = Path(__file__).parent / "fixtures" / "character.json"


@pytest.mark.parametrize(
    "text",
    [
        "12345678",
        " 12345678 ",
        "https://www.dndbeyond.com/characters/12345678",
        "https://www.dndbeyond.com/characters/12345678/AbC123",
        "http://dndbeyond.com/characters/12345678?x=1",
        "dndbeyond.com/profile/someone/characters/12345678",
        "https://character-service.dndbeyond.com/character/v5/character/12345678?includeCustomItems=true",
    ],
)
def test_a_number_or_any_sheet_link_names_a_character(text: str) -> None:
    assert client.parse_reference(text) == 12345678


@pytest.mark.parametrize(
    "text",
    ["", "character", "https://example.com/characters/1", "https://www.dndbeyond.com/spells/12"],
)
def test_anything_else_is_refused_with_a_way_forward(text: str) -> None:
    with pytest.raises(BadReference) as caught:
        client.parse_reference(text)

    assert caught.value.hint and "dndbeyond.com/characters" in caught.value.hint


def _transport(handler: httpx.MockTransport | None = None, **answer: object) -> httpx.MockTransport:
    if handler is not None:
        return handler
    return httpx.MockTransport(lambda request: httpx.Response(**answer))  # type: ignore[arg-type]


def test_a_public_character_is_read() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=FIXTURE.read_bytes())

    character = client.fetch(12345678, transport=httpx.MockTransport(answer))

    assert character.name == "Mira" and len(character.inventory) == 42
    request = seen[0]
    assert request.url.path == "/character/v5/character/12345678"
    assert request.url.params["includeCustomItems"] == "true"
    assert request.headers["user-agent"].startswith("lorenzo-beyond/")
    assert request.headers.get("cookie") is None and request.headers.get("authorization") is None


@pytest.mark.parametrize("status", [401, 403, 404])
def test_a_character_that_is_not_public_says_how_to_make_it_so(status: int) -> None:
    with pytest.raises(NotAvailable) as caught:
        client.fetch(1, transport=_transport(status_code=status))

    assert caught.value.code == 2 and "Public" in (caught.value.hint or "")


def test_an_envelope_that_says_no_is_the_same_story() -> None:
    body = json.dumps({"success": False, "message": "Forbidden", "data": None})

    with pytest.raises(NotAvailable) as caught:
        client.fetch(1, transport=_transport(status_code=200, content=body))

    assert "Forbidden" in str(caught.value)


def test_a_server_error_is_tried_twice_and_then_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lorenzo_beyond.client.time.sleep", lambda _: None)
    calls: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(Unreachable):
        client.fetch(1, transport=httpx.MockTransport(answer))

    assert len(calls) == 2


def test_a_dropped_connection_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lorenzo_beyond.client.time.sleep", lambda _: None)
    calls: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("down")
        return httpx.Response(200, content=FIXTURE.read_bytes())

    assert client.fetch(1, transport=httpx.MockTransport(answer)).name == "Mira"


def test_another_client_error_is_not_retried() -> None:
    with pytest.raises(Unreachable) as caught:
        client.fetch(1, transport=_transport(status_code=429))

    assert "429" in str(caught.value)


def test_a_document_in_a_new_shape_says_where() -> None:
    document = json.loads(FIXTURE.read_text())
    document["data"]["inventory"][0]["definition"]["name"] = None

    with pytest.raises(ChangedShape) as caught:
        client.read_document(json.dumps(document))

    assert caught.value.code == 3 and "inventory.0.definition.name" in str(caught.value)
    assert "issues" in (caught.value.hint or "")


def test_not_json_at_all_is_a_changed_shape_too() -> None:
    with pytest.raises(ChangedShape):
        client.read_document("<html>maintenance</html>")


def test_a_proxy_that_refuses_is_named_as_such(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lorenzo_beyond.client.time.sleep", lambda _: None)

    def answer(request: httpx.Request) -> httpx.Response:
        raise httpx.ProxyError("403")

    with pytest.raises(Unreachable) as caught:
        client.fetch(1, transport=httpx.MockTransport(answer))

    assert "proxy or firewall" in (caught.value.hint or "")
