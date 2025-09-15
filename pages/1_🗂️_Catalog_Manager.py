# catalog_dashboard/pages/1_🗂️_Catalog_Manager.py
import streamlit as st
import pandas as pd
from utils.data_loader import load_data
from utils.config_loader import APP_CONFIG
from connectors.baserow_connector import BaserowConnector

st.set_page_config(
    page_title="Catalog Manager",
    page_icon="🗂️",
    layout="wide"
)

# --- HELPER FUNCTION TO INITIALIZE/REFRESH STATE ---
def initialize_state(force_refresh=False):
    if 'editor_df' not in st.session_state or force_refresh:
        if force_refresh:
            st.cache_data.clear()
        
        df, _ = load_data()
        if not df.empty:
            df['Status'] = df['Status'].fillna('Uncategorized')
            df['Status'] = df['Status'].apply(lambda x: 'Uncategorized' if str(x).strip() == '' else x)
            df.insert(0, "_selected", False)
            st.session_state.original_df = df.copy()
            st.session_state.editor_df = df.copy()
        else:
            st.session_state.original_df = pd.DataFrame()
            st.session_state.editor_df = pd.DataFrame()
        st.session_state.pop('confirming_delete', None)

# --- INITIALIZE STATE ---
initialize_state()

# --- HEADER ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🗂️ Unified Catalog Manager")
    st.markdown("View, search, and edit all catalog data in one place.")
with col2:
    if st.button("🔄 Discard Changes & Refresh Data"):
        initialize_state(force_refresh=True)
        st.rerun()

# --- KPI DASHBOARD ---
st.markdown("---")
st.header("📈 Catalog at a Glance")
df_for_kpis = st.session_state.editor_df
if not df_for_kpis.empty:
    total_mskus = df_for_kpis['Msku'].nunique()
    total_skus = len(df_for_kpis)
    active_listings = df_for_kpis[df_for_kpis['Status'].str.lower() == 'active'].shape[0]
    panels_connected = df_for_kpis['Panel'].nunique()
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Master SKUs", f"{total_mskus:,}")
    kpi2.metric("Total Listings", f"{total_skus:,}")
    kpi3.metric("Active Listings", f"{active_listings:,}")
    kpi4.metric("Platforms Connected", panels_connected)

st.markdown("---")

# --- TABS FOR VIEWING & EDITING ---
tab1, tab2 = st.tabs(["📊 Visual Insights & Search", "✍️ Interactive Editor"])

with tab1:
    st.header("Visual Insights")
    if not df_for_kpis.empty:
        viz1, viz2 = st.columns(2)
        with viz1:
            st.subheader("Listings per Platform")
            st.bar_chart(df_for_kpis['Panel'].value_counts())
        with viz2:
            st.subheader("Listing Status Overview")
            st.bar_chart(df_for_kpis['Status'].value_counts())
    
    st.header("🔍 Read-Only Data Explorer")
    search_term = st.text_input("Search by SKU, MSKU, or ASIN", placeholder="Enter a value to filter the table...", key="viewer_search")
    
    # --- FIX 3: Clean up columns for the read-only view ---
    display_cols_viewer = ['Sku', 'Msku', 'Asin', 'Panel', 'Status']
    df_viewer = df_for_kpis[[col for col in display_cols_viewer if col in df_for_kpis.columns]]

    if search_term and not df_viewer.empty:
        mask = df_viewer.apply(lambda row: any(search_term.lower() in str(cell).lower() for cell in row), axis=1)
        st.dataframe(df_viewer[mask], use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_viewer, use_container_width=True, hide_index=True)

