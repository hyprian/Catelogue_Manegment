# catalog_dashboard/utils/data_loader.py
import streamlit as st
import pandas as pd
from datetime import datetime
from connectors.baserow_connector import BaserowConnector
from utils.config_loader import APP_CONFIG

@st.cache_data(ttl=3600) # Cache data for 1 hour
def load_data():
    """
    Fetches the main SKU data and Amazon ASIN data from Baserow,
    merges them, and returns a single DataFrame.
    """
    if "error" in APP_CONFIG:
        st.error(f"Configuration Error: {APP_CONFIG['error']}")
        return pd.DataFrame(), None

    baserow_config = APP_CONFIG.get('baserow', {})
    all_skus_table_id = baserow_config.get('all_skus_table_id')
    amazon_table_id = baserow_config.get('amazon_listings_table_id') # <-- NEW: Get new table ID

    if not all([baserow_config.get('api_token'), baserow_config.get('base_url'), all_skus_table_id, amazon_table_id]):
        st.error("Baserow configuration is incomplete. Ensure 'all_skus_table_id' and 'amazon_listings_table_id' are in your GSheet.")
        return pd.DataFrame(), None

    connector = BaserowConnector(
        api_token=baserow_config['api_token'],
        base_url=baserow_config['base_url']
    )

    # --- FETCH DATA FROM BOTH TABLES ---
    df_all_skus = connector.get_table_as_dataframe(all_skus_table_id)
    df_amazon = connector.get_table_as_dataframe(amazon_table_id)
    timestamp = datetime.now()

    if df_all_skus.empty:
        st.warning("Main SKU data table is empty.")
        return pd.DataFrame(), timestamp

    # --- MERGE LOGIC ---
    if not df_amazon.empty and 'Sku' in df_amazon.columns and 'Asin' in df_amazon.columns:
        # Prepare the Amazon data: select only relevant columns and drop duplicates to prevent row multiplication
        amazon_asin_data = df_amazon[['Sku', 'Asin']].drop_duplicates(subset=['Sku'])

        # Perform a LEFT merge to add ASIN to the main SKU list
        # 'how="left"' ensures all rows from df_all_skus are kept
        merged_df = pd.merge(df_all_skus, amazon_asin_data, on='Sku', how='left')
        
        return merged_df, timestamp
    else:
        # If amazon data is empty or malformed, add an empty 'Asin' column for consistency
        df_all_skus['Asin'] = None
        return df_all_skus, timestamp