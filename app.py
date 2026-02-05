import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# ============================================================================
# DATABASE INITIALIZATION & UTILITIES
# ============================================================================

DB_PATH = "bet_tracker.db"

def init_db():
    """Initialize SQLite database with book_pnl and bets tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Book P&L table (simplified - just P&L, no risk tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date DATE NOT NULL,
            book TEXT NOT NULL,
            timeframe_type TEXT NOT NULL DEFAULT 'daily',
            pnl REAL NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_date, book, timeframe_type)
        )
    """)
    
    # Individual bets table (with full tracking - amount risked, odds, status)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date DATE NOT NULL,
            book TEXT NOT NULL,
            description TEXT,
            amount_risked REAL NOT NULL,
            american_odds REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            pnl REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# TRANSACTION UTILITIES (Book P&L)
# ============================================================================

def upsert_transaction(event_date, book, risked, won, timeframe_type='daily'):
    """
    Insert or update a transaction using UPSERT logic.
    Increments total_risked and total_won for the given (event_date, book, timeframe_type) tuple.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO transactions (event_date, book, timeframe_type, total_risked, total_won, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(event_date, book, timeframe_type) DO UPDATE SET
            total_risked = total_risked + ?,
            total_won = total_won + ?,
            last_updated = CURRENT_TIMESTAMP
    """, (event_date, book, timeframe_type, risked, won, risked, won))
    
    conn.commit()
    conn.close()

def get_all_transactions():
    """Fetch all transactions from the database as a DataFrame."""
    conn = get_db_connection()
    query = "SELECT event_date, book, timeframe_type, total_risked, total_won, last_updated FROM transactions ORDER BY event_date DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        df['event_date'] = pd.to_datetime(df['event_date'])
        df['net_profit'] = df['total_won'] - df['total_risked']
    
    return df

def delete_transaction(event_date, book, timeframe_type='daily'):
    """Delete a transaction by event_date, book, and timeframe_type."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE event_date = ? AND book = ? AND timeframe_type = ?", 
                   (event_date, book, timeframe_type))
    
    conn.commit()
    conn.close()

def update_transaction(event_date, book, total_risked, total_won, timeframe_type='daily'):
    """Update a transaction with new values."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE transactions 
        SET total_risked = ?, total_won = ?, last_updated = CURRENT_TIMESTAMP
        WHERE event_date = ? AND book = ? AND timeframe_type = ?
    """, (total_risked, total_won, event_date, book, timeframe_type))
    
    conn.commit()
    conn.close()

# ============================================================================
# BET UTILITIES (Individual Bets)
# ============================================================================

def calculate_pnl_from_odds(amount_risked, american_odds, won):
    """Calculate PnL from American odds and win/loss status."""
    if not won:
        return -amount_risked
    
    if american_odds > 0:
        # Positive odds: profit = amount_risked * (odds / 100)
        return amount_risked * (american_odds / 100)
    else:
        # Negative odds: profit = amount_risked / (-odds / 100)
        return amount_risked / (-american_odds / 100)

def check_for_recent_duplicate(amount_risked, days_back=7):
    """Check if a similar non-round bet amount was recently placed (within X days)."""
    # Only flag non-round numbers (more likely to be duplicates)
    if amount_risked == int(amount_risked):
        return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT event_date, book, amount_risked 
        FROM bets
        WHERE amount_risked = ? AND event_date >= ?
        ORDER BY event_date DESC
        LIMIT 1
    """, (amount_risked, cutoff_date))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'date': result[0],
            'book': result[1],
            'amount': result[2]
        }
    
    return None

def insert_bet(event_date, book, description, amount_risked, american_odds, status, pnl=None):
    """Insert a new individual bet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO bets (event_date, book, description, amount_risked, american_odds, status, pnl, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (event_date, book, description, amount_risked, american_odds, status, pnl))
    
    conn.commit()
    conn.close()

def get_all_bets():
    """Fetch all bets from the database as a DataFrame."""
    conn = get_db_connection()
    query = """
        SELECT id, event_date, book, description, amount_risked, american_odds, status, pnl, last_updated 
        FROM bets 
        ORDER BY event_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        df['event_date'] = pd.to_datetime(df['event_date'])
    
    return df

