# catalog_dashboard/utils/config_loader.py
import yaml
import os
import logging
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@st.cache_resource
def get_gspread_client():
    try:
        creds_dict = st.secrets["google_credentials"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        logging.info("Successfully connected to Google Sheets API.")
        return client
    except Exception as e:
        logging.error(f"Failed to connect to Google Sheets API: {e}")
        return None

def get_settings_from_gsheet(client, spreadsheet_id, worksheet_name):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        settings_dict = {row['Setting_Key']: row['Setting_Value'] for row in records if row.get('Setting_Key')}
        logging.info(f"Successfully fetched {len(settings_dict)} settings from Google Sheet.")
        return settings_dict
    except Exception as e:
        logging.error(f"Failed to fetch settings from GSheet: {e}")
        return {"error": str(e)}

@st.cache_data(show_spinner=False)
def load_app_config():
    """Loads config from YAML and merges dynamic settings from Google Sheets."""
    try:
        with open("settings.yaml", 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return {"error": "settings.yaml not found."}

    gsheet_settings = config.get("google_sheet_settings", {})
    spreadsheet_id = gsheet_settings.get("spreadsheet_id")
    worksheet_name = gsheet_settings.get("worksheet_name")

    if not all([spreadsheet_id, worksheet_name]):
        return {"error": "GSheet settings missing in settings.yaml"}

    gsheet_client = get_gspread_client()
    if gsheet_client is None:
        return {"error": "Failed to connect to Google Sheets."}

    dynamic_settings = get_settings_from_gsheet(gsheet_client, spreadsheet_id, worksheet_name)
    if "error" in dynamic_settings:
        return dynamic_settings

    # Merge dynamic settings into the main config
    config['baserow'].update(dynamic_settings)
    return config

APP_CONFIG = load_app_config()