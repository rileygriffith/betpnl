import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Bet Tracker", layout="wide") # Changed to wide for charts

conn = st.connection("gsheets", type=GSheetsConnection)

def calc_pnl(risk, odds):
    if risk is None or odds is None: return 0.0
    if odds > 0:
        return risk * (odds / 100)
    elif odds < 0:
        return risk * (100 / abs(odds))
    return 0.0

# Load Data
df_ledger = conn.read(worksheet="transactions", ttl=0).dropna(how="all")
df_pending = conn.read(worksheet="pending", ttl=0).dropna(how="all")

# Convert dates to datetime objects for math
df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date'])

# --- MONTHLY CALCULATIONS ---
now = datetime.now()
df_month = df_ledger[(df_ledger['event_date'].dt.month == now.month) & 
                     (df_ledger['event_date'].dt.year == now.year)].copy()

monthly_pnl = df_month['total_won'].sum()
pnl_color = "green" if monthly_pnl >= 0 else "red"

# Prepare daily data for the line chart
# Group by date and sum PnL for all books on that day
daily_pnl = df_month.groupby('event_date')['total_won'].sum().reset_index()
daily_pnl = daily_pnl.sort_values('event_date')

# --- HEADER ---
st.title("💰 Bet Management")
c1, c2 = st.columns(2)
c1.metric("All-Time PnL", f"${df_ledger['total_won'].sum():,.2f}")
c2.metric(f"PnL for {now.strftime('%B')}", f"${monthly_pnl:,.2f}", 
          delta=f"{monthly_pnl:,.2f}", delta_color="normal")

# --- VISUALS SECTION ---
st.divider()
if not daily_pnl.empty:
    st.subheader(f"Performance: {now.strftime('%B %Y')}")
    
    # Altair Chart: Line with points
    # Color logic: Red if monthly total is down, Green if up
    chart = alt.Chart(daily_pnl).mark_line(
        point=True, 
        color=pnl_color,
        strokeWidth=3
    ).encode(
        x=alt.X('event_date:T', title='Date', axis=alt.Axis(format='%b %d')),
        y=alt.Y('total_won:Q', title='Daily PnL ($)'),
        tooltip=['event_date', 'total_won']
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No data for the current month yet.")

st.divider()

# --- ENTRY TABS ---
tab_bet, tab_bulk, tab_pending = st.tabs(["🎯 Single Bet", "📊 Bulk/Manual PnL", "⏳ Pending Sweats"])

# --- TAB 1: SINGLE BET ENTRY ---
with tab_bet:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            b_date = st.date_input("Date", datetime.now(), key="b_date")
            b_book = st.text_input("Sportsbook", key="b_book", placeholder="DraftKings...")
        with col2:
            b_risk = st.number_input("Risked ($)", min_value=0.0, step=1.0, key="b_risk", value=None)
            b_odds = st.number_input("American Odds", step=1, key="b_odds", value=None, placeholder="-110")
        
        potential = calc_pnl(b_risk, b_odds)
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        date_str = b_date.strftime('%Y-%m-%d')

        with btn_col1:
            if st.button("✅ Win", use_container_width=True, type="primary"):
                if b_risk and b_odds and b_book:
                    mask = (df_ledger['event_date'] == pd.Timestamp(b_date)) & (df_ledger['book'] == b_book)
                    if mask.any():
                        df_ledger.loc[mask, 'total_won'] += potential
                    else:
                        new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": potential, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                        df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                    conn.update(worksheet="transactions", data=df_ledger)
                    st.rerun()

        with btn_col2:
            if st.button("❌ Loss", use_container_width=True):
                if b_risk and b_book:
                    mask = (df_ledger['event_date'] == pd.Timestamp(b_date)) & (df_ledger['book'] == b_book)
                    if mask.any():
                        df_ledger.loc[mask, 'total_won'] -= b_risk
                    else:
                        new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": -b_risk, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                        df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                    conn.update(worksheet="transactions", data=df_ledger)
                    st.rerun()

        with btn_col3:
            if st.button("⏳ Pending", use_container_width=True):
                if b_risk and b_odds and b_book:
                    new_pending = pd.DataFrame([{"event_date": date_str, "book": b_book, "amount_risked": b_risk, "odds": b_odds, "potential_pnl": potential, "status": "pending"}])
                    df_pending = pd.concat([df_pending, new_pending], ignore_index=True)
                    conn.update(worksheet="pending", data=df_pending)
                    st.rerun()

# --- TAB 2: BULK ENTRY (logic remains same, uses value=None) ---
with tab_bulk:
    with st.form("bulk_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            p_date = st.date_input("Date", datetime.now(), key="p_date")
            p_timeframe = st.selectbox("Timeframe", ["daily", "monthly", "yearly"])
        with col2:
            p_book = st.text_input("Sportsbook/Source", key="p_book")
            p_pnl = st.number_input("Net PnL ($)", step=0.01, key="p_pnl", value=None)
        if st.form_submit_button("Log Bulk PnL"):
            if p_pnl is not None:
                date_str = p_date.strftime('%Y-%m-%d')
                new_row = pd.DataFrame([{"event_date": date_str, "book": p_book, "timeframe_type": p_timeframe, "total_risked": 0.0, "total_won": p_pnl, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

# --- TAB 3: PENDING VIEW ---
with tab_pending:
    if not df_pending.empty:
        st.dataframe(df_pending, use_container_width=True, hide_index=True)
        if st.button("Clear All Pending"):
            conn.update(worksheet="pending", data=pd.DataFrame(columns=df_pending.columns))
            st.rerun()
    else:
        st.info("No active sweats.")

# --- FOOTER ---
with st.expander("📜 History"):
    st.dataframe(df_ledger.sort_values("event_date", ascending=False), use_container_width=True)