def update_bet(bet_id, status, pnl):
    """Update a bet's status and PnL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE bets 
        SET status = ?, pnl = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, pnl, bet_id))
    
    conn.commit()
    conn.close()

def delete_bet(bet_id):
    """Delete a bet by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM bets WHERE id = ?", (bet_id,))
    
    conn.commit()
    conn.close()

# ============================================================================
# ANALYTICS UTILITIES
# ============================================================================

def get_today_stats():
    """Get today's P&L stats (daily entries only)."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for today (daily entries only)
    cursor.execute("""
        SELECT SUM(total_won) as total_pnl
        FROM transactions
        WHERE event_date = ? AND timeframe_type = 'daily'
    """, (today,))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for today
    cursor.execute("""
        SELECT SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date = ? AND status != 'open'
    """, (today,))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results (total_won already contains P&L)
    total_pnl = (trans_result[0] or 0) + (bets_result[0] or 0)
    
    return {
        'total_risked': 0,
        'total_pnl': total_pnl,
        'roi': 0
    }

def get_week_stats():
    """Get this week's P&L stats (daily and weekly entries only)."""
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for the week (daily and weekly entries only)
    cursor.execute("""
        SELECT SUM(total_won) as total_pnl
        FROM transactions
        WHERE event_date >= ? AND event_date <= ? AND timeframe_type IN ('daily', 'weekly')
    """, (week_start, today_str))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for the week
    cursor.execute("""
        SELECT SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date >= ? AND event_date <= ? AND status != 'open'
    """, (week_start, today_str))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results (total_won already contains P&L)
    total_pnl = (trans_result[0] or 0) + (bets_result[0] or 0)
    
    return {
        'total_risked': 0,
        'total_pnl': total_pnl,
        'roi': 0
    }

def get_month_stats():
    """Get this month's P&L stats (daily, weekly, and monthly entries only)."""
    today = datetime.now()
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for the month (daily, weekly, and monthly entries only)
    cursor.execute("""
        SELECT SUM(total_won) as total_pnl
        FROM transactions
        WHERE event_date >= ? AND event_date <= ? AND timeframe_type IN ('daily', 'weekly', 'monthly')
    """, (month_start, today_str))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for the month
    cursor.execute("""
        SELECT SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date >= ? AND event_date <= ? AND status != 'open'
    """, (month_start, today_str))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results (total_won already contains P&L)
    total_pnl = (trans_result[0] or 0) + (bets_result[0] or 0)
    
    return {
        'total_risked': 0,
        'total_pnl': total_pnl,
        'roi': 0
    }

