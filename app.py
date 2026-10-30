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

# Process Leave Forecast Data with Specific Row Mapping
df_leave = pd.DataFrame()
if raw_leave_data:
    month_row_mapping = {
        20: "July",
        35: "August",
        56: "September",
        75: "October",
        94: "November",
        113: "December"
    }
    
    current_month = "Unknown Month"
    processed_rows = []
    max_cols = 0
    
    for idx, row in enumerate(raw_leave_data, start=1):
        if not row:
            continue
            
        if idx in month_row_mapping:
            current_month = month_row_mapping[idx]
            
        first_cell = str(row[0]).strip() if len(row) > 0 else ""
        if first_cell and first_cell.lower() not in ["name", "agent name", ""] and not any(m.lower() == first_cell.lower() for m in month_row_mapping.values()):
            new_row = [first_cell, current_month] + row[1:]
            max_cols = max(max_cols, len(new_row))
            processed_rows.append(new_row)
            
    if processed_rows:
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
        
        # Dictionary para sa eksaktong bilang ng araw kada buwan sa 2026
        days_in_months = {
            "January": 31, "February": 28, "March": 31, "April": 30,
            "May": 31, "June": 30, "July": 31, "August": 31,
            "September": 30, "October": 31, "November": 30, "December": 31
        }

        # Subukang i-filter ang Day columns batay sa 'Month' ng bawat row
        processed_leave_results = []
        for idx, row in leave_results.iterrows():
            month_name = str(row.get("Month", "")).strip()
            max_days = days_in_months.get(month_name, 31)
            
            # Gawing blank ang anumang Day column na lampas sa tunay na bilang ng araw ng buwan
            for d in range(max_days + 1, 32):
                day_col = f"Day_{d}"
                if day_col in row:
                    row[day_col] = ""
            processed_leave_results.append(row)

        if processed_leave_results:
            leave_results = pd.DataFrame(processed_leave_results)

        # Tanggalin ang Day columns kung puro blank ang laman sa buong nakitang results
        cols_to_keep = []
        for col in leave_results.columns:
            if str(col).startswith("Day_"):
                try:
                    day_num = int(str(col).split("_")[1])
                    if day_num <= 31:
                        # Panatilihin lang ang column kung hindi puro blank ang laman nito
                        if not leave_results[col].astype(str).str.strip().eq("").all():
                            cols_to_keep.append(col)
                except ValueError:
                    pass
            else:
                cols_to_keep.append(col)
                
        leave_results = leave_results[cols_to_keep]

        if not leave_results.empty:
            st.dataframe(leave_results, use_container_width=True)
        else:
            st.info("No records found in Leave Forecast.")
