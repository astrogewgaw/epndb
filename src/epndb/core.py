"""
epndb: Pythonic interface to the EPN's Database of Pulsar Profiles.
"""

from pathlib import Path
from epndb.utils import getdb
from rich.progress import track
from rich.console import Console
from typing import List, Optional
from epndb._version import __version__
from sqlalchemy.orm import selectinload
from sqlmodel import select, create_engine
from sqlmodel import Field, Session, SQLModel, Relationship

BASEDIR = Path(__file__).parent.resolve()

DBNAME = "epn"
DATADIR = BASEDIR / "data"
DBPATH = DATADIR / f"{DBNAME}.db"
ENGINE = create_engine(f"sqlite:///{DBPATH}", echo=False)


console = Console()


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