with tab2:
    st.header("Interactive Data Editor")
    if st.session_state.editor_df.empty:
        st.warning("No data to edit.")
    else:
        sort_cols = st.multiselect("Sort table by:", options=[col for col in st.session_state.editor_df.columns if col not in ['_selected', 'id', 'order']], placeholder="Choose column(s) to sort by")
        
        display_df = st.session_state.editor_df.copy()
        if sort_cols:
            display_df = display_df.sort_values(by=sort_cols).reset_index(drop=True)

        column_config = {
            # --- FIX 2: Adjust column width ---
            "_selected": st.column_config.CheckboxColumn("Select", width="small", required=True),
            "id": None, "order": None,
            "Asin": st.column_config.TextColumn("ASIN", disabled=True),
            "Status": st.column_config.SelectboxColumn(options=["Active", "Deleted", "Uncategorized"], required=True),
            "Panel": st.column_config.SelectboxColumn(options=df_for_kpis['Panel'].unique().tolist(), required=True),
        }

        edited_df = st.data_editor(display_df, column_config=column_config, use_container_width=True, hide_index=True, key="catalog_editor")

        selected_rows = edited_df[edited_df['_selected']]
        if not selected_rows.empty:
            # ... [Bulk action logic remains the same] ...
            st.subheader(f"🚀 Bulk Actions for {len(selected_rows)} Selected Rows")
            baserow_config = APP_CONFIG.get('baserow', {})
            connector = BaserowConnector(api_token=baserow_config['api_token'], base_url=baserow_config['base_url'])
            table_id = baserow_config.get('all_skus_table_id')
            row_ids_to_modify = selected_rows['id'].tolist()

            col_status, col_panel = st.columns(2)
            with col_status:
                new_status = st.selectbox("Set status to:", options=["Active", "Deleted", "Uncategorized"], index=None, placeholder="Choose a status...")
                if st.button("Apply Status Change", disabled=(new_status is None), use_container_width=True):
                    updates = [{'id': row_id, 'Status': new_status} for row_id in row_ids_to_modify]
                    if connector.update_rows(table_id, updates):
                        st.success(f"Successfully updated status for {len(updates)} rows.")
                        initialize_state(force_refresh=True); st.rerun()
                    else: st.error("Failed to update status.")
            with col_panel:
                panel_options = st.session_state.editor_df['Panel'].unique().tolist()
                new_panel = st.selectbox("Set panel to:", options=panel_options, index=None, placeholder="Choose a panel...")
                if st.button("Apply Panel Change", disabled=(new_panel is None), use_container_width=True):
                    updates = [{'id': row_id, 'Panel': new_panel} for row_id in row_ids_to_modify]
                    if connector.update_rows(table_id, updates):
                        st.success(f"Successfully updated panel for {len(updates)} rows.")
                        initialize_state(force_refresh=True); st.rerun()
                    else: st.error("Failed to update panel.")
            
            st.error("Danger Zone: Deleting records is permanent.")
            if st.button("🗑️ Delete Selected Rows", type="primary"):
                st.session_state.confirming_delete = True
            if st.session_state.get('confirming_delete', False):
                st.warning(f"**Are you sure you want to permanently delete these {len(row_ids_to_modify)} records?**")
                col_confirm, col_cancel = st.columns(2)
                if col_confirm.button("✅ Yes, I'm sure, delete them", use_container_width=True):
                    if connector.delete_rows(table_id, row_ids_to_modify):
                        st.success(f"Successfully deleted {len(row_ids_to_modify)} rows.")
                        initialize_state(force_refresh=True); st.rerun()
                    else: st.error("Failed to delete rows.")
                if col_cancel.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirming_delete = False; st.rerun()

        elif not st.session_state.original_df.reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
            st.warning("You have unsaved changes from direct edits!")
            if st.button("💾 Save Direct Edits", type="primary"):
                with st.spinner("Finding differences and saving..."):
                    # --- THIS IS THE NEW, ROBUST LOGIC ---
                    
                    # 1. Prepare the DataFrames by setting 'id' as the index.
                    # This aligns the rows perfectly, regardless of display order.
                    original_indexed = st.session_state.original_df.set_index('id')
                    edited_indexed = edited_df.set_index('id')
                    
                    # 2. Use pandas.compare to find the exact differences.
                    # It returns a DataFrame showing only the changed cells.
                    try:
                        diff = original_indexed.compare(edited_indexed)
                    except Exception as e:
                        st.error(f"Error comparing dataframes: {e}. This can happen if rows were added/deleted.")
                        st.stop()

                    if diff.empty:
                        st.info("No changes to save.")
                        st.stop()

                    # 3. Construct the update payload from the diff.
                    updates_to_send = []
                    for row_id, changes in diff.iterrows():
                        # The payload must start with the row's ID
                        update_payload = {'id': int(row_id)}
                        
                        # Get the changed values. 'self' refers to the edited_df, 'other' to original_df.
                        # We only care about the new values from 'self'.
                        changed_columns = changes.dropna().xs('self', level=1)
                        update_payload.update(changed_columns.to_dict())
                        
                        updates_to_send.append(update_payload)

                    # --- END OF NEW LOGIC ---

                    baserow_config = APP_CONFIG.get('baserow', {})
                    # IMPORTANT: Ensure you are updating the correct table. 
                    # The viewer loads from multiple tables, but edits should likely go to one.
                    # Let's assume edits go to the 'all_skus_table_id' for now.
                    # ⚠️ To be researched further: Confirm which table should be the destination for edits.
                    table_id = baserow_config.get('all_skus_table_id') 
                    
                    if not table_id:
                        st.error("Configuration error: 'all_skus_table_id' not found.")
                        st.stop()

                    connector = BaserowConnector(api_token=baserow_config['api_token'], base_url=baserow_config['base_url'])
                    
                    if connector.update_rows(table_id, updates_to_send):
                        st.success(f"Successfully updated {len(updates_to_send)} records.")
                        initialize_state(force_refresh=True)
                        st.rerun()
                    else:
                        st.error("Failed to save changes.")