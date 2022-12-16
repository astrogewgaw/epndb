"""
Utilities for epndb.
"""

import re
import bs4
import requests

from typing import List, Dict
from rich.progress import track
from rich.console import Console


console = Console()
URL = "http://www.epta.eu.org/epndb"


class EPNDBError(Exception):
    pass


def getdb() -> List[Dict]:

    """
    Extract all relevant information from the EPN's Database of Pulsar Profiles.

    This is a utility function that scraps the database from where it is hosted
    on the web, and then proceeds to extract the relevant information about each
    pulsar and its corresponding profiles. It does not download any profile from
    the database; that is done only when desired by the user, via the URLs for
    different data formats for each profile. It returns a list of dictionaries,
    wherein each dictionary corresponds to a pulsar.
    """

    one = lambda x: x[0]
    txt = lambda x: [
        f"{URL}/ascii/{i['href']}".replace("#", "")
        .replace(".ar", ".txt")
        .replace(".epn", ".txt")
        .strip()
        for i in x.find_all("a")
    ]

    with console.status("Requesting..."):
        page = requests.get(f"{URL}/list.php")
        code = page.status_code
        if code != 200:
            raise EPNDBError(f"Cannot connect to database. ERROR CODE: {code}.")

    soup = bs4.BeautifulSoup(page.content, "lxml")
    tags = one(soup.find_all("ul")).find_all("li", recursive=False)

    pulsars = []
    for tag in track(tags, description="Scraping..."):
        matched = re.search(
            re.compile(
                r"{JNAME}\s*(?:\({BNAME}\))?\s*\[{NPROF}\]".format(
                    JNAME=r"([J][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)",
                    BNAME=r"([B][0-9]{2,4}[+-][0-9]{2,4}[A-Z]?)",
                    NPROF=r"([0-9]+)",
                )
            ),
            tag.text,
        )
        if matched:
            jname, bname, nprof = matched.groups()
        else:
            continue

        pulsars.append(
            {
                "JNAME": jname,
                "BNAME": bname,
                "NPROF": nprof,
                "PROFS": [
                    {
                        "URL": url,
                        "STOKES": stokes,
                        "CITATION": citation,
                        "FREQ": float(one(freq.split())),
                    }
                    for (freq, stokes, citation), url in zip(
                        re.findall(
                            re.compile(
                                r"{FREQ}[,]\s*{STOKES}\s*\[{CITATION}\]".format(
                                    FREQ=r"([0-9]+[.][0-9]+\s*MHz)",
                                    STOKES=r"([IQUV]+)",
                                    CITATION=r"([a-z]+[+]?[0-9]+)",
                                )
                            ),
                            tag.text,
                        ),
                        txt(tag),
                    )
                ],
            }
        )
    return pulsars
