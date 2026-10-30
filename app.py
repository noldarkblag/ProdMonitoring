import streamlit as st
import pandas as pd
import urllib.parse

st.set_page_config(page_title="Prod & Leave Search", layout="wide")

st.title("🔍 Production & Leave Forecast Search Tool")

# Base Spreadsheet ID mula sa iyong link
SHEET_ID = "1n99mFwmsRmcw731vuXp3_mUKOx3O4xXkgZqwSjXu7CY"

# Helper function para kumuha ng data gamit ang Sheet Name
@st.cache_data(ttl=300)
def fetch_sheet_data(sheet_name):
    # I-encode ang sheet name para sa URL
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    try:
        df = pd.read_csv(url)
        # Tanggalin ang mga blank columns/rows kung mayroon
        df = df.dropna(how="all")
        return df
    except Exception as e:
        st.error(f"Error sa pag-load ng '{sheet_name}': {e}")
        return pd.DataFrame()

# Load Data mula sa magkaibang tab/sheet name
with st.spinner("Binabasa ang Google Sheet..."):
    df_prod = fetch_sheet_data("prod tracker v2")
    df_leave = fetch_sheet_data("2026 leave forecast")

# Search Field
search_name = st.text_input("I-type ang Pangalan (halimbawa: Arnold):", "")

if search_name:
    st.subheader(f"Results for: '{search_name}'")
    
    # 1. Production Details Search
    st.write("### 📊 Production Details (`prod tracker v2`)")
    if not df_prod.empty:
        # Hahanapin ang column na may kinalaman sa 'Name' o 'Agent'
        name_cols = [c for c in df_prod.columns if 'name' in str(c).lower() or 'agent' in str(c).lower()]
        target_col = name_cols[0] if name_cols else df_prod.columns[0]
        
        prod_results = df_prod[df_prod[target_col].astype(str).str.contains(search_name, case=False, na=False)]
        
        if not prod_results.empty:
            st.dataframe(prod_results, use_container_width=True)
        else:
            st.info("Walang nahanap na record sa Production Tracker.")
    else:
        st.warning("Hindi ma-access ang 'prod tracker v2'. Tiyaking naka-Public / Anyone with link view access ang sheet.")

    st.markdown("---")

    # 2. Leave Forecast Search
    st.write("### 📅 Leave Forecast (`2026 leave forecast`)")
    if not df_leave.empty:
        name_cols_leave = [c for c in df_leave.columns if 'name' in str(c).lower() or 'agent' in str(c).lower()]
        target_col_leave = name_cols_leave[0] if name_cols_leave else df_leave.columns[0]
        
        leave_results = df_leave[df_leave[target_col_leave].astype(str).str.contains(search_name, case=False, na=False)]
        
        if not leave_results.empty:
            st.dataframe(leave_results, use_container_width=True)
        else:
            st.info("Walang nahanap na record sa Leave Forecast.")
    else:
        st.warning("Hindi ma-access ang '2026 leave forecast'.")