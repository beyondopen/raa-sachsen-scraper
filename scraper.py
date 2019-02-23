import datetime
import re
import os

import lxml.html

os.environ["SCRAPERWIKI_DATABASE_NAME"] = "sqlite:///data.sqlite"

import scraperwiki


def process_page(doc):
    for entry in doc.xpath("//h1"):
        text_list = entry.xpath("./..//p/text()")

        if len(text_list) == 0:
            continue

        text = " ".join(text_list)
        try:
            date = entry.xpath(".//time[1]/@datetime")[0]
        except Exception:
            break

        location = entry.xpath("./a[1]/@title")[0]
        uri = "https://www.raa-sachsen.de/" + entry.xpath("./a[1]/@href")[0]
        headline_string = entry.xpath("./a[1]//text()")[-1]
        county = re.findall(r"\((.*)\)", headline_string)[0]

        whole_h1 = " ".join(entry.xpath(".//text()"))

        if "Stadt Leipzig" in whole_h1:
            location = "Leipzig"

        if "Stadt Dresden" in whole_h1:
            location = "Dresden"

        if "Stadt Chemnitz" in whole_h1:
            location = "Chemnitz"

        location = ", ".join([location, county, "Sachsen", "Germany"])

        sources = entry.xpath("./..//p[@style='text-align: right;']//text()")

        scraperwiki.sqlite.save(
            unique_keys=["uri"],
            data={
                "description": text,
                "startDate": date,
                "iso3166_2": "DE-SN",
                "uri": uri,
            },
            table_name="data",
        )

        scraperwiki.sqlite.save(
            unique_keys=["reportURI"],
            data={"subdivisions": location, "reportURI": uri},
            table_name="location",
        )

        for s in sources:
            scraperwiki.sqlite.save(
                unique_keys=["reportURI"],
                data={"name": s, "reportURI": uri},
                table_name="source",
            )


base_url = "https://www.raa-sachsen.de/chronik.html?page_n13=%s"

urls = [base_url % i for i in range(1, 1000)]

for url in urls:
    try:
        html = scraperwiki.scrape(url)
    except:
        # break on 404 because we reached the end
        break
    doc = lxml.html.fromstring(html)
    process_page(doc)
