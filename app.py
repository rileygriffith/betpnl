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
    """Initialize SQLite database with transactions and bets tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Aggregate transactions table (book P&L by day)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            event_date DATE NOT NULL,
            book TEXT NOT NULL,
            total_risked REAL NOT NULL DEFAULT 0,
            total_won REAL NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_date, book)
        )
    """)
    
    # Individual bets table (single bet level data)
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

def upsert_transaction(event_date, book, risked, won):
    """
    Insert or update a transaction using UPSERT logic.
    Increments total_risked and total_won for the given (event_date, book) pair.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(event_date, book) DO UPDATE SET
            total_risked = total_risked + ?,
            total_won = total_won + ?,
            last_updated = CURRENT_TIMESTAMP
    """, (event_date, book, risked, won, risked, won))
    
    conn.commit()
    conn.close()

def get_all_transactions():
    """Fetch all transactions from the database as a DataFrame."""
    conn = get_db_connection()
    query = "SELECT event_date, book, total_risked, total_won, last_updated FROM transactions ORDER BY event_date DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        df['event_date'] = pd.to_datetime(df['event_date'])
        df['net_profit'] = df['total_won'] - df['total_risked']
    
    return df

def delete_transaction(event_date, book):
    """Delete a transaction by event_date and book."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE event_date = ? AND book = ?", (event_date, book))
    
    conn.commit()
    conn.close()

def update_transaction(event_date, book, total_risked, total_won):
    """Update a transaction with new values."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE transactions 
        SET total_risked = ?, total_won = ?, last_updated = CURRENT_TIMESTAMP
        WHERE event_date = ? AND book = ?
    """, (total_risked, total_won, event_date, book))
    
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
    """Get today's P&L stats."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for today
    cursor.execute("""
        SELECT SUM(total_risked) as total_risked, SUM(total_won) as total_won
        FROM transactions
        WHERE event_date = ?
    """, (today,))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for today
    cursor.execute("""
        SELECT SUM(amount_risked) as total_risked, SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date = ? AND status != 'open'
    """, (today,))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results
    total_risked = (trans_result[0] or 0) + (bets_result[0] or 0)
    total_won = (trans_result[1] or 0)
    total_pnl = (bets_result[1] or 0) if bets_result[1] else 0
    
    if trans_result[0] and trans_result[1]:
        total_pnl += (trans_result[1] - trans_result[0])
    
    return {
        'total_risked': total_risked,
        'total_pnl': total_pnl,
        'roi': (total_pnl / total_risked * 100) if total_risked > 0 else 0
    }

def get_week_stats():
    """Get this week's P&L stats."""
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for the week
    cursor.execute("""
        SELECT SUM(total_risked) as total_risked, SUM(total_won) as total_won
        FROM transactions
        WHERE event_date >= ? AND event_date <= ?
    """, (week_start, today_str))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for the week
    cursor.execute("""
        SELECT SUM(amount_risked) as total_risked, SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date >= ? AND event_date <= ? AND status != 'open'
    """, (week_start, today_str))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results
    total_risked = (trans_result[0] or 0) + (bets_result[0] or 0)
    total_won = (trans_result[1] or 0)
    total_pnl = (bets_result[1] or 0) if bets_result[1] else 0
    
    if trans_result[0] and trans_result[1]:
        total_pnl += (trans_result[1] - trans_result[0])
    
    return {
        'total_risked': total_risked,
        'total_pnl': total_pnl,
        'roi': (total_pnl / total_risked * 100) if total_risked > 0 else 0
    }

