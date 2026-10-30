import streamlit as st
import pandas as pd
import requests

# Streamlit Page Setup
st.set_page_config(page_title="Prod & Leave Search", layout="wide")
st.title("🔍 Production & Schedule Search Tool")

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
    raw_leave_data = fetch_sheet_raw("Schedule Monitoring")
    raw_login_data = fetch_sheet_raw("Login")

# Helper function to convert raw list data into DataFrame
def raw_to_dataframe(raw_data):
    if not raw_data:
        return pd.DataFrame()
    header_idx = 0
    for idx, row in enumerate(raw_data):
        if any(row):
            header_idx = idx
            break
    headers = raw_data[header_idx]
    rows = raw_data[header_idx + 1:]
    padded_rows = [row + [''] * (len(headers) - len(row)) for row in rows]
    return pd.DataFrame(padded_rows, columns=headers)

# Process Prod & Login Data
df_prod = raw_to_dataframe(raw_prod_data)
df_login = raw_to_dataframe(raw_login_data)

# Process Schedule Monitoring Data
df_leave = pd.DataFrame()
if raw_leave_data:
    header_idx = None
    for idx, row in enumerate(raw_leave_data):
        if row and any("Name" in str(cell) for cell in row):
            header_idx = idx
            break
            
    if header_idx is not None:
        headers = [str(cell).strip() for cell in raw_leave_data[header_idx]]
        data_rows = raw_leave_data[header_idx + 1:]
        
        valid_rows = []
        for row in data_rows:
            if row and len(row) > 0:
                name_cell = str(row[0]).strip()
                if name_cell and not any(term in name_cell.lower() for term in ["total", "duty", "leave"]):
                    valid_rows.append(row)
                    
        padded_rows = [r + [''] * (len(headers) - len(r)) for r in valid_rows]
        df_leave = pd.DataFrame(padded_rows, columns=headers)

# --- EXTRACT FIRST NAMES ONLY FOR DROPDOWN ---
def get_all_names(df_login, df_prod, df_leave):
    names = set()
    
    def extract_first_name(series):
        for val in series.dropna():
            name_str = str(val).strip()
            if name_str:
                first_name = name_str.split()[0].capitalize()
                names.add(first_name)

    if not df_login.empty:
        col = next((c for c in df_login.columns if any(k in str(c).lower() for k in ['name', 'agent', 'employee'])), df_login.columns[0])
        extract_first_name(df_login[col])
        
    if not df_prod.empty:
        col = next((c for c in df_prod.columns if any(k in str(c).lower() for k in ['name', 'agent'])), df_prod.columns[0])
        extract_first_name(df_prod[col])
        
    if not df_leave.empty:
        col = next((c for c in df_leave.columns if any(k in str(c).lower() for k in ['name', 'agent'])), df_leave.columns[0])
        extract_first_name(df_leave[col])

    clean_names = sorted([name for name in names if name])
    return ["ALL"] + clean_names

# Get options for dropdown
name_options = get_all_names(df_login, df_prod, df_leave)

# --- MAIN FILTERS ---
date_range = st.date_input(
    "📅 Select Date Range:",
    value=[],
    help="Select Start Date and End Date"
)

# Search Dropdown Selection
selected_name = st.selectbox(
    "🔍 Select Name:",
    options=name_options,
    index=0,
    help="Select a first name from the list or choose 'ALL' to view all records."
)

# Helper function to filter by Date Range
def filter_by_date_range(df, start_date, end_date):
    if df.empty:
        return df
    
    date_col = None
    for col in df.columns:
        if 'date' in str(col).lower() or 'timestamp' in str(col).lower() or 'petsa' in str(col).lower():
            date_col = col
            break
            
    if date_col:
        raw_series = df[date_col].astype(str).str.strip()
        cleaned_series = raw_series.str.replace(r'^[A-Za-z]+,\s*', '', regex=True)
        series_with_year = cleaned_series.apply(
            lambda x: x + " 2026" if not any(y in x for y in ["2024", "2025", "2026"]) else x
        )
        parsed_dates = pd.to_datetime(series_with_year, errors='coerce')
        mask = (parsed_dates.dt.date >= start_date) & (parsed_dates.dt.date <= end_date)
        return df[mask]
        
    return df

