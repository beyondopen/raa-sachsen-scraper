import os
import re

import lxml.html
from cleantext import normalize_whitespace
from dateparser import parse

os.environ["SCRAPERWIKI_DATABASE_NAME"] = "sqlite:///data.sqlite"

# must be imported after setting db name
import scraperwiki

DEBUG = False


def split_date_county(t):
    t = normalize_whitespace(t, no_line_breaks=True)
    if "|" in t:
        date, county = t.split("|")
    else:
        date = t
        county = "Landkreis unbekannt"
    date = date.replace("Vorfall vom", "")
    date = parse(date, languages=["de"])
    return date, county.strip()


def process_page(doc):
    for entry in doc.xpath("//article[@class='post-model']"):
        date_county = entry.xpath(".//span[@class='spotlight smaller']/text()")[0]
        date, county = split_date_county(date_county)

        # headline contains links to details page
        location = entry.xpath(".//h2//text()")[0]
        uri = "https://www.raa-sachsen.de" + entry.xpath(".//h2/a/@href")[0]

        if DEBUG:
            print(uri)

        # getting main text, consider special cases
        text_list = entry.xpath(
            ".//div[contains(@class, 'content-element summary')]//p/text()"
        )
        if len(text_list) == 0:
            text_list = entry.xpath(".//p/text()")
        if len(text_list) == 0:
            text_list = entry.xpath(
                ".//div[contains(@class, 'content-element')]/text()"
            )

        text_list = [normalize_whitespace(t, no_line_breaks=True) for t in text_list]
        text_list = [t for t in text_list if len(t) > 0]

        # skip if really no text
        if len(text_list) == 0:
            print("no data for: ", uri)
            continue

        if text_list[-1].startswith("Quelle:"):
            sources = text_list[-1].replace("Quelle:", "")
            text_list = text_list[:-1]
        else:
            # old format
            sources = entry.xpath(".//p[@style='text-align: right;']//text()")
            if len(sources) == 0:
                sources = None
            else:
                sources = sources[0]
                text_list = text_list[:-1]

        if not sources is None:
            sources = [t.strip() for t in sources.split(",")]

        title = None
        if len(text_list) > 1 and len(text_list[0]) * 2 < len(text_list[1]):
            title = text_list[0]
            text_list = text_list[1:]

        description = "\n\n".join(text_list)

        location = ", ".join([location, county, "Sachsen", "Deutschland"])

        scraperwiki.sqlite.save(
            unique_keys=["identifier"],
            data={
                "description": description,
                "title": title,
                "date": date,
                "subdivisions": location,
                "iso3166_2": "DE-SN",
                "url": uri,
                "rg_id": uri,
                "aggregator": "RAA Sachsen",
            },
            table_name="incidents",
        )

        if not sources is None:
            for s in sources:
                scraperwiki.sqlite.save(
                    unique_keys=["identifier"],
                    data={"name": s, "identifier": uri},
                    table_name="sources",
                )


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
    process_page(doc)
