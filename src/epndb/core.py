"""
Core functionality for epndb.
"""

import requests
import numpy as np
import proplot as pplt

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
        the profile as a Numpy array for the specified Stokes' parameter(s). The
        default for the latter is Stokes' I. It is possible to get multiple
        Stokes' parameters at once; for example, stokes = "IQ" will return both
        Stokes' I and Q as separate Numpy arrays.
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
            text = page.text
            data = text.split("\n")
            return np.loadtxt(
                data,
                unpack=True,
                usecols=[i + 3 for i, _ in enumerate(stokes)],
            )
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
                "Stokes' Parameters": self.stokes,
                f"Refer to {self.citation}": "",
            },
        )

    def plot(
        self,
        style: str = "-",
        save: bool = False,
        color: str = "black",
        normalise: bool = True,
        smoothen: bool = False,
        path: Optional[str] = None,
    ):

        """
        Plot this profile.
        """

        pass


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

    def plot_profiles(
        self,
        save: bool = False,
        path: Optional[str] = None,
        styles: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        freqs: Optional[List[float]] = None,
    ):

        """
        Plot the profiles for this pulsar.
        """

        pass


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
