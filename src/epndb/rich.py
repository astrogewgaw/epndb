"""
Rich text formatting for epndb.
"""


from typing import Dict
from rich.panel import Panel
from rich.table import Table
from epndb.consts import console


def card(attrs: Dict, title: str = "") -> None:

    """
    Display a dictionary's fields in a nicely formatted card.
    """

    grid = Table.grid(
        expand=True,
        padding=(0, 2, 0, 2),
    )

    grid.add_column(justify="left")
    grid.add_column(justify="right")

    for key, value in attrs.items():
        grid.add_row(f"[i]{key}[/i]", f"[b]{value}[/b]")

    console.print(
        Panel(
            grid,
            padding=2,
            expand=False,
            title=f"[b]{title}[/b]",
        )
    )
