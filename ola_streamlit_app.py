import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="OLA Ride Booking Analytics",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: #f4f7fb;
        border: 1px solid #e5eaf2;
        padding: 14px 16px;
        border-radius: 12px;
    }
    div[data-testid="stMetricValue"] {font-size: 1.65rem;}
</style>
""", unsafe_allow_html=True)

EXPECTED_COLUMNS = [
    "date", "time", "booking_id", "booking_status", "customer_id",
    "vehicle_type", "pickup_location", "drop_location", "v_tat", "c_tat",
    "canceled_rides_by_customer", "canceled_rides_by_driver",
    "incomplete_rides", "incomplete_rides_reason", "booking_value",
    "payment_method", "ride_distance", "driver_ratings",
    "customer_rating", "vehicle_images"
]

st.title("🚕 OLA Ride Booking Analytics")
st.caption("Interactive SQL-powered dashboard | Python · Pandas · SQLite · Plotly")

@st.cache_data(show_spinner=False)
def load_csv(uploaded_file, local_path):
    if uploaded_file is not None:
        data = pd.read_csv(uploaded_file)
    else:
        data = pd.read_csv(local_path)
    data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]
    return data

uploaded = st.sidebar.file_uploader("Upload OLA cleaned CSV", type=["csv"])
default_path = Path(__file__).parent / "OLA_DataSet_Cleaned.csv"

try:
    df = load_csv(uploaded, str(default_path))
except FileNotFoundError:
    st.info("Upload OLA_DataSet_Cleaned.csv using the sidebar to start the dashboard.")
    st.stop()
except Exception as exc:
    st.error(f"Could not read the CSV file: {exc}")
    st.stop()

missing_columns = [c for c in EXPECTED_COLUMNS if c not in df.columns]
if missing_columns:
    st.error("The uploaded file does not match the expected OLA dataset. Missing columns: " + ", ".join(missing_columns))
    st.write("Columns found:", df.columns.tolist())
    st.stop()

# Normalize data types for consistent SQL filtering and charting.
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["time"] = df["time"].astype("string").str.strip()
for col in ["booking_value", "ride_distance", "v_tat", "c_tat", "driver_ratings", "customer_rating"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# SQLite table used by every SQL section.
@st.cache_resource
def create_connection():
    return sqlite3.connect(":memory:", check_same_thread=False)

conn = create_connection()
df.to_sql("ola_bookings", conn, if_exists="replace", index=False)

def sql_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

def money(value):
    if pd.isna(value):
        return "—"
    return f"₹{value:,.0f}"

# Sidebar filters
st.sidebar.header("Dashboard Filters")
min_date = df["date"].min()
max_date = df["date"].max()

if pd.notna(min_date) and pd.notna(max_date):
    date_range = st.sidebar.date_input(
        "Booking date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date()
    )
else:
    date_range = None

statuses = sorted(df["booking_status"].dropna().astype(str).unique().tolist())
vehicles = sorted(df["vehicle_type"].dropna().astype(str).unique().tolist())
payments = sorted(df["payment_method"].dropna().astype(str).unique().tolist())

selected_status = st.sidebar.multiselect("Booking status", statuses, default=statuses)
selected_vehicle = st.sidebar.multiselect("Vehicle type", vehicles, default=vehicles)
selected_payment = st.sidebar.multiselect("Payment method", payments, default=payments)

filtered = df.copy()
if date_range and len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    filtered = filtered[filtered["date"].between(start_date, end_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
if selected_status:
    filtered = filtered[filtered["booking_status"].isin(selected_status)]
else:
    filtered = filtered.iloc[0:0]
if selected_vehicle:
    filtered = filtered[filtered["vehicle_type"].isin(selected_vehicle)]
else:
    filtered = filtered.iloc[0:0]
if selected_payment:
    filtered = filtered[filtered["payment_method"].isin(selected_payment)]
else:
    filtered = filtered.iloc[0:0]

# Build a separate filtered SQLite table so the dashboard SQL reflects sidebar selections.
filtered.to_sql("filtered_bookings", conn, if_exists="replace", index=False)

success_count = int((filtered["booking_status"] == "Success").sum())
total_revenue = filtered.loc[filtered["booking_status"] == "Success", "booking_value"].sum()
unique_customers = filtered["customer_id"].nunique()
success_rate = (success_count / len(filtered) * 100) if len(filtered) else 0

tab_overview, tab_booking, tab_revenue, tab_customer, tab_vehicle, tab_sql, tab_data = st.tabs([
    "📊 Overview", "📅 Booking Analysis", "💰 Revenue Analysis",
    "👥 Customer & Driver", "🚘 Vehicle Analysis", "🧠 SQL Explorer", "🗂️ Data Preview"
])

with tab_overview:
    st.subheader("Business Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", f"{len(filtered):,}")
    c2.metric("Successful Rides", f"{success_count:,}")
    c3.metric("Success Rate", f"{success_rate:.1f}%")
    c4.metric("Revenue from Successful Rides", money(total_revenue))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Unique Customers", f"{unique_customers:,}")
    c6.metric("Avg. Booking Value", money(filtered.loc[filtered.booking_status == "Success", "booking_value"].mean()))
    c7.metric("Avg. Ride Distance", f"{filtered.loc[filtered.booking_status == 'Success', 'ride_distance'].mean():.2f} km" if filtered.loc[filtered.booking_status == "Success", "ride_distance"].notna().any() else "—")
    c8.metric("Avg. Customer Rating", f"{filtered.loc[filtered.booking_status == 'Success', 'customer_rating'].mean():.2f}/5" if filtered.loc[filtered.booking_status == "Success", "customer_rating"].notna().any() else "—")

    left, right = st.columns(2)
    status_sql = """
        SELECT booking_status, COUNT(*) AS total_bookings
        FROM filtered_bookings
        GROUP BY booking_status ORDER BY total_bookings DESC
    """
    status_result = sql_df(status_sql)
    with left:
        st.plotly_chart(px.pie(status_result, names="booking_status", values="total_bookings",
                               hole=0.48, title="Booking Status Distribution"), use_container_width=True)
    vehicle_sql = """
        SELECT vehicle_type, COUNT(*) AS total_bookings
        FROM filtered_bookings GROUP BY vehicle_type
        ORDER BY total_bookings DESC
    """
    vehicle_result = sql_df(vehicle_sql)
    with right:
        st.plotly_chart(px.bar(vehicle_result, x="vehicle_type", y="total_bookings",
                               title="Bookings by Vehicle Type", text_auto=True), use_container_width=True)

    st.markdown("**Booking status SQL result**")
    st.dataframe(status_result, use_container_width=True, hide_index=True)

with tab_booking:
    st.subheader("Booking Performance")
    q = """
        SELECT DATE(date) AS booking_date, COUNT(*) AS total_bookings,
               SUM(CASE WHEN booking_status='Success' THEN 1 ELSE 0 END) AS successful_bookings
        FROM filtered_bookings
        GROUP BY DATE(date) ORDER BY booking_date
    """
    daily = sql_df(q)
    if not daily.empty:
        st.plotly_chart(px.line(daily, x="booking_date",
                                y=["total_bookings", "successful_bookings"],
                                markers=True, title="Daily Booking Trend"),
                        use_container_width=True)
    else:
        st.info("No booking data for the selected filters.")

    q = """
        SELECT booking_status, COUNT(*) AS total_bookings
        FROM filtered_bookings GROUP BY booking_status ORDER BY total_bookings DESC
    """
    status = sql_df(q)
    st.markdown("**SQL: Booking status distribution**")
    st.code(q, language="sql")
    st.dataframe(status, use_container_width=True, hide_index=True)

    q = """
        SELECT SUBSTR(time, 1, 2) AS booking_hour, COUNT(*) AS total_bookings
        FROM filtered_bookings
        WHERE time IS NOT NULL AND LENGTH(time) >= 2
        GROUP BY booking_hour ORDER BY booking_hour
    """
    hours = sql_df(q)
    if not hours.empty:
        st.plotly_chart(px.bar(hours, x="booking_hour", y="total_bookings",
                               title="Bookings by Hour", labels={"booking_hour": "Hour"}),
                        use_container_width=True)

with tab_revenue:
    st.subheader("Revenue Performance")
    q = """
        SELECT vehicle_type, ROUND(SUM(booking_value), 2) AS revenue,
               COUNT(*) AS successful_rides,
               ROUND(AVG(booking_value), 2) AS avg_booking_value
        FROM filtered_bookings
        WHERE booking_status='Success'
        GROUP BY vehicle_type ORDER BY revenue DESC
    """
    revenue_vehicle = sql_df(q)
    st.markdown("**SQL: Revenue by vehicle type**")
    st.code(q, language="sql")
    st.dataframe(revenue_vehicle, use_container_width=True, hide_index=True)
    if not revenue_vehicle.empty:
        st.plotly_chart(px.bar(revenue_vehicle, x="vehicle_type", y="revenue",
                               color="vehicle_type", title="Revenue by Vehicle Type",
                               text_auto=".2s"), use_container_width=True)

    q = """
        SELECT payment_method, ROUND(SUM(booking_value), 2) AS revenue,
               COUNT(*) AS successful_rides
        FROM filtered_bookings
        WHERE booking_status='Success'
        GROUP BY payment_method ORDER BY revenue DESC
    """
    payment = sql_df(q)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(px.pie(payment, names="payment_method", values="revenue",
                               hole=0.45, title="Revenue by Payment Method"),
                        use_container_width=True)
    with col2:
        st.markdown("**SQL: Revenue by payment method**")
        st.dataframe(payment, use_container_width=True, hide_index=True)

    q = """
        SELECT STRFTIME('%Y-%m', date) AS booking_month,
               ROUND(SUM(booking_value), 2) AS revenue
        FROM filtered_bookings
        WHERE booking_status='Success'
        GROUP BY booking_month ORDER BY booking_month
    """
    monthly = sql_df(q)
    if not monthly.empty:
        st.plotly_chart(px.line(monthly, x="booking_month", y="revenue",
                                markers=True, title="Monthly Revenue Trend"),
                        use_container_width=True)

with tab_customer:
    st.subheader("Customer & Driver Insights")
    q = """
        SELECT customer_id, COUNT(*) AS successful_rides
        FROM filtered_bookings WHERE booking_status='Success'
        GROUP BY customer_id ORDER BY successful_rides DESC LIMIT 10
    """
    top_customers = sql_df(q)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top 10 customers by successful rides**")
        st.dataframe(top_customers, use_container_width=True, hide_index=True)
    q = """
        SELECT canceled_rides_by_driver AS cancellation_reason, COUNT(*) AS cancellations
        FROM filtered_bookings
        WHERE booking_status='Canceled by Driver'
          AND canceled_rides_by_driver IS NOT NULL
        GROUP BY canceled_rides_by_driver ORDER BY cancellations DESC
    """
    #driver_cancel = sql_df(q)
    #with col2:
      #  st.markdown("**Driver cancellation reasons**")
      #  st.dataframe(driver_cancel, use_container_width=True, hide_index=True)
    #if not driver_cancel.empty:
      #  st.plotly_chart(px.bar(driver_cancel, x="cancellations", y="cancellation_reason",
        #                       orientation="h", title="Reasons for Driver Cancellations"),
        #                use_container_width=True)
                        

    q = """
        SELECT ROUND(AVG(driver_ratings), 2) AS avg_driver_rating,
               ROUND(AVG(customer_rating), 2) AS avg_customer_rating
        FROM filtered_bookings WHERE booking_status='Success'
    """
    ratings = sql_df(q)
    st.markdown("**Average ratings (successful rides)**")
    st.dataframe(ratings, use_container_width=True, hide_index=True)

    q = """
        SELECT incomplete_rides_reason, COUNT(*) AS incomplete_rides
        FROM filtered_bookings
        WHERE incomplete_rides='Yes' AND incomplete_rides_reason IS NOT NULL
        GROUP BY incomplete_rides_reason ORDER BY incomplete_rides DESC
    """
    incomplete = sql_df(q)
    st.markdown("**Incomplete ride reasons**")
    st.dataframe(incomplete, use_container_width=True, hide_index=True)

with tab_vehicle:
    st.subheader("Vehicle Performance")
    q = """
        SELECT vehicle_type,
               COUNT(*) AS total_bookings,
               SUM(CASE WHEN booking_status='Success' THEN 1 ELSE 0 END) AS successful_rides,
               ROUND(AVG(CASE WHEN booking_status='Success' THEN ride_distance END), 2) AS avg_ride_distance,
               ROUND(AVG(CASE WHEN booking_status='Success' THEN driver_ratings END), 2) AS avg_driver_rating,
               ROUND(AVG(CASE WHEN booking_status='Success' THEN customer_rating END), 2) AS avg_customer_rating
        FROM filtered_bookings GROUP BY vehicle_type ORDER BY total_bookings DESC
    """
    vehicle_perf = sql_df(q)
    st.code(q, language="sql")
    st.dataframe(vehicle_perf, use_container_width=True, hide_index=True)
    if not vehicle_perf.empty:
        st.plotly_chart(px.bar(vehicle_perf, x="vehicle_type",
                               y=["successful_rides", "total_bookings"],
                               barmode="group", title="Total vs Successful Bookings by Vehicle"),
                        use_container_width=True)

    q = """
        SELECT pickup_location, COUNT(*) AS total_pickups
        FROM filtered_bookings
        GROUP BY pickup_location ORDER BY total_pickups DESC LIMIT 10
    """
    pickup = sql_df(q)
    if not pickup.empty:
        st.plotly_chart(px.bar(pickup, x="total_pickups", y="pickup_location",
                               orientation="h", title="Top 10 Pickup Locations"),
                        use_container_width=True)

with tab_sql:
    st.subheader("SQL Query Explorer")
    st.write("Run SELECT queries against the `filtered_bookings` table (respects the sidebar filters) or `ola_bookings` (entire dataset).")
    examples = {
        "Total bookings": "SELECT COUNT(*) AS total_bookings FROM filtered_bookings;",
        "Booking status distribution": """SELECT booking_status, COUNT(*) AS total_bookings