def get_alltime_stats():
    """Get all-time P&L stats (all timeframes)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate all transactions (all timeframes)
    cursor.execute("""
        SELECT SUM(total_won) as total_pnl
        FROM transactions
    """)
    
    trans_result = cursor.fetchone()
    
    # All settled bets
    cursor.execute("""
        SELECT SUM(pnl) as total_pnl
        FROM bets
        WHERE status != 'open'
    """)
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results (total_won already contains P&L)
    total_pnl = (trans_result[0] or 0) + (bets_result[0] or 0)
    
    return {
        'total_risked': 0,
        'total_pnl': total_pnl,
        'roi': 0
    }

# ============================================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Betting Tracker",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database on first load
init_db()

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================

with st.sidebar:
    st.title("🎰 Betting Tracker")
    
    if st.button("📊 Dashboard", width='stretch', key="nav_dashboard"):
        st.session_state.page = "📊 Dashboard"
    if st.button("📝 Enter", width='stretch', key="nav_enter"):
        st.session_state.page = "📝 Enter Bets"
    if st.button("📋 Data", width='stretch', key="nav_ledger"):
        st.session_state.page = "📋 Ledger"
    
    if "page" not in st.session_state:
        st.session_state.page = "📊 Dashboard"
    
    page = st.session_state.page
    
    st.divider()
    
    st.subheader("ℹ️ About")
    st.write(
        """
        **Rapid-Entry Betting Tracker**
        
        Track your sports bets across multiple books with real-time analytics.
        
        **Features:**
        - ⚡ Fast data entry
        - 📊 Performance by timeframe
        - 📈 Individual bet tracking
        - 💾 Local SQLite database
        """
    )

# ============================================================================
# PAGE ROUTING
# ============================================================================

if page == "📊 Dashboard":
    # ====================================================================
    # PAGE 1: DASHBOARD (Analytics)
    # ====================================================================
    
    st.header("📊 Dashboard")
    
    # Get stats for different timeframes
    today_stats = get_today_stats()
    month_stats = get_month_stats()
    alltime_stats = get_alltime_stats()
    
    # Display KPI cards
    st.subheader("Performance Overview")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Today")
        color = "green" if today_stats['total_pnl'] >= 0 else "red"
        st.markdown(f"<h3 style='color: {color};'>${today_stats['total_pnl']:,.2f}</h3>", unsafe_allow_html=True)
    
    with col2:
        st.subheader("This Month")
        color = "green" if month_stats['total_pnl'] >= 0 else "red"
        st.markdown(f"<h3 style='color: {color};'>${month_stats['total_pnl']:,.2f}</h3>", unsafe_allow_html=True)
    
    with col3:
        st.subheader("All Time")
        color = "green" if alltime_stats['total_pnl'] >= 0 else "red"
        st.markdown(f"<h3 style='color: {color};'>${alltime_stats['total_pnl']:,.2f}</h3>", unsafe_allow_html=True)
    
    st.divider()
    
    # Get all transactions for charts
    df_trans = get_all_transactions()
    df_bets = get_all_bets()
    
    if not df_trans.empty or not df_bets.empty:
        st.subheader("Cumulative Profit/Loss Over Time (Latest Month)")
        
        # Filter to only last month's data
        today = datetime.now()
        month_ago = today - timedelta(days=30)
        
        # Combine transactions and settled bets data
        combined_data = []
        
        if not df_trans.empty:
            recent_trans = df_trans[df_trans['event_date'] >= month_ago]
            for idx, row in recent_trans.iterrows():
                combined_data.append({
                    'date': row['event_date'],
                    'pnl': row['net_profit']
                })
        
        if not df_bets.empty:
            settled_bets = df_bets[df_bets['status'] != 'open']
            recent_bets = settled_bets[settled_bets['event_date'] >= month_ago]
            for idx, row in recent_bets.iterrows():
                combined_data.append({
                    'date': row['event_date'],
                    'pnl': row['pnl'] if row['pnl'] else 0
                })
        
        if combined_data:
            combined_df = pd.DataFrame(combined_data)
            # Aggregate P&L by date (sum all books for each day)
            daily_pnl = combined_df.groupby('date')['pnl'].sum().reset_index()
            daily_pnl = daily_pnl.sort_values('date')
            daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_pnl['date'],
                y=daily_pnl['cumulative_pnl'],
                mode='lines+markers',
                name='Cumulative P&L',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=6)
            ))
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Cumulative P&L ($)",
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Performance by Sportsbook")
        
        # Aggregate by book
        book_stats = []
        
        if not df_trans.empty:
            trans_by_book = df_trans.groupby('book').agg({
                'total_risked': 'sum',
                'net_profit': 'sum'
            }).reset_index()
            
            for idx, row in trans_by_book.iterrows():
                book_stats.append({
                    'book': row['book'],
                    'total_risked': row['total_risked'],
                    'pnl': row['net_profit']
                })
        
        if not df_bets.empty:
            bets_settled = df_bets[df_bets['status'] != 'open']
            if not bets_settled.empty:
                bets_by_book = bets_settled.groupby('book').agg({
                    'amount_risked': 'sum',
                    'pnl': 'sum'
                }).reset_index()
                
                for idx, row in bets_by_book.iterrows():
                    existing = [b for b in book_stats if b['book'] == row['book']]
                    if existing:
                        existing[0]['total_risked'] += row['amount_risked']
                        existing[0]['pnl'] += row['pnl'] if row['pnl'] else 0
                    else:
                        book_stats.append({
                            'book': row['book'],
                            'total_risked': row['amount_risked'],
                            'pnl': row['pnl'] if row['pnl'] else 0
                        })
        
        if book_stats:
            book_df = pd.DataFrame(book_stats).sort_values('pnl')
            
            colors = ['#d62728' if x < 0 else '#2ca02c' for x in book_df['pnl']]
            
            # Calculate appropriate height based on number of sportsbooks
            height = max(400, 50 + (40 * len(book_df)))
            
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=book_df['book'],
                x=book_df['pnl'],
                orientation='h',
                marker=dict(color=colors),
                text=book_df['pnl'].apply(lambda x: f"${x:.2f}"),
                textposition='outside',
                textfont=dict(size=12)
            ))
            
            fig2.update_layout(
                xaxis_title="Net P&L ($)",
                yaxis_title="Sportsbook",
                hovermode='y',
                template='plotly_white',
                height=height,
                showlegend=False,
                yaxis=dict(tickfont=dict(size=12))
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No bets recorded yet. Head to Enter Bets to start tracking.")

elif page == "📝 Enter Bets":
    # ====================================================================
    # PAGE 2: DATA ENTRY (Both modes on same page)
    # ====================================================================
    
    st.header("📝 Enter Bets")
    
    # Initialize all session state variables at page load
    # (before any form elements render)
    if 'last_pnl_date' not in st.session_state:
        st.session_state.last_pnl_date = datetime.now().date()
    if 'last_pnl_month' not in st.session_state:
        st.session_state.last_pnl_month = datetime.now().month
    if 'last_pnl_year' not in st.session_state:
        st.session_state.last_pnl_year = datetime.now().year
    if 'last_bet_date' not in st.session_state:
        st.session_state.last_bet_date = datetime.now().date()
    
    col_pnl, col_bet = st.columns(2)
    
    # ====================================================================
    # PANEL 1: Book P&L Entry
    # ====================================================================
    with col_pnl:
        st.subheader("Book P&L")
        st.write("Profit/loss for a book")
        
        # Timeframe selector (outside form so it can trigger rerun)
        timeframe = st.radio(
            "Timeframe",
            ["Daily", "Weekly", "Monthly", "Yearly"],
            horizontal=True,
            index=0,
            key="pnl_timeframe"
        )
        
        with st.form("book_pnl_form", clear_on_submit=True):
            # Show different inputs based on timeframe
            if timeframe == "Daily":
                event_date_pnl = st.date_input(
                    "Event Date",
                    value=st.session_state.last_pnl_date,
                    key="pnl_date_daily"
                )
                st.session_state.last_pnl_date = event_date_pnl
            elif timeframe == "Weekly":
                today = datetime.now().date()
                week_start = today - timedelta(days=today.weekday())
                event_date_pnl = st.date_input(
                    "Week Starting (Event Date)",
                    value=st.session_state.last_pnl_date,
                    key="pnl_date_weekly"
                )
                st.session_state.last_pnl_date = event_date_pnl
            elif timeframe == "Monthly":
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    month = st.number_input(
                        "Month (1-12)",
                        min_value=1,
                        max_value=12,
                        value=st.session_state.last_pnl_month,
                        key="pnl_month"
                    )
                    st.session_state.last_pnl_month = month
                with col_m2:
                    year = st.number_input(
                        "Year",
                        min_value=2000,
                        max_value=2100,
                        value=st.session_state.last_pnl_year,
                        key="pnl_year"
                    )
                    st.session_state.last_pnl_year = year
                event_date_pnl = datetime(int(year), int(month), 1).date()
            else:  # Yearly
                year = st.number_input(
                    "Year",
                    min_value=2000,
                    max_value=2100,
                    value=st.session_state.last_pnl_year,
                    key="pnl_year_yearly"
                )
                st.session_state.last_pnl_year = year
                event_date_pnl = datetime(int(year), 1, 1).date()
            
            book_name_pnl = st.text_input(
                "Sportsbook Name",
                placeholder="e.g., DraftKings",
                key="pnl_book"
            )
            pnl_input = st.text_input(
                "P&L ($)",
                placeholder="e.g., 50.00 or -25.50",
                key="pnl_amount"
            )
            
            # Convert to float
            pnl_amount = None
            if pnl_input.strip():
                try:
                    pnl_amount = float(pnl_input)
                except ValueError:
                    pnl_amount = None
            
            # Real-time preview
            if pnl_amount is not None:
                if pnl_amount >= 0:
                    st.success(f"**P&L: +${pnl_amount:.2f}**", icon="✅")
                else:
                    st.error(f"**P&L: ${pnl_amount:.2f}**", icon="❌")
            
            submitted_pnl = st.form_submit_button("📤 Submit P&L", width='stretch')
            
            if submitted_pnl:
                if not book_name_pnl.strip():
                    st.error("Please enter a sportsbook name.")
                elif pnl_amount is None:
                    st.error("Please enter a valid P&L amount.")
                else:
                    # For Book P&L: always set risked=0, won=pnl
                    timeframe_lower = timeframe.lower()
                    upsert_transaction(
                        str(event_date_pnl),
                        book_name_pnl.strip(),
                        0,
                        pnl_amount,
                        timeframe_lower
                    )
                    st.success(f"✅ P&L recorded: {book_name_pnl} on {event_date_pnl}")
                    st.rerun()
    
    # ====================================================================
    # PANEL 2: Individual Bet Entry
    # ====================================================================
    with col_bet:
        st.subheader("Individual Bet")
        st.write("Single bet with odds")
        
        with st.form("individual_bet_form", clear_on_submit=True):
            event_date_bet = st.date_input(
                "Event Date",
                value=st.session_state.last_bet_date,
                key="bet_date"
            )
            st.session_state.last_bet_date = event_date_bet
            book_name_bet = st.text_input(
                "Sportsbook",
                placeholder="e.g., DraftKings",
                key="bet_book"
            )
            description = st.text_input(
                "Bet Description",
                placeholder="e.g., NBA Parlay",
                key="bet_desc"
            )
            amount_risked_input = st.text_input(
                "Amount Risked ($)",
                placeholder="e.g., 50.00",
                key="bet_risked"
            )
            
            # Convert to float
            amount_risked = None
            if amount_risked_input.strip():
                try:
                    amount_risked = float(amount_risked_input)
                    if amount_risked <= 0:
                        amount_risked = None
                except ValueError:
                    amount_risked = None
            
            american_odds_input = st.text_input(
                "American Odds",
                value="-110",
                key="bet_odds"
            )
            
            # Convert to float
            american_odds = None
            if american_odds_input.strip():
                try:
                    american_odds = float(american_odds_input)
                except ValueError:
                    american_odds = None
            
            bet_status = st.radio(
                "Status",
                ["open", "won", "lost"],
                horizontal=True,
                key="bet_status"
            )
            
            # Check for duplicate amounts
            if amount_risked is not None and amount_risked > 0:
                duplicate = check_for_recent_duplicate(amount_risked)
                if duplicate:
                    st.warning(
                        f"⚠️ **Possible duplicate**: "
                        f"{duplicate['amount']} @ {duplicate['book']} on {duplicate['date']}"
                    )
            
            # Calculate potential payout
            if amount_risked is not None and amount_risked > 0 and american_odds is not None:
                if bet_status == "open":
                    st.info("💡 Potential return depends on outcome. Bet marked as open.")
                else:
                    if bet_status == "won":
                        pnl = calculate_pnl_from_odds(amount_risked, american_odds, True)
                        st.success(f"✅ **Payout: +${pnl:.2f}**")
                    else:
                        pnl = -amount_risked
                        st.error(f"❌ **Loss: ${pnl:.2f}**")
            
            submitted_bet = st.form_submit_button("📤 Submit Bet", width='stretch')
            
            if submitted_bet:
                if not book_name_bet.strip():
                    st.error("Please enter a sportsbook name.")
                elif amount_risked is None or amount_risked <= 0:
                    st.error("Please enter a valid amount risked.")
                elif american_odds is None:
                    st.error("Please enter valid American odds.")
                else:
                    pnl_value = None
                    if bet_status != "open":
                        pnl_value = calculate_pnl_from_odds(amount_risked, american_odds, bet_status == "won")
                    
                    insert_bet(
                        str(event_date_bet),
                        book_name_bet.strip(),
                        description if description.strip() else None,
                        amount_risked,
                        american_odds,
                        bet_status,
                        pnl_value
                    )
                    st.success(f"✅ Bet recorded: {book_name_bet} - ${amount_risked} @ {american_odds}")
                    st.rerun()
    
    # Display recent entries
    st.divider()
    st.subheader("Recent Entries")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Recent Transactions**")
        trans_df = get_all_transactions()
        if not trans_df.empty:
            display_trans = trans_df.copy()
            display_trans['event_date'] = display_trans['event_date'].dt.strftime('%Y-%m-%d')
            display_trans = display_trans[['event_date', 'book', 'total_risked', 'total_won', 'net_profit']].head(5)
            display_trans.columns = ['Date', 'Book', 'Risked', 'Won', 'P&L']
            st.dataframe(display_trans, width='stretch', hide_index=True)
        else:
            st.info("No transactions yet.")
    
    with col2:
        st.write("**Recent Individual Bets**")
        bets_df = get_all_bets()
        if not bets_df.empty:
            display_bets = bets_df.copy()
            display_bets['event_date'] = display_bets['event_date'].dt.strftime('%Y-%m-%d')
            display_bets = display_bets[['event_date', 'book', 'description', 'amount_risked', 'status']].head(5)
            display_bets.columns = ['Date', 'Book', 'Description', 'Risked', 'Status']
            st.dataframe(display_bets, width='stretch', hide_index=True)
        else:
            st.info("No bets yet.")

elif page == "📋 Ledger":
    # ====================================================================
    # PAGE 3: DATA MANAGEMENT
    # ====================================================================
    
    st.header("📋 Data")
    
    col_trans, col_bets = st.columns(2)
    
    # ====================================================================
    # Transactions Table with Edit/Delete
    # ====================================================================
    with col_trans:
        st.subheader("Transactions")
        
        df_trans = get_all_transactions()
        
        if not df_trans.empty:
            # Format for display
            display_trans = df_trans.copy()
            display_trans['event_date'] = display_trans['event_date'].dt.strftime('%Y-%m-%d')
            display_trans = display_trans[['event_date', 'book', 'timeframe_type', 'total_risked', 'total_won', 'net_profit']]
            display_trans.columns = ['Date', 'Book', 'Type', 'Risked', 'Won', 'P&L']
            
            # Editable table
            edited_trans = st.data_editor(
                display_trans,
                width='stretch',
                hide_index=True,
                key="trans_editor",
                num_rows="dynamic"
            )
            
            # Find deleted rows and delete them
            if len(edited_trans) < len(display_trans):
                deleted_rows = set(range(len(display_trans))) - set(edited_trans.index if hasattr(edited_trans, 'index') else range(len(edited_trans)))
                for idx in deleted_rows:
                    if idx < len(display_trans):
                        row = display_trans.iloc[idx]
                        delete_transaction(row['Date'], row['Book'], row['Type'])
                st.success("✅ Row deleted!")
                st.rerun()
            
            # Handle edits - compare with original
            if not edited_trans.equals(display_trans):
                for idx, row in edited_trans.iterrows():
                    if idx < len(display_trans):
                        orig = display_trans.iloc[idx]
                        if not row.equals(orig):
                            update_transaction(row['Date'], row['Book'], row['Risked'], row['Won'], row['Type'])
                st.success("✅ Changes saved!")
                st.rerun()
        else:
            st.info("No transactions yet")
    
    # ====================================================================
    # Individual Bets Table with Edit/Delete
    # ====================================================================
    with col_bets:
        st.subheader("Individual Bets")
        
        df_bets = get_all_bets()
        
        if not df_bets.empty:
            # Format for display
            display_bets = df_bets.copy()
            display_bets['event_date'] = display_bets['event_date'].dt.strftime('%Y-%m-%d')
            display_bets = display_bets[['id', 'event_date', 'book', 'amount_risked', 'american_odds', 'status']]
            display_bets.columns = ['ID', 'Date', 'Book', 'Risked', 'Odds', 'Status']
            
            # Editable table
            edited_bets = st.data_editor(
                display_bets,
                width='stretch',
                hide_index=True,
                key="bets_editor",
                num_rows="dynamic"
            )
            
            # Find deleted rows and delete them
            if len(edited_bets) < len(display_bets):
                deleted_rows = set(range(len(display_bets))) - set(edited_bets.index if hasattr(edited_bets, 'index') else range(len(edited_bets)))
                for idx in deleted_rows:
                    if idx < len(display_bets):
                        row = display_bets.iloc[idx]
                        delete_bet(int(row['ID']))
                st.success("✅ Row deleted!")
                st.rerun()
            
            # Handle edits
            for idx, row in edited_bets.iterrows():
                if idx < len(display_bets):
                    orig = display_bets.iloc[idx]
                    if not row.equals(orig):
                        # Recalculate P&L if status changed
                        pnl_value = None
                        if row['Status'] != "open":
                            pnl_value = calculate_pnl_from_odds(row['Risked'], row['Odds'], row['Status'] == "won")
                        
                        update_bet(int(row['ID']), row['Status'], pnl_value)
            
            if not edited_bets.equals(display_bets):
                st.success("✅ Changes saved!")
                st.rerun()
        else:
            st.info("No bets yet")
