import re
import math
import unyt as u
import numpy as np

from bs4 import Tag
from enum import Enum
from typing import List
from attrs import define
from bs4 import BeautifulSoup
from datetime import timedelta
from requests_cache import CachedSession

url = "http://www.epta.eu.org/epndb"

session = CachedSession(
    "epndb",
    use_cache_dir=True,
    cache_control=True,
    match_headers=True,
    stale_if_error=True,
    allowable_methods=["GET"],
    allowable_codes=[200, 400],
    expire_after=timedelta(days=7),
)


def get_links(tag: Tag):
    links = []
    atags = tag("a")
    for atag in atags:
        link = atag["href"]
        link = f"{url}/ascii/{link}"
        link = link.replace("#", "")
        link = link.replace(".ar", ".txt")
        link = link.replace(".epn", ".txt")
        links.append(link)
    return links


@define
class Profile:

    """
    Represents a pulsar's profile in the EPN's Database of Pulsar Profiles.
    """

    _freq: str
    _poln: str
    _refn: str
    _link: str

    @property
    def freq(self):
        return u.unyt_quantity.from_string(self._freq)

    @property
    def poln(self):
        return self._poln

    @property
    def refn(self):
        return self._refn

    @property
    def link(self):
        return self._link


@define
class Pulsar:

    """
    Represents a pulsar in the EPN's Database of Pulsar Profiles.
    """

    jname: str
    bname: str
    nprof: int
    profiles: List[Profile]

    def profile(
        self,
        freq: float,
        poln: str = "I",
    ):

        """
        Obtain this pulsar's profile from the EPN's Database of Pulsar Profiles.

        Returns the profile as a Numpy array for a particular frequency, freq,
        and Stokes' parameter, poln. The default for the latter is Stokes' I.
        One can obtain profiles for multiple Stokes' parameters; for example,
        poln = 'IQ' will return both Stokes' I and Q as separate Numpy arrays.
        """

        class POLN(Enum):
            I = 1
            Q = 2
            U = 3
            V = 4

        for profile in self.profiles:
            if math.isclose(
                profile.freq,  # type: ignore
                freq,
                rel_tol=1e-2,
            ):
                response = session.get(profile.link)
                if response.status_code == 404:

                    # HACK: This is ensures that we can still get a profile from
                    # the database, since some pulsars have their BNAME instead
                    # of their JNAME in the links to their ASCII files. This can
                    # be removed if corrections are made to the database itself.

                    response = session.get(
                        re.sub(
                            re.escape(f"/{self.jname}/"),
                            f"/{self.bname}/",
                            profile.link,
                        )
                    )

                    if response.status_code == 404:
                        raise ValueError("No ASCII version for profile.")

                cols = [POLN[_].value + 2 for _ in poln]
                return np.loadtxt(response.text.split("\n"), usecols=cols)


@define
class EPNDB:

    """
    The EPN's Database of Pulsar Profiles.
    """

    pulsars: List[Pulsar]

    @classmethod
    def get(cls):
        page = session.get(f"{url}/list.php")
        soup = BeautifulSoup(page.content, "lxml")

        rxI = re.compile(
            r"""
            (?P<JNAME>[J][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)\s*
            (\((?P<BNAME>[B][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)\))?\s*
            \[(?P<NPROF>[0-9]+)\]\s*
            """,
            re.VERBOSE,
        )

        rxII = re.compile(
            r"""
            (?P<FREQ>[0-9]+[.][0-9]+\s*?MHz|GHz)[,]\s*
            (?P<POLN>[IQUV])\s*
            \[(?P<REFN>[a-z]+[+]?[0-9]+)\]
            """,
            re.VERBOSE,
        )

        pulsars = []
        tags = soup("ul")[0]("li", recursive=False)
        for tag in tags:
            matches = re.search(rxI, tag.text)
            if matches is not None:
                values = matches.groupdict()
                jname = values["JNAME"]
                nprof = values["NPROF"]
                bname = values.get("BNAME", "")
            else:
                continue
            pulsars.append(
                Pulsar(
                    jname,
                    bname,
                    int(nprof),
                    [
                        Profile(
                            freq,
                            poln,
                            refn,
                            link,
                        )
                        for (
                            (freq, poln, refn),
                            link,
                        ) in zip(re.findall(rxII, tag.text), get_links(tag))
                    ],
                )
            )
        return cls(pulsars=pulsars)