FROM filtered_bookings
GROUP BY booking_status
ORDER BY total_bookings DESC;""",
        "Successful ride revenue": """SELECT ROUND(SUM(booking_value), 2) AS total_revenue
FROM filtered_bookings
WHERE booking_status = 'Success';""",
        "Revenue by vehicle": """SELECT vehicle_type, ROUND(SUM(booking_value), 2) AS revenue
FROM filtered_bookings
WHERE booking_status = 'Success'
GROUP BY vehicle_type
ORDER BY revenue DESC;""",
        "Top 10 pickup locations": """SELECT pickup_location, COUNT(*) AS rides
FROM filtered_bookings
GROUP BY pickup_location
ORDER BY rides DESC
LIMIT 10;""",
        "Top 10 customers": """SELECT customer_id, COUNT(*) AS successful_rides
FROM filtered_bookings
WHERE booking_status = 'Success'
GROUP BY customer_id
ORDER BY successful_rides DESC
LIMIT 10;"""
    }
    choice = st.selectbox("Load an example query", list(examples.keys()))
    default_query = examples[choice]
    user_query = st.text_area("SQL query", value=default_query, height=180)
    if st.button("▶ Run SQL Query", type="primary"):
        normalized = user_query.strip().lower()
        if not (normalized.startswith("select") or normalized.startswith("with")):
            st.error("Only SELECT or WITH queries are allowed.")
        elif ";" in normalized.rstrip(";"):
            st.error("Please run one SQL statement at a time.")
        else:
            try:
                output = pd.read_sql_query(user_query, conn)
                st.success(f"Query returned {len(output):,} rows.")
                st.dataframe(output, use_container_width=True, hide_index=True)
                st.download_button("Download SQL result as CSV",
                                   output.to_csv(index=False).encode("utf-8"),
                                   file_name="ola_sql_query_result.csv",
                                   mime="text/csv")
            except Exception as exc:
                st.error(f"SQL error: {exc}")

with tab_data:
    st.subheader("Dataset Preview")
    st.write(f"Showing {len(filtered):,} filtered rows out of {len(df):,} total rows.")
    st.dataframe(filtered.head(1000), use_container_width=True, hide_index=True)
    st.download_button(
        "⬇ Download filtered data as CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="ola_filtered_bookings.csv",
        mime="text/csv"
    )
    st.download_button(
        "⬇ Download complete cleaned data as CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="ola_bookings_cleaned.csv",
        mime="text/csv"
    )

st.sidebar.divider()
st.sidebar.caption("OLA Ride Booking Analytics · SQLite SQL results")
st.sidebar.caption(f"Loaded {len(df):,} rows and {len(df.columns)} columns.")
