import json
from pathlib import Path

import pytest

from lorenzo_beyond import convert
from lorenzo_beyond.errors import TooBig
from lorenzo_beyond.ledger import MAX_QUANTITY, Line, render_markdown
from lorenzo_beyond.models import Character

from .conformance import problems

FIXTURE = Path(__file__).parent / "fixtures" / "character.json"


def fixture_sheet() -> Character:
    return Character.model_validate(json.loads(FIXTURE.read_text())["data"])


def sheet(*items: dict[str, object], **extra: object) -> Character:
    """A character with these inventory rows (id, name, and anything else the row needs)."""
    rows = []
    for item in items:
        row = dict(item)
        extra_definition: dict[str, object] = row.pop("definition", {})  # type: ignore[assignment]
        definition = {"id": row["id"], "name": row.pop("name"), **extra_definition}
        rows.append({"quantity": 1, "containerEntityId": 1, **row, "definition": definition})
    return Character.model_validate({"id": 1, "name": "Mira", "inventory": rows, **extra})


def by_name(lines: list[Line]) -> dict[str, Line]:
    return {line.name: line for line in lines}


def test_the_real_shaped_sheet_converts_to_a_conforming_ledger() -> None:
    result = convert.convert(fixture_sheet())

    assert problems(render_markdown(result.ledger)) == []
    assert result.lines == 41 and result.descriptions == 36


def test_equipped_things_and_the_ones_on_the_character_are_equipped() -> None:
    result = convert.convert(fixture_sheet())
    equipped = by_name(result.ledger.equipped)

    assert {
        "Quarterstaff",
        "Pearl of Power",
        "Backpack",
        "Bag of Holding",
        "Clothes, Common",
    } <= set(equipped)
    assert "Coin purse" in equipped


def test_heavy_things_and_mounts_are_left_behind() -> None:
    result = convert.convert(fixture_sheet())

    assert [line.name for line in result.ledger.not_carried] == ["Barrel", "Barrel", "Riding Horse"]
    horse = result.ledger.not_carried[2]
    assert [c.name for c in horse.contents] == ["Saddle, Riding"]


def test_the_carried_set_can_be_chosen() -> None:
    character = fixture_sheet()
    roots, _ = convert.build_tree(character)
    backpack = next(e for e in roots if e.name == "Backpack")

    result = convert.convert(character, carried={backpack.item.id})

    assert "Clothes, Common" in [line.name for line in result.ledger.not_carried]
    assert "Backpack" in [line.name for line in result.ledger.equipped]


def test_separate_rows_of_the_same_thing_become_one_stack_inside_a_container() -> None:
    bag = by_name(convert.convert(fixture_sheet()).ledger.equipped)["Bag of Holding"]
    daggers = [line for line in bag.contents if line.name == "Dagger"]

    assert [(d.quantity) for d in daggers] == [3]


def test_a_bundle_is_weighed_per_piece_and_a_big_stack_is_split() -> None:
    bag = by_name(convert.convert(fixture_sheet()).ledger.equipped)["Bag of Holding"]
    bearings = by_name(bag.contents)["Ball Bearings (bag of 1,000)"]

    assert bearings.weight == pytest.approx(0.002)
    assert bearings.quantity == 1000

    big = convert.convert(
        sheet(
            {"id": 9, "name": "Pouch", "definition": {"isContainer": True}},
            {"id": 10, "name": "Arrow", "quantity": 2500, "containerEntityId": 9},
            {"id": 11, "name": "Chest", "definition": {"isContainer": True}},
        )
    )
    pouch = big.ledger.not_carried[0] if big.ledger.not_carried else big.ledger.equipped[0]
    assert [a.quantity for a in pouch.contents] == [MAX_QUANTITY, MAX_QUANTITY, 500]


def test_a_homebrew_item_keeps_its_text_note_and_weight() -> None:
    bag = by_name(
        convert.convert(fixture_sheet()).ledger.not_carried
        and convert.convert(fixture_sheet()).ledger.equipped
    )
    sack = by_name(bag["Bag of Holding"].contents)["Sack"]

    assert sack.quantity == 19 and sack.weight == 1.0
    assert sack.note == "actually .5 lbs"
    assert sack.description == "Sack with enogh space for bones of a humanoid."


def test_attunement_is_the_characters_state_and_goes_in_the_note() -> None:
    pearl = by_name(convert.convert(fixture_sheet()).ledger.equipped)["Pearl of Power"]

    assert pearl.note == "Attuned"
    assert pearl.description is not None
    assert pearl.description.startswith(
        "*Wondrous item, uncommon, requires attunement (spellcaster)*"
    )


