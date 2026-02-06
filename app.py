import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Bet Tracker", layout="centered")

# Connect to Google Sheets (Setup your secrets in Streamlit Cloud)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Fetch data and drop completely empty rows
    return conn.read(worksheet="transactions", ttl=0).dropna(how="all")

df = load_data()

# --- HEADER & KEY METRIC ---
# We calculate All-Time PnL by summing the 'total_won' column 
# (which based on your data, currently holds the net PnL values)
all_time_pnl = df['total_won'].sum()

st.title("💰 Total PnL")
st.metric(label="All-Time Profit/Loss", value=f"${all_time_pnl:,.2f}", delta=None)

st.divider()

# --- INPUT SECTION ---
st.subheader("Add New Entry")

with st.form("pnl_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        entry_date = st.date_input("Date", datetime.now())
        # Your 4 timeframe types
        timeframe = st.selectbox("Timeframe", ["daily", "monthly", "yearly", "other"])
        
    with col2:
        book = st.text_input("Sportsbook", placeholder="e.g. HardRock")
        pnl_value = st.number_input("PnL ($)", value=0.0, step=0.01, help="Positive for win, negative for loss")

    submit = st.form_submit_button("Log PnL")

    if submit:
        if not book:
            st.error("Please enter a Sportsbook name.")
        else:
            # Prepare new row
            new_row = pd.DataFrame([{
                "event_date": entry_date.strftime('%Y-%m-%d'),
                "book": book,
                "timeframe_type": timeframe,
                "total_risked": 0.0,  # Keeping column for schema compatibility
                "total_won": pnl_value, # Storing PnL here for simplicity
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            
            # Append and Update
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="transactions", data=updated_df)
            
            st.success(f"Logged ${pnl_value:,.2f} for {book}")
            st.rerun()

# --- RECENT HISTORY ---
st.divider()
st.subheader("Recent Entries")
if not df.empty:
    # Show the last 10 entries, sorted by date
    recent = df.sort_values(by="event_date", ascending=False).head(10)
    st.table(recent[['event_date', 'book', 'timeframe_type', 'total_won']])