import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Bet Tracker", layout="centered")

conn = st.connection("gsheets", type=GSheetsConnection)

def calc_pnl(risk, odds):
    if odds > 0:
        return risk * (odds / 100)
    elif odds < 0:
        return risk * (100 / abs(odds))
    return 0.0

# Load both sheets
df_ledger = conn.read(worksheet="transactions", ttl=0).dropna(how="all")
df_pending = conn.read(worksheet="pending", ttl=0).dropna(how="all")

# --- HEADER ---
all_time_pnl = df_ledger['total_won'].sum()
st.title("💰 Bet Management")
st.metric(label="All-Time Profit/Loss", value=f"${all_time_pnl:,.2f}")

st.divider()

# --- ENTRY SECTION ---
st.subheader("New Individual Bet")
with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        b_date = st.date_input("Date", datetime.now())
        b_book = st.text_input("Sportsbook")
    with col2:
        b_risk = st.number_input("Risked ($)", min_value=0.0, step=5.0)
        b_odds = st.number_input("American Odds", step=1, value=-110)
    
    # Calculate potential win for the UI
    potential = calc_pnl(b_risk, b_odds)
    st.caption(f"Potential Profit: ${potential:.2f} | Total Return: ${potential + b_risk:.2f}")

    # Three Button Logic
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    date_str = b_date.strftime('%Y-%m-%d')

    with btn_col1:
        if st.button("✅ Log Win", use_container_width=True, type="primary"):
            # Upsert into Ledger
            mask = (df_ledger['event_date'].astype(str) == date_str) & (df_ledger['book'] == b_book)
            if mask.any():
                df_ledger.loc[mask, 'total_won'] += potential
                st.warning("Updated existing ledger entry.")
            else:
                new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": potential, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
            conn.update(worksheet="transactions", data=df_ledger)
            st.success("Win Logged!")
            st.rerun()

    with btn_col2:
        if st.button("❌ Log Loss", use_container_width=True):
            # Upsert into Ledger (Subtracting Risk)
            mask = (df_ledger['event_date'].astype(str) == date_str) & (df_ledger['book'] == b_book)
            if mask.any():
                df_ledger.loc[mask, 'total_won'] -= b_risk
                st.warning("Updated existing ledger entry.")
            else:
                new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": -b_risk, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
            conn.update(worksheet="transactions", data=df_ledger)
            st.error(f"Loss of ${b_risk} Logged.")
            st.rerun()

    with btn_col3:
        if st.button("⏳ Mark Pending", use_container_width=True):
            new_pending = pd.DataFrame([{
                "event_date": date_str,
                "book": b_book,
                "amount_risked": b_risk,
                "odds": b_odds,
                "potential_pnl": potential,
                "status": "pending"
            }])
            df_pending = pd.concat([df_pending, new_pending], ignore_index=True)
            conn.update(worksheet="pending", data=df_pending)
            st.info("Added to Pending List.")
            st.rerun()

# --- PENDING TRACKER ---
st.divider()
st.subheader("⏳ Active Sweats")
if not df_pending.empty:
    # Display pending bets with a "Clear All" button for maintenance
    st.dataframe(df_pending, use_container_width=True, hide_index=True)
    if st.button("Clear All Pending Bets"):
        empty_pending = pd.DataFrame(columns=df_pending.columns)
        conn.update(worksheet="pending", data=empty_pending)
        st.rerun()
else:
    st.write("No pending bets. Place some action!")

# --- LEDGER VIEW ---
with st.expander("📜 View Recent Ledger"):
    if not df_ledger.empty:
        st.dataframe(df_ledger.sort_values("event_date", ascending=False).head(10), use_container_width=True)