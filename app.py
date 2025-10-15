import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime
import re

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

# --- Helpers ---
def extract_first_number(x):
    """Return first numeric value found in a string/cell, else NaN."""
    if pd.isna(x):
        return pd.NA
    s = str(x).strip()
    if s == "" or s.lower() in {"na", "n/a", "none", "-", "--"}:
        return pd.NA
    s = s.replace(",", "")  # remove thousands separators
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else pd.NA

def coerce_intake_columns(df: pd.DataFrame):
    """
    Find columns likely representing intake (Bottle/NG) and coerce them to numeric
    by extracting numbers from strings.
    Returns (df_copy, intake_candidates)
    """
    dfx = df.copy()
    # normalized columns
    dfx.columns = [c.strip() for c in dfx.columns]

    # any column name mentioning 'bottle' or 'ng'
    mask = pd.Series(dfx.columns).str.contains(r"\b(bottle|ng)\b", case=False, regex=True)
    candidates = pd.Series(dfx.columns)[mask].tolist()

    # also include exact common names if present (in case of extra spaces/case)
    for hard in ["Bottle (ml)", "NG (ml)"]:
        if hard in dfx.columns and hard not in candidates:
            candidates.append(hard)

    # Coerce candidate columns to numeric by extracting first number
    for c in candidates:
        dfx[c] = dfx[c].apply(extract_first_number).astype("Float64")

    return dfx, candidates

# --- Load data ---
@st.cache_data(ttl=60)
def load_df():
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    df.columns = [c.strip() for c in df.columns]
    return df

# Optional: manual refresh
cols_hdr = st.columns([1, 1, 6])
with cols_hdr[0]:
    if st.button("Refresh data 🔄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with cols_hdr[1]:
    st.write("")  # spacer

df_raw = load_df()

st.subheader("Sheet data")
if df_raw.empty:
    st.info("No rows yet — add one below.")
else:
    st.dataframe(df_raw, use_container_width=True, height=400)

# --- Plotly line plot: Time start vs Bottle/NG consumption ---
st.divider()
st.subheader("Intake over time")

if df_raw.empty:
    st.info("Nothing to plot yet.")
else:
    time_col_name = "Time start"
    if time_col_name not in df_raw.columns:
        st.warning(f'Cannot plot: "{time_col_name}" column not found.')
    else:
        df, auto_candidates = coerce_intake_columns(df_raw)

        # 1) Parse "Time start" to datetime
        s = df[time_col_name].astype(str).str.strip()
        ts = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)

        # Handle HHMM/HMM like "0900" or "900": anchor to today's date
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
            # 2) Build the set of columns that actually have numeric values after coercion
            def has_numeric_values(series: pd.Series) -> bool:
                return pd.to_numeric(series, errors="coerce").notna().sum() > 0

            numeric_like_cols = [c for c in plot_df.columns
                                 if c not in ("__time__", time_col_name) and has_numeric_values(plot_df[c])]

            # Prefer auto-detected Bottle/NG; fall back to any numeric-like columns
            default_cols = [c for c in auto_candidates if c in numeric_like_cols]
            if not default_cols and "Bottle (ml)" in numeric_like_cols:
                default_cols = ["Bottle (ml)"]
            if not default_cols and "NG (ml)" in numeric_like_cols:
                default_cols = ["NG (ml)"]

            value_cols = st.multiselect(
                "Intake series to plot",
                options=numeric_like_cols,
                default=default_cols or numeric_like_cols[:2],
                help="We extract numbers from text (e.g., '120 ml', '1,200'). Choose the series to plot.",
            )

            if not value_cols:
                st.info("Pick one or more intake columns to plot.")
            else:
                long_df = (
                    plot_df.sort_values("__time__")
                    .melt(id_vars="__time__", value_vars=value_cols,
                          var_name="Series", value_name="Value")
                )
                # ensure numeric for plotting
                long_df["Value"] = pd.to_numeric(long_df["Value"], errors="coerce")
                long_df = long_df.dropna(subset=["Value"])

                if long_df.empty:
                    st.warning("Selected columns contain no numeric values to plot.")
                else:
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
    if df_raw.empty:
        columns = ["Time start", "Bottle (ml)", "NG (ml)", "Notes"]
    else:
        columns = [c.strip() for c in df_raw.columns.tolist()]

    inputs = {}
    cols = st.columns(2)
    for i, col in enumerate(columns):
        with cols[i % 2]:
            # If the column looks like bottle/ng, offer number input; else text
            if re.search(r"\b(bottle|ng)\b", col, flags=re.I):
                val = st.number_input(col, value=0.0, step=1.0, format="%.2f")
            else:
                val = st.text_input(col, value="")
            inputs[col] = val

    submitted = st.form_submit_button("Append row ➕")
    if submitted:
        # Maintain column order when appending
        values = [inputs.get(c, "") for c in columns]
        ws.append_row(values)  # appends at the bottom
        st.success("Row added!")
        st.cache_data.clear()  # refresh the table
        st.rerun()