# Helper function to filter by Name
def filter_by_name(df, selected):
    if df.empty or selected == "ALL":
        return df
    
    target_col = df.columns[0]
    for col in df.columns:
        if any(k in str(col).lower() for k in ['name', 'agent', 'employee']):
            target_col = col
            break
            
    return df[df[target_col].astype(str).str.contains(selected, case=False, na=False)].copy()

# Helper function to render table with Frozen First Column
def render_sticky_table(df):
    html_table = df.to_html(index=False, classes='sticky-table')
    st.markdown("""
    <style>
    .table-container {
        overflow-x: auto;
        max-width: 100%;
        border: 1px solid #e6e6e6;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .sticky-table {
        border-collapse: collapse;
        width: 100%;
        font-family: sans-serif;
        font-size: 14px;
    }
    .sticky-table th, .sticky-table td {
        padding: 8px 12px;
        border: 1px solid #e6e6e6;
        white-space: nowrap;
        text-align: left;
    }
    .sticky-table th {
        background-color: #f0f2f6;
        color: #31333F;
    }
    /* Frozen First Column (Name) */
    .sticky-table td:first-child, .sticky-table th:first-child {
        position: sticky;
        left: 0;
        background-color: #ffffff;
        z-index: 1;
        border-right: 2px solid #d3d3d3;
        font-weight: 600;
    }
    .sticky-table th:first-child {
        background-color: #f0f2f6;
        z-index: 2;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="table-container">{html_table}</div>', unsafe_allow_html=True)

# --- DISPLAY RESULTS ---
if selected_name:
    st.subheader(f"Results for: '{selected_name}'")
    
    start_date, end_date = None, None
    if len(date_range) == 2:
        start_date, end_date = date_range[0], date_range[1]
        st.caption(f"Filtered Date Range: **{start_date}** to **{end_date}**")

    # 1. LOGIN / TIME IN & TIME OUT SEARCH (WITH FROZEN FIRST COLUMN)
    st.write("### 🔑 Login / Attendance Status (`Login`)")
    if not df_login.empty:
        login_results = filter_by_name(df_login, selected_name)
        
        if start_date and end_date:
            login_results = filter_by_date_range(login_results, start_date, end_date)
            
        if not login_results.empty:
            render_sticky_table(login_results)
        else:
            st.info("No login/attendance records found for the selected filter.")
    else:
        st.info("Unable to read 'Login' sheet or sheet is empty.")

    st.markdown("---")

    # 2. PRODUCTION DETAILS SEARCH (WITH FROZEN FIRST COLUMN)
    st.write("### 📊 Production Details (`prod tracker v2`)")
    if not df_prod.empty:
        prod_results = filter_by_name(df_prod, selected_name)
        
        if start_date and end_date:
            prod_results = filter_by_date_range(prod_results, start_date, end_date)
            
        if not prod_results.empty:
            render_sticky_table(prod_results)
        else:
            st.info("No records found in Production Tracker.")

    st.markdown("---")

    # 3. SCHEDULE / LEAVE MONITORING SEARCH (WITH FROZEN FIRST COLUMN)
    st.write("### 📅 Schedule Monitoring (`Schedule Monitoring`)")
    if not df_leave.empty:
        leave_results = filter_by_name(df_leave, selected_name)
        leave_results = leave_results.loc[:, (leave_results != '').any(axis=0)]

        if not leave_results.empty:
            render_sticky_table(leave_results)
        else:
            st.info("No records found in Schedule Monitoring.")
    else:
        st.info("Unable to read 'Schedule Monitoring' sheet or sheet is empty.")
