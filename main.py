import time
import os
import polars as pl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LINKS_FILE = "tenders.csv"
RESULTS_DIR = "results"  # The folder where results will be stored
SUMMARY_URL = "https://prozorro.gov.ua/api/tenders"
API_URL = "https://public-api.prozorro.gov.ua/api/2.5/tenders"

COLUMN_MAPPING = {
    "ua_id": "Tender ID",
    "award_id": "Award ID",
    "amount": "Amount",
    "currency": "Currency",
    "supplier_name": "Supplier Name",
    "supplier_edrpou": "Supplier EDRPOU",
    "contact_name": "Contact Name",
    "contact_email": "Contact Email",
    "error": "Error Message"
}

def crop_link(url: str) -> str:
    return url.strip().rstrip('/').split('/')[-1]

def get_session():
    """Creates a requests session that automatically retries on 503/429 errors."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session


def fetch_tender_data(ua_id: str, session):
    # Prepare a default dictionary with all keys as None to keep CSV schema clean
    base_record = {k: None for k in COLUMN_MAPPING.keys()}
    base_record["ua_id"] = ua_id

    try:
        # Resolve UUID via Summary
        summary_resp = session.get(f"{SUMMARY_URL}/{ua_id}/summary", timeout=15)
        summary_resp.raise_for_status()
        internal_id = summary_resp.json()['id']

        # Fetch details via API
        api_resp = session.get(f"{API_URL}/{internal_id}", timeout=15)
        api_resp.raise_for_status()
        data = api_resp.json()['data']

        results = []
        for award in data.get('awards', []):
            if award['status'] == 'active':
                supplier = award['suppliers'][0]
                contact = supplier.get('contactPoint', {})

                record = base_record.copy()
                record.update({
                    "award_id": award.get('id'),
                    "amount": award['value']['amount'],
                    "currency": award['value']['currency'],
                    "supplier_name": supplier.get('name'),
                    "supplier_edrpou": supplier['identifier']['id'],
                    "contact_name": contact.get('name'),
                    "contact_email": contact.get('email')
                })
                results.append(record)

        return results if results else [base_record] # Returns row with UA-ID but empty fields

    except Exception as e:
        error_record = base_record.copy()
        error_record["error"] = str(e)
        return [error_record]

def save_to_csv(data: list, filename: str):
    if not data: return

    df = pl.DataFrame(data)

    # Rename columns to human-readable
    rename_map = {k: v for k, v in COLUMN_MAPPING.items() if k in df.columns}
    df = df.rename(rename_map)

    # Select columns in the order they appear in COLUMN_MAPPING
    final_column_order = [v for v in COLUMN_MAPPING.values() if v in df.columns]
    df = df.select(final_column_order)

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    df.write_csv(filename)
    print(f"Saved full data to: {filename}")


def save_unique_suppliers(data: list, filename: str):
    if not data: return
    df = pl.DataFrame(data)
    selected_keys = ["supplier_name", "supplier_edrpou", "contact_name", "contact_email"]
    available_keys = [k for k in selected_keys if k in df.columns]

    if "supplier_edrpou" in df.columns:
        unique_df = (
            df.filter(pl.col("supplier_edrpou").is_not_null())
            .select(available_keys)
            .unique(subset=["supplier_edrpou"])
            .rename({k: COLUMN_MAPPING[k] for k in available_keys})
        )

        final_column_order = [v for v in COLUMN_MAPPING.values() if v in unique_df.columns]
        unique_df = unique_df.select(final_column_order)

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        unique_df.write_csv(filename)
        print(f"Saved {len(unique_df)} unique suppliers to: {filename}")

def main():
    session = get_session()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    try:
        links = pl.read_csv(LINKS_FILE, has_header=False).to_series().to_list()
    except Exception as e:
        print(f"Error reading {LINKS_FILE}: {e}")
        return

    data = []
    for link in links:
        ua_id = crop_link(link)
        print(f"Processing {ua_id}...")
        data.extend(fetch_tender_data(ua_id, session))
        # avoid hitting 60 requests/min
        time.sleep(1.001)

    # Put the results into the results/ folder
    save_to_csv(data, os.path.join(RESULTS_DIR, "tender_details.csv"))
    save_unique_suppliers(data, os.path.join(RESULTS_DIR, "unique_suppliers.csv"))

if __name__ == "__main__":
    main()