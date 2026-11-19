# OLA Ride Booking Analytics Dashboard

An interactive Streamlit dashboard for exploring OLA ride bookings with SQL (SQLite), Pandas, and Plotly.

## Features
- Booking KPIs and status distribution
- Booking trends and peak-hour analysis
- Revenue by vehicle type, payment method, and month
- Customer and driver cancellation analysis
- Vehicle performance, ratings, and pickup locations
- SQL Explorer for SELECT/WITH queries
- Filtered dataset and SQL-result CSV downloads

## Dataset
Place `OLA_DataSet_Cleaned(1).csv` in the same folder as `ola_streamlit_app.py`, or upload a CSV with the same OLA dataset structure using the app sidebar.

Expected columns:
`date, time, booking_id, booking_status, customer_id, vehicle_type, pickup_location, drop_location, v_tat, c_tat, canceled_rides_by_customer, canceled_rides_by_driver, incomplete_rides, incomplete_rides_reason, booking_value, payment_method, ride_distance, driver_ratings, customer_rating, vehicle_images`

## Run locally
```bash
pip install -r requirements_ola_streamlit.txt
streamlit run ola_streamlit_app.py
```

## Run in Google Colab
```python
!pip install -q streamlit plotly
```
Upload `ola_streamlit_app.py` and `OLA_DataSet_Cleaned(1).csv` to the Colab session, then run:
```python
!streamlit run ola_streamlit_app.py &>/content/streamlit.log &
```
For a public preview, use a tunneling service approved in your environment. Do not expose private datasets publicly.
