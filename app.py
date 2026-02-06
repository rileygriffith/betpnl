import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import pytz

# --- CONFIG ---
st.set_page_config(page_title="Bet Tracker", layout="wide")
local_tz = pytz.timezone("America/New_York")
now_local = datetime.now(local_tz)

# Initialize Session States
if "sticky_date" not in st.session_state:
    st.session_state.sticky_date = (now_local - timedelta(days=1)).date()
if "staged_bets" not in st.session_state:
    st.session_state.staged_bets = []

# --- NORMALIZATION ENGINE ---
def normalize_dataframe(df, sheet_type="transactions"):
    """Ensures the dataframe is perfectly formatted before sending to GSheets."""
    if df.empty:
        if sheet_type == "transactions":
            return pd.DataFrame(columns=["event_date", "book", "timeframe_type", "total_won", "last_updated"])
        else:
            return pd.DataFrame(columns=["event_date", "book", "amount_risked", "odds", "potential_pnl", "status"])
    
    df = df.copy()
    
    # Force event_date to standardized string
    df['event_date'] = pd.to_datetime(df['event_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['book'] = df['book'].astype(str).str.strip().str.title()
    
    if sheet_type == "transactions":
        df['timeframe_type'] = df['timeframe_type'].astype(str).str.strip().str.lower()
        df['total_won'] = pd.to_numeric(df['total_won'], errors='coerce').fillna(0.0).astype(float)
        
        # Safe Datetime Conversion
        df['last_updated'] = pd.to_datetime(df['last_updated'], errors='coerce')
        df['last_updated'] = df['last_updated'].fillna(pd.Timestamp.now())
        df['last_updated'] = df['last_updated'].dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        df['amount_risked'] = pd.to_numeric(df['amount_risked'], errors='coerce').fillna(0.0).astype(float)
        df['potential_pnl'] = pd.to_numeric(df['potential_pnl'], errors='coerce').fillna(0.0).astype(float)
        df['status'] = df['status'].astype(str).str.strip().str.lower()

    return df

def calc_pnl(risk, odds):
    try:
        r, o = float(risk), float(odds)
        if o > 0: return r * (o / 100)
        elif o < 0: return r * (100 / abs(o))
    except: return 0.0
    return 0.0

# --- CONNECTION WITH CACHING (PREVENTS 429 ERROR) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def fetch_data(worksheet):
    df = conn.read(worksheet=worksheet, ttl=0)
    return normalize_dataframe(df, worksheet)

try:
    df_ledger = fetch_data("transactions")
    df_pending = fetch_data("pending")
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# --- CALCULATIONS ---
existing_books = sorted(df_ledger['book'].unique().tolist()) if not df_ledger.empty else ["Rebet", "Draftkings", "Fanduel"]

if not df_ledger.empty:
    df_calc = df_ledger.copy()
    df_calc['event_date'] = pd.to_datetime(df_calc['event_date'])
    
    # Metrics
    all_time_pnl = df_ledger['total_won'].sum()
    df_month = df_calc[(df_calc['event_date'].dt.month == now_local.month) & (df_calc['event_date'].dt.year == now_local.year)].copy()
    monthly_pnl = df_month['total_won'].sum()
    
    # Chart Logic
    daily_totals = df_month.groupby('event_date')['total_won'].sum().reset_index().sort_values('event_date')
    daily_totals['cumulative_pnl'] = daily_totals['total_won'].cumsum()
else:
    daily_totals = pd.DataFrame()
    monthly_pnl, all_time_pnl = 0.0, 0.0

# --- UI DISPLAY ---
st.title("💰 Bet Management")

# Metric Row
c1, c2 = st.columns(2)
c1.metric("All-Time PnL", f"${all_time_pnl:,.2f}")
c2.metric(f"{now_local.strftime('%B')} PnL", f"${monthly_pnl:,.2f}")

# Cumulative PnL Line Chart
if not daily_totals.empty:
    pnl_color = "green" if monthly_pnl >= 0 else "red"
    line = alt.Chart(daily_totals).mark_line(point=True, color=pnl_color).encode(
        x=alt.X('event_date:T', title='Date'),
        y=alt.Y('cumulative_pnl:Q', title='Cumulative PnL ($)'),
        tooltip=['event_date', 'cumulative_pnl']
    ).properties(height=300)
    st.altair_chart(line, use_container_width=True)

# --- STAGING AREA ---
if st.session_state.staged_bets:
    with st.container(border=True):
        st.subheader("📋 Staging Queue")
        df_stage = pd.DataFrame(st.session_state.staged_bets)
        st.dataframe(df_stage, use_container_width=True, hide_index=True)
        
        q_c1, q_c2 = st.columns([1, 5])
        if q_c1.button("🚀 Commit to Ledger", type="primary", use_container_width=True):
            with st.spinner("Batch writing to Sheets..."):
                final_df = pd.concat([df_ledger, df_stage], ignore_index=True)
                conn.update(worksheet="transactions", data=normalize_dataframe(final_df))
                st.session_state.staged_bets = []
                st.cache_data.clear()
                st.success("Ledger Updated!")
                st.rerun()
        if q_c2.button("🗑️ Clear Queue"):
            st.session_state.staged_bets = []
            st.rerun()

st.divider()
tab_bet, tab_bulk, tab_pending = st.tabs(["🎯 Single Bet", "📊 Bulk PnL", "⏳ Pending Sweats"])

# TAB 1: SINGLE BET
with tab_bet:
    with st.form("single_bet_form", border=True):
        col1, col2 = st.columns(2)
        with col1:
            sb_date = st.date_input("Date", value=st.session_state.sticky_date)
            sb_book = st.selectbox("Sportsbook", options=existing_books, index=None, placeholder="Select Book...")
        with col2:
            sb_risk = st.number_input("Risked ($)", min_value=0.0, step=1.0)
            sb_odds = st.number_input("American Odds", step=1, value=100)
        
        sb_c1, sb_c2, sb_c3 = st.columns(3)
        win_submit = sb_c1.form_submit_button("✅ Win (Stage)", use_container_width=True)
        loss_submit = sb_c2.form_submit_button("❌ Loss (Stage)", use_container_width=True)
        pend_submit = sb_c3.form_submit_button("⏳ Pending (Direct)", use_container_width=True)

        if win_submit or loss_submit or pend_submit:
            if sb_book and sb_risk > 0:
                p_win = calc_pnl(sb_risk, sb_odds)
                if pend_submit:
                    new_pending = pd.DataFrame([{
                        "event_date": sb_date.strftime('%Y-%m-%d'), "book": sb_book,
                        "amount_risked": float(sb_risk), "odds": int(sb_odds),
                        "potential_pnl": float(p_win), "status": "pending"
                    }])
                    conn.update(worksheet="pending", data=normalize_dataframe(pd.concat([df_pending, new_pending], ignore_index=True), "pending"))
                    st.cache_data.clear()
                    st.rerun()
                else:
                    final_pnl = float(p_win) if win_submit else -float(sb_risk)
                    st.session_state.staged_bets.append({
                        "event_date": sb_date.strftime('%Y-%m-%d'),
                        "book": sb_book, "timeframe_type": "single",
                        "total_won": final_pnl,
                        "last_updated": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    st.rerun()

# TAB 2: BULK PNL
with tab_bulk:
    with st.form("bulk_pnl_form", border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            b_date = st.date_input("Date", value=st.session_state.sticky_date)
            b_type = st.selectbox("Type", ["daily", "bulk", "monthly"])
        with col_b:
            b_book = st.selectbox("Sportsbook", options=existing_books, index=None, placeholder="Select Book...")
            b_pnl  = st.number_input("Net PnL ($)", step=0.01, format="%.2f")
        
        if st.form_submit_button("Add to Queue", use_container_width=True):
            if b_book and b_pnl != 0:
                st.session_state.staged_bets.append({
                    "event_date": b_date.strftime('%Y-%m-%d'),
                    "book": b_book, "timeframe_type": b_type,
                    "total_won": float(b_pnl),
                    "last_updated": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S')
                })
                st.rerun()

# TAB 3: PENDING
with tab_pending:
    if not df_pending.empty:
        df_p_clean = df_pending.copy()
        df_p_clean['display'] = df_p_clean['book'] + " ($" + df_p_clean['amount_risked'].astype(str) + ")"
        selected_idx = st.selectbox("Resolve", options=df_p_clean.index, format_func=lambda x: df_p_clean.loc[x, 'display'])
        res1, res2 = st.columns(2)
        
        if res1.button("🏆 WIN SWEAT", width="stretch"):
            sel = df_p_clean.loc[selected_idx]
            st.session_state.staged_bets.append({
                "event_date": sel['event_date'], "book": sel['book'], "timeframe_type": "daily",
                "total_won": float(sel['potential_pnl']), "last_updated": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S')
            })
            conn.update(worksheet="pending", data=normalize_dataframe(df_p_clean.drop(selected_idx).drop(columns=['display']), "pending"))
            st.cache_data.clear()
            st.rerun()
            
        st.dataframe(df_pending, use_container_width=True)
    else:
        st.info("No active sweats.")

# PREVIEW LEDGER
st.divider()
st.subheader("Live Ledger (Top 10)")
if not df_ledger.empty:
    st.dataframe(df_ledger.sort_values('last_updated', ascending=False).head(10), use_container_width=True, hide_index=True)