import re
import math
import attrs
import unyt as u
import numpy as np

from bs4 import BeautifulSoup
from datetime import timedelta
from typing import List, Optional
from requests_cache import CachedSession

Array = np.ndarray
One = lambda _: _[0]
Quantity = u.unyt_quantity
URL = "http://www.epta.eu.org/epndb"

Session = CachedSession(
    "epndb",
    use_cache_dir=True,
    cache_control=True,
    match_headers=True,
    stale_if_error=True,
    allowable_methods=["GET"],
    allowable_codes=[200, 400],
    expire_after=timedelta(days=7),
)


@attrs.define
class Profile:

    """
    Represents a pulsar's profile in the EPN's Database of Pulsar Profiles.
    """

    ref: str
    stokes: str
    fileurl: str
    freq: Quantity


@attrs.define
class Pulsar:

    """
    Represents a pulsar in the EPN's Database of Pulsar Profiles.
    """

    name: str
    jname: str
    bname: str
    nprof: int
    profs: List[Profile]

    def profile(
        self,
        freq: float,
        stokes: str = "I",
    ) -> Optional[Array]:

        """
        Obtain this pulsar's profile from the EPN's Database of Pulsar Profiles.

        Returns the profile as a Numpy array for a particular frequency, freq,
        and Stokes' parameter, poln. The default for the latter is Stokes' I.
        One can obtain profiles for multiple Stokes' parameters; for example,
        poln = 'IQ' will return both Stokes' I and Q as separate Numpy arrays.
        """

        if freq < 0.0:
            raise ValueError("Frequency cannot be negative.")

        if len(stokes) > 4:
            raise ValueError("There are only 4 Stokes' parameters.")

        for prof in self.profs:
            if math.isclose(
                freq,
                prof.freq,
                rel_tol=1e-3,
            ):
                page = Session.get(prof.fileurl)
                if page.status_code == 404:
                    regex = re.escape(f"/{self.jname}/")
                    page = Session.get(re.sub(regex, f"/{self.bname}/", prof.fileurl))
                    if page.status_code == 404:
                        raise ValueError("No ASCII version for this profile.")
                return np.loadtxt(
                    page.text.split("\n"),
                    unpack=True,
                    usecols=[i + 3 for i, _ in enumerate(stokes)],
                )


@attrs.define
class EPNDB:

    """
    The EPN's Database of Pulsar Profiles.
    """

    pulsars: List[Pulsar]

    @classmethod
    def get(cls):

        """
        Scrap the database.
        """

        page = Session.get(f"{URL}/list.php")
        parsed = BeautifulSoup(page.content, "lxml")

        tags = One(parsed.find_all("ul"))
        tags = tags.find_all("li", recursive=False)

        def get_links(tag):
            links = []
            atags = tag("a")
            for atag in atags:
                link = atag["href"]
                link = f"{URL}/ascii/{link}"
                link = link.replace("#", "")
                link = link.replace(".ar", ".txt")
                link = link.replace(".epn", ".txt")
                links.append(link)
            return links

        pulsars = []
        for tag in tags:
            matched = re.search(
                r"""
                (?P<JNAME>[J][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)\s*
                (\((?P<BNAME>[B][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)\))?\s*
                \[(?P<NPROF>[0-9]+)\]\s*
                """,
                tag.text,
                re.VERBOSE,
            )
            if matched is not None:
                values = matched.groupdict()
                jname = values["JNAME"]
                nprof = values["NPROF"]
                bname = values.get("BNAME", "")
            else:
                continue
            pulsars.append(
                Pulsar(
                    name=jname,
                    jname=jname,
                    bname=bname,
                    nprof=int(nprof),
                    profs=[
                        Profile(
                            ref=ref,
                            stokes=stokes,
                            fileurl=link,
                            freq=Quantity.from_string(freq),  # type: ignore
                        )
                        for ((freq, stokes, ref), link,) in zip(
                            re.findall(
                                r"""
                                ([0-9]+[.][0-9]+\s*?MHz|GHz)[,]\s*
                                ([IQUV])\s*
                                \[([a-z]+[+]?[0-9]+)\]
                                """,
                                tag.text,
                                re.VERBOSE,
                            ),
                            get_links(tag),
                        )
                    ],
                )
            )
        return cls(pulsars=pulsars)
