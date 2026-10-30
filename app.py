import streamlit as st
import pandas as pd
import requests

# Streamlit Page Setup
st.set_page_config(page_title="Prod & Leave Search", layout="wide")
st.title("🔍 Production & Leave Forecast Search Tool")

# Google Spreadsheet ID
SHEET_ID = "1n99mFwmsRmcw731vuXp3_mUKOx3O4xXkgZqwSjXu7CY"

# Retrieve API Key from Streamlit Secrets
API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

@st.cache_data(ttl=300)
def fetch_sheet_raw(sheet_name):
    """Fetch raw worksheet data using Google Sheets API v4."""
    if not API_KEY:
        st.error("Google API Key is missing! Please configure GOOGLE_API_KEY in Streamlit Secrets.")
        return []
        
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/'{sheet_name}'?key={API_KEY}"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json().get('values', [])
    else:
        st.error(f"Error loading '{sheet_name}': {response.status_code} - {response.json().get('error', {}).get('message', '')}")
        return []

# Fetch raw sheet values
with st.spinner("Fetching data from Google Sheets..."):
    raw_prod_data = fetch_sheet_raw("prod tracker v2")
    raw_leave_data = fetch_sheet_raw("2026 leave forecast")

# Process Prod Data
df_prod = pd.DataFrame()
if raw_prod_data:
    header_idx = 0
    for idx, row in enumerate(raw_prod_data):
        if any(row):
            header_idx = idx
            break
    headers = raw_prod_data[header_idx]
    rows = raw_prod_data[header_idx + 1:]
    padded_rows = [row + [''] * (len(headers) - len(row)) for row in rows]
    df_prod = pd.DataFrame(padded_rows, columns=headers)

# Process Leave Forecast Data with Month Mapping
df_leave = pd.DataFrame()
if raw_leave_data:
    months_list = ["January", "February", "March", "April", "May", "June", 
                   "July", "August", "September", "October", "November", "December"]
    
    current_month = "Unknown Month"
    processed_rows = []
    max_cols = 0
    
    # Iterate through all rows in Leave Forecast to attach the corresponding Month
    for row in raw_leave_data:
        if not row:
            continue
        
        # Check if the row indicates a Month header
        first_cell = str(row[0]).strip()
        matching_month = next((m for m in months_list if m.lower() == first_cell.lower()), None)
        
        if matching_month:
            current_month = matching_month
            continue
            
        # Add the identified month into the second column position
        new_row = [row[0], current_month] + row[1:]
        max_cols = max(max_cols, len(new_row))
        processed_rows.append(new_row)
        
    if processed_rows:
        # Build clean dynamic column names
        cols = ["Name", "Month"] + [f"Day_{i}" for i in range(1, max_cols - 1)]
        padded_leave_rows = [r + [''] * (max_cols - len(r)) for r in processed_rows]
        df_leave = pd.DataFrame(padded_leave_rows, columns=cols)

# --- SIDEBAR FILTERS ---
st.sidebar.header("⚙️ Filter Options")

# Date Range Picker
st.sidebar.subheader("📅 Date Range Filter")
date_range = st.sidebar.date_input(
    "Select Date Range:",
    value=[],
    help="Select Start Date and End Date"
)

# Search Input
search_name = st.text_input("🔍 Search Name (e.g., Arnold):", "")

def filter_by_date_range(df, start_date, end_date):
    if df.empty:
        return df
    
    date_col = None
    for col in df.columns:
        if 'date' in str(col).lower():
            date_col = col
            break
            
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        mask = (df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)
        return df[mask]
    return df

# --- DISPLAY RESULTS ---
if search_name:
    st.subheader(f"Results for: '{search_name}'")
    
    start_date, end_date = None, None
    if len(date_range) == 2:
        start_date, end_date = date_range[0], date_range[1]
        st.caption(f"Filtered Date Range: **{start_date}** to **{end_date}**")

    # 1. PRODUCTION DETAILS SEARCH
    st.write("### 📊 Production Details (`prod tracker v2`)")
    if not df_prod.empty:
        target_col = df_prod.columns[0]
        for col in df_prod.columns:
            if 'name' in str(col).lower() or 'agent' in str(col).lower():
                target_col = col
                break
        
        prod_results = df_prod[df_prod[target_col].astype(str).str.contains(search_name, case=False, na=False)].copy()
        
        if start_date and end_date:
            prod_results = filter_by_date_range(prod_results, start_date, end_date)
            
        if not prod_results.empty:
            st.dataframe(prod_results, use_container_width=True)
        else:
            st.info("No records found in Production Tracker.")

    st.markdown("---")

    # 2. LEAVE FORECAST SEARCH
    st.write("### 📅 Leave Forecast (`2026 leave forecast`)")
    if not df_leave.empty:
        leave_results = df_leave[df_leave["Name"].astype(str).str.contains(search_name, case=False, na=False)].copy()
        
        # Remove completely empty columns
        leave_results = leave_results.dropna(how='all', axis=1)
        
        if not leave_results.empty:
            st.dataframe(leave_results, use_container_width=True)
        else:
            st.info("No records found in Leave Forecast.")
