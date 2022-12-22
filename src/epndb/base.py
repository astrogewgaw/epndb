"""
The heart of the epndb package.
"""

from sqlmodel import select
from epndb.scrap import get_db
from epndb.consts import Paths
from rich.progress import track
from sqlmodel import SQLModel, Session
from sqlalchemy.orm import selectinload
from epndb.consts import engine, console
from epndb.models import Pulsar, Profile


class DB:

    """
    The EPN's Database of Pulsar Profiles.
    """

    @staticmethod
    def update(force: bool = True) -> None:

        """
        Update the database. If force is True, update it regardless of whether
        or not it's already on disk. Otherwise, update it only if it's not
        present on disk. Default behaviour is to always update.
        """

        exists = Paths.db.exists()

        def get():

            """
            Instantiate, scrap and store the database.
            """

            with console.status("Initialising..."):
                meta = SQLModel.metadata
                meta.create_all(engine)
            with Session(engine) as session:
                data = get_db()
                for row in track(data, description="Storing..."):
                    session.add(
                        Pulsar(
                            name=row["JNAME"],
                            alias=row["BNAME"],
                            profiles=[
                                Profile(
                                    url=item["URL"],
                                    freq=item["FREQ"],
                                    stokes=item["STOKES"],
                                    cite=item["CITATION"],
                                )
                                for item in row["PROFS"]
                            ],
                        )
                    )
                session.commit()

        if force:
            if exists:
                Paths.db.unlink()
            get()
        else:
            if exists:
                return
            get()

    @classmethod
    def search(cls, name: str):

        """
        Search for pulsars in the database.
        """

        with Session(engine) as session:
            return session.exec(
                select(Pulsar)
                .where(Pulsar.name == name)
                .options(selectinload(Pulsar.profiles).selectinload(Profile.pulsar))
            ).all()
