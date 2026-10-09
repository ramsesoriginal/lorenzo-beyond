"""Bring a D&D Beyond character's inventory into Lorenzo, as a LorenzoLedger file."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lorenzo-beyond")
except PackageNotFoundError:  # running from a checkout that was never installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
