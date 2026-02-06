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

# --- ENTRY TABS ---
tab_bet, tab_bulk, tab_pending = st.tabs(["🎯 Single Bet", "📊 Bulk/Manual PnL", "⏳ Pending Sweats"])

# --- TAB 1: SINGLE BET ENTRY ---
with tab_bet:
    st.subheader("Individual Game Entry")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            b_date = st.date_input("Date", datetime.now(), key="b_date")
            b_book = st.text_input("Sportsbook", key="b_book")
        with col2:
            b_risk = st.number_input("Risked ($)", min_value=0.0, step=5.0, key="b_risk")
            b_odds = st.number_input("American Odds", step=1, value=-110, key="b_odds")
        
        potential = calc_pnl(b_risk, b_odds)
        st.caption(f"Potential Profit: ${potential:.2f}")

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        date_str = b_date.strftime('%Y-%m-%d')

        with btn_col1:
            if st.button("✅ Win", use_container_width=True, type="primary"):
                mask = (df_ledger['event_date'].astype(str) == date_str) & (df_ledger['book'] == b_book)
                if mask.any():
                    df_ledger.loc[mask, 'total_won'] += potential
                else:
                    new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": potential, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                    df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

        with btn_col2:
            if st.button("❌ Loss", use_container_width=True):
                mask = (df_ledger['event_date'].astype(str) == date_str) & (df_ledger['book'] == b_book)
                if mask.any():
                    df_ledger.loc[mask, 'total_won'] -= b_risk
                else:
                    new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": -b_risk, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                    df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

        with btn_col3:
            if st.button("⏳ Pending", use_container_width=True):
                new_pending = pd.DataFrame([{"event_date": date_str, "book": b_book, "amount_risked": b_risk, "odds": b_odds, "potential_pnl": potential, "status": "pending"}])
                df_pending = pd.concat([df_pending, new_pending], ignore_index=True)
                conn.update(worksheet="pending", data=df_pending)
                st.rerun()

# --- TAB 2: BULK / MANUAL PNL ENTRY ---
with tab_bulk:
    st.subheader("Bulk PnL Entry")
    with st.form("bulk_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            p_date = st.date_input("Date", datetime.now(), key="p_date")
            p_timeframe = st.selectbox("Timeframe Type", ["daily", "monthly", "yearly", "other"])
        with col2:
            p_book = st.text_input("Sportsbook/Source", key="p_book")
            p_pnl = st.number_input("Net PnL ($)", step=0.01, key="p_pnl")

        if st.form_submit_button("Log Bulk PnL"):
            date_str = p_date.strftime('%Y-%m-%d')
            mask = (df_ledger['event_date'].astype(str) == date_str) & (df_ledger['book'] == p_book)
            
            if mask.any():
                df_ledger.loc[mask, 'total_won'] = p_pnl # Overwrites in manual mode
            else:
                new_row = pd.DataFrame([{
                    "event_date": date_str, "book": p_book, "timeframe_type": p_timeframe,
                    "total_risked": 0.0, "total_won": p_pnl,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
            
            conn.update(worksheet="transactions", data=df_ledger)
            st.success("Bulk Entry Saved!")
            st.rerun()

# --- TAB 3: PENDING VIEW ---
with tab_pending:
    st.subheader("Active Sweats")
    if not df_pending.empty:
        # Mini Metrics for pending
        m1, m2 = st.columns(2)
        m1.metric("Total Risked", f"${df_pending['amount_risked'].sum():,.2f}")
        m2.metric("Potential Gain", f"${df_pending['potential_pnl'].sum():,.2f}")
        
        st.dataframe(df_pending, use_container_width=True, hide_index=True)
        
        if st.button("Clear All Pending"):
            conn.update(worksheet="pending", data=pd.DataFrame(columns=df_pending.columns))
            st.rerun()
    else:
        st.info("No pending bets currently.")

# --- FOOTER: HISTORY ---
st.divider()
with st.expander("📜 Recent Ledger History"):
    if not df_ledger.empty:
        st.dataframe(df_ledger.sort_values("event_date", ascending=False).head(15), use_container_width=True)