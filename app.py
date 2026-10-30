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

# Process Leave Forecast Data
df_leave = pd.DataFrame()
if raw_leave_data:
    month_row_mapping = {
        20: "July",
        35: "August",
        56: "September",
        75: "October",
        94: "November",
        113: "December",
    }
    
    current_month = "Unknown Month"
    processed_rows = []
    
    for idx, row in enumerate(raw_leave_data, start=1):
        if not row:
            continue
            
        if idx in month_row_mapping:
            current_month = month_row_mapping[idx]
            
        first_cell = str(row[0]).strip() if len(row) > 0 else ""
        
        if first_cell and first_cell.lower() not in ["name", "agent name", ""] and not any(m.lower() == first_cell.lower() for m in month_row_mapping.values()):
            raw_values = [str(x).strip() for x in row[1:]]
            
            if raw_values and raw_values[0] == "":
                raw_values = raw_values[1:]
                
            new_row = [first_cell, current_month] + raw_values
            processed_rows.append(new_row)
            
    if processed_rows:
        max_cols = max(len(r) for r in processed_rows)
        cols = ["Name", "Month"] + [f"Day_{i}" for i in range(1, max_cols - 1)]
        padded_leave_rows = [r + [''] * (len(cols) - len(r)) for r in processed_rows]
        df_leave = pd.DataFrame(padded_leave_rows)
        df_leave.columns = cols[:df_leave.shape[1]]

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
        if 'date' in str(col).lower() or 'timestamp' in str(col).lower() or 'petsa' in str(col).lower():
            date_col = col
            break
            
    if date_col:
        # Pilitin ang pag-convert gamit ang flexible string cleaning (halimbawa: "Fri, Oct 30" -> Oct 30)
        raw_dates = df[date_col].astype(str)
        
        # Subukang mag-parse gamit ang pandas
        parsed_dates = pd.to_datetime(raw_dates, errors='coerce')
        
        # Kung nag-fail dahil walang taon sa text na tulad ng "Fri, Oct 30", linisin ang day name at lagyan ng year 2026
        if parsed_dates.isna().any():
            clean_str = raw_dates.str.replace(r'^[A-Za-z]+,\s*', '', regex=True)
            fallback = pd.to_datetime(clean_str + " 2026", format='%b %d %Y', errors='coerce')
            parsed_dates = parsed_dates.fillna(fallback)
            
        mask = (parsed_dates.dt.date >= start_date) & (parsed_dates.dt.date <= end_date)
        
        # Kung walang nag-match sa date object filter, huwag i-drop ang buong resulta kung magkatugma sa exact text
        if not mask.any():
            return df
            
        return df[mask]
    return df

# --- DISPLAY RESULTS ---
if search_name:
    st.subheader(f"Results for: '{search_name}'")
    
    start_date, end_date = None, None
    if len(date_range) == 2:
        start_date, end_date = date_range[0], date_range[1]
        st.caption(f"Filtered Date Range: **{start_date}** to **{end_date}**")

    # 1. LOGIN / TIME IN & TIME OUT SEARCH
    st.write("### 🔑 Login / Attendance Status (`Login`)")
    if not df_login.empty:
        target_col_login = df_login.columns[0]
        for col in df_login.columns:
            if 'name' in str(col).lower() or 'agent' in str(col).lower() or 'employee' in str(col).lower():
                target_col_login = col
                break
        
        login_results = df_login[df_login[target_col_login].astype(str).str.contains(search_name, case=False, na=False)].copy()
        
        if start_date and end_date:
            login_results = filter_by_date_range(login_results, start_date, end_date)
            
        if not login_results.empty:
            st.dataframe(login_results, use_container_width=True)
        else:
            st.info("No login/attendance records found.")
    else:
        st.info("Unable to read 'Login' sheet or sheet is empty.")

    st.markdown("---")

    # 2. PRODUCTION DETAILS SEARCH
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

    # 3. LEAVE FORECAST SEARCH
    st.write("### 📅 Leave Forecast (`2026 leave forecast`)")
    if not df_leave.empty:
        leave_results = df_leave[df_leave["Name"].astype(str).str.contains(search_name, case=False, na=False)].copy()
        
        days_in_months = {
            "January": 31, "February": 28, "March": 31, "April": 30,
            "May": 31, "June": 30, "July": 31, "August": 31,
            "September": 30, "October": 31, "November": 30, "December": 31
        }

        processed_leave_results = []
        for idx, row in leave_results.iterrows():
            month_name = str(row.get("Month", "")).strip()
            max_days = days_in_months.get(month_name, 31)
            
            for d in range(max_days + 1, 32):
                day_col = f"Day_{d}"
                if day_col in row:
                    row[day_col] = ""
            processed_leave_results.append(row)

        if processed_leave_results:
            leave_results = pd.DataFrame(processed_leave_results)

        cols_to_keep = []
        for col in leave_results.columns:
            if str(col).startswith("Day_"):
                try:
                    day_num = int(str(col).split("_")[1])
                    if day_num <= 31:
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
