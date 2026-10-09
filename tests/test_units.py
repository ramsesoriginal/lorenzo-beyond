import pytest

from lorenzo_beyond import units


@pytest.mark.parametrize(
    ("gold", "text"),
    [
        (0.01, "1 cp"),
        (0.05, "5 cp"),
        (0.2, "2 sp"),
        (0.5, "5 sp"),
        (2.0, "2 gp"),
        (75, "75 gp"),
        (1.25, "125 cp"),
        (None, None),
        (0, None),
    ],
)
def test_a_price_is_the_largest_exact_coin(gold: float | None, text: str | None) -> None:
    assert units.price(gold) == text


def test_a_bundles_weight_is_shared_among_its_pieces() -> None:
    assert units.weight_per_piece(2.0, 1000) == 0.002
    assert units.weight_per_piece(1.0, 0) == 1.0  # a bundle of 0 means no bundle
    assert units.weight_per_piece(1.0, None) == 1.0
    assert units.weight_per_piece(0, 1) is None
    assert units.weight_per_piece(None, 1) is None


def test_weights_are_written_without_noise() -> None:
    assert units.weight_text(0.002) == "0.002"
    assert units.weight_text(4.0) == "4"
    assert units.weight_text(1 / 3) == "0.3333"


def test_a_purse_names_its_coins_and_its_worth_in_gold() -> None:
    note, worth = units.purse({"cp": 13, "sp": 90, "gp": 371, "ep": 0, "pp": 0})

    assert note == "371 gp, 90 sp, 13 cp"
    assert worth == "380.13 gp"
    assert units.purse({"cp": 0, "gp": 0}) == (None, None)
    assert units.purse({"pp": 2}) == ("2 pp", "20 gp")