def get_month_stats():
    """Get this month's P&L stats."""
    today = datetime.now()
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregate transactions for the month
    cursor.execute("""
        SELECT SUM(total_risked) as total_risked, SUM(total_won) as total_won
        FROM transactions
        WHERE event_date >= ? AND event_date <= ?
    """, (month_start, today_str))
    
    trans_result = cursor.fetchone()
    
    # Settled bets for the month
    cursor.execute("""
        SELECT SUM(amount_risked) as total_risked, SUM(pnl) as total_pnl
        FROM bets
        WHERE event_date >= ? AND event_date <= ? AND status != 'open'
    """, (month_start, today_str))
    
    bets_result = cursor.fetchone()
    
    conn.close()
    
    # Combine results
    total_risked = (trans_result[0] or 0) + (bets_result[0] or 0)
    total_won = (trans_result[1] or 0)
    total_pnl = (bets_result[1] or 0) if bets_result[1] else 0
    
    if trans_result[0] and trans_result[1]:
        total_pnl += (trans_result[1] - trans_result[0])
    
    return {
        'total_risked': total_risked,
        'total_pnl': total_pnl,
        'roi': (total_pnl / total_risked * 100) if total_risked > 0 else 0
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
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "📝 Enter Bets", "📋 Ledger"],
        label_visibility="collapsed"
    )
    
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
    week_stats = get_week_stats()
    month_stats = get_month_stats()
    
    # Display KPI cards
    st.subheader("Performance Overview")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Today")
        st.metric("P&L", f"${today_stats['total_pnl']:,.2f}")
        st.metric("Risked", f"${today_stats['total_risked']:,.2f}")
        st.metric("ROI %", f"{today_stats['roi']:.2f}%")
    
    with col2:
        st.subheader("This Week")
        st.metric("P&L", f"${week_stats['total_pnl']:,.2f}")
        st.metric("Risked", f"${week_stats['total_risked']:,.2f}")
        st.metric("ROI %", f"{week_stats['roi']:.2f}%")
    
    with col3:
        st.subheader("This Month")
        st.metric("P&L", f"${month_stats['total_pnl']:,.2f}")
        st.metric("Risked", f"${month_stats['total_risked']:,.2f}")
        st.metric("ROI %", f"{month_stats['roi']:.2f}%")
    
    st.divider()
    
    # Get all transactions for charts
    df_trans = get_all_transactions()
    df_bets = get_all_bets()
    
    if not df_trans.empty or not df_bets.empty:
        st.subheader("Cumulative Profit/Loss Over Time")
        
        # Combine transactions and settled bets data
        combined_data = []
        
        if not df_trans.empty:
            for idx, row in df_trans.iterrows():
                combined_data.append({
                    'date': row['event_date'],
                    'pnl': row['net_profit']
                })
        
        if not df_bets.empty:
            settled_bets = df_bets[df_bets['status'] != 'open']
            for idx, row in settled_bets.iterrows():
                combined_data.append({
                    'date': row['event_date'],
                    'pnl': row['pnl'] if row['pnl'] else 0
                })
        
        if combined_data:
            combined_df = pd.DataFrame(combined_data)
            combined_df = combined_df.sort_values('date')
            combined_df['cumulative_pnl'] = combined_df['pnl'].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=combined_df['date'],
                y=combined_df['cumulative_pnl'],
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
            
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=book_df['book'],
                x=book_df['pnl'],
                orientation='h',
                marker=dict(color=colors),
                text=book_df['pnl'].apply(lambda x: f"${x:.2f}"),
                textposition='outside'
            ))
            
            fig2.update_layout(
                xaxis_title="Net P&L ($)",
                yaxis_title="Sportsbook",
                hovermode='y',
                template='plotly_white',
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No bets recorded yet. Head to Enter Bets to start tracking.")

elif page == "📝 Enter Bets":
    # ====================================================================
    # PAGE 2: DATA ENTRY (Both modes on same page)
    # ====================================================================
    
    st.header("📝 Enter Bets")
    
    col_pnl, col_bet = st.columns(2)
    
    # ====================================================================
    # PANEL 1: Book P&L Entry
    # ====================================================================
    with col_pnl:
        st.subheader("Book P&L")
        st.write("Daily profit/loss for a book")
        
        with st.form("book_pnl_form", clear_on_submit=True):
            event_date_pnl = st.date_input(
                "Event Date",
                value=datetime.now().date(),
                key="pnl_date"
            )
            book_name_pnl = st.text_input(
                "Sportsbook Name",
                placeholder="e.g., DraftKings",
                key="pnl_book"
            )
            risked_amount = st.number_input(
                "Total Risked ($)",
                min_value=0.0,
                step=1.0,
                value=None,
                key="pnl_risked"
            )
            won_amount = st.number_input(
                "Total Won ($)",
                min_value=0.0,
                step=1.0,
                value=None,
                key="pnl_won"
            )
            
            # Real-time preview
            if risked_amount is not None and won_amount is not None:
                net_pnl = won_amount - risked_amount
                if net_pnl >= 0:
                    st.success(f"**Net P&L: +${net_pnl:.2f}**", icon="✅")
                else:
                    st.error(f"**Net P&L: ${net_pnl:.2f}**", icon="❌")
            
            submitted_pnl = st.form_submit_button("📤 Submit P&L", use_container_width=True)
            
            if submitted_pnl:
                if not book_name_pnl.strip():
                    st.error("Please enter a sportsbook name.")
                elif risked_amount is None or won_amount is None:
                    st.error("Please enter both amounts.")
                elif risked_amount == 0 and won_amount == 0:
                    st.error("Please enter at least one non-zero amount.")
                else:
                    upsert_transaction(
                        str(event_date_pnl),
                        book_name_pnl.strip(),
                        risked_amount,
                        won_amount
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
                "Bet Date",
                value=datetime.now().date(),
                key="bet_date"
            )
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
            amount_risked = st.number_input(
                "Amount Risked ($)",
                min_value=0.01,
                step=1.0,
                value=None,
                key="bet_risked"
            )
            american_odds = st.number_input(
                "American Odds",
                value=-110,
                step=10,
                key="bet_odds"
            )
            
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
            if amount_risked is not None and amount_risked > 0:
                if bet_status == "open":
                    st.info("💡 Potential return depends on outcome. Bet marked as open.")
                else:
                    if bet_status == "won":
                        pnl = calculate_pnl_from_odds(amount_risked, american_odds, True)
                        st.success(f"✅ **Payout: +${pnl:.2f}**")
                    else:
                        pnl = -amount_risked
                        st.error(f"❌ **Loss: ${pnl:.2f}**")
            
            submitted_bet = st.form_submit_button("📤 Submit Bet", use_container_width=True)
            
            if submitted_bet:
                if not book_name_bet.strip():
                    st.error("Please enter a sportsbook name.")
                elif amount_risked is None or amount_risked <= 0:
                    st.error("Amount risked must be greater than 0.")
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
            st.dataframe(display_trans, use_container_width=True, hide_index=True)
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
            st.dataframe(display_bets, use_container_width=True, hide_index=True)
        else:
            st.info("No bets yet.")

elif page == "📋 Ledger":
    # ====================================================================
    # PAGE 3: DATA MANAGEMENT
    # ====================================================================
    
    st.header("📋 Ledger")
    
    ledger_tab1, ledger_tab2 = st.tabs(["Transactions", "Individual Bets"])
    
    with ledger_tab1:
        st.subheader("Transaction Ledger")
        st.write("Manage your daily book P&L records.")
        
        df_trans = get_all_transactions()
        
        if not df_trans.empty:
            # Edit section
            st.write("**Edit Transactions**")
            
            edit_df = df_trans.copy()
            edit_df['event_date'] = edit_df['event_date'].dt.strftime('%Y-%m-%d')
            edit_df = edit_df[['event_date', 'book', 'total_risked', 'total_won', 'net_profit']]
            edit_df.columns = ['Date', 'Book', 'Risked ($)', 'Won ($)', 'Net Profit ($)']
            
            edited_df = st.data_editor(
                edit_df,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed"
            )
            
            if st.button("💾 Sync Changes", use_container_width=True, key="trans_sync"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM transactions")
                    
                    for idx, row in edited_df.iterrows():
                        cursor.execute("""
                            INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (row['Date'], row['Book'], row['Risked ($)'], row['Won ($)']))
                        
                        conn.commit()
                    
                    conn.close()
                    st.success("✅ Changes saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            
            st.divider()
            
            # Delete section
            st.write("**Delete Transactions**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_date = st.selectbox(
                    "Select Date",
                    options=sorted(edit_df['Date'].unique(), reverse=True),
                    key="trans_delete_date"
                )
            
            with col2:
                books_for_date = edited_df[edited_df['Date'] == selected_date]['Book'].unique().tolist()
                selected_book = st.selectbox(
                    "Select Book",
                    options=books_for_date,
                    key="trans_delete_book"
                )
            
            with col3:
                if st.button("🗑️ Delete", use_container_width=True, type="secondary", key="trans_delete_btn"):
                    delete_transaction(selected_date, selected_book)
                    st.success("✅ Deleted!")
                    st.rerun()
        
        else:
            st.info("No transactions yet.")
    
    with ledger_tab2:
        st.subheader("Individual Bets Ledger")
        st.write("Manage your individual bet records.")
        
        df_bets = get_all_bets()
        
        if not df_bets.empty:
            # Display all bets
            display_bets = df_bets.copy()
            display_bets['event_date'] = display_bets['event_date'].dt.strftime('%Y-%m-%d')
            display_bets = display_bets[['id', 'event_date', 'book', 'description', 'amount_risked', 'american_odds', 'status', 'pnl']]
            display_bets.columns = ['ID', 'Date', 'Book', 'Description', 'Risked ($)', 'Odds', 'Status', 'P&L ($)']
            
            st.dataframe(display_bets, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Update bet status
            st.write("**Update Bet Status**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                bet_to_update = st.selectbox(
                    "Select Bet",
                    options=df_bets['id'].tolist(),
                    format_func=lambda x: f"ID {x}: {df_bets[df_bets['id']==x]['description'].values[0] or 'No description'}",
                    key="bet_update_select"
                )
            
            with col2:
                new_status = st.selectbox(
                    "New Status",
                    ["open", "won", "lost"],
                    key="bet_update_status"
                )
            
            with col3:
                if st.button("✏️ Update", use_container_width=True, key="bet_update_btn"):
                    selected_bet = df_bets[df_bets['id'] == bet_to_update].iloc[0]
                    
                    pnl_value = None
                    if new_status != "open":
                        pnl_value = calculate_pnl_from_odds(
                            selected_bet['amount_risked'],
                            selected_bet['american_odds'],
                            new_status == "won"
                        )
                    
                    update_bet(bet_to_update, new_status, pnl_value)
                    st.success("✅ Bet updated!")
                    st.rerun()
            
            st.divider()
            
            # Delete bet
            st.write("**Delete Bet**")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                bet_to_delete = st.selectbox(
                    "Select Bet to Delete",
                    options=df_bets['id'].tolist(),
                    format_func=lambda x: f"ID {x}: {df_bets[df_bets['id']==x]['description'].values[0] or 'No description'}",
                    key="bet_delete_select"
                )
            
            with col2:
                if st.button("🗑️ Delete", use_container_width=True, type="secondary", key="bet_delete_btn"):
                    delete_bet(bet_to_delete)
                    st.success("✅ Deleted!")
                    st.rerun()
        
        else:
            st.info("No individual bets yet.")
