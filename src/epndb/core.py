"""
epndb: Pythonic interface to the EPN's Database of Pulsar Profiles.
"""

import requests
import numpy as np

from pathlib import Path
from epndb.utils import getdb
from rich.progress import track
from rich.console import Console
from typing import List, Optional
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

    @classmethod
    def get(cls, name: str):
        with Session(ENGINE) as session:
            statement = select(cls)
            statement = statement.where(cls.name == name)
            statement = statement.options(selectinload(cls.profiles))
            result = session.exec(statement)
            return result.one()

    def profile(
        self,
        freq: float,
        stokes: str = "I",
    ) -> Optional[Array]:

        """
        Obtain this pulsar's profile from the EPN's Database of Pulsar Profiles.
        Returns the profile as a Numpy array for a particular frequency, freq,
        and Stokes' parameter, stokes.

        NOTE:

            1. The default for the latter is Stokes' I. One can obtain profiles
            for multiple Stokes' parameters; for example, stokes = "IQ" will
            return both Stokes' I and Q as separate Numpy arrays.

            2. The value of the frequency does not have to be exact; as long as
            the value provided by the user is within 5 MHz of the actual value,
            this method will try to return the corresponding profile. This value
            is arbitrary.
        """

        if freq < 0.0:
            raise ValueError("Frequency cannot be negative.")

        if len(stokes) > 4:
            raise ValueError("There are only 4 Stokes' parameters.")

        for profile in self.profiles:

            if np.abs(freq - profile.freq) > 5:
                raise ValueError(f"No profile for {freq} ± 5 MHz.")

            link = profile.url
            page = requests.get(link)
            code = page.status_code
            if code != 200:
                link = link.replace(f"/{self.jname}/", f"/{self.bname}/")
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
