import os
import re

import lxml.html
from lxml.html.clean import Cleaner
from cleantext import normalize_whitespace, clean
from dateparser import parse

os.environ["SCRAPERWIKI_DATABASE_NAME"] = "sqlite:///data.sqlite"

# must be imported after setting db name
import scraperwiki

DEBUG = False

# Not sure if cleaning is important, but it can't (?) hurt either.
# https://www.raa-sachsen.de/support/chronik/vorfaelle/wurzen-851
# but keep inline style: https://stackoverflow.com/a/20432945/4028896
cleaner = Cleaner(
    page_structure=False, safe_attrs=lxml.html.defs.safe_attrs | set(["style"])
)


def strip_lk(text):
    return (
        text.replace("LK ", "")
        .replace("Landkreis ", "")
        .replace("Landkreis: ", "")
        .strip()
    )


def split_date_county(t):
    t = normalize_whitespace(t, no_line_breaks=True)
    if "|" in t:
        date, county = t.split("|")
        county = strip_lk(county)
    else:
        date = t
        county = None
    date = date.replace("Vorfall vom", "")
    date = parse(date, languages=["de"])
    return date, county


def process_text_list(entry):
    # getting main text, consider special cases
    text_list = entry.xpath(
        ".//div[contains(@class, 'content-element summary')]//p//text()"
    )

    for x in [
        entry.xpath(".//div[contains(@class, 'content-element summary')]/text()"),
        entry.xpath(".//p//text()"),
        entry.xpath(".//div[contains(@class, 'content-model--text')]//text()"),
        # entry.xpath(".//div[contains(@class, 'content-element')]//text()"),
    ]:
        for t in x:
            if t not in text_list:
                text_list.append(t)

    text_list = [normalize_whitespace(t, no_line_breaks=True) for t in text_list]
    text_list = [t for t in text_list if len(t) > 0]

    # skip if really no text
    if len(text_list) == 0:
        return

    sources = None

    for t in text_list:
        if clean(t) == clean("Alle Beiträge sehen"):
            text_list.remove(t)

        if (
            t.startswith("Quelle:")
            or t.startswith("Quellen:")
            or t.startswith("Quelle ")
        ):
            if sources is not None:
                raise ValueError("found sources twice?")
            sources = (
                t.replace("Quelle:", "")
                .replace("Quellen:", "")
                .replace("Quelle ", "")
                .strip()
            )
            text_list.remove(t)

    if sources is None:
        # old format
        sources = entry.xpath(".//p[@style='text-align: right;']//text()")
        if len(sources) == 0:
            sources = None
        else:
            sources = sources[0]
            text_list = [t for t in text_list if t.strip() != sources.strip()]

    another_county = None
    for t in text_list:
        if t.startswith("Landkreis:"):
            another_county = strip_lk(t)
            text_list.remove(t)

    # not sure about this heuristic...
    title = None
    if len(text_list) > 1 and len(text_list[0]) * 2 < len(text_list[1]):
        title = text_list[0]
        text_list = text_list[1:]

    description = "\n\n".join(text_list)

    if DEBUG:
        print()
        print(sources)
        print(title)
        print(description)
        print()
    return sources, title, description, another_county


def fetch_details_page(url):
    """For some incidents we have to go to the details page.
    """
    if DEBUG:
        print("checking details page", url)
    html = scraperwiki.scrape(url)
    doc = lxml.html.fromstring(html)
    doc = cleaner.clean_html(doc)
    return process_entry(list(doc.xpath(".//article"))[0], details_page=True, uri=url)


def process_entry(entry, details_page=False, uri=None):
    if details_page:
        uri = uri
    else:
        uri = "https://www.raa-sachsen.de" + entry.xpath(".//h2/a/@href")[0]

    if DEBUG:
        print(uri)

    date_county = entry.xpath(".//span[@class='spotlight smaller']/text()")[0]
    date, county = split_date_county(date_county)

    results = process_text_list(entry)
    if results is None:
        # abort
        print("skipping, no data for: ", uri)
        return
    sources, title, description, another_county = results

    # headline contains links to details page, differs with h1 and h2
    if details_page:
        location = entry.xpath(".//h1//text()")[0]
    else:
        location = entry.xpath(".//h2//text()")[0]

    if another_county and not another_county in county:
        raise ValueError("something wrong with " + uri)

    if county is not None and county.startswith("Stadt "):
        county = county.replace("Stadt ", "").strip()
        if not county in location:
            location = county + ", " + location
            county = None
            print("the city was not in the location string", location)

    if not sources is None:
        sources = [t.strip() for t in sources.split(",")]
    else:
        # good heuristic to check if more content is available on the details page
        if details_page:
            print("stopping here, not source on details page for ", uri)
        else:
            # abort this entry and try details page

            details_description = fetch_details_page(uri)
            if DEBUG:
                print(len(details_description), len(description), details_description)
            if details_description is not None and len(details_description) >= len(
                description
            ):
                return
            else:
                print("discarding output of scraping details page directly.")

    scraperwiki.sqlite.save(
        unique_keys=["rg_id"],
        data={
            "description": description,
            "title": title,
            "date": date,
            "city": location,
            "county": county,
            "url": uri,
            "rg_id": uri,
            "chronicler_name": "RAA Sachsen",
        },
        table_name="incidents",
    )

    if not sources is None:
        for s in sources:
            scraperwiki.sqlite.save(
                unique_keys=["rg_id"],
                data={"name": s, "rg_id": uri},
                table_name="sources",
            )

    # force commit to prevent duplicates
    # https://github.com/sensiblecodeio/scraperwiki-python/issues/107
    scraperwiki.sqlite.commit_transactions()
    return description


def process_page(doc):
    for entry in doc.xpath("//article[@class='post-model']"):
        process_entry(entry)


base_url = "https://www.raa-sachsen.de/support/chronik?page=%s"

# get count of pages
html = scraperwiki.scrape(base_url % 1)
last_page = re.findall(r"Seite 1 von (\d\d\d)", str(html))[0]

urls = [base_url % i for i in range(1, int(last_page) + 1)]

for url in urls:
    if DEBUG:
        print(url)
    html = scraperwiki.scrape(url)
    doc = lxml.html.fromstring(html)
    doc = cleaner.clean_html(doc)
    # print(lxml.html.tostring(doc))
    process_page(doc)

# save meta data

scraperwiki.sqlite.save(
    unique_keys=["chronicler_name"],
    data={
        "iso3166_1": "DE",
        "iso3166_2": "DE-SN",
        "chronicler_name": "RAA Sachsen",
        "chronicler_description": "Die RAA Sachsen e.V. wurde Anfang der 1990er Jahre vor dem Hintergrund zunehmender rechtsextremistischer Gewalt im Freitstaat Sachsen - nicht zuletzt der ausländerfeindlichen Übergriffe im September 1991 in Hoyerswerda - auf Initiative der Freudenberg Stiftung und der RAA Neue Länder gegründet. Die Arbeit gegen Rechtsextremismus stellt seither einen zentralen Arbeitsschwerpunkt der RAA dar.",
        "chronicler_url": "https://www.raa-sachsen.de/",
        "chronicle_source": "https://www.raa-sachsen.de/support/chronik",
    },
    table_name="chronicle",
)

scraperwiki.sqlite.commit_transactions()
