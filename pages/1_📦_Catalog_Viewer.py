# catalog_dashboard/pages/1_📦_Catalog_Viewer.py
import streamlit as st
import pandas as pd

# We can import from the utils folder because Streamlit adds the root directory to the path
from utils.data_loader import load_data

st.set_page_config(
    page_title="Catalog Viewer",
    page_icon="📦",
    layout="wide"
)

# --- HEADER AND REFRESH BUTTON ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📦 Catalog Viewer Dashboard")
    st.markdown("A central hub to analyze and review all marketplace listings.")
with col2:
    if st.button("🔄 Refresh Data"):
        # Clear the cache for all functions
        st.cache_data.clear()
        st.rerun()

# --- LOAD DATA ---
df, last_updated = load_data()

if df.empty:
    st.warning("Could not load data. Please check configurations or try refreshing.")
    st.stop()

if last_updated:
    st.caption(f"Data last updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")

# --- DATA CLEANING ---
# <-- MODIFICATION 1: Handle blank statuses -->
# Replace any NaN or empty string values in 'Status' with 'Uncategorized'
df['Status'] = df['Status'].fillna('Uncategorized')
df['Status'] = df['Status'].apply(lambda x: 'Uncategorized' if str(x).strip() == '' else x)


# --- KPI DASHBOARD ---
st.markdown("---")
st.header("📈 Catalog at a Glance")

required_cols = ['Msku', 'Sku', 'Panel', 'Status']
if not all(col in df.columns for col in required_cols):
    st.error(f"The loaded data is missing one or more required columns: {required_cols}")
    st.stop()

total_mskus = df['Msku'].nunique()
total_skus = len(df)
active_listings = df[df['Status'].str.lower() == 'active'].shape[0]
panels_connected = df['Panel'].nunique()

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Master SKUs (MSKUs)", f"{total_mskus:,}")
kpi2.metric("Total Marketplace Listings", f"{total_skus:,}")
kpi3.metric("Active Listings", f"{active_listings:,}")
kpi4.metric("Platforms Connected", panels_connected)

# --- VISUALIZATIONS ---
st.markdown("---")
st.header("📊 Visual Insights")

viz1, viz2 = st.columns(2)

with viz1:
    st.subheader("Listings per Platform")
    panel_counts = df['Panel'].value_counts()
    st.bar_chart(panel_counts)

with viz2:
    st.subheader("Listing Status Overview")
    status_counts = df['Status'].value_counts()
    st.bar_chart(status_counts)


# --- DATA EXPLORER ---
st.markdown("---")
st.header("🔍 Data Explorer")
st.markdown("Use the search and filters below to deep-dive into the catalog data.")

# <-- MODIFICATION 1: Update search to include ASIN -->
search_term = st.text_input("Search by SKU, MSKU, or ASIN", placeholder="Enter a SKU, MSKU, or ASIN...")

if search_term:
    # Search in 'Sku', 'Msku', and 'Asin' columns, handling potential missing values (na=False)
    mask = df['Sku'].str.contains(search_term, case=False, na=False) | \
           df['Msku'].str.contains(search_term, case=False, na=False) | \
           df['Asin'].str.contains(search_term, case=False, na=False)
    filtered_df = df[mask]
else:
    filtered_df = df

# <-- MODIFICATION 2: Add 'Asin' to the list of columns to display -->
display_columns = ['Sku', 'Msku', 'Asin', 'Panel', 'Status']
columns_to_show = [col for col in display_columns if col in filtered_df.columns]

st.dataframe(filtered_df[columns_to_show], use_container_width=True)
st.info(f"Showing {len(filtered_df)} of {len(df)} total listings.")
