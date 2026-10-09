import json

from lorenzo_beyond.ledger import Ledger, Line, render_json, render_markdown

from .conformance import problems


def sample() -> Ledger:
    return Ledger(
        owner="Mira",
        equipped=[
            Line(
                "Quarterstaff",
                weight=4,
                value="2 sp",
                kind="weapon",
                description="*Weapon*\n\nA staff.\n\n- one\n- two",
            ),
            Line("Backpack", contents=[Line("Rations", quantity=7, note="good | dry")]),
        ],
        not_carried=[Line("Vault key")],
    )


def test_markdown_is_the_ledger_shape() -> None:
    assert render_markdown(sample()) == (
        "format: lorenzo-ledger/1\n"
        "owner: Mira\n"
        "\n"
        "## Equipped\n"
        "- Quarterstaff | weight: 4 | value: 2 sp | kind: weapon\n"
        "  > *Weapon*\n"
        "  >\n"
        "  > A staff.\n"
        "  >\n"
        "  > - one\n"
        "  > - two\n"
        "- Backpack\n"
        "  - 7 x Rations | note: good \\| dry\n"
        "\n"
        "## Not carried\n"
        "- Vault key\n"
    )


def test_what_it_writes_conforms() -> None:
    assert problems(render_markdown(sample())) == []


def test_json_is_the_same_model() -> None:
    document = json.loads(render_json(sample()))

    assert document["format"] == "lorenzo-ledger/1"
    staff = document["equipped"][0]
    assert staff["weight"] == 4 and staff["description"].startswith("*Weapon*")
    assert document["equipped"][1]["contents"][0] == {
        "name": "Rations",
        "quantity": 7,
        "note": "good | dry",
    }
    assert document["not_carried"] == [{"name": "Vault key"}]


def test_names_and_notes_are_one_line() -> None:
    text = render_markdown(Ledger("A\nB", equipped=[Line("two\nlines", note="a\n b")]))

    assert "owner: A B" in text and "- two lines | note: a b" in text


def test_identical_lines_are_the_same_but_containers_never() -> None:
    assert Line("Dagger", weight=1).same_as(Line("Dagger", weight=1))
    assert not Line("Dagger").same_as(Line("Dagger", note="x"))
    assert not Line("Bag", contents=[Line("a")]).same_as(Line("Bag", contents=[Line("a")]))
