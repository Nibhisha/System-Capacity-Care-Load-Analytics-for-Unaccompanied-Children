import os
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="UAC System Capacity & Care Load Analytics", layout="wide")
st.title("System Capacity & Care Load Analytics for Unaccompanied Children")
st.caption("Operational analytics dashboard for CBP custody, HHS care, transfers, discharges, capacity stress, and backlog pressure.")

DATA_FILE = "processed_uac_metrics.csv"

@st.cache_data
def load_data(path: str = DATA_FILE) -> pd.DataFrame:
    if not os.path.exists(path):
        st.error(f"Data file not found: {path}")
        st.write("Files found in this folder:", os.listdir("."))
        st.stop()

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    if "Date" not in df.columns:
        st.error("The dataset must contain a Date column.")
        st.write("Columns found:", list(df.columns))
        st.stop()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    numeric_cols = [c for c in df.columns if c != "Date"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    required = [
        "Children in CBP custody",
        "Children in HHS Care",
        "Children transferred out of CBP custody",
        "Children discharged from HHS Care",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error("Missing required columns: " + ", ".join(missing))
        st.write("Columns found:", list(df.columns))
        st.stop()

    if "Total System Load" not in df.columns:
        df["Total System Load"] = df["Children in CBP custody"] + df["Children in HHS Care"]
    if "Net Daily Intake" not in df.columns:
        df["Net Daily Intake"] = df["Children transferred out of CBP custody"] - df["Children discharged from HHS Care"]
    if "Backlog Indicator" not in df.columns:
        df["Backlog Indicator"] = df["Net Daily Intake"].rolling(7, min_periods=1).sum()
    if "Care Load Volatility Index" not in df.columns:
        df["Care Load Volatility Index"] = df["Total System Load"].pct_change().abs().rolling(7, min_periods=1).mean() * 100
    if "Stress Threshold P90" not in df.columns:
        df["Stress Threshold P90"] = df["Total System Load"].quantile(0.90)

    return df

df = load_data()

with st.sidebar:
    st.header("Controls")
    min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
    dr = st.date_input("Date range", [min_d, max_d], min_value=min_d, max_value=max_d)
    gran = st.selectbox("Time granularity", ["Daily", "Weekly", "Monthly"])

    available_metrics = [
        "Children in CBP custody",
        "Children in HHS Care",
        "Total System Load",
        "Net Daily Intake",
        "Backlog Indicator",
        "Care Load Volatility Index",
    ]
    available_metrics = [m for m in available_metrics if m in df.columns]
    metrics = st.multiselect(
        "Metrics",
        available_metrics,
        default=[m for m in ["Children in CBP custody", "Children in HHS Care", "Total System Load"] if m in available_metrics],
    )

if len(dr) == 2:
    start, end = pd.to_datetime(dr[0]), pd.to_datetime(dr[1])
    view = df[(df["Date"] >= start) & (df["Date"] <= end)].copy()
else:
    view = df.copy()

if view.empty:
    st.warning("No records found for the selected date range.")
    st.stop()

if gran != "Daily":
    rule = "W-MON" if gran == "Weekly" else "MS"
    mean_cols = [c for c in ["Children in CBP custody", "Children in HHS Care", "Total System Load", "Backlog Indicator", "Care Load Volatility Index", "Stress Threshold P90"] if c in view.columns]
    sum_cols = [c for c in ["Children apprehended and placed in CBP custody", "Children transferred out of CBP custody", "Children discharged from HHS Care", "Net Daily Intake"] if c in view.columns]
    agg = {c: "mean" for c in mean_cols}
    agg.update({c: "sum" for c in sum_cols})
    view = view.set_index("Date").resample(rule).agg(agg).reset_index()

latest = view.iloc[-1]
cols = st.columns(5)
cols[0].metric("Total Children Under Care", f"{latest.get('Total System Load', 0):,.0f}")
cols[1].metric("CBP Custody", f"{latest.get('Children in CBP custody', 0):,.0f}")
cols[2].metric("HHS Care", f"{latest.get('Children in HHS Care', 0):,.0f}")
cols[3].metric("Net Intake Pressure", f"{latest.get('Net Daily Intake', 0):,.0f}")
cols[4].metric("Backlog Indicator", f"{latest.get('Backlog Indicator', 0):,.0f}")

st.subheader("System Load Overview")
if metrics:
    long = view.melt(id_vars="Date", value_vars=metrics, var_name="Metric", value_name="Children")
    st.plotly_chart(px.line(long, x="Date", y="Children", color="Metric"), use_container_width=True)
else:
    st.info("Select at least one metric from the sidebar.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("CBP vs HHS Load Comparison")
    st.plotly_chart(px.area(view, x="Date", y=["Children in CBP custody", "Children in HHS Care"]), use_container_width=True)
with c2:
    st.subheader("Net Intake & Backlog Trends")
    st.plotly_chart(px.line(view, x="Date", y=["Net Daily Intake", "Backlog Indicator"]), use_container_width=True)

st.subheader("Capacity Stress Monitor")
st.plotly_chart(px.line(view, x="Date", y=["Total System Load", "Stress Threshold P90"]), use_container_width=True)

st.subheader("Data Table")
st.dataframe(view, use_container_width=True)
