# catalog_dashboard/connectors/baserow_connector.py
import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaserowConnector:
    def __init__(self, api_token, base_url):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Authorization": f"Token {api_token}"}
        if not api_token:
            logger.error("Baserow API token is not provided.")
            raise ValueError("Baserow API token is required.")

    def _get_all_rows(self, table_id):
        all_rows = []
        page = 1
        size = 200  # Max size allowed by Baserow
        while True:
            url = f"{self.base_url}/api/database/rows/table/{table_id}/?user_field_names=true&page={page}&size={size}"
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                all_rows.extend(results)
                if data.get("next") is None or not results:
                    break
                page += 1
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching data from Baserow table {table_id}, page {page}: {e}")
                raise
        return all_rows

    def get_table_as_dataframe(self, table_id):
        logger.info(f"Fetching data for Baserow table ID: {table_id}")
        try:
            rows = self._get_all_rows(table_id)
            if not rows:
                logger.warning(f"No data found in Baserow table {table_id}.")
                return pd.DataFrame()

            df = pd.DataFrame(rows)

            # Clean up Baserow's object format for 'select' or 'link' fields
            for col in df.columns:
                if df[col].apply(lambda x: isinstance(x, dict) and 'value' in x).any():
                    df[col] = df[col].apply(lambda x: x['value'] if isinstance(x, dict) and 'value' in x else x)
                elif df[col].apply(lambda x: isinstance(x, list) and x and isinstance(x[0], dict) and 'value' in x[0]).any():
                    df[col] = df[col].apply(lambda x: [item['value'] for item in x if isinstance(item, dict) and 'value' in item] if isinstance(x, list) else x)

            logger.info(f"Successfully fetched and processed {len(df)} rows from table {table_id}.")
            return df
        except Exception as e:
            logger.error(f"Failed to get data for table {table_id}: {e}")
            return pd.DataFrame()