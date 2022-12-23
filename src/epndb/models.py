"""
Models for epndb's database.
"""

import requests
import numpy as np

from enum import Enum
from epndb.rich import card
from epndb.plots import lines
from typing import List, Optional
from numpy import ndarray as Array
from sqlmodel import Field, SQLModel, Relationship


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
    cite: str
    freq: float
    stokes: str
    pulsar: Optional["Pulsar"] = Relationship(back_populates="profiles")
    pulsar_id: Optional[int] = Field(default=None, foreign_key="pulsar.id")

    def __str__(self) -> str:
        if self.pulsar is not None:
            return f"Profile for PSR {self.pulsar.name} at 𝜈 = {self.freq} MHz."
        else:
            return f"Profile at 𝜈 = {self.freq} MHz."

    def __repr__(self) -> str:
        return str(self)

    def data(self, stokes: str = "I") -> Array:

        """
        Obtain this profile from the EPN's Database of Pulsar Profiles. Returns
        the profile as a Numpy array for the specified Stokes parameter(s). The
        default for the latter is Stokes I. It is possible to get multiple
        Stokes parameters at once; for example, stokes = "IQ" will return both
        Stokes I and Q as a multi-dimensional Numpy array.
        """

        if self.pulsar is not None:
            link = self.url
            page = requests.get(link)
            code = page.status_code
            if code != 200:
                link = link.replace(f"/{self.pulsar.name}/", f"/{self.pulsar.alias}/")
            page = requests.get(link)
            code = page.status_code
            if code != 200:
                raise ValueError(f"Cannot connect to database. ERROR CODE: {code}.")

            skip = 3
            text = page.text
            raw = text.split("\n")
            data = np.loadtxt(
                raw,
                unpack=False,
                usecols=[Stokes[_].value + skip for _ in stokes],
            )
            return data
        else:
            raise ValueError("Something is wrong with the database.")

    def info(self):

        """
        Get this profile's information from the database.
        """

        card(
            title="Profile",
            attrs={
                "Frequency": f"{self.freq:.2f}",
                "Stokes Parameters": self.stokes,
            },
        )

    def plot(self, stokes: str = "I") -> None:

        """
        Plot this profile.
        """

        fig = lines(
            title=str(self),
            labels=[_ for _ in stokes],
            data=self.data(stokes=stokes),
        )

        fname = f"{self.pulsar.name}" if self.pulsar is not None else "profile.png"

        fig.show(
            config=dict(
                scrollZoom=True,
                displaylogo=False,
                displayModeBar=True,
                toImageButtonOptions=dict(
                    width=1000,
                    height=1000,
                    format="png",
                    filename=fname,
                ),
            )
        )


class Pulsar(SQLModel, table=True):

    """
    Represents a pulsar in the EPN's Database of Pulsar Profiles.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    alias: Optional[str]
    profiles: List[Profile] = Relationship(back_populates="pulsar")

    def __str__(self) -> str:
        return f"PSR {self.name}, with {self.nprof} profiles."

    def __repr__(self) -> str:
        return str(self)

    @property
    def nprof(self) -> int:

        """
        Number of profiles for this pulsar.
        """

        return len(self.profiles)

    def info(self) -> None:

        """
        Get this pulsar's information from the database.
        """

        card(
            title="Pulsar",
            attrs={
                "Name": self.name,
                "Alternate name": self.alias,
                "Number of profiles": f"{self.nprof}",
                "Profiles": "\n".join(
                    [f"{_.freq:.2f} MHz, {_.stokes} [{_.cite}]" for _ in self.profiles]
                ),
            },
        )
