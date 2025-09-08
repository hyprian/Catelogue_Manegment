# catalog_dashboard/services/ai_service.py
import streamlit as st
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

def generate_pandas_code_with_gemini(question: str, schema: str) -> str:
    """
    Generates Python pandas code to answer a question based on a database schema.

    :param question: The user's natural language question.
    :param schema: A string describing the available pandas DataFrames and their columns.
    :return: A string containing the Python code, or an error message.
    """
    try:
        api_key = st.secrets.get("gemini", {}).get("api_key")
        if not api_key:
            return "Error: Gemini API key is not configured in secrets.toml"
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # This is the "mega-prompt" that gives the AI all the context it needs.
        prompt = f"""
        You are an expert Python data analyst. Your task is to answer the user's question by writing pandas code.
        The data has been pre-loaded into pandas DataFrames.

        Available DataFrames (Schema):
        {schema}
        df_Current_Inventory_Sellable: columns ['id', 'order', 'Product Name', 'msku', 'Opening Stock', 'Daily Averge', 'Buffer Stock', 'TLCQ', 'Cost', 'Cogs', 'Product Status', 'BLR7', 'BLR8', 'BOM5', 'BOM7', 'CCU1', 'CCX1', 'DEL4', 'DEL5', 'DEX3', 'PNQ2', 'PNQ3', 'Packing material', 'Field 1', 'Field 2', 'Field 3', 'Field 4', 'Field 5', 'Field 6', 'Field 7', 'Field 8', 'Field 9', 'Field 10', 'Field 11', 'Field 12']

        Column Descriptions:
        - The 'Panel' column in `df_all_skus` contains the name of the marketplace or platform.
        - 'Msku' is the master SKU, a unique identifier for a product across all platforms.
        - 'Sku' is the marketplace-specific SKU.
        - In `df_Current_Inventory_Sellable`, 'msku' is the master SKU.
        - 'TLCQ', 'BLR7', 'BLR8', etc., are warehouse codes representing different fulfillment centers. The values in these columns are the stock counts for the MSKU in that warehouse.
        - The total current inventory for an MSKU is the sum of all warehouse columns (TLCQ, BLR7, BLR8, BOM5, BOM7, CCU1, CCX1, DEL4, DEL5, DEX3, PNQ2, PNQ3).
        - 'Cost' represents the cost of goods for the MSKU.

        Instructions:
        1. Write Python code to answer the question using ONLY the provided DataFrames.
        2. Your code's final output MUST be a print() statement.
        3. Do NOT include any explanations, comments, or markdown formatting (like ```python).
        4. Just return the raw Python code. Do not define a function unless the query is complex. If you must define a function, you MUST also include a line at the end that calls the function.
        5. **IMPORTANT:** All columns in all DataFrames are loaded as text/string type. You MUST convert columns to numeric types (integer or float) before performing any mathematical calculations (e.g., sum, mean, >). Use `pd.to_numeric(df['column'], errors='coerce').fillna(0)` for safe conversion.

        User's Question: {question}
        """

        response = model.generate_content(prompt)
        
        # Clean up the response to ensure it's just code
        code = response.text.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.endswith("```"):
            code = code[:-3]
            
        logger.info(f"Gemini generated code: \n{code}")
        return code.strip()

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return f"Error: Could not generate code due to an API error: {e}"