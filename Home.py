# catalog_dashboard/Home.py
import streamlit as st

st.set_page_config(
    page_title="Catalog Management Home",
    page_icon="🏠",
    layout="wide"
)

st.title("Welcome to the Catalog Management Project 📈")

st.markdown("---")

st.header("Project Vision")
st.write("""
This project aims to create a centralized, intelligent catalog management system. 
The primary goal is to transform our product data from a static, fragmented state into a strategic, automated asset. 
By building a single source of truth for all marketplace listings and implementing an automated pricing engine, we will reduce manual workload, 
eliminate data inconsistencies, and maximize profitability.
""")

st.info("👈 **Select a dashboard from the sidebar** to begin analyzing the catalog data.")

st.header("Available Modules")
st.markdown("""
- **📦 Catalog Viewer:** An interactive dashboard to search, filter, and review all SKU and MSKU data from our central Baserow database.
- **(Upcoming) 💰 Dynamic Pricing Engine:** An automated system to adjust product prices based on real-time inventory levels.
- **(Upcoming) 📊 Performance Analytics:** Dashboards to track sales, reviews, and content changes over time.
""")