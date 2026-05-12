# Prozorro Tender Scraper

An input file named `tenders.csv` in the root directory (one link per line) is the source

## Usage

1. install dependencies `pip install -r requirements.txt`
2. run the script `python main.py`

## Output

All results are automatically saved into the `results/` folder:

* tender_details.csv: A list of details on every tender - tender id, award id, (amount)winning price, currency,
  supplier(winner) name, supplier edrpou, contact name, contact email.
* unique_suppliers.csv: A cleaned list containing unique winning companies and their contact persons and emails.

## Note

If you run into a 503 or 429 Service Unavailable error that persists, the Prozorro portal might be under heavy load. The
script
is built to wait and try again. Just wait a bit and try again in 5-10 minutes.