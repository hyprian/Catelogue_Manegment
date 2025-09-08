# catalog_dashboard/pages/3_🤖_AI_Chatbot.py
import streamlit as st
import pandas as pd
import io
import re # Import the regular expression library
from contextlib import redirect_stdout

from utils.config_loader import APP_CONFIG
from connectors.baserow_connector import BaserowConnector
from services.ai_service import generate_pandas_code_with_gemini

st.set_page_config(page_title="AI Chatbot", page_icon="🤖", layout="wide")

st.title("🤖 AI Chatbot for Baserow Data")

# --- NEW HELPER FUNCTION TO SANITIZE NAMES ---
def sanitize_for_variable_name(name: str) -> str:
    """Converts a human-readable string into a valid Python variable name."""
    # Remove special characters
    s = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Remove leading/trailing underscores
    s = s.strip('_')
    # Ensure it doesn't start with a number
    if s and s[0].isdigit():
        s = '_' + s
    return s

@st.cache_data(show_spinner="Loading table: {table_name}...")
def load_single_table(table_name, table_id):
    """Loads and caches a single table from Baserow."""
    baserow_config = APP_CONFIG.get('baserow', {})
    connector = BaserowConnector(
        api_token=baserow_config.get('api_token'),
        base_url=baserow_config.get('base_url')
    )
    return connector.get_table_as_dataframe(table_id)

# --- CONFIGURATION AND TABLE SELECTION ---
if "error" in APP_CONFIG:
    st.error(f"Configuration Error: {APP_CONFIG['error']}")
    st.stop()

ALL_AVAILABLE_TABLES = APP_CONFIG.get('chatbot_tables', {})
if not ALL_AVAILABLE_TABLES:
    st.warning("No chatbot tables configured. Please set up the 'ChatbotTables' tab in your Google Sheet.")
    st.stop()

st.info("Select the data tables you want to load into the AI's context for this session.")

selected_tables = st.multiselect(
    "Available Data Tables:",
    options=list(ALL_AVAILABLE_TABLES.keys()),
    default=st.session_state.get('selected_tables', []),
    key="table_selector"
)

if selected_tables != st.session_state.get('selected_tables', []):
    st.session_state.selected_tables = selected_tables
    st.session_state.messages = []
    st.rerun()

# --- DYNAMIC DATA LOADING AND SCHEMA GENERATION ---
dataframes = {}
schema_parts = []
if st.session_state.get('selected_tables'):
    for table_name in st.session_state.selected_tables:
        table_id = ALL_AVAILABLE_TABLES[table_name]
        
        # --- THIS IS THE FIX ---
        # Use the sanitizer to create a valid Python variable name
        sanitized_name = sanitize_for_variable_name(table_name)
        df_name = f"df_{sanitized_name}"
        
        df = load_single_table(table_name=table_name, table_id=table_id)
        if not df.empty:
            dataframes[df_name] = df
            # We show the AI the clean, sanitized name
            schema_parts.append(f"- `{df_name}` (from table '{table_name}'): columns {df.columns.tolist()}")

schema = "\n".join(schema_parts)

with st.sidebar:
    st.header("Loaded Data Context")
    if schema:
        st.markdown(schema)
    else:
        st.markdown("No tables selected.")

# --- CHAT INTERFACE (remains the same) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a question about the selected tables..."):
    if not dataframes:
        st.warning("Please select at least one table before asking a question.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI is thinking..."):
                code_to_execute = generate_pandas_code_with_gemini(prompt, schema)
                
                if "def " in code_to_execute:
                    try:
                        func_name = code_to_execute.split('def ')[1].split('(')[0].strip()
                        df_names = ", ".join(dataframes.keys())
                        code_to_execute += f"\n{func_name}({df_names})"
                    except Exception: pass

                if code_to_execute.startswith("Error:"):
                    response = code_to_execute
                else:
                    output_buffer = io.StringIO()
                    try:
                        with redirect_stdout(output_buffer):
                            exec(code_to_execute, globals(), dataframes)
                        response = output_buffer.getvalue()
                        if not response:
                            response = "The code executed successfully but produced no output."
                    except Exception as e:
                        response = f"The AI generated code that resulted in an error:\n\n`{str(e)}`"
                
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})