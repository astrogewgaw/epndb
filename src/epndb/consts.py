"""
Package-wide constants for epndb.
"""

from pathlib import Path
from rich.console import Console
from sqlmodel import create_engine

# The URL for the database.
url = "http://www.epta.eu.org/epndb"


class Paths:

    """
    Relevant paths for epndb.
    """

    pkg = Path(__file__).parent.resolve()
    assets = pkg / "assets"
    db = assets / "epn.db"


# Relevant file extensions.
exts = [
    ".ar",
    ".txt",
    ".epn",
    ".fits",
    ".T8ch",
    ".psrfits",
]

# The Rich Console.
console = Console()

# The SQL Engine.
engine = create_engine(f"sqlite:///{Paths.db}", echo=False)
