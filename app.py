import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Sheets + Streamlit Demo", page_icon="🗂️", layout="centered")

st.title("🗂️ Google Sheets ↔️ Streamlit (starter app)")

# --- Auth & open worksheet ---
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# st.secrets expects:
# - st.secrets["gcp_service_account"]  (dict with your service account JSON)
# - st.secrets["sheet_id"]             (string)
# - st.secrets["worksheet_name"]       (string, defaults to "Sheet1" if missing)

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPE
)
client = gspread.authorize(creds)

sheet_id = st.secrets["sheet_id"]
worksheet_name = st.secrets.get("worksheet_name", "Sheet1")

ws = client.open_by_key(sheet_id).worksheet(worksheet_name)

# --- Load data ---
@st.cache_data(ttl=60)
def load_df():
    rows = ws.get_all_records()
    return pd.DataFrame(rows)

df = load_df()

st.subheader("Sheet data")
if df.empty:
    st.info("No rows yet — add one below.")
else:
    st.dataframe(df, use_container_width=True, height=400)

# --- Simple append form (optional) ---
st.divider()
st.subheader("Add a row")

with st.form("add_row"):
    # Dynamically build inputs from current columns (or example fields if empty)
    if df.empty:
        columns = ["Name", "Protein", "Carbs", "Fat", "Label"]
    else:
        columns = df.columns.tolist()

    inputs = {}
    cols = st.columns(2)
    for i, col in enumerate(columns):
        with cols[i % 2]:
            # Try to be numeric if current column looks numeric
            if not df.empty and pd.api.types.is_numeric_dtype(df[col]):
                val = st.number_input(col, value=0.0, step=1.0, format="%.2f")
            else:
                val = st.text_input(col, value="")
            inputs[col] = val

    submitted = st.form_submit_button("Append row ➕")
    if submitted:
        # Maintain column order when appending
        values = [inputs[c] for c in columns]
        ws.append_row(values)  # appends at the bottom
        st.success("Row added!")
        st.cache_data.clear()  # refresh the table
        st.rerun()
