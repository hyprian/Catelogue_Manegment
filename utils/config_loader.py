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
    
def get_chatbot_tables_from_gsheet(client, spreadsheet_id, worksheet_name):
    """Fetches chatbot table configurations from a dedicated Google Sheet tab."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        # Creates a dictionary like {'all_skus': 707, 'amazon_listing': 708}
        tables_dict = {row['Table_Name']: row['Table_ID'] for row in records if row.get('Table_Name')}
        logging.info(f"Successfully fetched {len(tables_dict)} chatbot table configs from GSheet.")
        return tables_dict
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"Chatbot worksheet '{worksheet_name}' not found in the Google Sheet.")
        return {"error": f"Worksheet '{worksheet_name}' not found."}
    except Exception as e:
        logging.error(f"Failed to fetch chatbot tables from GSheet: {e}")
        return {"error": str(e)}
    
@st.cache_data(show_spinner=False)
def load_app_config():
    """Loads config from YAML and merges dynamic settings from Google Sheets."""
    try:
        with open("settings.yaml", 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return {"error": "settings.yaml not found."}
    
    baserow_api_token_env = os.getenv('BASEROW_API_TOKEN')
    if baserow_api_token_env:
        config['baserow']['api_token'] = baserow_api_token_env
        logging.info("Loaded Baserow API token from environment variable.")

    gsheet_settings = config.get("google_sheet_settings", {})
    spreadsheet_id = gsheet_settings.get("spreadsheet_id")
    
    if not spreadsheet_id:
        return {"error": "GSheet spreadsheet_id missing in settings.yaml"}

    gsheet_client = get_gspread_client()
    if gsheet_client is None:
        return {"error": "Failed to connect to Google Sheets."}

    # 1. Fetch main settings
    main_worksheet = gsheet_settings.get("worksheet_name")
    if main_worksheet:
        dynamic_settings = get_settings_from_gsheet(gsheet_client, spreadsheet_id, main_worksheet)
        if "error" in dynamic_settings: return dynamic_settings
        config['baserow'].update(dynamic_settings)

    # 2. Fetch chatbot table settings
    chatbot_worksheet = gsheet_settings.get("chatbot_worksheet_name")
    if chatbot_worksheet:
        chatbot_tables = get_chatbot_tables_from_gsheet(gsheet_client, spreadsheet_id, chatbot_worksheet)
        if "error" in chatbot_tables: return chatbot_tables
        # Store this as a separate dictionary in the config
        config['chatbot_tables'] = chatbot_tables
    
    return config

APP_CONFIG = load_app_config()
