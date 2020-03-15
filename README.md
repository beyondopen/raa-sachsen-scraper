# RAA Sachsen Scraper

Scraping right-wing incidents in Sachsen, Germany as monitored by the NGO [RAA Sachsen](https://www.raa-sachsen.de).

-   Website: https://www.raa-sachsen.de/support/chronik
-   Data: https://morph.io/dmedak/raa-sachsen-scraper

## Usage

For local development:

-   Install [Pipenv](https://github.com/pypa/pipenv)
-   `pipenv install`
-   `pipenv run python scraper.py`

For Morph:

-   `pipenv lock --requirements > requirements.txt`
-   commit the `requirements.txt`
-   modify `runtime.txt`

## Morph

This is a scraper that runs on [Morph](https://morph.io). To get started [see the documentation](https://morph.io/documentation)

## License

MIT.
