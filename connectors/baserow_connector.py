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
        

    def create_rows(self, table_id, rows_data):
        """
        Creates one or more new rows in a Baserow table.
        :param table_id: The ID of the table.
        :param rows_data: A list of dictionaries, where each dictionary is a new row.
        :return: The JSON response from the API or None on failure.
        """
        url = f"{self.base_url}/api/database/rows/table/{table_id}/batch/?user_field_names=true"
        payload = {"items": rows_data}
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully created {len(rows_data)} row(s) in table {table_id}.")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create rows in table {table_id}: {e} - Response: {e.response.text}")
            return None

    def update_rows(self, table_id, rows_data):
        """
        Updates one or more existing rows in a Baserow table.
        :param table_id: The ID of the table.
        :param rows_data: A list of dictionaries. Each dict MUST include the 'id' of the row to update.
        :return: The JSON response from the API or None on failure.
        """
        url = f"{self.base_url}/api/database/rows/table/{table_id}/batch/?user_field_names=true"
        payload = {"items": rows_data}
        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully updated {len(rows_data)} row(s) in table {table_id}.")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update rows in table {table_id}: {e} - Response: {e.response.text}")
            return None

    def delete_rows(self, table_id, row_ids):
        """
        Deletes one or more rows from a Baserow table in batches of 200.
        :param table_id: The ID of the table.
        :param row_ids: A list of integer row IDs to delete.
        :return: True on success, False on failure.
        """
        if not row_ids:
            logger.info(f"Table {table_id}: No row IDs provided for deletion.")
            return True

        # Ensure all IDs are integers
        try:
            valid_row_ids = [int(rid) for rid in row_ids]
        except (ValueError, TypeError) as e:
            logger.error(f"Table {table_id}: Invalid non-integer row ID found in list: {e}")
            return False

        url = f"{self.base_url}/api/database/rows/table/{table_id}/batch-delete/"
        batch_size = 200  # Baserow's limit
        overall_success = True

        for i in range(0, len(valid_row_ids), batch_size):
            chunk_of_ids = valid_row_ids[i:i + batch_size]
            
            # --- THIS IS THE FIX ---
            # The payload key should be 'items', not 'row_ids' for this endpoint.
            payload = {"items": chunk_of_ids}
            
            logger.info(f"Table {table_id}: Deleting chunk {i//batch_size + 1}, containing {len(chunk_of_ids)} row IDs.")
            
            try:
                response = requests.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"Successfully deleted chunk of {len(chunk_of_ids)} row(s) from table {table_id}.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to delete chunk from table {table_id}: {e} - Response: {e.response.text}")
                overall_success = False
                break # Stop on the first failed chunk

        return overall_success