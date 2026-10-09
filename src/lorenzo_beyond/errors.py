"""What can go wrong, said the way a person would want to hear it."""

from __future__ import annotations


class BeyondError(Exception):
    """Something the person can act on. `hint` says what to try; `code` is the exit status."""

    code = 1

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class BadReference(BeyondError):
    """The text is not a character link or id."""


class NotAvailable(BeyondError):
    """D&D Beyond has no such character, or will not show it without a login."""

    code = 2


class Unreachable(BeyondError):
    """The request never got an answer."""

    code = 2


class ChangedShape(BeyondError):
    """D&D Beyond answered, but not in the shape this version knows."""

    code = 3


class TooBig(BeyondError):
    """The ledger format has limits, and this inventory is past one."""
