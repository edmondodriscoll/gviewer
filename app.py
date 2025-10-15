import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

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

# Optional: manual refresh
cols_hdr = st.columns([1, 1, 6])
with cols_hdr[0]:
    if st.button("Refresh data 🔄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with cols_hdr[1]:
    st.write("")  # spacer

df = load_df()

st.subheader("Sheet data")
if df.empty:
    st.info("No rows yet — add one below.")
else:
    st.dataframe(df, use_container_width=True, height=400)

# --- Plotly line plot: Time start vs Bottle/NG consumption ---
st.divider()
st.subheader("Intake over time")

if df.empty:
    st.info("Nothing to plot yet.")
else:
    time_col_name = "Time start"
    if time_col_name not in df.columns:
        st.warning(f'Cannot plot: "{time_col_name}" column not found.')
    else:
        s = df[time_col_name].astype(str).str.strip()

        # 1) Parse "Time start" to datetime
        ts = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)

        # Handle HHMM/HMM like "0900" or "900": assume today's date for the x-axis
        is_hhmm = s.str.fullmatch(r"\d{3,4}")
        if is_hhmm.any():
            today = pd.Timestamp.today().normalize()

            def parse_hhmm(x: str):
                x = x.zfill(4)  # "900" -> "0900"
                try:
                    t = datetime.strptime(x, "%H%M").time()
                    return pd.Timestamp.combine(today, t)
                except Exception:
                    return pd.NaT

            filled = s.where(is_hhmm, None).dropna().map(parse_hhmm)
            ts = ts.fillna(filled)

        plot_df = df.copy()
        plot_df["__time__"] = ts
        plot_df = plot_df.dropna(subset=["__time__"])

        if plot_df.empty:
            st.warning("No valid times to plot after parsing. Check your 'Time start' values.")
        else:
            # 2) Auto-detect likely intake columns (bottle / NG), keep numeric ones, let user adjust
            candidates = []
            for c in plot_df.columns:
                if c in ("__time__", time_col_name):
                    continue
                # auto-pick if column name mentions 'bottle' or 'ng'
                if pd.Series([c]).str.contains(r"\b(bottle|ng)\b", case=False, regex=True).any():
                    candidates.append(c)

            numeric_cols = [c for c in plot_df.columns if pd.api.types.is_numeric_dtype(plot_df[c])]
            default_cols = [c for c in candidates if c in numeric_cols]

            value_cols = st.multiselect(
                "Intake series to plot",
                options=numeric_cols,
                default=default_cols or (numeric_cols[:2] if len(numeric_cols) >= 1 else []),
                help="Select the numeric columns representing intake amounts (e.g., 'Bottle (ml)', 'NG (ml)').",
            )

            if not value_cols:
                st.info("Pick one or more numeric intake columns to plot.")
            else:
                long_df = (
                    plot_df.sort_values("__time__")
                    .melt(id_vars="__time__", value_vars=value_cols,
                          var_name="Series", value_name="Value")
                    .dropna(subset=["Value"])
                )

                fig = px.line(
                    long_df,
                    x="__time__",
                    y="Value",
                    color="Series",
                    markers=True,
                    labels={"__time__": "Time start", "Value": "Consumption"},
                )
                fig.update_layout(
                    height=360,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend_title_text="",
                    hovermode="x unified",
                )
                fig.update_traces(
                    mode="lines+markers",
                    hovertemplate="Time=%{x}<br>%{legendgroup}: %{y}<extra></extra>"
                )

                st.plotly_chart(fig, use_container_width=True)

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
                # If "Time start" and it's empty DataFrame, accept free text (e.g., 0900 or full datetime)
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
