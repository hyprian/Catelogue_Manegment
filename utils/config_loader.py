# catalog_dashboard/utils/config_loader.py
import yaml
import os
import logging
import gspread
from google.oauth2.service_account import Credentials

# --- NEW: Environment-aware setup ---
IS_STREAMLIT_APP = False
try:
    import streamlit as st
    IS_STREAMLIT_APP = True
    # Define the caching decorator for the Streamlit environment
    cache_data_decorator = st.cache_data(show_spinner=False)
    cache_resource_decorator = st.cache_resource
except ImportError:
    # If Streamlit is not installed, create a dummy decorator that does nothing.
    # This allows the functions to be called without error in the scraper script.
    def dummy_decorator(func):
        return func
    cache_data_decorator = dummy_decorator
    cache_resource_decorator = dummy_decorator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@cache_resource_decorator
def get_gspread_client():
    creds_dict = None
    if IS_STREAMLIT_APP:
        try:
            creds_dict = st.secrets["google_credentials"]
            logging.info("Successfully loaded Google credentials from st.secrets.")
        except Exception as e:
            logging.error(f"Failed to load secrets from Streamlit: {e}")
            return None
    else:
        # Fallback for standalone scripts (like our scraper)
        logging.info("st.secrets not available. Falling back to environment variables.")
        try:
            private_key = os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_PRIVATE_KEY", "").replace('\\n', '\n')
            if not private_key:
                logging.error("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_PRIVATE_KEY env var is missing or empty.")
                return None

            creds_dict = {
                "type": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_TYPE"),
                "project_id": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_PROJECT_ID"),
                "private_key_id": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_PRIVATE_KEY_ID"),
                "private_key": private_key,
                "client_email": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_CLIENT_EMAIL"),
                "client_id": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_CLIENT_ID"),
                "auth_uri": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_AUTH_URI"),
                "token_uri": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_TOKEN_URI"),
                "auth_provider_x509_cert_url": os.environ.get("STREAMLIT_SECRETS_GOOGLE_CREDENTIALS_AUTH_PROVIDER_X509_CERT_URL"),
            }
            logging.info("Successfully loaded Google credentials from environment variables.")
        except Exception as e:
            logging.error(f"Failed to construct credentials from environment variables: {e}")
            return None

    if not creds_dict:
        logging.error("Could not load Google credentials from any source.")
        return None

    try:
        creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        logging.info("Successfully connected to Google Sheets API.")
        return client
    except Exception as e:
        logging.error(f"Failed to connect to Google Sheets API with loaded credentials: {e}")
        return None

# The rest of your config loader functions...
def get_settings_from_gsheet(client, spreadsheet_id, worksheet_name):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        settings_dict = {row['Setting_Key']: row['Setting_Value'] for row in records if row.get('Setting_Key')}
        logging.info(f"Successfully fetched {len(settings_dict)} settings from GSheet '{worksheet_name}'.")
        return settings_dict
    except Exception as e:
        logging.error(f"Failed to fetch settings from GSheet '{worksheet_name}': {e}")
        return {"error": str(e)}

def get_chatbot_tables_from_gsheet(client, spreadsheet_id, worksheet_name):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        tables_dict = {row['Table_Name']: row['Table_ID'] for row in records if row.get('Table_Name')}
        logging.info(f"Successfully fetched {len(tables_dict)} chatbot table configs from GSheet.")
        return tables_dict
    except gspread.exceptions.WorksheetNotFound:
        logging.error(f"Chatbot worksheet '{worksheet_name}' not found in the Google Sheet.")
        return {"error": f"Worksheet '{worksheet_name}' not found."}
    except Exception as e:
        logging.error(f"Failed to fetch chatbot tables from GSheet: {e}")
        return {"error": str(e)}

@cache_data_decorator
def load_app_config():
    try:
        with open("settings.yaml", 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return {"error": "settings.yaml not found."}

    gsheet_settings = config.get("google_sheet_settings", {})
    spreadsheet_id = gsheet_settings.get("spreadsheet_id")
    
    if not spreadsheet_id: return {"error": "GSheet spreadsheet_id missing in settings.yaml"}

    gsheet_client = get_gspread_client()
    if gsheet_client is None: return {"error": "Failed to connect to Google Sheets."}

    main_worksheet = gsheet_settings.get("worksheet_name")
    if main_worksheet:
        dynamic_settings = get_settings_from_gsheet(gsheet_client, spreadsheet_id, main_worksheet)
        if "error" in dynamic_settings: return dynamic_settings
        config['baserow'].update(dynamic_settings)

    chatbot_worksheet = gsheet_settings.get("chatbot_worksheet_name")
    if chatbot_worksheet:
        chatbot_tables = get_chatbot_tables_from_gsheet(gsheet_client, spreadsheet_id, chatbot_worksheet)
        if "error" in chatbot_tables: return chatbot_tables
        config['chatbot_tables'] = chatbot_tables
    
    return config

APP_CONFIG = load_app_config()