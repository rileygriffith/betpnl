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
df_ledger = conn.read(worksheet="transactions", ttl=0).dropna(how="all")
df_pending = conn.read(worksheet="pending", ttl=0).dropna(how="all")

# Pre-processing for Dropdowns & Charts
df_ledger['event_date'] = pd.to_datetime(df_ledger['event_date'])

# Get unique list of sportsbooks for the dropdowns
existing_books = sorted(df_ledger['book'].unique().tolist()) if not df_ledger.empty else []

# --- MONTHLY CALCULATIONS ---
now = datetime.now()
df_month = df_ledger[(df_ledger['event_date'].dt.month == now.month) & 
                     (df_ledger['event_date'].dt.year == now.year)].copy()

daily_totals = df_month.groupby('event_date')['total_won'].sum().reset_index().sort_values('event_date')
daily_totals['cumulative_pnl'] = daily_totals['total_won'].cumsum()

monthly_pnl = df_month['total_won'].sum()
pnl_color = "green" if monthly_pnl >= 0 else "red"

# --- HEADER METRICS ---
st.title("💰 Bet Management")
c1, c2 = st.columns(2)
c1.metric("All-Time PnL", f"${df_ledger['total_won'].sum():,.2f}")
c2.metric(f"{now.strftime('%B')} Cumulative PnL", f"${monthly_pnl:,.2f}", delta=f"{monthly_pnl:,.2f}")

st.divider()

# --- CUMULATIVE CHART ---
if not daily_totals.empty:
    line = alt.Chart(daily_totals).mark_line(point=True, color=pnl_color, strokeWidth=3, interpolate='monotone').encode(
        x=alt.X('event_date:T', title='Date'),
        y=alt.Y('cumulative_pnl:Q', title='Cumulative PnL ($)'),
        tooltip=[alt.Tooltip('event_date:T', title='Date'), alt.Tooltip('cumulative_pnl:Q', format='$.2f')]
    )
    rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='white', strokeDash=[5, 5]).encode(y='y')
    st.altair_chart(line + rule, use_container_width=True)

st.divider()

# --- ENTRY TABS ---
tab_bet, tab_bulk, tab_pending = st.tabs(["🎯 Single Bet", "📊 Bulk PnL", "⏳ Pending Sweats"])

with tab_bet:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            b_date = st.date_input("Date", datetime.now(), key="b_date")
            # HYBRID DROPDOWN: Pick existing or type new
            b_book = st.selectbox("Sportsbook", options=existing_books, key="b_book_select", 
                                  placeholder="Select or type a new book...", 
                                  index=None, accept_new_options=True)
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
                    if mask.any(): df_ledger.loc[mask, 'total_won'] += potential
                    else:
                        new_row = pd.DataFrame([{"event_date": date_str, "book": b_book, "timeframe_type": "daily", "total_risked": 0.0, "total_won": potential, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                        df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                    conn.update(worksheet="transactions", data=df_ledger)
                    st.rerun()

        with btn_col2:
            if st.button("❌ Loss", use_container_width=True):
                if b_risk and b_book:
                    mask = (df_ledger['event_date'] == pd.Timestamp(b_date)) & (df_ledger['book'] == b_book)
                    if mask.any(): df_ledger.loc[mask, 'total_won'] -= b_risk
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

with tab_bulk:
    with st.form("bulk_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            p_date = st.date_input("Date", datetime.now(), key="p_date")
            p_timeframe = st.selectbox("Type", ["daily", "monthly", "yearly"])
        with col2:
            # Same hybrid logic for bulk entry
            p_book = st.selectbox("Source", options=existing_books, key="p_book_select", 
                                  index=None, accept_new_options=True)
            p_pnl = st.number_input("Net PnL ($)", step=0.01, key="p_pnl", value=None)
        if st.form_submit_button("Log Bulk PnL"):
            if p_pnl is not None and p_book:
                new_row = pd.DataFrame([{"event_date": p_date.strftime('%Y-%m-%d'), "book": p_book, "timeframe_type": p_timeframe, "total_risked": 0.0, "total_won": p_pnl, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                df_ledger = pd.concat([df_ledger, new_row], ignore_index=True)
                conn.update(worksheet="transactions", data=df_ledger)
                st.rerun()

with tab_pending:
    if not df_pending.empty:
        st.data_editor(df_pending, use_container_width=True, hide_index=True)
        if st.button("Clear All Pending"):
            conn.update(worksheet="pending", data=pd.DataFrame(columns=df_pending.columns))
            st.rerun()

# --- DATA MANAGEMENT PANEL ---
st.divider()
st.subheader("⚙️ Data Management")
with st.expander("Edit or Delete Ledger Entries"):
    # Sort history newest first for the editor
    df_ledger_display = df_ledger.copy()
    df_ledger_display['event_date'] = df_ledger_display['event_date'].dt.strftime('%Y-%m-%d')
    df_ledger_display = df_ledger_display.sort_values('event_date', ascending=False)
    
    edited_df = st.data_editor(df_ledger_display, use_container_width=True, num_rows="dynamic", key="ledger_editor")
    
    if st.button("💾 Save Changes to Ledger"):
        conn.update(worksheet="transactions", data=edited_df)
        st.success("Google Sheets updated!")
        st.rerun()