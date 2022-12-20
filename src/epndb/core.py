"""
Core functionality for epndb.
"""

import requests
import numpy as np
import plotly.graph_objects as go

from enum import Enum
from pathlib import Path
from rich.progress import track
from rich.console import Console
from typing import List, Optional
from epndb.utils import getdb, display
from epndb._version import __version__
from sqlalchemy.orm import selectinload
from sqlmodel import select, create_engine
from sqlmodel import Field, Session, SQLModel, Relationship


Array = np.ndarray
console = Console()

BASEDIR = Path(__file__).parent.resolve()

DBNAME = "epn"
DATADIR = BASEDIR / "data"
DBPATH = DATADIR / f"{DBNAME}.db"
ENGINE = create_engine(f"sqlite:///{DBPATH}", echo=False)


def version() -> str:

    """
    Returns the version of epndb installed.
    """

    return str(__version__)


class Stokes(Enum):

    """
    Enumeration for Stokes parameters.
    """

    I = 0
    Q = 1
    U = 2
    V = 3

    def __repr__(self):
        return "<%s.%s>" % (self.__class__.__name__, self._name_)


class Profile(SQLModel, table=True):

    """
    Represents a pulsar's profile in the EPN's Database of Pulsar Profiles.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    url: str
    freq: float
    stokes: str
    citation: str
    pulsar: Optional["Pulsar"] = Relationship(back_populates="profiles")
    pulsar_id: Optional[int] = Field(default=None, foreign_key="pulsar.id")

    def __str__(self) -> str:
        if self.pulsar is not None:
            return f"Profile for PSR {self.pulsar.name} at 𝜈 = {self.freq} MHz."
        else:
            return f"Profile at 𝜈 = {self.freq} MHz."

    def __repr__(self) -> str:
        return str(self)

    def get(
        self,
        stokes: str = "I",
    ) -> Array:

        """
        Obtain this profile from the EPN's Database of Pulsar Profiles. Returns
        the profile as a Numpy array for the specified Stokes parameter(s). The
        default for the latter is Stokes I. It is possible to get multiple
        Stokes parameters at once; for example, stokes = "IQ" will return both
        Stokes I and Q as separate Numpy arrays.
        """

        if self.pulsar is not None:
            link = self.url
            page = requests.get(link)
            code = page.status_code
            if code != 200:
                link = link.replace(f"/{self.pulsar.jname}/", f"/{self.pulsar.bname}/")
            page = requests.get(link)
            code = page.status_code
            if code != 200:
                raise ValueError(f"Cannot connect to database. ERROR CODE: {code}.")

            skip = 3
            text = page.text
            raw = text.split("\n")
            data = np.loadtxt(
                raw,
                unpack=True,
                usecols=[Stokes[_].value + skip for _ in stokes],
            )
            return data
        else:
            raise ValueError("Something is wrong with the database.")

    def info(self):

        """
        Get this profile's information from the database.
        """

        display(
            title="Profile",
            attrs={
                "Frequency": f"{self.freq:.2f}",
                "Stokes Parameters": self.stokes,
                f"Refer to {self.citation}": "",
            },
        )

    def plot(
        self,
        stokes: str = "I",
        baseline: bool = True,
        normalise: bool = False,
    ) -> None:

        """
        Plot this profile.
        """

        fig = go.Figure()
        data = self.get(stokes=stokes)
        data = [data] if data.ndim == 1 else data
        data = np.asarray(data)
        for name, column in zip(stokes, data):
            x = np.arange(column.size)
            x -= column.argmax()
            column /= column.max() if normalise else 1.0
            column -= np.median(column) if baseline else 0.0
            fig.add_trace(go.Scatter(x=x, y=column, name=name))
        fig.update_traces(hovertemplate=None)

        fig.update_layout(
            font_size=20,
            hovermode="x",
            title=str(self),
            font_color="white",
            template="plotly_dark",
            font_family="Spectral",
            title_font_color="goldenrod",
            title_font_family="Spectral SC",
            hoverlabel=dict(
                font_size=12,
                bgcolor="black",
                font_color="white",
                font_family="Spectral",
            ),
            xaxis_title="Peak Offset",
            yaxis_title="".join(
                [
                    ("Normalised " if normalise else ""),
                    "Flux Density",
                ]
            ),
        )

        fig.show(
            config=dict(
                scrollZoom=True,
                displaylogo=False,
                displayModeBar=True,
                toImageButtonOptions=dict(
                    width=1000,
                    height=1000,
                    format="png",
                    filename=f"{self.pulsar.name}"
                    if self.pulsar is not None
                    else "profile.png",
                ),
            )
        )


class Pulsar(SQLModel, table=True):

    """
    Represents a pulsar in the EPN's Database of Pulsar Profiles.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    jname: str
    nprof: int
    bname: Optional[str] = None
    profiles: List[Profile] = Relationship(back_populates="pulsar")

    def __str__(self) -> str:
        return f"PSR {self.name}, with {self.nprof} profiles."

    def __repr__(self) -> str:
        return str(self)

    @classmethod
    def get(cls, name: str):

        """
        Get a pulsar from the database.
        """

        with Session(ENGINE) as session:
            return session.exec(
                select(cls)
                .where(cls.name == name)
                .options(selectinload(cls.profiles).selectinload(Profile.pulsar))
            ).one()

    def info(self):

        """
        Get this pulsar's information from the database.
        """

        display(
            title="Pulsar",
            attrs={
                "Name": self.name,
                "Alternate name": self.bname,
                "Number of profiles": f"{self.nprof}",
                "Profiles": "\n".join(
                    [
                        f"{_.freq:.2f} MHz, {_.stokes} [{_.citation}]"
                        for _ in self.profiles
                    ]
                ),
            },
        )


def init() -> None:

    """
    Initialise and create the database.
    """

    if not Path(DBPATH).exists():
        with console.status("Initialising..."):
            SQLModel.metadata.create_all(ENGINE)
        with Session(ENGINE) as session:
            data = getdb()
            for row in track(data, description="Storing..."):
                session.add(
                    Pulsar(
                        name=row["JNAME"],
                        jname=row["JNAME"],
                        bname=row["BNAME"],
                        nprof=row["NPROF"],
                        profiles=[
                            Profile(
                                url=item["URL"],
                                freq=item["FREQ"],
                                stokes=item["STOKES"],
                                citation=item["CITATION"],
                            )
                            for item in row["PROFS"]
                        ],
                    )
                )
            session.commit()
