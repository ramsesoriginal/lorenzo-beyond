"""D&D Beyond's numbers, as the ledger writes them (pounds per piece, coins as text)."""

from __future__ import annotations

COINS = (("pp", 1000), ("gp", 100), ("ep", 50), ("sp", 10), ("cp", 1))


def copper(gold: float) -> int:
    """Gold pieces (as D&D Beyond prices things) in copper, which is exact."""
    return round(gold * 100)


def value_text(copper_pieces: int) -> str | None:
    """`0.05` gp is `5 cp`, `0.2` is `2 sp`, `2` is `2 gp`: the largest coin that is exact.

    Platinum and electrum are never used for a price: a sheet that says 100 gp means 100 gp.
    """
    if copper_pieces <= 0:
        return None
    for unit, size in (("gp", 100), ("sp", 10)):
        if copper_pieces % size == 0:
            return f"{copper_pieces // size} {unit}"
    return f"{copper_pieces} cp"


def gold_text(copper_pieces: int) -> str | None:
    """A sum of money in gold, to the copper piece (`380.13 gp`), for a purse's worth."""
    if copper_pieces <= 0:
        return None
    gold = f"{copper_pieces / 100:.2f}".rstrip("0").rstrip(".")
    return f"{gold} gp"


def price(gold: float | None) -> str | None:
    return None if gold is None else value_text(copper(gold))


def weight_per_piece(weight: float | None, bundle_size: int | None) -> float | None:
    """Pounds for one piece. D&D Beyond gives the weight of a bundle (2 lb per 1,000 bearings)."""
    if not weight or weight <= 0:
        return None
    return weight / (bundle_size if bundle_size and bundle_size > 0 else 1)


def weight_text(pounds: float) -> str:
    return f"{pounds:.4f}".rstrip("0").rstrip(".")


def purse(currencies: dict[str, int]) -> tuple[str | None, str | None]:
    """A coin purse's note (`371 gp, 90 sp`) and its worth in the ledger's `value` field."""
    held = [(unit, currencies.get(unit, 0)) for unit, _ in COINS]
    parts = [f"{amount} {unit}" for unit, amount in held if amount]
    total = sum(amount * dict(COINS)[unit] for unit, amount in held)
    return (", ".join(parts) or None), gold_text(total)