def test_a_weapon_shows_its_damage_and_properties_above_its_text() -> None:
    staff = by_name(convert.convert(fixture_sheet()).ledger.equipped)["Quarterstaff"]

    assert staff.kind == "weapon" and staff.value == "2 sp" and staff.weight == 4
    assert staff.description is not None
    assert staff.description.split("\n\n")[:2] == [
        "*Weapon (Quarterstaff)*",
        "1d6 bludgeoning · Versatile · Topple",
    ]


def test_the_coin_purse_is_one_line_with_the_coins_in_its_note() -> None:
    purse = by_name(convert.convert(fixture_sheet()).ledger.equipped)["Coin purse"]

    assert purse.note == "371 gp, 90 sp, 13 cp" and purse.value == "380.13 gp"
    assert "Coin purse" not in by_name(
        convert.convert(fixture_sheet(), options=convert.Options(coins=False)).ledger.equipped
    )


def test_descriptions_can_be_left_out() -> None:
    result = convert.convert(fixture_sheet(), options=convert.Options(descriptions=False))

    assert result.descriptions == 0


def test_the_owner_defaults_to_the_character_and_can_be_named() -> None:
    assert convert.convert(fixture_sheet()).ledger.owner == "Mira"
    assert (
        convert.convert(fixture_sheet(), options=convert.Options(owner="Mira")).ledger.owner
        == "Mira"
    )


def test_a_loose_stack_goes_into_one_named_container_with_a_warning() -> None:
    result = convert.convert(sheet({"id": 5, "name": "Dart", "quantity": 45, "equipped": True}))

    loose = result.ledger.equipped[0]
    assert loose.name == convert.LOOSE and [(c.name, c.quantity) for c in loose.contents] == [
        ("Dart", 45)
    ]
    assert any("Dart" in w for w in result.warnings)
    assert problems(render_markdown(result.ledger)) == []


def test_two_top_level_rows_stay_two_lines() -> None:
    result = convert.convert(sheet({"id": 11, "name": "Torch"}, {"id": 12, "name": "Torch"}))

    assert [line.name for line in result.ledger.equipped] == ["Torch", "Torch"]


def test_a_container_that_holds_things_is_written_once_whatever_its_count() -> None:
    result = convert.convert(
        sheet(
            {"id": 5, "name": "Sack", "quantity": 2},
            {"id": 6, "name": "Apple", "containerEntityId": 5},
        )
    )

    sack = result.ledger.equipped[0]
    assert sack.quantity == 1 and [c.name for c in sack.contents] == ["Apple"]
    assert any("hold things" in w for w in result.warnings)


def test_an_item_whose_container_is_missing_goes_to_the_top_with_a_warning() -> None:
    result = convert.convert(sheet({"id": 5, "name": "Orphan", "containerEntityId": 999}))

    assert [line.name for line in result.ledger.equipped] == ["Orphan"]
    assert any("container is not on the sheet" in w for w in result.warnings)


def test_a_loop_of_containers_is_broken_and_said() -> None:
    result = convert.convert(
        sheet(
            {"id": 5, "name": "A", "containerEntityId": 6},
            {"id": 6, "name": "B", "containerEntityId": 5},
        )
    )

    assert any("loop" in w for w in result.warnings)
    assert result.lines == 2


def test_a_description_over_the_limit_is_cut_at_a_paragraph_and_said() -> None:
    long = "".join(f"<p>{'word ' * 200}</p>" for _ in range(40))
    result = convert.convert(sheet({"id": 5, "name": "Tome", "definition": {"description": long}}))

    description = result.ledger.equipped[0].description
    assert description is not None and len(description) <= 20_000 and description.endswith("…")
    assert any("Tome" in w and "cut" in w for w in result.warnings)


def test_too_many_lines_is_refused_with_a_way_out() -> None:
    items = [{"id": n, "name": f"Thing {n}"} for n in range(1, 1100)]

    with pytest.raises(TooBig) as caught:
        convert.convert(sheet(*items))

    assert "1024" in str(caught.value) and caught.value.hint


def test_containers_nested_too_deep_are_refused() -> None:
    items = [
        {"id": n, "name": f"Box {n}", "containerEntityId": n - 1 if n > 1 else 1}
        for n in range(1, 9)
    ]

    with pytest.raises(TooBig):
        convert.convert(sheet(*items))


@pytest.mark.parametrize(
    ("by", "text"),
    [
        ("", "requires attunement"),
        ("Spellcaster", "requires attunement (spellcaster)"),
        ("by a Wizard", "requires attunement by a wizard"),
        ("Requires attunement by a cleric", "requires attunement by a cleric"),
    ],
)
def test_attunement_is_said_in_the_sheets_words(by: str, text: str) -> None:
    assert convert._attunement(by) == text
