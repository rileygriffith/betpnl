import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Bet Tracker", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

def calc_pnl(risk, odds):
    if risk is None or odds is None: return 0.0
    if odds > 0:
        return risk * (odds / 100)
    elif odds < 0:
        return risk * (100 / abs(odds))
    return 0.0

# --- LOAD DATA ---
try:
    df_ledger = conn.read(worksheet="transactions", ttl=0)
    df_pending = conn.read(worksheet="pending", ttl=0)
except Exception:
    df_ledger = pd.DataFrame(columns=["event_date", "book", "timeframe_type", "total_risked", "total_won", "last_updated"])
    df_pending = pd.DataFrame(columns=["event_date", "book", "amount_risked", "odds", "potential_pnl", "status"])

# --- CLEANING ---
df_ledger = df_ledger.dropna(subset=['event_date', 'book', 'total_won'], how='all')
if not df_ledger.empty:
    df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date'], errors='coerce')
    df_ledger = df_ledger.dropna(subset=['event_date'])
    df_ledger['total_won'] = pd.to_numeric(df_ledger['total_won'], errors='coerce').fillna(0.0)
    df_ledger['last_updated'] = pd.to_datetime(df_ledger['last_updated'], errors='coerce')

existing_books = sorted(df_ledger['book'].unique().tolist()) if not df_ledger.empty else []

# --- MONTHLY CALCULATIONS ---
now = datetime.now()
df_month = df_ledger[(df_ledger['event_date'].dt.month == now.month) & (df_ledger['event_date'].dt.year == now.year)].copy()
daily_totals = df_month.groupby('event_date')['total_won'].sum().reset_index().sort_values('event_date')
daily_totals['cumulative_pnl'] = daily_totals['total_won'].cumsum()
monthly_pnl = df_month['total_won'].sum() if not df_month.empty else 0.0
pnl_color = "green" if monthly_pnl >= 0 else "red"

# --- UI HEADER ---
st.title("💰 Bet Management")
c1, c2 = st.columns(2)
c1.metric("All-Time PnL", f"${df_ledger['total_won'].sum():,.2f}")
c2.metric(f"{now.strftime('%B')} PnL", f"${monthly_pnl:,.2f}", delta=f"{monthly_pnl:,.2f}")

st.divider()

# --- CHART ---
if not daily_totals.empty:
    line = alt.Chart(daily_totals).mark_line(point=True, color=pnl_color, strokeWidth=3).encode(
        x=alt.X('event_date:T', title='Date'),
        y=alt.Y('cumulative_pnl:Q', title='Cumulative PnL ($)'),
        tooltip=['event_date', 'cumulative_pnl']
    )
    st.altair_chart(line, use_container_width=True)

st.divider()

# --- TABS ---
tab_bet, tab_bulk, tab_pending = st.tabs(["🎯 Single Bet", "📊 Bulk PnL", "⏳ Pending Sweats"])

# TAB 1: SINGLE BET
with tab_bet:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            b_date = st.date_input("Date", datetime.now(), key="ent_date")
            b_book = st.selectbox("Sportsbook", options=existing_books, key="b_book_select", index=None, accept_new_options=True)
        with col2:
            b_risk = st.number_input("Risked ($)", min_value=0.0, step=1.0, key="b_risk", value=None)
            b_odds = st.number_input("American Odds", step=1, key="b_odds", value=None)
        
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        date_str = b_date.strftime('%Y-%m-%d')
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if btn_col1.button("✅ Win", use_container_width=True, type="primary"):
            if b_risk and b_odds and b_book:
                p = calc_pnl(b_risk, b_odds)
                new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_won": p, "last_updated": update_time}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date']).dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

        if btn_col2.button("❌ Loss", use_container_width=True):
            if b_risk and b_book:
                new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_won": -b_risk, "last_updated": update_time}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date']).dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

        if btn_col3.button("⏳ Pending", use_container_width=True):
            if b_risk and b_odds and b_book:
                p = calc_pnl(b_risk, b_odds)
                new_p = pd.DataFrame([{"event_date": date_str, "book": b_book, "amount_risked": b_risk, "odds": b_odds, "potential_pnl": p, "status": "pending"}])
                df_pending = pd.concat([df_pending, new_p], ignore_index=True)
                conn.update(worksheet="pending", data=df_pending)
                st.rerun()

# TAB 2: BULK PNL
with tab_bulk:
    with st.form("bulk_form", clear_on_submit=True):
        st.subheader("Manual PnL Entry")
        col1, col2 = st.columns(2)
        with col1:
            p_date = st.date_input("Date", datetime.now(), key="p_date")
            p_timeframe = st.selectbox("Type", ["daily", "monthly", "yearly", "other"], key="p_type")
        with col2:
            p_book = st.selectbox("Source", options=existing_books, key="p_book_select", index=None, accept_new_options=True)
            p_pnl = st.number_input("Net PnL ($)", step=0.01, key="p_pnl", value=None)
        
        if st.form_submit_button("Log Bulk PnL"):
            if p_pnl is not None and p_book:
                new_row = pd.DataFrame([{
                    "event_date": p_date.strftime('%Y-%m-%d'), 
                    "book": p_book, 
                    "timeframe_type": p_timeframe, 
                    "total_risked": 0.0, 
                    "total_won": p_pnl, 
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date']).dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

# TAB 3: PENDING RESOLVE
with tab_pending:
    if not df_pending.empty:
        st.subheader("Resolve a Sweat")
        df_pending['display_name'] = df_pending['book'] + " ($" + df_pending['amount_risked'].astype(str) + " on " + df_pending['event_date'].astype(str) + ")"
        bet_to_resolve = st.selectbox("Select Bet", options=df_pending.index, format_func=lambda x: df_pending.loc[x, 'display_name'])
        
        res_col1, res_col2 = st.columns(2)
        selected_bet = df_pending.loc[bet_to_resolve]

        if res_col1.button("🏆 Resolve as WIN", use_container_width=True, type="primary"):
            new_row = pd.DataFrame([{"event_date": selected_bet['event_date'], "book": selected_bet['book'], "timeframe_type": "daily", "total_won": selected_bet['potential_pnl'], "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
            df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
            df_pending = df_pending.drop(bet_to_resolve).drop(columns=['display_name'])
            df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date']).dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=df_ledger)
            conn.update(worksheet="pending", data=df_pending)
            st.rerun()

        if res_col2.button("💀 Resolve as LOSS", use_container_width=True):
            new_row = pd.DataFrame([{"event_date": selected_bet['event_date'], "book": selected_bet['book'], "timeframe_type": "daily", "total_won": -selected_bet['amount_risked'], "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
            df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
            df_pending = df_pending.drop(bet_to_resolve).drop(columns=['display_name'])
            df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date']).dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=df_ledger)
            conn.update(worksheet="pending", data=df_pending)
            st.rerun()

        st.divider()
        st.dataframe(df_pending.drop(columns=['display_name']), use_container_width=True, hide_index=True)
    else:
        st.info("No active sweats.")

# DATA MANAGEMENT
st.divider()
with st.expander("⚙️ Bulk Edit Ledger"):
    if not df_ledger.empty:
        df_edit = df_ledger.copy()
        df_edit['event_date'] = df_edit['event_date'].dt.strftime('%Y-%m-%d')
        df_edit = df_edit.sort_values('last_updated', ascending=False)
        edited_df = st.data_editor(df_edit, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Save Bulk Changes"):
            edited_df['event_date'] = pd.to_datetime(edited_df['event_date'], errors='coerce').dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=edited_df)
            st.rerun()